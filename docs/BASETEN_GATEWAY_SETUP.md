# Baseten fallback through the private OpenClaw Gateway

**Prepared:** 22 November 2026. **Scope:** installed schema/source inspection and public
documentation reads only. This guide contains no credentials and performs no model request,
installation, service restart, or configuration mutation.

The user authorized Baseten as a fallback for the existing Cerebras reviewer and identified
the model as **Muse Spark Open**, `meta-models/muse-spark-open-1026`. It is distinct from
Meta's `muse-spark-1.3`; do not substitute the Meta provider or its credential.

## Provider endpoint and authentication

Baseten's current Model APIs use the OpenAI-compatible origin:

```text
https://inference.baseten.co/v1
```

Its official Chat Completions documentation shows ordinary OpenAI SDK `api_key` handling
and `Authorization: Bearer $BASETEN_API_KEY`. A custom `Api-Key` authorization header is not
needed for this endpoint. Some other Baseten deployment/management endpoints have different
contracts; this guide targets the Model APIs endpoint only.

Keep the key in server-owned private environment/secret storage. It must not appear in
`.env.example`, static JavaScript, saved proof bodies, exports, source commits, or command-line
arguments. The browser continues to call BeforeRun's `/api` endpoints; only OpenClaw contacts
Baseten.

## Minimal additive configuration

Merge the provider entry into the dedicated `beforerun` profile. Preserve every unrelated
provider, model, agent, tool, session, and credential setting. The snippet is a patch shape,
not a replacement for the whole configuration:

```json
{
  "models": {
    "providers": {
      "baseten": {
        "baseUrl": "https://inference.baseten.co/v1",
        "apiKey": "${BASETEN_API_KEY}",
        "api": "openai-completions",
        "models": [
          {
            "id": "meta-models/muse-spark-open-1026",
            "name": "Muse Spark Open",
            "input": ["text"]
          }
        ]
      }
    }
  },
  "agents": {
    "entries": {
      "beforerun-reviewer": {
        "model": {
          "primary": "cerebras/moonshotai-kimi-k3.1-pro-trial",
          "fallbacks": ["baseten/meta-models/muse-spark-open-1026"]
        }
      }
    }
  }
}
```

If that reviewer already has a different configured primary or other explicitly authorized
fallbacks, inspect and preserve them when merging rather than replacing unfamiliar work.
The `input: ["text"]` declaration limits the current BeforeRun scope; it is not a claim about
the model's full media capabilities. Context limits, output limits, reasoning capabilities,
pricing, and account eligibility are intentionally not invented. The installed model schema
requires only `id` and `name`; the other metadata fields are optional.

Installed OpenClaw 2026.11.6 lists its Baseten integration as an optional external provider
plugin. That plugin offers authenticated catalog discovery, but is not required for this
explicit custom OpenAI-compatible provider entry. No plugin install is part of this setup.

## Native fallback and activation

The installed native agent policy supports `agents.entries.*.model.fallbacks`. An agent's
primary is strict until its own model object supplies a non-empty fallback list. Adding the
list above keeps the Cerebras primary and lets native recovery advance to the configured
Baseten model on eligible provider failures. It does not require another reviewer agent or
an application-side direct-provider bypass.

Fallback is a Gateway decision and can vary by turn. Eligible rate-limit fallback stickiness
does not change the selected primary. Native provider retries/timeouts may consume the
application's shared deadline before fallback is reached; a configured list is not proof of
successful or immediate failover. User cancellation and the application budget still apply.

Keep the existing reviewer's deny-all internal-tool policy, disabled context/startup injection,
empty reviewer skills, agent-to-agent restrictions, and private loopback Gateway boundary.
Do not weaken isolation to make the fallback answer. The same bounded caller tools, canonical
history, source identities, receipts, quotes, and checked-report validation remain required.

The Gateway process must be able to resolve `BASETEN_API_KEY`. The application's project
`.env` does not automatically supply an already-running Gateway daemon. OpenClaw documents
its profile/private environment or managed-service environment as the relevant source.
Writing the key or configuration alone does not verify reload, activation, or inference;
retain that distinction if no approved service reload/restart is performed.

The HTTP reviewer route remains `openclaw/beforerun-reviewer`. Its returned route alias does
not independently identify the provider/model that answered. Display the configured primary
and fallback clearly, and obtain redacted upstream/failover evidence before asserting actual
Baseten use or successful Cerebras delivery. A Baseten answer cannot be described as a
Cerebras/Kimi proof.

Baseten documents Model API calls as usage-priced. A platform plan with no monthly fee is
not a verified free inference allowance. The task's existing free-only live condition remains
in force; the supplied key authorizes local setup, not unverified paid testing.

## Sources and verification limits

- [Baseten Model APIs overview](https://docs.baseten.co/inference/model-apis/overview), public
  unauthenticated GET returned HTTP 200 during this review.
- [Baseten Chat Completions reference](https://docs.baseten.co/reference/inference-api/chat-completions),
  public unauthenticated GET returned HTTP 200 during this review.
- Installed OpenClaw `docs/providers/baseten.md`, explicit configuration at lines 170–205.
- Installed OpenClaw `docs/concepts/model-failover.md`, native agent selection policy at
  lines 220–245 and provider-failure recovery at lines 467–480.
- Installed `dist/zod-schema.core-BWFCYYML.mjs`, model definition/provider schema around
  lines 625–739. A custom provider requires `baseUrl` and a `models` array.

The exact user-supplied Muse Spark Open model was not established by the installed curated
Baseten catalog. Account access, native tool acceptance, effective loaded policy, actual
failover, returned usage, pricing/free credits, and billing remain unverified until an
appropriately authorized live run supplies that evidence.

## Local setup applied

The requested key was saved without terminal echo in the ignored project `.env` and the
private dedicated Gateway provider configuration, both with mode `0600`. For the existing
daemon, the provider uses a private credential value rather than depending on a newly
exported process variable; no credential appears in this guide. The environment-reference
example above remains appropriate when the operator supplies the variable to the Gateway.

The existing Cerebras primary, all other providers/agents/settings, deny-all reviewer tools,
and isolation settings were preserved. Reversible private backups were retained outside the
release scope. The fallback list now includes `baseten/meta-models/muse-spark-open-1026`.
`openclaw --profile beforerun config validate --json` passed; raw CLI/config output was not saved.
No service restart, provider inference, installation, publication, or push was performed.

BeforeRun now exposes the configured primary/fallback in capabilities, job metadata and
exports, and displays the processing notice before submission and beside the report.
These are configuration facts, not proof of a successful upstream switch. Reports retain
their original checked assumptions, and the client still requires the reviewer route alias.

The old offline release checkpoint predates this provider change. Reevaluate both provider
paths and free allowances before enabling admission or making live claims. Runtime reload,
actual model/account access, function-tool compatibility and failover remain unverified.
