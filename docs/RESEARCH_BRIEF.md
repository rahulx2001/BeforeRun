# BeforeRun: research and product recommendation

> **Background research.** Use [MASTER_BUILD_PLAN.md](MASTER_BUILD_PLAN.md) for the
> authoritative implementation sequence, OpenClaw integration, current result policy,
> evaluation gates, and complete roadmap. The research and source comparisons below
> are preserved, not a claim of implemented functionality.

**Research date: 15 November 2026. Status: planning only.** The user selected public
GitHub repository review first and explicitly requested research without building the
scanner before the hackathon. No detection capability or performance result is implied
by this document.

**Product scope clarification:** the user intends Gatekeeper-style package/dependency
protection **plus** GitHub repository review. This brief scopes the first event
milestone, not complete Gatekeeper feature parity. Package input remains planned.
Read [PRODUCT_SCOPE.md](PRODUCT_SCOPE.md) for the comparison and two-input architecture.

Read this brief for the product decision; use [TECHNICAL_DESIGN.md](TECHNICAL_DESIGN.md)
for the implementation specification, [EVALUATION_AND_DEMO.md](EVALUATION_AND_DEMO.md)
for tests and the 24-hour plan, and [RESEARCH_SOURCES.md](RESEARCH_SOURCES.md) for the
43 primary references, evidence quality, and unresolved checks.

## 1. Recommendation

Proceed with a focused **review before setup** product. Its central question should be:

> What could this setup command execute at this commit, and what changed since the
> revision I last reviewed?

The first experience should accept a public GitHub root URL, an optional target revision,
an optional comparison revision, and a supported command context. It should retrieve
source as data, let Kimi investigate the selected setup path, and present a short finding
with exact evidence and visible limits.

Make **Node repository setup review** the required event demonstration. Allow Python
setup inspection only after the Node workflow and its failure cases pass. This narrows
the earlier Node-and-Python draft: broad ecosystem coverage is an expensive promise,
whereas a correct, inspectable result for one workflow can stand on its own. The public
interface may illustrate future inputs, but enabled controls must match real coverage.

Treat success as a better decision before execution, not a guarantee against infection.
The initial product neither prevents account takeover nor intercepts package installation.
It cannot recover secrets from an already compromised computer. These are boundaries of
the proposed product, not reasons to abandon the idea.

## 2. Why the threat is credible, and what the URL does not identify

An install command can trigger code. npm documents lifecycle scripts; Python build
frontends invoke backend hooks that may also be needed for metadata generation.
This supports the user's scenario without needing to identify the person in the reel.
[S02](RESEARCH_SOURCES.md#s02), [S04](RESEARCH_SOURCES.md#s04),
[S05](RESEARCH_SOURCES.md#s05).

The URL alone leaves several questions unanswered: Which revision? Which directory?
Which command and package-manager version? Which dependencies or release assets will be
used? What local configuration changes execution? A good first version collects the
minimum supported context and makes remaining assumptions explicit.

| Documented example | Observed mechanism | Implication for BeforeRun |
|---|---|---|
| Nx, August 2025; maintainer postmortem published September 5 | A stolen publishing token enabled malicious npm releases with postinstall behavior. | Reviewing a GitHub branch alone can miss an altered published package; artifact inspection is separate work. |
| tj-actions/changed-files, March 2025 | A compromised action exposed CI secrets through logs. | The execution context is CI. Do not describe workflow code as something `npm install` automatically runs on a laptop. |
| Shai-Hulud, described by GitHub in December 2025 | Compromised credentials and lifecycle scripts helped propagate package attacks. | Entry-point review is useful, but account, publishing, dependency, and runtime controls remain separate layers. |

Sources: [S07](RESEARCH_SOURCES.md#s07), [S08](RESEARCH_SOURCES.md#s08),
[S09](RESEARCH_SOURCES.md#s09). These examples do not establish that BeforeRun would
have detected those incidents, and none is asserted to be the reel the user watched.

SLSA's threat model separates source, build, distribution, and dependencies. npm provenance
can link an artifact to build/source information without proving its contents harmless.
Therefore the report must distinguish **source inspected**, **artifact inspected**, and
**external code unresolved**. [S10](RESEARCH_SOURCES.md#s10),
[S11](RESEARCH_SOURCES.md#s11).

## 3. Existing tools and the contribution worth making

This is a documentation-based comparison, not a benchmark. Feature availability and
quality must not be inferred from the category alone.

| Existing project or product | Documented role | Consequence for our scope |
|---|---|---|
| Gatekeeper, pinned reviewed revision | Agent investigation, checked references, version/fork comparisons, audit and install guard. | Strong overlap. Attribute the inspiration and describe actual new work accurately. |
| Socket | Supply-chain behavior alerts and AI-detected potential malware, alongside other package risks. | Behavior analysis is established. We cannot claim to be the first to look beyond CVEs. |
| GuardDog 3.0 | Static YARA analysis with attack-stage correlation; its FAQ says it does not use LLMs or execute package code. | Useful future baseline. Its sandbox isolates the scanner, which differs from executing a suspected package. |
| Semgrep | Rule-based source analysis. | A possible baseline or later integration, rather than a required second engine during the event. |
| OSV-Scanner | Dependency and known-vulnerability analysis with its supported additional features. | Useful complementary information; advisory absence does not settle a new source-behavior question. |
| GitHub dependency review | Dependency changes and known vulnerability information in review workflows. | Complement existing GitHub tools; do not claim GitHub has no supply-chain defenses. |
| OpenSSF Scorecard | Repository security-practice checks. | Useful context, not proof of the inspected setup behavior. |
| OpenSSF Package Analysis | Static and dynamic package analysis, including sandboxed execution. | Demonstrates the operational scope of behavioral execution; defer that system to later research. |

Sources: [S12](RESEARCH_SOURCES.md#s12)–[S19](RESEARCH_SOURCES.md#s19).

A defensible contribution is the combination of a low-friction repository URL workflow,
commit-specific setup review, change explanation, readable evidence, and measured
interactive investigation on Cerebras. This is a product-direction hypothesis, not a
claim of global originality or proven market demand.

After the event, validate usefulness with developers: Can they identify the relevant
command? Does the report change an installation decision? Can they understand a false
alarm and an incomplete result? Do they repeat the workflow? No outreach was performed
for this research, and willingness to pay is unknown.

## 4. Scope: required, conditional, and later

| Priority | Capability | Completion condition |
|---|---|---|
| Required | Public GitHub root URL and exact commit | Every inspected file and evidence link refers to the resolved revision. |
| Required | Node root setup path and relevant local helpers | Command assumptions and supported edges are stated; unresolved calls remain unknown. |
| Required | Optional user-selected comparison commit | Compare both bounded snapshots; review target behavior even if a hook is unchanged. |
| Required | Live Kimi investigation through Cerebras | Kimi chooses useful file reads/searches; the backend enforces permissions and limits. |
| Required | Evidence and coverage | Every visible reference is validated; failures and unread code remain visible. |
| Required | Harmless, concerning, ambiguous, and failure cases | Demonstrate correct handling, not only one successful detection. |
| Conditional | Python root setup/build review | Backend declarations, helpers, external-backend gaps, and dedicated cases are handled. |
| Conditional | Ask the evidence | Reuse bounded reads; add only if required checks pass early. |
| Later | npm/PyPI artifact inputs and lockfile dependency review | Implement exact artifact identity, package semantics, and independent evaluation. |
| Later | Shell, PowerShell, Make, CI, IDE/devcontainer, workspace-wide analysis | Define execution semantics and scope for each, then test them. |
| Later | Install guard, monitoring, private repositories, remediation, dynamic analysis | Separate authorization, isolation, operational, and accuracy work. |

A shell helper reached from a supported Node hook can be displayed and investigated as
source in the first version. That does not justify claiming complete shell-language
reachability. Similarly, spotting a workflow or nested package is useful inventory;
comprehensive analysis of it is a separate capability. IDE automation has its own trust
model, illustrated by VS Code Workspace Trust. [S41](RESEARCH_SOURCES.md#s41),
[S42](RESEARCH_SOURCES.md#s42).

## 5. What the investigator should look for

These are proposed behavioral questions, not sufficient malware signatures.

| Question | Stronger supporting evidence | Common legitimate explanation to check |
|---|---|---|
| Is sensitive data collected and transmitted? | A supported setup path, sensitive source, outgoing operation, and visible relationship. | Reading a build flag, documented telemetry, a fixture containing a fake credential. |
| Is remote code fetched and executed? | Setup invokes a downloader and then executes its result. | Fetching a declared compiler/binary; still report that unread code limits the review. |
| Is code constructed or decoded before execution? | Decode/evaluation relationship and relevant caller. | A bundled asset, generated code, ordinary encoding. |
| Does setup establish persistent execution? | It writes a startup target or registers a service/task. | An explicitly expected service installer. |
| Does setup alter unexpected files or settings? | A path outside normal build outputs with a supported invocation. | Normal cache creation or documented configuration setup. |
| Did the update change the reachable helper or origin? | Hook-to-helper relationship plus target/baseline evidence. | A legitimate refactor or changed build dependency. |
| Is apparently risky code unused in this command? | The cited content is a test/example or a path without a supported invocation. | Benign documentation or security-test samples. |

The output should distinguish suspicious behavior, expected behavior, and insufficient
evidence. It must not convert the presence of network access, `eval`, a secret-related
word, obfuscation, or a new contributor into a malicious verdict. OpenSSF's label policy
also distinguishes telemetry and other ambiguous behavior from malicious activity;
its database can include borderline entries. [S20](RESEARCH_SOURCES.md#s20).

Inspect the target setup path as well as changed files. Two important cases are an
unchanged hook calling a modified helper, and harmful behavior present in both revisions.
Do not automatically label the parent commit, release tag, signed commit, or popular
project as a trusted baseline. A comparison can establish differences without proving
that either side is safe.

## 6. Analysis strategy

Use a small hybrid design:

1. Deterministic code resolves identity, selects files, parses bounded metadata, records
   simple entry relationships, and manages the evidence ledger.
2. Kimi chooses read/search steps, relates observations across files, checks plausible
   benign explanations, and proposes findings with evidence IDs.
3. Deterministic validators enforce identity, ranges, tool permissions, budget accounting,
   and the narrow execution relationships the application can actually verify.
4. The report distinguishes a validated excerpt from a supported path and from a model's
   semantic interpretation. Those are three different kinds of evidence.

A real line reference can still support an incorrect conclusion. An imported helper can
still be conditional or unused. A model's confidence is not a calibrated probability.
These distinctions should appear in the data model rather than relying only on a footer.

Do not start with fine-tuning, embeddings, a vector database, multiple investigator agents,
or an unrestricted coding-agent framework. For one small repository, explicit file
inventory and bounded reads are easier to audit. Add complexity only when an evaluated
failure justifies it. These are design recommendations, not claims that these methods
can never be useful.

## 7. Safe retrieval is part of the product

Prefer GitHub API trees and blobs. Resolve the selected revision once, record the commit
and tree, and retrieve ordinary files by the object IDs from that tree. Do not install
the project to discover its metadata or dependencies.

GitHub documents comparison-file limits, recursive-tree truncation, and contents-endpoint
symlink behavior. Our chosen strategy addresses those particular hazards while preserving
visible gaps for large or unsupported input. [S22](RESEARCH_SOURCES.md#s22)–
[S25](RESEARCH_SOURCES.md#s25).

The detailed design must enforce fixed outbound API destinations, bounded responses,
no following of repository-supplied links, safe source rendering, and tools restricted
to the current snapshot. Code comments and README instructions are evidence to analyze,
never authorization for the scanner. OWASP provides relevant SSRF, prompt injection,
and output-rendering guidance. [S28](RESEARCH_SOURCES.md#s28)–
[S30](RESEARCH_SOURCES.md#s30).

Static analysis also parses attacker-controlled data. Reading source without executing
it reduces a major risk but does not justify promising the scanner itself is invulnerable.
Parser limits, maintained dependencies, and an isolated worker with minimal credentials
belong in the implementation design.

## 8. The report the user should see

Lead with the finding and its reason, then expose the evidence and investigation activity.
A proposed report contains:

- Repository, full commit, optional baseline, command context, and review time.
- A conclusion such as **Needs review** or **No concerning findings in inspected code**.
- A separate completion indicator: complete within stated scope, partial, failed,
  unsupported, or cancelled. A partial report may still contain an important finding.
- A short explanation of the supported command-to-file path and the claimed behavior.
- Exact evidence excerpts and links, with whether each relationship is supported or inferred.
- New/existing/unknown change status and both sides of any displayed comparison.
- Counts and reasons for files read, skipped, or unavailable, plus unresolved external code.
- Practical next actions: open evidence, inspect a missing component, choose another
  revision, or refrain from the concerning setup until reviewed.

Avoid a reassuring green shield, a probability of safety, an automatic install button,
or a one-click deletion/upgrade presented as a verified fix. A prior revision is not
an automatically safe replacement. Never copy sensitive-looking values into a shareable
report when a redacted excerpt can explain the finding.

Illustrative wording, not a real finding: **“The new setup hook invokes a helper that
reads credential files and sends their contents to an external endpoint. The hook and
helper references are shown below. This review covers the selected source commit;
dependencies and remote payloads remain unchecked.”**

## 9. Kimi/Cerebras: real role, unresolved details

The event listing names Kimi K3.1 Pro, but the public model catalogue and capability tables
reviewed here do not establish that private model's ID, context limit, tool-call behavior,
structured-output support, or price. Check the account and the organizer-supplied identifier
at kickoff. Do not substitute parameters from `kimi-k2.7-code` or invent a model name.
[S01](RESEARCH_SOURCES.md#s01), [S31](RESEARCH_SOURCES.md#s31)–
[S36](RESEARCH_SOURCES.md#s36).

Give Kimi investigation decisions, not merely a final summarization step. Keep tool
execution and validation in the backend. Stream actual progress events such as a resolved
commit, completed file read, or validated reference. Do not expose private reasoning
or call a canned activity animation live investigation.

If native tool calling is unavailable but model access works, a constrained JSON action
protocol can be a fallback, with identical allowlists and validation. If output formatting
is unreliable, permit one bounded repair and then return an incomplete result. If the
event model is unavailable, a labeled replay can explain the design but cannot satisfy
a claim that a live Kimi investigation worked.

## 10. Cost, latency, and operations

Measure retrieval, model rounds, validation, time to first useful evidence, total time,
request counts, token use, retries, and cache state. Throughput marketing numbers are
not end-to-end latency results. With repeated model calls, charge each call's input,
including conversation history resent with that call.

Use the formula:

`estimated model cost = total billed input tokens × input rate + total billed output tokens × output rate`

Adjust units and cached-token prices only when those rates apply to the confirmed model.
Do not quote a fabricated dollar cost or guarantee that the preview is free.
[S35](RESEARCH_SOURCES.md#s35), [S37](RESEARCH_SOURCES.md#s37).

GitHub's unauthenticated allowance can be exhausted by a few file-heavy reviews on a
shared server. Plan optional backend authentication with minimal read permissions,
content caching by object identity, request accounting, and clear throttling errors.
Public repositories remain the application policy even if the server credential could
access more. [S26](RESEARCH_SOURCES.md#s26), [S27](RESEARCH_SOURCES.md#s27).

Keep the first deployment local or a controlled demo. A public service needs per-client
and global limits, protected result access, cancellation, cache expiry, and spend controls.
These are event-time engineering choices, not a reason to build account systems now.
Disclose that selected public source is sent to Cerebras; verify account-specific retention
terms before making privacy promises. [S38](RESEARCH_SOURCES.md#s38).

## 11. Do and do not

| Do | Do not |
|---|---|
| Pin a revision and record command assumptions. | Scan a moving branch and imply a later install uses the same source. |
| Follow helpers and review the target setup path. | Inspect only changed manifest lines. |
| Keep independent evidence, path, and interpretation labels. | Treat a valid citation as proof the model is correct. |
| Compare against a selected baseline. | Call the preceding commit clean without evidence. |
| Separate findings from completion/coverage. | Turn timeouts or skipped code into a clean bill of health. |
| Enforce capabilities in backend code. | Trust instructions embedded in the repository or a prompt alone. |
| Read source as bounded data. | Run setup, package-manager metadata generation, or downloaded payloads. |
| Evaluate benign lookalikes and hidden paths. | Demonstrate only a conspicuous fake attack and claim general accuracy. |
| Measure real latency and disclose cache/replay state. | Reuse vendor throughput claims as a measured product speedup. |
| Attribute existing work and measure any comparison. | Claim unprecedented AI malware scanning or guaranteed superiority. |
| Design and document before the event. | Implement the core, functional fixtures, or real scans in this preparation phase. |
| Protect the final event hours for validation and submission. | Add ecosystems until there is no time to test the main workflow. |

## 12. Decision record and next steps

| Decision | Status | Reason |
|---|---|---|
| GitHub repository first | Selected by user | Directly matches the proposed before-setup experience. |
| Node required, Python conditional | Research recommendation | Controls execution-semantics and evaluation scope. |
| Trees/blobs rather than clone/install | Research recommendation | Preserve object identity, file modes, and a narrow retrieval capability. |
| Optional explicit baseline | Research recommendation | Avoid inventing a trustworthy previous version. |
| Hybrid investigation with checked evidence | Research recommendation | Give Kimi useful judgment while keeping permissions and invariants deterministic. |
| No broad safety score or automatic install | Research recommendation | A limited static review cannot justify either promise. |
| Single local/controlled demo before public scale | Research recommendation | Keep operational work within the event budget. |
| npm artifacts, full dependencies, CI, private repos, guards later | Planned sequence | Each requires its own identity, execution, and validation design. |

Before the event: finalize this scope, check registration/capacity access, prepare the
storyboard on paper, and review the provider documentation. During the event: build the
small working path, create safe fixtures, validate it, measure it, record it, and submit.
The [event playbook](EVALUATION_AND_DEMO.md) defines the sequence and cutoffs.

Outstanding uncertainties are explicit: private-model access/capabilities and price,
real detection quality, false-positive behavior, latency, developer demand, and coverage
of code outside the chosen source snapshot. Research narrows the design; it does not
substitute for those measurements.
