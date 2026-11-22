from __future__ import annotations

import asyncio
import hashlib
import json

import pytest
from pydantic import ValidationError
from review_helpers import context

from beforerun.features.budgets import ReviewError
from beforerun.features.contracts import (
    DecodeOperation,
    ErrorCode,
    EvidenceKind,
    EvidenceQuote,
    RevisionSide,
)


def _admit(ledger, path: str, side: RevisionSide = RevisionSide.TARGET) -> str:
    file_id = ledger.snapshot.file_id(side, path)
    assert file_id is not None
    asyncio.run(ledger.snapshot.admit_file(file_id))
    return file_id


def test_crlf_bom_quotes_and_links_keep_real_source_coordinates() -> None:
    raw = "\ufeffα\r\nbeta\r\nγ".encode("utf-8")
    snapshot, ledger, _ = context({"source.txt": raw})
    file_id = _admit(ledger, "source.txt")
    evidence = ledger.issue(file_id, 1, 2)

    assert evidence.representation == "\ufeffα\nbeta"
    assert evidence.raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert (
        evidence.representation_sha256
        == hashlib.sha256(evidence.representation.encode()).hexdigest()
    )
    assert evidence.span.first_line == 1
    assert evidence.span.last_line == 2
    assert evidence.span.first_byte_offset == 0
    assert evidence.span.last_byte_offset == raw.index("γ".encode())
    assert evidence.span.last_column == len("beta".encode()) + 1
    assert ledger.link(evidence.evidence_id).endswith("/source.txt#L1-L2")

    quote = EvidenceQuote(
        evidence_id=evidence.evidence_id,
        exact_quote="\ufeffα\nbeta",
        first_original_line=1,
        last_original_line=2,
    )
    with pytest.raises(ReviewError):
        ledger.validate_quote(quote)
    ledger.deliver([evidence.evidence_id], 1)
    assert ledger.validate_quote(quote) == evidence


def test_minified_chunks_never_split_or_invent_utf8_columns() -> None:
    raw = "é🙂".encode() + b"x" * (12 * 1024) + b"tail"
    snapshot, ledger, _ = context({"minified.js": raw})
    file_id = _admit(ledger, "minified.js")

    with pytest.raises(ReviewError) as caught:
        ledger.issue(file_id, 1, 1, byte_offset_in_line=1)
    assert caught.value.code is ErrorCode.INVALID_TOOL_ARGUMENTS

    first = ledger.issue(file_id, 1, 1, byte_offset_in_line=2)
    assert first.representation.startswith("🙂")
    assert first.span.first_byte_offset == 2
    assert first.span.first_column == 3
    assert first.span.last_byte_offset == 2 + len(first.representation.encode())
    chunk_id = json.loads(ledger.bundle([first.evidence_id]))[0]["next_chunk_id"]
    assert chunk_id is not None
    second = ledger.issue_chunk(chunk_id)
    assert second.span.first_byte_offset == 2 + len(first.representation.encode())
    assert second.representation.startswith("x")
    assert second.representation.endswith("tail")


def test_unknown_cross_review_and_fetched_but_undelivered_ids_are_not_citations() -> None:
    first_snapshot, first_ledger, _ = context({"same.js": b"same bytes\n"})
    second_snapshot, second_ledger, _ = context(
        {"same.js": b"same bytes\n"}, review_id="review_abcdefghijklmnop"
    )
    first_id = _admit(first_ledger, "same.js")
    _admit(second_ledger, "same.js")
    evidence = first_ledger.issue(first_id)

    assert first_snapshot is not second_snapshot
    with pytest.raises(ReviewError) as caught:
        first_ledger.require_delivered(evidence.evidence_id)
    assert caught.value.code is ErrorCode.INVALID_MODEL_OUTPUT
    with pytest.raises(ReviewError):
        second_ledger.require(evidence.evidence_id)
    with pytest.raises(ReviewError):
        first_ledger.require("ev_abcdefghijklmnop")

    receipt = first_ledger.deliver([evidence.evidence_id, evidence.evidence_id], 1)
    assert len(receipt.items) == 1
    assert receipt.items[0].representation == evidence.representation
    assert first_ledger.require_delivered(evidence.evidence_id) == evidence


def test_quote_checks_reject_wrong_text_ranges_and_virtual_rows() -> None:
    snapshot, ledger, _ = context({"lines.js": b"first\nsecond\nthird\n"})
    file_id = _admit(ledger, "lines.js")
    evidence = ledger.issue(file_id, 1, 2)
    ledger.deliver([evidence.evidence_id], 1)

    valid = EvidenceQuote(
        evidence_id=evidence.evidence_id,
        exact_quote="first\nsecond",
        first_original_line=1,
        last_original_line=2,
    )
    assert ledger.validate_quote(valid) == evidence
    for quote in (
        EvidenceQuote(
            evidence_id=evidence.evidence_id,
            exact_quote="second",
            first_original_line=1,
            last_original_line=1,
        ),
        EvidenceQuote(
            evidence_id=evidence.evidence_id,
            exact_quote="third",
            first_original_line=3,
            last_original_line=3,
        ),
        EvidenceQuote(evidence_id=evidence.evidence_id, exact_quote="invented"),
    ):
        with pytest.raises(ReviewError) as caught:
            ledger.validate_quote(quote)
        assert caught.value.code is ErrorCode.INVALID_MODEL_OUTPUT


def test_redaction_preserves_raw_identity_but_rejects_unshown_secret_quotes() -> None:
    raw = b"token=supersecretvalue\n"
    snapshot, ledger, _ = context({"secret.txt": raw})
    file_id = _admit(ledger, "secret.txt")
    evidence = ledger.issue(file_id)
    receipt = ledger.deliver([evidence.evidence_id], 1)

    assert evidence.kind is EvidenceKind.REDACTED
    assert evidence.representation == "token=[REDACTED]"
    assert evidence.raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert "supersecretvalue" not in receipt.model_dump_json()
    with pytest.raises(ReviewError):
        ledger.validate_quote(
            EvidenceQuote(evidence_id=evidence.evidence_id, exact_quote=raw.decode().strip())
        )
    marker_quote = EvidenceQuote(
        evidence_id=evidence.evidence_id,
        exact_quote="token=[REDACTED]",
        first_original_line=1,
        last_original_line=1,
    )
    assert ledger.validate_quote(marker_quote) == evidence


def test_derived_evidence_exposes_parent_decoding_and_no_virtual_github_lines() -> None:
    snapshot, ledger, _ = context({"literal.txt": b'"SGVsbG8="\n'})
    file_id = _admit(ledger, "literal.txt")
    parent = ledger.issue(file_id)
    ledger.deliver([parent.evidence_id], 1)
    derived = ledger.issue_derived(
        parent.evidence_id,
        "Hello\nvirtual row 2",
        EvidenceKind.DECODED,
        (DecodeOperation.BASE64,),
    )
    view = json.loads(ledger.bundle([derived.evidence_id]))[0]

    assert derived.parent_evidence_id == parent.evidence_id
    assert derived.span == parent.span
    assert derived.raw_sha256 == parent.raw_sha256
    assert view["parent_evidence_id"] == parent.evidence_id
    assert view["decoding_operations"] == ["base64"]
    assert view["source_url"].endswith("#L1")
    assert "#L2" not in view["source_url"]

    ledger.deliver([derived.evidence_id], 2)
    assert (
        ledger.validate_quote(
            EvidenceQuote(evidence_id=derived.evidence_id, exact_quote="virtual row 2")
        )
        == derived
    )
    with pytest.raises(ReviewError):
        ledger.validate_quote(
            EvidenceQuote(
                evidence_id=derived.evidence_id,
                exact_quote="virtual row 2",
                first_original_line=2,
                last_original_line=2,
            )
        )


def test_diff_requires_distinct_original_side_counterparts() -> None:
    snapshot, ledger, _ = context({"change.js": b"target\n"}, {"change.js": b"baseline\n"})
    target_id = _admit(ledger, "change.js")
    baseline_id = _admit(ledger, "change.js", RevisionSide.BASELINE)
    target = ledger.issue(target_id)
    baseline = ledger.issue(baseline_id)

    with pytest.raises(ReviewError):
        ledger.issue_derived(target.evidence_id, "-baseline\n+target", EvidenceKind.DIFF)
    other_target = ledger.issue(target_id)
    with pytest.raises(ReviewError):
        ledger.issue_derived(
            target.evidence_id,
            "-baseline\n+target",
            EvidenceKind.DIFF,
            counterpart_id=other_target.evidence_id,
        )

    diff = ledger.issue_derived(
        target.evidence_id,
        "-baseline\n+target",
        EvidenceKind.DIFF,
        counterpart_id=baseline.evidence_id,
    )
    view = json.loads(ledger.bundle([diff.evidence_id]))[0]
    assert diff.side is RevisionSide.TARGET
    assert diff.parent_evidence_id == target.evidence_id
    assert diff.counterpart_evidence_id == baseline.evidence_id
    assert view["counterpart_source_url"].endswith("/change.js#L1")
    assert "b" * 40 in view["counterpart_source_url"]
    assert "a" * 40 in view["source_url"]


def test_receipt_validation_is_atomic_and_source_coordinates_are_strict() -> None:
    snapshot, ledger, _ = context({"empty.txt": b""})
    file_id = _admit(ledger, "empty.txt")
    for kwargs in (
        {"first_line": 0},
        {"first_line": True},
        {"first_line": 1, "last_line": 0},
        {"first_line": 1, "last_line": 1, "byte_offset_in_line": -1},
    ):
        with pytest.raises(ReviewError):
            ledger.issue(file_id, **kwargs)

    evidence = ledger.issue(file_id)
    assert evidence.representation == ""
    assert evidence.span.first_byte_offset == evidence.span.last_byte_offset == 0
    too_many = [ledger.issue(file_id) for _ in range(65)]
    with pytest.raises(ValidationError):
        ledger.deliver([item.evidence_id for item in too_many], 1)
    assert ledger.delivered == {}
    assert ledger.receipts == []
