"""Tree-derived, original-side comparison records for the product surface."""

from __future__ import annotations

import difflib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from beforerun.features.budgets import Budget, ReviewError
from beforerun.features.contracts import ErrorCode, RevisionSide
from beforerun.features.evidence import EvidenceLedger, redact
from beforerun.features.snapshot import Snapshot, issued_id

_MAX_DIFF_INPUT_BYTES = 12 * 1024
_MAX_DIFF_INPUT_LINES = 160
_MAX_DIFF_OUTPUT_BYTES = 12_000
_MAX_DIFF_OUTPUT_LINES = 200
_DIFF_LIMIT_NOTE = "[Diff bounded; inspect original-side evidence and pinned source.]"


class ComparisonEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_pair_id: str
    path: str
    change: Literal["added", "removed", "modified", "mode_changed", "unchanged", "unknown"]
    mode_changed: bool = False
    target_file_id: str | None = None
    baseline_file_id: str | None = None
    target_evidence_ids: tuple[str, ...] = Field(default=(), max_length=8)
    baseline_evidence_ids: tuple[str, ...] = Field(default=(), max_length=8)
    evidence_complete: bool = False
    evidence_gaps: tuple[str, ...] = Field(default=(), max_length=4)
    diff: str = Field(default="", max_length=12_000)
    diff_limited: bool = False


class ComparisonView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested: bool
    complete: bool
    complete_within_inventory: bool
    entries: tuple[ComparisonEntry, ...] = Field(default=(), max_length=20_000)
    error: str | None = Field(default=None, max_length=500)


def compare_inventories(snapshot: Snapshot, *, baseline_requested: bool = False) -> ComparisonView:
    """Compare tree facts, not GitHub's supplementary compare-endpoint file list."""

    if RevisionSide.BASELINE not in snapshot.revisions:
        if baseline_requested:
            return failed_comparison(
                "The requested baseline is unavailable; change status remains unknown."
            )
        return ComparisonView(
            requested=False,
            complete=True,
            complete_within_inventory=True,
        )
    target = snapshot.paths.get(RevisionSide.TARGET, {})
    baseline = snapshot.paths.get(RevisionSide.BASELINE, {})
    target_complete = snapshot.inventory_complete.get(RevisionSide.TARGET, False)
    baseline_complete = snapshot.inventory_complete.get(RevisionSide.BASELINE, False)
    entries: list[ComparisonEntry] = []
    for path in sorted(set(target) | set(baseline)):
        target_id = target.get(path)
        baseline_id = baseline.get(path)
        target_record = snapshot.require_file(target_id).record if target_id else None
        baseline_record = snapshot.require_file(baseline_id).record if baseline_id else None
        mode_changed = bool(
            target_record and baseline_record and target_record.mode != baseline_record.mode
        )
        if target_record and not baseline_record:
            change = "added" if baseline_complete else "unknown"
        elif baseline_record and not target_record:
            change = "removed" if target_complete else "unknown"
        elif target_record and baseline_record and target_record.blob_id != baseline_record.blob_id:
            change = "modified"
        elif mode_changed:
            change = "mode_changed"
        else:
            change = "unchanged"
        # A tree object is still listed, but it has no blob evidence to fetch here.
        entries.append(
            ComparisonEntry(
                file_pair_id=issued_id("pair"),
                path=path,
                change=change,
                mode_changed=mode_changed,
                target_file_id=target_id,
                baseline_file_id=baseline_id,
            )
        )
    inventory_complete = target_complete and baseline_complete
    return ComparisonView(
        requested=True,
        complete=inventory_complete,
        complete_within_inventory=inventory_complete,
        entries=tuple(entries),
    )


def failed_comparison(message: str) -> ComparisonView:
    return ComparisonView(
        requested=True,
        complete=False,
        complete_within_inventory=False,
        error=message,
    )


def _bounded_diff(old: str, new: str, path: str) -> tuple[str, bool]:
    # Bound work before splitting or invoking SequenceMatcher, not just its output.
    for text in (old, new):
        if len(text) > _MAX_DIFF_INPUT_BYTES or len(text.encode("utf-8")) > _MAX_DIFF_INPUT_BYTES:
            return (
                "[Diff omitted: source exceeds the byte limit; inspect original-side evidence.]",
                True,
            )
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    if max(len(old_lines), len(new_lines)) > _MAX_DIFF_INPUT_LINES:
        return (
            "[Diff omitted: source exceeds the line limit; inspect original-side evidence.]",
            True,
        )
    old, _ = redact(old)
    new, _ = redact(new)
    lines = list(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=f"baseline/{path}",
            tofile=f"target/{path}",
            lineterm="",
            n=3,
        )
    )
    truncated = len(lines) > _MAX_DIFF_OUTPUT_LINES
    output = "\n".join(lines[:_MAX_DIFF_OUTPUT_LINES])
    encoded = output.encode("utf-8")
    content_limit = _MAX_DIFF_OUTPUT_BYTES - len(_DIFF_LIMIT_NOTE.encode("utf-8")) - 1
    if len(encoded) > content_limit:
        output = encoded[:content_limit].decode("utf-8", errors="ignore")
        truncated = True
    if truncated:
        output += "\n" + _DIFF_LIMIT_NOTE
    return output, truncated


async def materialize_comparison(
    snapshot: Snapshot,
    ledger: EvidenceLedger,
    comparison: ComparisonView,
    relevant_paths: set[str] | None = None,
    *,
    budget: Budget | None = None,
) -> ComparisonView:
    """Fetch selected counterparts under Agent A's shared snapshot/source budget.

    Absence of counterpart evidence never upgrades a finding's change claim. The UI shows
    ``evidence_complete`` independently from tree-derived added/removed/modified facts.
    Explicitly selected unchanged paths are materialized too, so an unchanged hook or
    helper has distinct evidence for each revision. Without a selection, fetch changed
    entries only. Evidence issuance does not claim delivery or validated behavior.
    """

    if not comparison.requested or comparison.error:
        return comparison
    if ledger.snapshot is not snapshot:
        raise ReviewError(
            ErrorCode.INVALID_TOOL_ARGUMENTS, "Comparison evidence belongs to another snapshot."
        )
    budget = budget if budget is not None else getattr(snapshot.source, "budget", None)
    selected: list[ComparisonEntry] = []
    all_evidence_complete = comparison.complete
    for entry in comparison.entries:
        if budget is not None:
            budget.check()
        if relevant_paths is None and entry.change == "unchanged":
            selected.append(entry)
            continue
        if relevant_paths is not None and entry.path not in relevant_paths:
            selected.append(entry)
            continue
        target_text: str | None = None
        baseline_text: str | None = None
        target_ids: list[str] = []
        baseline_ids: list[str] = []
        gaps: list[str] = []
        for side, file_id in (
            (RevisionSide.TARGET, entry.target_file_id),
            (RevisionSide.BASELINE, entry.baseline_file_id),
        ):
            if file_id is None:
                if not snapshot.inventory_complete.get(side, False):
                    gaps.append(
                        f"{side.value}: incomplete inventory cannot establish path absence."
                    )
                continue
            try:
                if budget is not None:
                    budget.check()
                await snapshot.admit_file(file_id, required=False)
                if budget is not None:
                    budget.check()
                stored = snapshot.require_file(file_id)
                if stored.text is None:
                    gaps.append(f"{side.value}: counterpart source is unread or unsupported.")
                    continue
                evidence = ledger.issue(file_id)
                source_lines = stored.text.splitlines() or [""]
                if (
                    evidence.span.last_line != len(source_lines)
                    or evidence.span.last_column != len(source_lines[-1].encode("utf-8")) + 1
                ):
                    gaps.append(
                        f"{side.value}: excerpt is bounded; remaining source is not represented."
                    )
                if side is RevisionSide.TARGET:
                    target_ids.append(evidence.evidence_id)
                    target_text = stored.text
                else:
                    baseline_ids.append(evidence.evidence_id)
                    baseline_text = stored.text
            except ReviewError as error:  # source errors become scoped comparison gaps
                if error.code in {ErrorCode.REVIEW_CANCELLED, ErrorCode.BUDGET_EXHAUSTED}:
                    raise
                gaps.append(f"{side.value}: counterpart evidence could not be issued.")
        readable_sides = (entry.target_file_id is None or target_text is not None) and (
            entry.baseline_file_id is None or baseline_text is not None
        )
        diff, diff_limited = "", False
        if entry.change in {"added", "removed", "modified"} and readable_sides:
            diff, diff_limited = _bounded_diff(baseline_text or "", target_text or "", entry.path)
        if budget is not None:
            budget.check()
        evidence_complete = not gaps
        selected.append(
            entry.model_copy(
                update={
                    "target_evidence_ids": tuple(target_ids),
                    "baseline_evidence_ids": tuple(baseline_ids),
                    "evidence_complete": evidence_complete,
                    "evidence_gaps": tuple(gaps),
                    "diff": diff,
                    "diff_limited": diff_limited,
                }
            )
        )
        if relevant_paths is not None and entry.path in relevant_paths and not evidence_complete:
            all_evidence_complete = False
        if relevant_paths is None and not evidence_complete:
            all_evidence_complete = False
    return comparison.model_copy(
        update={
            "entries": tuple(selected),
            "complete": all_evidence_complete,
        }
    )
