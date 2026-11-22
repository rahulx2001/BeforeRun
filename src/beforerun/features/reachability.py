"""Bounded static npm command/import relationships over admitted snapshot source."""

from __future__ import annotations

import json
import posixpath
import re
import shlex
from dataclasses import dataclass

from beforerun.features.budgets import Budget
from beforerun.features.contracts import (
    EncodingStatus,
    ErrorCode,
    ErrorRecord,
    Evidence,
    FetchStatus,
    Relationship,
    RelationshipSupport,
    RevisionSide,
)
from beforerun.features.evidence import EvidenceLedger
from beforerun.features.snapshot import Snapshot, issued_id

_MAX_SEED_EVIDENCE = 48
_MAX_GAPS = 64
_REQUIRE = re.compile(r"\brequire\s*\(\s*(['\"])([^'\"\r\n]+)\1\s*\)")
_IMPORT_CALL = re.compile(r"\bimport\s*\(\s*(['\"])([^'\"\r\n]+)\1\s*\)")
_STATIC_IMPORT = re.compile(
    r"\b(?:import|export)\s+(?:[^;\r\n]*?\s+from\s+)?(['\"])([^'\"\r\n]+)\1"
)
_DYNAMIC_CALL = re.compile(r"\b(?:require|import)\s*\(")
_SHELL_SYNTAX = re.compile(r"[;&|`$<>\r\n]")


@dataclass(frozen=True, slots=True)
class CommandOrigin:
    """A literal command attached to trusted package-manifest evidence."""

    label: str
    command: str
    caller_file_id: str
    caller_evidence_id: str


@dataclass(frozen=True, slots=True)
class ReachabilityResult:
    evidence_by_file: dict[str, str]
    relationships: tuple[Relationship, ...]
    required_file_ids: frozenset[str]
    seed_evidence_ids: tuple[str, ...]
    errors: tuple[ErrorRecord, ...]
    assumptions: tuple[str, ...]


class _ResolutionError(ValueError):
    pass


def _normalize_source_path(
    specifier: str,
    base_directory: str,
    *,
    relative_import: bool,
) -> str:
    if (
        not specifier
        or len(specifier) > 512
        or "\\" in specifier
        or any(ord(character) < 32 or ord(character) == 127 for character in specifier)
    ):
        raise _ResolutionError("A local source specifier has an unsupported form.")
    if specifier.startswith("/") or re.match(r"^[A-Za-z]:", specifier):
        raise _ResolutionError("Absolute and host filesystem paths are not admitted.")
    if relative_import and not specifier.startswith(("./", "../")):
        raise _ResolutionError("A package or external import is outside local-source scope.")
    normalized = posixpath.normpath(posixpath.join(base_directory, specifier))
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        raise _ResolutionError("A local source specifier escapes the pinned repository tree.")
    return normalized


def _resolve_local_file(
    snapshot: Snapshot,
    specifier: str,
    base_directory: str,
    *,
    relative_import: bool,
    suffix_resolution: bool,
) -> str:
    path = _normalize_source_path(
        specifier,
        base_directory,
        relative_import=relative_import,
    )
    candidates = [path]
    if suffix_resolution and not posixpath.splitext(path)[1]:
        candidates.extend(path + suffix for suffix in (".js", ".cjs", ".mjs", ".json"))
        candidates.extend(
            posixpath.join(path, "index" + suffix) for suffix in (".js", ".cjs", ".mjs")
        )
    for candidate in candidates:
        file_id = snapshot.file_id(RevisionSide.TARGET, candidate)
        if file_id is not None:
            return file_id
    raise _ResolutionError("A referenced local file is absent or has unresolved suffix semantics.")


def manifest_command_is_excerpted(command: str, evidence: Evidence) -> bool:
    """Recognize raw or JSON-string-escaped command text without decoding arbitrary data."""

    json_content = json.dumps(command, ensure_ascii=False)[1:-1]
    return command in evidence.representation or json_content in evidence.representation


def _covered_by_evidence(evidence: Evidence, line: int, literal: str) -> bool:
    return (
        evidence.span.first_line <= line <= evidence.span.last_line
        and literal in evidence.representation
    )


async def trace_commands(
    snapshot: Snapshot,
    ledger: EvidenceLedger,
    budget: Budget,
    *,
    origins: tuple[CommandOrigin, ...],
    scripts: dict[str, str],
    analyzer_version: str,
    evidence_by_file: dict[str, str] | None = None,
    required_file_ids: frozenset[str] = frozenset(),
    seed_evidence_ids: tuple[str, ...] = (),
    entry_evidence_ids: frozenset[str] = frozenset(),
    max_depth: int = 4,
    max_helper_files: int = 24,
    max_relationships: int = 64,
) -> ReachabilityResult:
    """Trace the declared subset without a shell, parser execution, or host path access."""

    if not 0 <= max_depth <= 8:
        raise ValueError("max_depth must be between 0 and 8")
    if not 1 <= max_helper_files <= 64:
        raise ValueError("max_helper_files must be between 1 and 64")
    if not 1 <= max_relationships <= 128:
        raise ValueError("max_relationships must be between 1 and 128")

    evidence_by_file = dict(evidence_by_file or {})
    required = set(required_file_ids)
    seeds = list(dict.fromkeys(seed_evidence_ids))
    relationships: list[Relationship] = []
    relationship_keys: set[tuple[str, str, str]] = set()
    errors: list[ErrorRecord] = []
    error_messages: set[str] = set()
    scanned: set[str] = set()
    visited_commands: set[tuple[str, str]] = set()
    helper_ids: set[str] = set()

    def gap(message: str) -> None:
        if message not in error_messages and len(errors) < _MAX_GAPS:
            error_messages.add(message)
            errors.append(ErrorRecord(code=ErrorCode.SOURCE_LIMIT, message=message))

    def relationship(
        caller: Evidence,
        callee: Evidence,
        kind: str,
        support: RelationshipSupport,
        assumptions: tuple[str, ...],
    ) -> None:
        key = (caller.evidence_id, callee.evidence_id, kind)
        if key in relationship_keys:
            return
        if len(relationships) >= max_relationships:
            gap("The static relationship cap left additional local edges unresolved.")
            return
        relationship_keys.add(key)
        relationships.append(
            Relationship(
                relationship_id=issued_id("rel"),
                caller_evidence_id=caller.evidence_id,
                callee_evidence_id=callee.evidence_id,
                kind=kind,
                support=support,
                assumptions=assumptions,
                analyzer_version=analyzer_version,
            )
        )

    async def load_file(file_id: str) -> Evidence | None:
        budget.check()
        existing = evidence_by_file.get(file_id)
        if existing is not None:
            return ledger.require(existing)
        required.add(file_id)
        if len(helper_ids) >= max_helper_files:
            gap("The reachable-helper file cap left a required local file unread.")
            return None
        helper_ids.add(file_id)
        record = await snapshot.admit_file(file_id, required=False)
        budget.check()
        if (
            record.fetch_status is not FetchStatus.FETCHED
            or record.encoding_status is not EncodingStatus.UTF8
            or snapshot.require_file(file_id).text is None
        ):
            gap("A reachable local file could not be read as admitted UTF-8 source.")
            return None
        evidence = ledger.issue(file_id)
        evidence_by_file[file_id] = evidence.evidence_id
        return evidence

    async def scan_imports(file_id: str, evidence: Evidence, depth: int) -> None:
        if file_id in scanned:
            return
        if depth > max_depth:
            gap("The static import depth limit left deeper local relationships unresolved.")
            return
        scanned.add(file_id)
        stored = snapshot.require_file(file_id)
        if stored.text is None:
            return
        matches: list[tuple[int, str, str, bool, str]] = []
        literal_spans: list[tuple[int, int]] = []
        for pattern, kind, suffixes in (
            (_REQUIRE, "local_require", True),
            (_IMPORT_CALL, "local_dynamic_import_literal", False),
            (_STATIC_IMPORT, "local_import", False),
        ):
            for match in pattern.finditer(stored.text):
                specifier = match.group(2)
                line = stored.text.count("\n", 0, match.start()) + 1
                matches.append((line, specifier, kind, suffixes, match.group(0)))
                literal_spans.append(match.span())
        for line, specifier, kind, suffixes, matched_text in sorted(matches):
            budget.check()
            if not _covered_by_evidence(evidence, line, matched_text):
                gap("A local import outside the bounded caller excerpt remains unresolved.")
                continue
            try:
                callee_id = _resolve_local_file(
                    snapshot,
                    specifier,
                    posixpath.dirname(stored.record.path),
                    relative_import=True,
                    suffix_resolution=suffixes,
                )
            except _ResolutionError as error:
                gap(str(error))
                continue
            if not _covered_by_evidence(evidence, line, specifier):
                gap("A local import outside the bounded caller excerpt remains unresolved.")
                continue
            callee = await load_file(callee_id)
            if callee is None:
                continue
            relationship(
                evidence,
                callee,
                kind,
                RelationshipSupport.INFERRED,
                (
                    "A literal relative import/require match is a static candidate edge, not "
                    "proof that a runtime branch executed.",
                ),
            )
            await scan_imports(callee_id, callee, depth + 1)
        for match in _DYNAMIC_CALL.finditer(stored.text):
            if not any(start <= match.start() < stop for start, stop in literal_spans):
                gap("A computed import/require has unresolved runtime-dependent behavior.")
                break

    async def visit_command(origin: CommandOrigin, depth: int) -> None:
        budget.check()
        if depth > max_depth:
            gap("The npm command nesting limit left a local command unresolved.")
            return
        visit_key = (origin.caller_file_id, origin.command)
        if visit_key in visited_commands:
            return
        visited_commands.add(visit_key)
        if _SHELL_SYNTAX.search(origin.command):
            gap("Shell chains, expansion, substitution, and redirection remain unresolved.")
            return
        try:
            words = shlex.split(origin.command, comments=False, posix=True)
        except ValueError:
            gap("A lifecycle command has unsupported shell quoting.")
            return
        if len(words) == 3 and words[:2] == ["npm", "run"]:
            script_name = words[2]
            nested = scripts.get(script_name)
            if nested is None:
                gap("A nested npm run reference names a missing or unsupported script.")
                return
            caller = ledger.require(origin.caller_evidence_id)
            stored = snapshot.require_file(origin.caller_file_id)
            if stored.text is None or not manifest_command_is_excerpted(nested, caller):
                gap("A nested npm script is outside the bounded manifest evidence excerpt.")
                return
            relationship(
                caller,
                caller,
                "nested_npm_run",
                RelationshipSupport.INFERRED,
                ("npm run is a manifest relationship only; npm was never invoked.",),
            )
            await visit_command(
                CommandOrigin(
                    label="nested npm script",
                    command=nested,
                    caller_file_id=origin.caller_file_id,
                    caller_evidence_id=origin.caller_evidence_id,
                ),
                depth + 1,
            )
            return
        if len(words) != 2 or words[0] != "node":
            gap("A non-literal-node, package-bin, inline, or native command remains unresolved.")
            return
        caller = ledger.require(origin.caller_evidence_id)
        try:
            callee_id = _resolve_local_file(
                snapshot,
                words[1],
                "",
                relative_import=False,
                suffix_resolution=False,
            )
        except _ResolutionError as error:
            gap(str(error))
            return
        callee = await load_file(callee_id)
        if callee is None:
            return
        support = (
            RelationshipSupport.SUPPORTED
            if origin.caller_evidence_id in entry_evidence_ids
            else RelationshipSupport.INFERRED
        )
        relationship(
            caller,
            callee,
            "npm_lifecycle_local_command",
            support,
            (
                "The literal local command is connected to the declared npm context; runtime "
                "control flow, environment, and npm configuration remain separate assumptions.",
            ),
        )
        if callee.evidence_id not in seeds and len(seeds) < _MAX_SEED_EVIDENCE:
            seeds.append(callee.evidence_id)
        await scan_imports(callee_id, callee, depth)

    for origin in origins:
        await visit_command(origin, 0)

    return ReachabilityResult(
        evidence_by_file=evidence_by_file,
        relationships=tuple(relationships),
        required_file_ids=frozenset(required),
        seed_evidence_ids=tuple(seeds[:_MAX_SEED_EVIDENCE]),
        errors=tuple(errors),
        assumptions=(
            "Only literal local node commands, nested npm run references, and supported relative "
            "imports/requires were followed.",
            "Regex-derived import edges are candidate static relationships, not runtime proof.",
            "Computed/dynamic code, arbitrary shell, package binaries, custom loaders, native "
            "actions, and external packages remain unresolved where encountered.",
        ),
    )
