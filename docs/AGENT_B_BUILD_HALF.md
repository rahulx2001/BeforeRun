# Agent B — Product surface, comparison, and release (Half 2 of 2)

**Updated: 22 November 2026.**  
**Sibling:** [AGENT_A_BUILD_HALF.md](AGENT_A_BUILD_HALF.md)  
**Authority:** [MASTER_BUILD_PLAN.md](MASTER_BUILD_PLAN.md) (this half is ownership only; do not contradict it)

**Your job:** Build commit comparison, the jobs API, the real review UI, safe demo fixtures, and the release/measurement gates — everything that turns Agent A’s checked report into a usable product.

**Partner:** Agent A owns intake → snapshot → evidence → npm context → tools → OpenClaw investigation → validation/report. You consume their contracts and (after SYNC-2) their pipeline façade.

---

## Copyable prompt for this agent

```text
Work in /Users/rahulkumarsinghj/Desktop/BeforeRun.

You are Agent B (Product surface & release). Read:
- docs/MASTER_BUILD_PLAN.md (authority)
- docs/AGENT_B_BUILD_HALF.md (your ownership)
- docs/AGENT_A_BUILD_HALF.md (do not edit Agent A core pipeline files)

Implement only Agent B stages and files listed in AGENT_B_BUILD_HALF.md.
Do not rewrite github_source, snapshot, evidence, npm_setup, signals, reachability,
safe_tools, openclaw_client, investigator, validate, or report unless fixing a
clear integration bug at a sync point — prefer filing the issue for Agent A.

Until Agent A finishes SYNC-2, stub the review pipeline behind an interface and build
jobs + UI against mocked checked reports. Keep the existing FastAPI/static scaffold.

BeforeRun reviews pinned public GitHub source as data. Never clone/checkout/install/import/execute
the submitted repository. Browser must never talk to the OpenClaw Gateway directly.
Use offline/mocked tests by default. Ask before installs, live model calls, credentials,
publication, or pushes.

At the end of each stage: list changed paths, checks run, blockers, and the next Agent B stage.
```

---

## Shared rules (both agents)

1. Master plan wins on tool names, result states, budgets, and safety.
2. Do not claim Agent A’s investigation modules are done.
3. Do not expand into section 23 roadmap (R1–R12) until MVP gates pass.
4. Sync only at the checkpoints below; otherwise stay in your file tree.
5. Prefer additive checkpoints per stage, not one giant diff.

---

## You own these files

```text
src/beforerun/features/
  compare.py            # pinned inventory comparison (§18)
  job_store.py
  review_service.py     # orchestrates Agent A pipeline + jobs/cancel/events
  routes.py             # /api review endpoints (§16)

src/beforerun/
  app.py                # mount routes only; keep /health honest
  cli.py                # later review/export subcommands when stage allows

src/beforerun/static/
  index.html            # enable form only when wired to real jobs
  styles.css            # report states as needed
  shell.js              # leave theme/shell behavior intact unless required
  reviews.js            # form, poll, reset, cancel, render, export

tests/
  test_compare.py
  test_review_api.py
  test_ui_review.py     # if/when browser tests are added
  fixtures/compare/     # Node 20→22 helper story, etc.
  fixtures/jobs/        # recorded job/event payloads
  fixtures/demo/        # public demo packaging (§21)

docs/ (ops you may update when your stage says so)
  IMPLEMENTATION_RECORD.md   # append your stage notes
  # measurement / attribution updates only in S13
```

**Do not own (Agent A):** `github_source.py`, `snapshot.py`, `npm_setup.py`, `signals.py`, `reachability.py`, `evidence.py`, `safe_tools.py`, `openclaw_client.py`, `investigator.py`, `validate.py`, `report.py`, and their dedicated unit tests.

**Contracts:** Import Agent A’s `contracts.py` / `settings.py` / `budgets.py`. You may add **job / API / UI-only** fields in clearly separated models. Do not silently rename Agent A evidence or finding fields.

---

## Master-plan sections to read (in order)

| Priority | Sections | Why |
|---|---|---|
| Required | 1–9, 7 | Product + non-negotiable controls |
| Required | 13 (report shapes), 16–18, 19 | Jobs, UI, compare, budgets |
| Required | 20–21, 22 stages S00, S06, S10–S13 | Tests, fixtures, your stages |
| Required | 24–28 | Deploy, ops, measure, release |
| Skim | 10–15 | Know what Agent A delivers into your service |
| Use | 30 | Stage brief template |

Skip implementing: OpenClaw setup/tools/investigator/validation core (A). You only integrate.

---

## Your stages (do in order)

| Stage | Effort | Deliverable |
|---|---|---|
| **S00** | 15–30m | Shared with A: inspect git, secrets, scaffold checks. Coordinate who writes the decision-record bullets. |
| **Parallel early** | 1–2h | Fixture layout (§21), harmless compare story scaffold, OpenAPI/route stubs, UI against **mocked** job JSON. |
| **Wait** | — | Do not implement real compare until **SYNC-1** (Agent A snapshot + evidence APIs). |
| **S06** | 1–2h | `compare.py` + benign Node 20→22 helper case; tests for existing/changed/removed/unknown. |
| **S10** | 1–2h | `job_store.py`, `review_service.py`, `routes.py`; mount in `app.py`. Stub pipeline until SYNC-2. |
| **SYNC-2** | — | Replace stub with Agent A `pipeline` / report entry. One end-to-end mocked review. |
| **S11** | 90–150m | `static/reviews.js` + real form/status/events/evidence/compare/coverage. |
| **S12** | 3–4h+ | **Lead** the core gate matrix (§20); file defects to A or fix your surface. Freeze features. |
| **S13** | 2–3h | Measure, runbook, attribution, labeled demo — only with user authorization for publish/submit. |

Do **not** implement S01–S05, S07–S09 — those are Agent A.

---

## Sync checkpoints with Agent A

| When | You provide | You need from A |
|---|---|---|
| After their S02 | Job/API field proposals if any | Frozen Intake / Evidence / Finding / Report contracts |
| SYNC-1 | Nothing blocking | Snapshot maps + evidence issue API for `compare.py` |
| After S10 (stubbed) | Jobs API that accepts intake and returns mocked reports | — |
| SYNC-2 | Wiring + contract bug list | Callable checked/partial report pipeline |
| S12 | Gate run record, fail list | Fixes in A modules for A-owned failures |

---

## Mock strategy (so you are not blocked)

Until SYNC-2, `review_service` should call a narrow protocol, for example:

```text
ReviewPipeline.run(intake, budgets, cancel_token) -> CheckedReport | PartialReport | Failure
```

Ship a `FakeReviewPipeline` that returns fixture reports for UI/API tests. Swap in Agent A’s implementation at SYNC-2 without rewriting routes.

---

## Acceptance for Agent B half

- [ ] Compare explains unchanged hook + changed helper (Node 20→22 story) with original-side evidence.
- [ ] Jobs API: intake, status, events, evidence, cancel, export; ownership and admission limits enforced.
- [ ] Browser never reaches OpenClaw/Cerebras; only your `/api` surface.
- [ ] UI: submit, scoped report, evidence, comparison, coverage, cancel/retry, inert untrusted text.
- [ ] `/health` stays liveness — missing model access is not “scanner works.”
- [ ] S12 gate record exists with real pass/fail for enabled scope (G1–G7).
- [ ] S13 claims match measurements; no automatic publish.

---

## Rough effort share

~10–16 engineer-hours (early fixtures/UI stubs + S06 + S10–S13). Matches Agent A’s core pipeline load. After S02/SYNC-1 you can run fully in parallel with A’s S05/S07–S09 work.
