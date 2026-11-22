# Core features

This package contains the implemented, offline-tested review pipeline:

- public GitHub URL/ref validation, commit resolution, and bounded source retrieval
- Node setup entry points and referenced helper inspection without execution
- optional comparison with a selected baseline commit
- evidence receipts, quote/span/revision validation, and derived provenance
- snapshot-only `br_` tools with ownership, argument, budget, and cancellation checks
- the bounded OpenClaw investigator and canonical tool transcript
- checked reports with separate assessment, completion, and coverage
- owned jobs, status/events/cancellation/export, and the browser review surface

Live OpenClaw/Kimi/Cerebras proof and the release gates remain pending. See
[RELEASE_GATES.md](../../../docs/RELEASE_GATES.md),
[LOCAL_RUNBOOK.md](../../../docs/LOCAL_RUNBOOK.md), and
[LIVE_PROOF_TEMPLATE.md](../../../docs/LIVE_PROOF_TEMPLATE.md).

No Gatekeeper application code has been copied. BeforeRun is inspired by Gatekeeper by
lb2002; see [ATTRIBUTION_DRAFT.md](../../../docs/ATTRIBUTION_DRAFT.md).
