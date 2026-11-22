# Report integration limit for Agent A

The S13 proof-runner tests found a report construction limit for custom response-model
identifiers. `Settings.openclaw_expected_model` accepts identifiers up to 160 characters,
but `Settings.model_route` combines that identifier with route/explanation text, and
`Report.model_route` is constrained to the 128-character `VersionText` contract.

A 32-character custom identifier can therefore be accepted by the client and still fail
report construction. The default `openclaw/beforerun-reviewer` expectation used by this
candidate fits the contract. The proof-runner custom-identity test uses a shorter valid
identifier and separately verifies hashed/redacted output and model mismatch rejection.

Suggested Agent A fix: keep the report's configured-route identifier within the contract
and put the upstream-verification explanation in a separate display field, or deliberately
align the shared contract limits. Add a regression with the longest supported expected
identifier. This release work did not modify Agent A settings/contracts/report code.

Do not configure a longer custom response identity and claim a checked end-to-end report
until that integration is fixed. Successful client response matching alone remains weaker
than independent successful upstream-model evidence.
