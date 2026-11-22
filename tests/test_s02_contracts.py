from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from beforerun.features.budgets import Budget, BudgetExceeded, ReviewError
from beforerun.features.contracts import (
    Assessment,
    BrFinishArgs,
    BrFinishInvocation,
    DecisionBatch,
    DeliveryReceipt,
    ErrorCode,
    Evidence,
    EvidenceKind,
    Priority,
    ReviewInput,
    RevisionSide,
    SourceSpan,
    StopReason,
    ToolName,
    parse_tool_invocation,
)
from beforerun.features.settings import Settings, get_settings

SHA256 = "a" * 64


def test_input_is_root_only_and_rejects_unsupported_authority() -> None:
    review = ReviewInput(
        repository_url="https://github.com/example/project",
        command_context="npm_install",
        project_directory=".",
    )
    assert review.command_context.value == "npm_install"
    with pytest.raises(ValidationError):
        ReviewInput(
            repository_url="https://github.com/example/project",
            project_directory="scripts",
        )
    with pytest.raises(ValidationError):
        ReviewInput(
            repository_url="https://github.com/example/project",
            command_context="pip_install_project",
        )
    with pytest.raises(ValidationError):
        ReviewInput(
            repository_url="https://github.com/example/project\nhttp://127.0.0.1",
        )
    with pytest.raises(ValidationError):
        ReviewInput(
            repository_url="https://github.com/example/project",
            model_route="other/model",
        )


def test_candidate_cannot_smuggle_server_owned_completion_or_coverage() -> None:
    source = Evidence(
        evidence_id="ev_abcdefghijklmnop",
        file_id="file_abcdefghijklmnop",
        revision_id="rev_abcdefghijklmnop",
        side=RevisionSide.TARGET,
        span=SourceSpan(first_line=1, first_column=1, last_line=1, last_column=2),
        representation="x",
        raw_sha256=SHA256,
        representation_sha256=SHA256,
        kind=EvidenceKind.SOURCE,
    )
    finding = {
        "finding_id": "find_abcdefghijklmnop",
        "title": "Inert test finding",
        "behavior_category": "test",
        "impact": "Fixture only",
        "priority": "low",
        "priority_reason": "Contract test",
        "evidence_ids": [source.evidence_id],
        "trigger_context": "No execution",
        "relationship_ids": [],
        "benign_explanation_considered": "This is an inert schema fixture.",
        "change_status": "not_compared",
        "unknowns": [],
    }
    from beforerun.features.contracts import CandidateReport, Finding

    parsed = CandidateReport(
        assessment=Assessment.SUSPICIOUS,
        summary="Schema test",
        findings=(Finding.model_validate(finding),),
        stop_reason=StopReason.FINISHED,
    )
    assert parsed.findings[0].priority is Priority.LOW
    for field in ("completion", "coverage", "model_route", "source_url"):
        with pytest.raises(ValidationError):
            Finding.model_validate({**finding, field: "model-controlled"})
    with pytest.raises(ValidationError):
        CandidateReport.model_validate(
            {
                "assessment": "benign",
                "summary": "Untrusted candidate",
                "findings": [],
                "stop_reason": "finished",
                "completion": "complete",
            }
        )


def test_derived_evidence_requires_parent_and_decode_parameters() -> None:
    common = {
        "evidence_id": "ev_abcdefghijklmnop",
        "file_id": "file_abcdefghijklmnop",
        "revision_id": "rev_abcdefghijklmnop",
        "side": "target",
        "span": {
            "first_line": 1,
            "first_column": 1,
            "last_line": 1,
            "last_column": 2,
        },
        "representation": "x",
        "raw_sha256": SHA256,
        "representation_sha256": SHA256,
    }
    with pytest.raises(ValidationError):
        Evidence.model_validate({**common, "kind": "decoded"})
    with pytest.raises(ValidationError):
        Evidence.model_validate(
            {
                **common,
                "kind": "decoded",
                "parent_evidence_id": "ev_prontqabcdefghij",
            }
        )
    decoded = Evidence.model_validate(
        {
            **common,
            "kind": "decoded",
            "parent_evidence_id": "ev_prontqabcdefghij",
            "decoding_operations": ["base64"],
        }
    )
    assert decoded.parent_evidence_id == "ev_prontqabcdefghij"


def test_tool_schema_admits_only_bounded_snapshot_operations() -> None:
    call = parse_tool_invocation(
        {
            "tool_call_id": "call-1",
            "name": "br_read_excerpt",
            "arguments": {
                "file_id": "file_abcdefghijklmnop",
                "first_original_line": 2,
                "last_original_line": 4,
            },
        }
    )
    assert call.name is ToolName.READ_EXCERPT
    for name in ("read", "exec", "web_fetch", "br_fetch_url"):
        with pytest.raises(ValidationError):
            parse_tool_invocation({"tool_call_id": "call-1", "name": name, "arguments": {}})
    with pytest.raises(ValidationError):
        parse_tool_invocation(
            {
                "tool_call_id": "call-1",
                "name": "br_read_excerpt",
                "arguments": {
                    "file_id": "file_abcdefghijklmnop",
                    "first_original_line": 1,
                    "last_original_line": 2,
                    "url": "http://127.0.0.1/never-fetch",
                },
            }
        )
    with pytest.raises(ValidationError):
        parse_tool_invocation(
            {
                "tool_call_id": "call-1",
                "name": "br_read_excerpt",
                "arguments": {
                    "file_id": "file_abcdefghijklmnop",
                    "first_original_line": 1,
                    "last_original_line": 161,
                },
            }
        )


def test_decision_batch_rejects_oversized_duplicate_or_combined_finish_calls() -> None:
    finish = BrFinishInvocation(
        tool_call_id="call-finish",
        name=ToolName.FINISH,
        arguments=BrFinishArgs(reason="Enough evidence"),
    )
    DecisionBatch(calls=(finish,))
    with pytest.raises(ValidationError):
        DecisionBatch(calls=(finish, finish))
    read = {
        "tool_call_id": "call-read",
        "name": "br_read_excerpt",
        "arguments": {
            "file_id": "file_abcdefghijklmnop",
            "first_original_line": 1,
            "last_original_line": 2,
        },
    }
    with pytest.raises(ValidationError):
        DecisionBatch.model_validate({"calls": [finish.model_dump(), read]})
    with pytest.raises(ValidationError):
        DecisionBatch.model_validate({"calls": [read, read, read]})


def test_receipt_requires_exact_bounded_delivery_items() -> None:
    with pytest.raises(ValidationError):
        DeliveryReceipt(
            receipt_id="rcpt_abcdefghijklmnop",
            review_id="review_abcdefghijklmnop",
            turn=1,
            delivered_at=datetime.now(UTC),
            model_route="test-route",
            items=(),
        )


def test_budget_shares_retry_request_and_cancellation_limits() -> None:
    budget = Budget(Settings(max_github_attempts=3), started_at=100.0, clock=lambda: 100.0)
    budget.reserve_github("metadata")
    budget.reserve_github("metadata", is_retry=True)
    assert budget.usage().github_attempts == 2
    with pytest.raises(BudgetExceeded):
        budget.reserve_github("metadata", is_retry=True)
    assert budget.usage().github_attempts == 2
    budget.reserve_github("tree")
    with pytest.raises(BudgetExceeded):
        budget.reserve_github("blob")
    with pytest.raises(ReviewError) as cancelled:
        budget.cancel_event.set()
        budget.check()
    assert cancelled.value.code is ErrorCode.REVIEW_CANCELLED


def test_budget_deadline_uses_injected_monotonic_clock() -> None:
    budget = Budget(Settings(runtime_seconds=5.0), started_at=100.0, clock=lambda: 104.0)
    assert budget.usage().remaining_ms == 1000
    budget.clock = lambda: 105.0
    with pytest.raises(BudgetExceeded):
        budget.check()


def test_token_reservation_reconciles_provider_usage_once() -> None:
    budget = Budget(Settings(max_input_tokens=100, max_output_tokens=20))
    reservation = budget.reserve_tokens(
        estimated_input_tokens=80,
        requested_output_tokens=15,
    )
    assert (budget.input_tokens, budget.output_tokens) == (80, 15)
    with pytest.raises(BudgetExceeded):
        budget.reserve_tokens(estimated_input_tokens=21, requested_output_tokens=1)
    budget.reconcile_tokens(
        reservation,
        actual_input_tokens=75,
        actual_output_tokens=12,
    )
    assert (budget.input_tokens, budget.output_tokens) == (75, 12)
    with pytest.raises(ValueError):
        budget.reconcile_tokens(
            reservation,
            actual_input_tokens=75,
            actual_output_tokens=12,
        )


def test_finalization_and_repair_stay_inside_model_allowance() -> None:
    budget = Budget(Settings(max_model_attempts=3, max_tool_operations=1))
    budget.reserve_decision()
    budget.reserve_tool()
    budget.reserve_model(final=True)
    with pytest.raises(BudgetExceeded):
        budget.reserve_decision()
    with pytest.raises(BudgetExceeded):
        budget.reserve_tool()
    with pytest.raises(BudgetExceeded):
        budget.reserve_model(final=True)
    budget.reserve_model(repair=True)
    with pytest.raises(BudgetExceeded):
        budget.reserve_model(repair=True)


def test_environment_cannot_raise_server_hard_ceilings(monkeypatch: pytest.MonkeyPatch) -> None:
    cases = {
        "BEFORERUN_RUNTIME_SECONDS": "91",
        "BEFORERUN_QUEUE_SECONDS": "31",
        "BEFORERUN_MAX_GITHUB_ATTEMPTS": "33",
        "BEFORERUN_MAX_MODEL_ATTEMPTS": "9",
        "BEFORERUN_MAX_ACTIVE_REVIEWS": "2",
        "BEFORERUN_MAX_QUEUED_REVIEWS": "3",
    }
    for name, value in cases.items():
        monkeypatch.setenv(name, value)
        get_settings.cache_clear()
        with pytest.raises(ValueError):
            get_settings()
        monkeypatch.delenv(name)
    get_settings.cache_clear()


def test_gateway_url_rejects_credentials_paths_and_insecure_remote_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for value in (
        "https://user:password@example.com",
        "http://example.com",
        "http://127.0.0.1:18789/private",
        "file:///tmp/openclaw",
    ):
        monkeypatch.setenv("OPENCLAW_BASE_URL", value)
        get_settings.cache_clear()
        with pytest.raises(ValueError):
            get_settings()
    get_settings.cache_clear()


def test_budget_source_cap_is_atomic() -> None:
    budget = Budget(Settings(max_distinct_blobs=1, max_source_bytes=8, max_file_bytes=8))
    budget.add_source(1, "a" * 40, 4)
    budget.add_source(1, "a" * 40, 4)
    assert budget.usage().distinct_blobs == 1
    assert budget.usage().source_bytes == 4
    with pytest.raises(ReviewError):
        budget.add_source(1, "b" * 40, 1)
    assert budget.usage().source_bytes == 4
    with pytest.raises(ReviewError):
        budget.add_source(2, "a" * 40, 9)
    assert budget.usage().distinct_blobs == 1


def test_async_cancellation_event_does_not_need_a_running_loop() -> None:
    async def run() -> None:
        budget = Budget(Settings())
        budget.cancel_event.set()
        with pytest.raises(ReviewError):
            budget.reserve_model()

    asyncio.run(run())
