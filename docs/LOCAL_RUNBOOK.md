# Local prototype runbook

Use the already prepared environment. Do not replace `.env`, install submitted repositories,
start another user's Gateway, or enable public hosting to work around an integration failure.

## What works

The backend connects the public GitHub tree/blob reader, `NpmSetupAnalyzer`, `SnapshotTools`,
private OpenClaw adapter, investigator, reference validator, report policy, and owned jobs.
The browser talks only to `/api`; it never selects a Gateway, provider, model, or credential.
The assembled pipeline has an end-to-end test with both HTTP routes mocked.

`CheckedReviewPipeline.with_npm(settings)` supplies the real static analyzer.
`AnalysisProvider.analyze(intake, snapshot, ledger, budget)` remains the narrow dependency
interface; its `AnalysisContext` carries required files, seeds, relationships, assumptions,
signals and errors. Errors remain coverage gaps. `withhold_helper=True` is available for the
annotated integration fixture so a helper body must be obtained through a model-chosen tool.
It is not a separate detection rule or a production quality claim.

## Model identity check

The OpenClaw client requires every response to include a `model` value. It compares that
value with `OPENCLAW_EXPECTED_MODEL` when set, otherwise with
`openclaw/<OPENCLAW_AGENT>`. A missing or mismatched value is rejected. This blocks an
accidental cross-route response at the Gateway boundary; it does not independently prove
the upstream provider, so record separate provider/model evidence in the live proof.

## Start and check

From the project root, using installed Node 24 for local syntax checks:

```sh
PATH=/opt/homebrew/opt/node@24/bin:$PATH make check
PATH=/opt/homebrew/opt/node@24/bin:$PATH make dev
```

The UI is `http://127.0.0.1:8000`. `/health` is process liveness only.
`/api/capabilities` distinguishes connected pipeline code from `review_enabled`.
**Submissions are disabled by default even though the pipeline is mounted.** No paid model
request runs on startup or a health/capabilities poll. Do not flip the server-owned enablement
switch until the required live isolation/model/behavior gates are reviewed and authorized.

After that review and explicit approval, an operator can opt in for a local process with
`BEFORERUN_ENABLE_REVIEWS=1 make dev`. Only the exact value `1` enables admission. This is a
server environment switch, never a browser field; unset it to reject new jobs without
deleting existing reports. It is not an attestation that live gates passed. This build
did not set the switch or make any live source/model request.

Run the prepared browser test separately:

```sh
PATH=/opt/homebrew/opt/node@24/bin:$PATH make browser-check
```

It uses installed Chrome/Chromium, a fresh temporary profile, local application files,
mocked application APIs, disabled background networking, and blocked external DNS.
Chrome cannot launch inside this host's restricted command sandbox; run this specific test
with the approved execution scope. An unavailable browser is an unverified gate, not a pass.

## Prepared environment observed

Offline audit on 22 November 2026:

- Python 3.12.16
- Node 24.22.3
- Chrome 157.0.8103.79
- `pip check` clean
- OpenClaw CLI not found on `PATH`; record the running Gateway version in the live proof.

## Reproduce offline gates and measurements

```sh
PATH=/opt/homebrew/opt/node@24/bin:$PATH .venv/bin/python tests/fixtures/demo/run_gates.py --output docs/CORE_GATE_RESULTS.json
.venv/bin/python tests/fixtures/demo/measure_mock.py --output docs/MOCK_MEASUREMENTS.json --repeats 5
```

The case matrix is a development regression mapping, not an independent held-out evaluation.
Mock timings exclude actual GitHub/network/inference latency and queue/browser time. Request
counts are mocked transport observations. Mock usage fields do not establish billable tokens,
cost, upstream identity, accuracy, or a live additional read. See `EVALUATION_RESULTS.md`.

## Operating limits

- Run one application worker while jobs are in memory. Reload/restart loses jobs.
- At most one active review plus two queued reviews. Ephemeral records are capped at 128;
  TTL/capacity pruning removes app records, and expiry requests cancellation of active work.
- Idempotent repeats return the same admitted job; changed input under the same key conflicts.
- Cancellation stops new local work and closes local response streams. Provider abort/billing
  remains unconfirmed; clearing the UI does not erase provider transcripts or exports.
- Partial/failed/cancelled/unsupported results retain useful checked material and gaps.
  An empty incomplete result is `undetermined`, not a clean repository.
- Exports are explicit and best-effort sanitized. Review them before sharing.

## Before a live release

Complete [LIVE_PROOF_TEMPLATE.md](LIVE_PROOF_TEMPLATE.md) during the authorized run. Verify the
dedicated profile's effective policy and required Kimi/Cerebras route using the authorized S01
procedure. Record versions and a real additional helper read, correct tool-result identity,
forbidden-action rejection, cancellation, and error behavior. Set `OPENCLAW_EXPECTED_MODEL` to
the exact response model the Gateway returns, or leave it blank to require
`openclaw/<OPENCLAW_AGENT>`. Rerun gates after provider, model, tool-policy or source/validator
changes. Resolve publication license/notices and review release files/history/recording for
secrets before any deliberate publication. Public hosting, private repositories, package audits,
follow-ups and install guards remain outside this MVP. No external publication or submission is
performed by these commands.

## Prepared release follow-up

The read-only [route diagnosis](LIVE_ROUTE_DIAGNOSIS.md) identifies provider queue rejection
and a text-only/explicit-tool-allowlist mismatch in the retained failed run. It supports
preparing the existing deny-all reviewer policy without another configuration change; it
does not prove effective running isolation or successful inference.

The prepared `tests/fixtures/demo/run_live_proof.py` refuses execution without explicit
authorization and an authorization reference. The proposed initial run is capped at three
Gateway requests including retries and 512 output tokens per request, over one inert
in-memory fixture. It makes no GitHub request and never enables admission. Verify the
approved provider spend/limits separately; Gateway retries are not a billing cap.

The owner selected [Apache-2.0](../LICENSE); [NOTICE](../NOTICE) and
[DEPENDENCY_NOTICES.md](DEPENDENCY_NOTICES.md) record local attribution and dependency notices.
The [offline storyboard](demo/index.html) contains four reviewed saved-fixture frames.
Use `tests/fixtures/demo/prepare_candidate.py` with an output directory outside this workspace
to export the reviewed product scope. That snapshot excludes old Git history and private
assistant state. Do not publish this workspace's existing history: removed private files
remain reachable there. The local snapshot and demo leave live/release gates incomplete.

## Approved Baseten fallback

The owner requested Muse Spark Open (`meta-models/muse-spark-open-1026`) on Baseten as an
automatic fallback for the Cerebras primary. The dedicated Gateway's native model ladder
now includes `baseten/meta-models/muse-spark-open-1026`. BeforeRun keeps the same reviewer
alias and strict response/citation checks; it never contacts Baseten from the browser.

See [BASETEN_GATEWAY_SETUP.md](BASETEN_GATEWAY_SETUP.md) for the applied private setup,
configuration validation and activation limits. The application reads `OPENCLAW_FALLBACK_MODEL`
from its server environment to display the approved configured policy. An already running
app needs its normal local restart to read changed environment settings; no process was
restarted by this setup. Configuration presence does not attest to a successful live failover.

Native failover handles eligible provider authentication/billing, rate-limit and timeout
failures. Gateway authorization, cancellation, operator/session restrictions and local
terminal errors remain failure boundaries. The application does not add a provider bypass
or reset its request/token/deadline budgets. Internal retries still need billing review.

Baseten Model APIs are usage-priced; a saved key or provider metadata is not a verified free
allowance. The existing free-only live condition remains in force for either provider.
