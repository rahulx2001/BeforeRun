# Restricted Gateway route diagnosis

**Date:** 22 November 2026. **Scope:** read-only local inspection; no Gateway/model request,
credential change, service restart, installation, or reviewer policy mutation.

The failed proof has two distinct causes in the retained logs. The evidence is summarized in
[route_diagnosis.json](live-proof/route_diagnosis.json); raw logs, prompts, account identifiers,
request/session IDs, credentials, and upstream response bodies are intentionally omitted.

## Provider rejection

Five transport-response events at 14:41:52–14:42:07 IST record **Cerebras HTTP 429** with error
code **`queue_exceeded`** and type **`too_many_requests_error`** for the configured
`moonshotai-kimi-k3.1-pro-trial` model. Gateway request numbers are 1–5. These are observed
transport events in that bounded log window; they are not five completed reviews or an
exhaustive billing/request journal.

The error establishes queue/rate rejection. The model's `trial` suffix does not establish
trial expiration or account quota exhaustion. The inspected safe fields provide no numeric
account limits, verified pricing, successful inference, returned usage, or charge reconciliation.
The source route remains `https://api.cerebras.ai` through OpenClaw; no alternate model or
direct-provider bypass was tested or proposed.

An application request may generate several Gateway/provider attempts. An application retry
limit or `max_tokens` alone does not establish a provider cost ceiling or confirmed upstream
abort. A live spend boundary needs verified pricing/limits and provider-side reconciliation.

## Restricted text-smoke error

The 14:52:50 IST Gateway errors match the installed runtime diagnostic **“No callable tools
remain after resolving explicit tool allowlist”**, with detail **“no registered tools matched.”**
The restricted smoke combined an explicit `br_read_excerpt` allowlist with a text-only request.
Installed OpenClaw's `applyToolChoice` removes all caller tools for `tool_choice="none"`.
No callable tool can satisfy that explicit requirement, so this case fails before a useful
native tool round-trip. This does not demonstrate that `br_read_excerpt` requires an installed
plugin.

The installed source supports native caller function tools separately from filtered core tools:

| Installed source (relative to OpenClaw 2026.11.6) | Relevant behavior |
|---|---|
| `dist/openai-compatible-input-limits-BgJ-Gyyo.mjs:240` | `tool_choice="none"` removes the caller tool list. |
| `dist/attempt-S43tUjWN.mjs:344` | Caller-tool preparation checks global deny-all, then per-run caller-tool restrictions. |
| `dist/attempt-S43tUjWN.mjs:5417` | Native client tools are combined with the filtered core tool surface. |
| `dist/attempt-S43tUjWN.mjs:6929` | An explicit requirement with no callable tool produces the recorded diagnostic. |
| `dist/attempt-tool-run-context-DwM7ivmG.mjs:13` | Runtime caller-tool restrictions derive from the per-run `toolsAllow` override. |
| `docs/gateway/openai-http-api.md:219` | HTTP caller function-tool choice is distinct from internal OpenClaw tools. |

## Smallest candidate procedure

No configuration change is needed to prepare the next candidate:

1. Retain the saved reviewer policy `tools.deny=["*"]` with no explicit `allow` field for
   text smoke. Keep context injection/startup disabled, empty reviewer skills, no model
   fallbacks, disabled agent-to-agent access, and loopback binding.
2. After explicit live authorization and verification of the spend limits, send the bounded
   text smoke with `tools=[]`, `tool_choice="none"`.
3. For the inert round-trip, supply only server-owned `br_read_excerpt`; validate the returned
   native call before dispatching the bounded snapshot reader and recording its receipt.
4. Continue with the exact assistant/tool IDs, validate the checked citation, and verify
   forbidden/cross-job actions and cancellation limits under the effective installed policy.
5. Stop on a failed prerequisite and retain its sanitized evidence. Do not enable public
   admission based on configuration/source inspection alone.

The inspected installed code treats **global** `tools.deny=["*"]` as a blocker for native
caller tools. The saved dedicated profile has no global allow/deny gate; its deny-all policy
is scoped to the reviewer. Static inspection supports trying native caller tools with that
reviewer policy, but does not attest that the running Gateway applied it or that a provider
accepted the tool schema. No live check was performed during this diagnosis.

## Isolation and version limits

- Saved reviewer policy denies all internal tools, disables context injection, inherits
  disabled startup context, and has empty skills. Effective bootstrap/memory behavior,
  plugin callbacks, actual caller-tool availability, and forbidden-action enforcement remain
  unverified. Disabling advertised tools alone is not proof of all context isolation.
- Session visibility is `agent`; no separate job-level Gateway boundary is established by
  that setting. Keep canonical transcripts and evidence ledgers owned by each application
  job. Any stable Gateway `user`/session key must be server-generated per review thread.
- No explicit OS/container sandbox mode was found in the inspected dedicated configuration.
  A named profile does not isolate the host filesystem or credentials by itself.
- The Gateway remains a private operator endpoint. The browser must only use BeforeRun's
  `/api` surface; never expose its token, general proxy, model selection, or session headers.
- Installed OpenClaw package: **2026.11.6**. Logs record Node **24.22.3**. The inspected
  `version=2026.11.6` connection fields describe clients, so they cannot establish the running
  Gateway build. Running-Gateway version proof remains pending.

G2–G4 remain incomplete. This diagnosis explains failed requests and prepares a narrower
procedure; it does not convert the failed live proof into a passing release gate.
