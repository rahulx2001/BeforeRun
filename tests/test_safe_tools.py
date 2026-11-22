from __future__ import annotations

import asyncio
import json
import socket
import subprocess

import pytest
from review_helpers import call, context

from beforerun.features.budgets import ReviewError
from beforerun.features.compare import compare_inventories
from beforerun.features.contracts import DecodeOperation, ErrorCode, RevisionSide
from beforerun.features.safe_tools import (
    OUTPUT_BYTES,
    SnapshotTools,
    static_decode,
    tool_definitions,
)
from beforerun.features.settings import Settings


@pytest.fixture(autouse=True)
def forbid_host_side_effects(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Offline tools cannot launch a process or open a real connection.")

    monkeypatch.setattr(socket.socket, "connect", reject)
    monkeypatch.setattr(subprocess, "Popen", reject)


def test_read_list_decode_strings_and_finish_have_owned_delivery() -> None:
    async def run():
        snapshot, ledger, budget = context(
            {"literal.txt": b'"SGVsbG8="', "strings.js": b'const x = "<script>inert</script>";\n'}
        )
        tools = SnapshotTools(snapshot, ledger, budget)
        listing = await tools.dispatch(
            call(
                "br_list_files",
                {
                    "container_id": tools.container_id(RevisionSide.TARGET),
                    "side": "target",
                },
            ),
            turn=1,
        )
        assert len(json.loads(listing.results[0].output)["entries"]) == 2
        file_id = snapshot.file_id(RevisionSide.TARGET, "literal.txt")
        read = await tools.dispatch(
            call(
                "br_read_excerpt",
                {
                    "file_id": file_id,
                    "first_original_line": 1,
                    "last_original_line": 1,
                },
                "read_1",
            ),
            turn=2,
        )
        evidence_id = json.loads(read.results[0].output)["evidence"][0]["evidence_id"]
        assert ledger.require_delivered(evidence_id).representation == '"SGVsbG8="'
        decoded = await tools.dispatch(
            call(
                "br_static_decode",
                {
                    "source_evidence_id": evidence_id,
                    "operations": ["base64"],
                },
                "decode_1",
            ),
            turn=3,
        )
        view = json.loads(decoded.results[0].output)["evidence"][0]
        assert view["representation"] == "Hello" and view["kind"] == "decoded"
        assert ledger.require_delivered(view["evidence_id"]).parent_evidence_id == evidence_id
        strings = await tools.dispatch(
            call(
                "br_extract_strings",
                {
                    "file_id": snapshot.file_id(RevisionSide.TARGET, "strings.js"),
                },
                "strings_1",
            ),
            turn=4,
        )
        assert "<script>inert</script>" in strings.results[0].output
        result = await tools.dispatch(
            call("br_finish", {"reason": "Evidence is sufficient."}, "finish_1"), turn=5
        )
        assert result.finish_reason and budget.tool_operations == 5
        assert len(tool_definitions()) == 7

    asyncio.run(run())


@pytest.mark.parametrize(
    "name,args",
    [
        ("exec", {"command": "unused"}),
        (
            "br_read_excerpt",
            {"file_id": "/etc/passwd", "first_original_line": 1, "last_original_line": 1},
        ),
        (
            "br_read_excerpt",
            {"file_id": "file_" + "z" * 24, "first_original_line": 1, "last_original_line": 161},
        ),
        ("br_search_source", {"terms": ["x"], "url": "https://callback.invalid"}),
        ("br_static_decode", {"source_evidence_id": "ev_" + "z" * 24, "operations": ["eval"]}),
    ],
)
def test_forbidden_or_malformed_arguments_have_no_side_effects(name, args) -> None:
    snapshot, ledger, budget = context({"source.js": b"// inert\n"})
    with pytest.raises(ReviewError):
        asyncio.run(SnapshotTools(snapshot, ledger, budget).dispatch(call(name, args), turn=1))
    assert budget.tool_operations == 0 and snapshot.source.calls == []
    assert ledger.receipts == []


def test_whole_batch_and_cross_job_containers_are_validated_before_fetch() -> None:
    snapshot, ledger, budget = context({"source.js": b"// inert\n"})
    other_snapshot, other_ledger, other_budget = context()
    other = SnapshotTools(other_snapshot, other_ledger, other_budget)
    proposed = call(
        "br_read_excerpt",
        {
            "file_id": snapshot.file_id(RevisionSide.TARGET, "source.js"),
            "first_original_line": 1,
            "last_original_line": 1,
        },
    )
    proposed["calls"].extend(
        call(
            "br_list_files",
            {
                "container_id": other.container_id(RevisionSide.TARGET),
                "side": "target",
            },
            "second",
        )["calls"]
    )
    with pytest.raises(ReviewError):
        asyncio.run(SnapshotTools(snapshot, ledger, budget).dispatch(proposed, turn=1))
    assert budget.tool_operations == 0 and snapshot.source.calls == []


def test_search_is_bounded_pointer_only_and_never_fetches_unread_files() -> None:
    async def run():
        snapshot, ledger, budget = context({"docs.txt": b"dummy\n" * 20, "unread.txt": b"dummy"})
        file_id = snapshot.file_id(RevisionSide.TARGET, "docs.txt")
        await snapshot.admit_file(file_id)
        before = list(snapshot.source.calls)
        result = await SnapshotTools(snapshot, ledger, budget).dispatch(
            call(
                "br_search_source",
                {
                    "terms": ["dummy"],
                    "file_ids": list(snapshot.paths[RevisionSide.TARGET].values()),
                },
            ),
            turn=1,
        )
        value = json.loads(result.results[0].output)
        assert len(value["hits"]) == 15 and value["truncated"]
        assert value["unread_file_ids"]
        assert all(hit["pointer_only"] for hit in value["hits"])
        assert snapshot.source.calls == before and ledger.receipts == []

    asyncio.run(run())


def test_diff_delivers_distinct_original_sides_and_does_not_certify_behavior() -> None:
    async def run():
        snapshot, ledger, budget = context(
            {"helper.js": b"const node = 22;\n"}, {"helper.js": b"const node = 20;\n"}
        )
        comparison = compare_inventories(snapshot)
        tools = SnapshotTools(snapshot, ledger, budget, comparison)
        result = await tools.dispatch(
            call(
                "br_read_diff",
                {
                    "file_pair_id": comparison.entries[0].file_pair_id,
                },
            ),
            turn=1,
        )
        value = json.loads(result.results[0].output)
        assert "-const node = 20" in value["diff"] and "+const node = 22" in value["diff"]
        assert {item["side"] for item in value["evidence"]} == {"target", "baseline"}
        for item in value["evidence"]:
            assert ledger.require_delivered(item["evidence_id"]).span.first_line == 1

    asyncio.run(run())


def test_cancel_exhaustion_and_duplicate_calls_cannot_start_new_work() -> None:
    async def run():
        snapshot, ledger, budget = context(settings=Settings(max_tool_operations=1))
        tools = SnapshotTools(snapshot, ledger, budget)
        proposed = call("br_finish", {"reason": "Stop."})
        await tools.dispatch(proposed, turn=1)
        with pytest.raises(ReviewError):
            await tools.dispatch(proposed, turn=2)
        with pytest.raises(ReviewError):
            await tools.dispatch(call("br_finish", {"reason": "Stop."}, "new"), turn=2)
        budget.cancel_event.set()
        with pytest.raises(ReviewError) as failure:
            await tools.dispatch(call("br_finish", {"reason": "Stop."}, "later"), turn=3)
        assert failure.value.code is ErrorCode.REVIEW_CANCELLED
        assert budget.tool_operations == 1

    asyncio.run(run())


@pytest.mark.parametrize(
    "value,operation,expected",
    [
        ("48656c6c6f", DecodeOperation.HEX, "Hello"),
        (r"\u0048\x69", DecodeOperation.ESCAPE, "Hi"),
        ("[72,105]", DecodeOperation.CHARACTER_CODE, "Hi"),
    ],
)
def test_literal_decoding_has_no_evaluation(value, operation, expected) -> None:
    assert static_decode(value, (operation,)) == expected
    if operation is DecodeOperation.ESCAPE:
        assert static_decode("import('host')", (operation,)) == "import('host')"
    else:
        with pytest.raises(ReviewError):
            static_decode("import('host')", (operation,))


def test_oversized_serialized_source_is_not_marked_delivered() -> None:
    async def run():
        snapshot, ledger, budget = context({"escaped.txt": b"\\" * (12 * 1024)})
        result = await SnapshotTools(snapshot, ledger, budget).dispatch(
            call(
                "br_read_excerpt",
                {
                    "file_id": snapshot.file_id(RevisionSide.TARGET, "escaped.txt"),
                    "first_original_line": 1,
                    "last_original_line": 1,
                },
            ),
            turn=1,
        )
        assert not result.results[0].succeeded
        assert result.results[0].error.code is ErrorCode.SOURCE_LIMIT
        assert ledger.receipts == []

    asyncio.run(run())


def test_invalid_receipt_turn_is_rejected_before_fetch_or_budget_mutation() -> None:
    snapshot, ledger, budget = context({"source.js": b"// inert\n"})
    with pytest.raises(ReviewError) as failure:
        asyncio.run(
            SnapshotTools(snapshot, ledger, budget).dispatch(
                call(
                    "br_read_excerpt",
                    {
                        "file_id": snapshot.file_id(RevisionSide.TARGET, "source.js"),
                        "first_original_line": 1,
                        "last_original_line": 1,
                    },
                ),
                turn=0,
            )
        )
    assert failure.value.code is ErrorCode.INVALID_TOOL_ARGUMENTS
    assert budget.tool_operations == 0 and snapshot.source.calls == []
    assert ledger.receipts == []


def test_static_decode_cannot_extend_derived_provenance_beyond_string_depth() -> None:
    async def run():
        snapshot, ledger, budget = context({"literal.txt": b'"U0dWc2JHOD0="'})
        tools = SnapshotTools(snapshot, ledger, budget)
        read = await tools.dispatch(
            call(
                "br_read_excerpt",
                {
                    "file_id": snapshot.file_id(RevisionSide.TARGET, "literal.txt"),
                    "first_original_line": 1,
                    "last_original_line": 1,
                },
                "read",
            ),
            turn=1,
        )
        source_id = json.loads(read.results[0].output)["evidence"][0]["evidence_id"]
        decoded = await tools.dispatch(
            call(
                "br_static_decode",
                {"source_evidence_id": source_id, "operations": ["base64"]},
                "decode",
            ),
            turn=2,
        )
        derived_id = json.loads(decoded.results[0].output)["evidence"][0]["evidence_id"]
        assert ledger.require_delivered(derived_id).representation == "SGVsbG8="
        with pytest.raises(ReviewError) as failure:
            await tools.dispatch(
                call(
                    "br_static_decode",
                    {"source_evidence_id": derived_id, "operations": ["base64"]},
                    "decode_again",
                ),
                turn=3,
            )
        assert failure.value.code is ErrorCode.INVALID_TOOL_ARGUMENTS
        assert budget.tool_operations == 2 and len(ledger.receipts) == 2

    asyncio.run(run())


def test_foreign_comparison_pair_is_rejected_before_materialization() -> None:
    snapshot, ledger, budget = context({"current.js": b"// current\n"})
    other_snapshot, _, _ = context({"other.js": b"new\n"}, {"other.js": b"old\n"})
    foreign = compare_inventories(other_snapshot)
    tools = SnapshotTools(snapshot, ledger, budget, foreign)
    with pytest.raises(ReviewError) as failure:
        asyncio.run(
            tools.dispatch(
                call("br_read_diff", {"file_pair_id": foreign.entries[0].file_pair_id}),
                turn=1,
            )
        )
    assert failure.value.code is ErrorCode.INVALID_TOOL_ARGUMENTS
    assert budget.tool_operations == 0 and snapshot.source.calls == []
    assert ledger.receipts == []


def test_malformed_unicode_finish_is_a_structured_rejection_without_work() -> None:
    snapshot, ledger, budget = context()
    reason = "inert fixture: " + "\ud800"
    with pytest.raises(ReviewError) as failure:
        asyncio.run(
            SnapshotTools(snapshot, ledger, budget).dispatch(
                call("br_finish", {"reason": reason}), turn=1
            )
        )
    assert failure.value.code is ErrorCode.INVALID_TOOL_ARGUMENTS
    assert budget.tool_operations == 0 and ledger.receipts == []


def test_unadmitted_revision_container_fails_closed() -> None:
    snapshot, ledger, budget = context()
    tools = SnapshotTools(snapshot, ledger, budget)
    with pytest.raises(ReviewError) as failure:
        tools.container_id(RevisionSide.BASELINE)
    assert failure.value.code is ErrorCode.INVALID_TOOL_ARGUMENTS
    assert budget.tool_operations == 0


def test_list_files_paginates_at_eighty_without_inventing_inventory() -> None:
    async def run():
        files = {f"src/{index:03d}.txt": b"inert" for index in range(81)}
        snapshot, ledger, budget = context(files)
        tools = SnapshotTools(snapshot, ledger, budget)
        target = tools.container_id(RevisionSide.TARGET)
        first = await tools.dispatch(
            call("br_list_files", {"container_id": target, "side": "target"}, "page_1"),
            turn=1,
        )
        value = json.loads(first.results[0].output)
        assert len(value["entries"]) == 80 and value["next_cursor"] == 80
        assert value["total"] == 81 and value["inventory_complete"]
        second = await tools.dispatch(
            call(
                "br_list_files",
                {"container_id": target, "side": "target", "cursor": 80},
                "page_2",
            ),
            turn=2,
        )
        last = json.loads(second.results[0].output)
        assert len(last["entries"]) == 1 and last["next_cursor"] is None
        assert snapshot.source.calls == [] and ledger.receipts == []

    asyncio.run(run())


def test_minified_chunk_requires_matching_current_file_and_preserves_columns() -> None:
    async def run():
        snapshot, ledger, budget = context({"one.js": b"x" * (12 * 1024 + 20), "two.js": b"other"})
        tools = SnapshotTools(snapshot, ledger, budget)
        one = snapshot.file_id(RevisionSide.TARGET, "one.js")
        two = snapshot.file_id(RevisionSide.TARGET, "two.js")
        first = await tools.dispatch(
            call(
                "br_read_excerpt",
                {"file_id": one, "first_original_line": 1, "last_original_line": 1},
                "first_chunk",
            ),
            turn=1,
        )
        view = json.loads(first.results[0].output)["evidence"][0]
        assert view["truncated"] and view["next_chunk_id"]
        continued = await tools.dispatch(
            call(
                "br_read_excerpt",
                {"file_id": one, "chunk_id": view["next_chunk_id"]},
                "next_chunk",
            ),
            turn=2,
        )
        next_view = json.loads(continued.results[0].output)["evidence"][0]
        assert next_view["span"]["first_line"] == 1
        assert next_view["span"]["first_column"] == 12 * 1024 + 1
        assert next_view["representation"] == "x" * 20
        with pytest.raises(ReviewError):
            await tools.dispatch(
                call(
                    "br_read_excerpt",
                    {"file_id": two, "chunk_id": view["next_chunk_id"]},
                    "wrong_file",
                ),
                turn=3,
            )
        assert budget.tool_operations == 2
        assert snapshot.require_file(two).record.selected is False

    asyncio.run(run())


def test_extracted_string_outputs_and_receipts_have_identical_bounded_sets() -> None:
    async def run():
        raw = " ".join(f'"value-{index:02d}"' for index in range(80)).encode()
        snapshot, ledger, budget = context({"strings.js": raw})
        tools = SnapshotTools(snapshot, ledger, budget)
        result = await tools.dispatch(
            call(
                "br_extract_strings",
                {"file_id": snapshot.file_id(RevisionSide.TARGET, "strings.js")},
            ),
            turn=1,
        )
        assert result.results[0].succeeded
        value = json.loads(result.results[0].output)
        assert value["truncated"] and 1 <= len(value["strings"]) <= 32
        assert len(result.results[0].output.encode("utf-8")) <= OUTPUT_BYTES
        visible_ids = {
            item[kind]["evidence_id"] for item in value["strings"] for kind in ("literal", "source")
        }
        receipt_ids = {item.evidence_id for receipt in ledger.receipts for item in receipt.items}
        assert visible_ids == receipt_ids
        assert len(visible_ids) == 2 * len(value["strings"])
        for item in value["strings"]:
            assert item["literal"]["kind"] == "string"
            assert item["literal"]["parent_evidence_id"] == item["source"]["evidence_id"]
            assert item["source"]["span"]["first_line"] == 1

    asyncio.run(run())


def test_static_decode_requires_delivery_and_bounds_every_operation() -> None:
    async def run():
        snapshot, ledger, budget = context({"literal.txt": b'"SGVsbG8="'})
        file_id = snapshot.file_id(RevisionSide.TARGET, "literal.txt")
        await snapshot.admit_file(file_id)
        undelivered = ledger.issue(file_id)
        tools = SnapshotTools(snapshot, ledger, budget)
        with pytest.raises(ReviewError) as failure:
            await tools.dispatch(
                call(
                    "br_static_decode",
                    {
                        "source_evidence_id": undelivered.evidence_id,
                        "operations": ["base64"],
                    },
                ),
                turn=1,
            )
        assert failure.value.code is ErrorCode.INVALID_MODEL_OUTPUT
        assert budget.tool_operations == 0 and ledger.receipts == []

    asyncio.run(run())
    assert static_decode("U0dWc2JHOD0=", (DecodeOperation.BASE64,) * 2) == "Hello"
    with pytest.raises(ReviewError) as failure:
        static_decode("x" * (12 * 1024 + 1), (DecodeOperation.ESCAPE,))
    assert failure.value.code is ErrorCode.SOURCE_LIMIT
    with pytest.raises(ReviewError):
        static_decode("[1114112]", (DecodeOperation.CHARACTER_CODE,))
    with pytest.raises(ReviewError):
        static_decode(r"\q", (DecodeOperation.ESCAPE,))


def test_diff_hunk_cursor_pages_server_rows_with_original_side_evidence() -> None:
    async def run():
        old = "\n".join(f"const value{index} = 0;" for index in range(50)).encode()
        new = "\n".join(f"const value{index} = 1;" for index in range(50)).encode()
        snapshot, ledger, budget = context({"helper.js": new}, {"helper.js": old})
        comparison = compare_inventories(snapshot)
        tools = SnapshotTools(snapshot, ledger, budget, comparison)
        pair = comparison.entries[0].file_pair_id
        first = await tools.dispatch(call("br_read_diff", {"file_pair_id": pair}, "diff_1"), turn=1)
        first_value = json.loads(first.results[0].output)
        assert len(first_value["diff"].splitlines()) == 40
        assert first_value["next_cursor"] == 40
        assert {item["side"] for item in first_value["evidence"]} == {"target", "baseline"}
        second = await tools.dispatch(
            call(
                "br_read_diff",
                {"file_pair_id": pair, "hunk_cursor": 40},
                "diff_2",
            ),
            turn=2,
        )
        second_value = json.loads(second.results[0].output)
        assert len(second_value["diff"].splitlines()) == 40
        assert second_value["next_cursor"] == 80
        assert "-const value40 = 0;" in second_value["diff"]
        assert "+const value20 = 1;" in second_value["diff"]
        assert len(ledger.receipts) == 2

    asyncio.run(run())
