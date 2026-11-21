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
