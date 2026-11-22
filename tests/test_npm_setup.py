from __future__ import annotations

import asyncio
import socket
import subprocess

import pytest
from s05_helpers import analyze, error_text, evidence_paths, fixture_files, manifest

from beforerun.features.contracts import (
    CandidateReport,
    CommandContext,
    Completion,
    FetchStatus,
    RelationshipSupport,
    ReviewInput,
    StopReason,
)
from beforerun.features.investigator import InvestigationOutcome
from beforerun.features.npm_setup import (
    NPM_CONDITIONAL_ORDER,
    NPM_DEFAULT_NATIVE_COMMAND,
    NPM_LIFECYCLE_ORDER,
    NPM_SEMANTICS_VERSION,
)
from beforerun.features.report import build_report
from beforerun.features.validate import ValidationContext


@pytest.fixture(autouse=True)
def forbid_network_and_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("S05 tests must not perform networking or launch processes.")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)


def test_declared_npm_contract_and_all_root_lifecycle_names_in_order() -> None:
    ordered = NPM_LIFECYCLE_ORDER + NPM_CONDITIONAL_ORDER
    scripts = {name: f"node scripts/{index:02d}.cjs" for index, name in enumerate(ordered)}
    files = {"package.json": manifest(scripts)}
    files.update(
        {
            f"scripts/{index:02d}.cjs": f"// inert {name}\n".encode()
            for index, name in enumerate(ordered)
        }
    )
    snapshot, ledger, _, analysis = asyncio.run(analyze(files))
    assert analysis.supported and not analysis.errors
    assert NPM_SEMANTICS_VERSION == "npm 11.21.3"
    assert ordered[-1] == "dependencies"
    callee_paths = [
        snapshot.require_file(ledger.require(edge.callee_evidence_id).file_id).record.path
        for edge in analysis.relationships
    ]
    assert callee_paths == [f"scripts/{index:02d}.cjs" for index in range(len(ordered))]
    assert all(edge.support is RelationshipSupport.SUPPORTED for edge in analysis.relationships)
    assert len(analysis.seed_evidence_ids) == len(ordered) + 1


@pytest.mark.parametrize("script_name", ["install", "preinstall"])
def test_explicit_install_scripts_suppress_native_default(script_name: str) -> None:
    snapshot, _, _, analysis = asyncio.run(
        analyze(
            {
                "package.json": manifest({script_name: "node scripts/check.cjs"}),
                "scripts/check.cjs": b"// inert\n",
                "binding.gyp": b"{}",
            }
        )
    )
    binding_id = snapshot.file_id("target", "binding.gyp")
    assert binding_id not in analysis.required_file_ids
    assert snapshot.require_file(binding_id).record.fetch_status is FetchStatus.PENDING
    assert NPM_DEFAULT_NATIVE_COMMAND not in error_text(analysis)
    assert not analysis.errors


def test_binding_without_install_and_preinstall_keeps_native_gap() -> None:
    snapshot, _, _, analysis = asyncio.run(
        analyze(
            {
                "package.json": manifest({"prepare": "node scripts/check.cjs"}),
                "scripts/check.cjs": b"// inert\n",
                "binding.gyp": b"{}",
            }
        )
    )
    binding_id = snapshot.file_id("target", "binding.gyp")
    assert binding_id in analysis.required_file_ids
    assert snapshot.require_file(binding_id).record.fetch_status is FetchStatus.PENDING
    assert NPM_DEFAULT_NATIVE_COMMAND in error_text(analysis)
    assert analysis.seed_evidence_ids  # Other bounded source remains available.


def test_ignore_scripts_suppresses_hooks_without_reading_home_or_helper() -> None:
    secret = "fixture-secret-must-not-be-exported"
    snapshot, _, _, analysis = asyncio.run(
        analyze(
            {
                "package.json": manifest({"prepare": "node scripts/check.cjs"}),
                "scripts/check.cjs": b"// inert\n",
                ".npmrc": (
                    "ignore-scripts=true\nregistry=https://registry.invalid/\n"
                    f"_authToken={secret}\n"
                ).encode(),
            }
        )
    )
    helper_id = snapshot.file_id("target", "scripts/check.cjs")
    assert helper_id not in analysis.required_file_ids
    assert snapshot.require_file(helper_id).record.fetch_status is FetchStatus.PENDING
    assert analysis.relationships == ()
    assert secret not in " ".join(analysis.assumptions)
    assert any("ignore-scripts=true" in item for item in analysis.assumptions)
    assert any("registry" in item for item in analysis.assumptions)


def test_review_only_does_not_claim_install_time_execution() -> None:
    snapshot, _, _, analysis = asyncio.run(
        analyze(
            {
                "package.json": manifest({"prepare": "node scripts/check.cjs"}),
                "scripts/check.cjs": b"// inert\n",
                "binding.gyp": b"{}",
            },
            command=CommandContext.REVIEW_ONLY,
        )
    )
    assert analysis.relationships == ()
    assert not analysis.errors
    assert snapshot.file_id("target", "binding.gyp") not in analysis.required_file_ids
    assert any("no particular install-time" in item for item in analysis.assumptions)


@pytest.mark.parametrize(
    "package",
    [b'{"scripts": []}', b"not json", b"[]", b'{"scripts":{"prepare": 7}}'],
)
def test_malformed_manifest_fails_unsupported_not_clean(package: bytes) -> None:
    _, _, _, analysis = asyncio.run(analyze({"package.json": package}))
    assert not analysis.supported
    assert analysis.errors
    assert analysis.relationships == ()


def test_missing_manifest_is_unsupported() -> None:
    _, _, _, analysis = asyncio.run(analyze({"README.md": b"inert"}))
    assert not analysis.supported
    assert not analysis.seed_evidence_ids
    assert "no root package.json" in error_text(analysis)


def test_review_only_without_package_json_reads_root_setup_files() -> None:
    snapshot, ledger, _, analysis = asyncio.run(
        analyze(
            {
                "requirements.txt": b"requests==2.32.3\n",
                "Makefile": b"install:\n\tpip install -r requirements.txt\n",
                "README.md": b"do not treat this as a setup file\n",
            },
            command=CommandContext.REVIEW_ONLY,
        )
    )
    assert analysis.supported
    assert not analysis.errors
    assert evidence_paths(snapshot, ledger, analysis) == {"requirements.txt", "Makefile"}
    assert any("No root package.json" in item for item in analysis.assumptions)


def test_review_only_excerpt_does_not_require_the_unread_tail() -> None:
    snapshot, _, _, analysis = asyncio.run(
        analyze(
            {
                "requirements.txt": b"requests==2.32.3\n",
                "requirements-lock.txt": b"pkg==1\n" * 200,
            },
            command=CommandContext.REVIEW_ONLY,
        )
    )
    assert snapshot.file_id("target", "requirements.txt") in analysis.required_file_ids
    assert snapshot.file_id("target", "requirements-lock.txt") not in analysis.required_file_ids
    assert any("requirements-lock.txt" in item for item in analysis.assumptions)


def test_npm_install_without_package_json_stays_unsupported() -> None:
    _, _, _, analysis = asyncio.run(
        analyze(
            {"requirements.txt": b"requests==2.32.3\n"},
            command=CommandContext.NPM_INSTALL,
        )
    )
    assert not analysis.supported
    assert "no root package.json" in error_text(analysis)


def test_custom_shell_and_unreadable_npmrc_remain_explicit_gaps() -> None:
    snapshot, _, _, analysis = asyncio.run(
        analyze(
            {
                "package.json": manifest({"prepare": "node scripts/check.cjs"}),
                "scripts/check.cjs": b"// inert\n",
                ".npmrc": b"script-shell=/bin/custom-shell\n",
                "binding.gyp": b"{}",
            }
        )
    )
    assert analysis.supported
    assert analysis.relationships == ()
    assert "custom npm script-shell" in error_text(analysis)
    assert snapshot.file_id("target", ".npmrc") in analysis.required_file_ids
    assert snapshot.file_id("target", "binding.gyp") in analysis.required_file_ids
    assert NPM_DEFAULT_NATIVE_COMMAND in error_text(analysis)
    assert snapshot.file_id("target", "scripts/check.cjs") not in analysis.required_file_ids


def test_non_lifecycle_scripts_do_not_reach_uncalled_helpers() -> None:
    snapshot, _, _, analysis = asyncio.run(
        analyze(
            {
                "package.json": manifest(
                    {
                        "test": "node scripts/test.cjs",
                        "build": "node scripts/build.cjs",
                    }
                ),
                "scripts/test.cjs": b"fetch('https://example.invalid')\n",
                "scripts/build.cjs": b"process.env.API_KEY\n",
            }
        )
    )
    assert analysis.relationships == ()
    assert not analysis.errors
    assert len(analysis.seed_evidence_ids) == 1
    assert analysis.signals == ()
    for path in ("scripts/test.cjs", "scripts/build.cjs"):
        file_id = snapshot.file_id("target", path)
        assert snapshot.require_file(file_id).record.fetch_status is FetchStatus.PENDING


def test_benign_annotated_fixture_is_source_relation_not_behavior_verdict() -> None:
    snapshot, ledger, _, analysis = asyncio.run(analyze(fixture_files("benign")))
    assert analysis.supported and not analysis.errors
    assert len(analysis.relationships) == 1
    edge = analysis.relationships[0]
    assert edge.support is RelationshipSupport.SUPPORTED
    callee = ledger.require(edge.callee_evidence_id)
    assert snapshot.require_file(callee.file_id).record.path == "scripts/check-node.cjs"
    assert "not runtime" in " ".join(analysis.assumptions).lower() or any(
        "runtime" in item for item in edge.assumptions
    )


def test_reviewer_targeting_text_is_a_lead_not_an_instruction() -> None:
    _, _, _, analysis = asyncio.run(analyze(fixture_files("reviewer_targeting")))
    assert len(analysis.relationships) == 1
    assert any(signal.rule_id == "reviewer_targeting_text" for signal in analysis.signals)
    signal = next(
        signal for signal in analysis.signals if signal.rule_id == "reviewer_targeting_text"
    )
    assert signal.evidence_id or signal.pointer
    assert "never authority" in signal.reason
    assert "Ignore the instructions" not in " ".join(analysis.assumptions)
    assert not hasattr(analysis, "assessment")


def test_unsupported_inline_fixture_remains_partial_even_if_model_says_benign() -> None:
    snapshot, ledger, budget, analysis = asyncio.run(analyze(fixture_files("unsupported_inline")))
    assert analysis.supported and analysis.errors
    assert analysis.relationships == ()
    assert "inline" in error_text(analysis)
    # The checked completion layer, not the analyzer, combines an empty model proposal and gaps.
    ledger.deliver(analysis.seed_evidence_ids, 1)
    candidate = CandidateReport(
        assessment="benign",
        summary="Inert adapter fixture proposal, not a detection-quality result.",
        findings=(),
        stop_reason=StopReason.FINISHED,
    )
    outcome = InvestigationOutcome(candidate, StopReason.FINISHED, (), ())
    validation = ValidationContext(
        ReviewInput(
            repository_url="https://github.com/example/inert-fixture",
            command_context=CommandContext.NPM_INSTALL,
        ),
        ledger,
        analysis.relationships,
        analysis.entry_evidence_ids,
    )
    report = build_report(
        validation,
        outcome,
        budget,
        required_file_ids=analysis.required_file_ids,
        assumptions=analysis.assumptions,
        analysis_errors=analysis.errors,
        unsupported=not analysis.supported,
    )
    assert report.completion is Completion.PARTIAL
    assert report.assessment.value == "undetermined"
    assert report.coverage.model_shown_files == 1
    assert (
        snapshot.require_file(snapshot.file_id("target", "package.json")).record.fetch_status
        is FetchStatus.FETCHED
    )
