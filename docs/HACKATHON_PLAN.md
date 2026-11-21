# BeforeRun build plan

> **Historical event outline — superseded for implementation.** Use
> [MASTER_BUILD_PLAN.md](MASTER_BUILD_PLAN.md) for the complete stages, scope cutoffs,
> OpenClaw tasks, test gates, and broader product roadmap. Event details below are
> recorded historical instructions, not a fresh account-status verification.

Working name: **BeforeRun**. Tagline: **See what runs before you run it.**

Selected direction on **15 November 2026**: **GitHub repository review first**.
This is the first milestone of **Gatekeeper-style package protection plus repository
review**. The [full product scope](PRODUCT_SCOPE.md) preserves package/dependency
investigation while distinguishing it from the work promised for this 24-hour entry.
A developer pastes a public repository URL before running its setup commands. BeforeRun will
inspect a pinned source commit, follow setup code, and compare a selected earlier revision to
explain suspicious changes with evidence. A compromised update can introduce harmful install
behavior even in a previously familiar project. These capabilities do not exist in the scaffold.

Use [COMPLETION_CHECKLIST.md](COMPLETION_CHECKLIST.md) to track preparation, functional
work, verification, and submission. It distinguishes the required first version from
optional and post-event extensions.

## Prepared before the event

- [x] Local project skeleton and Python framework configuration
- [x] Static interface wireframe with disabled investigation form
- [x] Generic health endpoint and development-server entry point
- [x] Environment-variable template, with no credentials or guessed model ID
- [x] Compilation/lint configuration and CI workflow definition
- [x] Timing rule, implementation plan, and private attribution draft
- [x] Framework installation and pinned dependency list
- [x] Local compilation, lint, dependency consistency, and interface/health-route checks

Local validation is recorded in `PREPARATION_CHECKS.md`.
Hosted CI is not verified until the workflow has actually run.

The [research brief](RESEARCH_BRIEF.md), [technical design](TECHNICAL_DESIGN.md), and
[evaluation playbook](EVALUATION_AND_DEMO.md) refine this plan using
[primary sources](RESEARCH_SOURCES.md). Research recommendation: require Node setup
review for the demo and make Python conditional on dedicated validation.

## Core work during 21–22 November

| Time from kickoff | Work |
|---|---|
| 0–1 hour | Verify approved model access, supported tool/response modes, and limits with harmless input. |
| 1–4 hours | Validate public GitHub input, resolve commits, retrieve bounded trees/blobs, and record source identity. |
| 4–7 hours | Implement Node entry-point/helper inspection, optional comparison, and event-created fixtures. |
| 7–11 hours | Implement the bounded Kimi investigator, evidence validation, and partial results. |
| 11–14 hours | Connect the interface and actual progress; make the optional-scope decision at hour 12. |
| 14–18 hours | Exercise required cases, correct false alarms/failures, and freeze features at hour 18. |
| 18–21 hours | Measure latency/usage, verify reproducibility, and finalize documentation/attribution. |
| 21–24 hours | Record a <=60 second demo and submit before the deadline with a time buffer. |

This is an estimate, not a commitment that the full Gatekeeper feature set fits 24 hours.
The event core is one public repository and a useful investigation of selected setup/build
files. Require Node install hooks and referenced helpers first. Python build metadata
and setup paths are conditional on the core passing early and the Python-specific cases
passing before the feature freeze. Unresolved execution paths remain visible gaps.
npm registry input, full dependency analysis, private repositories,
registry-wide monitoring, model fine-tuning, an install guard, and campaign tracking are
separate extensions.

## Optional additions

The [feature backlog](FEATURE_BACKLOG.md) compares proposed additions with Gatekeeper's
documented and reviewed workflows. After the required Node workflow passes, one optional
extension is **Ask the evidence**:
follow-up questions for the current repository, using the same bounded reads and reference checks.
It is estimated at another 2–4 hours after the core works; the schedule above has no reserved
time for it. Add it only if the core passes its checks early, and protect the final six hours
for validation and submission. Project dependency paths, broader application command analysis,
and source-to-release comparisons are later extensions. A small display of unread or unresolved
areas belongs to the core's existing uncertainty requirement.

At hour 12, drop Python and follow-up chat if the Node workflow has not produced valid
end-to-end evidence. Do not add both optional features by default. At hour 18, freeze
features and protect validation, measurement, and submission time.

The [package manager roadmap](PACKAGE_MANAGER_ROADMAP.md) adds npm registry input after
repository review, then PyPI for pip/uv, Homebrew, Cargo, and other ecosystems. The common
investigator can be reused, while artifact retrieval, manager-specific project audits, and
install guards require separate work.

## Selected GitHub repository workflow

[REPOSITORY_REVIEW_PLAN.md](REPOSITORY_REVIEW_PLAN.md) defines the first workflow:
paste a public GitHub URL, pin its commit, inspect setup/build files, compare selected
revisions, and show evidence and unresolved paths. Accept the repository root URL, an
optional target ref, an optional comparison ref, and a command context: review only or
`npm install`. Enable `pip install .` only after the conditional Python adapter passes.
The selected command is analysis context, never a command for BeforeRun to execute. All source reads and evidence links use the resolved
commit, even if the branch moves during review. A previous commit is a comparison
baseline rather than proof of a clean version.

## Acceptance checks for the event core

- Kimi K3.1 Pro on Cerebras makes investigation decisions; its role goes beyond presentation text.
- Repository code is inspected as data rather than executed; no installation or build occurs.
- URL/ref resolution, source reads, comparison, and evidence links use the same pinned commits.
- Every displayed reference is checked against the file and lines actually read.
- Installation-time claims are checked against the intended command and visible script/file chain.
- A harmless revision, a fictional harmful setup update, and a cleared apparent flag are demonstrated.
- Incomplete coverage or upstream failure produces uncertainty, not a declaration of safety.
- Latency numbers come from real timed runs. Provider comparisons use the same task and disclose differences.
- Replays, if needed, are labeled and never represented as live model calls.
- Public documentation identifies inspiration, reused components, and actual contributions accurately.

## Demo storyboard to develop during the event

**The update that changed everything.** Develop a clearly labeled fictional repository with
two commits during the event. The second connects an install hook to code referencing dummy
sensitive data and a controlled destination. Paste its URL and select the two revisions.
Show the real investigator finding the change, following the setup path, and citing evidence.
Show a benign install script being cleared too. BeforeRun reads the fixture as data and never
executes its setup code. Measure the actual run and fit the recording within 60 seconds.

## What the rules do not settle

The pasted FAQ does not expressly say that an exact copy of someone else's completed product
qualifies. Attribution and an upstream license do not override the core-development rule.
If the plan changes to importing Gatekeeper's finished core, ask the organizers about eligibility
before treating that fork as the competition entry.
