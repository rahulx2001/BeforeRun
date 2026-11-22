# Agent A — Core investigation engine (Half 1 of 2)

**Updated: 22 November 2026.**  
**Sibling:** [AGENT_B_BUILD_HALF.md](AGENT_B_BUILD_HALF.md)  
**Authority:** [MASTER_BUILD_PLAN.md](MASTER_BUILD_PLAN.md) (this half is ownership only; do not contradict it)

**Your job:** Build the trusted review pipeline from GitHub intake through a checked report object — everything that turns a pinned public repo into validated findings **without** owning the HTTP jobs API or the browser UI.

**Partner:** Agent B owns jobs API, static UI, fixtures packaging, release gates orchestration, and ops/docs. You hand Agent B a callable orchestration surface; they wire routes and the form to it.

---

## Copyable prompt for this agent

```text
Work in /Users/rahulkumarsinghj/Desktop/BeforeRun.

You are Agent A (Core investigation engine). Read:
- docs/MASTER_BUILD_PLAN.md (authority)
- docs/AGENT_A_BUILD_HALF.md (your ownership)
- docs/AGENT_B_BUILD_HALF.md (do not edit Agent B files)

Implement only Agent A stages and files listed in AGENT_A_BUILD_HALF.md.
Do not edit job_store.py, review_service.py, routes.py, static/reviews.js, or UI wiring.
If a shared contract change is required, update contracts/settings/budgets and leave a short note in docs/IMPLEMENTATION_RECORD.md for Agent B.

Keep the existing Python/FastAPI/static scaffold. Create modules only when their stage arrives.
BeforeRun reviews pinned public GitHub source as data. Never clone/checkout/install/import/execute
the submitted repository. All generative investigation goes through OpenClaw profile beforerun /
agent beforerun-reviewer and snapshot-only br_ tools. No direct Cerebras bypass.

Use offline/mocked tests by default. Ask before installs, live model calls, credentials, or pushes.
At the end of each stage: list changed paths, checks run, blockers, and the next Agent A stage.
```

---

## Shared rules (both agents)

1. Master plan wins on tool names, result states, budgets, and safety.
2. Do not claim another agent's modules are done.
3. Do not expand into section 23 roadmap (R1–R12) until MVP gates pass.
4. Sync only at the checkpoints below; otherwise stay in your file tree.
5. Prefer additive PRs / local checkpoints per stage, not one giant diff.

---

## You own these files

```text
src/beforerun/features/
  contracts.py          # shared schemas — you land the first version
  settings.py
  budgets.py
  github_source.py
  snapshot.py
  npm_setup.py
  signals.py
  reachability.py
  evidence.py
  safe_tools.py
  openclaw_client.py
  investigator.py
  validate.py
  report.py
  # OPTIONAL thin façade for Agent B (no HTTP):
  pipeline.py           # run_review(intake) -> CheckedReport | PartialReport

tests/
  test_intake.py
  test_github_source.py
  test_snapshot.py
  test_npm_setup.py
  test_reachability.py
  test_evidence.py
  test_safe_tools.py
  test_openclaw_contract.py
  test_investigator.py
  test_report_policy.py
  fixtures/source/      # inert source / recorded GitHub HTTP only
  fixtures/openclaw/    # recorded Gateway / tool-round fixtures

integrations/openclaw/  # only if HTTP client already works and master plan §10.9 applies
```

**Do not touch (Agent B):** `job_store.py`, `review_service.py`, `routes.py`, `compare.py` (Agent B owns comparison presentation map after your snapshot IDs exist — see sync), `static/*` connection work, `app.py` route mounts (except leave `/health` alone), `tests/test_compare.py`, `tests/test_review_api.py`, `tests/fixtures/ui/`.

**Exception — contracts:** You own the first landing of `contracts.py` / `settings.py` / `budgets.py`. Agent B may add job/API/UI fields only in clearly marked sections and must not break your schemas.

---

## Master-plan sections to read (in order)

| Priority | Sections | Why |
|---|---|---|
| Required | 1–9, 7, 10–15, 19 | Product, safety, OpenClaw, intake → verdict |
| Required | 22 stages S00–S05, S07–S09 | Your build order |
| Required | 20.1–20.3 cases you own | B/R/E/A/F cases tied to source/evidence/tools |
| Skim | 16–18, 21, 24–28 | Know what B expects from your report object |
| Use | 30 | Stage brief template |

Skip implementing: §16 jobs API, §17 UI, §18 compare (B), §21 fixture packaging for demo (B leads), §23+ roadmap.

---

## Your stages (do in order)

| Stage | Effort | Deliverable |
|---|---|---|
| **S00** | 15–30m | Shared with B: inspect git, secrets, `make check`, short decision record. Do not fight over the same files. |
| **S01** | 1–2h | Restricted OpenClaw route proof (§10). Redacted integration note + `test_openclaw_contract.py` seed. |
| **S02** | 45–90m | `contracts.py`, `settings.py`, `budgets.py`. **Sync A→B:** freeze public schema names Agent B will import. |
| **S03** | 2–3h | `github_source.py`, `snapshot.py`. Immutable admitted snapshot. |
| **S04** | 1–2h | `evidence.py` + receipts. |
| **S05** | 90–150m | `npm_setup.py`, `signals.py`, `reachability.py`. |
| **SYNC-1** | — | Snapshot ID maps + evidence issue API stable enough for Agent B's `compare.py`. |
| **S07** | 90–150m | `safe_tools.py` (all `br_` ops + negative tests). |
| **S08** | 2–3h | `openclaw_client.py`, prompts, `investigator.py`. |
| **S09** | 1–2h | `validate.py`, `report.py` (+ optional `pipeline.py`). |
| **SYNC-2** | — | Hand Agent B a `run_review`-style entry that returns a checked report from mocked or live deps. |

Do **not** implement S06, S10, S11, S12, S13 — those are Agent B (S12/S13 are joint at the end).

---

## Sync checkpoints with Agent B

| When | You provide | You need from B |
|---|---|---|
| After S02 | Frozen contracts for Intake, Snapshot, Evidence, Finding, Report, budgets/error codes | Confirmation they can type job/API wrappers against them |
| After S03+S04 (SYNC-1) | Path/object/mode maps + evidence issue/receipt APIs | Nothing blocking; B starts `compare.py` |
| After S09 (SYNC-2) | Callable pipeline → checked/partial report | B wires `review_service` + UI; you fix contract bugs only |
| During S12 | Fix failures in your modules | B runs the gate matrix and files issues against your surface |

---

## Acceptance for Agent A half

- [ ] Public GitHub URL → pinned commit → bounded snapshot (mocked tests green).
- [ ] Evidence IDs cannot cite unshown / cross-job / virtual-row content.
- [ ] npm root setup leads + reachability gaps are honest.
- [ ] All `br_` tools reject host escape, other-job access, and execution.
- [ ] OpenClaw loop (mocked) produces a structured candidate; live smoke only if authorized.
- [ ] `validate` + `report` never turn invalid/partial output into whole-repo “benign.”
- [ ] Optional `pipeline.py` (or equivalent) returns the report object Agent B mounts — **no** FastAPI routes required from you.

---

## Rough effort share

~11–18 engineer-hours of MVP core (S01–S05, S07–S09). Matches Agent B’s surface + gates load (~10–16h). Stay off B’s files so both can run concurrently after S02.
