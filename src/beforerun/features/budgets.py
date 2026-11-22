"""One shared, monotonic budget for retrieval, tools, model calls, and repair."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from beforerun.features.contracts import BudgetUsage, ErrorCode
from beforerun.features.settings import Settings


class ReviewError(Exception):
    """A stable public error; upstream bodies and secrets never become messages."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class BudgetExceeded(ReviewError):
    def __init__(self, message: str = "The shared review budget is exhausted.") -> None:
        super().__init__(ErrorCode.BUDGET_EXHAUSTED, message)


@dataclass(frozen=True, slots=True)
class TokenReservation:
    reservation_id: int
    reserved_input_tokens: int
    reserved_output_tokens: int
    reconciled: bool = False


@dataclass(slots=True)
class Budget:
    settings: Settings
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    started_at: float = field(default_factory=time.monotonic)
    clock: Callable[[], float] = field(default=time.monotonic, repr=False)
    github_attempts: int = 0
    model_attempts: int = 0
    decision_turns: int = 0
    tool_operations: int = 0
    distinct_blobs: int = 0
    source_bytes: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    final_attempts: int = 0
    repairs: int = 0
    tree_entries: int = 0
    tree_envelope_bytes: int = 0
    _blob_ids: set[tuple[str, str]] = field(default_factory=set)
    _retry_operations: set[str] = field(default_factory=set)
    _token_reservations: dict[int, TokenReservation] = field(default_factory=dict)
    _next_token_reservation: int = 0

    def start(self) -> None:
        """Start the runtime allowance after the separate queue wait."""

        if self.cancel_event.is_set():
            raise ReviewError(ErrorCode.REVIEW_CANCELLED, "Review cancellation was requested.")
        self.started_at = self.clock()

    def check(self) -> None:
        if self.cancel_event.is_set():
            raise ReviewError(ErrorCode.REVIEW_CANCELLED, "Review cancellation was requested.")
        if self.remaining_seconds <= 0:
            raise BudgetExceeded("The review exceeded its wall-clock deadline.")

    @property
    def elapsed_ms(self) -> int:
        return max(0, int((self.clock() - self.started_at) * 1000))

    @property
    def remaining_seconds(self) -> float:
        elapsed = self.clock() - self.started_at
        return max(0.0, self.settings.runtime_seconds - elapsed)

    @staticmethod
    def _nonnegative_int(value: int, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{label} must be a nonnegative integer")
        return value

    def _reserve_retry(self, operation_id: str | None, is_retry: bool) -> None:
        if not is_retry:
            return
        if operation_id is None or not 1 <= len(operation_id) <= 128:
            raise ValueError("a retry requires an operation ID containing 1-128 characters")
        if operation_id in self._retry_operations:
            raise BudgetExceeded("This operation already used its one transient retry.")
        self._retry_operations.add(operation_id)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Conservative estimator used when the upstream tokenizer is unavailable."""

        return max(1, (len(text.encode("utf-8")) + 2) // 3)

    def reserve_github(self, operation_id: str | None = None, *, is_retry: bool = False) -> None:
        self.check()
        if self.github_attempts >= self.settings.max_github_attempts:
            raise BudgetExceeded("The GitHub request limit was reached.")
        self._reserve_retry(operation_id, is_retry)
        self.github_attempts += 1

    def reserve_model(
        self,
        *,
        final: bool = False,
        repair: bool = False,
        operation_id: str | None = None,
        is_retry: bool = False,
    ) -> None:
        self.check()
        if self.model_attempts >= self.settings.max_model_attempts:
            raise BudgetExceeded("The model request limit was reached.")
        if repair and self.repairs >= 1:
            raise BudgetExceeded("A model-output repair was already attempted.")
        if final and not is_retry and self.final_attempts >= 1:
            raise BudgetExceeded("The initial final response was already requested.")
        self._reserve_retry(operation_id, is_retry)
        if final:
            self.final_attempts += 1
        if repair:
            self.repairs += 1
        self.model_attempts += 1

    def reserve_decision(self) -> None:
        self.check()
        if self.final_attempts:
            raise BudgetExceeded("Finalization forbids further decision turns.")
        if self.decision_turns >= self.settings.max_decision_turns:
            raise BudgetExceeded("The model decision limit was reached.")
        self.decision_turns += 1

    def reserve_tool(self) -> None:
        self.check()
        if self.final_attempts:
            raise BudgetExceeded("Finalization forbids further tool operations.")
        if self.tool_operations >= self.settings.max_tool_operations:
            raise BudgetExceeded("The snapshot tool-operation limit was reached.")
        self.tool_operations += 1

    def reserve_tokens(
        self,
        *,
        estimated_input_tokens: int,
        requested_output_tokens: int,
    ) -> TokenReservation:
        """Reserve cumulative history and output before an upstream request."""

        input_tokens = self._nonnegative_int(estimated_input_tokens, "estimated input tokens")
        output_tokens = self._nonnegative_int(requested_output_tokens, "requested output tokens")
        if output_tokens == 0:
            raise ValueError("a model attempt requires a positive output allowance")
        self.check()
        if self.input_tokens + input_tokens > self.settings.max_input_tokens:
            raise BudgetExceeded("The cumulative estimated input-token limit was reached.")
        if self.output_tokens + output_tokens > self.settings.max_output_tokens:
            raise BudgetExceeded("The cumulative output-token allowance was reached.")
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self._next_token_reservation += 1
        reservation = TokenReservation(
            self._next_token_reservation,
            input_tokens,
            output_tokens,
        )
        self._token_reservations[reservation.reservation_id] = reservation
        return reservation

    def reconcile_tokens(
        self,
        reservation: TokenReservation,
        *,
        actual_input_tokens: int,
        actual_output_tokens: int,
    ) -> None:
        """Replace exact reservations with provider usage; observed overage stays visible."""

        actual_input = self._nonnegative_int(actual_input_tokens, "actual input tokens")
        actual_output = self._nonnegative_int(actual_output_tokens, "actual output tokens")
        stored = self._token_reservations.get(reservation.reservation_id)
        if stored is None or stored != reservation or stored.reconciled:
            raise ValueError("unknown or already reconciled token reservation")
        self.input_tokens += actual_input - stored.reserved_input_tokens
        self.output_tokens += actual_output - stored.reserved_output_tokens
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise AssertionError("token reconciliation produced negative accounting")
        self._token_reservations[stored.reservation_id] = TokenReservation(
            stored.reservation_id,
            actual_input,
            actual_output,
            reconciled=True,
        )
        if self.input_tokens > self.settings.max_input_tokens:
            raise BudgetExceeded("Actual model input exceeded the cumulative token budget.")
        if self.output_tokens > self.settings.max_output_tokens:
            raise BudgetExceeded("Actual model output exceeded the cumulative token budget.")

    def add_source(self, repository_id: int, blob_id: str, byte_length: int) -> None:
        self.check()
        if byte_length < 0 or byte_length > self.settings.max_file_bytes:
            raise ReviewError(
                ErrorCode.SOURCE_LIMIT, "A selected blob exceeds the file-size limit."
            )
        key = (str(repository_id), blob_id)
        if key in self._blob_ids:
            return
        if len(self._blob_ids) >= self.settings.max_distinct_blobs:
            raise ReviewError(ErrorCode.SOURCE_LIMIT, "The distinct-blob limit was reached.")
        if self.source_bytes + byte_length > self.settings.max_source_bytes:
            raise ReviewError(ErrorCode.SOURCE_LIMIT, "The decoded-source byte limit was reached.")
        self._blob_ids.add(key)
        self.distinct_blobs = len(self._blob_ids)
        self.source_bytes += byte_length

    def add_tree_bytes(self, byte_length: int) -> None:
        self.check()
        self._nonnegative_int(byte_length, "tree response byte length")
        if self.tree_envelope_bytes + byte_length > self.settings.max_tree_envelope_bytes:
            raise ReviewError(
                ErrorCode.SOURCE_LIMIT,
                "The shared target/baseline tree-response limit was reached.",
            )
        self.tree_envelope_bytes += byte_length

    def reserve_tree_entries(self, entry_count: int) -> int:
        self.check()
        count = self._nonnegative_int(entry_count, "tree entry count")
        remaining = max(0, self.settings.max_tree_entries - self.tree_entries)
        admitted = min(count, remaining)
        self.tree_entries += admitted
        return admitted

    def add_model_usage(self, request_text: str, output_text: str, allowance: int) -> None:
        """Count estimated request/history tokens and cap generated output locally."""

        input_tokens = self.estimate_tokens(request_text)
        output_tokens = self.estimate_tokens(output_text) if output_text else 0
        if self.input_tokens + input_tokens > self.settings.max_input_tokens:
            raise ReviewError(
                ErrorCode.BUDGET_EXHAUSTED, "The cumulative input-token limit was reached."
            )
        if self.output_tokens + output_tokens > self.settings.max_output_tokens:
            raise ReviewError(
                ErrorCode.BUDGET_EXHAUSTED, "The cumulative output-token limit was reached."
            )
        if allowance <= 0 or allowance > self.settings.max_output_tokens - self.output_tokens:
            raise BudgetExceeded("No bounded model-output allowance remains.")
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def usage(self) -> BudgetUsage:
        return BudgetUsage(
            elapsed_ms=self.elapsed_ms,
            remaining_ms=max(0, int(self.remaining_seconds * 1000)),
            github_attempts=self.github_attempts,
            model_attempts=self.model_attempts,
            decision_turns=self.decision_turns,
            tool_operations=self.tool_operations,
            distinct_blobs=self.distinct_blobs,
            source_bytes=self.source_bytes,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            final_attempts=self.final_attempts,
            repairs=self.repairs,
            tree_entries=self.tree_entries,
            tree_envelope_bytes=self.tree_envelope_bytes,
        )
