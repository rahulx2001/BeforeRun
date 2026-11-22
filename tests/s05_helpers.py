"""Inert helpers for S05. No live package-manager or target-code behavior."""

from __future__ import annotations

import json
from pathlib import Path

from review_helpers import context

from beforerun.features.contracts import CommandContext, ReviewInput
from beforerun.features.npm_setup import NpmSetupAnalyzer
from beforerun.features.pipeline import AnalysisContext

FIXTURES = Path(__file__).parent / "fixtures/npm_setup"


def fixture_files(case: str) -> dict[str, bytes]:
    root = FIXTURES / case
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def review_input(command: CommandContext = CommandContext.NPM_INSTALL) -> ReviewInput:
    return ReviewInput(
        repository_url="https://github.com/example/inert-fixture",
        command_context=command,
    )


async def analyze(
    files: dict[str, bytes],
    *,
    command: CommandContext = CommandContext.NPM_INSTALL,
    baseline: dict[str, bytes] | None = None,
    max_depth: int = 4,
    max_helper_files: int = 24,
) -> tuple[object, object, object, AnalysisContext]:
    snapshot, ledger, budget = context(files, baseline)
    analyzer = NpmSetupAnalyzer(max_depth=max_depth, max_helper_files=max_helper_files)
    result = await analyzer.analyze(review_input(command), snapshot, ledger, budget)
    return snapshot, ledger, budget, result


def manifest(scripts: dict[str, str], **extra: object) -> bytes:
    return json.dumps({"name": "inert", "version": "1.0.0", "scripts": scripts, **extra}).encode()


def error_text(analysis: AnalysisContext) -> str:
    return " ".join(error.message for error in analysis.errors)


def evidence_paths(snapshot, ledger, analysis: AnalysisContext) -> set[str]:
    return {
        snapshot.require_file(ledger.require(evidence_id).file_id).record.path
        for evidence_id in analysis.seed_evidence_ids
    }
