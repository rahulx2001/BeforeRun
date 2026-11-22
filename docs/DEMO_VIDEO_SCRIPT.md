# BeforeRun — 60-second introduction and demo

Record a short screen demonstration with a face-camera introduction if desired. Open on
the helper comparison, then use the saved fixture storyboard. Keep **MOCKED FIXTURE —
NO LIVE MODEL CALL** visible throughout. This is an offline prototype demonstration;
do not show a real repository being executed, invent live progress, or present fixture
timing/IDs as measurements. The install command should appear on screen, not be executed.

The voiceover is about 130 words. At roughly 160 spoken words per minute, it leaves about ten
seconds for clicks and visual holds. The timestamps include those holds. Read naturally;
slow down slightly over the evidence and comparison views.

## Final script and screen sequence

| Time | Voiceover | Screen |
|---|---|---|
| 0–5s | “The GitHub setup command stayed the same. Its helper changed.” | Start on the fixture helper diff. Highlight the two changed lines. Overlay: **Same command. Changed helper.** |
| 5–11s | “Meet BeforeRun, a tool for reviewing setup source before you run it.” | Reveal the product name, then the repository form. |
| 11–20s | “This is a mocked walkthrough. Paste a public GitHub URL and pick two versions to compare.” | Use the input fixture frame. Point to repository, root npm install and target/baseline fields. Advance to the saved report; do not imply a live submission. |
| 20–27s | “First, BeforeRun pins that exact version and reads supported npm setup source without executing the repository.” | Zoom into pinned target/baseline metadata. Overlay: **Exact version. Source only.** |
| 27–34s | “Now compare the helper. Its Node requirement changes from twenty to twenty-two. This is a compatibility update.” | Show `requiredMajor = 20` → `requiredMajor = 22`. Keep the compatibility label visible. |
| 34–41s | “Open the simulated finding. Inspect the quoted code and its original line numbers.” | Show the inert evidence frame. Point to the source lines; keep **SIMULATED FINDING** visible. |
| 41–46s | “Now check coverage. Missing evidence is listed, and this report stays partial.” | Show coverage/exclusions and highlight **partial** plus the unresolved helper. |
| 46–56s | “Finally, OpenClaw is the configured reviewer, with Cerebras primary and Muse Spark Open on Baseten as fallback. Live model proof is still pending.” | Use a simple provider diagram marked **CONFIGURED · LIVE VALIDATION PENDING**. Keep it still; do not depict a completed real model request. |
| 56–60s | “BeforeRun. Review the source before you run it.” | Return to the helper/source view with the wordmark. End on the final word. |

Use a small highlight or crop every two to three seconds to guide attention. Hold the
important source/coverage text long enough to read. The first frame should contain the
comparison, not an empty logo card. Avoid footage of `.env`, provider configuration,
credentials, personal logs or unredacted responses.

## Two alternate openings

1. “What will this GitHub project run during setup?”
2. “Would you trust a setup warning without seeing the code?”

## Caption

Same command. Changed helper. BeforeRun makes GitHub setup source easier to inspect.
Explore the mocked fixture demo. #OpenClaw #DeveloperTools #GitHub

## Facts sheet

| Script fact | Source and scope |
|---|---|
| Public GitHub source review, selected command, pinned revision, no submitted-source execution | [README](../README.md) describes the implemented offline-tested prototype and release limits. |
| The hook stays unchanged while the helper changes | The [baseline package](../tests/fixtures/compare/node-version-check/baseline/package.json) and [target package](../tests/fixtures/compare/node-version-check/target/package.json) both use `prepare: node scripts/check-node.js`. This is a fixture example. |
| Node twenty to twenty-two is benign compatibility | [Compare fixture annotation](../tests/fixtures/compare/node-version-check/annotation.json) and [demo notes](demo/README.md). It is not a malware discovery. |
| Simulated finding, quoted source, line display, partial coverage | [Saved job fixture](../tests/fixtures/jobs/checked_result.json) and [reviewed storyboard](demo/index.html). These are mocked payloads and captured UI, not live model evidence. |
| Configured OpenClaw route, Cerebras primary, Baseten Muse Spark Open fallback | [Baseten setup record](BASETEN_GATEWAY_SETUP.md). The user-approved model is `meta-models/muse-spark-open-1026`; schema validation passed, actual upstream use remains unverified. |
| Live model proof pending | [Release gates](RELEASE_GATES.md) and [live proof record](LIVE_PROOF_TEMPLATE.md). No inference success, malware accuracy, free allowance or real latency is claimed. |
| Sixty-second target | User's requested duration; pacing includes visual holds and needs a final rehearsal. |

## Draft and review notes

Five opening candidates were evaluated for clarity, curiosity and factual support:
the unchanged-command helper reveal; a GitHub setup question; a warning/source question;
a new-commit comparison; and a partial-coverage question. The helper reveal was selected
because the middle of the demo closes that exact loop with a visible benign change.

Three full angles were drafted: command-to-review, helper comparison, and evidence trust.
Each passed the writing checker at 90/100 with zero hard failures. The final revision
adds clear stage reveals and retains one action at the end. Its 95/100 heuristic score
reflects writing checks, not a prediction of views or retention. The remaining soft flag
is the custom product CTA rather than the checker's preferred “follow/comment/link” wording.

The spoken script makes no invented incident, live detection, working failover, speed,
accuracy or whole-repository safety claim. New visual information appears at intervals
under eight seconds. Production admission remains disabled; only the saved demo is shown.
