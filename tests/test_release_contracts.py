"""Additional release regressions over inert or abstract evidence contracts."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import pytest
from test_pipeline import harness
from test_report_policy import outcome, prepared

from beforerun.features.budgets import Budget, ReviewError
from beforerun.features.contracts import ErrorCode, ErrorRecord, EvidenceKind, ReviewInput
from beforerun.features.npm_setup import NpmSetupAnalyzer
from beforerun.features.report import build_report
from beforerun.features.validate import validate_finding


def test_documented_download_does_not_certify_unread_payload() -> None:
    validation, budget, item, _ = prepared(b"OBSERVED_OPERATION: documented binary download")
    item = item.model_copy(
        update={"title": "Documented download", "impact": "Downloaded payload was not inspected."}
    )
    interrupted = replace(
        outcome((item,), "suspicious"),
        errors=(
            ErrorRecord(
                code=ErrorCode.SOURCE_LIMIT,
                message="Downloaded binary payload remains unread.",
            ),
        ),
    )
    report = build_report(validation, interrupted, budget)
    assert report.assessment.value == "suspicious" and report.completion.value == "partial"
    assert "unread" in report.coverage.errors[0].message


def test_unused_credential_looking_text_has_no_install_malware_claim() -> None:
    validation, _, item, _ = prepared(b"Documentation credential example only; no operation")
    item = item.model_copy(
        update={"relationship_ids": (), "impact": "It steals credentials during install."}
    )
    with pytest.raises(ReviewError):
        validate_finding(item, validation)


def test_noop_simulation_can_be_benign_without_forcing_a_malicious_label() -> None:
    validation, budget, item, _ = prepared(b"DUMMY_DATA -> NOOP_SINK")
    item = item.model_copy(update={"impact": "A no-op simulation, not actual data transfer."})
    report = build_report(validation, outcome((item,), "benign"), budget)
    assert report.assessment.value == "benign" and report.completion.value == "complete"


def test_a_relationship_to_another_file_does_not_support_the_observation() -> None:
    validation, _, item, _ = prepared()
    unrelated = validation.relationships[0].model_copy(
        update={
            "callee_evidence_id": next(iter(validation.entry_evidence_ids)),
        }
    )
    with pytest.raises(ReviewError):
        validate_finding(item, replace(validation, relationships=(unrelated,)))


def test_real_npm_analyzer_supports_the_mocked_extra_helper_read() -> None:
    async def run():
        pipeline, _, calls = harness()
        pipeline.analyzer = NpmSetupAnalyzer()
        pipeline.withhold_helper = True
        intake = ReviewInput(
            repository_url="https://github.com/example/inert-fixture", command_context="npm_install"
        )
        budget = Budget(pipeline.settings)
        result = await pipeline.run("review_" + "p" * 24, intake, budget, budget.cancel_event)
        assert result.report.coverage.model_shown_files == 2
        assert result.report.completion.value == "complete"
        initial = json.loads(calls[0]["messages"][1]["content"])
        assert len(initial["source_evidence"]) == 1
        assert initial["context"]["relationships"]
        assert calls[1]["messages"][3]["tool_call_id"] == "helper_read"

    asyncio.run(run())


def test_operator_enablement_requires_explicit_server_opt_in(monkeypatch) -> None:
    from beforerun.app import reviews_enabled

    monkeypatch.delenv("BEFORERUN_ENABLE_REVIEWS", raising=False)
    assert not reviews_enabled()
    monkeypatch.setenv("BEFORERUN_ENABLE_REVIEWS", "true")
    assert not reviews_enabled()
    monkeypatch.setenv("BEFORERUN_ENABLE_REVIEWS", "1")
    assert reviews_enabled()


def test_validated_indirect_entry_path_reaches_the_observed_file() -> None:
    validation, _, item, evidence = prepared()
    ledger = validation.ledger
    entry = next(iter(validation.entry_evidence_ids))
    middle = ledger.issue_derived(entry, "DECLARED_ENTRY", EvidenceKind.STRING)
    ledger.deliver([middle.evidence_id], 2)
    first = validation.relationships[0].model_copy(
        update={
            "relationship_id": "rel_" + "a" * 24,
            "callee_evidence_id": middle.evidence_id,
        }
    )
    second = validation.relationships[0].model_copy(
        update={"caller_evidence_id": middle.evidence_id}
    )
    item = item.model_copy(
        update={"relationship_ids": (first.relationship_id, second.relationship_id)}
    )
    checked = validate_finding(item, replace(validation, relationships=(first, second)))
    assert checked.validation.execution_context_support.value == "supported"
