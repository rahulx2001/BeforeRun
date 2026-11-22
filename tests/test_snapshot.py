from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime

import pytest

from beforerun.features.budgets import ReviewError
from beforerun.features.contracts import (
    EncodingStatus,
    ErrorCode,
    FetchStatus,
    GitMode,
    PinnedRevision,
    RevisionSide,
)
from beforerun.features.github_source import Blob
from beforerun.features.snapshot import Snapshot


def _revision(side: RevisionSide = RevisionSide.TARGET) -> PinnedRevision:
    suffix = "a" if side is RevisionSide.TARGET else "b"
    return PinnedRevision(
        revision_id=f"rev_{side.value}_{suffix * 16}",
        repository_id=101,
        canonical_owner="example",
        canonical_name="inert-fixture",
        requested_ref="main",
        commit_sha=suffix * 40,
        tree_sha=suffix * 40,
        resolution_timestamp=datetime.now(UTC),
        side=side,
    )


def _blob_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


class FakeSource:
    def __init__(self, blobs: dict[str, bytes] | None = None) -> None:
        self.blobs = blobs or {}
        self.calls: list[tuple[str, str]] = []

    async def blob(self, revision: PinnedRevision, expected_sha: str) -> Blob:
        self.calls.append((revision.commit_sha, expected_sha))
        try:
            content = self.blobs[expected_sha]
        except KeyError as error:
            raise ReviewError(ErrorCode.REF_NOT_FOUND, "Fixture blob is unavailable.") from error
        return Blob(blob_id=expected_sha, content=content)


def _entry(path: str, raw: bytes | None = None, mode: str = "100644", kind: str = "blob") -> dict:
    sha = _blob_sha(raw if raw is not None else path.encode())
    result = {"path": path, "mode": mode, "type": kind, "sha": sha}
    return result


def test_tree_reregistration_cannot_restore_false_completeness() -> None:
    source = FakeSource()
    snapshot = Snapshot({RevisionSide.TARGET: _revision()}, source)  # type: ignore[arg-type]
    snapshot.register_tree(RevisionSide.TARGET, [], truncated=True)
    snapshot.register_tree(RevisionSide.TARGET, [], truncated=False)
    assert snapshot.inventory_complete[RevisionSide.TARGET] is False

    other = Snapshot({RevisionSide.TARGET: _revision()}, source)  # type: ignore[arg-type]
    other.register_tree(RevisionSide.TARGET, [{"path": "../outside"}], truncated=False)
    other.register_tree(RevisionSide.TARGET, [], truncated=False)
    assert other.inventory_complete[RevisionSide.TARGET] is False
    assert other.errors


@pytest.mark.parametrize(
    ("mode", "kind"),
    [("100644", "commit"), ("160000", "blob"), ("040000", "blob"), ("120000", "tree")],
)
def test_tree_mode_and_object_type_must_agree(mode: str, kind: str) -> None:
    snapshot = Snapshot({RevisionSide.TARGET: _revision()}, FakeSource())  # type: ignore[arg-type]
    snapshot.register_tree(
        RevisionSide.TARGET,
        [_entry("inconsistent", mode=mode, kind=kind)],
        False,
    )

    assert snapshot.entries() == []
    assert snapshot.inventory_complete[RevisionSide.TARGET] is False
    assert snapshot.errors


def test_duplicate_paths_do_not_replace_admitted_object_identity() -> None:
    first_raw = b"first\n"
    first = _entry("package.json", first_raw)
    second = _entry("package.json", b"replacement\n")
    snapshot = Snapshot({RevisionSide.TARGET: _revision()}, FakeSource())  # type: ignore[arg-type]
    snapshot.register_tree(RevisionSide.TARGET, [first], False)
    file_id = snapshot.file_id(RevisionSide.TARGET, "package.json")
    snapshot.register_tree(RevisionSide.TARGET, [second], False)

    assert snapshot.file_id(RevisionSide.TARGET, "package.json") == file_id
    assert snapshot.require_file(file_id or "").record.blob_id == _blob_sha(first_raw)
    assert snapshot.inventory_complete[RevisionSide.TARGET] is False


@pytest.mark.parametrize("path", ["/absolute", "../escape", "a//b", "a/./b", "a/../b", "a\n/b"])
def test_hostile_tree_paths_are_excluded_not_used_as_filesystem_paths(path: str) -> None:
    snapshot = Snapshot({RevisionSide.TARGET: _revision()}, FakeSource())  # type: ignore[arg-type]
    snapshot.register_tree(
        RevisionSide.TARGET,
        [{"path": path, "mode": "100644", "type": "blob", "sha": "a" * 40}],
        False,
    )
    assert snapshot.entries() == []
    assert snapshot.inventory_complete[RevisionSide.TARGET] is False


def test_modes_lfs_and_binary_are_recorded_without_dereference_or_execution() -> None:
    lfs = b"version https://git-lfs.github.com/spec/v1\noid sha256:" + b"a" * 64 + b"\n"
    binary = b"\xff\x00\xfe"
    executable = b"console.log('inert data only');\n"
    blobs = {
        _blob_sha(lfs): lfs,
        _blob_sha(binary): binary,
        _blob_sha(executable): executable,
    }
    source = FakeSource(blobs)
    snapshot = Snapshot({RevisionSide.TARGET: _revision()}, source)  # type: ignore[arg-type]
    symlink = _entry("link", b"../../outside", mode="120000")
    submodule = _entry("vendor/project", mode="160000", kind="commit")
    snapshot.register_tree(
        RevisionSide.TARGET,
        [
            symlink,
            submodule,
            _entry("large.bin", lfs),
            _entry("binary.dat", binary),
            _entry("run.js", executable, mode="100755"),
        ],
        False,
    )

    async def admit(path: str):
        file_id = snapshot.file_id(RevisionSide.TARGET, path)
        assert file_id
        return await snapshot.admit_file(file_id, required=False)

    results = {path: asyncio.run(admit(path)) for path in snapshot.paths[RevisionSide.TARGET]}
    assert results["link"].fetch_status is FetchStatus.SKIPPED
    assert results["vendor/project"].fetch_status is FetchStatus.SKIPPED
    assert results["large.bin"].encoding_status is EncodingStatus.UNSUPPORTED
    assert results["large.bin"].raw_sha256 == hashlib.sha256(lfs).hexdigest()
    assert results["binary.dat"].encoding_status is EncodingStatus.BINARY
    assert results["binary.dat"].raw_sha256 == hashlib.sha256(binary).hexdigest()
    assert results["run.js"].mode is GitMode.EXECUTABLE_BLOB
    assert results["run.js"].fetch_status is FetchStatus.FETCHED
    assert source.calls == [
        (_revision().commit_sha, _blob_sha(lfs)),
        (_revision().commit_sha, _blob_sha(binary)),
        (_revision().commit_sha, _blob_sha(executable)),
    ]


def test_crlf_bom_long_lines_and_empty_files_keep_original_offsets() -> None:
    crlf_bom = b"\xef\xbb\xbffirst\r\nsecond\r\nthird"
    long = b"x" * 20_000
    empty = b""
    source = FakeSource(
        {
            _blob_sha(crlf_bom): crlf_bom,
            _blob_sha(long): long,
            _blob_sha(empty): empty,
        }
    )
    snapshot = Snapshot({RevisionSide.TARGET: _revision()}, source)  # type: ignore[arg-type]
    snapshot.register_tree(
        RevisionSide.TARGET,
        [
            _entry("crlf.txt", crlf_bom),
            _entry("long.js", long),
            _entry("empty.txt", empty),
        ],
        False,
    )

    async def run() -> None:
        crlf_id = snapshot.file_id(RevisionSide.TARGET, "crlf.txt")
        long_id = snapshot.file_id(RevisionSide.TARGET, "long.js")
        empty_id = snapshot.file_id(RevisionSide.TARGET, "empty.txt")
        assert crlf_id and long_id and empty_id
        await snapshot.admit_file(crlf_id)
        await snapshot.admit_file(long_id)
        await snapshot.admit_file(empty_id)

        crlf = snapshot.require_file(crlf_id)
        assert crlf.text == "\ufefffirst\r\nsecond\r\nthird"
        assert [(line.start_byte, line.end_byte) for line in crlf.record.line_map] == [
            (0, 10),
            (10, 18),
            (18, 23),
        ]
        assert crlf.record.raw_sha256 == hashlib.sha256(crlf_bom).hexdigest()
        assert snapshot.require_file(long_id).record.line_map[0].end_byte == 20_000
        empty_record = snapshot.require_file(empty_id).record
        assert empty_record.fetch_status is FetchStatus.FETCHED
        assert [(line.line, line.start_byte, line.end_byte) for line in empty_record.line_map] == [
            (1, 0, 0)
        ]

    asyncio.run(run())


def test_shared_blob_reuses_bytes_text_and_line_maps_with_distinct_path_bindings() -> None:
    raw = b"shared source\n"
    first_entry = _entry("first.js", raw)
    second_entry = {**first_entry, "path": "second.js"}
    source = FakeSource({_blob_sha(raw): raw})
    snapshot = Snapshot({RevisionSide.TARGET: _revision()}, source)  # type: ignore[arg-type]
    snapshot.register_tree(RevisionSide.TARGET, [first_entry, second_entry], False)

    async def run() -> None:
        first_id = snapshot.file_id(RevisionSide.TARGET, "first.js")
        second_id = snapshot.file_id(RevisionSide.TARGET, "second.js")
        assert first_id and second_id and first_id != second_id
        await snapshot.admit_file(first_id)
        await snapshot.admit_file(second_id)

        first = snapshot.require_file(first_id)
        second = snapshot.require_file(second_id)
        assert first.record.path == "first.js"
        assert second.record.path == "second.js"
        assert first.record.revision_id == second.record.revision_id
        assert first.content is second.content
        assert first.text is second.text
        assert first.record.line_map is second.record.line_map

    asyncio.run(run())
    assert len(source.calls) == 2


def test_cross_review_file_ids_are_not_interchangeable() -> None:
    raw = b"same immutable bytes\n"
    entry = _entry("same.js", raw)
    first = Snapshot({RevisionSide.TARGET: _revision()}, FakeSource())  # type: ignore[arg-type]
    second = Snapshot({RevisionSide.BASELINE: _revision(RevisionSide.BASELINE)}, FakeSource())  # type: ignore[arg-type]
    first.register_tree(RevisionSide.TARGET, [entry], False)
    second.register_tree(RevisionSide.BASELINE, [entry], False)
    first_id = first.file_id(RevisionSide.TARGET, "same.js")
    second_id = second.file_id(RevisionSide.BASELINE, "same.js")
    assert first_id and second_id and first_id != second_id
    with pytest.raises(ReviewError) as caught:
        second.require_file(first_id)
    assert caught.value.code is ErrorCode.INVALID_TOOL_ARGUMENTS
