"""Offline proof-runner tests. No credentials, .env reads, or real connections."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from beforerun.features.budgets import ReviewError
from beforerun.features.settings import Settings

RUNNER = Path(__file__).parent / "fixtures/demo/run_live_proof.py"
SPEC = importlib.util.spec_from_file_location("prepared_proof_runner", RUNNER)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
SETTINGS = Settings(
    openclaw_base_url="http://127.0.0.1:18790", openclaw_gateway_token="inert-offline-fixture-token"
)


def reply(message, finish="stop", usage=True):
    body = {
        "model": SETTINGS.expected_response_model,
        "choices": [{"message": message, "finish_reason": finish}],
    }
    if usage:
        body["usage"] = {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35}
    return httpx.Response(200, json=body)


def proper_response(payload, *, foreign=False, wrong_quote=False, usage=True):
    messages = payload["messages"]
    if len(messages) == 1:
        return reply({"role": "assistant", "content": "CONNECTION_OK"}, usage=usage)
    if payload["tool_choice"] == "auto":
        arguments = json.loads(messages[-1]["content"])["arguments"]
        return reply(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "read_proof",
                        "type": "function",
                        "function": {
                            "name": "br_read_excerpt",
                            "arguments": json.dumps(arguments),
                        },
                    }
                ],
            },
            "tool_calls",
            usage=usage,
        )
    tool = next(message for message in messages if message["role"] == "tool")
    evidence = json.loads(tool["content"])["evidence"][0]
    evidence_id = "ev_" + "z" * 24 if foreign else evidence["evidence_id"]
    candidate = {
        "assessment": "benign",
        "summary": "Inert memory marker only.",
        "stop_reason": "finished",
        "findings": [
            {
                "finding_id": "find_" + "f" * 24,
                "title": "Inert source marker",
                "behavior_category": "source_observation",
                "impact": "A static marker; no program behavior was executed.",
                "priority": "low",
                "priority_reason": "Only fixed text is observed.",
                "evidence_ids": [evidence_id],
                "evidence_quotes": [
                    {
                        "evidence_id": evidence_id,
                        "exact_quote": "invented private token"
                        if wrong_quote
                        else runner.FIXTURE_MARKER,
                        "first_original_line": 1,
                        "last_original_line": 1,
                    }
                ],
                "trigger_context": "Source-only inert fixture.",
                "relationship_ids": [],
                "benign_explanation_considered": "A harmless test marker.",
                "change_status": "not_compared",
                "unknowns": ["Synthetic source identity; no real repository fetched."],
            }
        ],
    }
    return reply({"role": "assistant", "content": json.dumps(candidate)}, usage=usage)


def execute(handler, **kwargs):
    return asyncio.run(
        runner.execute_proof(
            authorize_live=True,
            authorization_reference="offline-test-authorization",
            settings=SETTINGS,
            transport=httpx.MockTransport(handler),
            **kwargs,
        )
    )


def test_default_refuses_before_environment_client_or_output_access(monkeypatch, tmp_path, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("Unauthorized proof accessed configuration or HTTP.")

    monkeypatch.setattr(runner, "load_dotenv", forbidden)
    monkeypatch.setattr(runner, "get_settings", forbidden)
    monkeypatch.setattr(runner.httpx, "AsyncClient", forbidden)
    output = tmp_path / "must-not-exist.json"
    assert runner.main(["--output", str(output)]) == 2
    assert not output.exists()
    assert json.loads(capsys.readouterr().out)["error_code"] == "LIVE_NOT_AUTHORIZED"
    with pytest.raises(runner.ProofRefusal, match="LIVE_NOT_AUTHORIZED"):
        asyncio.run(runner.execute_proof())


def test_authorization_reference_is_required_and_request_cap_is_hard(monkeypatch):
    monkeypatch.setattr(runner, "get_settings", lambda: pytest.fail("Config must not be read."))
    for reference, cap in (("", 3), ("ref", 0), ("ref", 9), ("ref", True)):
        with pytest.raises(runner.ProofRefusal):
            asyncio.run(
                runner.execute_proof(
                    authorize_live=True, authorization_reference=reference, max_requests=cap
                )
            )


def test_real_client_canonical_continuation_and_real_validator_check_the_citation():
    requests = []

    def handle(request):
        payload = json.loads(request.content)
        requests.append(payload)
        return proper_response(payload)

    result = execute(handle)
    assert result["status"] == "passed_inert_reference_proof"
    assert result["checked_report_created"] and result["gateway_requests"] == 3
    assert result["execution_mode"] == "offline_test" and not result["release_ready"]
    assert result["checked_citation"]["range_quote_checked"]
    assert result["checked_citation"]["span"]["first_line"] == 1
    assert requests[0]["tool_choice"] == "none" and requests[1]["tool_choice"] == "auto"
    assert len(requests[1]["tools"]) == 7
    assert all(request["max_tokens"] <= 512 for request in requests)
    assert requests[2]["messages"][2]["tool_calls"][0]["id"] == "read_proof"
    assert requests[2]["messages"][3]["tool_call_id"] == "read_proof"
    assert all(row["duration_ms"] >= 0 for row in result["attempts"])
    assert all(row["usage"]["prompt_tokens"] == 20 for row in result["attempts"])
    assert result["provider_cost"] is None and result["provider_request_count"] is None


@pytest.mark.parametrize("foreign,wrong_quote", [(True, False), (False, True)])
def test_foreign_ids_and_wrong_exact_quotes_never_create_checked_reports(foreign, wrong_quote):
    result = execute(
        lambda request: proper_response(
            json.loads(request.content), foreign=foreign, wrong_quote=wrong_quote
        )
    )
    assert result["status"] == "failed" and not result["checked_report_created"]
    assert "checked_citation" not in result
    assert "invented private token" not in json.dumps(result)


def test_missing_usage_and_cost_remain_unknown():
    result = execute(lambda request: proper_response(json.loads(request.content), usage=False))
    assert result["checked_report_created"]
    assert all(all(value is None for value in row["usage"].values()) for row in result["attempts"])
    assert all(row["cost"] is None for row in result["attempts"])


def test_retries_are_counted_and_exhaustion_stops_before_a_fourth_request():
    requests = []

    def handle(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(503, text="PRIVATE_UPSTREAM_BODY_SHOULD_NOT_ESCAPE")
        return proper_response(json.loads(request.content))

    result = execute(handle, max_requests=3)
    assert len(requests) == result["gateway_requests"] == 3
    assert result["attempts"][0]["http_status"] == 503
    assert not result["checked_report_created"] and result["error_code"] == "BUDGET_EXHAUSTED"
    assert "PRIVATE_UPSTREAM" not in json.dumps(result)


def test_successful_retry_is_in_the_journal_with_a_larger_explicit_cap():
    requests = []

    def handle(request):
        requests.append(request)
        return (
            httpx.Response(503)
            if len(requests) == 1
            else proper_response(json.loads(request.content))
        )

    result = execute(handle, max_requests=4)
    assert result["checked_report_created"] and len(result["attempts"]) == 4
    assert [row["phase"] for row in result["attempts"][:2]] == ["text_smoke", "text_smoke"]


def test_redirects_and_foreign_destinations_never_reach_a_second_origin():
    seen = []

    def handle(request):
        seen.append(str(request.url))
        return httpx.Response(302, headers={"Location": "https://callback.invalid/secret"})

    result = execute(handle)
    assert len(seen) == 1 and result["gateway_requests"] == 1
    assert not result["checked_report_created"]
    assert "callback.invalid" not in json.dumps(result)

    async def check_foreign():
        guard = runner.BoundedGatewayTransport(SETTINGS, httpx.MockTransport(handle), 3)
        with pytest.raises(ReviewError):
            await guard.handle_async_request(
                httpx.Request("POST", "https://callback.invalid/v1/chat/completions")
            )
        await guard.aclose()

    asyncio.run(check_foreign())
    assert len(seen) == 1


def test_unsupported_tool_and_secret_failure_text_are_not_dispatched_or_saved():
    def handle(request):
        payload = json.loads(request.content)
        if len(payload["messages"]) == 1:
            return proper_response(payload)
        return reply(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "bad",
                        "type": "function",
                        "function": {
                            "name": "exec",
                            "arguments": '{"command":"PRIVATE_COMMAND"}',
                        },
                    }
                ],
            },
            "tool_calls",
        )

    result = execute(handle)
    assert result["gateway_requests"] == 2 and result["error_code"] == "UNEXPECTED_TOOL_CALL"
    assert "PRIVATE_COMMAND" not in json.dumps(result)

    def fail(request):
        raise httpx.ConnectError("PRIVATE_TOKEN_IN_EXCEPTION", request=request)

    result = execute(fail)
    assert result["gateway_requests"] == 2
    assert "PRIVATE_TOKEN_IN_EXCEPTION" not in json.dumps(result)


def test_existing_artifact_is_preserved_before_env_loading(monkeypatch, tmp_path, capsys):
    path = tmp_path / "existing.json"
    path.write_text("preserve me")
    monkeypatch.setattr(runner, "load_dotenv", lambda *a, **k: pytest.fail("No env read expected."))
    assert (
        runner.main(["--authorize-live", "--authorization-reference", "ref", "--output", str(path)])
        == 2
    )
    assert path.read_text() == "preserve me"
    assert json.loads(capsys.readouterr().out)["error_code"] == "OUTPUT_EXISTS"


def test_invalid_unicode_authorization_refuses_without_a_traceback_or_config_read(monkeypatch):
    monkeypatch.setattr(runner, "get_settings", lambda: pytest.fail("No config read expected."))
    with pytest.raises(runner.ProofRefusal, match="AUTHORIZATION_REFERENCE_REQUIRED"):
        asyncio.run(
            runner.execute_proof(authorize_live=True, authorization_reference="private\ud800")
        )


@pytest.mark.parametrize(
    "base",
    [
        "https://private-user:PRIVATE_PASSWORD@gateway.invalid",
        "https://gateway.invalid/?token=PRIVATE_QUERY",
        "https://gateway.invalid/#PRIVATE_FRAGMENT",
        "https://gateway.invalid/PRIVATE_PATH",
    ],
)
def test_invalid_gateway_origins_are_never_sent_or_serialized(base, monkeypatch):
    monkeypatch.setattr(
        runner.httpx,
        "AsyncHTTPTransport",
        lambda *a, **k: pytest.fail("Invalid config must fail before creating real transport."),
    )
    result = asyncio.run(
        runner.execute_proof(
            authorize_live=True,
            authorization_reference="offline-ref",
            settings=replace(SETTINGS, openclaw_base_url=base),
        )
    )
    assert not result["checked_report_created"] and result["attempts"] == []
    assert result["error_code"] == "CONFIGURATION_UNAVAILABLE"
    assert "gateway_origin" not in result and "PRIVATE_" not in json.dumps(result)


def test_custom_expected_model_is_hashed_and_model_mismatch_stops_before_tool_work():
    model = "PRIVATE_MODEL"
    configured = replace(SETTINGS, openclaw_expected_model=model)

    def handle(request):
        response = proper_response(json.loads(request.content))
        body = response.json()
        body["model"] = model
        return httpx.Response(200, json=body)

    result = asyncio.run(
        runner.execute_proof(
            authorize_live=True,
            authorization_reference="PRIVATE_AUTHORIZATION_TEXT",
            settings=configured,
            transport=httpx.MockTransport(handle),
        )
    )
    assert result["checked_report_created"]
    assert result["expected_response_model"] is None
    assert result["expected_response_model_sha256"]
    assert all(row["response_model"] is None for row in result["attempts"])
    assert all(row["response_model_matches_expectation"] for row in result["attempts"])
    assert "PRIVATE_" not in json.dumps(result)

    mismatch = asyncio.run(
        runner.execute_proof(
            authorize_live=True,
            authorization_reference="offline-ref",
            settings=configured,
            transport=httpx.MockTransport(
                lambda request: proper_response(json.loads(request.content))
            ),
        )
    )
    assert not mismatch["checked_report_created"] and mismatch["gateway_requests"] == 1
    assert mismatch["attempts"][0]["response_model_matches_expectation"] is False
    assert "PRIVATE_" not in json.dumps(mismatch)


def test_help_succeeds_without_authorization_or_configuration_access(monkeypatch, capsys):
    monkeypatch.setattr(runner, "get_settings", lambda: pytest.fail("No config read expected."))
    monkeypatch.setattr(runner, "load_dotenv", lambda *a, **k: pytest.fail("No env read expected."))
    assert runner.main(["--help"]) == 0
    assert "--authorize-live" in capsys.readouterr().out
