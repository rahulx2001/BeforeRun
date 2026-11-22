# MVP release gate record

**Date:** 22 November 2026  
**Scope assessed:** public GitHub root intake, root `npm_install` / `review_only`, optional
same-repository baseline, local single-process jobs and browser surface.  
**Release decision:** **BLOCKED. Do not enable public reviews or claim a working scanner.**

This record distinguishes executed offline checks from the failed, incomplete live proof
recorded in [LIVE_PROOF_TEMPLATE.md](LIVE_PROOF_TEMPLATE.md). A mocked
checked report validates the product surface, not OpenClaw/Kimi quality or malware detection.

| Gate | Current result | Observable evidence and remaining blocker |
|---|---|---|
| G1 Source boundary | **PASS — offline scope** | Fixed-origin pinning, object/tree identity, cache provenance, modes, source/envelope limits and adversarial intake pass the source suite. No live retrieval was performed here. |
| G2 Tool isolation | **PASS backend / live gate incomplete** | All seven dispatchers have negative ownership/argument/process/network tests. Live artifacts record restrictive saved configuration and restoration to deny-all; a read-only recheck confirms the saved policy. Effective installed-Gateway caller-tool allowlisting, bootstrap isolation, and forbidden-action behavior remain unverified. |
| G3 Evidence | **PASS offline / live gate incomplete** | Connected validator checks delivered source identities, exact spans/quotes, derived parents, entry paths and qualified comparison. Live smoke failed before any successful tool round-trip, delivered citation, or checked report. |
| G4 Model role | **FAILED live attempt / gate incomplete — release blocker** | Initial text smoke timed out; a second restricted-policy smoke attempt returned HTTP 500 with no response model or usage. The retained artifacts establish no successful Kimi/Cerebras delivery, live tool choice, or independent upstream identity proof. The configured route and response-model assertion do not establish successful upstream delivery. See the live proof record for redacted artifacts and limitations. |
| G5 Behavior honesty | **PASS development contracts / quality unmeasured** | `CORE_GATE_RESULTS.json` records 27/27 mapped offline case passes. No-op/unused-text and unsupported-trigger policies are tested; independent held-out or live interpretation quality is not established. |
| G6 Failure policy | **PASS offline / limited live negatives** | Mixed findings, empty/partial/cancelled results, retained checked material, shared limits, queue races, expiry/restarts and bounded repair/retries pass offline. Recorded live denial created no checked report; local cancellation stopped new requests. Active provider inference, upstream abort/billing, and live partial-report preservation remain unconfirmed. |
| G7 Interface/operation | **PASS offline workflow / live release pending** | Checked pipeline through mocked HTTP, owned API, real Chrome DOM, input/focus/mobile/reset/stale/cancel/events and sanitized exports pass. Apache-2.0, product/dependency notices, four reviewed offline demo frames, and a private-state-excluding product scope are prepared. Existing Git history contains removed private state and must not be published. Live operation and final release sign-off remain pending. |

## Enabled behavior while blocked

- The UI and `/api/capabilities` expose `review_enabled` independently of process liveness.
- New submissions fail closed unless `ReviewService.reviews_enabled` is explicitly enabled.
- Test pipelines opt in locally and use only inert fixtures. Production has no mocked-report
  fallback and no direct Cerebras route.
- `/health` means only that the application process responds; it never means scanner readiness.

## Remaining evidence before re-evaluation

- [x] Transcribe the attempted live run and saved-policy restoration evidence in
      [LIVE_PROOF_TEMPLATE.md](LIVE_PROOF_TEMPLATE.md); record failures without claiming passing gates.
- [x] Prepare the real-client inert proof runner and offline refusal/citation/bounds tests.
- [x] Record the operator's conditional authorization: live only with a verified free allowance.
- [ ] Verify that free allowance for the exact configured model/account before any inference.
      [free_allowance_check.json](live-proof/free_allowance_check.json) records the unmet prerequisite.
- [ ] Complete the remaining live proof checks within that approved scope and allowance.
- [ ] Record the dedicated profile, Gateway version, response model, and independent
      Kimi/Cerebras evidence.
- [ ] Run the live S01 text smoke and inert tool round-trip; record forbidden-action and
      session/history results.
- [ ] Run one live end-to-end review and validate its checked citations.
- [ ] Record real cold/cached latency, token usage, cost, and quality limits.
- [x] Apply owner-selected Apache-2.0 and product NOTICE; inventory dependency licenses/notices.
- [x] Review the local product text, saved proof artifacts, offline recording and original
      history paths. Existing-history publication is blocked; candidate scope excludes it.
- [x] Record an accurately labeled [offline fixture storyboard](demo/index.html).
- [x] Freeze a separate local offline candidate and rerun its full offline/browser checks:
      **316 offline tests + 1 Chrome test passed** against commit `b443a5d9f248`.
      See [CHECKPOINT.json](release-candidate/CHECKPOINT.json). This is not an enabled release.

## Exit criteria

Reevaluate every row against the real S01/live handoff and release revision. G2, G4, citation validity, false reassurance,
ownership leakage, and target execution are hard blockers. Narrow or disable failing surfaces;
do not hide failures behind demo text. Publication, submission, and live paid/model calls remain
separate explicit user decisions.

## Local release preparation

The prepared source snapshot excludes private assistant state, credential files, installed
environments, raw Gateway/provider logs, and inherited Git history. Its final manifest/check
and scoped screening records are retained separately from the self-hashed product files.
Public hosting, publication, pushes, and inference outside the verified free-only scope
remain unauthorized. Live latency, usage, cost and quality measurements are still incomplete.

The parentless local candidate ref is `refs/beforerun/offline-candidate-20261122-b443a5d9f248`.
Its archive contains 129 reviewed product files plus the generated manifest, with no inherited
Git history. The original branch/staging were preserved. Audit/checkpoint attachments record
post-commit verification separately from the frozen self-hashed content.

## Subsequent approved provider change

The owner subsequently authorized a native Baseten fallback for Muse Spark Open,
`meta-models/muse-spark-open-1026`, while preserving the Cerebras primary. Private setup
and schema validation are recorded in [BASETEN_GATEWAY_SETUP.md](BASETEN_GATEWAY_SETUP.md).
Configured-provider disclosure is included in API/job/export/UI surfaces. The earlier
checkpoint remains historical evidence for its exact pre-fallback tree.

Live G2–G4, provider/model eligibility, function-tool acceptance, actual failover and usage/cost
remain incomplete for the new provider path. A response using the reviewer alias cannot
prove Cerebras or Baseten upstream identity. User-requested fallback is approved configuration,
not permission to spend outside the existing verified-free-only live scope.
