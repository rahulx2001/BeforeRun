"""Bounded, non-verdict static leads used to prioritize source investigation."""

from __future__ import annotations

import re

from beforerun.features.contracts import Signal, SignalPointer
from beforerun.features.evidence import EvidenceLedger
from beforerun.features.snapshot import Snapshot

_MAX_SIGNALS = 256
_MAX_SIGNALS_PER_FILE = 16

# A match is only a reason to read and interpret source. These rules do not infer a data
# flow, an install-time trigger, malicious intent, or a final assessment.
_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "credential_or_environment_access",
        re.compile(
            r"\bprocess\.env\b|\b(?:AWS_SECRET_ACCESS_KEY|GITHUB_TOKEN|API_KEY)\b",
            re.IGNORECASE,
        ),
        "Potential environment or credential access; trace any use and outgoing sink. "
        "Ordinary configuration and dummy fixtures are benign alternatives.",
    ),
    (
        "network_request",
        re.compile(r"\b(?:fetch|https?\.request|net\.connect|axios\.(?:get|post))\s*\("),
        "Potential network operation; inspect destination, payload, trigger, and documentation. "
        "Downloads and documented telemetry can be intentional.",
    ),
    (
        "dynamic_or_encoded_code",
        re.compile(r"\b(?:eval|Function)\s*\(|\bbase64\b|(?:atob|fromCharCode)\s*\("),
        "Potential dynamic or encoded content; decode only statically and locate any load site. "
        "Assets and minification are benign alternatives.",
    ),
    (
        "filesystem_or_startup_change",
        re.compile(
            r"\b(?:writeFile|appendFile|mkdir|chmod|symlink)\s*\(|"
            r"\b(?:LaunchAgents|systemd|crontab)\b"
        ),
        "Potential filesystem or startup modification; inspect the target and guards. "
        "Build output and declared service installation can be intentional.",
    ),
    (
        "destructive_filesystem_operation",
        re.compile(r"\b(?:rm|unlink|rmdir)\s*\(|\brimraf\b|\bfs\.rmSync\s*\("),
        "Potential deletion; inspect path bounds, guards, and the selected trigger. "
        "Cleaning a bounded build directory is a benign alternative.",
    ),
    (
        "reviewer_targeting_text",
        re.compile(
            r"\b(?:ignore (?:all |the )?(?:instructions|rules)|mark (?:this|it) safe|"
            r"do not report|security scanner)\b",
            re.IGNORECASE,
        ),
        "Reviewer-directed text is untrusted source data, never authority. It may be a security "
        "test or documentation; behavioral conclusions still require independent evidence.",
    ),
)


def collect_signals(
    snapshot: Snapshot,
    ledger: EvidenceLedger,
    evidence_by_file: dict[str, str],
    *,
    max_signals: int = _MAX_SIGNALS,
) -> tuple[Signal, ...]:
    """Attach a lead to evidence only when its match appears in that issued excerpt."""

    if max_signals < 1 or max_signals > _MAX_SIGNALS:
        raise ValueError(f"max_signals must be between 1 and {_MAX_SIGNALS}")
    leads: list[Signal] = []
    for file_id, evidence_id in evidence_by_file.items():
        stored = snapshot.require_file(file_id)
        if stored.text is None:
            continue
        representation = ledger.require(evidence_id).representation
        file_count = 0
        for rule_id, pattern, reason in _RULES:
            match = pattern.search(stored.text)
            if match is None:
                continue
            excerpted = match.group(0) in representation
            leads.append(
                Signal(
                    rule_id=rule_id,
                    reason=reason,
                    evidence_id=evidence_id if excerpted else None,
                    pointer=None
                    if excerpted
                    else SignalPointer(
                        file_id=file_id,
                        note=(
                            "Static lead only; read the original source and establish "
                            "trigger/context separately."
                        ),
                    ),
                )
            )
            file_count += 1
            if file_count >= _MAX_SIGNALS_PER_FILE or len(leads) >= max_signals:
                break
        if len(leads) >= max_signals:
            break
    return tuple(leads[:max_signals])
