"""Source, delivery, span, context, and comparison checks for each proposed finding."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from beforerun.features.budgets import ReviewError
from beforerun.features.compare import ComparisonView
from beforerun.features.contracts import (
    ChangeStatus,
    CommandContext,
    ErrorCode,
    Evidence,
    EvidenceKind,
    Finding,
    ReferenceValidation,
    Relationship,
    RelationshipSupport,
    ReviewInput,
    RevisionSide,
    ValidatedFinding,
)
from beforerun.features.evidence import EvidenceLedger, redact
from beforerun.features.safe_tools import static_decode


@dataclass(frozen=True)
class ValidationContext:
    intake: ReviewInput
    ledger: EvidenceLedger
    relationships: tuple[Relationship, ...] = ()
    entry_evidence_ids: frozenset[str] = field(default_factory=frozenset)
    comparison: ComparisonView | None = None


def checked_evidence(context: ValidationContext, evidence_id: str, depth: int = 0) -> Evidence:
    if depth > 2:
        raise ReviewError(
            ErrorCode.INVALID_MODEL_OUTPUT, "Derived evidence exceeds its provenance depth."
        )
    ledger = context.ledger
    evidence = ledger.require_delivered(evidence_id)
    stored = ledger.snapshot.require_file(evidence.file_id)
    revision = ledger.snapshot.revision_for(stored)
    if (
        evidence.revision_id != revision.revision_id
        or evidence.side is not revision.side
        or evidence.raw_sha256 != stored.record.raw_sha256
        or hashlib.sha256(evidence.representation.encode()).hexdigest()
        != evidence.representation_sha256
    ):
        raise ReviewError(
            ErrorCode.INVALID_MODEL_OUTPUT, "Evidence identity or representation is inconsistent."
        )
    if evidence.parent_evidence_id:
        parent = checked_evidence(context, evidence.parent_evidence_id, depth + 1)
        if (
            evidence.file_id != parent.file_id
            or evidence.span != parent.span
            or evidence.revision_id != parent.revision_id
        ):
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT,
                "Derived evidence has inconsistent original coordinates.",
            )
        if evidence.kind is EvidenceKind.DIFF:
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT,
                "Cite original-side evidence instead of diff display rows.",
            )
        if evidence.kind is EvidenceKind.DECODED:
            expected = redact(static_decode(parent.representation, evidence.decoding_operations))[0]
            if evidence.representation != expected:
                raise ReviewError(
                    ErrorCode.INVALID_MODEL_OUTPUT, "Decoded evidence does not match its parent."
                )
        if (
            evidence.kind is EvidenceKind.STRING
            and evidence.representation not in parent.representation
        ):
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT, "Literal evidence is absent from its parent."
            )
    else:
        if stored.text is None or not stored.record.line_map:
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT, "Evidence has no admitted original source."
            )
        lines = stored.text.splitlines() or [""]
        span = evidence.span
        if (
            span.last_line > len(lines)
            or span.first_column > len(lines[span.first_line - 1].encode()) + 1
            or span.last_column > len(lines[span.last_line - 1].encode()) + 1
        ):
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT, "Evidence exceeds its original source span."
            )
        selected = lines[span.first_line - 1 : span.last_line]
        try:
            if len(selected) == 1:
                original = (
                    selected[0]
                    .encode()[span.first_column - 1 : span.last_column - 1]
                    .decode("utf-8")
                )
            else:
                selected[0] = selected[0].encode()[span.first_column - 1 :].decode("utf-8")
                selected[-1] = selected[-1].encode()[: span.last_column - 1].decode("utf-8")
                original = "\n".join(selected)
        except UnicodeError as error:
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT, "Evidence columns split a source character."
            ) from error
        expected = redact(original)[0] if evidence.kind is EvidenceKind.REDACTED else original
        if evidence.representation != expected:
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT, "Evidence differs from its admitted source span."
            )
    return evidence


def _change_support(
    finding: Finding, context: ValidationContext
) -> tuple[ChangeStatus, RelationshipSupport]:
    comparison = context.comparison
    if not context.intake.baseline_ref:
        return ChangeStatus.NOT_COMPARED, RelationshipSupport.UNRESOLVED
    if comparison is None or comparison.error or not comparison.complete_within_inventory:
        return ChangeStatus.UNKNOWN, RelationshipSupport.UNRESOLVED
    quotes = [
        (context.ledger.require(quote.evidence_id), quote.exact_quote)
        for quote in finding.evidence_quotes
    ]
    target = [(item, text) for item, text in quotes if item.side is RevisionSide.TARGET]
    baseline = [(item, text) for item, text in quotes if item.side is RevisionSide.BASELINE]
    paths = {context.ledger.snapshot.require_file(item.file_id).record.path for item, _ in quotes}
    relevant = [entry for entry in comparison.entries if entry.path in paths]
    if not relevant or any(not entry.evidence_complete for entry in relevant):
        return ChangeStatus.UNKNOWN, RelationshipSupport.UNRESOLVED
    status = finding.change_status
    if status in {ChangeStatus.CHANGED, ChangeStatus.EXISTING} and target and baseline:
        paired = []
        for entry in relevant:
            old_quotes = {text for item, text in baseline if item.file_id == entry.baseline_file_id}
            new_quotes = {text for item, text in target if item.file_id == entry.target_file_id}
            if old_quotes and new_quotes:
                paired.append((old_quotes, new_quotes, entry))
        same_operation = bool(paired) and all(old == new for old, new, _ in paired)
        if status is ChangeStatus.EXISTING and same_operation:
            return status, RelationshipSupport.INFERRED
        if status is ChangeStatus.CHANGED and any(
            old != new and entry.change == "modified" for old, new, entry in paired
        ):
            return status, RelationshipSupport.INFERRED
    if (
        status is ChangeStatus.INTRODUCED
        and target
        and not baseline
        and any(entry.change == "added" for entry in relevant)
    ):
        return status, RelationshipSupport.INFERRED
    if (
        status is ChangeStatus.REMOVED
        and baseline
        and not target
        and any(entry.change == "removed" for entry in relevant)
    ):
        return status, RelationshipSupport.INFERRED
    return ChangeStatus.UNKNOWN, RelationshipSupport.UNRESOLVED


def validate_finding(finding: Finding, context: ValidationContext) -> ValidatedFinding:
    evidence = [checked_evidence(context, key) for key in finding.evidence_ids]
    if not finding.benign_explanation_considered.strip() or not finding.evidence_quotes:
        raise ReviewError(
            ErrorCode.INVALID_MODEL_OUTPUT,
            "A finding needs cited observations and a benign alternative.",
        )
    for quote in finding.evidence_quotes:
        if quote.evidence_id not in finding.evidence_ids:
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT, "A quote cites an unrelated finding reference."
            )
        item = checked_evidence(context, quote.evidence_id)
        if quote.exact_quote not in item.representation:
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT, "A finding quote is absent from delivered evidence."
            )
        if quote.first_original_line is not None:
            if (
                quote.first_original_line < item.span.first_line
                or quote.last_original_line > item.span.last_line
            ):
                raise ReviewError(
                    ErrorCode.INVALID_MODEL_OUTPUT, "A quote exceeds its issued original range."
                )
            if item.kind in {EvidenceKind.SOURCE, EvidenceKind.REDACTED}:
                offset = quote.first_original_line - item.span.first_line
                count = quote.last_original_line - quote.first_original_line + 1
                shown = "\n".join(item.representation.splitlines()[offset : offset + count])
                if quote.exact_quote not in shown:
                    raise ReviewError(
                        ErrorCode.INVALID_MODEL_OUTPUT, "A quote names the wrong original lines."
                    )
    relationships = {item.relationship_id: item for item in context.relationships}
    support = RelationshipSupport.UNRESOLVED
    checked_edges = []
    for key in finding.relationship_ids:
        relationship = relationships.get(key)
        if relationship is None:
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT, "A finding cited an unissued relationship."
            )
        caller = checked_evidence(context, relationship.caller_evidence_id)
        callee = checked_evidence(context, relationship.callee_evidence_id)
        if caller.side is not callee.side:
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT, "An execution edge mixes revision sides."
            )
        checked_edges.append((relationship, caller, callee))
    rank = {
        RelationshipSupport.UNRESOLVED: 0,
        RelationshipSupport.INFERRED: 1,
        RelationshipSupport.SUPPORTED: 2,
    }
    reached = {key: RelationshipSupport.SUPPORTED for key in context.entry_evidence_ids}
    for _ in range(len(checked_edges) + 1):
        changed = False
        for relationship, caller, callee in checked_edges:
            if caller.evidence_id not in reached:
                continue
            value = min(reached[caller.evidence_id], relationship.support, key=rank.get)
            if rank[value] > rank.get(reached.get(callee.evidence_id), -1):
                reached[callee.evidence_id] = value
                changed = True
        if not changed:
            break
    operation_support = [
        reached[item.evidence_id]
        for item in evidence
        if item.evidence_id not in context.entry_evidence_ids and item.evidence_id in reached
    ]
    if operation_support:
        support = max(operation_support, key=rank.get)
    elif finding.relationship_ids:
        raise ReviewError(
            ErrorCode.INVALID_MODEL_OUTPUT, "No cited entry path reaches the source observation."
        )
    if context.intake.command_context is CommandContext.REVIEW_ONLY:
        support = RelationshipSupport.INFERRED
    source = "\n".join(item.representation for item in evidence).lower()
    claim = (finding.title + " " + finding.impact).lower()
    if support is RelationshipSupport.UNRESOLVED and re.search(
        r"during install|install.time|stole|steals|exfiltrates|installed malware", claim
    ):
        raise ReviewError(
            ErrorCode.INVALID_MODEL_OUTPUT, "An unsupported execution consequence was overstated."
        )
    if re.search(r"\b(dummy|simulated|simulation|noop|inert)\b|no.op", source) and re.search(
        r"stole|stolen|exfiltrated|infected|confirmed malware|real credentials", claim
    ):
        raise ReviewError(
            ErrorCode.INVALID_MODEL_OUTPUT, "A simulation was overstated as a real harmful outcome."
        )
    status, change_support = _change_support(finding, context)
    notes = ["References locate delivered source; semantic interpretation is not a runtime proof."]
    unknowns = list(finding.unknowns)
    if support is not RelationshipSupport.SUPPORTED:
        notes.append("The selected execution trigger is inferred or unresolved.")
        unknowns.append("Execution and runtime control flow were not verified.")
    if context.intake.baseline_ref:
        notes.append("Change classification is qualified to corresponding inspected source paths.")
        unknowns.append("Comparison does not certify the baseline or the whole target repository.")
    finding = finding.model_copy(
        update={
            "change_status": status,
            "unknowns": tuple(dict.fromkeys(unknowns))[:16],
            "title": redact(finding.title)[0],
            "impact": redact(finding.impact)[0],
            "trigger_context": redact(finding.trigger_context)[0],
            "benign_explanation_considered": redact(finding.benign_explanation_considered)[0],
            "priority_reason": redact(finding.priority_reason)[0],
            "behavior_category": redact(finding.behavior_category)[0],
        }
    )
    return ValidatedFinding(
        finding=finding,
        display_summary=redact(f"{finding.title}: {finding.impact}")[0][:4000],
        validation=ReferenceValidation(
            schema_checked=True,
            source_identity_checked=True,
            delivery_checked=True,
            range_quote_checked=True,
            execution_context_support=support,
            change_claim_support=change_support,
            interpretation_notes=tuple(notes),
        ),
    )
