"""Capture the real UI over a saved fixture with no network or model requests.

Uses installed Chrome and a fresh temporary profile. The output is an explicitly labeled
offline storyboard, not a live review, checked-citation proof, or malware evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STATIC = ROOT / "src/beforerun/static"
FIXTURE = ROOT / "tests/fixtures/jobs/checked_result.json"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
FRAMES = [
    ("01-input.png", "Choose pinned revisions", "input"),
    ("02-report.png", "Partial fixture report and compatibility comparison", "report"),
    ("03-evidence.png", "Open an inert source excerpt", "evidence"),
    ("04-coverage.png", "Read exclusions and processing limits", "coverage"),
]

BOOTSTRAP = r"""
const demoCalls = [];
const demoJob = structuredClone(demoFixture);
demoJob.review_id = demoFixture.report.review_id;
demoJob.state = "terminal";
demoJob.phase = "finished";
demoJob.pipeline_mode = "mock";
demoJob.errors = [];
window.fetch = async (url, options = {}) => {
  const path = new URL(url, location.href).pathname;
  if (!path.startsWith("/api/")) throw new Error("Non-API fetch blocked in offline demo");
  demoCalls.push({ path, method: options.method || "GET" });
  const reply = (body) => ({ ok: true, status: 200, json: async () => body });
  if (path === "/api/capabilities") return reply({ review_enabled: true });
  if (path === "/api/reviews" && options.method === "POST") {
    return reply({ review_id: demoJob.review_id, state: "queued", phase: "accepted" });
  }
  if (path.endsWith("/events")) return reply({
    events: [{ sequence: 1, event_type: "fixture_replay", timestamp: "fixture time",
      message: "Saved fixture replay only; no GitHub, Gateway or provider request." }],
    next_cursor: 1, terminal: true, truncated: false,
  });
  if (path.includes("/evidence/")) {
    const id = path.split("/").at(-1);
    return reply(demoFixture.evidence.find((item) => item.evidence.evidence_id === id));
  }
  if (path.endsWith("/cancel")) return reply({ cancel_requested: true });
  return reply(demoJob);
};
document.addEventListener("DOMContentLoaded", async () => {
  try {
    const banner = document.createElement("aside");
    banner.className = "offline-demo-banner";
    const title = document.createElement("strong");
    title.textContent = "MOCKED FIXTURE — no live model";
    const note = document.createElement("span");
    note.textContent = "No live retrieval or inference. IDs, checks and timings are synthetic. "
      + "G2–G4 remain unverified.";
    banner.append(title, note);
    document.body.prepend(banner);
    document.querySelector(".design-notice").textContent =
      "Offline replay of the app UI. Every API response comes from the saved fixture; "
      + "no repository or provider is contacted.";
    const waitFor = async (predicate) => {
      for (let index = 0; index < 300; index += 1) {
        if (predicate()) return;
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
      throw new Error("Offline demo state did not render");
    };
    const form = document.getElementById("review-form");
    await waitFor(() => !document.getElementById("review-submit").disabled);
    form.elements.namedItem("repository_url").value =
      demoFixture.report.review_input.repository_url;
    form.elements.namedItem("target_ref").value = "target-fixture";
    form.elements.namedItem("baseline_ref").value = "baseline-fixture";
    form.elements.namedItem("command_context").value = "npm_install";
    if (demoStage !== "input") {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      await waitFor(() => document.getElementById("review-announcement")
        .textContent.includes("Review terminal"));
      const output = document.getElementById("review-output");
      if (!output.textContent.includes("Mocked fixture review") || window.__fixtureXss) {
        throw new Error("Fixture labeling or inert text check failed");
      }
      document.body.classList.add("demo-stage-" + demoStage);
      if (demoStage === "evidence") {
        output.querySelector(".evidence-card").open = true;
      } else if (demoStage === "coverage") {
        output.querySelectorAll("details").forEach((item) => { item.open = true; });
      }
    }
    window.scrollTo(0, 0);
    document.body.dataset.offlineDemo = "ready-" + demoStage;
    const receipt = document.createElement("script");
    receipt.type = "application/json";
    receipt.id = "offline-demo-receipt";
    receipt.textContent = JSON.stringify({
      mode: "mock", stage: demoStage, calls: demoCalls, live_requests: 0,
    });
    document.body.append(receipt);
  } catch (error) {
    document.body.dataset.offlineDemo = "failed";
  }
});
"""

OVERLAY_STYLE = """
html { scroll-behavior: auto !important; }
.offline-demo-banner { position: fixed; inset: 0 0 auto; z-index: 10000;
  min-height: 72px; padding: 13px 24px; color: #25392e; background: #fff2da;
  border-bottom: 2px solid #8b5b23; font: 16px/1.4 system-ui, sans-serif; }
.offline-demo-banner strong { display: block; font-size: 19px; }
.offline-demo-banner span { display: block; font-size: 12px; margin-top: 3px; }
body { padding-top: 76px; }
.sidebar { top: 76px; }
.topbar { top: 76px; }
body[class*="demo-stage-"] .content > :not(#review-output):not(#review-announcement) {
  display: none;
}
.demo-stage-evidence .review-live > :not(.findings-section) { display: none; }
.demo-stage-coverage .review-live > :not(.coverage-card):not(.activity-card) { display: none; }
"""

STORYBOARD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' file:;
style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; base-uri 'none';
form-action 'none'">
<title>BeforeRun — offline fixture storyboard</title>
<style>
body{margin:0;background:#f4f4ee;color:#25392e;font:16px/1.5 system-ui,sans-serif}
header,main,footer{max-width:1100px;margin:auto;padding:24px}
header{border-bottom:2px solid #8b5b23;background:#fff2da}
h1{font-size:24px;margin:0 0 8px}p{margin:8px 0}
.controls{display:flex;flex-wrap:wrap;gap:10px;margin:20px 0}
button{font:inherit;border:1px solid #637366;border-radius:6px;padding:8px 16px;
background:#fffef9;color:#25392e;cursor:pointer}
button:focus-visible{outline:3px solid #21553b;outline-offset:2px}
figure{margin:0}img{width:100%;height:auto;display:block;border:1px solid #dce3d6}
figcaption{padding:12px 0}footer{font-size:14px;border-top:1px solid #dce3d6}
</style></head><body>
<header><h1>MOCKED FIXTURE — no live model</h1>
<p>BeforeRun's real interface, replayed with a saved checked-report fixture and mocked APIs.</p>
<p>No GitHub retrieval, OpenClaw/Cerebras inference, submitted-source execution,
or malware evaluation occurred.</p></header>
<main><div class="controls"><button id="previous">Previous</button>
<button id="play" aria-pressed="false">Play storyboard</button>
<button id="next">Next</button></div>
<figure><img id="frame" src="01-input.png" alt="Fixture form with target and baseline revisions">
<figcaption id="caption" aria-live="polite"></figcaption></figure></main>
<footer><p>The example repository, hashes, evidence IDs, validation flags,
and 12 ms duration are synthetic fixture data. They are not live checked-citation
or performance evidence.</p>
<p>The Node 20 → 22 comparison is an inert compatibility example. The concern is a simulation;
partial coverage, unread helpers, dependencies, downloads and native binaries stay visible.</p>
<p>The retained live smoke attempts failed. Effective Gateway isolation, successful Kimi/Cerebras
delivery, checked citations and real latency/tokens/cost remain unresolved.
This recording does not enable reviews or publication.</p></footer>
<script>
const slides = [
 ["01-input.png", "1 / 4 — Select synthetic target and baseline revisions. "
   + "Mock capabilities enable only this isolated replay."],
 ["02-report.png", "2 / 4 — Partial fixture report and Node 20 → 22 comparison. "
   + "Assessment, completion and scope are separate."],
 ["03-evidence.png", "3 / 4 — Open original-line fixture text. HTML-looking source remains inert; "
   + "the finding is explicitly simulated."],
 ["04-coverage.png", "4 / 4 — Read missing required evidence, excluded surfaces "
   + "and processing assumptions. Cost is unknown."]
];
let current = 0, timer = null;
const draw = () => {
 document.getElementById("frame").src = slides[current][0];
 document.getElementById("frame").alt = slides[current][1];
 document.getElementById("caption").textContent = slides[current][1];
};
document.getElementById("previous").onclick = () => {
 current = (current + slides.length - 1) % slides.length; draw();
};
document.getElementById("next").onclick = () => {
 current = (current + 1) % slides.length; draw();
};
document.getElementById("play").onclick = () => {
 const button = document.getElementById("play");
 if (timer) {
  clearInterval(timer); timer = null; button.textContent = "Play storyboard";
  button.setAttribute("aria-pressed", "false");
 } else {
  timer = setInterval(() => { current = (current + 1) % slides.length; draw(); }, 8000);
  button.textContent = "Pause storyboard"; button.setAttribute("aria-pressed", "true");
 }
};
draw();
</script></body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/demo")
    args = parser.parse_args()
    output = args.output.resolve()
    executable = str(CHROME) if CHROME.is_file() else shutil.which("chromium")
    if not executable:
        raise SystemExit("Installed Chrome/Chromium is required; no browser will be installed.")
    expected = [name for name, _, _ in FRAMES] + ["index.html", "manifest.json"]
    if any((output / name).exists() for name in expected):
        raise SystemExit(
            "Refusing to overwrite existing demo artifacts. Choose a new output directory."
        )
    output.mkdir(parents=True, exist_ok=True)
    fixture = FIXTURE.read_text()
    markup = (STATIC / "index.html").read_text()
    markup = markup.replace('"/static/', '"' + STATIC.as_uri() + "/")
    frames = []
    with tempfile.TemporaryDirectory(prefix="beforerun-offline-demo-") as directory:
        temporary = Path(directory)
        for name, title, stage in FRAMES:
            page = temporary / f"{stage}.html"
            bootstrap = (
                "const demoFixture = " + fixture.replace("<", "\\u003c") + ";\n"
                "const demoStage = " + json.dumps(stage) + ";\n" + BOOTSTRAP
            )
            page.write_text(
                markup.replace(
                    "<head>",
                    '<head><meta http-equiv="Content-Security-Policy" '
                    "content=\"connect-src 'none'; object-src 'none'; frame-src 'none'; "
                    "form-action 'none'\"><style>"
                    + OVERLAY_STYLE
                    + "</style><script>"
                    + bootstrap
                    + "</script>",
                    1,
                )
            )
            target = output / name
            result = subprocess.run(
                [
                    executable,
                    "--headless",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                    "--disable-component-update",
                    "--disable-sync",
                    "--disable-extensions",
                    "--disable-default-apps",
                    "--disable-breakpad",
                    "--host-resolver-rules=MAP * ~NOTFOUND",
                    "--window-size=1440,1100",
                    "--virtual-time-budget=6000",
                    "--dump-dom",
                    "--screenshot=" + str(target),
                    "--user-data-dir=" + str(temporary / ("profile-" + stage)),
                    page.as_uri(),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode or f'data-offline-demo="ready-{stage}"' not in result.stdout:
                raise SystemExit(f"Offline {stage} frame did not reach its checked UI state.")
            if not target.is_file():
                raise SystemExit(f"Chrome did not capture the offline {stage} frame.")
            frames.append(
                {
                    "file": name,
                    "title": title,
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                    "render_state_checked": True,
                }
            )
    (output / "index.html").write_text(STORYBOARD)
    manifest = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "producer": "tests/fixtures/demo/record_demo.py",
        "mode": "offline saved-fixture UI replay",
        "live_requests": 0,
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "viewport": {"width": 1440, "height": 1100},
        "capture_framing": "Existing UI panels framed at page top; fixture content unchanged.",
        "frames": frames,
        "visual_review": "pending",
        "live_gate_evidence": False,
        "release_ready": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"mode": manifest["mode"], "frames": len(frames), "live_requests": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
