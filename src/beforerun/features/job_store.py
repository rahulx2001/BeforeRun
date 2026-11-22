"""Bounded in-memory jobs, ownership checks, event cursors, and expiry.

Run exactly one application worker process. This store is intentionally ephemeral; a
restart or expiry never fabricates a recovered report or erases Gateway/provider copies.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from beforerun.features.budgets import Budget, ReviewError
from beforerun.features.compare import ComparisonView
from beforerun.features.contracts import (
    Assessment,
    Completion,
    ErrorCode,
    ErrorRecord,
    EventType,
    JobPhase,
    JobState,
    JobStatus,
    Report,
    ReviewEvent,
    ReviewInput,
)
from beforerun.features.settings import Settings


def opaque_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(18)}"


class IdempotencyConflict(Exception):
    pass


@dataclass(slots=True)
class ReviewRecord:
    status: JobStatus
    budget: Budget
    report: Report | None = None
    comparison: ComparisonView | None = None
    evidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[ErrorRecord] = field(default_factory=list)
    stop_reason: str | None = None
    events: list[ReviewEvent] = field(default_factory=list)
    event_sequence: int = 0
    pipeline_mode: str = "unverified"

    @property
    def review_id(self) -> str:
        return self.status.review_id

    @property
    def owner_id(self) -> str:
        return self.status.owner_id

    def public_status(self) -> dict[str, Any]:
        value = self.status.model_dump(mode="json", exclude={"owner_id"})
        value.update(
            {
                "report": self.report.model_dump(mode="json") if self.report else None,
                "comparison": self.comparison.model_dump(mode="json") if self.comparison else None,
                "errors": [error.model_dump(mode="json") for error in self.errors],
                "stop_reason": self.stop_reason,
                "ephemeral": True,
                "pipeline_mode": self.pipeline_mode,
            }
        )
        return value


class JobStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.records: dict[str, ReviewRecord] = {}
        self.idempotency: dict[tuple[str, str], tuple[str, str]] = {}
        self._lock = asyncio.Lock()

    def _prune(self) -> None:
        now = datetime.now(UTC)
        expired = [
            review_id
            for review_id, record in self.records.items()
            if (now - record.status.updated_at).total_seconds() > self.settings.job_ttl_seconds
        ]
        for review_id in expired:
            self.records[review_id].budget.cancel_event.set()
            del self.records[review_id]
        self.idempotency = {
            key: value for key, value in self.idempotency.items() if value[0] in self.records
        }

    def _event(
        self,
        record: ReviewRecord,
        event_type: EventType,
        message: str,
        data: dict[str, str | int | bool] | None = None,
    ) -> ReviewEvent:
        record.event_sequence += 1
        event = ReviewEvent(
            sequence=record.event_sequence,
            review_id=record.review_id,
            event_type=event_type,
            timestamp=datetime.now(UTC),
            message=message,
            data=data or {},
        )
        if len(record.events) >= 500:
            for index, old in enumerate(record.events):
                if old.event_type is not EventType.TERMINAL:
                    del record.events[index]
                    break
        record.events.append(event)
        return event

    async def create(
        self,
        owner_id: str,
        intake: ReviewInput,
        idempotency_key: str | None,
    ) -> tuple[ReviewRecord, bool]:
        async with self._lock:
            self._prune()
            if len(self.records) >= 128:
                terminal = sorted(
                    (
                        record
                        for record in self.records.values()
                        if record.status.state is JobState.TERMINAL
                    ),
                    key=lambda record: record.status.updated_at,
                )
                if not terminal:
                    raise ReviewError(ErrorCode.ADMISSION_LIMIT, "The ephemeral job store is full.")
                del self.records[terminal[0].review_id]
                self.idempotency = {
                    key: value
                    for key, value in self.idempotency.items()
                    if value[0] in self.records
                }
            fingerprint = hashlib.sha256(intake.model_dump_json().encode("utf-8")).hexdigest()
            if idempotency_key:
                existing = self.idempotency.get((owner_id, idempotency_key))
                if existing:
                    review_id, previous_fingerprint = existing
                    if previous_fingerprint != fingerprint:
                        raise IdempotencyConflict(
                            "This idempotency key already names a different request."
                        )
                    return self.records[review_id], True
            active = sum(
                record.status.state is not JobState.TERMINAL for record in self.records.values()
            )
            if active >= self.settings.max_active_reviews + self.settings.max_queued_reviews:
                raise ReviewError(
                    ErrorCode.ADMISSION_LIMIT,
                    "The local review queue is full. Retry after an active review finishes.",
                )
            now = datetime.now(UTC)
            review_id = opaque_id("review")
            budget = Budget(self.settings)
            status = JobStatus(
                review_id=review_id,
                owner_id=owner_id,
                state=JobState.QUEUED,
                phase=JobPhase.ACCEPTED,
                review_input=intake,
                created_at=now,
                updated_at=now,
            )
            record = ReviewRecord(status=status, budget=budget)
            self.records[review_id] = record
            if idempotency_key:
                self.idempotency[(owner_id, idempotency_key)] = (review_id, fingerprint)
            self._event(record, EventType.ACCEPTED, "Review accepted into the bounded local queue.")
            return record, False

    def owned(self, review_id: str, owner_id: str) -> ReviewRecord | None:
        self._prune()
        record = self.records.get(review_id)
        if record is None or not secrets.compare_digest(record.owner_id, owner_id):
            return None
        return record

    async def phase(self, record: ReviewRecord, phase: JobPhase, message: str) -> None:
        async with self._lock:
            if record.status.state is JobState.TERMINAL:
                return
            state = JobState.RUNNING if record.status.state is JobState.RUNNING else JobState.QUEUED
            record.status = record.status.model_copy(
                update={"phase": phase, "state": state, "updated_at": datetime.now(UTC)}
            )
            self._event(record, EventType.PHASE_CHANGED, message, {"phase": phase.value})

    async def record_event(self, record, kind, message, data) -> None:
        async with self._lock:
            if record.status.state is JobState.TERMINAL:
                return
            updates = {"updated_at": datetime.now(UTC)}
            if kind is EventType.PHASE_CHANGED and "phase" in data:
                phase = JobPhase(data["phase"])
                if phase is JobPhase.TERMINAL:
                    raise ValueError("only storage finalization can terminate a job")
                updates["phase"] = phase
            record.status = record.status.model_copy(update=updates)
            self._event(record, kind, message, data)

    async def start(self, record: ReviewRecord) -> None:
        async with self._lock:
            if record.status.state is JobState.TERMINAL:
                return
            record.status = record.status.model_copy(
                update={
                    "state": JobState.RUNNING,
                    "phase": JobPhase.RESOLVING,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._event(
                record,
                EventType.PHASE_CHANGED,
                "Source resolution started.",
                {"phase": "resolving"},
            )

    async def cancel(self, record: ReviewRecord) -> None:
        async with self._lock:
            if record.status.state is JobState.TERMINAL:
                return
            record.budget.cancel_event.set()
            record.status = record.status.model_copy(
                update={"cancel_requested": True, "updated_at": datetime.now(UTC)}
            )
            self._event(
                record,
                EventType.PHASE_CHANGED,
                "Cancellation requested; no new local work will be started. "
                "Upstream abort is unconfirmed.",
                {"cancel_requested": True},
            )

    async def succeed(
        self,
        record: ReviewRecord,
        report: Report,
        *,
        comparison: ComparisonView | None = None,
        evidence: dict[str, dict[str, Any]] | None = None,
        stop_reason: str | None = None,
        pipeline_mode: str = "unverified",
    ) -> None:
        async with self._lock:
            if record.status.state is JobState.TERMINAL:
                return
            if (
                report.review_id != record.review_id
                or report.review_input != record.status.review_input
            ):
                raise ReviewError(
                    ErrorCode.INVALID_MODEL_OUTPUT,
                    "The checked report identity does not match the admitted review.",
                )
            if record.budget.cancel_event.is_set():
                report = report.model_copy(
                    update={
                        "completion": Completion.CANCELLED,
                        "assessment": Assessment.UNDETERMINED
                        if report.assessment is Assessment.BENIGN
                        else report.assessment,
                    }
                )
            record.report = report
            record.comparison = comparison
            record.evidence = evidence or {}
            record.stop_reason = stop_reason
            record.pipeline_mode = pipeline_mode
            record.status = record.status.model_copy(
                update={
                    "state": JobState.TERMINAL,
                    "phase": JobPhase.TERMINAL,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._event(
                record,
                EventType.REPORT_VALIDATED,
                "The checked report was stored for its owning session.",
            )
            self._event(
                record,
                EventType.TERMINAL,
                "Review reached a terminal checked-report state.",
                {"assessment": report.assessment.value, "completion": report.completion.value},
            )

    async def fail(self, record: ReviewRecord, error: ErrorRecord, stop_reason: str) -> None:
        async with self._lock:
            if record.status.state is JobState.TERMINAL:
                return
            record.errors.append(error)
            record.stop_reason = stop_reason
            record.status = record.status.model_copy(
                update={
                    "state": JobState.TERMINAL,
                    "phase": JobPhase.TERMINAL,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._event(
                record,
                EventType.TERMINAL,
                error.message,
                {"code": error.code.value, "retryable": error.retryable},
            )

    async def event_page(
        self,
        record: ReviewRecord,
        after: int,
        limit: int = 100,
    ) -> dict[str, Any]:
        if after < 0 or after > record.event_sequence:
            raise ReviewError(ErrorCode.INVALID_INPUT, "The event cursor is invalid.")
        remaining = [event for event in record.events if event.sequence > after]
        truncated = bool(record.events and record.events[0].sequence > after + 1)
        page = remaining[:limit]
        next_cursor = page[-1].sequence if page else after
        return {
            "events": [event.model_dump(mode="json") for event in page],
            "next_cursor": next_cursor,
            "truncated": truncated,
            "terminal": record.status.state is JobState.TERMINAL,
        }
