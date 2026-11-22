"""Bounded stateless OpenClaw chat adapter. Credentials and routing are server-owned."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from beforerun.features.budgets import Budget, BudgetExceeded, ReviewError
from beforerun.features.contracts import ErrorCode, ModelAttemptKind
from beforerun.features.safe_tools import tool_definitions
from beforerun.features.settings import Settings, _validate_gateway_url

MAX_RESPONSE_BYTES = 64 * 1024


def _valid_unicode(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise ReviewError(
            ErrorCode.INVALID_MODEL_OUTPUT, "Reviewer text is not valid Unicode."
        ) from error
    return value


def _serialized_transcript(value: dict[str, Any]) -> str:
    try:
        serialized = json.dumps(value, ensure_ascii=False, allow_nan=False)
        serialized.encode("utf-8")
        return serialized
    except (TypeError, ValueError, UnicodeError) as error:
        raise ReviewError(
            ErrorCode.INVALID_MODEL_OUTPUT, "Reviewer transcript is not valid JSON text."
        ) from error


@dataclass(frozen=True)
class ModelReply:
    message: dict[str, Any]
    finish_reason: str
    response_model: str


class OpenClawClient:
    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.origin = _validate_gateway_url(settings.openclaw_base_url)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", settings.openclaw_agent):
            raise ValueError("reviewer agent must be a configured simple identifier")
        self._owned = client is None
        self.client = client or httpx.AsyncClient(
            follow_redirects=False, trust_env=False, timeout=30
        )

    async def close(self) -> None:
        if self._owned:
            await self.client.aclose()

    async def _exchange(self, payload: dict[str, Any], budget: Budget) -> dict[str, Any]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.settings.openclaw_gateway_token:
            headers["Authorization"] = "Bearer " + self.settings.openclaw_gateway_token
        async with self.client.stream(
            "POST",
            self.origin + "/v1/chat/completions",
            headers=headers,
            json=payload,
            follow_redirects=False,
        ) as response:
            budget.check()
            if 300 <= response.status_code < 400:
                raise ReviewError(
                    ErrorCode.OPENCLAW_UNAVAILABLE, "Gateway redirects are not permitted."
                )
            if response.status_code == 401:
                raise ReviewError(
                    ErrorCode.OPENCLAW_UNAVAILABLE, "Gateway authentication was rejected."
                )
            if response.status_code in {402, 403}:
                raise ReviewError(
                    ErrorCode.MODEL_ACCESS_DENIED, "The configured reviewer route denied access."
                )
            if response.status_code == 429 or response.status_code >= 500:
                raise ReviewError(
                    ErrorCode.OPENCLAW_UNAVAILABLE,
                    "The reviewer route is temporarily unavailable.",
                    retryable=True,
                )
            if response.status_code != 200:
                raise ReviewError(
                    ErrorCode.OPENCLAW_UNAVAILABLE,
                    "The configured reviewer endpoint is unavailable.",
                )
            declared = response.headers.get("content-length")
            if declared and (not declared.isdecimal() or int(declared) > MAX_RESPONSE_BYTES):
                raise ReviewError(
                    ErrorCode.INVALID_MODEL_OUTPUT, "The reviewer response exceeds its envelope."
                )
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                budget.check()
                if len(raw) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise ReviewError(
                        ErrorCode.INVALID_MODEL_OUTPUT,
                        "The reviewer response exceeds its envelope.",
                    )
                raw.extend(chunk)
            try:
                value = json.loads(bytes(raw))
            except (ValueError, UnicodeError, RecursionError) as error:
                raise ReviewError(
                    ErrorCode.INVALID_MODEL_OUTPUT, "The reviewer response is not bounded JSON."
                ) from error
            if not isinstance(value, dict):
                raise ReviewError(
                    ErrorCode.INVALID_MODEL_OUTPUT, "The reviewer response has an invalid shape."
                )
            return value

    async def _cancellable_exchange(
        self, payload: dict[str, Any], budget: Budget
    ) -> dict[str, Any]:
        request = asyncio.create_task(self._exchange(payload, budget))
        cancelled = asyncio.create_task(budget.cancel_event.wait())
        try:
            done, _ = await asyncio.wait(
                {request, cancelled},
                timeout=budget.remaining_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            budget.check()
            if request not in done:
                raise BudgetExceeded("The reviewer request exceeded the shared deadline.")
            return await request
        finally:
            cancelled.cancel()
            if not request.done():
                request.cancel()
            await asyncio.gather(request, cancelled, return_exceptions=True)

    async def complete(
        self,
        messages: list[dict[str, Any]],
        budget: Budget,
        *,
        kind: ModelAttemptKind = ModelAttemptKind.DECISION,
    ) -> ModelReply:
        budget.check()
        if self._owned and not self.settings.openclaw_gateway_token:
            raise ReviewError(
                ErrorCode.OPENCLAW_UNAVAILABLE, "The private Gateway credential is not configured."
            )
        final = kind is not ModelAttemptKind.DECISION
        available = self.settings.max_output_tokens - budget.output_tokens
        allowance = min(
            2048 if kind is ModelAttemptKind.FINAL else 1024,
            available - (3072 if not final else 0),
        )
        if allowance <= 0:
            raise BudgetExceeded("No bounded final/repair allowance remains.")
        payload = {
            "model": "openclaw/" + self.settings.openclaw_agent,
            "messages": messages,
            "tools": tool_definitions(),
            "tool_choice": "none" if final else "auto",
            "max_tokens": allowance,
            "stream": False,
        }
        # Full history is submitted statelessly. No account-wide user/session key is reused.
        estimated_input = budget.estimate_tokens(_serialized_transcript(payload))
        operation_id = f"model-{budget.model_attempts + 1}"
        for attempt in range(2):
            budget.reserve_model(
                final=kind is ModelAttemptKind.FINAL,
                repair=kind is ModelAttemptKind.REPAIR,
                operation_id=operation_id,
                is_retry=attempt > 0,
            )
            reservation = budget.reserve_tokens(
                estimated_input_tokens=estimated_input, requested_output_tokens=allowance
            )
            try:
                value = await self._cancellable_exchange(payload, budget)
            except (httpx.TimeoutException, httpx.TransportError) as error:
                if attempt == 0:
                    continue
                raise ReviewError(
                    ErrorCode.OPENCLAW_UNAVAILABLE, "The bounded Gateway request failed."
                ) from error
            except ReviewError as error:
                if attempt == 0 and error.retryable:
                    continue
                raise
            reported_model = value.get("model")
            if not isinstance(reported_model, str) or not reported_model:
                raise ReviewError(
                    ErrorCode.INVALID_MODEL_OUTPUT,
                    "Reviewer response is missing its model identity.",
                )
            reported_model = _valid_unicode(reported_model)
            if reported_model != self.settings.expected_response_model:
                raise ReviewError(
                    ErrorCode.MODEL_ACCESS_DENIED,
                    "The configured reviewer route returned an unexpected model.",
                )
            usage = value.get("usage")
            if isinstance(usage, dict):
                prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
                if any(
                    isinstance(item, bool) or not isinstance(item, int) or item < 0
                    for item in (prompt, completion)
                ):
                    raise ReviewError(
                        ErrorCode.INVALID_MODEL_OUTPUT, "Reviewer usage metadata is invalid."
                    )
                budget.reconcile_tokens(
                    reservation, actual_input_tokens=prompt, actual_output_tokens=completion
                )
            choices = value.get("choices")
            if (
                not isinstance(choices, list)
                or len(choices) != 1
                or not isinstance(choices[0], dict)
            ):
                raise ReviewError(ErrorCode.INVALID_MODEL_OUTPUT, "Expected one reviewer response.")
            choice = choices[0]
            message = choice.get("message")
            if not isinstance(message, dict) or message.get("role") != "assistant":
                raise ReviewError(ErrorCode.INVALID_MODEL_OUTPUT, "Expected an assistant response.")
            content = message.get("content")
            calls = message.get("tool_calls")
            if content is not None and not isinstance(content, str):
                raise ReviewError(
                    ErrorCode.INVALID_MODEL_OUTPUT, "Reviewer content has an invalid shape."
                )
            if content is not None:
                content = _valid_unicode(content)
            if calls is not None and (not isinstance(calls, list) or len(calls) > 2 or not calls):
                raise ReviewError(
                    ErrorCode.INVALID_MODEL_OUTPUT, "Reviewer tool array exceeds the contract."
                )
            canonical_calls = []
            for call in calls or ():
                if (
                    not isinstance(call, dict)
                    or call.get("type") != "function"
                    or not isinstance(call.get("id"), str)
                    or not isinstance(call.get("function"), dict)
                ):
                    raise ReviewError(
                        ErrorCode.INVALID_MODEL_OUTPUT, "Tool response identity is malformed."
                    )
                function = call["function"]
                name = function.get("name")
                arguments = function.get("arguments")
                if not isinstance(name, str) or not isinstance(arguments, str):
                    raise ReviewError(
                        ErrorCode.INVALID_MODEL_OUTPUT, "Tool function fields are malformed."
                    )
                # Preserve identity/arguments exactly while dropping private/provider extensions.
                canonical_calls.append(
                    {
                        "id": _valid_unicode(call["id"]),
                        "type": "function",
                        "function": {
                            "name": _valid_unicode(name),
                            "arguments": _valid_unicode(arguments),
                        },
                    }
                )
            finish = choice.get("finish_reason")
            if (
                finish not in {"stop", "tool_calls"}
                or bool(canonical_calls) != (finish == "tool_calls")
                or final
                and canonical_calls
            ):
                raise ReviewError(
                    ErrorCode.INVALID_MODEL_OUTPUT,
                    "Reviewer output is truncated, inconsistent, or violates final mode.",
                )
            # Ignore private reasoning and arbitrary upstream fields.
            canonical = {"role": "assistant", "content": content}
            if canonical_calls:
                canonical["tool_calls"] = canonical_calls
            return ModelReply(canonical, finish, reported_model)
        raise AssertionError("bounded retry loop must terminate")
