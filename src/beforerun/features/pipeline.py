"""Checked review façade for jobs. S05 analysis is an injected, trusted dependency."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

from beforerun.features.budgets import Budget, ReviewError
from beforerun.features.compare import (
    compare_inventories,
    failed_comparison,
    materialize_comparison,
)
from beforerun.features.contracts import (
    ErrorCode,
    ErrorRecord,
    EventType,
    JobPhase,
    Relationship,
    ReviewInput,
    RevisionSide,
    Signal,
    StopReason,
)
from beforerun.features.evidence import EvidenceLedger
from beforerun.features.github_source import GitHubSource, parse_repository_url
from beforerun.features.investigator import InvestigationOutcome, Investigator
from beforerun.features.openclaw_client import OpenClawClient
from beforerun.features.report import build_report
from beforerun.features.review_service import EvidenceView, PipelineResult
from beforerun.features.safe_tools import SnapshotTools
from beforerun.features.settings import Settings
from beforerun.features.snapshot import Snapshot
from beforerun.features.validate import ValidationContext

EventSink = Callable[[EventType, str, dict[str, str | int | bool]], Awaitable[None]]


@dataclass(frozen=True)
class AnalysisContext:
    seed_evidence_ids: tuple[str, ...] = ()
    required_file_ids: frozenset[str] = field(default_factory=frozenset)
    entry_evidence_ids: frozenset[str] = field(default_factory=frozenset)
    relationships: tuple[Relationship, ...] = ()
    assumptions: tuple[str, ...] = ()
    supported: bool = True
    signals: tuple[Signal, ...] = ()
    errors: tuple[ErrorRecord, ...] = ()


class AnalysisProvider(Protocol):
    async def analyze(
        self,
        intake: ReviewInput,
        snapshot: Snapshot,
        ledger: EvidenceLedger,
        budget: Budget,
    ) -> AnalysisContext: ...


class CheckedReviewPipeline:
    """No mock verdict fallback. Each invocation owns its source, ledger and transcript."""

    def __init__(
        self,
        settings: Settings,
        analyzer: AnalysisProvider | None = None,
        *,
        source_factory: Callable[[Budget], GitHubSource] | None = None,
        reviewer_factory: Callable[[], OpenClawClient] | None = None,
        mode: str = "configured_gateway",
        withhold_helper: bool = False,
    ) -> None:
        self.settings, self.analyzer, self.mode = settings, analyzer, mode
        self.withhold_helper = withhold_helper
        self.source_factory = source_factory or (lambda budget: GitHubSource(settings, budget))
        self.reviewer_factory = reviewer_factory or (lambda: OpenClawClient(settings))

    @classmethod
    def with_npm(cls, settings: Settings, **kwargs) -> "CheckedReviewPipeline":
        from beforerun.features.npm_setup import NpmSetupAnalyzer

        return cls(settings, NpmSetupAnalyzer(), **kwargs)

    async def run(
        self,
        review_id: str,
        intake: ReviewInput,
        budget: Budget,
        cancel_token: asyncio.Event,
    ) -> PipelineResult:
        return await self.run_with_events(review_id, intake, budget, cancel_token)

    async def run_with_events(
        self,
        review_id: str,
        intake: ReviewInput,
        budget: Budget,
        cancel_token: asyncio.Event,
        emit: EventSink | None = None,
    ) -> PipelineResult:
        if cancel_token is not budget.cancel_event:
            raise ValueError("pipeline cancellation must use the shared budget token")
        budget.check()
        source = self.source_factory(budget)
        reviewer = None

        async def event(kind: EventType, message: str, data: dict[str, Any]) -> None:
            if emit:
                await emit(kind, message, data)

        async def phase(value: JobPhase) -> None:
            budget.check()
            await event(
                EventType.PHASE_CHANGED, "Review phase: " + value.value, {"phase": value.value}
            )

        try:
            await phase(JobPhase.RESOLVING)
            owner, name = parse_repository_url(intake.repository_url)
            repository = await source.repository(owner, name)
            target = await source.pin(repository, intake.target_ref, RevisionSide.TARGET)
            revisions = {RevisionSide.TARGET: target}
            comparison_error = None
            await event(
                EventType.REVISION_PINNED,
                "Target revision pinned.",
                {"side": "target", "sha": target.commit_sha},
            )
            if intake.baseline_ref:
                try:
                    baseline = await source.pin(
                        repository, intake.baseline_ref, RevisionSide.BASELINE
                    )
                    revisions[RevisionSide.BASELINE] = baseline
                    await event(
                        EventType.REVISION_PINNED,
                        "Baseline revision pinned.",
                        {"side": "baseline", "sha": baseline.commit_sha},
                    )
                except ReviewError as error:
                    if error.code in {ErrorCode.REVIEW_CANCELLED, ErrorCode.BUDGET_EXHAUSTED}:
                        raise
                    comparison_error = "The requested baseline could not be resolved."
            await phase(JobPhase.INVENTORY)
            snapshot = Snapshot(revisions, source)
            for side, revision in revisions.items():
                budget.check()
                entries, truncated = await source.tree(revision)
                snapshot.register_tree(side, entries, truncated)
            ledger = EvidenceLedger(review_id, snapshot, self.settings)
            comparison = (
                failed_comparison(comparison_error)
                if comparison_error
                else compare_inventories(snapshot, baseline_requested=bool(intake.baseline_ref))
            )
            analysis = AnalysisContext(
                supported=False,
                assumptions=("Setup analyzer unavailable; execution context is unsupported.",),
            )
            outcome = InvestigationOutcome(None, StopReason.SOURCE_ERROR, (), ())
            try:
                await phase(JobPhase.STATIC_ANALYSIS)
                if self.analyzer:
                    analysis = await self.analyzer.analyze(intake, snapshot, ledger, budget)
                budget.check()
                relevant = {
                    snapshot.require_file(key).record.path for key in analysis.required_file_ids
                }
                comparison = await materialize_comparison(
                    snapshot, ledger, comparison, relevant, budget=budget
                )
                if analysis.supported:
                    await phase(JobPhase.INVESTIGATING)
                    reviewer = self.reviewer_factory()
                    tools = SnapshotTools(snapshot, ledger, budget, comparison)
                    seed_ids = list(analysis.seed_evidence_ids)
                    # Keep one relevant helper outside the seed. Its source must be
                    # requested, not counted as shown merely because static analysis read it.
                    for key in seed_ids if self.withhold_helper else ():
                        item = ledger.require(key)
                        path = snapshot.require_file(item.file_id).record.path
                        if key not in analysis.entry_evidence_ids and path not in {
                            "package.json",
                            ".npmrc",
                        }:
                            seed_ids.remove(key)
                            break
                    bounded_seeds = []
                    seed_bytes = 0
                    for key in seed_ids:
                        size = len(ledger.require(key).representation.encode("utf-8"))
                        if seed_bytes + size <= 48 * 1024 and len(bounded_seeds) < 32:
                            bounded_seeds.append(key)
                            seed_bytes += size
                    seed_ids = bounded_seeds
                    outcome = await Investigator(reviewer, tools).run(
                        seed_ids,
                        {
                            "command": intake.command_context.value,
                            "target_sha": target.commit_sha,
                            "assumptions": analysis.assumptions,
                            "relationships": [
                                item.model_dump(mode="json") for item in analysis.relationships
                            ],
                            "signals": [item.model_dump(mode="json") for item in analysis.signals],
                            "analysis_errors": [
                                item.model_dump(mode="json") for item in analysis.errors
                            ],
                            "required_files": [
                                {
                                    "file_id": item.record.file_id,
                                    "path": item.record.path,
                                    "fetch_status": item.record.fetch_status.value,
                                }
                                for item in sorted(
                                    (
                                        snapshot.require_file(key)
                                        for key in analysis.required_file_ids
                                    ),
                                    key=lambda item: item.record.path,
                                )[:64]
                            ],
                            "comparison": {
                                "requested": comparison.requested,
                                "complete": comparison.complete,
                                "error": comparison.error,
                                "entries_truncated": len(comparison.entries) > 40,
                                "entries": [
                                    {
                                        "file_pair_id": item.file_pair_id,
                                        "path": item.path,
                                        "change": item.change,
                                        "evidence_complete": item.evidence_complete,
                                        "evidence_gaps": list(item.evidence_gaps),
                                    }
                                    for item in comparison.entries[:40]
                                ],
                            },
                            "remaining_budget": {
                                "decision_turns": max(
                                    0,
                                    budget.settings.max_decision_turns - budget.decision_turns,
                                ),
                                "tool_operations": max(
                                    0,
                                    budget.settings.max_tool_operations - budget.tool_operations,
                                ),
                                "model_attempts": max(
                                    0,
                                    budget.settings.max_model_attempts - budget.model_attempts,
                                ),
                                "runtime_ms": max(0, int(budget.remaining_seconds * 1000)),
                            },
                            "available_files": [
                                {
                                    "file_id": item.record.file_id,
                                    "path": item.record.path,
                                    "side": snapshot.side_for(item).value,
                                }
                                for item in snapshot.entries(blobs_only=True)[:80]
                            ],
                        },
                    )
                if not budget.cancel_event.is_set() and budget.remaining_seconds > 0:
                    await phase(JobPhase.VALIDATING)
            except (ReviewError, asyncio.CancelledError) as error:
                cancelled = budget.cancel_event.is_set()
                code = ErrorCode.REVIEW_CANCELLED if cancelled else ErrorCode.BUDGET_EXHAUSTED
                if isinstance(error, ReviewError):
                    code = error.code
                stop = (
                    StopReason.CANCELLED
                    if code is ErrorCode.REVIEW_CANCELLED
                    else StopReason.BUDGET_EXHAUSTED
                    if code is ErrorCode.BUDGET_EXHAUSTED
                    else StopReason.SOURCE_ERROR
                )
                outcome = InvestigationOutcome(
                    None,
                    stop,
                    (
                        ErrorRecord(
                            code=code,
                            message="The bounded review stopped before final validation.",
                        ),
                    ),
                    (),
                )
            validation = ValidationContext(
                intake, ledger, analysis.relationships, analysis.entry_evidence_ids, comparison
            )
            report = build_report(
                validation,
                outcome,
                budget,
                required_file_ids=analysis.required_file_ids,
                assumptions=analysis.assumptions,
                analysis_errors=analysis.errors,
                unsupported=not analysis.supported,
            )
            for receipt in ledger.receipts:
                await event(
                    EventType.EVIDENCE_DELIVERED,
                    "Source representation supplied to the reviewer transcript.",
                    {"turn": receipt.turn, "items": len(receipt.items)},
                )
            for step in outcome.steps:
                if not step.accepted:
                    await event(
                        EventType.TOOL_REJECTED,
                        "An analyst operation was rejected.",
                        {"operation": step.requested_operation},
                    )
            return PipelineResult(
                report=report,
                comparison=comparison,
                stop_reason=outcome.stop_reason.value,
                evidence=tuple(
                    EvidenceView(
                        evidence=item,
                        path=snapshot.require_file(item.file_id).record.path,
                        source_url=ledger.link(item.evidence_id),
                    )
                    for item in list(ledger.evidence.values())[:500]
                ),
                pipeline_mode=self.mode,
            )
        finally:
            await source.close()
            if reviewer:
                await reviewer.close()
