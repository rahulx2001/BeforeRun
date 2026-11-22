"""Repeated MOCK pipeline timings. No live provider, price, accuracy, or SLA claims."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import statistics
import sys
import time
from pathlib import Path

from beforerun.features.budgets import Budget
from beforerun.features.contracts import ReviewInput
from beforerun.features.npm_setup import NpmSetupAnalyzer

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests"))


async def measure(repeats: int) -> list[dict]:
    from test_pipeline import harness

    runs = []
    for number in range(repeats):
        pipeline, source_calls, model_calls = harness()
        pipeline.analyzer = NpmSetupAnalyzer()
        pipeline.withhold_helper = True
        budget = Budget(pipeline.settings)
        intake = ReviewInput(
            repository_url="https://github.com/example/inert-fixture", command_context="npm_install"
        )
        started = time.perf_counter()
        result = await pipeline.run(
            "review_" + f"measurement_{number:016d}", intake, budget, budget.cancel_event
        )
        runs.append(
            {
                "run": number + 1,
                "wall_ms": (time.perf_counter() - started) * 1000,
                "completion": result.report.completion.value,
                "assessment": result.report.assessment.value,
                "mock_github_requests": len(source_calls),
                "mock_reviewer_requests": len(model_calls),
                "model_shown_files": result.report.coverage.model_shown_files,
                "tool_operations": budget.tool_operations,
            }
        )
    return runs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20:
        parser.error("repeats must be between 1 and 20")
    runs = asyncio.run(measure(args.repeats))
    elapsed = [run["wall_ms"] for run in runs]
    sources = sorted(
        [
            *(ROOT / "src/beforerun").rglob("*.py"),
            *(ROOT / "src/beforerun/features/prompts").glob("*.txt"),
        ]
    )
    fingerprint = hashlib.sha256()
    for path in sources:
        fingerprint.update(str(path.relative_to(ROOT)).encode())
        fingerprint.update(path.read_bytes())
    value = {
        "mode": "MOCK_HTTP_DEVELOPMENT_REGRESSION",
        "runs": runs,
        "timing_boundary": "Pipeline only, mocked HTTP; excludes queue, browser and live latency",
        "median_ms": statistics.median(elapsed),
        "range_ms": [min(elapsed), max(elapsed)],
        "provider_cost": "unknown; no live provider request made",
        "provider_tokens": "not measured; mock usage metadata is not billable usage",
        "accuracy": "not measured; not an independent held-out malware corpus",
        "working_tree_source_sha256": fingerprint.hexdigest(),
        "python": sys.version.split()[0],
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("fastapi", "httpx", "pydantic", "pytest")
        },
    }
    args.output.write_text(json.dumps(value, indent=2) + "\n")


if __name__ == "__main__":
    main()
