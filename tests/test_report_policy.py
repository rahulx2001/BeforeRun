from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace

import pytest
from review_helpers import context

from beforerun.features.budgets import ReviewError
from beforerun.features.compare import compare_inventories, materialize_comparison
from beforerun.features.contracts import (
    Assessment,
    CandidateReport,
    ChangeStatus,
    Completion,
    EvidenceKind,
    Finding,
    Relationship,
    RelationshipSupport,
    ReviewInput,
    RevisionSide,
    StopReason,
)
from beforerun.features.investigator import InvestigationOutcome, parse_candidate
from beforerun.features.report import build_report, export_json, export_text
from beforerun.features.validate import ValidationContext, checked_evidence, validate_finding


def finding(evidence, **changes):
    value = {
        "finding_id": "find_" + "f" * 24,
        "title": "Source operation",
        "behavior_category": "source_observation",
        "impact": "Potential disclosure requires review.",
        "priority": "high",
        "priority_reason": "Source-backed operation under the selected context.",
        "evidence_ids": [evidence.evidence_id],
        "evidence_quotes": [
            {
                "evidence_id": evidence.evidence_id,
                "exact_quote": evidence.representation[:2000],
                "first_original_line": evidence.span.first_line,
                "last_original_line": evidence.span.last_line,
            }
        ],
        "trigger_context": "Declared root setup context.",
        "relationship_ids": [],
        "benign_explanation_considered": "A documented operation could be intentional.",
        "change_status": "not_compared",
        "unknowns": [],
        **changes,
    }
    return Finding.model_validate(value)


def prepared(raw=b"OBSERVED_OPERATION: sensitive source -> external sink", *, deliver=True):
    snapshot, ledger, budget = context(
        {
            "entry.txt": b"DECLARED_ENTRY",
            "operation.txt": raw,
            "unread.txt": b"unread required surface",
        }
    )

    async def run():
        for path in ("entry.txt", "operation.txt"):
            await snapshot.admit_file(snapshot.file_id(RevisionSide.TARGET, path))

    asyncio.run(run())
    entry = ledger.issue(snapshot.file_id(RevisionSide.TARGET, "entry.txt"))
    evidence = ledger.issue(snapshot.file_id(RevisionSide.TARGET, "operation.txt"))
    if deliver:
        ledger.deliver([entry.evidence_id, evidence.evidence_id], 1)
    edge = Relationship(
        relationship_id="rel_" + "r" * 24,
        caller_evidence_id=entry.evidence_id,
        callee_evidence_id=evidence.evidence_id,
        kind="declared_entry",
        support=RelationshipSupport.SUPPORTED,
        analyzer_version="abstract-policy-fixture",
    )
    validation = ValidationContext(
        ReviewInput(
            repository_url="https://github.com/example/inert-fixture", command_context="npm_install"
        ),
        ledger,
        (edge,),
        frozenset({entry.evidence_id}),
    )
    item = finding(evidence, relationship_ids=[edge.relationship_id])
    return validation, budget, item, evidence


def outcome(findings=(), assessment="benign", stop=StopReason.FINISHED):
    candidate = CandidateReport(
        assessment=assessment,
        summary="Abstract policy fixture; not a malware benchmark.",
        findings=findings,
        stop_reason=stop,
    )
    return InvestigationOutcome(candidate, stop, (), ())


def test_checked_serious_finding_survives_unread_required_source_and_invalid_sibling() -> None:
    validation, budget, item, evidence = prepared()
    bad = item.model_copy(
        update={"finding_id": "find_" + "b" * 24, "evidence_ids": ("ev_" + "z" * 24,)}
    )
    unread_id = validation.ledger.snapshot.file_id(RevisionSide.TARGET, "unread.txt")
    report = build_report(
        validation,
        outcome((item, bad), "malicious"),
        budget,
        required_file_ids=frozenset({unread_id}),
    )
    assert len(report.findings) == 1
    assert report.assessment is Assessment.MALICIOUS and report.completion is Completion.PARTIAL
    assert unread_id in report.coverage.required_unresolved_files
    assert report.coverage.errors
    assert report.findings[0].validation.delivery_checked


def test_fetched_but_not_delivered_is_never_a_checked_reference() -> None:
    validation, _, item, _ = prepared(deliver=False)
    with pytest.raises(ReviewError):
        validate_finding(item, validation)


@pytest.mark.parametrize("mutation", ["quote", "line", "side", "text"])
def test_invented_quote_original_range_side_and_representation_are_rejected(mutation) -> None:
    validation, _, item, evidence = prepared()
    if mutation == "quote":
        quote = item.evidence_quotes[0].model_copy(update={"exact_quote": "invented operation"})
        item = item.model_copy(update={"evidence_quotes": (quote,)})
    elif mutation == "line":
        quote = item.evidence_quotes[0].model_copy(
            update={"first_original_line": 2, "last_original_line": 2}
        )
        item = item.model_copy(update={"evidence_quotes": (quote,)})
    elif mutation == "side":
        validation.ledger.evidence[evidence.evidence_id] = evidence.model_copy(
            update={"side": RevisionSide.BASELINE}
        )
    else:
        digest = hashlib.sha256(b"invented operation").hexdigest()
        validation.ledger.evidence[evidence.evidence_id] = evidence.model_copy(
            update={
                "representation": "invented operation",
                "representation_sha256": digest,
            }
        )
        validation.ledger.delivered[evidence.evidence_id] = digest
    with pytest.raises(ReviewError):
        validate_finding(item, validation)


def test_empty_complete_and_empty_partial_have_different_assessments() -> None:
    validation, budget, _, evidence = prepared()
    full = build_report(
        validation, outcome(), budget, required_file_ids=frozenset({evidence.file_id})
    )
    assert full.assessment is Assessment.BENIGN and full.completion is Completion.COMPLETE
    unread = validation.ledger.snapshot.file_id(RevisionSide.TARGET, "unread.txt")
    partial = build_report(validation, outcome(), budget, required_file_ids=frozenset({unread}))
    assert (
        partial.assessment is Assessment.UNDETERMINED and partial.completion is Completion.PARTIAL
    )


def test_bounded_excerpt_and_cancelled_scope_cannot_become_complete_benign() -> None:
    validation, budget, _, evidence = prepared(b"x" * 20_000)
    report = build_report(
        validation, outcome(), budget, required_file_ids=frozenset({evidence.file_id})
    )
    assert report.assessment is Assessment.UNDETERMINED
    cancelled = InvestigationOutcome(None, StopReason.CANCELLED, (), ())
    assert build_report(validation, cancelled, budget).completion is Completion.CANCELLED


def test_simulated_source_cannot_claim_real_theft_and_missing_context_is_qualified() -> None:
    validation, _, item, _ = prepared(b"simulated noop dummy fixture")
    with pytest.raises(ReviewError):
        validate_finding(
            item.model_copy(update={"impact": "It stole real credentials."}), validation
        )
    checked = validate_finding(item.model_copy(update={"relationship_ids": ()}), validation)
    assert checked.validation.execution_context_support is RelationshipSupport.UNRESOLVED
    assert checked.finding.unknowns


def test_mixed_schema_candidates_retain_valid_findings_without_forcing_confidence() -> None:
    _, _, item, _ = prepared()
    raw = {
        "assessment": "malicious",
        "summary": "Abstract fixture",
        "stop_reason": "finished",
        "findings": [item.model_dump(mode="json"), {"title": "invalid"}],
    }
    candidate, errors = parse_candidate(json.dumps(raw))
    assert candidate.findings == (item,) and errors


def test_change_labels_need_both_original_sides_or_qualified_absence() -> None:
    async def run():
        snapshot, ledger, budget = context({"helper.txt": b"Node 22"}, {"helper.txt": b"Node 20"})
        comparison = await materialize_comparison(snapshot, ledger, compare_inventories(snapshot))
        entry = comparison.entries[0]
        ids = entry.target_evidence_ids + entry.baseline_evidence_ids
        ledger.deliver(list(ids), 1)
        first, second = (ledger.require(key) for key in ids)
        item = finding(
            first,
            change_status="changed",
            evidence_ids=list(ids),
            evidence_quotes=[
                {"evidence_id": first.evidence_id, "exact_quote": "Node 22"},
                {"evidence_id": second.evidence_id, "exact_quote": "Node 20"},
            ],
        )
        validation = ValidationContext(
            ReviewInput(
                repository_url="https://github.com/example/inert-fixture", baseline_ref="baseline"
            ),
            ledger,
            comparison=comparison,
        )
        assert validate_finding(item, validation).finding.change_status is ChangeStatus.CHANGED
        incomplete = replace(
            validation,
            comparison=comparison.model_copy(update={"complete_within_inventory": False}),
        )
        assert validate_finding(item, incomplete).finding.change_status is ChangeStatus.UNKNOWN

    asyncio.run(run())


def test_derived_virtual_coordinates_and_secret_exports_are_checked() -> None:
    validation, budget, item, evidence = prepared(b"Node 22")
    derived = evidence.model_copy(
        update={
            "evidence_id": "ev_" + "d" * 24,
            "kind": EvidenceKind.DIFF,
            "parent_evidence_id": evidence.evidence_id,
            "representation": "fake diff",
            "representation_sha256": hashlib.sha256(b"fake diff").hexdigest(),
        }
    )
    validation.ledger.evidence[derived.evidence_id] = derived
    validation.ledger.deliver([derived.evidence_id], 2)
    with pytest.raises(ReviewError):
        checked_evidence(validation, derived.evidence_id)
    report = build_report(
        validation,
        outcome((item,), "suspicious"),
        budget,
        assumptions=("api_key=synthetic_fixture_secret",),
    )
    assert "synthetic_fixture_secret" not in export_json(report)
    assert "synthetic_fixture_secret" not in export_text(report)


def test_previously_checked_serious_finding_survives_cancelled_final_response() -> None:
    validation, budget, item, _ = prepared()
    checked = validate_finding(item, validation)
    report = build_report(
        validation,
        InvestigationOutcome(None, StopReason.CANCELLED, (), ()),
        budget,
        previous_findings=(checked,),
        previous_assessment=Assessment.MALICIOUS,
    )
    assert report.assessment is Assessment.MALICIOUS
    assert report.completion is Completion.CANCELLED and report.findings
