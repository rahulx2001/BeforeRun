# BeforeRun research sources

Research date: **15 November 2026**. This register supports the
[research brief](RESEARCH_BRIEF.md), [technical design](TECHNICAL_DESIGN.md), and
[evaluation and event playbook](EVALUATION_AND_DEMO.md). These documents are research
and specifications, not implemented functionality.

The 43 numbered entries below are primary sources: official documentation, project
repositories, incident reports from affected maintainers or investigators, and original
research. Product descriptions establish documented features, not independently measured
quality. Preprints are identified as such. Proposed limits, priorities, and acceptance
criteria in our documents are our engineering recommendations, not vendor guarantees.

## S01

**Cerebras x Kimi hackathon event listing.**
https://luma.com/cerebras-kimi-hackathon

The public listing identifies the event, its 21–22 November 2026 schedule, and the
Kimi K3.1 Pro/Cerebras theme. Use it for the event context. Detailed eligibility,
private-preview quotas, and submission instructions also depend on the supplied FAQ
recorded locally; the listing does not independently confirm every FAQ detail. It does
confirm the capacity-request deadline of November 20, 7:00 PM Pacific Time.

## S02

**npm: lifecycle scripts.**
https://docs.npmjs.com/cli/v11/using-npm/scripts/

Documents command-specific hooks, including install/prepare behavior and legitimate
build uses. A script's presence is not proof that every command executes it. Rules
must match the supported npm version and invocation.

## S03

**npm: configuration.**
https://docs.npmjs.com/cli/v11/using-npm/config/

Documents settings such as `ignore-scripts`. Explicit script commands and their
associated hooks have distinctions that must be preserved. Do not describe one flag
as making arbitrary repository use safe; inspect relevant configuration as data.

## S04

**pip: build-system interface.**
https://pip.pypa.io/en/stable/reference/build-system/

Describes dependency setup, metadata hooks, and wheel building through a backend.
Build isolation concerns Python dependency environments; it is not evidence of a
security sandbox. Do not invoke metadata/build operations to inspect an untrusted project.

## S05

**PEP 517: source-tree build-system interface.**
https://peps.python.org/pep-0517/

Defines build hooks and in-tree backends, including `backend-path`. Python review
must account for backend code and imported helpers, with explicit unknowns when those
are not inspected. A `pyproject.toml` file does not eliminate executable build behavior.

## S06

**Python: site-specific configuration.**
https://docs.python.org/3/library/site.html

Documents interpreter startup mechanisms including executable lines in `.pth` files.
This supports a future Python artifact review requirement; it is not coverage supplied
by inspecting a root repository's `setup.py` alone.

## S07

**Nx maintainer report: S1ngularity postmortem.**
https://nx.dev/blog/s1ngularity-postmortem

The affected project's account describes a publishing compromise and malicious
package behavior. Use it to distinguish CI/publishing compromise from a visible source
commit. Its incident-specific scope does not establish BeforeRun's detection capability.

## S08

**GitHub advisory: tj-actions/changed-files compromise.**
https://github.com/advisories/GHSA-mrrh-fwg8-r2c3

Documents the compromised action and exposure through CI logs. This is a CI execution
case, not an npm installation case. Findings must identify the execution context.

## S09

**GitHub: strengthening supply-chain security after Shai-Hulud.**
https://github.blog/security/supply-chain-security/strengthening-supply-chain-security-preparing-for-the-next-malware-campaign/

GitHub's response discusses an npm supply-chain compromise and package/credential
protection. Use it as evidence that account, source, publishing, and installed artifact
controls are separate layers; do not imply one source scan covers the whole chain.

## S10

**SLSA v1.2: threats overview.**
https://slsa.dev/spec/v1.2/threats-overview

Separates source, build, distribution, and dependency threats. It informs the boundary
of the proposed review; BeforeRun is not being claimed as SLSA compliant or as a complete
implementation of its mitigations.

## S11

**npm: provenance statements.**
https://docs.npmjs.com/generating-provenance-statements/

Provenance connects an artifact to source/build information. It does not establish
that the contents are benign. Artifact/provenance verification is a later capability,
separate from this event's source review.

## S12

**Gatekeeper README at the previously reviewed revision.**
https://github.com/lb2002/gatekeeper/blob/072210e91b19e3174d4afecefe1464acb0ca2c25/README.md

Read through the corresponding raw README. It documents an agent investigator,
reference verification, comparisons, audit/guard workflows, and other protections.
This is substantial overlap. The comparison is pinned to this revision and is not
an assertion about every current branch or a measured comparison of quality.

## S13

**Socket: alerts reference.**
https://docs.socket.dev/docs/alert-types

Describes behavior-oriented supply-chain signals, including potentially malicious
package behavior. This prevents claiming that behavior-based supply-chain analysis is
new. Vendor documentation alone does not demonstrate comparative detection accuracy.

## S14

**Datadog: GuardDog 3.0.**
https://securitylabs.datadoghq.com/articles/guarddog-3-0-release/

Describes a static YARA-based engine, attack-stage correlation, and scanner isolation.
The FAQ explicitly says GuardDog does not use LLMs or execute package code. Its scanner
sandbox protects analysis; it is not a package detonation system. Compare measured
results before making any performance claim.

## S15

**Semgrep documentation.**
https://semgrep.dev/docs/

Documents static analysis and rule-based workflows. Semgrep can be a future integration
or a measured baseline. It is not a complete answer to runtime-dependent malicious
behavior, and no Semgrep integration is implemented here.

## S16

**OSV-Scanner project documentation.**
https://google.github.io/osv-scanner/

Documents dependency identification and matching against vulnerability information,
including supported analysis features. Known-advisory lookup and investigation of
previously unseen source behavior are different evidence sources; combine them later
rather than treating either as universal malware detection.

## S17

**GitHub: dependency review.**
https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review

Documents dependency changes and known-vulnerability information for pull requests.
Use it as a complementary existing workflow. This research does not claim that GitHub
has no other code-security or malware defenses.

## S18

**OpenSSF Scorecard checks.**
https://github.com/ossf/scorecard/blob/main/docs/checks.md

Describes repository security-practice checks. Repository practice signals can provide
context, but they do not prove the behavior of the exact install path being inspected.
Stars, popularity, and an aggregate score are not substitutes for code evidence.

## S19

**OpenSSF Package Analysis.**
https://github.com/ossf/package-analysis

Its README describes installing/executing packages in an instrumented sandbox and
recording behavior. This is a different operational scope from a static source review.
Do not reproduce package execution inside BeforeRun's event service.

## S20

**OpenSSF malicious packages database.**
https://github.com/ossf/malicious-packages

Provides OSV-format reports about malicious packages and their provenance. These are
useful labels and pointers, not automatically a runnable, balanced benchmark. Check
record details and rights before assembling any later evaluation corpus.

## S21

**Datadog malicious software packages dataset.**
https://github.com/DataDog/malicious-software-packages-dataset

Offers research material for package-malware analysis. It is not required for the
hackathon demo, and malicious artifacts should not be installed on the development
machine. This research session used documentation only.

## S22

**GitHub REST: commits and comparison.**
https://docs.github.com/en/rest/commits/commits

Supports commit resolution. The comparison API has a documented changed-file limit;
pagination does not make an omitted file list complete. Use two pinned tree snapshots
for our bounded diff, with the fetched scope recorded.

## S23

**GitHub REST: Git trees.**
https://docs.github.com/en/rest/git/trees

Tree entries distinguish ordinary blobs, symlinks, and submodules. Recursive responses
can be truncated. BeforeRun must respect the returned flag and its own stricter limits;
a missing entry in a partial listing is not proof of absence.

## S24

**GitHub REST: Git blobs.**
https://docs.github.com/en/rest/git/blobs

Supports retrieving file contents by object identity. Fetch only approved blob IDs from
the pinned tree and enforce application size limits before and during decoding.
The provider's maximum supported object size is not an appropriate product budget.

## S25

**GitHub REST: repository contents.**
https://docs.github.com/en/rest/repos/contents

Documents directory/file limits and automatic handling of some symlinks. These semantics
are why the recommended event design uses trees and blobs for its source reads instead
of relying on contents responses to identify safe ordinary files.

## S26

**GitHub REST: rate limits.**
https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api

Documents a 60-request hourly unauthenticated limit and higher authenticated allowances,
with account-specific and secondary limits. Plan caching, bounded concurrency, and
visible throttling. Do not promise a per-user quota for traffic sharing one server/IP.

## S27

**GitHub REST: best practices.**
https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api

Covers response headers, rate-limit handling, pagination, and request behavior.
Use bounded retries and a documented API version. No source text should control
retry policy, credentials, or outbound destinations.

## S28

**OWASP: SSRF prevention cheat sheet.**
https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html

Explains allowlisting and redirect-related bypass concerns. Our design goes further
by constructing requests to fixed GitHub API endpoints instead of accepting arbitrary
fetch URLs from the user or the model.

## S29

**OWASP: LLM prompt injection prevention cheat sheet.**
https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html

Covers indirect instructions in retrieved material and layered controls. Prompts alone
do not establish isolation. Server-side tool permissions, bounded evidence access, and
adversarial evaluation remain necessary even with a well-written system prompt.

## S30

**OWASP: cross-site scripting prevention cheat sheet.**
https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html

Supports treating filenames, source excerpts, and model output as untrusted display
content. The event UI should render text safely and avoid interpreting repository
HTML or automatically loading repository-supplied images.

## S31

**Cerebras: model overview.**
https://inference-docs.cerebras.ai/models/overview

Provides the public model catalogue. It does not establish the private-preview
Kimi K3.1 Pro model ID or all its capabilities. Preserve that distinction in configuration,
estimates, and the kickoff checklist.

## S32

**Cerebras: tool use.**
https://inference-docs.cerebras.ai/capabilities/tool-use

Documents tool-call message handling and model-dependent support. Verify the actual
event model with a harmless tool at kickoff. Do not assume features from another Kimi
model transfer unchanged to the private preview.

## S33

**Cerebras: structured outputs.**
https://inference-docs.cerebras.ai/capabilities/structured-outputs

Describes schema-oriented response mechanisms and model restrictions. Even a schema-valid
report can be wrong about code. Server validation must check evidence identity, locations,
allowed values, budgets, and supported relationships independently.

## S34

**Cerebras: streaming.**
https://inference-docs.cerebras.ai/capabilities/streaming

Documents streamed responses. User-visible progress should come from actual completed
retrieval/tool/validation events; internal model reasoning is not required as a product
feature. Partial structured content is not a finalized report.

## S35

**Cerebras: rate limits.**
https://inference-docs.cerebras.ai/support/rate-limits

Explains request/token quotas and headers. The account's event allocation must be verified;
the locally recorded FAQ figures are planning assumptions until access is confirmed.
Context-window capacity and tokens-per-minute are different constraints.

## S36

**Cerebras: list models API.**
https://inference-docs.cerebras.ai/api-reference/models/list-models

Provides a way to inspect available model identifiers, subject to the actual account
and preview behavior. If private access is not exposed there, obtain the exact identifier
from the organizer/provider rather than guessing it.

## S37

**Cerebras inference pricing.**
https://inference-docs.cerebras.ai/support/pricing

Use the approved model's input/output prices and account billing terms when available.
Public pricing for a different model is not evidence of private-preview pricing.
This research therefore supplies a cost formula, not an invented per-scan dollar amount.

## S38

**Cerebras support policies.**
https://inference-docs.cerebras.ai/support/policies

The retrieved page is a policy index; its extracted FAQ did not expose answers sufficient
to verify inference retention or training-data behavior. Account terms need verification
before promising either. The proposed first workflow handles public repositories, still discloses that
selected source is sent to Cerebras, and never sends backend API credentials to the model.

## S39

**How Effective Are NPM Malicious Package Detectors? A Large-Scale Empirical Study.**
https://arxiv.org/abs/2603.27549

The preprint studies malware detection and evasions in the npm ecosystem. It motivates
mutation, false-positive, and cross-tool tests. Its measurements do not establish
BeforeRun's accuracy and should not be copied into the pitch as our results.

## S40

**TESSERACT: eliminating experimental bias in malware classification.**
https://www.usenix.org/conference/usenixsecurity19/presentation/pendlebury

Original research on evaluation bias across time and populations. Apply the general
lesson when constructing future package benchmarks: avoid family/near-duplicate leakage
and separate tuning data from held-out evaluation. Its original malware setting differs
from this repository-review product.

## S41

**Visual Studio Code: Workspace Trust.**
https://code.visualstudio.com/docs/editing/workspaces/workspace-trust

Explains risks from workspace-controlled execution and restrictions in untrusted
workspaces. Opening a project, running its setup, and executing CI are distinct contexts.
IDE/devcontainer automation is a later review surface, not event-demo coverage.

## S42

**GitHub Actions: secure use reference.**
https://docs.github.com/en/actions/reference/security/secure-use

Discusses workflow attack surfaces and action pinning, including the distinction between
mutable tags and exact commits. CI analysis must follow workflow-specific execution
relationships rather than applying npm installation rules.

## S43

**Gatekeeper license at the reviewed revision.**
https://github.com/lb2002/gatekeeper/blob/072210e91b19e3174d4afecefe1464acb0ca2c25/LICENSE

Read through the raw license. Retain accurate attribution and applicable notices for
any material actually reused. No upstream application code was imported for this research;
the existing attribution draft remains a publication task.

## Local evidence and unresolved checks

- **L01 — supplied event FAQ:** [HACKATHON_RULES.md](HACKATHON_RULES.md) records the
  preparation boundary, detailed times, quotas, and submission requirements supplied
  earlier. The FAQ short link did not yield usable contents during this research session.
  These details are therefore marked as supplied rules rather than independently
  reverified organizer text. Resolve any discrepancy with the organizers before submission.
- **L02 — workspace inspection:** the FastAPI app serves static pages and health status;
  the investigation form is disabled. Existing design screenshots are presentation
  artifacts, not executed scan results.
- **L03 — user decision:** GitHub repository review was selected before npm package input.
  The further recommendation to require Node first and gate Python on validation is
  based on this research, not an existing implemented capability.
- The reel's specific incident could not be identified from the description alone.
  The documented cases above illustrate the threat; none is asserted to be that reel.
- No live malicious payload, package installation, detector benchmark, provider billing
  measurement, model call, or hosted CI run was performed as part of this research.
- External pages can change. Recheck model access, relevant package-manager semantics,
  provider limits, and event requirements at kickoff; pin versions used in evaluations.
