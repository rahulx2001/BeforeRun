from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from beforerun.features.budgets import Budget, ReviewError
from beforerun.features.contracts import ErrorCode, ModelAttemptKind
from beforerun.features.openclaw_client import OpenClawClient
from beforerun.features.settings import Settings


def response(content="fixture", calls=None):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return {
        "model": "openclaw/beforerun-reviewer",
        "choices": [{"message": message, "finish_reason": "tool_calls" if calls else "stop"}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 20},
    }


def test_private_route_headers_and_stateless_history_are_server_owned() -> None:
    async def run():
        requests = []

        def reply(request):
            requests.append(request)
            return httpx.Response(200, json=response())

        settings = Settings(openclaw_gateway_token="dummy-fixture-token")
        async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as http:
            client = OpenClawClient(settings, client=http)
            await client.complete([{"role": "user", "content": "inert"}], Budget(settings))
        request = requests[0]
        payload = json.loads(request.content)
        assert str(request.url) == "http://127.0.0.1:18789/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer dummy-fixture-token"
        assert payload["model"] == "openclaw/beforerun-reviewer"
        assert "user" not in payload and not payload["stream"]
        assert {tool["function"]["name"] for tool in payload["tools"]} == {
            "br_list_files",
            "br_read_excerpt",
            "br_search_source",
            "br_static_decode",
            "br_extract_strings",
            "br_read_diff",
            "br_finish",
        }

    asyncio.run(run())


@pytest.mark.parametrize(
    "status,attempts,code",
    [
        (302, 1, ErrorCode.OPENCLAW_UNAVAILABLE),
        (401, 1, ErrorCode.OPENCLAW_UNAVAILABLE),
        (403, 1, ErrorCode.MODEL_ACCESS_DENIED),
        (429, 2, ErrorCode.OPENCLAW_UNAVAILABLE),
        (503, 2, ErrorCode.OPENCLAW_UNAVAILABLE),
    ],
)
def test_redirect_access_and_transient_errors_are_bounded(status, attempts, code) -> None:
    async def run():
        requests = []

        def reply(request):
            requests.append(request)
            return httpx.Response(
                status,
                headers={"location": "https://callback.invalid"},
                text="dummy-sensitive-upstream-body",
            )

        settings = Settings()
        budget = Budget(settings)
        async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as http:
            with pytest.raises(ReviewError) as failure:
                await OpenClawClient(settings, client=http).complete([], budget)
        assert failure.value.code is code
        assert "dummy-sensitive" not in failure.value.message
        assert len(requests) == budget.model_attempts == attempts
        assert all(request.url.host == "127.0.0.1" for request in requests)

    asyncio.run(run())


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {"role": "assistant"}, "finish_reason": "length"}]},
        response(calls=[{}, {}, {}]),
        {**response(), "usage": {"prompt_tokens": True, "completion_tokens": 0}},
    ],
)
def test_malformed_and_truncated_response_fails(value) -> None:
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=value))
        ) as http:
            with pytest.raises(ReviewError) as failure:
                await OpenClawClient(Settings(), client=http).complete([], Budget(Settings()))
        assert failure.value.code is ErrorCode.INVALID_MODEL_OUTPUT

    asyncio.run(run())


def test_response_model_identity_is_required_and_configurable() -> None:
    async def reply(value, settings):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=value))
        ) as http:
            return await OpenClawClient(settings, client=http).complete(
                [{"role": "user", "content": "inert"}], Budget(settings)
            )

    missing = response()
    missing.pop("model")
    with pytest.raises(ReviewError) as failure:
        asyncio.run(reply(missing, Settings()))
    assert failure.value.code is ErrorCode.INVALID_MODEL_OUTPUT

    malformed = {**response(), "model": 7}
    with pytest.raises(ReviewError) as failure:
        asyncio.run(reply(malformed, Settings()))
    assert failure.value.code is ErrorCode.INVALID_MODEL_OUTPUT

    unexpected = {**response(), "model": "openclaw/other-reviewer"}
    with pytest.raises(ReviewError) as failure:
        asyncio.run(reply(unexpected, Settings()))
    assert failure.value.code is ErrorCode.MODEL_ACCESS_DENIED

    configured = Settings(openclaw_expected_model="moonshotai/kimi-k3.1-pro")
    accepted = {**response(), "model": "moonshotai/kimi-k3.1-pro"}
    result = asyncio.run(reply(accepted, configured))
    assert result.response_model == "moonshotai/kimi-k3.1-pro"


def test_streamed_envelope_limit_and_active_cancellation() -> None:
    class Large(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(70):
                yield b"x" * 1024

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=Large()))
        ) as http:
            with pytest.raises(ReviewError) as failure:
                await OpenClawClient(Settings(), client=http).complete([], Budget(Settings()))
        assert failure.value.code is ErrorCode.INVALID_MODEL_OUTPUT
        started = asyncio.Event()

        async def wait_response(request):
            started.set()
            await asyncio.Event().wait()

        budget = Budget(Settings())
        async with httpx.AsyncClient(transport=httpx.MockTransport(wait_response)) as http:
            task = asyncio.create_task(OpenClawClient(Settings(), client=http).complete([], budget))
            await asyncio.wait_for(started.wait(), 1)
            budget.cancel_event.set()
            with pytest.raises(ReviewError) as cancelled:
                await asyncio.wait_for(task, 1)
        assert cancelled.value.code is ErrorCode.REVIEW_CANCELLED
        assert budget.model_attempts == 1

    asyncio.run(run())


def test_final_mode_rejects_tools_and_private_reasoning_is_ignored() -> None:
    async def run():
        value = response()
        value["choices"][0]["message"]["reasoning_content"] = "private-fixture-reasoning"
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=value))
        ) as http:
            reply = await OpenClawClient(Settings(), client=http).complete(
                [], Budget(Settings()), kind=ModelAttemptKind.FINAL
            )
        assert "reasoning_content" not in reply.message

    asyncio.run(run())


def test_tool_call_history_is_canonical_and_finish_reason_is_consistent() -> None:
    async def run():
        call = {
            "id": "finish_1",
            "type": "function",
            "function": {
                "name": "br_finish",
                "arguments": '{"reason":"inert"}',
                "upstream_internal": "discard",
            },
            "reasoning_content": "private tool reasoning must be discarded",
        }
        value = response(None, [call])
        value["choices"][0]["message"]["reasoning_content"] = "discard this too"
        requests = []

        def reply(request):
            requests.append(request)
            return httpx.Response(200, json=value)

        async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as http:
            canonical = await OpenClawClient(Settings(), client=http).complete(
                [], Budget(Settings())
            )
        assert canonical.message["tool_calls"] == [
            {
                "id": "finish_1",
                "type": "function",
                "function": {"name": "br_finish", "arguments": '{"reason":"inert"}'},
            }
        ]
        assert "reasoning_content" not in canonical.message
        assert len(requests) == 1

        value["choices"][0]["finish_reason"] = "stop"
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=value))
        ) as http:
            with pytest.raises(ReviewError) as failure:
                await OpenClawClient(Settings(), client=http).complete([], Budget(Settings()))
        assert failure.value.code is ErrorCode.INVALID_MODEL_OUTPUT

    asyncio.run(run())


def test_escaped_surrogate_in_response_is_invalid_not_a_transcript_crash() -> None:
    raw = (
        rb'{"choices":[{"message":{"role":"assistant","content":"\ud800"},'
        rb'"finish_reason":"stop"}]}'
    )

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=raw))
        ) as http:
            with pytest.raises(ReviewError) as failure:
                await OpenClawClient(Settings(), client=http).complete([], Budget(Settings()))
        assert failure.value.code is ErrorCode.INVALID_MODEL_OUTPUT

    asyncio.run(run())


def test_malformed_unicode_transcript_is_rejected_before_request_or_budget_use() -> None:
    async def run():
        requests = []
        budget = Budget(Settings())
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: requests.append(request) or httpx.Response(200, json=response())
            )
        ) as http:
            with pytest.raises(ReviewError) as failure:
                await OpenClawClient(Settings(), client=http).complete(
                    [{"role": "user", "content": "\ud800"}], budget
                )
        assert failure.value.code is ErrorCode.INVALID_MODEL_OUTPUT
        assert requests == [] and budget.model_attempts == 0
        assert budget.input_tokens == budget.output_tokens == 0

    asyncio.run(run())


def test_transport_failure_uses_only_one_bounded_retry_and_hides_details() -> None:
    async def run():
        requests = []

        def unavailable(request):
            requests.append(request)
            raise httpx.ConnectError("sensitive-upstream-detail", request=request)

        settings = Settings()
        budget = Budget(settings)
        async with httpx.AsyncClient(transport=httpx.MockTransport(unavailable)) as http:
            with pytest.raises(ReviewError) as failure:
                await OpenClawClient(settings, client=http).complete([], budget)
        assert failure.value.code is ErrorCode.OPENCLAW_UNAVAILABLE
        assert "sensitive-upstream-detail" not in failure.value.message
        assert len(requests) == budget.model_attempts == 2

    asyncio.run(run())
