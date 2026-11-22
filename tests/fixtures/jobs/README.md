# Job/API fixtures

`checked_result.json` is a human-authored, inert checked-report façade fixture used before
SYNC-2. It is not an OpenClaw response, provider transcript, malware sample, or live report.

- Case ID: `UI-API-INERT-001`
- Synthetic source identity: `example/inert-fixture`; target `aaa…`, baseline `bbb…`
- Context: root `npm_install`; static relationship is inferred, not executed
- Finding: simulated concern plus HTML-like source used to challenge safe rendering
- Expected assessment/completion: `suspicious` / `partial`, with an unresolved required file
- Comparison: modified helper with distinct target/baseline evidence IDs and original lines
- Benign alternative: all behavior is fixture text; no real outgoing operation occurs
- Required omissions: dependencies, downloaded payloads, native content, runtime control flow
- Expected model usage: zero attempts/tokens; no Cerebras/OpenClaw request

The fixture intentionally exercises independent assessment, completion, coverage, and comparison
fields. It must never be served as production fallback output or described as live model evidence.
