# BeforeRun

**See what runs before you run it.**

**Build from the [complete master plan](docs/MASTER_BUILD_PLAN.md).** It contains the
Gatekeeper feature mapping, GitHub review design, restricted OpenClaw integration,
step-by-step task checklists, test gates, deployment guidance, and full product roadmap.
Earlier planning documents remain background; the master plan takes precedence.

The intended product is **Gatekeeper-style package/dependency investigation plus
GitHub repository setup review**. GitHub review is the selected first hackathon
milestone; package investigation remains part of the product roadmap. See the
[product scope clarification](docs/PRODUCT_SCOPE.md) for the feature mapping,
shared-engine design, and distinction between the event milestone and full product.

This is a **local hackathon preparation scaffold** for GitHub repository review.
It contains a Python application skeleton, a health endpoint, a static interface wireframe,
development checks, and a plan. The investigation form is disabled; no repositories or packages
are downloaded, no model calls are made, and no findings are generated.

The selected first workflow is **paste a public GitHub URL before running its setup code**.
The planned review pins a commit, follows Node setup entry points, optionally compares
an earlier revision, and explains suspicious behavior with checked code references.
Python and other setup adapters are later, separately tested scopes. The planned review can
help identify a harmful update; it cannot guarantee that a computer will not be infected.

The supplied hackathon FAQ permits pre-existing scaffolding and frameworks, while requiring
the core functionality to be developed during the event with Kimi K3.1 Pro on Cerebras central
to the solution. See [the recorded rule](docs/HACKATHON_RULES.md).

## Local setup

Use Python 3.12 or newer:

```sh
cd /Users/rahulkumarsinghj/Desktop/BeforeRun
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e .
make check
make dev
```

Open http://127.0.0.1:8000. The health endpoint is http://127.0.0.1:8000/health.
The Windows virtualenv executable directory is `Scripts` instead of `bin`.

Alternatively, `make install PYTHON=python3.12` creates the environment and installs the framework.

The scaffold does not need an API key. Later, merge `.env.example` settings into a private
`.env` without overwriting existing values, and configure
credentials locally. The newer organizer FAQ supplies `moonshotai-kimi-k3.1-pro-trial`;
approved preview access still needs a real connection test. Environment files containing
credentials are ignored by Git. Follow the [master plan's build stages](docs/MASTER_BUILD_PLAN.md#22-step-by-step-implementation-stages)
to construct the GitHub reviewer. Its [OpenClaw setup](docs/MASTER_BUILD_PLAN.md#10-openclaw-integration-and-setup)
uses the dedicated `beforerun` profile, `beforerun-reviewer` agent, and snapshot-only `br_`
tools; do not mix it with unprofiled commands from the historical execution guide.

## Layout

```text
src/beforerun/
  app.py          generic server: interface and health endpoint
  cli.py          local startup and environment loading
  static/         HTML/CSS and theme preference only
  features/       documentation placeholder for event-time core work
tests/            documentation placeholder for event-time behavior checks
docs/
  MASTER_BUILD_PLAN.md             authoritative implementation plan
  GATEKEEPER_GITHUB_BUILD_PLAN.md
  EXECUTION_GUIDE.md
  HACKATHON_RULES.md
  HACKATHON_PLAN.md
  COMPLETION_CHECKLIST.md
  FEATURE_BACKLOG.md
  PACKAGE_MANAGER_ROADMAP.md
  REPOSITORY_REVIEW_PLAN.md
  PRODUCT_SCOPE.md
  RESEARCH_BRIEF.md
  TECHNICAL_DESIGN.md
  EVALUATION_AND_DEMO.md
  RESEARCH_SOURCES.md
  ATTRIBUTION_DRAFT.md
```

## Validation scope

`make check` verifies compilation and Ruff checks for the scaffold. It does not establish
package-detection accuracy, model behavior, an operational install guard, or full production readiness.
The CI workflow is defined but has not run on a hosted repository.

Framework dependencies are pinned in `requirements-dev.lock`. Local compilation, lint,
dependency consistency, and interface/health-route checks passed on Python 3.12.16.
See [the local check record](docs/PREPARATION_CHECKS.md) for the validation scope.

## Research and event preparation

The [master plan](docs/MASTER_BUILD_PLAN.md) consolidates this research into one buildable
sequence. Its [test strategy](docs/MASTER_BUILD_PLAN.md#20-test-strategy-and-case-matrix)
updates the earlier case expectations, including partial outcomes and safe simulations.

The [research brief](docs/RESEARCH_BRIEF.md) explains the recommended scope, real attack
patterns, existing tools, and what BeforeRun should and should not promise. The
[technical design](docs/TECHNICAL_DESIGN.md) specifies safe retrieval, bounded model tools,
evidence, result states, and operating limits. The
[evaluation and event playbook](docs/EVALUATION_AND_DEMO.md) defines 27 proposed core cases,
conditional Python checks, measurements, the 24-hour schedule, and a demo storyboard.
[43 primary references](docs/RESEARCH_SOURCES.md) support the research; unverified preview
details are explicitly recorded. This work changes documentation only.

## Next work

Start with [S00 and S01 in the master plan](docs/MASTER_BUILD_PLAN.md#22-step-by-step-implementation-stages):
preserve/verify the scaffold, then prove a real restricted OpenClaw/Kimi tool round-trip.
Continue through pinned retrieval, evidence, context/comparison, safe tools, investigation,
validation, jobs/UI, and measured release gates. The first enabled scope remains one public
GitHub repository, an optional baseline, and supported root-source review.
Use the master's [full roadmap](docs/MASTER_BUILD_PLAN.md#23-full-gatekeeper-style-roadmap)
for package audits, guards, monitoring, and reporting. The earlier event plan and completion
checklist are retained as historical background, not a second implementation authority.
The [feature backlog](docs/FEATURE_BACKLOG.md) records proposed additions, their upstream
comparison, and estimates. These features are not implemented in the scaffold.
The [GitHub repository review plan](docs/REPOSITORY_REVIEW_PLAN.md) defines the selected
workflow, a compromised-update example, and acceptance criteria. The current interface
already illustrates that input; retrieval, investigation, and results still need implementation.
The [package manager roadmap](docs/PACKAGE_MANAGER_ROADMAP.md) puts npm package input
after the repository workflow, followed by PyPI for pip/uv, Homebrew, and further ecosystems.
Package analysis, project audits, and install guards have separate milestones. Reading a
repository's setup files does not establish coverage of its registry dependencies.

This workspace has not been published or submitted. Finalize the private
[attribution draft](docs/ATTRIBUTION_DRAFT.md) and license before its first public release.
