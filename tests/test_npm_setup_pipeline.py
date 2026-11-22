"""S05 adapter integration with all HTTP mocked by the existing offline pipeline harness."""

from __future__ import annotations

import asyncio
import json

from test_pipeline import harness

from beforerun.features.budgets import Budget
from beforerun.features.contracts import CommandContext, ReviewInput
from beforerun.features.npm_setup import NpmSetupAnalyzer


def test_real_analyzer_seeds_helper_and_relationship_through_checked_pipeline() -> None:
    async def run():
        pipeline, _, model_calls = harness()
        pipeline.analyzer = NpmSetupAnalyzer()
        intake = ReviewInput(
            repository_url="https://github.com/example/inert-fixture",
            command_context=CommandContext.NPM_INSTALL,
        )
        budget = Budget(pipeline.settings)
        result = await pipeline.run("review_" + "n" * 24, intake, budget, budget.cancel_event)
        assert result.report.completion.value == "complete"
        assert result.report.assessment.value == "benign"
        assert result.report.coverage.model_shown_files == 2
        assert any("npm 11.21.3" in item for item in result.report.assumptions)
        initial = json.loads(model_calls[0]["messages"][1]["content"])
        assert len(initial["source_evidence"]) == 2
        assert initial["context"]["signals"] == []
        assert len(initial["context"]["relationships"]) == 1
        edge = initial["context"]["relationships"][0]
        assert edge["kind"] == "npm_lifecycle_local_command"
        assert edge["support"] == "supported"

    asyncio.run(run())
