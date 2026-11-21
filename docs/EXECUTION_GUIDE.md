# BeforeRun: execution guide

> **Historical setup guide — superseded for implementation.** Use
> [MASTER_BUILD_PLAN.md](MASTER_BUILD_PLAN.md) for current steps. In particular, do not
> combine this guide's unprofiled OpenClaw commands or older tool examples with the
> dedicated `beforerun` profile and snapshot-only `br_` policy in the master plan.

Prepared 21 November 2026 from the checked local repository, the organizer rules supplied
in this conversation, and the official references at the end. This is an implementation
guide. The review endpoints, modules, and test cases described below still need to be built.

## 1. The result to build

A developer supplies a public GitHub repository, a target revision, an optional baseline,
and `npm install` as context. BeforeRun pins the commits, reads the root setup files as data,
uses an OpenClaw reviewer powered by Kimi on Cerebras, and shows an explanation with checked
source references and coverage limits.

The main demonstration: `package.json` is unchanged, but the helper it calls raises the
minimum Node version from 20 to 22. Explain the consequence for a developer using Node 20.
Both fixture versions are harmless; BeforeRun does not execute either version.

Use one documented npm 11 root-install context. Workspaces, dependency scripts, Python,
registry package input, and install blocking are later extensions. A missing explicit hook
does not establish that nothing can run: npm has other lifecycle and native-build behavior.

## 2. Your starting point

- Project: `/Users/rahulkumarsinghj/Desktop/BeforeRun` on your Mac.
- Existing `.venv`: Python 3.12.16. Reuse it.
- Existing FastAPI server: `GET /` and `GET /health`.
- Existing UI: static; the review form is disabled.
- Compilation, lint, formatting, and dependency consistency passed during this inspection.
- Retrieval, model integration, comparisons, and behavioral tests are not implemented.
- OpenClaw was not on the inspected shell's PATH. Node was 25.1.0, npm 11.6.2.
- Your Cerebras preview request is submitted and awaiting approval.

The earlier Crio QCare/MLflow project is separate. Use this project's `.venv` and Python
3.12; its setup does not use `mlflow.db`, `make ui`, or the Crio GitLab remotes.

## 3. Timing and access

The supplied event window converts to **21 November 23:30 IST through 22 November
23:30 IST**. The Org ID request deadline was **21 November 08:30 IST**. Your submitted
request is pending; check the organizer's announcement/support channel for approval.

The newer organizer FAQ supplies `moonshotai-kimi-k3.1-pro-trial`. Older local documents
that say the ID is missing are stale. A configured model name is not evidence of access.
The decisive check is a successful request using your approved account.

Prepare tools and the existing scaffold before kickoff. Build the investigation,
comparison, live model integration, and functional demo during the event, in accordance
with the supplied core-development rule. While preview access is pending, implement and
test the source, evidence, and UI layers against clearly labeled local test data. A mock
or another model can test plumbing but is not the qualifying final integration.

## 4. Start the existing app

Use Mac Terminal. Run commands in order, and wait for each to finish before pasting more.

Terminal A:

```bash
cd /Users/rahulkumarsinghj/Desktop/BeforeRun
source .venv/bin/activate
python --version
make check
python -m pip check
make dev
```

Expect Python 3.12.x and passing checks. `make dev` stays running. Open
`http://127.0.0.1:8000`; it is the current design scaffold. In Terminal C, verify:

```bash
curl -fsS http://127.0.0.1:8000/health
```

Expect `status: ok` and `phase: scaffold`. The disabled form is expected at this point.
If 8000 is occupied, start `.venv/bin/python -m beforerun --reload --port 8001` instead.

If dependencies are missing, stop the server with Control+C and run `make install`.
The existing environment does not need to be recreated for this guide.

## 5. Save your local starting point

The inspection found no commits. After reviewing which files will be included, save a
local scaffold checkpoint:

```bash
cd /Users/rahulkumarsinghj/Desktop/BeforeRun
git add .gitignore .env.example .github Makefile README.md pyproject.toml requirements-dev.lock src tests docs
git diff --cached --stat
git commit -m "Record BeforeRun preparation scaffold"
```

This is a local commit. Publishing is a separate submission task. If Git asks for your
identity, configure your own name and email for this repository, then retry the commit.

## 6. Install and configure OpenClaw

> These commands are preserved historical examples, not the current setup sequence.
> Follow [section 10 of the master plan](MASTER_BUILD_PLAN.md#10-openclaw-integration-and-setup)
> to avoid configuring a personal Gateway or enabling the wrong tools.

OpenClaw's current guide supports Node 24.16+ on 24.x or 26.1+; it recommends newer patched
releases. Node 25 is outside those documented branches. Homebrew's Node 24 formula is an
available route on this Mac:

```bash
brew install node@24
export PATH="$(brew --prefix node@24)/bin:$PATH"
node --version
npm --version
```

Use that PATH export in each terminal running OpenClaw. Keep the current formula patched.

Choose the install command matching the npm version printed above:

```bash
# npm 12 or npm 11.16 and newer:
npm install -g openclaw@latest --allow-scripts=openclaw
```

```bash
# npm 11.15 and older:
npm install -g openclaw@latest
```

Run only the applicable installation command, wait for completion, then:

```bash
openclaw --version
openclaw plugins install @openclaw/cerebras-provider
openclaw onboard --auth-choice cerebras-api-key
openclaw models list --provider cerebras
```

Complete onboarding locally with your Cerebras key. Select local gateway operation and
token authentication. Skip messaging channels for this web-app integration.

The provider's default is a different model. Create a dedicated reviewer with the event
model explicitly selected:

```bash
openclaw agents add beforerun-reviewer --workspace "$HOME/.openclaw/workspace-beforerun" --model cerebras/moonshotai-kimi-k3.1-pro-trial --non-interactive
openclaw models status --agent beforerun-reviewer
openclaw config set gateway.http.endpoints.chatCompletions.enabled true --strict-json
openclaw config set 'agents.entries.beforerun-reviewer.tools.deny' '["*"]' --strict-json
```

If the reviewer already exists, inspect `openclaw agents list` and its configuration;
reuse it rather than recreating it. If the preview model is unknown to the local catalog,
merge a minimal explicit entry, retaining the credentials established by onboarding:

```bash
openclaw config set models.providers.cerebras '{"baseUrl":"https://api.cerebras.ai/v1","api":"openai-completions","models":[{"id":"moonshotai-kimi-k3.1-pro-trial","name":"Kimi K3.1 Pro trial"}]}' --strict-json --merge
openclaw config validate
```

This registers a name locally; it does not grant private-preview entitlement. Do not
invent context-window, pricing, or reasoning-capability metadata for the trial model.
If agent creation failed because the catalog entry was missing, retry that creation
command after registration, then apply the endpoint and reviewer-policy commands.

In Terminal B, run the gateway if onboarding has not already started one:

```bash
export PATH="$(brew --prefix node@24)/bin:$PATH"
openclaw gateway run --bind loopback --port 18789
```

Keep it running. If a gateway is already running, reuse it and verify its address instead
of starting a second process. Terminal A runs BeforeRun, Terminal B runs OpenClaw, and
Terminal C is for tests and commands.

## 7. Test the full connection after approval

Create `.env` from `.env.example` only if it does not already exist. Add the following
local app settings. They are proposed integration variables; the new client will read them.

```dotenv
OPENCLAW_BASE_URL=http://127.0.0.1:18789
OPENCLAW_AGENT=beforerun-reviewer
OPENCLAW_GATEWAY_TOKEN=your-local-gateway-token
CEREBRAS_MODEL=moonshotai-kimi-k3.1-pro-trial
```

Enter the real gateway token locally. It differs from the Cerebras API key, which OpenClaw
uses upstream. Keep both out of browser JavaScript. The agent's model configuration
determines the backend model; setting `CEREBRAS_MODEL` in the app alone does not change it.

In Terminal C, from the project root, run this harmless smoke after preview approval:

```bash
.venv/bin/python - <<'PY'
import os
import httpx
from dotenv import load_dotenv

load_dotenv(".env", override=False)
token = os.environ.get("OPENCLAW_GATEWAY_TOKEN")
if not token:
    raise SystemExit("Set OPENCLAW_GATEWAY_TOKEN in your local .env first.")
base = os.environ.get("OPENCLAW_BASE_URL", "http://127.0.0.1:18789").rstrip("/")
agent = os.environ.get("OPENCLAW_AGENT", "beforerun-reviewer")
response = httpx.post(
    base + "/v1/chat/completions",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "model": f"openclaw/{agent}",
        "tool_choice": "none",
        "messages": [{"role": "user", "content": "Reply exactly CONNECTION_OK. Do not use tools."}],
        "stream": False,
    },
    timeout=60.0,
)
response.raise_for_status()
print(response.json()["choices"][0]["message"].get("content", ""))
PY
```

The target is an actual answer from the configured Kimi route through OpenClaw. Confirm
the served route in gateway diagnostics as well. Do not treat a fallback-model response
as successful event-model verification.

- Connection refused: start/reach the gateway at the configured address.
- Gateway 401: check the local gateway token and authentication mode.
- Upstream entitlement/auth error: confirm Cerebras approval and credentials.
- Unknown model: check both local catalog registration and the organizer's model ID.
- Text success: next prove one harmless bounded tool call; text does not prove tool support.

## 8. Implement the event functionality in small stages

These are coding tasks, not terminal commands. Work under `src/beforerun/features/`.
Give each stage its own local commit after its acceptance checks pass.

### Stage A: review data and source retrieval

Suggested files: `contracts.py`, `github_source.py`, and `review_service.py`.

1. Add typed review input, pinned revision, file, evidence, coverage, and result records.
2. Accept public GitHub root URLs plus optional target/baseline refs and an enum command.
3. Resolve refs to exact commit SHAs once; use those identities for every subsequent read.
4. Read the root manifest and approved source blobs using the GitHub API, without installs.
5. Bound requests, body sizes, time, and file count. Record oversized/binary/symlink,
   submodule, missing, or truncated content as coverage gaps.

Finish when a request returns exact commit identities and manifest source, or a useful
failure. Test an invalid URL, unavailable ref, and a moving branch whose later reads
must still use the originally resolved commit.

### Stage B: setup paths and evidence

Suggested files: `npm_setup.py` and `evidence.py`.

1. Read root npm setup hooks for the documented command/version scope.
2. Support simple visible local helper references such as `node scripts/check-node.cjs`.
3. Keep dynamic shell expressions or unresolved imports as explicit unknowns.
4. Assign server-issued evidence IDs to numbered excerpts and retain which excerpts
   the reviewer actually received.
5. Generate permanent source links from the stored commit, path, and validated line range.

Finish when the app can show the root hook, its referenced helper, and exact source
lines from a pinned harmless fixture. A blank explicit-hook list must not produce a
blanket claim that no install behavior exists.

### Stage C: the OpenClaw investigator

> This stage's older tool contract is superseded by the master's `br_` dispatcher,
> [investigation algorithm](MASTER_BUILD_PLAN.md#14-investigation-algorithm), and
> [validation policy](MASTER_BUILD_PLAN.md#15-verdict-and-validation-policy).

Suggested file: `openclaw_client.py`.

Use the Gateway route `openclaw/beforerun-reviewer`. Start with a curated evidence packet
to establish the integration. Then expose one function tool, `read_review_excerpt`, so
Kimi can choose a relevant additional read. This meaningful choice satisfies the existing
local plan's requirement that Kimi participate in investigation rather than only reword
a precomputed verdict.

The tool accepts an issued file ID and bounded line range. The backend already knows
the current review; the model cannot select another user's review or an arbitrary URL.
Preserve the assistant tool call and match returned tool messages by `tool_call_id`.
Use explicit message history scoped to one review and cap rounds; do not mix reviews.

Configure the agent's internal tools separately so the review exposes only approved
evidence reads. The HTTP `tools` list alone does not restrict built-in tools. Verify the
effective set with the installed version. Avoid an empty explicit allowlist: current
OpenClaw versions can reject it before a model call.

The earlier deny-all policy is for the completion smoke/curated-packet stage. When the
client actually supplies `read_review_excerpt`, switch this dedicated agent to the
matching allowlist and validate the configuration:

```bash
openclaw config unset 'agents.entries.beforerun-reviewer.tools.deny'
openclaw config set 'agents.entries.beforerun-reviewer.tools.allow' '["read_review_excerpt"]' --strict-json
openclaw config validate
```

Verify that the caller-supplied read tool works and other tools remain unavailable
before using repository content. Parent/global tool policies can still impose limits.

Treat source text as data. The review has no need for shell execution, repository writes,
unrestricted browser/network tools, or access to local home directories. Enforce those
limits in configuration/backend checks rather than relying on a prompt.

Ask for a compact structured report with a summary, consequences, evidence IDs, and
unanswered questions. Parse and validate it in FastAPI. If the preview's structured-output
mode is unavailable, use ordinary text containing JSON, validate it, and allow at most one
format repair. Source references that cannot be validated remain unverified.

Finish when one genuine Kimi review requests the correct helper and returns a supported
explanation. A failed model call returns an explanation-unavailable/partial state while
preserving the source inventory.

### Stage D: the comparison that makes the product useful

Suggested file: `compare.py`.

Read the same scoped helper at both pinned revisions and compute a diff. Review helper
changes even when the manifest is unchanged. Preserve the side and commit of every excerpt.
If a requested baseline is unavailable, say so; do not silently call a snapshot a comparison.

Use the harmless event-created fixture: same hook, minimum Node version changes from
20 to 22. Return that exact behavior change, the expected consequence for Node 20,
and references to both versions. Also test an unrelated file change with no setup change.

### Stage E: connect the existing interface

Add planned routes to `app.py`:

| Route | Purpose |
|---|---|
| `POST /api/reviews` | Validate input, create a job, return 202 and an ID. |
| `GET /api/reviews/{id}` | Return current state, genuine progress, and final/partial result. |

Suggested states: queued, running, completed, partial, failed. Coverage and findings
are independent: one good finding can coexist with unread files.

Use the existing form, styles, and report layout. Add a frontend controller such as
`static/reviews.js`; enable the form only once connected. Poll the current review every
one or two seconds; show backend operations rather than invented percentage completion.
Render repository text as text. Keep tokens and the gateway address behind FastAPI.

Test Reset and starting another review: clear the visible report, stop the old poll,
and ignore late responses from the previous review. In a simple in-memory job store,
server restarts lose jobs; show a clear restart message rather than a permanent spinner.

Finish when a person can paste the fixture URL, choose revisions, click Review, and
read a real report without editing code or refreshing the browser manually.

## 9. Useful checks before recording

Write behavior tests as the implementation arrives. At minimum cover:

1. Unchanged hook with changed helper: identify the change and cite both commits.
2. No relevant setup change: report that limited observation without a broad safety claim.
3. Dynamic/unavailable helper: keep unresolved coverage visible.
4. Invented evidence ID or wrong lines: reject the reference.
5. Provider timeout or rate limit: useful failure/partial state, no reassuring verdict.
6. Source comments requesting extra authority: no change to permitted tools or source scope.
7. A branch moving during review: all excerpts remain tied to the chosen commit.
8. UI Reset during an outstanding request: the old result cannot reappear.

Once those tests exist:

```bash
cd /Users/rahulkumarsinghj/Desktop/BeforeRun
make check
.venv/bin/python -m pytest
.venv/bin/python -m pip check
```

`make check` currently covers source compilation/lint/formatting only. Extend checks to
new code and tests when needed. A pytest exit for no tests collected is not a passing
behavior suite. Run a real browser workflow after integration checks.

## 10. Measure, present, and submit

Use a monotonic timer for user-visible elapsed time. Separate retrieval, model, and total
review duration. Record the commits, model route, settings, and cache state. Repeat a few
named runs and show the actual times or median/range. Do not label total wait time as TPS.

If the main workflow is complete early, add Copy review summary: repository, commits,
command, explanation, permanent evidence links, and coverage omissions as Markdown.
Ask the evidence is the next optional feature. Keep extra ecosystems and install guards
out of this first event build.

Suggested 60-second demo:

| Segment | Show |
|---|---|
| 0–8 seconds | Same repository, two commits, unchanged install hook. |
| 8–18 seconds | Paste URL, select revisions, click Review. |
| 18–38 seconds | Real OpenClaw/Kimi review follows the helper and returns the change. |
| 38–50 seconds | Open the evidence and explain why Node 20 is affected. |
| 50–60 seconds | Actual elapsed time, inspected scope, and product name. |

If the actual review is longer, label edited/time-compressed footage and show its actual
duration. Finalize README setup instructions and attribution to match what was built.
For the supplied rules, the official submission is the X demo post tagging `@Cerebras`
and `@Kimi_Moonshot` with `#KimiOnCerebras`, plus the requested project/team/description.
Reddit is optional with the named event flair. Discord is for announcements/support;
older local notes calling it the submission destination are stale. Submit before
22 November 23:30 IST, leaving an upload buffer.

## 11. Suggested 24-hour allocation

| Hours after kickoff | Deliverable |
|---|---|
| 0–1 | Approved-model connection through OpenClaw; otherwise continue independent layers. |
| 1–4 | Typed records, validated GitHub input, commit-pinned reads. |
| 4–7 | Root setup paths, helper reads, numbered evidence. |
| 7–10 | Live bounded OpenClaw/Kimi investigation and validated output. |
| 10–12 | Two-commit helper comparison and one complete result. |
| 12–15 | Existing UI connected, real states, Reset/retry flow. |
| 15–18 | Behavior cases, errors, and integration fixes; freeze features. |
| 18–21 | Repeated timing runs, README, attribution, optional copyable summary if ready. |
| 21–24 | Recording, final verification, and submission with a buffer. |

Estimates assume a small first version. At hour 12, prioritize one working Node review.
After hour 18, spend time on reliability and submission rather than new product inputs.

## Official references checked

- [Event listing](https://luma.com/cerebras-kimi-hackathon); use the newer organizer FAQ
  supplied in this conversation for the trial model ID and detailed submission rules.
- [OpenClaw getting started](https://docs.openclaw.ai/start/getting-started)
- [OpenClaw installation](https://docs.openclaw.ai/install)
- [Homebrew Node 24](https://formulae.brew.sh/formula/node@24)
- [OpenClaw Cerebras provider](https://docs.openclaw.ai/providers/cerebras)
- [OpenClaw agents CLI](https://docs.openclaw.ai/cli/agents)
- [OpenClaw custom providers](https://docs.openclaw.ai/gateway/config-tools/custom-providers)
- [OpenClaw Gateway HTTP API](https://docs.openclaw.ai/gateway/openai-http-api)
- [OpenClaw tool restrictions](https://docs.openclaw.ai/tools/multi-agent-sandbox-tools)
- [npm 11 scripts](https://docs.npmjs.com/cli/v11/using-npm/scripts/)
- [GitHub permanent source links](https://docs.github.com/en/repositories/working-with-files/using-files/getting-permanent-links-to-files)

CLI/config commands were checked against published documentation. OpenClaw was not
installed during this planning task, and your pending private preview was not live-tested.
