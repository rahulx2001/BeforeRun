from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from beforerun.app import app
from beforerun.features.budgets import ReviewError
from beforerun.features.contracts import ErrorCode, JobState, ReviewInput
from beforerun.features.review_service import PipelineResult, ReviewService
from beforerun.features.settings import Settings

FIXTURE = Path(__file__).parent / "fixtures/jobs/checked_result.json"
BASE_URL = "http://127.0.0.1"
MUTATION = {"x-beforerun-request": "1"}
INTAKE = {
    "repository_url": "https://github.com/example/inert-fixture",
    "target_ref": "target-fixture",
    "baseline_ref": "baseline-fixture",
    "command_context": "npm_install",
    "project_directory": ".",
}


def checked_result() -> PipelineResult:
    return PipelineResult.model_validate_json(FIXTURE.read_bytes())


def bound_result(result: PipelineResult, review_id: str) -> PipelineResult:
    return result.model_copy(
        update={"report": result.report.model_copy(update={"review_id": review_id})}
    )


class FakePipeline:
    def __init__(self) -> None:
        self.calls = 0
        self.result = checked_result()

    async def run(self, review_id, intake, budget, cancel_token):  # type: ignore[no-untyped-def]
        self.calls += 1
        await asyncio.sleep(0.01)
        return bound_result(self.result, review_id)


class CancelAwarePipeline:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, review_id, intake, budget, cancel_token):  # type: ignore[no-untyped-def]
        self.calls += 1
        while True:
            budget.check()
            await asyncio.sleep(0.005)


def make_service(pipeline=None) -> ReviewService:  # type: ignore[no-untyped-def]
    return ReviewService(
        Settings(runtime_seconds=5, queue_seconds=1, max_active_reviews=1, max_queued_reviews=2),
        pipeline,
        reviews_enabled=pipeline is not None,
    )


def post_review(client: TestClient, key: str = "fixture-key-123456") -> object:
    return client.post(
        "/api/reviews",
        json=INTAKE,
        headers={**MUTATION, "idempotency-key": key},
    )


def wait_terminal(client: TestClient, review_id: str) -> dict:  # type: ignore[type-arg]
    for _ in range(200):
        response = client.get(f"/api/reviews/{review_id}")
        assert response.status_code == 200
        value = response.json()
        if value["state"] == "terminal":
            return value
        time.sleep(0.005)
    raise AssertionError("fixture job did not become terminal")


async def wait_record_terminal(service: ReviewService, review_id: str) -> None:
    for _ in range(200):
        record = service.store.records[review_id]
        if record.status.state is JobState.TERMINAL:
            return
        await asyncio.sleep(0.005)
    raise AssertionError("async fixture job did not become terminal")


def test_queue_timeout_releases_no_stale_semaphore_acquire() -> None:
    class FirstCallBlockingPipeline:
        def __init__(self) -> None:
            self.calls = 0
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def run(self, review_id, intake, budget, cancel_token):  # type: ignore[no-untyped-def]
            self.calls += 1
            if self.calls == 1:
                self.started.set()
                await self.release.wait()
            return bound_result(checked_result(), review_id)

    async def run() -> None:
        pipeline = FirstCallBlockingPipeline()
        service = ReviewService(
            Settings(
                runtime_seconds=5,
                queue_seconds=0.05,
                max_active_reviews=1,
                max_queued_reviews=2,
            ),
            pipeline,
            reviews_enabled=True,
        )
        try:
            intake = ReviewInput.model_validate(INTAKE)
            first, _ = await service.submit("owner", intake, "queue-first-123456")
            await asyncio.wait_for(pipeline.started.wait(), timeout=1)
            queued, _ = await service.submit("owner", intake, "queue-second-123456")
            await asyncio.wait_for(wait_record_terminal(service, queued.review_id), timeout=1)
            assert queued.errors[0].code is ErrorCode.ADMISSION_LIMIT

            pipeline.release.set()
            await asyncio.wait_for(wait_record_terminal(service, first.review_id), timeout=1)
            assert first.report is not None

            third, _ = await service.submit("owner", intake, "queue-third-123456")
            await asyncio.wait_for(wait_record_terminal(service, third.review_id), timeout=1)
            assert third.errors == []
            assert third.report is not None
            assert pipeline.calls == 2
        finally:
            await service.close()

    asyncio.run(run())


def test_owned_checked_job_events_evidence_idempotency_and_export() -> None:
    pipeline = FakePipeline()
    app.state.review_service = make_service(pipeline)
    with TestClient(app, base_url=BASE_URL) as client:
        response = post_review(client)
        assert response.status_code == 202, response.text
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        review_id = response.json()["review_id"]

        replay = post_review(client)
        assert replay.status_code == 202
        assert replay.json()["review_id"] == review_id
        assert replay.headers["x-idempotent-replay"] == "true"
        assert pipeline.calls == 1

        conflict = client.post(
            "/api/reviews",
            json={**INTAKE, "target_ref": "different"},
            headers={**MUTATION, "idempotency-key": "fixture-key-123456"},
        )
        assert conflict.status_code == 409

        terminal = wait_terminal(client, review_id)
        assert terminal["report"]["assessment"] == "suspicious"
        assert terminal["report"]["completion"] == "partial"
        assert terminal["report"]["coverage"]["required_unresolved_files"]
        assert terminal["comparison"]["entries"][0]["change"] == "modified"

        events = client.get(f"/api/reviews/{review_id}/events?after=0")
        assert events.status_code == 200
        assert events.json()["events"][-1]["event_type"] == "terminal"
        cursor = events.json()["next_cursor"]
        assert client.get(f"/api/reviews/{review_id}/events?after={cursor}").json()["events"] == []

        evidence_id = terminal["report"]["findings"][0]["finding"]["evidence_ids"][0]
        evidence = client.get(f"/api/reviews/{review_id}/evidence/{evidence_id}")
        assert evidence.status_code == 200
        assert "<script>" in evidence.json()["evidence"]["representation"]
        assert evidence.json()["source_url"].startswith("https://github.com/")

        exported = client.get(f"/api/reviews/{review_id}/export?format=json")
        assert exported.status_code == 200
        assert "attachment" in exported.headers["content-disposition"]
        assert exported.json()["privacy"]["redaction"].startswith("Best-effort")
        assert "gateway_token" not in exported.text.lower()

        # A different owner gets the same non-revealing response for status and evidence.
        client.cookies.clear()
        denied_status = client.get(f"/api/reviews/{review_id}")
        denied_evidence = client.get(f"/api/reviews/{review_id}/evidence/{evidence_id}")
        unknown = client.get("/api/reviews/review_unknown1234567890")
        assert (
            denied_status.status_code == denied_evidence.status_code == unknown.status_code == 404
        )
        assert denied_status.json() == unknown.json()


def test_invalid_input_and_cross_origin_never_start_pipeline() -> None:
    pipeline = FakePipeline()
    app.state.review_service = make_service(pipeline)
    with TestClient(app, base_url=BASE_URL) as client:
        for value in (
            "http://github.com/example/repository",
            "https://github.com/example/repository/tree/main",
            "https://example.com/example/repository",
            "https://user:password@github.com/example/repository",
            "https://github.com:8443/example/repository",
            "https://github.com/example%2Frepository",
        ):
            response = client.post(
                "/api/reviews",
                json={**INTAKE, "repository_url": value},
                headers=MUTATION,
            )
            assert response.status_code == 422, value
        extra = client.post("/api/reviews", json={**INTAKE, "model": "attacker"}, headers=MUTATION)
        assert extra.status_code == 422
        assert "attacker" not in extra.text

        no_header = client.post("/api/reviews", json=INTAKE)
        cross_origin = client.post(
            "/api/reviews",
            json=INTAKE,
            headers={**MUTATION, "origin": "https://attacker.invalid"},
        )
        wrong_host = client.post(
            "/api/reviews",
            json=INTAKE,
            headers={**MUTATION, "host": "attacker.invalid"},
        )
        assert no_header.status_code == cross_origin.status_code == wrong_host.status_code == 403
        assert pipeline.calls == 0


def test_cancel_is_cooperative_and_terminal() -> None:
    pipeline = CancelAwarePipeline()
    app.state.review_service = make_service(pipeline)
    with TestClient(app, base_url=BASE_URL) as client:
        response = post_review(client, "cancel-key-123456")
        review_id = response.json()["review_id"]
        for _ in range(100):
            if pipeline.calls:
                break
            time.sleep(0.005)
        cancelled = client.post(f"/api/reviews/{review_id}/cancel", headers=MUTATION)
        assert cancelled.status_code == 202
        terminal = wait_terminal(client, review_id)
        assert terminal["stop_reason"] == "cancelled"
        assert terminal["cancel_requested"] is True
        assert terminal["report"] is None
        assert terminal["errors"][0]["code"] == ErrorCode.REVIEW_CANCELLED.value
        assert client.post(f"/api/reviews/{review_id}/cancel", headers=MUTATION).status_code == 202
        assert pipeline.calls == 1
        assert client.get(f"/api/reviews/{review_id}/export").status_code == 409


def test_global_admission_limit_counts_running_and_queued_jobs() -> None:
    pipeline = CancelAwarePipeline()
    app.state.review_service = make_service(pipeline)
    with TestClient(app, base_url=BASE_URL) as client:
        review_ids = []
        for index in range(3):
            response = post_review(client, f"queue-key-{index}-123456")
            assert response.status_code == 202
            review_ids.append(response.json()["review_id"])
        full = post_review(client, "queue-key-overflow-123456")
        assert full.status_code == 429
        assert full.json()["detail"]["code"] == "ADMISSION_LIMIT"
        for review_id in review_ids:
            client.post(f"/api/reviews/{review_id}/cancel", headers=MUTATION)


def test_health_is_liveness_not_scanner_readiness() -> None:
    app.state.review_service = make_service()
    with TestClient(app, base_url=BASE_URL) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["readiness_claimed"] is False
        assert response.json()["review_pipeline_connected"] is False
        capabilities = client.get("/api/capabilities")
        assert capabilities.status_code == 200
        assert capabilities.json()["browser_gateway_access"] is False
        assert capabilities.json()["review_enabled"] is False
        assert "OPENCLAW_GATEWAY_TOKEN" not in capabilities.text


def test_release_kill_switch_blocks_new_model_work() -> None:
    service = make_service()
    service.reviews_enabled = False
    app.state.review_service = service
    with TestClient(app, base_url=BASE_URL) as client:
        capabilities = client.get("/api/capabilities").json()
        assert capabilities["review_enabled"] is False
        response = post_review(client, "disabled-key-123456")
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "OPENCLAW_UNAVAILABLE"


def test_immediate_cancel_does_not_leak_worker_slot() -> None:
    async def run() -> None:
        service = make_service(FakePipeline())
        try:
            intake = ReviewInput.model_validate(INTAKE)
            record, _ = await service.store.create("owner", intake, None)
            record.budget.cancel_event.set()
            with pytest.raises(ReviewError) as caught:
                await service._wait_for_slot(record)
            assert caught.value.code is ErrorCode.REVIEW_CANCELLED
            assert service._semaphore._value == 1
            await asyncio.wait_for(service._semaphore.acquire(), timeout=0.1)
            service._semaphore.release()
        finally:
            await service.close()

    asyncio.run(run())


def test_runtime_deadline_fails_closed_and_releases_slot() -> None:
    class SlowPipeline:
        async def run(self, review_id, intake, budget, cancel_token):  # type: ignore[no-untyped-def]
            await asyncio.sleep(10)
            return bound_result(checked_result(), review_id)

    async def run() -> None:
        service = ReviewService(
            Settings(
                runtime_seconds=0.05,
                queue_seconds=1,
                max_active_reviews=1,
                max_queued_reviews=2,
            ),
            SlowPipeline(),
            reviews_enabled=True,
        )
        try:
            intake = ReviewInput.model_validate(INTAKE)
            record, _ = await service.submit("owner", intake, "deadline-key-123456")
            await asyncio.wait_for(wait_record_terminal(service, record.review_id), timeout=2)
            assert record.report is None
            assert record.errors[0].code is ErrorCode.BUDGET_EXHAUSTED
            assert service._semaphore._value == 1
        finally:
            await service.close()

    asyncio.run(run())


def test_report_identity_must_match_admitted_job() -> None:
    class WrongIdentityPipeline:
        async def run(self, review_id, intake, budget, cancel_token):  # type: ignore[no-untyped-def]
            return checked_result()

    class WrongInputPipeline:
        async def run(self, review_id, intake, budget, cancel_token):  # type: ignore[no-untyped-def]
            report = bound_result(checked_result(), review_id).report
            wrong_input = ReviewInput.model_validate({**INTAKE, "target_ref": "different"})
            return PipelineResult(report=report.model_copy(update={"review_input": wrong_input}))

    async def run() -> None:
        for key, pipeline in (
            ("identity-key-123456", WrongIdentityPipeline()),
            ("input-key-123456", WrongInputPipeline()),
        ):
            service = ReviewService(
                Settings(
                    runtime_seconds=5,
                    queue_seconds=1,
                    max_active_reviews=1,
                    max_queued_reviews=2,
                ),
                pipeline,
                reviews_enabled=True,
            )
            try:
                intake = ReviewInput.model_validate(INTAKE)
                record, _ = await service.submit("owner", intake, key)
                await asyncio.wait_for(wait_record_terminal(service, record.review_id), timeout=1)
                assert record.report is None
                assert record.errors[0].code is ErrorCode.INVALID_MODEL_OUTPUT
                assert service._semaphore._value == 1
            finally:
                await service.close()

    asyncio.run(run())
