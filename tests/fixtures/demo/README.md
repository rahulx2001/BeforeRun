# Offline development demo

This package is fixture-only. It contains no live malware, real credential collector,
network sender, destructive operation, persistence mechanism, or usable encoded payload.
No repository was published and no recording was submitted.

- `core_matrix.json` maps the master plan's 27 cases to development contract regressions.
  Tests overlap across cases; neither 27/27 nor the underlying test count is malware accuracy.
- `run_gates.py` saves actual mapped pass/fail/skip/not-run outcomes with release readiness false.
- `measure_mock.py` runs five repetitions by default through the real source/context/tools/
  investigation/report code with both HTTP adapters mocked. The helper is withheld from seeds.
  Timings are mocked pipeline timings, not actual GitHub/model latency or provider benchmarks.
- The real browser test uses `../jobs/checked_result.json`, visibly labeled as mocked. Its
  simulated concern and HTML-like text challenge rendering and independent completion labels.

These fixtures were used during implementation; independent human-reviewed/held-out model
evaluation is not established. The Node 20→22 source comparison is a benign compatibility
story, not malware discovery. Any future replay/video must show “mocked fixture” or “simulation”
as applicable and state actual timings. Live model identity and quality remain separate gates.
