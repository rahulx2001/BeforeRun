"""Policy-derived checked reports and explicit best-effort sanitized exports."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from beforerun.features.budgets import Budget, ReviewError
from beforerun.features.contracts import (
    Assessment,
    Completion,
    Coverage,
    ErrorCode,
    ErrorRecord,
    FetchStatus,
    RelationshipSupport,
    Report,
    RevisionSide,
    StopReason,
    ValidatedFinding,
)
from beforerun.features.evidence import redact
from beforerun.features.investigator import InvestigationOutcome
from beforerun.features.validate import ValidationContext, validate_finding

EXCLUSIONS = (
    "Runtime execution and full application control flow",
    "Registry dependencies and downloaded artifacts",
    "Native binaries, submodules and Git LFS objects",
    "Whole-repository safety and incident response",
)


def build_report(
    context: ValidationContext,
    outcome: InvestigationOutcome,
    budget: Budget,
    *,
    required_file_ids: frozenset[str] = frozenset(),
    assumptions: tuple[str, ...] = (),
    analysis_errors: tuple[ErrorRecord, ...] = (),
    unsupported: bool = False,
    previous_findings: tuple[ValidatedFinding, ...] = (),
    previous_assessment: Assessment = Assessment.UNDETERMINED,
) -> Report:
    ledger, snapshot = context.ledger, context.ledger.snapshot
    errors = list(outcome.errors) + list(analysis_errors)
    accepted = list(previous_findings)
    seen = {item.finding.finding_id for item in accepted}
    if outcome.candidate is not None:
        for finding in outcome.candidate.findings:
            try:
                if finding.finding_id in seen:
                    raise ReviewError(
                        ErrorCode.INVALID_MODEL_OUTPUT, "A candidate repeated a finding identity."
                    )
                checked = validate_finding(finding, context)
                accepted.append(checked)
                seen.add(finding.finding_id)
            except (ReviewError, ValueError) as error:
                errors.append(
                    ErrorRecord(
                        code=ErrorCode.INVALID_MODEL_OUTPUT,
                        message=error.message
                        if isinstance(error, ReviewError)
                        else "A proposed finding failed validation.",
                    )
                )
    records = snapshot.entries(blobs_only=True)
    selected = [stored for stored in records if stored.record.selected]
    fetched = [stored for stored in selected if stored.record.fetch_status is FetchStatus.FETCHED]
    shown = {item.file_id for key, item in ledger.evidence.items() if key in ledger.delivered}
    fully_shown = set()
    for key, evidence in ledger.evidence.items():
        if key not in ledger.delivered or evidence.parent_evidence_id:
            continue
        stored = snapshot.require_file(evidence.file_id)
        lines = (stored.text or "").splitlines() or [""]
        if (
            evidence.span.first_line == 1
            and evidence.span.first_column == 1
            and evidence.span.last_line == len(lines)
            and evidence.span.last_column == len(lines[-1].encode()) + 1
        ):
            fully_shown.add(evidence.file_id)
    unresolved = tuple(sorted(required_file_ids - fully_shown))
    inventory_complete = snapshot.inventory_complete.get(RevisionSide.TARGET, False) and all(
        snapshot.inventory_complete.values()
    )
    if context.comparison and context.comparison.requested and not context.comparison.complete:
        errors.append(
            ErrorRecord(
                code=ErrorCode.SOURCE_LIMIT,
                message="Requested comparison has source or inventory gaps.",
            )
        )
    for _ in list(snapshot.errors)[:20]:
        errors.append(
            ErrorRecord(
                code=ErrorCode.SOURCE_LIMIT,
                message="A required source surface was unread or excluded.",
            )
        )
    coverage = Coverage(
        inventory_complete=inventory_complete,
        listed_files=len(records),
        selected_files=len(selected),
        fetched_files=len(fetched),
        model_shown_files=len(shown),
        skipped_files=sum(item.record.fetch_status is FetchStatus.SKIPPED for item in selected),
        required_unresolved_files=unresolved[:500],
        excluded_surfaces=EXCLUSIONS,
        errors=tuple(errors)[:100],
        budget=budget.usage(),
    )
    interrupted = outcome.stop_reason in {StopReason.CANCELLED, StopReason.BUDGET_EXHAUSTED}
    complete = (
        outcome.candidate is not None
        and outcome.stop_reason is StopReason.FINISHED
        and inventory_complete
        and not unresolved
        and not errors
        and not unsupported
    )
    completion = (
        Completion.UNSUPPORTED
        if unsupported
        else Completion.CANCELLED
        if outcome.stop_reason is StopReason.CANCELLED
        else Completion.COMPLETE
        if complete
        else Completion.PARTIAL
        if fetched or accepted
        else Completion.FAILED
    )
    if accepted:
        proposed = outcome.candidate.assessment if outcome.candidate else previous_assessment
        if proposed is Assessment.MALICIOUS and any(
            item.validation.execution_context_support is RelationshipSupport.SUPPORTED
            for item in accepted
        ):
            assessment = Assessment.MALICIOUS
        elif proposed is Assessment.BENIGN and complete:
            assessment = Assessment.BENIGN
        else:
            assessment = Assessment.SUSPICIOUS
    else:
        assessment = (
            Assessment.BENIGN
            if complete and outcome.candidate.assessment is Assessment.BENIGN
            else Assessment.UNDETERMINED
        )
    if interrupted and not accepted:
        assessment = Assessment.UNDETERMINED
    settings = budget.settings
    report = Report(
        review_id=ledger.review_id,
        review_input=context.intake,
        target=snapshot.revisions[RevisionSide.TARGET],
        baseline=snapshot.revisions.get(RevisionSide.BASELINE),
        findings=tuple(accepted)[:8],
        assessment=assessment,
        completion=completion,
        assumptions=(
            "Selected source was read as data, never installed or executed.",
            "Static relationships do not prove runtime control flow.",
            *assumptions,
        )[:32],
        coverage=coverage,
        openclaw_version=settings.openclaw_version,
        model_route=settings.model_route,
        prompt_version=settings.prompt_version,
        tool_policy_version=settings.tool_policy_version,
        analyzer_version=settings.analyzer_version,
        created_at=datetime.now(UTC),
        duration_ms=budget.elapsed_ms,
        report_version=1,
    )
    return Report.model_validate(sanitize(report.model_dump(mode="json")))


def sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)[0]
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [sanitize(item) for item in value]
    return value


def export_json(report: Report) -> str:
    return json.dumps(sanitize(report.model_dump(mode="json")), ensure_ascii=False, indent=2)


def export_text(report: Report) -> str:
    lines = [
        f"BeforeRun: {report.target.canonical_owner}/{report.target.canonical_name}",
        f"Commit: {report.target.commit_sha}",
        f"Assessment: {report.assessment.value}; completion: {report.completion.value}",
        f"Context: {report.review_input.command_context.value}; source was not executed.",
    ]
    for item in report.findings:
        lines.append(item.display_summary)
        lines.append("References: " + ", ".join(item.finding.evidence_ids))
        lines.extend(item.validation.interpretation_notes)
    lines.extend("Excluded: " + item for item in report.coverage.excluded_surfaces)
    lines.extend("Gap: " + item.message for item in report.coverage.errors)
    return redact("\n".join(lines))[0]
