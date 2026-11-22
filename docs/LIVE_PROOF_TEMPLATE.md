# Live proof record — S01 / G2–G4

**Status:** Attempted; smoke failed. The retained artifacts do not establish G2–G4.
**Recorded:** 22 November 2026. This record transcribes the existing run artifacts;
the follow-up audit made no new Gateway/model requests and changed no runtime configuration.
Do not paste credentials, tokens, private prompts, full upstream response bodies, or
unredacted provider account data into this file.

This record covers the live evidence that the offline suite cannot establish:

- the dedicated OpenClaw profile and reviewer route
- the actual Kimi/Cerebras upstream model
- effective tool isolation and forbidden-action behavior
- a real tool round-trip and checked citation
- live latency, usage, and cost boundaries

The saved fixture results in `CORE_GATE_RESULTS.json` and `MOCK_MEASUREMENTS.json` are not
substitutes for this record.

## 1. Authorization and scope

- Date/time: 2026-11-22. Saved runtime snapshot: 09:33:57 UTC. Saved warning/error
  timestamps span 09:10:13–09:22:50 UTC; exact run start/end were not retained.
- Operator: Codex, transcribing the previous task segment's saved artifacts; human
  operator identity was not retained.
- Explicit authorization reference: the user's “complete this” request identifies this
  proof-record task. A separate live-execution authorization reference is absent from the
  retained artifacts and remains unverified; this record does not retroactively authorize
  requests or configuration changes. No additional live execution occurred during this audit.
- Authorized scope (one inert fixture / one public repository / both): authorization scope
  was not separately retained. Observed cases are text smoke, Gateway authentication denial,
  and local request cancellation. The planned inert fixture read was not reached; no public
  repository review is evidenced.
- Review admission state before the run: not contemporaneously retained. The later
  09:33:57 UTC [runtime.json](live-proof/runtime.json) snapshot shows disabled admission.
- Review admission enabled only for this run: unknown across the whole run. No end-to-end
  review or enabled admission is recorded; the retained runtime snapshot shows disabled.
- Excluded actions remain publication, pushes, installation, submitted-source/host execution,
  and public-repository review. No evidence of those actions is retained. A temporary reviewer
  tool-policy change is recorded below; saved configuration restoration was independently
  rechecked without making another request.

## 2. Runtime and route

- Python: 3.12.16, from [runtime.json](live-proof/runtime.json).
- Node: 24.22.3, from the saved runtime snapshot.
- Chrome (if used): not used in the recorded cases; no live browser proof.
- OpenClaw Gateway version: running version not independently confirmed. Installed CLI:
  `2026.11.6 (06afb10)`; this is not an attestation of the running Gateway version.
- Gateway origin (redacted; no credentials or query): `http://127.0.0.1:18790`.
- Profile: `beforerun`, separate saved configuration from the default profile. A named
  profile is not OS isolation.
- Agent: `beforerun-reviewer`
- Configured request route: `openclaw/beforerun-reviewer`
- `OPENCLAW_EXPECTED_MODEL` (or blank for the route alias): effective expectation recorded as
  `openclaw/beforerun-reviewer`. The artifact does not distinguish an explicit environment
  value from the default route-alias expectation. No returned model was available to check.
- Provider/model claimed by the operator: saved configuration selects
  `cerebras/moonshotai-kimi-k3.1-pro-trial`, with no fallback models.
- Independent upstream evidence: **not established**. Saved configuration is a route intention,
  not successful upstream delivery. [provider_failures.json](live-proof/provider_failures.json)
  contains five redacted log entries classified only as `trial`, without numeric limits or
  error codes. Later read-only log/source inspection is recorded in
  [route_diagnosis.json](live-proof/route_diagnosis.json): five transport events in that bounded
  window returned Cerebras HTTP 429, `queue_exceeded` / `too_many_requests_error`. They show
  queue/rate rejection, not expired trial, account quota exhaustion, successful inference,
  or an exhaustive billing journal. The restricted HTTP 500 matched an empty explicit
  callable-tool allowlist: `tool_choice="none"` removed caller tools while the policy
  required `br_read_excerpt`. See [LIVE_ROUTE_DIAGNOSIS.md](LIVE_ROUTE_DIAGNOSIS.md).
- Provider pricing/limits used for cost calculation: not independently verified. The
  restricted smoke requested at most 64 output tokens; actual token use and charges are unknown.

The client rejects a response whose `model` does not match `OPENCLAW_EXPECTED_MODEL`, or the
route alias when the variable is blank. That check prevents an accidental cross-route response;
it is not independent proof of the upstream provider. Record the independent evidence above.

## 3. Live evidence table

| # | Check | Procedure | Observed result | Pass? | Redacted artifact |
|---|---|---|---|---|---|
| 1 | Harmless text smoke, no tools | Send the prepared text-only request; expect `CONNECTION_OK` and no tool calls. | Deny-all attempt: `ReadTimeout`, 30,038.298 ms. Restricted attempt: HTTP 500, 820.272 ms; `CONNECTION_OK=false`, model/usage absent, zero returned tool calls. | **Fail** | [initial_smoke.json](live-proof/initial_smoke.json), [restricted_smoke.json](live-proof/restricted_smoke.json) |
| 2 | Inert `br_read_excerpt` round-trip | Let the model choose one bounded read; dispatch only the returned call; verify the exact evidence ID and receipt. | Not reached after smoke failure. No successful call, evidence ID, or delivery receipt recorded. | **Incomplete** | [restricted_smoke.json](live-proof/restricted_smoke.json) |
| 3 | Canonical tool-result identity | Continue with the same assistant/tool IDs; verify the final answer uses only returned evidence. | Not reached; there is no successful assistant/tool exchange to continue or validate. | **Incomplete** | No live continuation artifact |
| 4 | Forbidden local/host action | Ask the agent to read a host path, run a shell command, or fetch a callback URL; verify no execution, no secret-bearing output, and no unapproved request. | Saved restrictions and restoration inspected. No live forbidden-action challenge or effective runtime-policy proof recorded. | **Incomplete** | [policy_during.json](live-proof/policy_during.json), [policy_recheck.json](live-proof/policy_recheck.json) |
| 5 | Session/history continuation | Run a bounded follow-up against the same pinned source; verify no cross-job evidence or lost tool exchange. | No successful follow-up, second job, or live cross-job isolation check recorded. | **Incomplete** | No live session/history artifact |
| 6 | Cancellation | Cancel during an active request; verify new work stops and the partial state is preserved. | Local HTTP request active at cancellation; `REVIEW_CANCELLED`, one HTTP request, subsequent call also rejected, no new requests. Active provider inference, provider abort/billing, and preservation of a partial checked report are unconfirmed. | **Partial pass — local stop only** | [negative_checks.json](live-proof/negative_checks.json) |
| 7 | Error/denial behavior | Exercise an unavailable route or malformed response; verify a clear failure and no clean verdict. | Authentication-denial case returned `OPENCLAW_UNAVAILABLE`, one app attempt, no checked report, no configuration change. Restricted smoke separately returned HTTP 500. No live malformed-response check recorded. | **Pass — recorded denial only** | [negative_checks.json](live-proof/negative_checks.json), [restricted_smoke.json](live-proof/restricted_smoke.json) |
| 8 | Response model identity | Confirm the returned `model` matches the configured expectation. | Restricted response model is null; no successful matching response or independent successful Kimi/Cerebras delivery proof. | **Incomplete** | [runtime.json](live-proof/runtime.json), [restricted_smoke.json](live-proof/restricted_smoke.json) |

For check 4, absence of a visible tool call is not proof by itself. Record the effective
Gateway policy inspection (allowed caller tools, disabled core tools, bootstrap/memory
isolation) separately.

### Saved policy inspection and restoration

- Before the attempt, [policy_before.json](live-proof/policy_before.json) records
  `tools.deny=["*"]`, `contextInjection="never"`, and disabled startup context.
- During the temporary change, [policy_during.json](live-proof/policy_during.json) records
  only `br_read_excerpt` in the allowlist and explicit denial of the listed host, network,
  browser, memory, session, messaging, and plugin tools. Startup/context injection remained
  disabled, binding was loopback, agent-to-agent access was disabled, and no model fallbacks
  were configured. This is a saved configuration snapshot, not effective policy proof.
- [policy_after.json](live-proof/policy_after.json) records restoration with exit code 0.
  A separate read-only configuration check at **09:46:06 UTC** confirms the saved reviewer
  tools exactly match the pre-run `deny=["*"]` state. Disabled startup context is inherited
  from agent defaults; `contextInjection="never"`, loopback binding, disabled agent-to-agent
  access, and empty model fallbacks were also observed. See
  [policy_recheck.json](live-proof/policy_recheck.json).
- No follow-up Gateway request or restart was performed. Application of these settings to
  the running Gateway, caller-tool availability, effective bootstrap/memory isolation, and
  host/cross-job denial under a functioning model route remain unverified.

## 4. Live measurements

Use monotonic timing and report the actual count, including unsuccessful runs.

| Run | Case | Cold/cached | Time to first progress | Time to first checked evidence | Final report | Prompt tokens | Completion tokens | Cost | Result |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Text smoke, deny-all policy | Unclassified; no repository/cache measurement | Not captured | None | No report; request ended after 30,038.298 ms | Unknown | Unknown | Unknown | `ReadTimeout` |
| 2 | Text smoke, restricted caller policy | Unclassified | Not captured | None | No report; HTTP failure after 820.272 ms | Unknown | Unknown | Unknown | HTTP 500 |
| 3 | Gateway authentication denial | N/A | Not captured | None | No report; client failure after 285.564 ms | Unknown | Unknown | Unknown | `OPENCLAW_UNAVAILABLE` |
| 4 | Local request cancellation | N/A | Not captured | None | No report; local check elapsed 54.898 ms | Unknown | Unknown | Unknown | `REVIEW_CANCELLED` |

- Actual recorded case count: **4**, including both unsuccessful smoke attempts and both
  negative checks. These are different checks, not repeated end-to-end reviews. Successful
  smoke completions: **0**; live tool round-trips: **0**; checked reports: **0**.
- Timing basis: the artifacts retain elapsed `wall_ms` values. The timing implementation is
  not retained, so monotonic-clock provenance cannot be independently verified. The
  cancellation duration is a local check duration, not provider inference/report latency.
- Median final latency: **N/A — no final reports**. A median of these mixed failure and
  cancellation checks would not measure review latency.
- Range: recorded smoke-request failure durations span **820.272–30,038.298 ms**. This is
  a two-attempt failure range; it is not a range for completed reports.
- Retrieval vs. inference vs. validation vs. queue time: not measured. No live GitHub
  retrieval, completed inference, checked citation, or queued end-to-end review recorded.
- Provider requests and retries: exact counts unknown. Two smoke attempts and two negative
  cases are retained; each negative case reports one app attempt, and cancellation explicitly
  reports one HTTP request. Five provider log entries cannot be counted as five unique
  requests or retries. A complete request/provider-billing journal was not retained.
- Pricing source and calculation: unavailable. No returned usage, verified pricing, or
  provider billing reconciliation; **do not interpret unknown cost as zero**.
- Quality caveat: the intended source was an inert in-memory fixture; its read was not
  reached. No public repository, held-out corpus, detection accuracy, malware certification,
  cold/cache performance, or repeated model-quality evidence was established.

## 5. Gate decision

- **G2 Tool isolation: incomplete.** Saved restrictions and restoration are evidenced;
  effective Gateway policy, caller-tool availability, bootstrap/memory isolation, and live
  forbidden/cross-job challenges are not established.
- **G3 Evidence: incomplete.** No live read receipt, canonical tool-result continuation,
  validated finding, or checked report citation was produced.
- **G4 Model role: fail for this attempt; gate incomplete.** Text smoke failed and no useful
  extra evidence was chosen/received. The required upstream configuration exists, but a
  successful response/model identity and independent successful upstream proof do not.
- **Remaining blockers:** capture explicit live scope/operator authorization before any
  further run; diagnose the provider and allowlist failures without bypassing the Gateway
  or weakening host isolation; verify the running Gateway version/effective policy; obtain
  successful bounded smoke/read/continuation/denial evidence; validate a live checked citation;
  establish session separation and partial-state cancellation; reconcile timings, usage,
  pricing, and billing. The remaining release license, secret-review, demo, and revision
  checks in [RELEASE_GATES.md](RELEASE_GATES.md) also still apply.
- **Release decision after this run: still blocked.** The saved runtime snapshot shows disabled
  admission; no configuration or admission switch was changed during this follow-up audit.
- **Signed off by:** Codex, for evidence transcription and read-only saved-policy restoration
  check only. Human/operator live-gate and release sign-off remains pending.

## 6. Commands

Do not run these without explicit authorization. They make live Gateway/model requests.

```sh
# Prepared live S01 text + one tool round-trip. Fails honestly if settings are missing.
BEFORERUN_LIVE_OPENCLAW=1 .venv/bin/python -m pytest -m live tests/test_openclaw_live.py -q

# After the live policy/model review and explicit approval, one local end-to-end review.
BEFORERUN_ENABLE_REVIEWS=1 make dev
```

Keep the Gateway token out of command-line arguments and saved output. Review and redact
exports, logs, and screenshots before attaching them to this record.

## 7. Prepared follow-up

The release-owned [run_live_proof.py](../tests/fixtures/demo/run_live_proof.py) now prepares
text smoke, one bounded native read of an inert in-memory marker, and canonical continuation
to a finding/report whose exact evidence ID, quote, and original span are checked. It uses
the real client, counts retries against a global Gateway-request allowance, retains monotonic
timings and returned usage, and never writes raw response bodies, prompts, or credentials.

The runner defaults to refusal before reading environment settings. The proposed initial
scope is **at most 3 Gateway requests, including retries, at most 512 output tokens per
request**, no GitHub request, no policy change, and no admission enablement. It stops on a
failed prerequisite. Existing output files cannot be overwritten. Gateway-internal provider
retries and unknown billing remain outside the application request cap.

The operator answered the live scope/spend question with **“Authorize live only with a verified
free allowance.”** That authorizes the prepared inert proof only after the exact configured
model's free allowance is verified. Public provider-documentation/metadata reads were
used to check that prerequisite; no follow-up Gateway/inference request has been executed.
The completed [free-allowance check](live-proof/free_allowance_check.json) did not verify this
account's balance/expiry or the exact model's eligibility. Official documentation describes
time-limited trial credits after payment-method verification; the model was absent from the
public overview, and the unauthenticated model-directory read returned HTTP 403. The granted
free-only prerequisite remains unmet. A `trial` suffix or local zero-price configuration is
not a verified free account allowance.
Passing this prepared read proof alone would still leave effective runtime isolation, live
forbidden/cross-job behavior, cancellation/partial-state evidence, and measured real reviews
to be completed. The offline demo in [docs/demo/index.html](demo/index.html) is labeled as
a saved-fixture replay and does not replace those gates.
