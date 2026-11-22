from __future__ import annotations

import asyncio
import socket
import subprocess
from pathlib import Path

import pytest
from review_helpers import context
from s05_helpers import analyze, error_text, manifest, review_input

from beforerun.features.compare import compare_inventories, materialize_comparison
from beforerun.features.contracts import FetchStatus, GitMode, RelationshipSupport
from beforerun.features.npm_setup import NpmSetupAnalyzer

COMPARE_FIXTURE = Path(__file__).parent / "fixtures/compare/node-version-check"


@pytest.fixture(autouse=True)
def forbid_network_and_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Reachability tests cannot use networking or target processes.")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)


def fetched_paths(snapshot) -> set[str]:
    return {
        stored.record.path
        for stored in snapshot.files_by_id.values()
        if stored.record.fetch_status is FetchStatus.FETCHED
    }


def test_nested_npm_run_and_literal_imports_keep_edge_kinds_and_limits() -> None:
    snapshot, ledger, _, analysis = asyncio.run(
        analyze(
            {
                "package.json": manifest(
                    {
                        "prepare": "npm run bundle",
                        "bundle": "node scripts/start.cjs",
                    }
                ),
                "scripts/start.cjs": (
                    'const nested = require("./nested");\n'
                    'const lazy = import("./" + nested.name);\n'
                ).encode(),
                "scripts/nested.js": b"// inert require-suffix fixture\n",
            }
        )
    )
    kinds = {edge.kind for edge in analysis.relationships}
    assert kinds == {
        "nested_npm_run",
        "npm_lifecycle_local_command",
        "local_require",
    }
    direct = next(edge for edge in analysis.relationships if edge.kind.endswith("command"))
    assert direct.support is RelationshipSupport.SUPPORTED
    static_import = next(edge for edge in analysis.relationships if edge.kind == "local_require")
    assert static_import.support is RelationshipSupport.INFERRED
    assert "computed import/require" in error_text(analysis)
    assert "runtime" in static_import.assumptions[0]
    assert fetched_paths(snapshot) == {
        "package.json",
        "scripts/start.cjs",
        "scripts/nested.js",
    }
    assert ledger.require(static_import.caller_evidence_id).representation.startswith(
        "const nested"
    )


def test_commonjs_suffix_index_and_esm_literal_forms_resolve_separately() -> None:
    snapshot, _, _, analysis = asyncio.run(
        analyze(
            {
                "package.json": manifest(
                    {
                        "preinstall": "node scripts/require.cjs",
                        "postinstall": "node scripts/import.mjs",
                    }
                ),
                "scripts/require.cjs": (
                    'const common = require("./common");\nconst pkg = require("./pkg");\n'
                ).encode(),
                "scripts/common.cjs": b"// inert suffix resolution\n",
                "scripts/pkg/index.js": b"// inert index resolution\n",
                "scripts/import.mjs": (
                    'import value from "./esm.js";\n'
                    'const lazy = import("./lazy.js");\n'
                    'export { value } from "./esm.js";\n'
                ).encode(),
                "scripts/esm.js": b"// inert exact ESM path\n",
                "scripts/lazy.js": b"// inert literal dynamic import\n",
            }
        )
    )
    assert fetched_paths(snapshot) == {
        "package.json",
        "scripts/require.cjs",
        "scripts/common.cjs",
        "scripts/pkg/index.js",
        "scripts/import.mjs",
        "scripts/esm.js",
        "scripts/lazy.js",
    }
    assert not analysis.errors
    kinds = [edge.kind for edge in analysis.relationships]
    assert kinds.count("local_require") == 2
    assert kinds.count("local_import") == 1  # Repeated static edges are deduplicated.
    assert kinds.count("local_dynamic_import_literal") == 1


def test_unsupported_esm_suffix_does_not_fabricate_commonjs_resolution() -> None:
    snapshot, _, _, analysis = asyncio.run(
        analyze(
            {
                "package.json": manifest({"prepare": "node scripts/main.mjs"}),
                "scripts/main.mjs": b'import value from "./helper";\n',
                "scripts/helper.js": b"// must not be treated as an exact ESM specifier\n",
            }
        )
    )
    assert "absent or has unresolved suffix" in error_text(analysis)
    helper_id = snapshot.file_id("target", "scripts/helper.js")
    assert snapshot.require_file(helper_id).record.fetch_status is FetchStatus.PENDING
    assert helper_id not in analysis.required_file_ids
    assert fetched_paths(snapshot) == {"package.json", "scripts/main.mjs"}


def test_computed_and_external_imports_stay_visible_gaps() -> None:
    _, _, _, analysis = asyncio.run(
        analyze(
            {
                "package.json": manifest({"prepare": "node scripts/main.cjs"}),
                "scripts/main.cjs": (
                    'const pkg = require("some-package");\n'
                    'const dynamic = require("./" + process.env.NAME);\n'
                    "import(variable);\n"
                ).encode(),
            }
        )
    )
    message = error_text(analysis)
    assert "package or external import" in message
    assert "computed import/require" in message
    assert not any(edge.kind.startswith("local_") for edge in analysis.relationships)


@pytest.mark.parametrize(
    "command",
    [
        "node scripts/helper.cjs && node scripts/other.cjs",
        "node -e \"console.log('inert')\"",
        "npx some-package",
        "node /tmp/outside.cjs",
        "node ../outside.cjs",
        "node $(outside)",
    ],
)
def test_unsupported_commands_and_host_paths_are_not_followed(command: str) -> None:
    snapshot, _, _, analysis = asyncio.run(
        analyze(
            {
                "package.json": manifest({"prepare": command}),
                "scripts/helper.cjs": b"// never fetched through an unsupported chain\n",
                "scripts/other.cjs": b"// never fetched\n",
            }
        )
    )
    assert analysis.errors
    assert analysis.relationships == ()
    assert fetched_paths(snapshot) == {"package.json"}


def test_relative_import_cannot_escape_tree_or_read_host_paths() -> None:
    snapshot, _, _, analysis = asyncio.run(
        analyze(
            {
                "package.json": manifest({"prepare": "node scripts/main.cjs"}),
                "scripts/main.cjs": (
                    'const outside = require("../../outside.cjs");\n'
                    'const absolute = require("/etc/passwd");\n'
                    'const windows = require("C:/outside.js");\n'
                ).encode(),
                "outside.cjs": b"// inside the tree but behind a root-escaping specifier\n",
            }
        )
    )
    assert analysis.errors
    assert not any(edge.kind.startswith("local_") for edge in analysis.relationships)
    assert fetched_paths(snapshot) == {"package.json", "scripts/main.cjs"}
    assert snapshot.file_id("target", "outside.cjs") not in analysis.required_file_ids


def test_cycles_terminate_without_hiding_the_cycle_edges() -> None:
    _, _, _, analysis = asyncio.run(
        analyze(
            {
                "package.json": manifest({"prepare": "node main.cjs"}),
                "main.cjs": b'require("./a");\n',
                "a.js": b'require("./main.cjs");\n',
            }
        )
    )
    assert len(analysis.relationships) == 3
    assert not analysis.errors
    assert len({edge.relationship_id for edge in analysis.relationships}) == 3


def test_depth_cap_is_a_gap_and_file_cap_preserves_unread_required_id() -> None:
    files = {
        "package.json": manifest({"prepare": "node main.cjs"}),
        "main.cjs": b'require("./a");\n',
        "a.js": b'require("./b");\n',
        "b.js": b'require("./c");\n',
        "c.js": b"// inert deepest file\n",
    }
    _, _, _, depth = asyncio.run(analyze(files, max_depth=1))
    assert "depth limit" in error_text(depth)
    snapshot, _, _, capped = asyncio.run(analyze(files, max_helper_files=1))
    a_id = snapshot.file_id("target", "a.js")
    assert a_id in capped.required_file_ids
    assert snapshot.require_file(a_id).record.fetch_status is FetchStatus.PENDING
    assert "file cap" in error_text(capped)
    assert fetched_paths(snapshot) == {"package.json", "main.cjs"}


def test_import_outside_bounded_excerpt_remains_unresolved() -> None:
    snapshot, _, _, analysis = asyncio.run(
        analyze(
            {
                "package.json": manifest({"prepare": "node main.cjs"}),
                "main.cjs": (b"// bounded excerpt filler\n" * 179 + b'require("./deep");\n'),
                "deep.js": b"// unread because the caller edge was not delivered\n",
            }
        )
    )
    assert "outside the bounded caller excerpt" in error_text(analysis)
    assert not any(edge.kind == "local_require" for edge in analysis.relationships)
    deep_id = snapshot.file_id("target", "deep.js")
    assert snapshot.require_file(deep_id).record.fetch_status is FetchStatus.PENDING


def test_symlink_helper_is_required_but_never_dereferenced() -> None:
    snapshot, ledger, budget = context(
        {
            "package.json": manifest({"prepare": "node helper.js"}),
            "helper.js": b"../outside-is-not-read",
        }
    )
    helper_id = snapshot.file_id("target", "helper.js")
    stored = snapshot.require_file(helper_id)
    stored.record = stored.record.model_copy(update={"mode": GitMode.SYMLINK})
    analysis = asyncio.run(NpmSetupAnalyzer().analyze(review_input(), snapshot, ledger, budget))
    assert helper_id in analysis.required_file_ids
    assert analysis.errors and analysis.relationships == ()
    assert stored.record.fetch_status is FetchStatus.SKIPPED
    assert len(snapshot.source.calls) == 1  # Only package.json was fetched.


def test_unchanged_hook_changed_helper_integrates_with_existing_s06_comparison() -> None:
    def files(side: str) -> dict[str, bytes]:
        root = COMPARE_FIXTURE / side
        return {
            path: (root / path).read_bytes() for path in ("package.json", "scripts/check-node.js")
        }

    snapshot, ledger, _, analysis = asyncio.run(
        analyze(files("target"), baseline=files("baseline"))
    )
    assert not analysis.errors
    assert len(analysis.relationships) == 1
    comparison = asyncio.run(
        materialize_comparison(
            snapshot,
            ledger,
            compare_inventories(snapshot),
            {"package.json", "scripts/check-node.js"},
        )
    )
    assert comparison.complete
    by_path = {entry.path: entry for entry in comparison.entries}
    assert by_path["package.json"].change == "unchanged"
    assert by_path["scripts/check-node.js"].change == "modified"
    edge = analysis.relationships[0]
    target_helper = ledger.require(edge.callee_evidence_id)
    assert "requiredMajor = 22" in target_helper.representation
    assert target_helper.side.value == "target"
    assert (
        "requiredMajor = 20"
        in ledger.require(by_path["scripts/check-node.js"].baseline_evidence_ids[0]).representation
    )
