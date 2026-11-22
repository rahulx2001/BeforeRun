"""Per-review immutable object bindings; no target path becomes a local filesystem path."""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from typing import Any

from beforerun.features.budgets import ReviewError
from beforerun.features.contracts import (
    EncodingStatus,
    ErrorCode,
    FetchStatus,
    GitMode,
    GitObjectType,
    PinnedRevision,
    RevisionSide,
    SourceFile,
    SourceLine,
)
from beforerun.features.github_source import GitHubSource


def issued_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(18)}"


@dataclass(slots=True)
class StoredSource:
    record: SourceFile
    content: bytes | None = None
    text: str | None = None


@dataclass(frozen=True, slots=True)
class _DecodedSource:
    content: bytes
    text: str | None
    raw_byte_length: int
    raw_sha256: str
    line_map: tuple[SourceLine, ...]
    fetch_status: FetchStatus
    encoding_status: EncodingStatus
    skip_reason: str | None

    def record_update(self) -> dict[str, Any]:
        return {
            "raw_byte_length": self.raw_byte_length,
            "raw_sha256": self.raw_sha256,
            "line_map": self.line_map,
            "fetch_status": self.fetch_status,
            "encoding_status": self.encoding_status,
            "skip_reason": self.skip_reason,
        }


_MODE_OBJECT_TYPE = {
    GitMode.BLOB: GitObjectType.BLOB,
    GitMode.EXECUTABLE_BLOB: GitObjectType.BLOB,
    GitMode.TREE: GitObjectType.TREE,
    GitMode.SYMLINK: GitObjectType.BLOB,
    GitMode.SUBMODULE: GitObjectType.COMMIT,
}


class Snapshot:
    """All mappings are owned by one review and one set of pinned revisions."""

    def __init__(self, revisions: dict[RevisionSide, PinnedRevision], source: GitHubSource) -> None:
        self.revisions = revisions
        self.source = source
        self.files_by_id: dict[str, StoredSource] = {}
        self.paths: dict[RevisionSide, dict[str, str]] = {side: {} for side in revisions}
        self.inventory_complete: dict[RevisionSide, bool] = {side: True for side in revisions}
        self.errors: dict[str, str] = {}
        self._decoded_blobs: dict[tuple[int, str], _DecodedSource] = {}

    def register_tree(
        self,
        side: RevisionSide,
        entries: list[dict[str, Any]],
        truncated: bool,
    ) -> None:
        revision = self.revisions[side]
        self.inventory_complete[side] = self.inventory_complete[side] and not truncated
        for entry in entries:
            try:
                path = entry["path"]
                mode = GitMode(entry["mode"])
                object_type = GitObjectType(entry["type"])
                if _MODE_OBJECT_TYPE[mode] is not object_type:
                    raise ValueError("tree mode and object type disagree")
                if not isinstance(path, str):
                    raise ValueError("path must be text")
                blob_id = entry.get("sha") if object_type is not GitObjectType.TREE else None
                if blob_id is not None and not re.fullmatch(r"[0-9a-f]{40}", blob_id):
                    raise ValueError("invalid object SHA")
                record = SourceFile(
                    file_id=issued_id("file"),
                    revision_id=revision.revision_id,
                    path=path,
                    mode=mode,
                    object_type=object_type,
                    blob_id=blob_id,
                )
            except (KeyError, TypeError, ValueError):
                self.inventory_complete[side] = False
                self.errors[f"{side.value}:invalid-entry"] = "An invalid tree entry was excluded."
                continue
            # Provider duplicates cannot silently replace object identity.
            if path in self.paths[side]:
                self.inventory_complete[side] = False
                self.errors[f"{side.value}:duplicate:{path}"] = (
                    "A duplicate tree path was excluded."
                )
                continue
            self.paths[side][path] = record.file_id
            self.files_by_id[record.file_id] = StoredSource(record=record)

    def file_id(self, side: RevisionSide, path: str) -> str | None:
        return self.paths.get(side, {}).get(path)

    def require_file(self, file_id: str) -> StoredSource:
        stored = self.files_by_id.get(file_id)
        if stored is None:
            raise ReviewError(ErrorCode.INVALID_TOOL_ARGUMENTS, "Unknown or cross-review file ID.")
        return stored

    def revision_for(self, stored: StoredSource) -> PinnedRevision:
        for revision in self.revisions.values():
            if revision.revision_id == stored.record.revision_id:
                return revision
        raise ReviewError(
            ErrorCode.INVALID_TOOL_ARGUMENTS,
            "The file has no admitted pinned revision.",
        )

    def side_for(self, stored: StoredSource) -> RevisionSide:
        return self.revision_for(stored).side

    def selected_records(self) -> list[StoredSource]:
        return [stored for stored in self.files_by_id.values() if stored.record.selected]

    def _apply_decoded(
        self,
        stored: StoredSource,
        record: SourceFile,
        decoded: _DecodedSource,
        *,
        required: bool,
    ) -> SourceFile:
        stored.content = decoded.content
        stored.text = decoded.text
        stored.record = record.model_copy(update=decoded.record_update())
        if required and decoded.fetch_status is FetchStatus.SKIPPED:
            self.errors[record.file_id] = decoded.skip_reason or "A required source file is unread."
        return stored.record

    async def admit_path(
        self, side: RevisionSide, path: str, *, required: bool = True
    ) -> SourceFile:
        file_id = self.file_id(side, path)
        if file_id is None:
            raise ReviewError(ErrorCode.REF_NOT_FOUND, f"The selected path is absent: {path}")
        return await self.admit_file(file_id, required=required)

    async def admit_file(self, file_id: str, *, required: bool = True) -> SourceFile:
        stored = self.require_file(file_id)
        record = stored.record
        if record.selected and record.fetch_status is not FetchStatus.PENDING:
            if required and record.fetch_status is FetchStatus.SKIPPED:
                self.errors[file_id] = record.skip_reason or "A required source file is unread."
            return record
        record = record.model_copy(update={"selected": True})
        stored.record = record
        if record.mode not in {GitMode.BLOB, GitMode.EXECUTABLE_BLOB} or record.blob_id is None:
            reason = "Symlink, submodule, or non-blob content is recorded but never dereferenced."
            stored.record = record.model_copy(
                update={
                    "fetch_status": FetchStatus.SKIPPED,
                    "encoding_status": EncodingStatus.UNSUPPORTED,
                    "skip_reason": reason,
                }
            )
            if required:
                self.errors[file_id] = reason
            return stored.record
        revision = self.revision_for(stored)
        cache_key = (revision.repository_id, record.blob_id)
        try:
            blob = await self.source.blob(revision, record.blob_id)
            cached = self._decoded_blobs.get(cache_key)
            if cached is not None:
                if cached.content != blob.content:
                    raise ReviewError(
                        ErrorCode.INVALID_INPUT,
                        "The same issued Git object returned different immutable bytes.",
                    )
                return self._apply_decoded(stored, record, cached, required=required)
            raw = blob.content
            digest = hashlib.sha256(raw).hexdigest()
            stored.content = raw
            raw_identity = {
                "raw_byte_length": len(raw),
                "raw_sha256": digest,
            }
            if b"\0" in raw:
                raise UnicodeError("NUL bytes mark unsupported binary content")
            text = raw.decode("utf-8", errors="strict")
            if text.startswith("version https://git-lfs.github.com/spec/v1"):
                decoded = _DecodedSource(
                    content=raw,
                    text=None,
                    line_map=(),
                    fetch_status=FetchStatus.SKIPPED,
                    encoding_status=EncodingStatus.UNSUPPORTED,
                    skip_reason="Git LFS pointer recorded; external object not retrieved.",
                    **raw_identity,
                )
                self._decoded_blobs[cache_key] = decoded
                return self._apply_decoded(stored, record, decoded, required=required)
            lines: list[SourceLine] = []
            offset = 0
            for number, line in enumerate(raw.splitlines(keepends=True), start=1):
                end = offset + len(line)
                lines.append(SourceLine(line=number, start_byte=offset, end_byte=end))
                offset = end
            if not lines:
                lines = [SourceLine(line=1, start_byte=0, end_byte=0)]
            decoded = _DecodedSource(
                content=raw,
                text=text,
                line_map=tuple(lines),
                fetch_status=FetchStatus.FETCHED,
                encoding_status=EncodingStatus.UTF8,
                skip_reason=None,
                **raw_identity,
            )
            self._decoded_blobs[cache_key] = decoded
            return self._apply_decoded(stored, record, decoded, required=required)
        except UnicodeError:
            reason = "Binary or non-UTF-8 content was not presented as exact source text."
            decoded = _DecodedSource(
                content=raw,
                text=None,
                line_map=(),
                fetch_status=FetchStatus.SKIPPED,
                encoding_status=EncodingStatus.BINARY,
                skip_reason=reason,
                **raw_identity,
            )
            self._decoded_blobs[cache_key] = decoded
            return self._apply_decoded(stored, record, decoded, required=required)
        except ReviewError as error:
            stored.record = record.model_copy(
                update={
                    "fetch_status": FetchStatus.SKIPPED,
                    "encoding_status": (
                        EncodingStatus.OVERSIZED
                        if error.code is ErrorCode.SOURCE_LIMIT
                        else EncodingStatus.UNSUPPORTED
                    ),
                    "skip_reason": error.message,
                }
            )
            if required:
                self.errors[file_id] = error.message
            if required:
                raise
            return stored.record

    def entries(self, *, blobs_only: bool = False) -> list[StoredSource]:
        records = sorted(self.files_by_id.values(), key=lambda item: item.record.path)
        if blobs_only:
            return [item for item in records if item.record.object_type is GitObjectType.BLOB]
        return records
