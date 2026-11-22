from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from beforerun.features.budgets import Budget, ReviewError
from beforerun.features.contracts import ErrorCode, FetchStatus, PinnedRevision, RevisionSide
from beforerun.features.github_source import GitHubSource, Repository, source_url
from beforerun.features.settings import Settings
from beforerun.features.snapshot import Snapshot

FIXTURE = Path(__file__).parent / "fixtures/source/moved_branch.json"
REV = PinnedRevision(
    revision_id="rev_target_abcdefghijklmnop",
    repository_id=101,
    canonical_owner="example",
    canonical_name="inert-fixture",
    requested_ref="main",
    commit_sha="1" * 40,
    tree_sha="2" * 40,
    resolution_timestamp=datetime.now(UTC),
    side=RevisionSide.TARGET,
)


def _blob_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def _response(value: dict[str, Any], status: int = 200) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(value).encode())


def test_moved_branch_never_changes_admitted_snapshot_identity() -> None:
    fixture = json.loads(FIXTURE.read_text())
    raw = fixture.pop("source_text").encode()
    blob_sha = _blob_sha(raw)
    blob = {
        "sha": blob_sha,
        "encoding": "base64",
        "size": len(raw),
        "content": base64.b64encode(raw).decode(),
    }
    fixture["tree"]["tree"][0]["sha"] = blob_sha
    requests: list[httpx.Request] = []
    commit_reads = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal commit_reads
        requests.append(request)
        assert request.url.scheme == "https"
        assert request.url.host == "api.github.com"
        assert request.headers["X-GitHub-Api-Version"] == "2026-03-10"
        if request.url.path == "/repos/example/inert-fixture":
            return _response(fixture["repository"])
        if request.url.path == "/repos/example/inert-fixture/commits/main":
            commit_reads += 1
            key = "initial_commit" if commit_reads == 1 else "moved_commit"
            assert request.headers["Accept"] == "application/vnd.github.sha"
            return httpx.Response(200, content=fixture[key]["sha"].encode("ascii"))
        if request.url.path.startswith("/repos/example/inert-fixture/git/commits/"):
            sha = request.url.path.rsplit("/", 1)[-1]
            key = "initial_commit" if sha == "1" * 40 else "moved_commit"
            commit = fixture[key]
            return _response({"sha": commit["sha"], "tree": commit["commit"]["tree"]})
        if request.url.path == ("/repos/example/inert-fixture/git/trees/" + "2" * 40):
            assert request.url.params["recursive"] == "1"
            return _response(fixture["tree"])
        if request.url.path == f"/repos/example/inert-fixture/git/blobs/{blob_sha}":
            return _response(blob)
        raise AssertionError(f"Unexpected request: {request.url}")

    async def run() -> None:
        settings = Settings()
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle), trust_env=False, follow_redirects=False
        ) as client:
            source = GitHubSource(settings, Budget(settings), client=client)
            repository = await source.repository("example", "inert-fixture")
            pinned = await source.pin(repository, None, RevisionSide.TARGET)
            snapshot = Snapshot({RevisionSide.TARGET: pinned}, source)
            entries, truncated = await source.tree(pinned)
            snapshot.register_tree(RevisionSide.TARGET, entries, truncated)
            record = await snapshot.admit_path(RevisionSide.TARGET, "package.json")
            moved = await source.pin(repository, None, RevisionSide.TARGET)

            assert pinned.commit_sha == "1" * 40
            assert moved.commit_sha == "3" * 40
            assert snapshot.revisions[RevisionSide.TARGET].commit_sha == "1" * 40
            assert record.fetch_status is FetchStatus.FETCHED
            assert snapshot.require_file(record.file_id).text == raw.decode()
            assert "1111111111111111111111111111111111111111" in source_url(
                pinned, record.path, 1, 1
            )
            assert all("/commits/main" not in str(item.url) for item in requests[2:4])

    asyncio.run(run())
    assert commit_reads == 2


def test_hostile_redirect_is_rejected_without_callback_or_token_forwarding() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/callback"})

    async def run() -> None:
        settings = Settings(github_token="inert-unit-test-token")
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle), trust_env=False, follow_redirects=False
        ) as client:
            source = GitHubSource(settings, Budget(settings), client=client)
            with pytest.raises(ReviewError) as caught:
                await source.repository("example", "project")
            assert caught.value.code is ErrorCode.INVALID_URL

    asyncio.run(run())
    assert len(requests) == 1
    assert requests[0].url.host == "api.github.com"
    assert requests[0].headers["Authorization"] == "Bearer inert-unit-test-token"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", True),
        ("id", "101"),
        ("owner", {"login": 101}),
        ("name", 101),
        ("default_branch", 101),
    ],
)
def test_repository_metadata_requires_unambiguous_types(field: str, value: object) -> None:
    metadata = {
        "id": 101,
        "owner": {"login": "example"},
        "name": "project",
        "default_branch": "main",
        "private": False,
        "visibility": "public",
    }
    metadata[field] = value

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: _response(metadata)),
            trust_env=False,
        ) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            with pytest.raises(ReviewError) as caught:
                await source.repository("example", "project")
            assert caught.value.code is ErrorCode.INVALID_INPUT

    asyncio.run(run())


@pytest.mark.parametrize(
    "private,visibility", [(True, "private"), (False, "internal"), (False, [])]
)
def test_repository_metadata_rejects_nonpublic_code(private: bool, visibility: object) -> None:
    metadata = {
        "id": 101,
        "owner": {"login": "example"},
        "name": "project",
        "default_branch": "main",
        "private": private,
        "visibility": visibility,
    }

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: _response(metadata)),
            trust_env=False,
        ) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            with pytest.raises(ReviewError) as caught:
                await source.repository("example", "project")
            assert caught.value.code is ErrorCode.INVALID_URL

    asyncio.run(run())


def test_malformed_commit_shape_is_a_stable_source_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, content=b"1" * 40)
        return _response({"sha": "1" * 40, "tree": []})

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle),
            trust_env=False,
        ) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            repository = Repository(
                repository_id=101,
                owner="example",
                name="project",
                default_branch="main",
            )
            with pytest.raises(ReviewError) as caught:
                await source.pin(repository, "main", RevisionSide.TARGET)
            assert caught.value.code is ErrorCode.INVALID_INPUT

    asyncio.run(run())


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [(429, ErrorCode.GITHUB_RATE_LIMIT, True), (404, ErrorCode.REF_NOT_FOUND, False)],
)
def test_rate_limit_and_missing_ref_are_honest_and_not_retried_forever(
    status: int, code: ErrorCode, retryable: bool
) -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, content=b"{}")

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle), trust_env=False
        ) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            with pytest.raises(ReviewError) as caught:
                await source.tree(REV)
            assert caught.value.code is code
            assert caught.value.retryable is retryable
            assert source.budget.usage().github_attempts == 1

    asyncio.run(run())
    assert len(requests) == 1


@pytest.mark.parametrize(
    ("headers", "expected_code", "retryable"),
    [
        ({}, ErrorCode.INVALID_URL, False),
        ({"X-RateLimit-Remaining": "0"}, ErrorCode.GITHUB_RATE_LIMIT, True),
        ({"Retry-After": "15"}, ErrorCode.GITHUB_RATE_LIMIT, True),
    ],
)
def test_access_denied_is_not_mislabeled_or_retried_as_rate_limit(
    headers: dict[str, str], expected_code: ErrorCode, retryable: bool
) -> None:
    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(403, headers=headers, content=b"{}")
            ),
            trust_env=False,
        ) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            with pytest.raises(ReviewError) as caught:
                await source.tree(REV)
            assert caught.value.code is expected_code
            assert caught.value.retryable is retryable
            assert source.budget.usage().github_attempts == 1

    asyncio.run(run())


@pytest.mark.parametrize("response_sha", [None, "3" * 40])
def test_tree_response_must_match_the_pinned_tree_identity(
    response_sha: str | None,
) -> None:
    tree: dict[str, Any] = {"tree": [], "truncated": False}
    if response_sha is not None:
        tree["sha"] = response_sha

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: _response(tree)),
            trust_env=False,
        ) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            with pytest.raises(ReviewError) as caught:
                await source.tree(REV)
            assert caught.value.code is ErrorCode.INVALID_INPUT
            assert source.budget.usage().tree_entries == 0

    asyncio.run(run())


def test_target_and_baseline_refs_resolve_independently() -> None:
    requests: list[httpx.Request] = []
    metadata = {
        "id": 101,
        "owner": {"login": "example"},
        "name": "project",
        "default_branch": "main",
        "private": False,
        "visibility": "public",
    }
    target_commit = {"sha": "1" * 40, "commit": {"tree": {"sha": "2" * 40}}}
    baseline_commit = {"sha": "3" * 40, "commit": {"tree": {"sha": "4" * 40}}}

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/repos/example/project":
            return _response(metadata)
        if request.url.path == "/repos/example/project/commits/main":
            return httpx.Response(200, content=target_commit["sha"].encode("ascii"))
        if request.url.path == "/repos/example/project/commits/release/v1":
            return httpx.Response(200, content=baseline_commit["sha"].encode("ascii"))
        if request.url.path == "/repos/example/project/git/commits/" + target_commit["sha"]:
            return _response({"sha": target_commit["sha"], "tree": target_commit["commit"]["tree"]})
        if request.url.path == "/repos/example/project/git/commits/" + baseline_commit["sha"]:
            return _response(
                {"sha": baseline_commit["sha"], "tree": baseline_commit["commit"]["tree"]}
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle), trust_env=False
        ) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            repository = await source.repository("example", "project")
            target = await source.pin(repository, "main", RevisionSide.TARGET)
            baseline = await source.pin(repository, "release/v1", RevisionSide.BASELINE)

            assert target.commit_sha == "1" * 40
            assert target.tree_sha == "2" * 40
            assert target.side is RevisionSide.TARGET
            assert baseline.commit_sha == "3" * 40
            assert baseline.tree_sha == "4" * 40
            assert baseline.side is RevisionSide.BASELINE
            assert baseline.requested_ref == "release/v1"
            assert target.revision_id != baseline.revision_id

    asyncio.run(run())
    assert len(requests) == 5
    assert b"release%2Fv1" in requests[-2].url.raw_path


def test_missing_baseline_does_not_change_a_successful_target_pin() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/example/project/commits/main":
            return httpx.Response(200, content=b"1" * 40)
        if request.url.path == "/repos/example/project/git/commits/" + "1" * 40:
            return _response({"sha": "1" * 40, "tree": {"sha": "2" * 40}})
        if request.url.path == "/repos/example/project/commits/absent":
            return httpx.Response(404, content=b"{}")
        raise AssertionError(f"Unexpected request: {request.url}")

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle), trust_env=False
        ) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            repository = Repository(101, "example", "project", "main")
            target = await source.pin(repository, None, RevisionSide.TARGET)

            with pytest.raises(ReviewError) as caught:
                await source.pin(repository, "absent", RevisionSide.BASELINE)

            assert caught.value.code is ErrorCode.REF_NOT_FOUND
            assert target.commit_sha == "1" * 40
            assert target.side is RevisionSide.TARGET

    asyncio.run(run())


def test_pin_reads_commit_identity_without_the_patch_payload() -> None:
    patch = b'{"files":' + (b"x" * (300 * 1024)) + b"}"
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/repos/example/project/commits/main":
            if request.headers.get("Accept") == "application/vnd.github.sha":
                return httpx.Response(200, content=b"1" * 40)
            return httpx.Response(200, content=patch)
        if request.url.path == "/repos/example/project/git/commits/" + "1" * 40:
            return _response({"sha": "1" * 40, "tree": {"sha": "2" * 40}})
        raise AssertionError(f"Unexpected request: {request.url}")

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle), trust_env=False
        ) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            repository = Repository(101, "example", "project", "main")
            pinned = await source.pin(repository, None, RevisionSide.TARGET)

            assert pinned.commit_sha == "1" * 40
            assert pinned.tree_sha == "2" * 40

    asyncio.run(run())
    assert len(requests) == 2
    assert len(patch) > Settings().max_envelope_bytes


def test_pin_rejects_an_oversized_sha_response_before_the_commit_object() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=b"a" * 128)

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle), trust_env=False
        ) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            repository = Repository(101, "example", "project", "main")
            with pytest.raises(ReviewError) as caught:
                await source.pin(repository, "main", RevisionSide.TARGET)
            assert caught.value.code is ErrorCode.SOURCE_LIMIT

    asyncio.run(run())
    assert len(requests) == 1


def test_pin_rejects_a_commit_object_that_does_not_match_the_resolved_sha() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, content=b"1" * 40)
        return _response({"sha": "2" * 40, "tree": {"sha": "3" * 40}})

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle), trust_env=False
        ) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            repository = Repository(101, "example", "project", "main")
            with pytest.raises(ReviewError) as caught:
                await source.pin(repository, "main", RevisionSide.TARGET)
            assert caught.value.code is ErrorCode.INVALID_INPUT

    asyncio.run(run())


def test_immutable_blob_cache_reuses_verified_bytes_across_revisions() -> None:
    raw = b"shared immutable source\n"
    sha = _blob_sha(raw)
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _response(
            {
                "sha": sha,
                "encoding": "base64",
                "size": len(raw),
                "content": base64.b64encode(raw).decode(),
            }
        )

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle), trust_env=False
        ) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            baseline = REV.model_copy(
                update={
                    "revision_id": "rev_baseline_bbbbbbbbbbbbbbbb",
                    "side": RevisionSide.BASELINE,
                    "commit_sha": "3" * 40,
                }
            )
            first = await source.blob(REV, sha)
            second = await source.blob(baseline, sha)
            repeated_target = await source.blob(REV, sha)

            assert first.content is second.content is repeated_target.content
            # A new revision is verified independently; repeats within one revision use cache.
            assert source.budget.usage().github_attempts == 2
            assert source.budget.usage().distinct_blobs == 1
            assert source.budget.usage().source_bytes == len(raw)

    asyncio.run(run())
    assert len(requests) == 2


def test_blob_rejects_unissued_object_syntax_before_networking() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _response({})

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle), trust_env=False
        ) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            with pytest.raises(ReviewError) as caught:
                await source.blob(REV, "../../main")
            assert caught.value.code is ErrorCode.INVALID_INPUT
            assert source.budget.usage().github_attempts == 0

    asyncio.run(run())
    assert requests == []


@pytest.mark.parametrize("mismatch", ["returned_sha", "content_digest"])
def test_blob_rejects_object_identity_and_content_hash_mismatch(mismatch: str) -> None:
    expected_raw = b"a"
    expected_sha = _blob_sha(expected_raw)
    response_raw = b"b" if mismatch == "content_digest" else expected_raw
    response_sha = "2" * 40 if mismatch == "returned_sha" else expected_sha
    response = _response(
        {
            "sha": response_sha,
            "encoding": "base64",
            "size": len(response_raw),
            "content": base64.b64encode(response_raw).decode(),
        }
    )

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: response),
            trust_env=False,
        ) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            with pytest.raises(ReviewError) as caught:
                await source.blob(REV, expected_sha)
            assert caught.value.code is ErrorCode.INVALID_INPUT
            assert source.budget.usage().source_bytes == 0

    asyncio.run(run())
