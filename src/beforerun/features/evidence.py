"""Issued excerpts, exact delivery receipts, redaction, and pinned source links."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from beforerun.features.budgets import ReviewError
from beforerun.features.contracts import (
    DecodeOperation,
    DeliveredEvidence,
    DeliveryReceipt,
    EncodingStatus,
    ErrorCode,
    Evidence,
    EvidenceKind,
    EvidenceQuote,
    FetchStatus,
    RevisionSide,
    SourceSpan,
)
from beforerun.features.github_source import source_url
from beforerun.features.settings import Settings
from beforerun.features.snapshot import Snapshot, StoredSource, issued_id

_SECRET = re.compile(
    r"(?i)("
    r"authorization\s*[:=]\s*(?:bearer\s+)?|"
    r"api[_-]?key\s*[:=]\s*|"
    r"secret\s*[:=]\s*|"
    r"token\s*[:=]\s*"
    r")(?:([\"'])([^\n]{1,}?)\2|([^\s,;\"'}]{4,}))"
)


def redact(text: str) -> tuple[str, bool]:
    def replacement(match: re.Match[str]) -> str:
        quote = match.group(2) or ""
        return f"{match.group(1)}{quote}[REDACTED]{quote}"

    redacted = _SECRET.sub(replacement, text)
    return redacted, redacted != text


def _digest(value: bytes | str) -> str:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clip_utf8(text: str, limit: int) -> tuple[str, int]:
    raw = text.encode("utf-8")[:limit]
    clipped = raw.decode("utf-8", errors="ignore")
    return clipped, len(clipped.encode("utf-8"))


class EvidenceLedger:
    def __init__(self, review_id: str, snapshot: Snapshot, settings: Settings) -> None:
        self.review_id = review_id
        self.snapshot = snapshot
        self.settings = settings
        self.evidence: dict[str, Evidence] = {}
        self.receipts: list[DeliveryReceipt] = []
        self.delivered: dict[str, str] = {}
        self.chunks: dict[str, tuple[str, int, int]] = {}
        self.truncated: dict[str, bool] = {}
        self._next_chunk_for: dict[str, str] = {}

    def issue(
        self,
        file_id: str,
        first_line: int = 1,
        last_line: int | None = None,
        *,
        byte_offset_in_line: int = 0,
    ) -> Evidence:
        if (
            isinstance(first_line, bool)
            or not isinstance(first_line, int)
            or isinstance(last_line, bool)
            or last_line is not None
            and not isinstance(last_line, int)
            or isinstance(byte_offset_in_line, bool)
            or not isinstance(byte_offset_in_line, int)
            or byte_offset_in_line < 0
        ):
            raise ReviewError(
                ErrorCode.INVALID_TOOL_ARGUMENTS,
                "Source lines and byte offsets must be nonnegative integers.",
            )
        stored = self.snapshot.require_file(file_id)
        record = stored.record
        if (
            record.fetch_status is not FetchStatus.FETCHED
            or record.encoding_status is not EncodingStatus.UTF8
            or stored.text is None
            or stored.content is None
        ):
            raise ReviewError(
                ErrorCode.INVALID_TOOL_ARGUMENTS,
                "The file has no readable exact source text.",
            )
        lines = stored.text.splitlines()
        if not lines:
            lines = [""]
        last_line = last_line if last_line is not None else min(len(lines), first_line + 159)
        if first_line < 1 or last_line < first_line or last_line > len(lines):
            raise ReviewError(
                ErrorCode.INVALID_TOOL_ARGUMENTS,
                "The requested original source range is invalid.",
            )
        if last_line - first_line + 1 > 160:
            raise ReviewError(
                ErrorCode.INVALID_TOOL_ARGUMENTS,
                "An excerpt cannot exceed 160 original lines.",
            )
        if first_line != last_line and byte_offset_in_line:
            raise ReviewError(
                ErrorCode.INVALID_TOOL_ARGUMENTS,
                "A minified chunk must name one original line.",
            )
        if len(record.line_map) < len(lines):
            raise ReviewError(
                ErrorCode.INVALID_TOOL_ARGUMENTS,
                "The file's original line map is incomplete.",
            )
        source = "\n".join(lines[first_line - 1 : last_line])
        if byte_offset_in_line:
            raw_line = lines[first_line - 1].encode("utf-8")
            if byte_offset_in_line >= len(raw_line):
                raise ReviewError(
                    ErrorCode.INVALID_TOOL_ARGUMENTS,
                    "The chunk offset is outside the source line.",
                )
            try:
                raw_line[:byte_offset_in_line].decode("utf-8", errors="strict")
            except UnicodeDecodeError as error:
                raise ReviewError(
                    ErrorCode.INVALID_TOOL_ARGUMENTS,
                    "The chunk offset splits a UTF-8 character.",
                ) from error
            source = raw_line[byte_offset_in_line:].decode("utf-8", errors="strict")
        representation, consumed = _clip_utf8(source, 12 * 1024)
        shown_lines = representation.split("\n")
        actual_last = first_line + len(shown_lines) - 1
        first_column = byte_offset_in_line + 1
        first_byte_offset = record.line_map[first_line - 1].start_byte + byte_offset_in_line
        clipped = consumed < len(source.encode("utf-8"))
        if clipped:
            if len(shown_lines) == 1:
                last_byte_offset = first_byte_offset + consumed
            else:
                last_byte_offset = record.line_map[actual_last - 1].start_byte + len(
                    shown_lines[-1].encode("utf-8")
                )
        else:
            last_byte_offset = record.line_map[actual_last - 1].end_byte
        last_column = (
            first_column + consumed
            if len(shown_lines) == 1
            else len(shown_lines[-1].encode("utf-8")) + 1
        )
        representation, was_redacted = redact(representation)
        revision = self.snapshot.revision_for(stored)
        evidence = Evidence(
            evidence_id=issued_id("ev"),
            file_id=file_id,
            revision_id=revision.revision_id,
            side=revision.side,
            span=SourceSpan(
                first_line=first_line,
                first_column=first_column,
                last_line=actual_last,
                last_column=last_column,
                first_byte_offset=first_byte_offset,
                last_byte_offset=last_byte_offset,
            ),
            representation=representation,
            raw_sha256=record.raw_sha256 or _digest(stored.content),
            representation_sha256=_digest(representation),
            kind=EvidenceKind.REDACTED if was_redacted else EvidenceKind.SOURCE,
        )
        self.evidence[evidence.evidence_id] = evidence
        self.truncated[evidence.evidence_id] = clipped
        if clipped and len(shown_lines) == 1:
            # Redaction changes display bytes, not the next original-source offset.
            next_offset = byte_offset_in_line + consumed
            chunk_id = issued_id("chunk")
            self.chunks[chunk_id] = (file_id, first_line, next_offset)
            # Chunk IDs are exposed as tool metadata, never as virtual source lines.
            self._next_chunk_for[evidence.evidence_id] = chunk_id
        return evidence

    def issue_chunk(self, chunk_id: str) -> Evidence:
        chunk = self.chunks.get(chunk_id)
        if chunk is None:
            raise ReviewError(ErrorCode.INVALID_TOOL_ARGUMENTS, "Unknown or cross-review chunk ID.")
        file_id, line, offset = chunk
        return self.issue(file_id, line, line, byte_offset_in_line=offset)

    def issue_derived(
        self,
        parent_id: str,
        representation: str,
        kind: EvidenceKind,
        operations: tuple[DecodeOperation, ...] = (),
        *,
        counterpart_id: str | None = None,
    ) -> Evidence:
        parent = self.require(parent_id)
        if kind not in {EvidenceKind.DECODED, EvidenceKind.STRING, EvidenceKind.DIFF}:
            raise ReviewError(
                ErrorCode.INVALID_TOOL_ARGUMENTS,
                "Derived evidence requires a decoded, string, or diff kind.",
            )
        counterpart = self.require(counterpart_id) if counterpart_id is not None else None
        if kind is EvidenceKind.DIFF:
            literal_kinds = {EvidenceKind.SOURCE, EvidenceKind.REDACTED}
            if (
                counterpart is None
                or parent.kind not in literal_kinds
                or counterpart.kind not in literal_kinds
                or counterpart.side is parent.side
                or counterpart.revision_id == parent.revision_id
            ):
                raise ReviewError(
                    ErrorCode.INVALID_TOOL_ARGUMENTS,
                    "Diff evidence requires literal source on distinct target/baseline sides.",
                )
            parent_path = self.snapshot.require_file(parent.file_id).record.path
            counterpart_path = self.snapshot.require_file(counterpart.file_id).record.path
            if parent_path != counterpart_path:
                raise ReviewError(
                    ErrorCode.INVALID_TOOL_ARGUMENTS,
                    "Diff evidence requires counterparts for the same admitted path.",
                )
        elif counterpart is not None:
            raise ReviewError(
                ErrorCode.INVALID_TOOL_ARGUMENTS,
                "Only diff evidence can have a counterpart source.",
            )
        clipped = len(representation.encode("utf-8")) > 12 * 1024
        representation, _ = _clip_utf8(representation, 12 * 1024)
        representation, _ = redact(representation)
        evidence = Evidence(
            evidence_id=issued_id("ev"),
            file_id=parent.file_id,
            revision_id=parent.revision_id,
            side=parent.side,
            span=parent.span,
            representation=representation,
            raw_sha256=parent.raw_sha256,
            representation_sha256=_digest(representation),
            kind=kind,
            parent_evidence_id=parent_id,
            counterpart_evidence_id=counterpart_id,
            decoding_operations=operations,
        )
        self.evidence[evidence.evidence_id] = evidence
        self.truncated[evidence.evidence_id] = clipped
        return evidence

    def require(self, evidence_id: str) -> Evidence:
        evidence = self.evidence.get(evidence_id)
        if evidence is None:
            raise ReviewError(
                ErrorCode.INVALID_TOOL_ARGUMENTS, "Unknown or cross-review evidence ID."
            )
        return evidence

    def require_delivered(self, evidence_id: str) -> Evidence:
        evidence = self.require(evidence_id)
        expected = self.delivered.get(evidence_id)
        if expected != evidence.representation_sha256:
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT,
                "A finding cited source that was fetched or listed but never delivered "
                "to the analyst.",
            )
        return evidence

    def deliver(
        self, evidence_ids: list[str], turn: int, tool_call_id: str | None = None
    ) -> DeliveryReceipt:
        unique = list(dict.fromkeys(evidence_ids))
        if not unique:
            raise ValueError("a delivery requires evidence")
        items = []
        for evidence_id in unique:
            evidence = self.require(evidence_id)
            items.append(
                DeliveredEvidence(
                    evidence_id=evidence_id,
                    representation=evidence.representation,
                    representation_sha256=evidence.representation_sha256,
                )
            )
        receipt = DeliveryReceipt(
            receipt_id=issued_id("rcpt"),
            review_id=self.review_id,
            turn=turn,
            delivered_at=datetime.now(UTC),
            model_route=self.settings.model_route,
            tool_call_id=tool_call_id,
            items=tuple(items),
        )
        for item in receipt.items:
            self.delivered[item.evidence_id] = item.representation_sha256
        self.receipts.append(receipt)
        return receipt

    def validate_quote(self, quote: EvidenceQuote) -> Evidence:
        """Check a model quote against delivered text and real, issued source boundaries."""

        evidence = self.require_delivered(quote.evidence_id)
        if quote.exact_quote not in evidence.representation:
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT,
                "The exact quote does not match the delivered evidence representation.",
            )
        first = quote.first_original_line
        last = quote.last_original_line
        if first is None or last is None:
            return evidence
        if first < evidence.span.first_line or last > evidence.span.last_line or first > last:
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT,
                "The quoted original-line range is outside the issued evidence span.",
            )
        if evidence.kind not in {EvidenceKind.SOURCE, EvidenceKind.REDACTED}:
            if (first, last) != (evidence.span.first_line, evidence.span.last_line):
                raise ReviewError(
                    ErrorCode.INVALID_MODEL_OUTPUT,
                    "Derived output rows cannot refine original GitHub source lines.",
                )
            return evidence
        lines = evidence.representation.split("\n")
        start = first - evidence.span.first_line
        stop = last - evidence.span.first_line + 1
        if stop > len(lines) or quote.exact_quote not in "\n".join(lines[start:stop]):
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT,
                "The exact quote is outside its declared original-line range.",
            )
        return evidence

    def bundle(self, evidence_ids: list[str]) -> str:
        """Structured untrusted user content, not a privileged repository instruction."""

        values = []
        for evidence_id in evidence_ids:
            evidence = self.require(evidence_id)
            stored = self.snapshot.require_file(evidence.file_id)
            values.append(
                {
                    "evidence_id": evidence_id,
                    "file_id": evidence.file_id,
                    "side": evidence.side.value,
                    "path": stored.record.path,
                    "kind": evidence.kind.value,
                    "span": evidence.span.model_dump(mode="json"),
                    "source_url": self.link(evidence_id),
                    "parent_evidence_id": evidence.parent_evidence_id,
                    "counterpart_evidence_id": evidence.counterpart_evidence_id,
                    "counterpart_source_url": (
                        self.link(evidence.counterpart_evidence_id)
                        if evidence.counterpart_evidence_id is not None
                        else None
                    ),
                    "decoding_operations": [
                        operation.value for operation in evidence.decoding_operations
                    ],
                    "raw_sha256": evidence.raw_sha256,
                    "representation_sha256": evidence.representation_sha256,
                    "representation": evidence.representation,
                    "truncated": self.truncated[evidence_id],
                    "next_chunk_id": self._next_chunk_for.get(evidence_id),
                }
            )
        return json.dumps(values, ensure_ascii=False)

    def link(self, evidence_id: str) -> str:
        evidence = self.require(evidence_id)
        stored = self.snapshot.require_file(evidence.file_id)
        revision = self.snapshot.revision_for(stored)
        return source_url(
            revision,
            stored.record.path,
            evidence.span.first_line,
            evidence.span.last_line,
        )

    def model_shown_files(self) -> int:
        file_ids = set()
        for evidence_id in self.delivered:
            file_ids.add(self.evidence[evidence_id].file_id)
        return len(file_ids)

    def readable_files(self, side: RevisionSide | None = None) -> list[StoredSource]:
        values = []
        for stored in self.snapshot.selected_records():
            if stored.record.fetch_status is not FetchStatus.FETCHED:
                continue
            if side is not None and self.snapshot.side_for(stored) is not side:
                continue
            values.append(stored)
        return values
