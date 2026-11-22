// Trusted UI test driver. Every application API request is intercepted locally.
const browserChecks = [];
const browserRequests = [];
let browserMode = "normal";
let browserPosts = 0;
let browserReleaseOld = null;
let browserBlockOld = false;
let browserOldId = null;
const browserJobs = new Map();
const browserTick = () => new Promise((resolve) => setTimeout(resolve, 0));
const browserAssert = (condition, message) => { if (!condition) throw new Error(message); };
const browserResponse = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });

window.fetch = async (url, options = {}) => {
  const parsed = new URL(url, location.href);
  browserAssert(parsed.pathname.startsWith("/api/"), "UI attempted a non-API fetch");
  browserRequests.push({ path: parsed.pathname, method: options.method || "GET" });
  if (parsed.pathname === "/api/capabilities") return browserResponse({
    review_enabled: true,
    gateway_model_policy: { automatic_fallback_configured: true, actual_upstream_verified: false },
  });
  if (parsed.pathname === "/api/reviews" && options.method === "POST") {
    browserPosts += 1;
    if (browserMode === "reject") return browserResponse({ detail: {
      code: "INVALID_INPUT", message: "Correct the public repository URL.",
      fields: [{ location: ["repository_url"], message: "Use a public GitHub root." }],
    } }, 422);
    const id = `review_browser_${browserPosts}`;
    const job = structuredClone(browserFixture);
    job.review_id = id;
    job.report.review_id = id;
    job.report.target.canonical_name = browserBlockOld ? "old-fixture" : "current-fixture";
    job.state = "terminal";
    job.pipeline_mode = "mock";
    job.model_processing = "Fixture configured fallback: Muse Spark Open on Baseten; actual upstream is unverified.";
    job.errors = [];
    browserJobs.set(id, job);
    if (browserBlockOld) browserOldId = id;
    return browserResponse({ review_id: id, state: "queued", phase: "accepted" });
  }
  const parts = parsed.pathname.split("/");
  const id = parts[3];
  if (parts[4] === "cancel") return browserResponse({ cancel_requested: true });
  if (parts[4] === "events") {
    const after = Number(parsed.searchParams.get("after"));
    const count = Math.min(100, 150 - after);
    const events = Array.from({ length: Math.max(0, count) }, (_, index) => ({
      sequence: after + index + 1, event_type: "file_fetched", timestamp: "fixture time",
      message: after + index + 1 === 150 ? "Final fixture event 150" : "Actual fixture event",
    }));
    return browserResponse({ events, next_cursor: after + events.length, truncated: false, terminal: true });
  }
  if (parts[4] === "evidence") {
    return browserResponse(browserFixture.evidence.find((item) => item.evidence.evidence_id === parts[5]));
  }
  if (parts[4] === "export") return browserResponse(browserJobs.get(id));
  if (browserBlockOld && id === browserOldId) {
    await new Promise((resolve) => { browserReleaseOld = resolve; });
  }
  return browserResponse(browserJobs.get(id));
};

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const form = document.getElementById("review-form");
    const submit = document.getElementById("review-submit");
    const output = document.getElementById("review-output");
    const announce = document.getElementById("review-announcement");
    const waitFor = async (predicate, message) => {
      for (let index = 0; index < 200; index += 1) {
        if (predicate()) return;
        await browserTick();
      }
      throw new Error(message);
    };
    const submitForm = () => {
      form.elements.namedItem("repository_url").value = "https://github.com/example/inert-fixture";
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    };
    const newReview = () => [...output.querySelectorAll("button")].find((item) => item.textContent === "New review").click();
    await waitFor(() => !submit.disabled, "capabilities did not enable the fixture form");
    const policyNote = document.getElementById("model-policy-note");
    browserAssert(!policyNote.hidden && policyNote.textContent.includes("Baseten"), "fallback processing was not disclosed before submit");
    submitForm();
    submitForm();
    await waitFor(() => announce.textContent.includes("Review terminal"), "fixture report did not render");
    browserAssert(browserPosts === 1, "double submission admitted two jobs");
    browserAssert(output.textContent.includes("Mocked fixture review"), "fixture mode is not labeled");
    browserAssert(output.textContent.includes("Final fixture event 150"), "terminal event pages were lost");
    browserAssert(output.textContent.includes("<script>"), "hostile excerpt was not rendered as text");
    browserAssert(!output.querySelector("script") && !output.querySelector("img"), "untrusted text created active markup");
    browserAssert(output.textContent.includes("partial"), "completion is not separate and visible");
    browserAssert(output.textContent.includes("actual upstream is unverified"), "report did not retain configured-policy limitations");
    browserAssert([...output.querySelectorAll("a[target=_blank]")].every((item) => item.rel.includes("noopener")), "source links lack tab isolation");
    browserChecks.push("submit/double-submit/inert-source/mock-label/events/partial/evidence");

    newReview();
    browserMode = "reject";
    submitForm();
    await waitFor(() => form.querySelector("[aria-invalid=true]"), "field error was not associated with its input");
    browserAssert(document.activeElement.id === "repo-url", "field correction did not receive keyboard focus");
    browserAssert(!output.textContent.includes("current-fixture"), "old report survived input rejection");
    browserChecks.push("field-error/focus/old-report-clearing");

    newReview();
    browserMode = "normal";
    browserBlockOld = true;
    submitForm();
    await waitFor(() => browserReleaseOld, "old request was not held");
    newReview();
    browserBlockOld = false;
    submitForm();
    await waitFor(() => output.textContent.includes("current-fixture"), "new report did not render");
    browserReleaseOld();
    await browserTick();
    await browserTick();
    browserAssert(!output.textContent.includes("old-fixture"), "stale response replaced the current report");
    browserAssert(browserRequests.some((item) => item.path === `/api/reviews/${browserOldId}/cancel`), "clearing did not cancel the old job");
    browserAssert(!form.querySelector("[aria-invalid=true]"), "old field errors survived reset");
    browserAssert(document.documentElement.scrollWidth <= window.innerWidth + 1, "mobile page overflows the viewport");
    browserChecks.push("stale-response/reset/cancel/mobile-wrapping");
    document.body.dataset.browserTest = "passed";
  } catch (error) {
    document.body.dataset.browserTest = "failed";
    browserChecks.push(String(error.stack || error));
  }
  const result = document.createElement("pre");
  result.id = "browser-test-results";
  result.textContent = JSON.stringify({ checks: browserChecks, requests: browserRequests });
  document.body.append(result);
});
