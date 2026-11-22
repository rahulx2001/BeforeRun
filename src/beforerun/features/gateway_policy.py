"""Server-owned configured provider disclosure; never contains API credentials."""

from __future__ import annotations

import os
from dataclasses import dataclass

BASETEN_MODEL = "meta-models/muse-spark-open-1026"
BASETEN_FALLBACK = "baseten/" + BASETEN_MODEL
CEREBRAS_PRIMARY = "cerebras/moonshotai-kimi-k3.1-pro-trial"


@dataclass(frozen=True)
class GatewayModelPolicy:
    fallback_model: str | None = None

    def __post_init__(self) -> None:
        if self.fallback_model not in {None, BASETEN_FALLBACK}:
            raise ValueError("The Gateway fallback must be the explicitly approved model.")

    @classmethod
    def from_environment(cls) -> GatewayModelPolicy:
        return cls(fallback_model=os.environ.get("OPENCLAW_FALLBACK_MODEL") or None)

    @property
    def disclosure(self) -> str | None:
        if not self.fallback_model:
            return None
        return (
            f"Configured Gateway primary: {CEREBRAS_PRIMARY}; automatic fallback: "
            f"{self.fallback_model}. Eligible upstream failures may switch providers. "
            "The returned reviewer alias does not verify which upstream answered; "
            "a Baseten response is not Cerebras/Kimi proof."
        )

    def public_data(self) -> dict:
        return {
            "primary": CEREBRAS_PRIMARY,
            "fallback": self.fallback_model,
            "automatic_fallback_configured": self.fallback_model is not None,
            "configured_policy_only": True,
            "actual_upstream_verified": False,
        }
