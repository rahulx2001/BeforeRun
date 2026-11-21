# GitHub repository review

> **Background workflow record — superseded for implementation.** Use
> [MASTER_BUILD_PLAN.md](MASTER_BUILD_PLAN.md) for supported contexts, safe tools,
> separate assessment/completion states, concrete tasks, and release gates.

Selected by the user as the **first workflow on 15 November 2026**, ahead of npm
package input. This is a product/implementation plan; repository scanning is not
implemented in the preparation scaffold. Functional work and demo fixtures must
follow [the event timing rule](HACKATHON_RULES.md).

This is an additional workflow in the intended Gatekeeper-inspired package/dependency
product. First means implementation order, not removing package investigation from
the product. See [PRODUCT_SCOPE.md](PRODUCT_SCOPE.md) for the full feature mapping.

The later [research brief](RESEARCH_BRIEF.md), [technical design](TECHNICAL_DESIGN.md),
and [evaluation playbook](EVALUATION_AND_DEMO.md) recommend Node as required event
scope, Python conditional on validation, and Git tree/blob retrieval. This document
summarizes the broader product workflow; the research pack defines the implementation
boundaries and acceptance gates.

## Developer problem

A repository's setup or build code can change after the developer last reviewed it.
Someone who then runs that code may expose their workstation or CI credentials to
harmful behavior. BeforeRun can review the exact source revision before the developer
runs its setup commands, showing suspicious behavior and supporting evidence.

Cloning a repository normally does not execute its setup scripts. The relevant trigger
is an installation, build, application-start command, or another action that executes
the changed code. Finding suspicious code does not establish that a GitHub account was
hacked; the report should describe the inspected commit and behavior.

## Compromised-update example

The motivating case is a familiar repository whose setup code was changed after an
account or repository compromise. A developer installs the updated project and the
new setup path executes with that developer's permissions. The desired intervention
is a review before that command runs.

For a fictional Node project, the evidence chain might be:

```text
npm install
  -> package.json: newly added postinstall hook
  -> scripts/setup.js: reads sensitive local data
  -> referenced helper: sends that data to an external destination
```

This is a planning example, not a finding from a scanned repository. A useful report
would explain the added hook, the referenced files, the sensitive resource and destination,
and which relationships are supported by the inspected text. It would link to the exact
commit and lines, with command assumptions and unresolved behavior stated separately.

Signals to investigate in context include:

| Behavior | Evidence needed before drawing a conclusion |
|---|---|
| Credential or environment-data collection and transmission | Sensitive sources, the outgoing request, and the visible relationship between them. Ordinary environment reads alone are insufficient. |
| Downloading and executing another program | The invoking setup path, the origin, and the execution operation. An unread remote payload remains unknown. |
| Decoding or constructing executable code | The decoding/evaluation chain and its connection to an entry point. Minified or encoded data alone is not proof of malware. |
| Creating persistent startup behavior | The setup trigger and the startup file, task, or service being changed. Legitimate installation tasks need context. |

Review the current setup path as well as the diff. An unchanged hook can invoke a
changed helper, and harmful behavior can already exist in the comparison revision.
Without a baseline, review the target snapshot and avoid claims about when behavior
was introduced. Evidence of harmful behavior alone cannot identify who changed it or
prove the account was hacked.

## Proposed workflow

1. Paste a public GitHub repository URL and optionally select a ref and intended command.
2. Resolve the ref to an exact commit SHA; show that SHA in the result.
3. Fetch and inspect a bounded source snapshot as data, without running repository code.
4. Identify setup/build entry points and let Kimi on Cerebras choose relevant file reads
   and searches within that snapshot.
5. Compare with a user-selected earlier commit/tag when available; identify the new
   behavior and the exact revisions compared.
6. Present findings, checked references, supported execution relationships, and gaps.

A repository URL alone may not identify the command the developer plans to run.
Apply known lifecycle rules only where supported; ask for or report the missing command
context when an execution claim depends on it. README commands are evidence to examine,
not instructions for the scanner to execute.

The existing interface illustrates repository root URL, optional target ref, optional
baseline ref, and command context. Initially support `review_only` and `npm_install`;
`pip_install_project` remains conditional on the Python acceptance gate. An omitted
target ref means resolve the default branch once, then use that commit for every source read. An omitted baseline means
snapshot review only. A supplied but unavailable baseline must produce a visible gap,
even if target-only inspection can continue.

## Files to prioritize

| Source | What to examine | Important distinction |
|---|---|---|
| `package.json` and referenced JavaScript | Install/build/start hooks and their visible file calls. | Use the lifecycle of the actual npm command. Unused code is not automatically install-time code. |
| `setup.py`, `pyproject.toml`, Python build code | Top-level setup behavior, declared backends, and referenced build hooks. | Building or preparing source metadata may execute backend code. Static uncertainty must remain visible. |
| Shell/PowerShell setup scripts and Makefiles | Explicit commands, downloads, file access, and referenced scripts. | A setup file's presence does not prove the developer's chosen command invokes it. |
| `.github/workflows/` and referenced actions/scripts | Commands, permissions, external actions, and handling of CI data. | CI execution and workstation installation are different contexts; third-party action code may remain unread. |
| Dependency declarations and fetched-code references | New packages, changed origins, remote scripts, and inaccessible code. | Reading the root repo does not inspect every dependency or remote payload. |

Read additional source files when the entry points lead to them. Kimi should assess
the behavior in context: environment-variable access, network traffic, subprocesses,
and minified code all have legitimate uses. A changed line or matching keyword alone
does not establish malware.

## Result design

Place the finding before the detailed investigation trace. Include:

- Repository, exact commit, optional baseline commit, and command context.
- **Needs review** or **No concerning findings in inspected code**, with a short
  explanation matching the evidence. Show completion separately: complete within declared
  scope, partial, failed, unsupported, or cancelled. A finding can coexist with partial coverage.
- New or changed behavior, linked to file/line excerpts from the inspected revision.
- The visible chain from a supported entry point to the cited behavior, or an unresolved
  relationship where that chain cannot be established.
- Coverage gaps: unread files, native code, submodules/LFS content, external actions,
  downloaded payloads, and unresolved dependencies, as applicable.
- Actions to open evidence, select another comparison revision, and copy findings.

An earlier commit is a comparison baseline, not automatically a clean or trusted version.
Do not interpret an absence of concerning findings as a guarantee that installation is safe.
The result applies to the inspected commit. A later branch/tag update requires another
review; the first workflow does not intercept installation commands. Source review also
does not establish that a separately downloaded release asset or registry package matches
the repository. Those artifacts require their own inspection.

## First useful scope

Start with **one public GitHub repository**, one pinned snapshot, an optional comparison
revision, and selected Node setup files and helpers. Add Python setup/build review only
after its dedicated cases pass within the event budget. Reuse the planned Kimi read/search
engine, numbered excerpts, reference checks, and result UI.

Use the pinned GitHub snapshot as the first input to that engine. Full dependency resolution,
package-manager command protection, private-repository authorization, comprehensive
native-code analysis, and registry-wide monitoring are later milestones.

Repo text, comments, and README files remain untrusted data. They cannot change tool
permissions, read bounds, or the investigation's instructions. Restrict retrieval to
supported GitHub source endpoints and validate URL/ref handling, archive paths, sizes,
and file types. Validate redirect destinations too. Resolve commits through GitHub's API;
bind tree/blob reads to that commit and record truncated responses as coverage gaps.
Use the pinned tree maps for comparison; the GitHub comparison API's changed-file list
has a limit. The contents API can dereference symlinks, so the event design reads blobs
selected from explicit tree modes instead.
Do not follow symlinks, submodule URLs, or LFS pointers into additional content during
the first review. Do not install the project, invoke its build backend, execute shell
commands from it, or evaluate package/formula code during investigation.

## Selected hackathon scope

GitHub review is the **selected main demo workflow**. The
[event plan](HACKATHON_PLAN.md) and [completion checklist](COMPLETION_CHECKLIST.md)
use GitHub commit/source retrieval and optional commit comparison, followed by the
common Kimi investigation, evidence checks, honest limits, validation, and submission
work. Add npm package input and further package ecosystems in subsequent stages.
The selected workflow remains planned rather than operational in the current scaffold.

## Event-created demo

Develop a clearly labeled fictional repo with two revisions during the event. The first
contains ordinary setup behavior; the second adds setup code that references dummy
sensitive data and a controlled destination. The scanner reads this code without
executing it. Show the commit comparison, Kimi's targeted file inspection, checked
references, and the supported setup trigger or its remaining uncertainty.

Also exercise legitimate setup behavior that resembles a risk signal and a partial
investigation with unavailable content. The demo must remain within 60 seconds and
use real measured latency. Repository fixtures should use dummy values rather than
credentials or live malware.

## Acceptance criteria

- URL/ref resolution pins the snapshot and displayed evidence to the same commit.
- A branch moving during review does not change the source being investigated.
- Retrieval and analysis stay within their configured limits and never execute repo code.
- Kimi performs investigation decisions through Cerebras rather than only rewriting a report.
- Every displayed file/line reference corresponds to text actually read.
- Execution claims are limited to supported command/file relationships; unknown paths
  are reported as unknown.
- A changed helper reached from an unchanged hook is considered; a missing baseline
  does not produce an invented change history or hide existing target behavior.
- A changed suspicious fixture is flagged with evidence, legitimate setup behavior is
  described accurately, and unavailable content produces a visible incomplete result.
- A source review does not claim to cover all release assets, package artifacts, native
  code, external downloads, or transitive dependencies.
- Release attribution, documentation, measurement, and submission follow the existing
  event checklist.

## Implementation references

- [GitHub commit API](https://docs.github.com/en/rest/commits/commits#get-a-commit)
  for resolving a selected revision, and
  [repository contents](https://docs.github.com/en/rest/repos/contents#get-repository-content)
  for commit-specific source reads and documented response limits.
- [npm lifecycle scripts](https://docs.npmjs.com/cli/v11/using-npm/scripts/)
  for the supported command's install hooks. Hooks and legitimate build scripts need
  behavioral investigation; their presence alone is not a finding.
- [pip build-system interface](https://pip.pypa.io/en/stable/reference/build-system/)
  for Python metadata/build hooks. Read declarations and referenced backend code as
  data; do not invoke pip to discover or execute those hooks during review.
