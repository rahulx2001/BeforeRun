# BeforeRun

BeforeRun reviews pinned public GitHub source as data, focusing on root npm setup and
optional comparison with an independently pinned baseline. It never clones, installs,
imports, or executes the submitted repository. The browser uses the application's
owned jobs API; the server owns the private OpenClaw route.

This is an **offline development candidate**. The source/context/tools/report pipeline,
jobs API, comparison, cancellation, inert rendering, and browser workflow have mocked
tests. The retained live text smoke failed; effective Gateway isolation, successful
Kimi/Cerebras delivery, checked live citations, usage/cost, and model quality are not
established. New reviews remain disabled by default. `/health` reports process liveness.

The local scope is one public repository root, optional same-repository baseline,
`review_only` or root `npm_install`, and one application process with ephemeral jobs.
Workspaces, registry dependencies, downloaded/native payloads, private repositories,
hosted admission, install guards, and whole-repository safety are outside this MVP.

## Local development

Use Python 3.12 or newer and the pinned dependencies in `requirements-dev.lock`.
The prepared environment can run `make check` and `make browser-check`; the latter uses
installed Chrome with mocked APIs. `make dev` starts the local app on loopback with
reviews disabled. Installation and real Gateway/model requests remain separate
operator actions; no install, publication, or live request is performed by this snapshot.

See [LOCAL_RUNBOOK.md](docs/LOCAL_RUNBOOK.md) for commands, processing limits, retention,
and operator enablement. The exact state of the release gates is recorded in
[RELEASE_GATES.md](docs/RELEASE_GATES.md), the failed run in
[LIVE_PROOF_TEMPLATE.md](docs/LIVE_PROOF_TEMPLATE.md), and the read-only route findings in
[LIVE_ROUTE_DIAGNOSIS.md](docs/LIVE_ROUTE_DIAGNOSIS.md).

## Offline demonstration

Open [the fixture storyboard](docs/demo/index.html) locally. Its four frames show the
real interface over saved mocked responses: input, a partial report/comparison, an inert
source excerpt, and coverage/processing limits. Synthetic evidence IDs, validation flags,
and duration are labeled. This demonstration is not a live inference or malware evaluation.

## Attribution and license

BeforeRun is inspired by [Gatekeeper by lb2002](https://github.com/lb2002/gatekeeper).
The recorded S07–S13 implementation introduces no copied Gatekeeper application modules
and makes no claim of upstream endorsement. Prior contributions and any incorporated
material still require owner provenance confirmation.

[DEPENDENCY_NOTICES.md](docs/DEPENDENCY_NOTICES.md) inventories the pinned environment;
dependencies and operator tools are referenced, not bundled. BeforeRun's project license is
[Apache-2.0](LICENSE), selected by the owner; attribution is recorded in [NOTICE](NOTICE). See
[RELEASE_LICENSE_REVIEW.md](docs/RELEASE_LICENSE_REVIEW.md).

This snapshot has no inherited Git history, personal assistant state, installed environment,
Gateway configuration, credentials, or raw provider logs. It is not a public release.

## Approved provider fallback

The current source supports disclosure of the owner-approved native OpenClaw fallback:
Cerebras is primary, with Muse Spark Open (`meta-models/muse-spark-open-1026`) on Baseten
for eligible provider failures. Configured policy is shown in capabilities, job metadata,
exports and the UI; actual upstream identity remains unverified. The private credentials
and Gateway configuration are operator-owned and excluded from this source snapshot.
See [BASETEN_GATEWAY_SETUP.md](docs/BASETEN_GATEWAY_SETUP.md). Live inference still requires
verified free eligibility under the current authorization.
