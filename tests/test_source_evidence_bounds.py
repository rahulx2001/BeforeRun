from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import ValidationError

from beforerun.features.budgets import Budget, ReviewError
from beforerun.features.contracts import (
    EncodingStatus,
    ErrorCode,
    EvidenceKind,
    FetchStatus,
    PinnedRevision,
    RevisionSide,
)
from beforerun.features.evidence import EvidenceLedger, redact
from beforerun.features.github_source import Blob, GitHubSource
from beforerun.features.settings import Settings
from beforerun.features.snapshot import Snapshot


def _revision(side: RevisionSide) -> PinnedRevision:
    suffix = "a" if side is RevisionSide.TARGET else "b"
    return PinnedRevision(
        revision_id=f"rev_{side.value}_{suffix * 16}",
        repository_id=1,
        canonical_owner="example",
        canonical_name="inert-fixture",
        requested_ref=side.value,
        commit_sha=suffix * 40,
        tree_sha=suffix * 40,
        resolution_timestamp=datetime.now(UTC),
        side=side,
    )


def _object_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def _tree_bytes(paths: list[str], tree_sha: str) -> bytes:
    return json.dumps(
        {
            "sha": tree_sha,
            "tree": [
                {
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": _object_sha(path.encode()),
                }
                for path in paths
            ],
            "truncated": False,
        }
    ).encode()


def _mock_client(bodies: list[bytes]) -> httpx.AsyncClient:
    responses = iter(
        httpx.Response(200, content=body, headers={"Content-Type": "application/json"})
        for body in bodies
    )

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.scheme == "https"
        assert request.url.host == "api.github.com"
        return next(responses)

    return httpx.AsyncClient(transport=httpx.MockTransport(handle), trust_env=False)


def test_tree_entry_cap_is_shared_by_target_and_baseline() -> None:
    async def run() -> None:
        bodies = [
            _tree_bytes(["target-a", "target-b"], _revision(RevisionSide.TARGET).tree_sha),
            _tree_bytes(["base-a", "base-b"], _revision(RevisionSide.BASELINE).tree_sha),
        ]
        async with _mock_client(bodies) as client:
            settings = Settings(max_tree_entries=3)
            source = GitHubSource(settings, Budget(settings), client=client)
            target, target_truncated = await source.tree(_revision(RevisionSide.TARGET))
            baseline, baseline_truncated = await source.tree(_revision(RevisionSide.BASELINE))

            assert len(target) == 2
            assert target_truncated is False
            assert len(baseline) == 1
            assert baseline_truncated is True
            assert source.budget.usage().tree_entries == 3

    asyncio.run(run())


def test_tree_streamed_byte_cap_is_shared_across_revisions() -> None:
    async def run() -> None:
        first = _tree_bytes(["a"], _revision(RevisionSide.TARGET).tree_sha)
        second = _tree_bytes(["b"], _revision(RevisionSide.BASELINE).tree_sha)
        assert len(first) == len(second)
        async with _mock_client([first, second]) as client:
            settings = Settings(max_tree_envelope_bytes=len(first) + len(second) - 1)
            source = GitHubSource(settings, Budget(settings), client=client)
            await source.tree(_revision(RevisionSide.TARGET))
            assert source.budget.usage().tree_envelope_bytes == len(first)

            with pytest.raises(ReviewError) as caught:
                await source.tree(_revision(RevisionSide.BASELINE))
            assert caught.value.code is ErrorCode.SOURCE_LIMIT
            assert source.budget.usage().tree_envelope_bytes == len(first)

    asyncio.run(run())


def test_streamed_body_limit_does_not_trust_content_length() -> None:
    async def run() -> None:
        body = _tree_bytes(["a"], _revision(RevisionSide.TARGET).tree_sha)
        response = httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "application/json", "Content-Length": "1"},
        )

        def handle(request: httpx.Request) -> httpx.Response:
            return response

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle), trust_env=False
        ) as client:
            settings = Settings(max_tree_envelope_bytes=len(body) - 1)
            source = GitHubSource(settings, Budget(settings), client=client)
            with pytest.raises(ReviewError) as caught:
                await source.tree(_revision(RevisionSide.TARGET))
            assert caught.value.code is ErrorCode.SOURCE_LIMIT

    asyncio.run(run())


def test_blob_accepts_bounded_github_base64_wrapping() -> None:
    async def run() -> None:
        raw = bytes(range(32, 127)) * 1000
        encoded = base64.b64encode(raw).decode("ascii")
        wrapped = "\r\n".join(encoded[index : index + 60] for index in range(0, len(encoded), 60))
        body = json.dumps(
            {
                "sha": _object_sha(raw),
                "encoding": "base64",
                "size": len(raw),
                "content": wrapped + "\r\n",
            }
        ).encode()
        async with _mock_client([body]) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            blob = await source.blob(_revision(RevisionSide.TARGET), _object_sha(raw))

            assert blob.content == raw
            assert source.budget.usage().source_bytes == len(raw)

    asyncio.run(run())


@pytest.mark.parametrize(
    ("overrides", "expected_code"),
    [
        ({"size": -1, "content": ""}, ErrorCode.INVALID_INPUT),
        ({"size": True, "content": ""}, ErrorCode.INVALID_INPUT),
        ({"size": "1", "content": "YQ=="}, ErrorCode.INVALID_INPUT),
        ({"size": 1, "content": None}, ErrorCode.INVALID_INPUT),
        ({"size": 1, "content": "YQ==="}, ErrorCode.INVALID_INPUT),
        ({"size": 1, "content": "!!!!"}, ErrorCode.INVALID_INPUT),
        ({"size": 1, "content": "YQ==é"}, ErrorCode.INVALID_INPUT),
        ({"size": 1, "content": "YQ==" + chr(0xD800)}, ErrorCode.INVALID_INPUT),
        ({"size": 1, "content": "\n" * 20}, ErrorCode.SOURCE_LIMIT),
        ({"size": 2, "content": "YQ=="}, ErrorCode.INVALID_INPUT),
    ],
)
def test_blob_rejects_invalid_declared_size_or_encoded_content(
    overrides: dict[str, object], expected_code: ErrorCode
) -> None:
    async def run() -> None:
        raw = b"a"
        body = json.dumps(
            {
                "sha": _object_sha(raw),
                "encoding": "base64",
                "size": len(raw),
                "content": base64.b64encode(raw).decode(),
                **overrides,
            }
        ).encode()
        async with _mock_client([body]) as client:
            settings = Settings()
            source = GitHubSource(settings, Budget(settings), client=client)
            with pytest.raises(ReviewError) as caught:
                await source.blob(_revision(RevisionSide.TARGET), _object_sha(raw))
            assert caught.value.code is expected_code
            assert source.budget.usage().source_bytes == 0

    asyncio.run(run())


def test_blob_rejects_oversized_declaration_before_decoding() -> None:
    async def run() -> None:
        raw = b"a"
        body = json.dumps(
            {
                "sha": _object_sha(raw),
                "encoding": "base64",
                "size": 9,
                "content": "not base64",
            }
        ).encode()
        async with _mock_client([body]) as client:
            settings = Settings(max_file_bytes=8, max_envelope_bytes=1024)
            source = GitHubSource(settings, Budget(settings), client=client)
            with pytest.raises(ReviewError) as caught:
                await source.blob(_revision(RevisionSide.TARGET), _object_sha(raw))
            assert caught.value.code is ErrorCode.SOURCE_LIMIT

    asyncio.run(run())


class _FixtureSource:
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def blob(self, revision: PinnedRevision, expected_sha: str) -> Blob:
        return Blob(blob_id=expected_sha, content=self.content)


def test_redaction_does_not_shift_next_original_byte_offset() -> None:
    raw = b"token=supersecretvalue " + b"x" * (12 * 1024)
    sha = _object_sha(raw)
    snapshot = Snapshot(
        {RevisionSide.TARGET: _revision(RevisionSide.TARGET)},
        _FixtureSource(raw),  # type: ignore[arg-type]
    )
    snapshot.register_tree(
        RevisionSide.TARGET,
        [{"path": "long.js", "mode": "100644", "type": "blob", "sha": sha}],
        False,
    )

    async def admit() -> str:
        file_id = snapshot.file_id(RevisionSide.TARGET, "long.js")
        assert file_id is not None
        record = await snapshot.admit_file(file_id)
        assert record.fetch_status is FetchStatus.FETCHED
        assert record.encoding_status is EncodingStatus.UTF8
        return file_id

    file_id = asyncio.run(admit())
    ledger = EvidenceLedger("review_abcdefghijklmnop", snapshot, Settings())
    first = ledger.issue(file_id, 1, 1)
    assert first.kind is EvidenceKind.REDACTED
    next_chunk_id = json.loads(ledger.bundle([first.evidence_id]))[0]["next_chunk_id"]
    assert next_chunk_id is not None

    second = ledger.issue_chunk(next_chunk_id)
    assert second.span.first_byte_offset == 12 * 1024
    assert second.span.first_column == 12 * 1024 + 1
    assert second.representation.encode() == raw[12 * 1024 :]


def _ledger(raw: bytes, path: str = "source.js") -> tuple[EvidenceLedger, str]:
    sha = _object_sha(raw)
    snapshot = Snapshot(
        {RevisionSide.TARGET: _revision(RevisionSide.TARGET)},
        _FixtureSource(raw),  # type: ignore[arg-type]
    )
    snapshot.register_tree(
        RevisionSide.TARGET,
        [{"path": path, "mode": "100644", "type": "blob", "sha": sha}],
        False,
    )

    async def admit() -> str:
        file_id = snapshot.file_id(RevisionSide.TARGET, path)
        assert file_id is not None
        record = await snapshot.admit_file(file_id)
        assert record.fetch_status is FetchStatus.FETCHED
        assert record.encoding_status is EncodingStatus.UTF8
        return file_id

    return EvidenceLedger("review_abcdefghijklmnop", snapshot, Settings()), asyncio.run(admit())


def test_redact_quoted_secret_values() -> None:
    text = "token = \"quoted-secret-value\" and api_key: 'another-secret'"
    redacted, changed = redact(text)
    assert changed
    assert "quoted-secret-value" not in redacted
    assert "another-secret" not in redacted
    assert redacted.count("[REDACTED]") == 2


def test_fully_represented_redacted_source_has_no_phantom_chunk() -> None:
    ledger, file_id = _ledger(b"token=shortsecret\n")
    evidence = ledger.issue(file_id, 1, 1)
    assert evidence.kind is EvidenceKind.REDACTED
    assert json.loads(ledger.bundle([evidence.evidence_id]))[0]["next_chunk_id"] is None


def test_clipped_unicode_span_advances_to_a_character_boundary() -> None:
    raw = b"a" + "\U0001f600".encode("utf-8") * 4000
    ledger, file_id = _ledger(raw)
    first = ledger.issue(file_id, 1, 1)
    represented = len(first.representation.encode("utf-8"))
    assert represented <= 12 * 1024
    assert represented < len(raw)
    assert first.span.last_byte_offset == represented
    assert first.span.last_column == represented + 1
    next_chunk_id = json.loads(ledger.bundle([first.evidence_id]))[0]["next_chunk_id"]
    assert next_chunk_id is not None
    second = ledger.issue_chunk(next_chunk_id)
    assert second.span.first_byte_offset == represented
    assert second.representation.startswith("\U0001f600")
    assert second.span.last_byte_offset == represented + len(second.representation.encode("utf-8"))


def test_delivery_is_recorded_only_after_receipt_validation() -> None:
    ledger, file_id = _ledger(b"const value = 1;\n")
    evidence = ledger.issue(file_id, 1, 1)
    with pytest.raises(ValidationError):
        ledger.deliver([evidence.evidence_id], 0)
    with pytest.raises(ReviewError) as caught:
        ledger.require_delivered(evidence.evidence_id)
    assert caught.value.code is ErrorCode.INVALID_MODEL_OUTPUT
    receipt = ledger.deliver([evidence.evidence_id], 1)
    assert receipt.items[0].evidence_id == evidence.evidence_id
    assert ledger.require_delivered(evidence.evidence_id) == evidence
