# BeforeRun completion checklist

> **Historical checklist.** Follow the authoritative task checklists and release gates
> in [MASTER_BUILD_PLAN.md](MASTER_BUILD_PLAN.md), especially sections 20, 22, and 28.
> Entries below preserve preparation history; they do not establish current scanner functionality.

Selected target on **15 November 2026**: a developer pastes a public GitHub repository
URL, optionally selects revisions and an intended setup command, and watches Kimi
investigate the pinned source on Cerebras. The result explains setup behavior and
changes with checked code references and visible gaps. See
[the repository review plan](REPOSITORY_REVIEW_PLAN.md) for scope and acceptance criteria.
npm package input follows this workflow in a later stage. The broader target is
Gatekeeper-style package protection plus repository review, as clarified in
[PRODUCT_SCOPE.md](PRODUCT_SCOPE.md). Completing this checklist establishes the
event milestone; it does not establish full Gatekeeper feature parity.

The [research pack](RESEARCH_BRIEF.md) refines the required demo to Node setup review;
Python is conditional. Use the [technical specification](TECHNICAL_DESIGN.md) and
[evaluation gates](EVALUATION_AND_DEMO.md) when implementing these tasks during the event.

Status recorded on **14 November 2026**: the local preparation scaffold is ready.
The functional tasks below remain to be developed. Core development belongs in the
**21 November, 23:30 IST → 22 November, 23:30 IST** event window, under
[the supplied rule](HACKATHON_RULES.md). Registration and capacity-request status have
not been verified by this workspace.

## Preparation before kickoff

- [x] Python framework, local development commands, and pinned development dependencies.
- [x] Static interface wireframe, generic health endpoint, and environment template.
- [x] Local scaffold checks, recorded in [PREPARATION_CHECKS.md](PREPARATION_CHECKS.md).
- [x] Event build plan, feature backlog, and private attribution draft.
- [ ] Register for the event and sign up for Cerebras Cloud.
- [ ] Submit the Cerebras Organization ID through the capacity-request form before
  **21 November, 08:30 IST**. Use the links in [HACKATHON_RULES.md](HACKATHON_RULES.md).
- [ ] Verify approved access to the organizer-supplied `moonshotai-kimi-k3.1-pro-trial`
  through the OpenClaw Gateway. See [EXECUTION_GUIDE.md](EXECUTION_GUIDE.md).
- [x] Select GitHub repository review as the first workflow, ahead of npm package input.
- [ ] Finalize the demo storyboard on paper. Develop source retrieval, the investigator,
  inspection logic, and functional demo fixtures during the event.

## Required functional work during the event

### 1. Repository input and retrieval

- [ ] Accept a public GitHub root URL, an optional branch/tag/commit, an optional
  comparison revision, and review-only or `npm install` context. Python context is conditional.
- [ ] Resolve the selected/default branch and optional baseline to exact commits.
  Show the repository identity and commits used; all source reads use those revisions.
- [ ] Retrieve Git trees and approved blobs as data with bounded requests, entries, bytes, and timeouts.
  Validate URLs, refs, redirect destinations, paths, and file types. Repository code
  is never installed, imported, or executed by BeforeRun.
- [ ] Record truncated listings and unread symlink, submodule, LFS, binary, and oversized
  content as gaps. Do not follow repository-controlled URLs to fetch extra code.
- [ ] Handle invalid input, missing/private repositories, unavailable refs, rate limits,
  unsupported sources, and failed retrievals with useful messages.

### 2. Static inspection and Kimi investigator

- [ ] Read Node manifests/install hooks and relevant configuration, then local helpers
  and visible file/import relationships. Supply numbered excerpts. Record the supported
  command/version assumptions and unread dependencies as gaps.
- [ ] Treat the selected command as analysis context. Follow only supported lifecycle
  rules and visible relationships; never run the command or setup/build code.
- [ ] Confirm the approved Kimi K3.1 Pro model ID and access through Cerebras; keep
  the API key on the backend.
- [ ] Let Kimi choose bounded read/search steps and use the resulting evidence to
  investigate. Configure reasoning only with documented, supported settings.
- [ ] Enforce timeouts, step/token limits, and bounded handling of rate limits or
  failed responses. A failed or partial investigation must remain visible.
- [ ] Keep repository comments, README text, and source contents as untrusted data;
  they cannot change investigation instructions or authorize additional tool access.

### 3. Commit changes and evidence checks

- [ ] Compare the target with the selected baseline commit when supplied; show changed
  scripts/files and the exact revisions. Use the pinned tree maps rather than assuming
  the comparison API lists every changed file. A baseline is not presumed clean or trusted.
- [ ] Review the target setup path even when its hook is unchanged. If no baseline was
  requested, make only snapshot claims. If a requested baseline is unavailable, show
  the gap rather than silently presenting a complete comparison.
- [ ] Check every displayed code reference against the file and lines actually read.
  Do not display invented references as verified evidence.
- [ ] Check an install-time claim against the command, relevant hook, and visible file chain.
  Unresolved paths remain uncertain; an absent static path does not prove safety.
- [ ] Show a finding or scoped absence of concerning findings, a plain explanation,
  supporting references, and unresolved questions. Citation checks establish that
  referenced text exists, not that every model interpretation is correct.
- [ ] State that the result applies to the inspected commit and selected source files.
  Later revisions, registry artifacts, external downloads, and transitive dependencies
  require further review; source findings do not establish account compromise.

### 4. Working interface

- [ ] Enable the existing repository/revision/command form once it is connected to
  the real backend.
- [ ] Display genuine progress: retrieval, files inspected, investigation steps,
  evidence checks, and completion. Label any replay as a replay.
- [ ] Make references open the relevant excerpt. Keep the commit comparison and
  explanation readable on a laptop and phone.
- [ ] Show what was read, skipped, or unavailable. Distinguish an incomplete result
  or service error from a completed investigation. Show findings and coverage independently.

### 5. Verification and performance

- [ ] Exercise three event-created cases: a harmless repository revision, a fictional
  harmful setup update, and legitimate build behavior that an initial flag could misread.
  Any sensitive values in fixtures are dummy values; analysis does not execute fixtures.
- [ ] Verify invalid input, unavailable refs/baselines, retrieval limits, branch movement,
  bad citations, unresolved execution paths, prompt injection in repo text, and API failures.
  Include an unchanged hook with a changed helper and a partial investigation. Use focused
  tests where they verify meaningful parsing, evidence-validation, or investigation behavior.
- [ ] Measure real time to first useful progress and total investigation time;
  record the repository/commits, model/settings, command context, and relevant cache state.
- [ ] Run the project's required checks and a full user workflow after integration.
  Resolve failures before recording the final demo.

## Conditional event extensions

- [ ] **Python setup review:** implement declared backend/in-tree path handling as data,
  record unread backends, and pass dedicated harmless, concerning, custom-backend, and
  missing-backend cases before enabling the selector.
- [ ] **Ask the evidence**: support follow-up questions for the current investigation,
  with bounded additional reads and the same reference checks. Estimate: another
  **2–4 hours after the core works**.

Select optional scope only if the required workflow passes early. At hour 12, drop
Python and follow-up chat if the Node path is not complete with valid evidence. Do not
assume both fit. Freeze features at hour 18 and protect the final six hours for
verification, measurement, demo recording, and submission.

## Release and submission

- [ ] Write README setup/use instructions, the actual feature scope, limitations,
  and Kimi/Cerebras's role.
- [ ] Finalize [ATTRIBUTION_DRAFT.md](ATTRIBUTION_DRAFT.md) before public release or
  submission. Identify Gatekeeper inspiration and actual reused material accurately;
  retain applicable license/notice requirements for anything reused.
- [ ] Prepare a runnable GitHub repository if publishing it; the FAQ recommends a
  repository. Provide reproducible startup instructions and omit credentials.
- [ ] Record a **maximum 60-second** demo showing the working investigation and how
  actual Cerebras inference latency affects the experience. A provider comparison is
  optional; if included, measure the same task and disclose relevant differences.
- [ ] Prepare the project name, team members, 2–4 sentence description, and video.
- [ ] Publish the official X submission tagging `@Cerebras` and `@Kimi_Moonshot` with
  `#KimiOnCerebras`. Reddit is optional with the official event flair; Discord is for
  announcements and support.
- [ ] Complete submission before **22 November, 23:30 IST**. The next day's preview
  access does not extend the deadline.

## After the hackathon

These are separate extensions with their own implementation and verification work.
See [FEATURE_BACKLOG.md](FEATURE_BACKLOG.md) for researched scope and estimates.

1. Fix preview: propose a dependency change and investigate the replacement before
   presenting it as a candidate fix.
2. Exposure map: connect the cited entry point, file behavior, sensitive resource,
   and destination; distinguish observed facts from unresolved relationships.
3. Dependency trail and application command context: explain why a package is in
   the developer's project and which supported commands could reach a finding.
4. Published-package/source comparison and, later, verified provenance.
5. Lockfile audits and PR/CI integration.
6. Install guard and project policies, with an explicit supported-command scope.
7. Add npm registry package input, then PyPI investigation for pip/uv and Homebrew,
   followed by Cargo and other candidates in [PACKAGE_MANAGER_ROADMAP.md](PACKAGE_MANAGER_ROADMAP.md).
   Project/lockfile audits and install guards are separate capabilities for each manager.
8. MCP integration for coding assistants.
9. Registry monitoring and campaign tracking, after repository review and the relevant
   registry package workflow are reliable and their detection limits have been evaluated.

## Definition of complete

The required boxes represent a complete first version when a fresh local setup can run
the repository-to-evidence workflow, all three demo cases behave as reviewed, failures and
coverage gaps are visible, and the demo and description are submitted on time. Optional
and post-event extensions do not block completing this version.
