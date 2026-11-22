# BeforeRun implementation record

This file records observable implementation evidence. It does not replace the acceptance
criteria and limits in [MASTER_BUILD_PLAN.md](MASTER_BUILD_PLAN.md).

## S00 — starting point and scope

**Date:** 22 November 2026  
**Status:** scaffold verified and scope fixed; repository review remains unimplemented.

### Preserved state

- `main` began with no commits and the supplied scaffold was untracked. No reset, clean,
  checkout, deletion, or dependency installation was performed.
- `.env`, `.venv`, generated package metadata, and caches are ignored. The existing `.env`
  contained nonempty credential/settings values; none was printed, copied into source,
  validated, or used for a model call. Its local permissions were tightened from `0644`
  to `0600` without changing its contents.
- Credential-signature scanning covered 39 project/environment text files. The only hit
  was the credential already present in ignored `.env`; the scan did not expose its value.
  This is a screening result, not proof that no secret exists.
- Agent/personal workspace files and `docs/design/` review artifacts were deliberately not
  selected for the product checkpoint. They remain untouched. In particular, binary design
  screenshots were not content-reviewed by this model and are not claimed secret-free.

### Fixed MVP decisions

| Decision | Enabled contract |
|---|---|
| Source | One public root `https://github.com/owner/repo`; no arbitrary host or private repository. |
| Revisions | Independently pinned target and optional same-repository baseline; a baseline is not presumed benign. |
| Project | Repository root only (`project_directory: "."`). |
| Commands | `review_only` and root `npm_install` only. The wireframe's inactive Python selector was removed. |
| npm semantics | S05 must verify and declare npm 11.21.3 root-install/no-package-argument behavior, including documented lifecycle order, conditional `dependencies`, `.npmrc` assumptions, and default native-build behavior. Target npm/code is never executed. |
| Investigation | Prefer native caller-supplied function tools through dedicated OpenClaw profile `beforerun` and agent `beforerun-reviewer`; use JSON-decision mode only if S01 proves it necessary. No direct-provider bypass or silent fallback model. |
| Tools | Implement and admit only the bounded `br_` snapshot operations in the master plan, never local filesystem/shell/browser/spawn tools. |
| Results | Assessment, completion, and coverage are independent. Invalid, empty, incomplete, cancelled, and unsupported outcomes cannot become reassuring clean results. |
| Budgets | Use one shared budget with the initial source/request/decision/token/time/concurrency caps in section 19 of the master plan. |
| Exclusions | No clone/checkout/import/install/build/evaluation of submitted source; no submodule/LFS/README URL following; no dependency, binary, full-application-reachability, guard, hosted/private-repository, or whole-repository safety claim. |

### Checks actually run

- `make check`: passed compilation, Ruff lint, and Ruff format checks for `src`.
- `.venv/bin/python -m pip check`: passed with no broken requirements.
- `.venv/bin/python -m ruff check tests`: passed.
- `.venv/bin/python -m ruff format --check tests`: passed.
- `.venv/bin/python -m pytest -m 'not live' tests`: **3 passed**. These tests cover scaffold
  routes/static assets, the disabled and root-only review form, and absence of a review API.
  Pytest emitted one upstream Starlette deprecation warning; it did not fail the checks.
- Supported Node PATH: `node --check src/beforerun/static/shell.js` passed with Node
  **24.22.3** and npm **11.19.1** available.
- `openclaw --version`: **2026.11.6 (06afb10)** through the installed launcher.

The default Node 25 executable failed to load a Homebrew `simdjson` library. The supported
Node 24 installation works and must be selected explicitly for OpenClaw CLI work. No model,
GitHub source, behavior-detection, hosted-CI, or end-to-end scanner test has run.

### Next gate

S01 must establish the dedicated profile and prove the exact Cerebras/Kimi route, restricted
text inference, and an inert `br_read_excerpt` round-trip (or deliberately tested JSON-decision
mode). The installed CLI/version is not evidence of provider entitlement, effective tool
isolation, or a working reviewer. Installation/account configuration and live model tests
require the separate authorization specified by the implementation brief.

## S02 — contracts, settings, and budgets

**Date:** 22 November 2026
**Status:** complete; no live OpenClaw/Cerebras configuration or inference was attempted.

### Changed paths

- `src/beforerun/features/contracts.py`: strict review/source/evidence/finding/report and
  discriminated snapshot-tool schemas, bounded text/collections/IDs/timestamps, and clear
  separation between model candidates and server-owned completion/coverage.
- `src/beforerun/features/settings.py`: server-owned limits, private credential fields,
  restricted Gateway origin validation, and hard ceilings for environment overrides.
- `src/beforerun/features/budgets.py`: shared monotonic deadline, request/decision/tool
  counters, one transient retry per operation, source/tree reservations, token reservation
  and reconciliation, final/repair limits, and cancellation checks.
- `pyproject.toml`, `requirements-dev.lock`: intentional Pydantic/HTTPX runtime and test
  dependency declarations/resolved versions.
- `tests/test_s02_contracts.py`: adversarial schema and shared-budget tests.

### Checks and blockers

- `.venv/bin/python -m pytest -q -m 'not live' tests/test_s02_contracts.py`: **14 passed**.
- Ruff lint/format checks for these files pass after the final stage formatting edit.
- No known S02 blocker. The next Agent A stage is S03; S01 remains deliberately excluded
  from this run.

### Next Agent A stage

S03 — complete GitHub pinning, immutable object bindings, adversarial source integrity,
and bounded snapshot tests. Existing S03/S04 files are preserved and audited, not replaced
wholesale.

## S03 — GitHub pinning and bounded snapshots

**Date:** 22 November 2026
**Status:** complete for the Agent A source/snapshot scope; no live retrieval or model call was attempted.

### Changed paths

- `src/beforerun/features/github_source.py`: strict URL/Git-ref and provider-shape validation,
  fixed API origin/version headers, public-repository checks, independent target/baseline pins,
  redirect refusal, header-aware rate-limit classification, root-tree SHA binding, streamed
  envelopes, declared/actual blob bounds, base64/Git-object integrity checks, and immutable
  repository/object byte caching with independent first-use verification per revision.
- `src/beforerun/features/snapshot.py`: monotonic inventory completeness, path/mode/type
  validation, duplicate protection, per-review IDs, symlink/submodule/LFS/binary exclusions,
  retained raw provenance, BOM-preserving UTF-8 decoding, exact original byte/line maps, and
  shared immutable decoded bytes/text/maps that preserve each path/revision binding.
- `tests/test_intake.py`, `tests/test_github_source.py`, `tests/test_snapshot.py`,
  `tests/test_source_evidence_bounds.py`: adversarial intake, redirect/token containment,
  moved branches, independent/missing baselines, malformed metadata and JSON strings,
  root/object hash mismatches, bounds, cache sharing, mode/type mismatches, hostile paths,
  CRLF/BOM/empty/long-file mappings, and cross-review isolation cases.
- `tests/fixtures/source/moved_branch.json`: inert branch-movement and pinned-tree fixture.
- `docs/IMPLEMENTATION_RECORD.md`: this stage evidence and handoff.

### Checks and blockers

- Scoped Agent A/source regression command covering intake, GitHub source, snapshots, source
  bounds, contracts, and the existing comparison consumer: **155 passed**.
- Ruff lint and format checks pass for all scoped S03 implementation/test files.
- A full offline run after the final source changes reported **164 passed, 4 failed**.
  All four failures are in Agent B's concurrently changing jobs/API tests
  (`tests/test_review_api.py`); Agent A did not edit those service/API files or tests.
- Repository-wide Ruff remains red on pre-existing line-length issues in the unfinished S04
  `evidence.py` and in Agent B-owned files. These are not silently marked clean.
- Supported Node 24 was selected only for the local JavaScript syntax test. The broken default
  Node 25 installation was not repaired or changed. No live OpenClaw/Cerebras configuration,
  provider inference, external GitHub request, dependency installation, commit, or push occurred.
- An independent S03 static review identified root-tree binding, cache allocation, mode/type,
  malformed-response, rate-limit, and resolution-test gaps. All six were addressed and covered
  by the scoped passing suite above.

### Next Agent A stage

S04 — evidence excerpts and delivery receipts. Preserve the new source bindings while testing
unknown/cross-job IDs, fetched-but-undelivered citations, exact spans/quotes, CRLF/minified
columns, redaction, and derived provenance. S01 remains deliberately excluded.

## S04 — Evidence excerpts and delivery receipts

**Date:** 22 November 2026  
**Status:** complete for the Agent A evidence-ledger scope; later investigator/report integration
remains subject to its own stage gates. No live source or model request was attempted.

### Audited implementation

- Preserved the existing `src/beforerun/features/evidence.py` implementation: immutable issued
  source/derived evidence, exact delivery receipts, per-ledger ID bindings, pinned source links,
  original source coordinates, bounded UTF-8 chunks, redaction, and parent/counterpart provenance.
- The tests establish that fetched/listed evidence is not citable until its exact representation
  has a valid delivery receipt; unknown and cross-review IDs are rejected.
- CRLF/BOM raw identity, normalized delivery, original line/byte/column mappings, minified chunk
  continuation, quoted-secret redaction, derived-row restrictions, exact quote/range checks, and
  atomic receipt failures are covered offline.
- `tests/test_evidence.py`: formatting-only cleanup during the final audit; no unfamiliar logic
  or test expectation was replaced.

### Checks and blockers

- Scoped evidence/source/snapshot/contract tests: **58 passed**.
- Full offline suite (`pytest -q -m 'not live' tests`): **231 passed**, with one upstream
  Starlette deprecation warning.
- Ruff lint and format checks pass for the evidence implementation and its test files.
- No S04 ledger blocker is known. S01 remains deliberately excluded, and these offline results
  do not claim live investigation quality or later-stage validation integration.

### Next Agent A stage

S05 — supported root npm setup discovery, static signals, and bounded reachability. Add the
missing modules and inert fixtures without executing submitted source. Preserve existing Agent B
comparison/API/UI work and the already-created later-stage Agent A files.

## Post-review remediation

**Date:** 22 November 2026
**Status:** offline checks green; release still blocked.

### Fixed defects

- `evidence.py`: receipt validation now precedes delivery-state changes; UTF-8 clipping records
  the actual character-boundary byte count and matching span end; quoted secret values are
  redacted; fully represented redacted lines no longer advertise a phantom continuation chunk.
- `review_service.py`: cancellation and semaphore acquisition no longer leak a worker slot;
  the shared wall-clock deadline encloses `pipeline.run()`; the pipeline receives the admitted
  review ID, and mismatched report identity/input is rejected before storage.
- `job_store.py`: report identity/input is also checked at the storage boundary.
- `reviews.js`: derived evidence is no longer numbered as literal source lines, and clearing or
  replacing a review also requests cancellation of the active server job.
- `app.py`, `routes.py`, `job_store.py`: Ruff lint/format cleanup only.

### Checks actually run

- `make check` with Node 24 selected: compilation, Ruff lint, Ruff format, and the full offline
  suite passed — **176 passed, 1 upstream deprecation warning**.
- `.venv/bin/python -m pip check`: no broken requirements.
- `node --check src/beforerun/static/reviews.js` with Node **24.22.3**: passed.

No live GitHub, OpenClaw, or model request ran; no dependency was installed; no production
review submission was enabled. The unavailable pipeline, missing investigation modules, and
G1–G7 release gates remain blockers described in `docs/RELEASE_GATES.md`.

## S05 — Root npm setup, signals, and bounded static reachability

**Date:** 22 November 2026  
**Status:** complete for the scoped offline Agent A adapter. This establishes source-backed npm
setup leads and static relationships, not runtime execution, live detection quality, or a
malware verdict.

### Implemented scope

- `src/beforerun/features/npm_setup.py`: pinned-root `package.json` discovery; declared npm
  **11.21.3** lifecycle order (`preinstall`, `install`, `postinstall`, `prepublish`, `preprepare`,
  `prepare`, `postprepare`) and conditional `dependencies`; project-only `.npmrc` handling;
  `ignore-scripts`, custom-shell/interpolation/`NODE_OPTIONS` gaps; and the default
  `node-gyp rebuild` fallback when `binding.gyp` exists without `install` or `preinstall`.
  User/global configuration, environment interpolation, registries, and dependency artifacts
  are never consulted.
- `src/beforerun/features/signals.py`: bounded environment/network/dynamic-code/filesystem/deletion/
  reviewer-text search leads with benign alternatives. Redacted or out-of-excerpt matches become
  non-citation source pointers; no signal is an assessment or execution trigger.
- `src/beforerun/features/reachability.py`: per-review source-ID traversal for literal local
  `node <path>` commands, nested `npm run <name>`, relative literal imports/requires, CommonJS
  suffix/index resolution, exact ESM specifiers, cycles, and depth/file/relationship/seed caps.
  Computed imports, external packages, arbitrary shell, inline code, package binaries, absolute/
  escaping paths, missing/unreadable/symlink files, native builds, and custom loaders remain
  explicit gaps. Every issued edge cites caller/callee evidence and says static candidate
  relationships do not prove runtime control flow.
- `src/beforerun/features/pipeline.py`, `report.py`: additive `AnalysisContext.signals/errors` and
  `build_report(analysis_errors=...)` propagation. Static analysis gaps now prevent a complete/
  reassuring report even when the model proposes no findings. The investigator context includes
  signals alongside relationships; `prompts/investigator-v1.txt` explicitly limits their authority.
- `tests/s05_helpers.py`, `test_npm_setup.py`, `test_reachability.py`, `test_signals.py`, and
  `test_npm_setup_pipeline.py`: offline discovery, ordering, configuration, native fallback,
  traversal, caps, cycles, path confinement, redacted leads, gap-sensitive completion, and real-
  analyzer pipeline checks with all HTTP mocked.
- `tests/fixtures/npm_setup/annotation.json` and the `benign`, `reviewer_targeting`, and
  `unsupported_inline` inert cases: human annotations distinguish fixture mechanics from behavior
  quality claims.

### Checks and limitations

- Scoped S05/S06/pipeline suite: **67 passed**, one upstream Starlette deprecation warning.
- Final `make check`: source compilation, Ruff lint, and Ruff format checks passed; full offline
  suite **268 passed**, one upstream Starlette deprecation warning.
- Unsupported/dynamic/native cases yield visible analysis errors and partial coverage rather than
  clean completeness. Static fixture outcomes are not evidence of live npm or model quality.
- No target repository was cloned, imported, installed, built, or executed; no shell/process,
  live GitHub, registry, OpenClaw, or Cerebras request was made; no dependency was installed.

## S06 — Existing comparison implementation verified

**Date:** 22 November 2026  
**Status:** verified through the existing Agent B implementation; no Agent B-owned source was
modified or replaced.

- Preserved `src/beforerun/features/compare.py` and `tests/test_compare.py`. Their tree-derived
  inventory states, original-side evidence, bounded diffs, incomplete-inventory handling, and
  unread-counterpart gaps were exercised with S05's unchanged-hook/changed-helper case.
- `test_unchanged_hook_changed_helper_integrates_with_existing_s06_comparison` confirms the
  unchanged root `prepare` hook, modified target helper, original target/baseline evidence, and
  completed bounded comparison. This is the benign Node-version fixture, not malware validation.
- A comparison/baseline remains evidence about differences, not proof of benign or malicious
  intent. S06's final checks are included in the **67** scoped and **268** full-suite passes above.

### Blockers and next Agent A stage

S01 remains deliberately excluded pending explicit authorization for live profile/provider
configuration. No S05/S06 offline blocker is known. The next stage is **S07 — snapshot-only tool
dispatcher**: audit and complete the existing `safe_tools.py` and its negative tests without
expanding filesystem, process, network, or arbitrary-URL authority.

## S07 — Snapshot-only tool dispatcher

**Date:** 22 November 2026  
**Status:** complete for the offline Agent A dispatcher scope. All seven operations were already
present and were preserved; adversarial review found and fixed four prevalidation/binding gaps.

### Audited implementation and fixes

- Preserved `src/beforerun/features/safe_tools.py`'s bounded `br_list_files`, `br_read_excerpt`,
  `br_search_source`, `br_static_decode`, `br_extract_strings`, `br_read_diff`, and `br_finish`
  operations, two-call batch limit, current-snapshot containers, per-review IDs, source-only
  pointers, structured errors, operation budgets, and exact evidence delivery semantics.
- Dispatch now rejects a nonpositive/noninteger delivery turn before schema-dependent receipt
  work, source fetching, evidence delivery, or tool-budget mutation. Previously `turn=0` reached
  receipt construction and leaked a Pydantic error after the read.
- Static decoding accepts literal source/redacted evidence or one extracted string, not decoded/
  diff evidence. This prevents tool-created provenance chains beyond the citation contract while
  retaining the ordinary source→string→decode workflow. Literal decoding still never evaluates
  code and remains bounded to two declared operations.
- `br_read_diff` prevalidation now binds both original-side file IDs to the current snapshot and
  their expected target/baseline sides. Foreign comparison pairs fail before materialization,
  fetching, delivery, or operation-budget consumption.
- Requesting a container for an unadmitted revision now produces a stable `ReviewError` instead
  of `StopIteration`. Model-supplied ownership is never trusted.
- `tests/test_safe_tools.py` adds regressions for invalid receipt turns, decoded-evidence reuse,
  foreign pairs, malformed Unicode, absent revisions, 80-entry inventory pagination, matching
  minified chunk/file IDs and original columns, exact string-output/receipt set equality,
  undelivered decode sources, decode input/output bounds, and 40-row diff cursor pagination.

### Checks and boundaries

- Baseline dispatcher/investigator/OpenClaw-contract audit: **30 passed** before the new cases.
- Final scoped dispatcher/investigator/OpenClaw/pipeline suite: **44 passed**, one upstream
  Starlette deprecation warning.
- Final `make check`: compilation, Ruff lint, and Ruff format passed; full offline suite
  **278 passed**, one upstream Starlette deprecation warning.
- The mocked OpenClaw payload exposes exactly the seven implemented `br_` function definitions.
  No live profile allowlist was changed or claimed verified: effective installed-Gateway policy
  remains the explicitly authorized S01/live integration gate.
- Tests forbid socket connections and process launches. No submitted source was executed; no live
  GitHub, OpenClaw, registry, or Cerebras request ran; no dependency was installed.

### Next Agent A stage

**S08 — iterative OpenClaw investigation.** Audit the existing `openclaw_client.py`, versioned
prompt, and `investigator.py`; complete mocked transport/history/repair/cancellation/budget cases.
The explicit harmless live tool smoke remains excluded until S01 authorization is provided.

## S08 — Iterative OpenClaw investigation

**Date:** 22 November 2026  
**Status:** complete for the mocked/offline investigation-loop scope. **S01 remains incomplete**, so
the genuine Kimi/Cerebras route, effective installed tool policy, and harmless live tool-use
acceptance are not claimed.

### Audited implementation and fixes

- Preserved the bounded stateless `openclaw_client.py` route: server-owned loopback/HTTPS Gateway
  origin and agent, no account-wide session key, no direct Cerebras client or fallback model,
  redirect refusal, bounded streamed JSON, one transient retry, cancellation, shared attempt/token/
  time budgets, and separate no-tool final/repair modes.
- Canonical assistant tool calls now retain exactly their `id`, `type`, function `name`, and raw
  `arguments` while discarding private reasoning and arbitrary upstream extension fields.
  Inconsistent `finish_reason`/tool-call combinations and malformed identities fail closed.
- Reviewer content, tool IDs/names/arguments, and outgoing transcript JSON are validated as UTF-8
  JSON text. Escaped lone surrogates now produce bounded `INVALID_MODEL_OUTPUT` errors before a
  request or token-budget mutation rather than crashing transcript token estimation.
- `investigator.py` retains canonical assistant/tool-result history, exact tool IDs, delayed
  evidence receipts, deliberate finish/decision/invalid/upstream/cancel/budget stops, and one final
  format repair. Repair context is now structured and bounded with `INVALID_MODEL_OUTPUT` and up to
  64 actually delivered evidence IDs; it cannot request new evidence or greater confidence.
- `pipeline.py` now supplies actual analysis errors, required file IDs/paths/fetch states, bounded
  comparison pair IDs/change/gap records, and remaining decision/tool/model/runtime budgets in the
  initial untrusted-data context. This also makes issued comparison pairs usable by `br_read_diff`.
- `prompts/investigator-v1.txt` explicitly requires behavior-source evidence for non-benign claims,
  evidence for and against hypotheses, benign alternatives, relevant entry-point inspection,
  bounded-search uncertainty, comparison unknowns, and server-owned coverage/model wording.
  Existing package data includes `features/prompts/*.txt`.
- `tests/test_openclaw_contract.py`, `test_investigator.py`, and `test_pipeline.py` add mocked cases
  for canonical history, malformed Unicode, finish consistency, raw transport retry, decision and
  model limits, no finalization after cancellation, structured repair context, and comparison/gap/
  budget context.

### Checks and limits

- Final S08/dispatcher/pipeline/report scope: **66 passed**, one upstream Starlette deprecation
  warning.
- Final `make check`: source compilation, Ruff lint, and Ruff format passed. The repository's
  current offline selection completed **290 passed, 1 browser test deselected**, with one upstream
  Starlette deprecation warning.
- All HTTP was mocked. No live GitHub, OpenClaw, Cerebras, registry, browser, or target process was
  invoked; no profile/credential was changed and no dependency was installed. Mocked model choices
  do not establish live investigation quality or upstream identity.
- Local cancellation prevents subsequent application calls; it does not claim that an upstream
  provider stopped inference or billing.

### Next Agent A stage

**S09 — finding validation and report policy.** Audit and complete the existing `validate.py` and
`report.py` with mixed-validity, empty/partial, serious-plus-gap, simulation, redaction, comparison,
and reproducibility tests. S01/live verification remains explicitly blocked pending authorization.

## Agent B — Live proof evidence audit and release record

**Date:** 22 November 2026

**Status:** proof record populated from retained failed-run artifacts; G2–G4 and release remain
blocked. This entry records a follow-up audit, not another live execution or a passing S01.

- `docs/LIVE_PROOF_TEMPLATE.md` now records both failed smoke attempts, the limited local
  cancellation/authentication-denial checks, all unexecuted proof rows, four recorded case
  durations, missing usage/pricing/upstream evidence, and the unresolved authorization provenance.
- `docs/RELEASE_GATES.md` now links those results and distinguishes saved policy restrictions
  from effective Gateway isolation. Existing offline gate evidence remains scoped to mocks.
- `docs/live-proof/policy_recheck.json` captures a read-only check of the dedicated reviewer's
  saved configuration at 09:46:06 UTC: tools exactly match the original deny-all state,
  context injection is disabled, startup is disabled through defaults, binding is loopback,
  agent-to-agent access is disabled, and model fallbacks are empty. The running Gateway's
  application of that policy was not independently confirmed.

Checks: all 10 saved JSON artifacts parse; report counts, failures, policy restoration, gate
states, table columns, and local links agree with the artifacts. The offline admission opt-in
regression passed (**1 passed**, one existing Starlette deprecation warning). New/rewritten proof
text and the audit entry passed a limited credential-pattern/whitespace check; this does not
replace the publication secret review. Repository-wide `git diff --check` still reports existing
Markdown trailing spaces in earlier implementation-record entries; those entries were preserved.

No new network/model request, configuration/credential change, install, source execution,
publication, or push occurred during this audit. No Agent A implementation was changed.

**Next Agent B stage:** S13 live measurement/release evidence remains unfinished. A further
explicitly scoped live run must first resolve the provider/allowlist failures and verify effective
isolation; then establish a successful read/checked citation, model identity, continuation,
cancellation limits, and real usage/cost. Admission and release remain blocked in the record.

## Agent B — Remaining local S13 preparation and isolated checkpoint

**Date:** 22 November 2026

Completed local release preparation without enabling reviews or publishing. The owner chose
Apache-2.0. Their live approval was explicitly conditional on a verified free allowance; public
Cerebras documentation/metadata reads did not establish account balance/expiry or eligibility
for the exact configured model, so no additional Gateway/inference request was made.

Changed paths:

- `LICENSE`, `NOTICE`, `pyproject.toml`, `README.md`: owner-selected license, metadata and attribution.
- `src/beforerun/static/styles.css`: pair coverage labels with their values on desktop/mobile.
- `tests/fixtures/demo/run_live_proof.py`, `tests/test_proof_runner.py`: real-client inert read,
  exact checked citation, bounded request/timing/usage journal, default refusal and redaction tests.
- `tests/fixtures/demo/prepare_candidate.py`, `tests/test_release_candidate.py`: scoped export,
  credential/history/cache/metadata exclusion, symlink/traversal/case-alias/manifest protections,
  and reproducible source export. Generated `.egg-info`/`.dist-info` are excluded.
- `tests/fixtures/demo/record_demo.py`, `docs/demo/*`: four visibly mocked fixture frames,
  interactive playback, capture receipts, and visual review.
- `docs/DEPENDENCY_NOTICES.md`, `docs/RELEASE_LICENSE_REVIEW.md`, `docs/LIVE_ROUTE_DIAGNOSIS.md`,
  `docs/INTEGRATION_LIMITS.md`: dependency/provenance review, provider/tool-policy diagnosis,
  and a long custom-response-model report limit noted for Agent A.
- `docs/live-proof/route_diagnosis.json`, `docs/live-proof/free_allowance_check.json`: redacted
  failed-route classification and unmet free-only authorization prerequisite.
- `docs/LIVE_PROOF_TEMPLATE.md`, `docs/LOCAL_RUNBOOK.md`, `docs/RELEASE_GATES.md`,
  `docs/RELEASE_CHECK_RESULTS.json`, `docs/RELEASE_SECRET_REVIEW.json`,
  `docs/release-candidate/*`, this record: evidence, scope, checks and checkpoint attestation.
- `dist/beforerun-offline-candidate-b443a5d9f248.tar.gz`: ignored local reviewed archive.

Checkpoint: `b443a5d9f24878775420b7c149f51b3a55e2a98b`, stored only at the local
`refs/beforerun/offline-candidate-20261122-b443a5d9f248` ref. It has no parent and contains
129 reviewed product files plus the generated manifest. Existing private files in old Git
history were preserved and excluded from this snapshot; the current branch/index were
unchanged. No publication, push, install, configuration mutation, or submitted-source execution
occurred. No Agent A core implementation was changed.

Validation: archive integrity/file hashes and exact re-export fingerprint passed. The archive
from that exact local commit passed compile, Ruff lint/format, **316 offline tests**, and
**1 actual Chrome test with mocked APIs**, with the existing Starlette deprecation warning.
The final scoped secret/recording review binds all 129 product files and four reviewed PNGs;
it found no unresolved credential pattern. Old Git history remains blocked from publication.

Blockers: the required free allowance and successful live G2–G4/evidence/usage/quality proof
remain unverified. The 32-character custom-response-model display overflow is documented for
Agent A; the configured default route expectation used by this candidate fits the contract.

Next Agent B stage: complete the remaining S13 live proof/measurements once provider-backed
free eligibility is verified, then reevaluate release gates. Conditional approval is already
recorded; do not infer a paid allowance or publish/push from it.

## Agent B — Owner-approved Baseten fallback

**Date:** 22 November 2026

The owner requested a Baseten credential and failure fallback, then clarified the model as
Muse Spark Open, `meta-models/muse-spark-open-1026`, distinct from Meta `muse-spark-1.3`.
That explicitly authorizes this fallback configuration despite the earlier default strict
single-provider plan. It does not authorize unverified paid inference.

Used the existing OpenClaw native provider-failover mechanism. The primary remains
`cerebras/moonshotai-kimi-k3.1-pro-trial`; its fallback is
`baseten/meta-models/muse-spark-open-1026` through `https://inference.baseten.co/v1`.
The supplied key was entered without terminal echo and saved only in ignored/private
server settings with mode `0600`. No key value is stored in this record or product code.
All unrelated profile/provider/agent/isolation settings were verified unchanged.

Changed paths: `.env.example`; `features/gateway_policy.py`, `review_service.py`, `routes.py`;
`static/index.html`, `reviews.js`; `tests/test_gateway_policy.py`, `test_ui_review.py`,
`tests/fixtures/demo/configure_baseten.py`, `tests/fixtures/jobs/browser_checks.js`;
`docs/BASETEN_GATEWAY_SETUP.md`, `LOCAL_RUNBOOK.md`, `RELEASE_GATES.md`, this record and README.
Private configuration changes are the ignored `.env` and dedicated Gateway profile JSON;
reversible private backups are outside release scope. Agent A core/client/budget/report
implementation was preserved.

Capabilities, job metadata and exports disclose the configured primary/fallback. The UI
shows processing disclosure before submission and beside reports. The reviewer alias stays
strict; actual upstream selection remains unverified because the Gateway echoes that alias.
Report assumptions are preserved even at the 32-item limit. Tests verify private merge
preservation, concurrent-write rejection, credential-free public metadata and inert UI text.

The Gateway configuration schema validation passed. Tests use only mocks and the prepared
Node 24/Chrome environment. No inference, install, service restart, publication or push ran.
The pre-fallback release checkpoint remains historical; the new provider path requires
fresh effective isolation, model/tool/failover and verified-free allowance evidence.

Final validation for this provider change: compile/Ruff lint/format passed, **326 offline tests
and 1 actual Chrome test with mocked APIs passed**. The browser assertions cover fallback
disclosure before submission and in the report. Private Gateway config schema validation
passed; a 123-file product-text scan found no supplied Baseten key or credential pattern.
Only the ignored/private credential files contain the supplied value.

Next Agent B stage: after verified free eligibility for the approved provider/model, run the
bounded live proof and validate failover without treating Baseten as Cerebras/Kimi evidence.
