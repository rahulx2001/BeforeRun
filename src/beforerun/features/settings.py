"""Server-owned settings. Browser input can never override these values."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from functools import lru_cache
from ipaddress import ip_address
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class Settings:
    openclaw_base_url: str = "http://127.0.0.1:18789"
    openclaw_agent: str = "beforerun-reviewer"
    openclaw_expected_model: str | None = None
    openclaw_gateway_token: str | None = None
    github_token: str | None = None
    runtime_seconds: float = 90.0
    queue_seconds: float = 30.0
    max_github_attempts: int = 32
    max_model_attempts: int = 8
    max_decision_turns: int = 6
    max_tool_operations: int = 6
    max_distinct_blobs: int = 24
    max_source_bytes: int = 2 * 1024 * 1024
    max_file_bytes: int = 128 * 1024
    max_envelope_bytes: int = 256 * 1024
    max_tree_envelope_bytes: int = 4 * 1024 * 1024
    max_tree_entries: int = 20_000
    max_input_tokens: int = 50_000
    max_output_tokens: int = 6_000
    max_active_reviews: int = 1
    max_queued_reviews: int = 2
    job_ttl_seconds: float = 3600.0
    prompt_version: str = "investigator-v1"
    tool_policy_version: str = "snapshot-tools-v1"
    analyzer_version: str = "npm-root-v1"
    openclaw_version: str = "configured-gateway; runtime version unverified"

    @property
    def expected_response_model(self) -> str:
        """Response-layer identity expected from the configured Gateway route.

        This is not independent proof of the upstream provider; it prevents an
        accidental cross-route response from being accepted silently.
        """

        return self.openclaw_expected_model or f"openclaw/{self.openclaw_agent}"

    @property
    def model_route(self) -> str:
        # This is the configured Gateway route, not a claim about upstream delivery.
        return (
            f"openclaw/{self.openclaw_agent} "
            f"(expected response model {self.expected_response_model}; "
            "upstream route not independently verified)"
        )


def _validate_gateway_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("OPENCLAW_BASE_URL cannot contain credentials, query, or fragment")
    if parsed.path not in {"", "/"}:
        raise ValueError("OPENCLAW_BASE_URL must be an origin without a path")
    if parsed.scheme == "http":
        try:
            loopback = parsed.hostname and ip_address(parsed.hostname).is_loopback
        except ValueError:
            loopback = parsed.hostname == "localhost"
        if not loopback:
            raise ValueError("plain HTTP OpenClaw Gateway must be on a loopback host")
    elif parsed.scheme != "https":
        raise ValueError("OPENCLAW_BASE_URL must use HTTPS or loopback HTTP")
    if not parsed.hostname or parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("OPENCLAW_BASE_URL has an invalid host or port")
    return value.rstrip("/")


def _positive_int(name: str, default: int, maximum: int) -> int:
    value = int(os.environ.get(name, default))
    if value <= 0 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def _bounded_seconds(name: str, default: float, maximum: float) -> float:
    value = float(os.environ.get(name, default))
    if not math.isfinite(value) or value <= 0 or value > maximum:
        raise ValueError(f"{name} must be finite, positive, and at most {maximum}")
    return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Read process settings once; secrets stay server-side and are never serialized."""

    base = _validate_gateway_url(os.environ.get("OPENCLAW_BASE_URL", "http://127.0.0.1:18789"))
    agent = os.environ.get("OPENCLAW_AGENT", "beforerun-reviewer")
    if not agent or len(agent) > 80 or any(not c.isalnum() and c not in "-_" for c in agent):
        raise ValueError("OPENCLAW_AGENT must be a simple configured agent identifier")
    expected_model = os.environ.get("OPENCLAW_EXPECTED_MODEL") or None
    if expected_model and (
        len(expected_model) > 160
        or any(ord(character) < 32 or ord(character) == 127 for character in expected_model)
    ):
        raise ValueError("OPENCLAW_EXPECTED_MODEL must be a short printable model identifier")
    return Settings(
        openclaw_base_url=base,
        openclaw_agent=agent,
        openclaw_expected_model=expected_model,
        openclaw_gateway_token=os.environ.get("OPENCLAW_GATEWAY_TOKEN") or None,
        github_token=os.environ.get("GITHUB_TOKEN") or None,
        runtime_seconds=_bounded_seconds("BEFORERUN_RUNTIME_SECONDS", 90.0, 90.0),
        queue_seconds=_bounded_seconds("BEFORERUN_QUEUE_SECONDS", 30.0, 30.0),
        max_github_attempts=_positive_int("BEFORERUN_MAX_GITHUB_ATTEMPTS", 32, 32),
        max_model_attempts=_positive_int("BEFORERUN_MAX_MODEL_ATTEMPTS", 8, 8),
        max_active_reviews=_positive_int("BEFORERUN_MAX_ACTIVE_REVIEWS", 1, 1),
        max_queued_reviews=_positive_int("BEFORERUN_MAX_QUEUED_REVIEWS", 2, 2),
    )
