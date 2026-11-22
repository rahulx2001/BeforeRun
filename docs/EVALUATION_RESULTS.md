# Evaluation results — fixture-only, no live model

**Date:** 22 November 2026  
**Status:** Offline product/contract measurements only. This is not a malware benchmark,
not a model-quality evaluation, and not evidence of real-world detection accuracy.

## Corpus actually run

- Pinned comparison tests using the fictional Node 20→22 helper fixture. The hook is
  unchanged, the helper is modified, and both original-side representations are checked.
  Missing counterpart evidence makes comparison coverage incomplete rather than proving novelty.
- Mocked checked-job API/UI tests using `tests/fixtures/jobs/checked_result.json`.
  Its concern and HTML-like text are synthetic; `model_attempts` is zero. No network sender,
  credential collector, destructive action, persistence mechanism, or executable payload exists.
- Contract tests supplied by Agent A for intake, budgets, source bounds, and evidence.
- Static DOM/API assertions plus Node syntax checks and a real Chrome DOM run with mocked
  application APIs and a fresh temporary profile; this is not a live API/model review.
- The 27 master-plan cases are mapped to development regressions in `CORE_GATE_RESULTS.json`:
  27/27 mapped cases passed through 54 selected tests. Cases overlap and were used during
  implementation; this is not independent human-reviewed/held-out evaluation or accuracy.
- The actual source/npm/tools/investigation/report pipeline ran with both HTTP adapters
  mocked. One relevant helper body was withheld from seeds and requested through a tool.

## Measurements and usage

`MOCK_MEASUREMENTS.json` records five mocked pipeline repetitions, their actual wall times,
transport request counts, versions and a source fingerprint. All five returned scoped benign,
complete fixture reports. These are pipeline-only mocked timings, excluding queue, browser,
network and real inference time. Mock usage fields are not billable provider usage.

No cold/cached live review, repeated real inference, provider tokens/cost, p95, accuracy, recall,
or controlled provider/hardware comparison was measured here. Live cost, latency and quality
are **unknown**. Final check evidence is summarized in `S07_S13_BUILD_RECORD.md`; earlier runs
are not cumulative latency measurements.

## Interpretation limits

Passing mocked routes proves only the tested jobs/report contracts. Passing source contracts does
not prove detection. The Node fixture demonstrates comparison plumbing, not malware discovery.
The simulated concern must never be called confirmed malware or evidence that secrets were stolen.
Abstentions, missing model access, unrun cases, and release-gate failures remain counted as blockers,
not removed from an accuracy denominator. See `RELEASE_GATES.md`.
