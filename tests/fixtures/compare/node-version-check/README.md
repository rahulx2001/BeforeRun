# Safe demo packaging

No public demo repository, video, or social post has been created or published.

For a local compatibility demonstration, use `../compare/node-version-check/` with two pinned
synthetic revisions. The only behavior change is the required Node major (20→22). Neither side
is executed. The expected story is "a harmless compatibility change behind an unchanged prepare
hook," never "malware found." A real future review still requires Agent A's checked pipeline and
the live G4 gate; the JSON job fixture cannot substitute for that investigation.

If a report demo uses `../jobs/checked_result.json`, label it prominently as a **mocked UI/API
fixture with zero model calls**. Its HTML-like text tests inert rendering; its simulated concern
does not show data theft, infection, detection recall, or upstream model identity.

Any edited, time-compressed, or replayed recording must be labeled. A video segment is not a scan
latency measurement. Publication, repository creation, posts, and submission need explicit user
authorization and a final license/secret/attribution review.

## S06 comparison checkpoint — 22 November 2026

The existing comparison implementation was extended, without changing Agent A's source,
snapshot, evidence, contracts, or budgets. Jobs, routes, and the browser were inspected and
preserved. The review pipeline remains unavailable in production and faked only in tests;
SYNC-2 has not been completed.

For a selected entry/helper scope, call
`materialize_comparison(snapshot, ledger, compare_inventories(snapshot), relevant_paths)`.
Include the unchanged entry and unchanged helpers in `relevant_paths` when they support a
behavior or context comparison. With no selection, only changed entries are fetched. Both
sides retain separate file/evidence IDs even for identical commits or cached bytes. Issued
evidence is not a delivery receipt or a validated behavior claim.

Use `compare_inventories(snapshot, baseline_requested=True)` when intake requested a baseline
but resolution did not produce one. Omitting a baseline intentionally still gives a target-only
review. Missing inventory markers fail closed; missing paths in incomplete inventories have
`change: unknown` rather than proving addition/removal. A simultaneous object/mode change keeps
`change: modified` and `mode_changed: true`.

`evidence_complete` describes the selected original-side representations, independently from
`complete_within_inventory`. Unread or clipped counterparts retain useful evidence and populate
`evidence_gaps`. Unread counterparts are never diffed as empty files. Diff matching admits at
most 12 KiB and 160 lines per side; output is capped at 12,000 UTF-8 bytes and 200 rows plus a
limit notice. Larger source keeps a bounded original-side excerpt and an explicit omission
notice. Output clipping sets `diff_limited` independently of source completeness. Diff text
uses the evidence module's best-effort redaction and never supplies virtual source links.

Behavior labels in `../cases.json` are human-authored expectations for Agent A's eventual
validator: existing behavior, changed entry context, removed behavior, and unknown counterpart
scope. S06 tests exercise the evidence/inventory plumbing needed for those cases; they do not
establish semantic validation, npm reachability, malware detection, or live model quality.

Checks actually run:

- Comparison tests: **27 passed**, including a mocked-HTTP shared-budget test and guards that
  fail on real socket connections or process launches.
- Existing API/UI tests: **11 passed** with the installed Node **24.22.3** selected on PATH.
  These UI tests check static DOM contracts and JavaScript syntax, not a real browser session.
- Ruff lint and format checks on `compare.py` and `test_compare.py`: passed.
- Full offline pytest suite: **133 passed, 17 failed**. Failures are in the existing
  `test_github_source.py`, `test_intake.py`, and `test_snapshot.py`; no Agent A file was edited.
- `make check`: compilation passed, then stopped on **33 existing lint errors** outside S06.
  The separate full format check also found five existing unformatted Agent A files/tests.
- The default Node 25 failed on its missing Homebrew `simdjson` library. Node 24 worked;
  no installation or environment configuration was changed.

Agent A handoff: source tests expose injected-client header handling, ambiguous metadata types,
malformed commit shapes, unissued blob syntax, URL/ref controls and normalization differences.
Snapshot tests expose restored completeness after a second registration, missing binary hashes,
and a broken empty-file fixture (followed by a BOM expectation that also needs reconciliation).
These source prerequisites and SYNC-2 remain release blockers. Existing lint defects in the
jobs/service/routes and the app import belong to a later Agent B checkpoint, not this S06 edit.

Next Agent B stage: **S10**, finish the existing jobs API's expiry/restart and queue/cancellation
coverage with mocked checked reports. Keep the pipeline stubbed until Agent A supplies SYNC-2.
No live GitHub/model call, credential changes, install, publication, or push was performed.
