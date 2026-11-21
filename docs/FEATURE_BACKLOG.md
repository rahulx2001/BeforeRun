# BeforeRun feature backlog

> **Background backlog.** The updated feature mapping, priorities, estimates, and
> independently gated milestones are in
> [the master roadmap](MASTER_BUILD_PLAN.md#23-full-gatekeeper-style-roadmap).
> Follow that plan for implementation; this file preserves earlier proposals/research.

Reviewed on **14 November 2026**. These are proposals, not implemented capabilities.
Scope updated on **15 November** to select GitHub repository review first. The
investigator and every functional extension must be developed during the
hackathon or afterward, following [the recorded timing rule](HACKATHON_RULES.md).

The [product scope](PRODUCT_SCOPE.md) clarifies that repository review is an addition
to the intended Gatekeeper-style package/dependency product. This backlog and the
GitHub-first schedule do not claim that BeforeRun already reproduces Gatekeeper.

The [research brief](RESEARCH_BRIEF.md) adds a broader existing-tool comparison,
a Node-first required demo, and conditional Python scope. Follow its
[evaluation gates and feature cutoffs](EVALUATION_AND_DEMO.md) before adding extensions.

## What the upstream project already covers

Reference: [Gatekeeper](https://github.com/lb2002/gatekeeper), reviewed at revision
[`072210e`](https://github.com/lb2002/gatekeeper/tree/072210e91b19e3174d4afecefe1464acb0ca2c25).
The review used its README, repository tree, investigator, lockfile audit,
install-reachability checker, and demo-page source. This is a comparison of those
workflows, not a claim of global originality or an exhaustive upstream audit.

- [The README](https://github.com/lb2002/gatekeeper/blob/072210e91b19e3174d4afecefe1464acb0ca2c25/README.md)
  already documents agent investigation, validated citations, version/fork comparisons,
  a PR audit/GitHub Action, an install guard, release waiting periods, registry monitoring,
  campaign memory, and a timestamped detection ledger.
- [The audit](https://github.com/lb2002/gatekeeper/blob/072210e91b19e3174d4afecefe1464acb0ca2c25/src/gatekeeper/audit.py#L45)
  retains a flat list of locked package versions. Its reviewed output identifies findings
  but does not retain the dependency paths that explain which direct dependency introduced them.
  It reads lockfiles rather than application code.
- [The reachability checker](https://github.com/lb2002/gatekeeper/blob/072210e91b19e3174d4afecefe1464acb0ca2c25/src/gatekeeper/evidence/reach.py#L1)
  follows visible relative imports from a package's install roots. This already addresses
  package-level install claims; application commands and application entry points are a
  separate context to add. A failed static check does not establish that code cannot run.
- [The demo](https://github.com/lb2002/gatekeeper/blob/072210e91b19e3174d4afecefe1464acb0ca2c25/src/gatekeeper/report/try_page.py#L34)
  accepts a package or lockfile and displays results. The reviewed interface has no
  user follow-up question workflow.
- The audit already reports unread packages, and the guard already verifies tarball
  integrity. A coverage display improves usability; source-to-release comparison asks
  a different question from checking the downloaded file against its registry checksum.

## Ranked additions

The selected [GitHub repository workflow](REPOSITORY_REVIEW_PLAN.md) addresses setup/build
code introduced in a repository update, with commit-pinned evidence and optional comparison.
It is the event core. npm registry input follows later; do not add all repository and
package-manager coverage to one 24-hour build. Limited root setup-command context belongs
to the core, while dependency paths and broader command analysis remain extensions.

Estimates are additional hands-on development time **after the event core works**.
They include basic verification, depend on the core's design, and are not commitments.
Do not add these estimates to the existing 24-hour schedule and assume everything fits.

| Priority | Addition | Developer benefit | First useful scope | Estimated extra effort | Timing |
|---|---|---|---|---|---|
| 1 | Ask the evidence | Ask why a finding matters or whether an apparent flag has a benign explanation. | Follow-up questions for the current repository investigation, with checked citations and bounded extra reads. | 2–4 hours | One optional hackathon extension if ahead of schedule. |
| 2 | Why is this dependency here? | Identify the direct dependency responsible for a flagged transitive package. | One npm lockfile v2/v3 plus the root manifest; show paths to the exact installed version. | 4–8 hours | After the hackathon, unless the core finishes substantially early. |
| 3 | Broader project command context | Extend the root setup path to application commands and dependencies. | One npm workspace/project, selected build/start commands, and explicit source/dependency relationships. | 1–2 days | After the hackathon; root setup context is already core scope. |
| 4 | Published package versus source | Notice install behavior present in the npm release but absent from its claimed source revision. | One public npm tarball and an explicitly selected source revision; compare manifest hooks and relevant files. | 1–3 days | After the hackathon. |
| Supporting improvement | Show what remains unchecked | Make investigation limits visible before a developer acts. | Read files, verified references, skipped files, unavailable dependencies, and unresolved execution paths. | 1–2 hours | Include a small display while implementing the core's required uncertainty states. |

### 1. Ask the evidence

Example: after a finding, the developer asks, **“Is this normal build tooling, or does
it read secrets?”** Kimi inspects the relevant code and answers with links to the exact
evidence. A second question can request another targeted read rather than receiving
an unsupported paraphrase of the first verdict.

Keep this to the current repository/session. Use the same read and citation checks as
the investigator. An answer must distinguish code it has seen, a possible execution
path, and a conclusion it cannot establish. File/line validation establishes that a
reference exists; it does not independently prove the model's interpretation correct.

Validation: a supported answer links to real evidence; an unsupported premise is
challenged; an unanswered question stays uncertain; a bounded session cannot exceed
the configured read/model budget. Repository text remains data during follow-ups too.

This gives Cerebras a visible role: the developer asks a new question and watches
the model make targeted investigation decisions. Measure real question-to-answer
latency; do not promise a speedup before measurement.

### 2. Why is this dependency here?

Example, using fictional package names:

```text
my-app -> chart-widget@2.1.0 -> hidden-helper@0.4.2
```

The finding tells the developer which dependency they can review, upgrade, or remove.
Track installed paths and versions rather than merging every package with the same name.
Show multiple introducing paths where applicable. An npm `dev`/`optional` label describes
dependency metadata, not proof that an install hook cannot affect a workstation or CI.

Validation: two installed versions of the same package retain different paths; hoisted
and nested dependencies resolve correctly; unsupported aliases/workspaces produce a
visible gap. Start with npm only; pnpm and Yarn are separate later work.

### 3. Broader project command context

The repository core already uses the intended root setup command and visible script/file
chain. This extension adds application build/start commands, workspace context, and
relationships to dependencies after the relevant package/project adapters exist.

Example: for **`npm run build`**, show the root build script and any directly named file,
then explain which cited behavior is associated with that path. Present install-time
behavior separately because it can execute even if the application never imports the
dependency. Apply lifecycle rules for the actual command rather than treating every
script as automatically executed.

The first version must describe only supported command/file relationships. Custom shell
logic, computed imports, native code, and bundler transformations can remain unresolved.
Do not claim complete application reachability or declare a dependency safe because a
static path was not found. Read configuration/source as data and never run the chosen command.

### 4. Published package versus source

Example: an npm release adds `postinstall: node setup.js`, but that hook and file do not
appear in the source revision supplied for the comparison. Show both manifests and the
extra file so a developer can investigate the discrepancy.

This is different from the version comparisons already in Gatekeeper and the commit
comparisons in BeforeRun's event plan.
It compares distribution contents with source, not one npm version with another.
Generated bundles and extra release files are common legitimate differences. Report
discrepancies rather than equating them with malware. A repository URL alone does not
prove which commit produced a release; label the selected revision and mapping uncertainty.

Signed provenance verification can be a later extension, using established verification
tools and checking the artifact digest and expected repository/revision. Kimi can explain
the verified facts; it must not decide whether a signature is cryptographically valid.

### Supporting improvement: show what remains unchecked

Turn the event core's uncertainty requirement into a short, visible display. For example,
**“Install entry file read; 3 references checked; native binary not inspected.”** Populate
it from actual inspection records. Use declared scope and inspected/unknown states rather
than a percentage that could be mistaken for a probability of safety.

## Recommended hackathon scope

Complete the selected [event core](HACKATHON_PLAN.md) first: one pinned public GitHub
repository, live Kimi investigation on Cerebras, optional commit comparison, verified
references, supported setup paths, and honest limits.
Make those limits visible as part of the result screen.

If the core passes its acceptance checks early, select **Ask the evidence** as the one
optional addition. Protect the final six hours for verification, measurement, recording,
and submission. Otherwise defer the addition; the current plan already uses all 24 hours.
Keep the fix preview and exposure map discussed earlier in the backlog too, rather than
trying to implement them all alongside these proposals.

Product direction after the event: **a developer can learn what a package does, why it is
in their application, and which actions could expose them to that behavior.**

## Additional package ecosystems

The [package manager roadmap](PACKAGE_MANAGER_ROADMAP.md) adds npm registry input after
repository review, then PyPI investigation for pip/uv, Homebrew, and Cargo. It also
records later candidates such as
Composer, NuGet, Maven/Gradle, Go, Conda, and apt/dnf. Package investigation, project audits,
and install guards have separate coverage for each tool; ecosystem names do not establish
working support. These extensions sit outside the existing event schedule.

## Demo extension, if implemented during the event

Use the event's clearly labeled fictional repository with two commits. The investigator notices
the new install hook and cites the relevant file. Ask **“Does this read a secret, or only
check the Node version?”** Show Kimi's real targeted read, the answer with checked
references, and a real elapsed time. End on the evidence and remaining limits.
This must fit inside the hackathon's 60-second demo limit; keep it out of the recording
if it crowds out the core workflow.
