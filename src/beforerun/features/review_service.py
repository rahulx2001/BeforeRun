"""HTTP-independent orchestration between a narrow checked-report pipeline and jobs."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from beforerun.features.budgets import Budget, BudgetExceeded, ReviewError
from beforerun.features.compare import ComparisonView
from beforerun.features.contracts import (
    Assessment,
    Completion,
    ErrorCode,
    ErrorRecord,
    Evidence,
    Report,
    ReviewInput,
)
from beforerun.features.gateway_policy import GatewayModelPolicy
from beforerun.features.job_store import JobStore, ReviewRecord
from beforerun.features.settings import Settings


class EvidenceView(BaseModel):
    """API-only source view; Agent A's evidence schema remains unchanged."""

    model_config = ConfigDict(extra="forbid")

    evidence: Evidence
    path: str = Field(min_length=1, max_length=4096)
    source_url: str = Field(min_length=1, max_length=4096)


class PipelineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report: Report
    comparison: ComparisonView | None = None
    evidence: tuple[EvidenceView, ...] = Field(default=(), max_length=500)
    stop_reason: str | None = Field(default=None, max_length=100)
    pipeline_mode: str = Field(default="unverified", max_length=80)


class ReviewPipeline(Protocol):
    async def run(
        self,
        review_id: str,
        intake: ReviewInput,
        budget: Budget,
        cancel_token: asyncio.Event,
    ) -> Report | PipelineResult: ...


class UnavailablePipeline:
    """Production-safe pre-SYNC-2 behavior: never substitutes a mock or static verdict."""

    async def run(
        self,
        review_id: str,
        intake: ReviewInput,
        budget: Budget,
        cancel_token: asyncio.Event,
    ) -> Report:
        raise ReviewError(
            ErrorCode.OPENCLAW_UNAVAILABLE,
            "The checked investigation pipeline is not connected. "
            "No source or model verdict was produced.",
        )


class ReviewService:
    def __init__(
        self,
        settings: Settings,
        pipeline: ReviewPipeline | None = None,
        *,
        reviews_enabled: bool = False,
        gateway_model_policy: GatewayModelPolicy | None = None,
    ) -> None:
        self.settings = settings
        self.gateway_model_policy = gateway_model_policy or GatewayModelPolicy.from_environment()
        self.pipeline = pipeline or UnavailablePipeline()
        self.reviews_enabled = reviews_enabled
        self.store = JobStore(settings)
        self._semaphore = asyncio.Semaphore(settings.max_active_reviews)
        self._tasks: set[asyncio.Task[None]] = set()

    @property
    def pipeline_connected(self) -> bool:
        return not isinstance(self.pipeline, UnavailablePipeline)

    async def submit(
        self,
        owner_id: str,
        intake: ReviewInput,
        idempotency_key: str | None = None,
    ) -> tuple[ReviewRecord, bool]:
        if not self.reviews_enabled:
            raise ReviewError(
                ErrorCode.OPENCLAW_UNAVAILABLE,
                "Review submission is disabled until the checked pipeline and release "
                "gates are enabled.",
            )
        record, replay = await self.store.create(owner_id, intake, idempotency_key)
        if not replay:
            task = asyncio.create_task(self._execute(record), name=f"beforerun:{record.review_id}")
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        return record, replay

    async def cancel(self, record: ReviewRecord) -> None:
        await self.store.cancel(record)

    async def _wait_for_slot(self, record: ReviewRecord) -> None:
        acquire = asyncio.create_task(self._semaphore.acquire())
        cancelled = asyncio.create_task(record.budget.cancel_event.wait())
        handed_off = False
        try:
            done, _ = await asyncio.wait(
                {acquire, cancelled},
                timeout=self.settings.queue_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if cancelled in done:
                raise ReviewError(
                    ErrorCode.REVIEW_CANCELLED,
                    "Review was cancelled while queued.",
                )
            if acquire not in done:
                raise ReviewError(
                    ErrorCode.ADMISSION_LIMIT,
                    "The review exceeded its queue-wait allowance.",
                )
            await acquire
            handed_off = True
        finally:
            cancelled.cancel()
            if not acquire.done():
                acquire.cancel()
            await asyncio.gather(acquire, cancelled, return_exceptions=True)
            if (
                not handed_off
                and acquire.done()
                and not acquire.cancelled()
                and acquire.exception() is None
            ):
                # The slot and the cancellation can complete in the same event-loop turn.
                self._semaphore.release()

    async def _execute(self, record: ReviewRecord) -> None:
        acquired = False
        try:
            await self._wait_for_slot(record)
            acquired = True
            await self.store.start(record)
            # Queue wait and the analysis deadline are separate allowances.
            record.budget.start()
            record.budget.check()
            remaining = record.budget.remaining_seconds
            if remaining <= 0:
                raise BudgetExceeded("The review exceeded its wall-clock deadline.")
            try:
                async with asyncio.timeout(remaining):
                    eventful = getattr(self.pipeline, "run_with_events", None)
                    args = (
                        record.review_id,
                        record.status.review_input,
                        record.budget,
                        record.budget.cancel_event,
                    )
                    if callable(eventful):

                        async def emit(kind, message, data):
                            await self.store.record_event(record, kind, message, data)

                        result = await eventful(*args, emit=emit)
                    else:
                        result = await self.pipeline.run(*args)
            except TimeoutError as error:
                raise BudgetExceeded("The review exceeded its wall-clock deadline.") from error
            normalized = (
                result if isinstance(result, PipelineResult) else PipelineResult(report=result)
            )
            try:
                record.budget.check()
            except ReviewError as interruption:
                if interruption.code not in {
                    ErrorCode.REVIEW_CANCELLED,
                    ErrorCode.BUDGET_EXHAUSTED,
                }:
                    raise
                report = normalized.report
                completion = (
                    Completion.CANCELLED
                    if interruption.code is ErrorCode.REVIEW_CANCELLED
                    else Completion.PARTIAL
                )
                coverage = report.coverage.model_copy(
                    update={
                        "errors": (
                            *report.coverage.errors,
                            ErrorRecord(
                                code=interruption.code,
                                message="Review interrupted; retained material is incomplete.",
                            ),
                        )[:100],
                        "budget": record.budget.usage(),
                    }
                )
                normalized = normalized.model_copy(
                    update={
                        "report": report.model_copy(
                            update={
                                "completion": completion,
                                "coverage": coverage,
                                "assessment": Assessment.UNDETERMINED
                                if report.assessment is Assessment.BENIGN
                                else report.assessment,
                            }
                        )
                    }
                )
            if normalized.report.review_id != record.review_id:
                raise ReviewError(
                    ErrorCode.INVALID_MODEL_OUTPUT,
                    "The checked report identity does not match the admitted review.",
                )
            if normalized.report.review_input != record.status.review_input:
                raise ReviewError(
                    ErrorCode.INVALID_MODEL_OUTPUT,
                    "The checked report input does not match the admitted review.",
                )
            evidence = {
                item.evidence.evidence_id: item.model_dump(mode="json")
                for item in normalized.evidence
            }
            await self.store.succeed(
                record,
                normalized.report,
                comparison=normalized.comparison,
                evidence=evidence,
                stop_reason=normalized.stop_reason,
                pipeline_mode=normalized.pipeline_mode,
            )
        except ReviewError as error:
            await self.store.fail(
                record,
                ErrorRecord(code=error.code, message=error.message, retryable=error.retryable),
                stop_reason="cancelled"
                if error.code is ErrorCode.REVIEW_CANCELLED
                else "pipeline_error",
            )
        except asyncio.CancelledError:
            await self.store.fail(
                record,
                ErrorRecord(
                    code=ErrorCode.REVIEW_CANCELLED, message="The local worker was stopped."
                ),
                stop_reason="cancelled",
            )
        except Exception:
            # Do not leak internal paths, upstream bodies, source, or credentials to the browser.
            await self.store.fail(
                record,
                ErrorRecord(
                    code=ErrorCode.INVALID_MODEL_OUTPUT,
                    message=(
                        "The checked pipeline ended without a valid report; "
                        "details stay in private diagnostics."
                    ),
                ),
                stop_reason="pipeline_error",
            )
        finally:
            if acquired:
                self._semaphore.release()

    async def close(self) -> None:
        for record in list(self.store.records.values()):
            record.budget.cancel_event.set()
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def evidence(self, record: ReviewRecord, evidence_id: str) -> dict[str, Any] | None:
        return record.evidence.get(evidence_id)

    def export(self, record: ReviewRecord) -> dict[str, Any] | None:
        if record.report is None:
            return None
        from beforerun.features.report import sanitize

        return sanitize(
            {
                "report": record.report.model_dump(mode="json"),
                "comparison": record.comparison.model_dump(mode="json")
                if record.comparison
                else None,
                "evidence": list(record.evidence.values()),
                "errors": [error.model_dump(mode="json") for error in record.errors],
                "gateway_model_policy": self.gateway_model_policy.public_data(),
                "model_processing": self.gateway_model_policy.disclosure,
                "privacy": {
                    "redaction": "Best-effort source redaction; review exports before sharing.",
                    "retention": (
                        "Explicit export only. App expiry does not erase Gateway, provider, "
                        "or recipient copies."
                    ),
                },
            }
        )
