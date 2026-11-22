from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import socket
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from beforerun.features.budgets import Budget, ReviewError
from beforerun.features.compare import compare_inventories, materialize_comparison
from beforerun.features.contracts import ErrorCode, GitMode, PinnedRevision, RevisionSide
from beforerun.features.evidence import EvidenceLedger
from beforerun.features.github_source import Blob, GitHubSource
from beforerun.features.settings import Settings
from beforerun.features.snapshot import Snapshot

FIXTURE = Path(__file__).parent / "fixtures/compare/node-version-check"
RELEVANT_PATHS = {"package.json", "scripts/check-node.js"}


@pytest.fixture(autouse=True)
def forbid_network_and_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError(
            "Comparison tests must not open network connections or launch processes."
        )

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


def _revision(side: RevisionSide, suffix: str) -> PinnedRevision:
    return PinnedRevision(
        revision_id=f"rev_{side.value}_{suffix * 16}",
        repository_id=1,
        canonical_owner="example",
        canonical_name="inert-fixture",
        requested_ref=side.value,
        commit_sha=(suffix * 40)[:40],
        tree_sha=(suffix * 40)[:40],
        resolution_timestamp=datetime.now(UTC),
        side=side,
    )


def _object_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


class FakeSource:
    def __init__(self) -> None:
        self.blobs: dict[tuple[RevisionSide, str], bytes] = {}
        self.calls: list[tuple[RevisionSide, str]] = []

    def add(self, side: RevisionSide, path: str, content: bytes) -> dict[str, str]:
        sha = _object_sha(content)
        self.blobs[(side, sha)] = content
        return {"path": path, "mode": "100644", "type": "blob", "sha": sha}

    async def blob(self, revision: PinnedRevision, expected_sha: str) -> Blob:
        self.calls.append((revision.side, expected_sha))
        try:
            content = self.blobs[(revision.side, expected_sha)]
        except KeyError as error:
            raise ReviewError(
                ErrorCode.SOURCE_LIMIT, "Fixture counterpart is unavailable."
            ) from error
        return Blob(blob_id=expected_sha, content=content)


def _snapshot(
    target: dict[str, bytes], baseline: dict[str, bytes] | None
) -> tuple[Snapshot, EvidenceLedger]:
    revisions = {
        RevisionSide.TARGET: _revision(RevisionSide.TARGET, "a"),
    }
    if baseline is not None:
        revisions[RevisionSide.BASELINE] = _revision(RevisionSide.BASELINE, "b")
    source = FakeSource()
    snapshot = Snapshot(revisions, source)  # type: ignore[arg-type]
    for side, files in ((RevisionSide.TARGET, target), (RevisionSide.BASELINE, baseline)):
        if files is not None:
            entries = [source.add(side, path, content) for path, content in files.items()]
            snapshot.register_tree(side, entries, False)
    ledger = EvidenceLedger("review_1234567890123456", snapshot, Settings())
    return snapshot, ledger


def _fixture_files(side: str) -> dict[str, bytes]:
    return {path: (FIXTURE / side / path).read_bytes() for path in RELEVANT_PATHS}


def _fixture_snapshot() -> tuple[Snapshot, EvidenceLedger]:
    return _snapshot(_fixture_files("target"), _fixture_files("baseline"))


def test_unchanged_hook_changed_helper_has_original_side_evidence() -> None:
    snapshot, ledger = _fixture_snapshot()
    comparison = asyncio.run(
        materialize_comparison(snapshot, ledger, compare_inventories(snapshot), RELEVANT_PATHS)
    )
    by_path = {entry.path: entry for entry in comparison.entries}

    assert by_path["package.json"].change == "unchanged"
    hook = by_path["package.json"]
    assert hook.evidence_complete
    assert hook.target_evidence_ids and hook.baseline_evidence_ids
    assert (
        ledger.require(hook.target_evidence_ids[0]).representation
        == ledger.require(hook.baseline_evidence_ids[0]).representation
    )
    helper = by_path["scripts/check-node.js"]
    assert helper.change == "modified"
    assert helper.evidence_complete
    assert len(helper.target_evidence_ids) == len(helper.baseline_evidence_ids) == 1
    assert "-const requiredMajor = 20;" in helper.diff
    assert "+const requiredMajor = 22;" in helper.diff
    for evidence_id in helper.target_evidence_ids + helper.baseline_evidence_ids:
        evidence = ledger.require(evidence_id)
        assert evidence.span.first_line == 1
        assert ledger.link(evidence_id).startswith("https://github.com/example/inert-fixture/blob/")
    target = ledger.require(helper.target_evidence_ids[0])
    baseline = ledger.require(helper.baseline_evidence_ids[0])
    assert target.side is RevisionSide.TARGET
    assert baseline.side is RevisionSide.BASELINE
    assert "requiredMajor = 22" in target.representation
    assert "requiredMajor = 20" in baseline.representation
    assert comparison.complete
    assert ledger.receipts == []  # Issuance is not a claim that the analyst saw this source.


def test_tree_facts_cover_add_remove_mode_and_identical_content() -> None:
    target_files = _fixture_files("target")
    target_files.pop("scripts/check-node.js")
    target_files["added.js"] = b"// inert\n"
    snapshot, _ = _snapshot(target_files, _fixture_files("baseline"))
    package_id = snapshot.file_id(RevisionSide.TARGET, "package.json")
    assert package_id
    package = snapshot.require_file(package_id)
    package.record = package.record.model_copy(update={"mode": GitMode.EXECUTABLE_BLOB})

    comparison = compare_inventories(snapshot)
    changes = {entry.path: entry.change for entry in comparison.entries}
    assert changes["added.js"] == "added"
    assert changes["scripts/check-node.js"] == "removed"
    assert changes["package.json"] == "mode_changed"
    assert comparison.complete


def test_missing_counterpart_preserves_unknown_evidence_scope() -> None:
    snapshot, ledger = _fixture_snapshot()
    baseline_id = snapshot.file_id(RevisionSide.BASELINE, "scripts/check-node.js")
    assert baseline_id
    snapshot.source.blobs = {  # type: ignore[union-attr]
        key: value
        for key, value in snapshot.source.blobs.items()
        if key[0] is RevisionSide.TARGET  # type: ignore[union-attr]
    }
    comparison = asyncio.run(
        materialize_comparison(snapshot, ledger, compare_inventories(snapshot))
    )
    helper = next(entry for entry in comparison.entries if entry.path.endswith("check-node.js"))
    assert helper.change == "modified"
    assert helper.evidence_complete is False
    assert comparison.complete is False
    assert helper.target_evidence_ids
    assert helper.baseline_evidence_ids == ()
    assert helper.diff == ""  # An unread baseline is not an empty baseline.
    assert helper.evidence_gaps == ("baseline: counterpart source is unread or unsupported.",)


def test_absent_baseline_is_not_a_failed_target_review() -> None:
    snapshot, _ = _fixture_snapshot()
    snapshot.revisions.pop(RevisionSide.BASELINE)
    comparison = compare_inventories(snapshot)
    assert comparison.requested is False
    assert comparison.complete is True


def test_requested_but_missing_baseline_remains_a_comparison_gap() -> None:
    snapshot, ledger = _snapshot(_fixture_files("target"), None)
    comparison = compare_inventories(snapshot, baseline_requested=True)
    result = asyncio.run(materialize_comparison(snapshot, ledger, comparison))
    assert result.requested
    assert not result.complete
    assert not result.complete_within_inventory
    assert result.error and "unavailable" in result.error
    assert result.entries == ()
    assert snapshot.source.calls == []  # type: ignore[union-attr]


@pytest.mark.parametrize("incomplete_side", [RevisionSide.BASELINE, RevisionSide.TARGET])
def test_incomplete_inventory_cannot_prove_addition_or_removal(
    incomplete_side: RevisionSide,
) -> None:
    # Both versions of the known helper remain usable, while a missing path is uncertain.
    target, baseline = _fixture_files("target"), _fixture_files("baseline")
    present = target if incomplete_side is RevisionSide.BASELINE else baseline
    present["possibly-missing.js"] = b"// Inert source observation, no execution.\n"
    snapshot, ledger = _snapshot(target, baseline)
    snapshot.inventory_complete[incomplete_side] = False
    comparison = asyncio.run(
        materialize_comparison(snapshot, ledger, compare_inventories(snapshot))
    )
    by_path = {entry.path: entry for entry in comparison.entries}
    assert by_path["possibly-missing.js"].change == "unknown"
    assert not by_path["possibly-missing.js"].evidence_complete
    assert by_path["possibly-missing.js"].diff == ""
    assert by_path["scripts/check-node.js"].change == "modified"
    assert by_path["scripts/check-node.js"].evidence_complete
    assert not comparison.complete
    assert not comparison.complete_within_inventory


def test_missing_inventory_marker_fails_closed() -> None:
    snapshot, _ = _fixture_snapshot()
    snapshot.inventory_complete.pop(RevisionSide.BASELINE)
    assert compare_inventories(snapshot).complete is False


def test_existing_behavior_keeps_both_sides_even_for_identical_commits() -> None:
    files = _fixture_files("baseline")
    snapshot, ledger = _snapshot(files, files)
    target = snapshot.revisions[RevisionSide.TARGET]
    baseline = snapshot.revisions[RevisionSide.BASELINE]
    snapshot.revisions[RevisionSide.BASELINE] = baseline.model_copy(
        update={"commit_sha": target.commit_sha, "tree_sha": target.tree_sha}
    )
    comparison = asyncio.run(
        materialize_comparison(snapshot, ledger, compare_inventories(snapshot), RELEVANT_PATHS)
    )
    assert comparison.complete
    for entry in comparison.entries:
        assert entry.change == "unchanged"
        assert entry.diff == ""
        assert entry.evidence_complete
        target_evidence = ledger.require(entry.target_evidence_ids[0])
        baseline_evidence = ledger.require(entry.baseline_evidence_ids[0])
        assert target_evidence.evidence_id != baseline_evidence.evidence_id
        assert target_evidence.revision_id != baseline_evidence.revision_id
        assert target_evidence.side is RevisionSide.TARGET
        assert baseline_evidence.side is RevisionSide.BASELINE
        assert target_evidence.raw_sha256 == baseline_evidence.raw_sha256
        assert target_evidence.representation == baseline_evidence.representation


def test_changed_entry_keeps_evidence_for_unchanged_helper() -> None:
    baseline = _fixture_files("baseline")
    target = dict(baseline)
    target["package.json"] = baseline["package.json"].replace(b'"prepare"', b'"preinstall"')
    snapshot, ledger = _snapshot(target, baseline)
    comparison = asyncio.run(
        materialize_comparison(snapshot, ledger, compare_inventories(snapshot), RELEVANT_PATHS)
    )
    by_path = {entry.path: entry for entry in comparison.entries}
    entry, helper = by_path["package.json"], by_path["scripts/check-node.js"]
    assert entry.change == "modified" and helper.change == "unchanged"
    assert '"preinstall"' in entry.diff and '"prepare"' in entry.diff
    assert helper.target_evidence_ids and helper.baseline_evidence_ids
    assert comparison.complete


def test_removed_behavior_preserves_baseline_spans_and_scoped_target_absence() -> None:
    snapshot, ledger = _snapshot({}, _fixture_files("baseline"))
    comparison = asyncio.run(
        materialize_comparison(snapshot, ledger, compare_inventories(snapshot), RELEVANT_PATHS)
    )
    assert comparison.complete
    for entry in comparison.entries:
        assert entry.change == "removed"
        assert entry.evidence_complete
        assert entry.target_file_id is None and entry.target_evidence_ids == ()
        evidence = ledger.require(entry.baseline_evidence_ids[0])
        assert evidence.side is RevisionSide.BASELINE
        assert evidence.span.first_line == 1
        assert "baseline/" + entry.path in entry.diff
    assert all(side is RevisionSide.BASELINE for side, _ in snapshot.source.calls)  # type: ignore[union-attr]


@pytest.mark.parametrize("added", [True, False])
def test_empty_file_addition_and_removal_is_readable(added: bool) -> None:
    files = {"empty.txt": b""}
    snapshot, ledger = _snapshot(files if added else {}, {} if added else files)
    comparison = asyncio.run(
        materialize_comparison(snapshot, ledger, compare_inventories(snapshot))
    )
    entry = comparison.entries[0]
    assert entry.change == ("added" if added else "removed")
    assert entry.evidence_complete and comparison.complete
    assert entry.diff == ""
    evidence = ledger.require((entry.target_evidence_ids or entry.baseline_evidence_ids)[0])
    assert evidence.representation == ""
    assert evidence.span.first_line == evidence.span.last_line == 1


def test_blob_and_mode_changes_are_both_preserved() -> None:
    snapshot, _ = _fixture_snapshot()
    file_id = snapshot.file_id(RevisionSide.TARGET, "scripts/check-node.js")
    assert file_id
    stored = snapshot.require_file(file_id)
    stored.record = stored.record.model_copy(update={"mode": GitMode.EXECUTABLE_BLOB})
    helper = next(
        entry for entry in compare_inventories(snapshot).entries if entry.path.endswith(".js")
    )
    assert helper.change == "modified"
    assert helper.mode_changed


def test_unsupported_counterpart_is_not_dereferenced_or_diffed_as_empty() -> None:
    snapshot, ledger = _fixture_snapshot()
    file_id = snapshot.file_id(RevisionSide.BASELINE, "scripts/check-node.js")
    assert file_id
    stored = snapshot.require_file(file_id)
    stored.record = stored.record.model_copy(update={"mode": GitMode.SYMLINK})
    comparison = asyncio.run(
        materialize_comparison(snapshot, ledger, compare_inventories(snapshot))
    )
    helper = next(entry for entry in comparison.entries if entry.path.endswith(".js"))
    assert not helper.evidence_complete and not comparison.complete
    assert helper.target_evidence_ids and not helper.baseline_evidence_ids
    assert helper.diff == ""
    assert (RevisionSide.BASELINE, stored.record.blob_id) not in snapshot.source.calls  # type: ignore[union-attr]


@pytest.mark.parametrize("large_source", [b"x" * 20_000, b"// inert line\n" * 161])
def test_large_and_minified_sources_bound_diff_work_before_matching(
    monkeypatch: pytest.MonkeyPatch, large_source: bytes
) -> None:
    def forbidden_diff(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Oversized input must not reach the diff matcher.")

    monkeypatch.setattr("beforerun.features.compare.difflib.unified_diff", forbidden_diff)
    snapshot, ledger = _snapshot({"helper.js": large_source}, {"helper.js": b"// old inert\n"})
    comparison = asyncio.run(
        materialize_comparison(snapshot, ledger, compare_inventories(snapshot))
    )
    entry = comparison.entries[0]
    assert entry.diff_limited and "Diff omitted" in entry.diff
    assert not entry.evidence_complete and not comparison.complete
    evidence = ledger.require(entry.target_evidence_ids[0])
    assert evidence.span.first_line == 1
    assert "#L1" in ledger.link(evidence.evidence_id)
    assert len(evidence.representation.encode("utf-8")) <= 12 * 1024


def test_diff_is_redacted_like_original_side_evidence() -> None:
    snapshot, ledger = _snapshot(
        {"config.txt": b"api_key=synthetic_target_value\nNode 22\n"},
        {"config.txt": b"api_key=synthetic_baseline_value\nNode 20\n"},
    )
    comparison = asyncio.run(
        materialize_comparison(snapshot, ledger, compare_inventories(snapshot))
    )
    entry = comparison.entries[0]
    assert "[REDACTED]" in entry.diff
    assert "synthetic_target_value" not in comparison.model_dump_json()
    assert "synthetic_baseline_value" not in comparison.model_dump_json()
    assert "-Node 20" in entry.diff and "+Node 22" in entry.diff
    for evidence_id in entry.target_evidence_ids + entry.baseline_evidence_ids:
        assert "[REDACTED]" in ledger.require(evidence_id).representation


def test_diff_output_is_bounded_in_utf8_and_rows_with_original_hunk_coordinates() -> None:
    # Short repeated Unicode lines challenge both the row and UTF-8 output limits.
    baseline = ("旧" * 20 + "\n") * 160
    target = ("新" * 20 + "\n") * 160
    snapshot, ledger = _snapshot({"unicode.js": target.encode()}, {"unicode.js": baseline.encode()})
    comparison = asyncio.run(
        materialize_comparison(snapshot, ledger, compare_inventories(snapshot))
    )
    entry = comparison.entries[0]
    assert entry.diff_limited
    assert len(entry.diff.encode("utf-8")) <= 12_000
    assert len(entry.diff.splitlines()) <= 201
    assert "@@ -1,160 +1,160 @@" in entry.diff
    assert entry.diff.endswith("[Diff bounded; inspect original-side evidence and pinned source.]")
    assert entry.evidence_complete  # Display limits are distinct from available source evidence.


def test_diff_hunk_rows_do_not_replace_original_evidence_coordinates() -> None:
    baseline = [f"// original line {number}" for number in range(1, 31)]
    target = list(baseline)
    target[19] = "// changed compatibility message"
    snapshot, ledger = _snapshot(
        {"helper.js": "\n".join(target).encode()}, {"helper.js": "\n".join(baseline).encode()}
    )
    comparison = asyncio.run(
        materialize_comparison(snapshot, ledger, compare_inventories(snapshot))
    )
    entry = comparison.entries[0]
    assert "@@ -17,7 +17,7 @@" in entry.diff
    for evidence_id in entry.target_evidence_ids + entry.baseline_evidence_ids:
        evidence = ledger.require(evidence_id)
        assert (evidence.span.first_line, evidence.span.last_line) == (1, 30)
        assert ledger.link(evidence_id).endswith("#L1-L30")


def test_only_selected_counterparts_are_fetched() -> None:
    snapshot, ledger = _fixture_snapshot()
    comparison = asyncio.run(
        materialize_comparison(snapshot, ledger, compare_inventories(snapshot), {"package.json"})
    )
    by_path = {entry.path: entry for entry in comparison.entries}
    assert by_path["package.json"].evidence_complete
    assert by_path["scripts/check-node.js"].target_evidence_ids == ()
    assert len(snapshot.source.calls) == 2  # type: ignore[union-attr]


def test_comparison_uses_the_shared_source_budget_with_mocked_http() -> None:
    async def run() -> None:
        target, baseline = _fixture_files("target"), _fixture_files("baseline")
        blobs = {_object_sha(raw): raw for raw in [*target.values(), *baseline.values()]}
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            sha = request.url.path.rsplit("/", 1)[-1]
            raw = blobs[sha]
            return httpx.Response(
                200,
                json={
                    "sha": sha,
                    "size": len(raw),
                    "encoding": "base64",
                    "content": base64.b64encode(raw).decode("ascii"),
                },
            )

        settings = Settings()
        budget = Budget(settings)
        snapshot, _ = _snapshot(target, baseline)
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            snapshot.source = GitHubSource(settings, budget, client=client)
            ledger = EvidenceLedger("review_1234567890123456", snapshot, settings)
            comparison = await materialize_comparison(
                snapshot, ledger, compare_inventories(snapshot), RELEVANT_PATHS
            )
        assert comparison.complete
        assert budget.github_attempts == len(requests) == 4
        assert budget.distinct_blobs == 3  # Shared bytes still have distinct side provenance.
        assert budget.source_bytes == sum(len(raw) for raw in blobs.values())
        assert budget.model_attempts == 0
        assert all(request.url.host == "api.github.com" for request in requests)

    asyncio.run(run())


@pytest.mark.parametrize("cancelled", [True, False])
def test_cancellation_and_deadline_stop_before_any_source_work(cancelled: bool) -> None:
    snapshot, ledger = _fixture_snapshot()
    budget = Budget(Settings(), clock=lambda: 1000.0, started_at=0.0)
    if cancelled:
        budget.cancel_event.set()
    with pytest.raises(ReviewError) as error:
        asyncio.run(
            materialize_comparison(snapshot, ledger, compare_inventories(snapshot), budget=budget)
        )
    assert error.value.code is (
        ErrorCode.REVIEW_CANCELLED if cancelled else ErrorCode.BUDGET_EXHAUSTED
    )
    assert snapshot.source.calls == []  # type: ignore[union-attr]
    assert ledger.evidence == {}


def test_cancellation_during_target_fetch_prevents_baseline_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, ledger = _fixture_snapshot()
    source = snapshot.source
    budget = Budget(Settings())
    original_blob = source.blob

    async def cancel_after_blob(revision: PinnedRevision, expected_sha: str) -> Blob:
        result = await original_blob(revision, expected_sha)
        budget.cancel_event.set()
        return result

    monkeypatch.setattr(source, "blob", cancel_after_blob)
    with pytest.raises(ReviewError) as error:
        asyncio.run(
            materialize_comparison(snapshot, ledger, compare_inventories(snapshot), budget=budget)
        )
    assert error.value.code is ErrorCode.REVIEW_CANCELLED
    assert len(source.calls) == 1  # type: ignore[attr-defined]
    assert ledger.evidence == {}


def test_other_snapshot_ledger_is_rejected_before_source_work() -> None:
    snapshot, _ = _fixture_snapshot()
    _, unrelated_ledger = _fixture_snapshot()
    with pytest.raises(ReviewError) as error:
        asyncio.run(
            materialize_comparison(snapshot, unrelated_ledger, compare_inventories(snapshot))
        )
    assert error.value.code is ErrorCode.INVALID_TOOL_ARGUMENTS
    assert snapshot.source.calls == []  # type: ignore[union-attr]


def test_fixture_annotations_keep_behavior_claims_separate_from_tree_facts() -> None:
    annotation = json.loads((FIXTURE / "annotation.json").read_text())
    cases = json.loads((FIXTURE.parent / "cases.json").read_text())
    assert annotation["expected_change_status"] == "changed"
    assert annotation["synthetic"] and cases["synthetic"]
    assert {case["expected_change_status"] for case in cases["cases"]} == {
        "existing",
        "changed",
        "removed",
        "unknown",
    }
    assert "Agent A validation" in cases["label_authority"]
