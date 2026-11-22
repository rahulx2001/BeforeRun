"""npm 11.21.3 root install-time setup detection for trusted snapshot files."""

from __future__ import annotations

import json
from dataclasses import dataclass

from beforerun.features.budgets import Budget
from beforerun.features.contracts import (
    CommandContext,
    EncodingStatus,
    ErrorCode,
    ErrorRecord,
    FetchStatus,
    ReviewInput,
    RevisionSide,
)
from beforerun.features.evidence import EvidenceLedger
from beforerun.features.pipeline import AnalysisContext
from beforerun.features.reachability import (
    CommandOrigin,
    manifest_command_is_excerpted,
    trace_commands,
)
from beforerun.features.signals import collect_signals
from beforerun.features.snapshot import Snapshot

NPM_SEMANTICS_VERSION = "npm 11.21.3"
NPM_LIFECYCLE_ORDER = (
    "preinstall",
    "install",
    "postinstall",
    "prepublish",
    "preprepare",
    "prepare",
    "postprepare",
)
NPM_CONDITIONAL_ORDER = ("dependencies",)
NPM_DEFAULT_NATIVE_COMMAND = "node-gyp rebuild"


def _issued_excerpt_covers_file(ledger: EvidenceLedger, file_id: str, evidence_id: str) -> bool:
    """True only when the issued excerpt is the whole admitted file."""
    evidence = ledger.require(evidence_id)
    stored = ledger.snapshot.require_file(file_id)
    lines = (stored.text or "").splitlines() or [""]
    return (
        not ledger.truncated.get(evidence_id)
        and evidence.span.first_line == 1
        and evidence.span.first_column == 1
        and evidence.span.last_line == len(lines)
        and evidence.span.last_column == len(lines[-1].encode()) + 1
    )


# Root files a review-only pass can inspect when the repository is not an npm project.
_ROOT_SETUP_PATHS = (
    "pyproject.toml",
    "requirements.txt",
    "requirements-lock.txt",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    "Makefile",
    "Dockerfile",
    "docker-compose.yml",
)
_REGISTRY_CONFIG_KEYS = frozenset(
    {
        "registry",
        "strict-ssl",
        "cafile",
        "cert",
        "key",
        "proxy",
        "https-proxy",
        "noproxy",
        "fetch-retries",
        "fetch-retry-factor",
        "fetch-retry-maxtimeout",
        "fetch-retry-mintimeout",
        "fetch-timeout",
    }
)


@dataclass(frozen=True, slots=True)
class _NpmConfig:
    ignore_scripts: bool
    unknown_ignore_scripts: bool
    custom_script_shell: bool
    interpolation: bool
    node_options: bool
    relevant_keys: tuple[str, ...]


def _parse_npmrc(text: str) -> _NpmConfig:
    """Parse the small project-file subset without user/global config or interpolation."""

    values: dict[str, str] = {}
    relevant: list[str] = []
    for raw_line in text.splitlines()[:256]:
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().lower()
        if not key:
            continue
        values[key] = value.strip()
        relevant.append(key)
    ignore_value = values.get("ignore-scripts", "").lower()
    ignore_scripts = ignore_value in {"true", "1", "yes"}
    unknown_ignore = "ignore-scripts" in values and ignore_value not in {
        "true",
        "1",
        "yes",
        "false",
        "0",
        "no",
    }
    return _NpmConfig(
        ignore_scripts=ignore_scripts,
        unknown_ignore_scripts=unknown_ignore,
        custom_script_shell="script-shell" in values,
        interpolation=any("${" in value for value in values.values()),
        node_options=bool(values.get("node-options")),
        relevant_keys=tuple(sorted(set(relevant))[:64]),
    )


class NpmSetupAnalyzer:
    """Discover only declared root npm setup behavior, never execute submitted source."""

    name = "npm-root-static"

    def __init__(self, *, max_depth: int = 4, max_helper_files: int = 24) -> None:
        if not 0 <= max_depth <= 8:
            raise ValueError("max_depth must be between 0 and 8")
        if not 1 <= max_helper_files <= 64:
            raise ValueError("max_helper_files must be between 1 and 64")
        self.max_depth = max_depth
        self.max_helper_files = max_helper_files

    async def analyze(
        self,
        intake: ReviewInput,
        snapshot: Snapshot,
        ledger: EvidenceLedger,
        budget: Budget,
    ) -> AnalysisContext:
        assumptions = [
            f"Lifecycle discovery uses {NPM_SEMANTICS_VERSION}; it does not describe other "
            "npm major versions.",
            "Only the pinned project .npmrc was inspected; user/global npm configuration and "
            "process environment were not read.",
            "No package manager, submitted module, shell, native tool, or dependency was executed.",
            "Registry/dependency artifacts are separate sources; registry configuration does not "
            "certify them, and user credentials were not read or exported.",
        ]
        errors: list[ErrorRecord] = []
        error_messages: set[str] = set()

        def gap(message: str, code: ErrorCode = ErrorCode.SOURCE_LIMIT) -> None:
            if message not in error_messages:
                error_messages.add(message)
                errors.append(ErrorRecord(code=code, message=message))

        required: set[str] = set()
        evidence_by_file: dict[str, str] = {}

        async def load(file_id: str) -> bool:
            budget.check()
            required.add(file_id)
            record = await snapshot.admit_file(file_id, required=False)
            budget.check()
            if (
                record.fetch_status is not FetchStatus.FETCHED
                or record.encoding_status is not EncodingStatus.UTF8
                or snapshot.require_file(file_id).text is None
            ):
                return False
            evidence = ledger.issue(file_id)
            evidence_by_file[file_id] = evidence.evidence_id
            return True

        manifest_id = snapshot.file_id(RevisionSide.TARGET, "package.json")
        if manifest_id is None:
            if intake.command_context is CommandContext.REVIEW_ONLY:
                seeds: list[str] = []
                for path in _ROOT_SETUP_PATHS:
                    file_id = snapshot.file_id(RevisionSide.TARGET, path)
                    if file_id is None:
                        continue
                    if await load(file_id):
                        seeds.append(evidence_by_file[file_id])
                    else:
                        gap(f"{path} could not be read as admitted UTF-8 source.")
                if seeds:
                    notes = [
                        "No root package.json is present. This review reads the pinned "
                        "root Python, Make, and container setup files only.",
                        "No installer, shell, or container build was executed.",
                        "npm install behavior is not established for this repository.",
                    ]
                    for file_id, evidence_id in evidence_by_file.items():
                        if _issued_excerpt_covers_file(ledger, file_id, evidence_id):
                            continue
                        required.discard(file_id)
                        path = snapshot.require_file(file_id).record.path
                        notes.append(
                            f"{path} is longer than the admitted excerpt, so its unread "
                            "tail is outside the completed scope."
                        )
                    return AnalysisContext(
                        assumptions=tuple(notes),
                        required_file_ids=frozenset(required),
                        seed_evidence_ids=tuple(seeds),
                        entry_evidence_ids=frozenset(seeds),
                        supported=True,
                        errors=tuple(errors),
                    )
            gap("The pinned target has no root package.json for npm setup analysis.")
            return AnalysisContext(
                assumptions=tuple(assumptions),
                supported=False,
                errors=tuple(errors),
            )
        if not await load(manifest_id):
            gap("The root package.json could not be read as admitted UTF-8 source.")
            return AnalysisContext(
                assumptions=tuple(assumptions),
                required_file_ids=frozenset(required),
                supported=False,
                errors=tuple(errors),
            )
        manifest_evidence_id = evidence_by_file[manifest_id]
        manifest_evidence = ledger.require(manifest_evidence_id)
        manifest_text = snapshot.require_file(manifest_id).text
        assert manifest_text is not None
        try:
            manifest = json.loads(manifest_text)
        except (json.JSONDecodeError, UnicodeError):
            gap("The root package.json is not valid JSON.", ErrorCode.INVALID_INPUT)
            manifest = None
        if not isinstance(manifest, dict):
            gap("The root package.json must contain a JSON object.", ErrorCode.INVALID_INPUT)
            manifest = None
        scripts = manifest.get("scripts", {}) if manifest is not None else None
        if (
            not isinstance(scripts, dict)
            or len(scripts) > 256
            or any(
                not isinstance(name, str)
                or not isinstance(command, str)
                or len(name) > 128
                or len(command) > 4096
                for name, command in scripts.items()
            )
        ):
            gap(
                "The root package scripts are malformed or exceed static bounds.",
                ErrorCode.INVALID_INPUT,
            )
            scripts = None
        if scripts is None:
            return AnalysisContext(
                assumptions=tuple(assumptions),
                required_file_ids=frozenset(required),
                seed_evidence_ids=(manifest_evidence_id,),
                entry_evidence_ids=frozenset({manifest_evidence_id}),
                supported=False,
                errors=tuple(errors),
            )

        seeds = [manifest_evidence_id]
        npm_config: _NpmConfig | None = None
        config_id = snapshot.file_id(RevisionSide.TARGET, ".npmrc")
        if config_id is not None:
            if await load(config_id):
                seeds.append(evidence_by_file[config_id])
                config_text = snapshot.require_file(config_id).text
                assert config_text is not None
                if len(config_text.splitlines()) > 256:
                    gap("The project .npmrc exceeds the supported 256-line parsing bound.")
                npm_config = _parse_npmrc(config_text)
                if npm_config.relevant_keys:
                    assumptions.append(
                        "Project .npmrc settings seen (keys only, values withheld): "
                        + ", ".join(npm_config.relevant_keys)
                        + "."
                    )
                if any(key in _REGISTRY_CONFIG_KEYS for key in npm_config.relevant_keys):
                    assumptions.append(
                        "Project registry settings were recorded; no registry metadata was fetched."
                    )
            else:
                gap("The project .npmrc is present but could not be read as admitted UTF-8 source.")

        installing = intake.command_context is CommandContext.NPM_INSTALL
        ignore_scripts = bool(npm_config and npm_config.ignore_scripts)
        if installing and npm_config is not None:
            if npm_config.unknown_ignore_scripts:
                gap("The project ignore-scripts value has unresolved configuration semantics.")
            if npm_config.custom_script_shell:
                gap("A custom npm script-shell leaves lifecycle command execution unresolved.")
            if npm_config.interpolation:
                gap("Environment interpolation in project npm configuration remains unresolved.")
            if npm_config.node_options:
                gap("Configured NODE_OPTIONS/custom loader behavior remains unresolved.")
        if ignore_scripts and installing:
            assumptions.append(
                "Project ignore-scripts=true suppresses npm lifecycle scripts under the "
                "declared adapter."
            )

        origins: list[CommandOrigin] = []
        custom_shell = bool(npm_config and npm_config.custom_script_shell)
        if installing and not ignore_scripts:
            if not custom_shell:
                for script_name in NPM_LIFECYCLE_ORDER + NPM_CONDITIONAL_ORDER:
                    command = scripts.get(script_name)
                    if command is None:
                        continue
                    if not command.strip():
                        continue
                    if not manifest_command_is_excerpted(command, manifest_evidence):
                        gap("A lifecycle command is outside the bounded package evidence excerpt.")
                        continue
                    origins.append(
                        CommandOrigin(
                            label=script_name,
                            command=command,
                            caller_file_id=manifest_id,
                            caller_evidence_id=manifest_evidence_id,
                        )
                    )
            binding_id = snapshot.file_id(RevisionSide.TARGET, "binding.gyp")
            if binding_id is not None and not {"install", "preinstall"}.intersection(scripts):
                required.add(binding_id)
                gap(
                    "binding.gyp activates the npm 11.21.3 default node-gyp rebuild fallback; "
                    "native build behavior remains deliberately unresolved."
                )
                assumptions.append(
                    "The default native fallback was recorded because install and preinstall "
                    "scripts were both absent; its action was not executed or rewritten."
                )
        if installing and not ignore_scripts and custom_shell:
            # Keep manifest entry evidence, but claim no command edge under an unknown shell.
            assumptions.append(
                "Lifecycle commands were not followed through a custom script shell."
            )

        if intake.command_context is CommandContext.REVIEW_ONLY:
            assumptions.append(
                "The selected review-only context establishes no particular install-time execution."
            )

        traced = await trace_commands(
            snapshot,
            ledger,
            budget,
            origins=tuple(origins),
            scripts=scripts,
            analyzer_version=budget.settings.analyzer_version,
            evidence_by_file=evidence_by_file,
            required_file_ids=frozenset(required),
            seed_evidence_ids=tuple(seeds),
            entry_evidence_ids=frozenset({manifest_evidence_id}),
            max_depth=self.max_depth,
            max_helper_files=self.max_helper_files,
        )
        errors.extend(error for error in traced.errors if error.message not in error_messages)
        all_assumptions = tuple(dict.fromkeys(assumptions + list(traced.assumptions)))
        signals = collect_signals(snapshot, ledger, traced.evidence_by_file)
        return AnalysisContext(
            assumptions=all_assumptions,
            required_file_ids=traced.required_file_ids,
            seed_evidence_ids=traced.seed_evidence_ids,
            entry_evidence_ids=frozenset({manifest_evidence_id}),
            relationships=traced.relationships,
            supported=True,
            signals=signals,
            errors=tuple(errors),
        )
