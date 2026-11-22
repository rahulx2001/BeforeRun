"""End-to-end checked pipeline with both GitHub and OpenClaw HTTP fully mocked."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta

import httpx
from fastapi.testclient import TestClient
from test_investigator import native
from test_openclaw_contract import response
from test_review_api import wait_terminal

from beforerun.app import app
from beforerun.features.budgets import Budget
from beforerun.features.contracts import EventType, JobState, ReviewInput, RevisionSide
from beforerun.features.github_source import GitHubSource
from beforerun.features.job_store import JobStore
from beforerun.features.openclaw_client import OpenClawClient
from beforerun.features.pipeline import AnalysisContext, CheckedReviewPipeline
from beforerun.features.review_service import ReviewService
from beforerun.features.settings import Settings


class FixtureAnalyzer:
    """Development compatibility fixture, not an independent model evaluation."""

    async def analyze(self, intake, snapshot, ledger, budget):
        file_id = snapshot.file_id(RevisionSide.TARGET, "package.json")
        await snapshot.admit_file(file_id)
        seed = ledger.issue(file_id)
        return AnalysisContext(
            seed_evidence_ids=(seed.evidence_id,),
            required_file_ids=frozenset(snapshot.paths[RevisionSide.TARGET].values()),
            assumptions=("OFFLINE FIXTURE: compatibility plumbing, not live model quality.",),
        )


def harness(analyzer=True):
    settings = Settings()
    files = {
        "package.json": b'{"scripts":{"prepare":"node helper.js"}}',
        "helper.js": b"// Inert Node 22 compatibility check.\n",
    }
    entries = []
    blobs = {}
    for path, raw in files.items():
        sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": sha})
        blobs[sha] = raw
    source_requests, model_requests = [], []

    def source_reply(request):
        source_requests.append(request)
        path = request.url.path
        if path == "/repos/example/inert-fixture":
            value = {
                "id": 1,
                "owner": {"login": "example"},
                "name": "inert-fixture",
                "default_branch": "main",
                "private": False,
                "visibility": "public",
            }
        elif "/git/commits/" in path:
            value = {"sha": "1" * 40, "tree": {"sha": "2" * 40}}
        elif "/commits/" in path:
            if path.endswith("/missing"):
                return httpx.Response(404)
            return httpx.Response(200, content=b"1" * 40)
        elif "/git/trees/" in path:
            value = {"sha": "2" * 40, "truncated": False, "tree": entries}
        elif "/git/blobs/" in path:
            sha = path.rsplit("/", 1)[-1]
            raw = blobs[sha]
            value = {
                "sha": sha,
                "size": len(raw),
                "encoding": "base64",
                "content": base64.b64encode(raw).decode(),
            }
        else:
            raise AssertionError("Unexpected source request")
        return httpx.Response(200, json=value)

    def model_reply(request):
        payload = json.loads(request.content)
        model_requests.append(payload)
        initial = json.loads(payload["messages"][1]["content"])
        helper = next(
            item for item in initial["context"]["available_files"] if item["path"] == "helper.js"
        )
        tool_messages = [message for message in payload["messages"] if message["role"] == "tool"]
        if payload["tool_choice"] == "none":
            value = response(
                json.dumps(
                    {
                        "assessment": "benign",
                        "summary": "Inert compatibility fixture.",
                        "findings": [],
                        "stop_reason": "finished",
                    }
                )
            )
        elif not tool_messages:
            value = response(
                None,
                [
                    native(
                        "br_read_excerpt",
                        {
                            "file_id": helper["file_id"],
                            "first_original_line": 1,
                            "last_original_line": 1,
                        },
                        "helper_read",
                    )
                ],
            )
        else:
            value = response(
                None, [native("br_finish", {"reason": "Compatibility source inspected."}, "finish")]
            )
        return httpx.Response(200, json=value)

    source_http = httpx.AsyncClient(transport=httpx.MockTransport(source_reply))
    model_http = httpx.AsyncClient(transport=httpx.MockTransport(model_reply))
    pipeline = CheckedReviewPipeline(
        settings,
        FixtureAnalyzer() if analyzer else None,
        source_factory=lambda budget: GitHubSource(settings, budget, client=source_http),
        reviewer_factory=lambda: OpenClawClient(settings, client=model_http),
        mode="mock",
    )
    return pipeline, source_requests, model_requests


def test_owned_api_runs_the_checked_pipeline_with_mocked_http_and_real_events() -> None:
    pipeline, source_calls, model_calls = harness()
    original = app.state.review_service
    app.state.review_service = ReviewService(pipeline.settings, pipeline, reviews_enabled=True)
    try:
        with TestClient(app, base_url="http://127.0.0.1") as client:
            accepted = client.post(
                "/api/reviews",
                json={
                    "repository_url": "https://github.com/example/inert-fixture",
                    "command_context": "review_only",
                },
                headers={"x-beforerun-request": "1"},
            )
            assert accepted.status_code == 202
            review_id = accepted.json()["review_id"]
            status = wait_terminal(client, review_id)
            report = status["report"]
            assert report["review_id"] == review_id
            assert report["completion"] == "complete" and report["assessment"] == "benign"
            assert report["coverage"]["model_shown_files"] == 2
            assert status["pipeline_mode"] == "mock"
            assert len(source_calls) == 6 and len(model_calls) == 3
            events = client.get(f"/api/reviews/{review_id}/events").json()["events"]
            assert any(item["event_type"] == "revision_pinned" for item in events)
            assert any(item["event_type"] == "evidence_delivered" for item in events)
            assert events[-1]["event_type"] == "terminal"
            exported = client.get(f"/api/reviews/{review_id}/export").json()
            assert exported["report"]["target"]["commit_sha"] == "1" * 40
            client.cookies.clear()
            assert client.get(f"/api/reviews/{review_id}").status_code == 404
    finally:
        app.state.review_service = original


def test_investigation_context_contains_pairs_gaps_files_and_real_limits() -> None:
    async def run():
        pipeline, _, model_calls = harness()
        intake = ReviewInput(
            repository_url="https://github.com/example/inert-fixture",
            baseline_ref="main",
            command_context="npm_install",
        )
        budget = Budget(pipeline.settings)
        result = await pipeline.run("review_" + "p" * 24, intake, budget, budget.cancel_event)
        assert result.report.completion.value == "complete"
        initial = json.loads(model_calls[0]["messages"][1]["content"])
        context = initial["context"]
        assert context["analysis_errors"] == []
        assert {item["path"] for item in context["required_files"]} == {
            "package.json",
            "helper.js",
        }
        comparison = context["comparison"]
        assert comparison["requested"] and comparison["complete"]
        assert not comparison["entries_truncated"] and len(comparison["entries"]) == 2
        assert all(item["change"] == "unchanged" for item in comparison["entries"])
        assert all(item["file_pair_id"].startswith("pair_") for item in comparison["entries"])
        remaining = context["remaining_budget"]
        assert remaining["decision_turns"] == 6
        assert remaining["tool_operations"] == 6
        assert remaining["model_attempts"] == 8
        assert 0 < remaining["runtime_ms"] <= 90_000

    asyncio.run(run())


def test_missing_baseline_keeps_target_and_unconnected_analyzer_is_unsupported() -> None:
    async def run():
        pipeline, _, calls = harness()
        intake = ReviewInput(
            repository_url="https://github.com/example/inert-fixture", baseline_ref="missing"
        )
        budget = Budget(pipeline.settings)
        result = await pipeline.run("review_" + "x" * 24, intake, budget, budget.cancel_event)
        assert result.report.completion.value == "partial"
        assert result.comparison.error and calls
        unavailable, _, calls = harness(analyzer=False)
        budget = Budget(unavailable.settings)
        result = await unavailable.run("review_" + "y" * 24, intake, budget, budget.cancel_event)
        assert result.report.completion.value == "unsupported"
        assert result.report.assessment.value == "undetermined" and calls == []

    asyncio.run(run())


def test_expiry_cancels_active_work_clears_idempotency_and_restart_does_not_restore() -> None:
    async def run():
        store = JobStore(Settings())
        intake = ReviewInput(repository_url="https://github.com/example/inert-fixture")
        record, _ = await store.create("owner", intake, "expiry-key")
        record.status = record.status.model_copy(
            update={"updated_at": datetime.now(UTC) - timedelta(hours=2)}
        )
        assert store.owned(record.review_id, "owner") is None
        assert record.budget.cancel_event.is_set() and not store.idempotency
        new, replay = await store.create("owner", intake, "expiry-key")
        assert not replay and new.review_id != record.review_id
        restarted = JobStore(Settings())
        assert restarted.owned(new.review_id, "owner") is None

    asyncio.run(run())


def test_event_pages_are_bounded_and_reconnect_cursor_reports_pruning() -> None:
    async def run():
        store = JobStore(Settings())
        record, _ = await store.create(
            "owner", ReviewInput(repository_url="https://github.com/example/inert-fixture"), None
        )
        for _ in range(510):
            await store.record_event(record, EventType.FILE_FETCHED, "Fixture source fetched.", {})
        page = await store.event_page(record, 0, 100)
        assert page["truncated"] and len(page["events"]) == 100
        assert len(record.events) == 500
        assert record.status.state is JobState.QUEUED

    asyncio.run(run())
