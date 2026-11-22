// Real review jobs only. No demo result is substituted after an unavailable/failed review.
(() => {
  const form = document.getElementById("review-form");
  const output = document.getElementById("review-output");
  const submit = document.getElementById("review-submit");
  const announcement = document.getElementById("review-announcement");
  const formNote = document.getElementById("form-note");
  const modelPolicyNote = document.getElementById("model-policy-note");
  if (!form || !output || !submit || !announcement) return;

  let generation = 0;
  let reviewEnabled = false;
  let submissionPending = false;
  submit.disabled = true;
  let activeJob = null;
  let abortController = null;
  let eventCursor = 0;
  let activity = [];
  const evidenceCache = new Map();

  function element(tag, className, text) {
    const value = document.createElement(tag);
    if (className) value.className = className;
    if (text !== undefined && text !== null) value.textContent = String(text);
    return value;
  }

  function heading(level, text, className) {
    return element(`h${level}`, className, text);
  }

  function action(label, handler, primary = false) {
    const value = element("button", `button${primary ? " button-primary" : ""}`, label);
    value.type = "button";
    value.addEventListener("click", handler);
    return value;
  }

  function sourceLink(url, label = "Open pinned source") {
    try {
      const parsed = new URL(url);
      if (
        parsed.protocol !== "https:" ||
        parsed.hostname !== "github.com" ||
        parsed.port || parsed.search ||
        parsed.username ||
        parsed.password ||
        !(parsed.pathname.includes("/blob/") || parsed.pathname.includes("/commit/"))
      ) return null;
      const value = element("a", "text-link", label);
      value.href = parsed.href;
      value.target = "_blank";
      value.rel = "noopener noreferrer";
      return value;
    } catch {
      return null;
    }
  }

  function announce(message) {
    announcement.textContent = message;
  }

  async function api(url, options = {}, signal) {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      signal,
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = body.detail || {};
      const error = new Error(detail.message || `Review request failed (${response.status}).`);
      error.code = detail.code || "REQUEST_FAILED";
      error.fields = detail.fields || [];
      throw error;
    }
    return body;
  }

  function resetState(clearForm = true) {
    const previousJob = activeJob;
    generation += 1;
    abortController?.abort();
    abortController = null;
    activeJob = null;
    eventCursor = 0;
    activity = [];
    submissionPending = false;
    for (const control of form.elements) {
      control.removeAttribute("aria-invalid");
      if (control.getAttribute("aria-describedby") === `${control.id}-error`) control.removeAttribute("aria-describedby");
    }
    for (const error of form.querySelectorAll(".field-error")) error.remove();
    evidenceCache.clear();
    submit.disabled = !reviewEnabled;
    if (clearForm) form.reset();
    if (previousJob) {
      // Clearing the UI must also stop the server-side job, not just local polling.
      void api(`/api/reviews/${previousJob}/cancel`, {
        method: "POST",
        headers: { "X-BeforeRun-Request": "1" },
      }).catch(() => {});
    }
  }

  function showIdle() {
    const hadJob = Boolean(activeJob);
    resetState(true);
    const headingRow = element("div", "panel-heading");
    const copy = element("div");
    copy.append(
      heading(2, "Your review will appear here", ""),
      element("p", "", "No repository has been fetched or investigated."),
    );
    headingRow.append(copy);
    output.className = "panel empty-review";
    output.replaceChildren(headingRow);
    announce(hadJob ? "Review cleared. Cancellation was requested for the prior job; upstream cancellation is unconfirmed." : "Review cleared. No review is active.");
  }

  function fieldErrors(fields) {
    let first = null;
    const allowed = new Set(["repository_url", "target_ref", "baseline_ref", "command_context"]);
    for (const field of fields || []) {
      const name = field.location?.[0];
      if (!allowed.has(name)) continue;
      const control = form.elements.namedItem(name);
      if (!control) continue;
      if (control.hasAttribute("aria-invalid")) continue;
      const error = element("p", "helper field-error", field.message);
      error.id = `${control.id}-error`;
      control.setAttribute("aria-invalid", "true");
      control.setAttribute("aria-describedby", error.id);
      control.parentElement.append(error);
      first ||= control;
    }
    first?.focus();
  }

  function actions(jobId, allowRetry = false) {
    const row = element("div", "report-bottom");
    const left = element("div", "report-actions");
    left.append(action("New review", showIdle));
    if (allowRetry) {
      left.append(action("Retry as a new review", () => form.requestSubmit(), true));
    }
    if (jobId) {
      const cancel = action("Cancel review", async () => {
        cancel.disabled = true;
        try {
          await api(`/api/reviews/${jobId}/cancel`, {
            method: "POST",
            headers: { "X-BeforeRun-Request": "1" },
          }, abortController?.signal);
          announce("Cancellation requested. Upstream cancellation is unconfirmed.");
        } catch (error) {
          if (error.name !== "AbortError") announce(error.message);
          cancel.disabled = false;
        }
      });
      left.append(cancel);
    }
    row.append(left);
    return row;
  }

  function activityList() {
    const details = element("details", "panel activity-card");
    const summary = element("summary", "", "Actual review activity");
    const list = element("ol", "activity-list");
    for (const event of activity.slice(-100)) {
      const item = element("li");
      const content = element("div");
      content.append(
        element("p", "", event.message),
        element("small", "", `${event.event_type} · event ${event.sequence} · ${event.timestamp}`),
      );
      item.append(content);
      list.append(item);
    }
    if (!activity.length) list.append(element("li", "", "No activity events have arrived yet."));
    details.append(summary, list);
    return details;
  }

  function renderProgress(status) {
    const wrapper = element("div", "review-live");
    const panel = element("section", "panel decision-card");
    panel.append(
      element("div", "decision-label", status.state === "queued" ? "Queued" : "Review running"),
      heading(2, status.state === "queued" ? "Waiting for a bounded worker" : "Review in progress", "decision-title"),
      element("p", "", `Actual phase: ${status.phase}. No percentage or model activity is invented.`),
      element("p", "decision-note", "Selected source is read as data. You can cancel; upstream inference cancellation is unconfirmed."),
    );
    wrapper.append(panel, activityList(), actions(status.review_id));
    output.className = "review-output";
    output.replaceChildren(wrapper);
  }

  function renderFailure(status) {
    const wrapper = element("div", "review-live");
    const panel = element("section", "panel decision-card error");
    const cancelled = status.cancel_requested || status.stop_reason === "cancelled";
    panel.append(
      element("div", "decision-label", cancelled ? "Cancelled" : "Review did not produce a checked report"),
      heading(2, cancelled ? "Analysis was interrupted" : "Not enough evidence to assess", "decision-title"),
      element("p", "", cancelled
        ? "Local work stopped. This is not evidence that the repository is benign."
        : "No model or static fallback verdict was manufactured. Retry creates a new bounded review."),
    );
    const errors = element("ul", "issue-list");
    for (const error of status.errors || []) {
      const item = element("li");
      const text = element("div");
      text.append(element("strong", "", error.code), element("span", "", error.message));
      item.append(text);
      errors.append(item);
    }
    if (!status.errors?.length) errors.append(element("li", "", "No checked report is available."));
    panel.append(errors);
    wrapper.append(panel, activityList(), actions(null, true));
    output.className = "review-output";
    output.replaceChildren(wrapper);
    announce(cancelled ? "Review cancelled." : "Review failed without a checked report.");
  }

  function assessmentCopy(report) {
    const assessment = report.assessment;
    const title = {
      malicious: "Harmful behavior found in inspected source.",
      suspicious: "Concerning behavior needs review.",
      benign: "No concerning behavior found in reviewed scope.",
      undetermined: "Not enough evidence to assess.",
    }[assessment] || "Not enough evidence to assess.";
    return {
      title,
      tone: assessment === "malicious" || assessment === "undetermined"
        ? "error"
        : assessment === "suspicious" || report.completion !== "complete"
          ? "warning"
          : "",
    };
  }

  function completionCopy(completion) {
    return {
      complete: "Complete within the declared bounded root-source scope — not a complete repository audit.",
      partial: "Partial: required source or validation work remains unresolved.",
      failed: "Failed: no successful checked assessment was completed.",
      unsupported: "Unsupported: the selected action is outside the implemented scope.",
      cancelled: "Cancelled before analysis finished.",
    }[completion] || "Completion is unknown.";
  }

  function repositoryHeader(report, jobId) {
    const panel = element("section", "panel report-meta-panel");
    const meta = element("div", "report-meta");
    const left = element("div");
    const repository = element("div", "repo-heading", `${report.target.canonical_owner}/${report.target.canonical_name}`);
    const revisions = element("div", "revision-line");
    const target = sourceLink(
      `https://github.com/${encodeURIComponent(report.target.canonical_owner)}/${encodeURIComponent(report.target.canonical_name)}/commit/${report.target.commit_sha}`,
      `Target ${report.target.commit_sha}`,
    );
    if (target) revisions.append(target);
    else revisions.append(element("code", "", report.target.commit_sha));
    if (report.baseline) revisions.append(element("span", "", `Baseline ${report.baseline.commit_sha}`));
    revisions.append(element("span", "", `Context ${report.review_input.command_context}`));
    revisions.append(element("span", "", `Report v${report.report_version}`));
    left.append(repository, revisions);
    meta.append(left);
    const download = element("a", "button", "Download redacted JSON");
    download.href = `/api/reviews/${jobId}/export?format=json`;
    download.download = `beforerun-${jobId}.json`;
    const copy = action("Copy redacted JSON", async () => {
      const ticket = generation;
      try {
        const exported = await api(download.href, {}, abortController?.signal);
        if (ticket !== generation || activeJob !== jobId) return;
        if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable; use Download redacted JSON.");
        await navigator.clipboard.writeText(JSON.stringify(exported, null, 2));
        announce("Redacted report JSON copied. Review it before sharing.");
      } catch (error) {
        if (error.name !== "AbortError" && ticket === generation) announce(error.message);
      }
    });
    const exportActions = element("div", "report-actions");
    exportActions.append(copy, download);
    panel.append(meta, exportActions);
    return panel;
  }

  function decision(report) {
    const copy = assessmentCopy(report);
    const panel = element("section", `panel decision-card ${copy.tone}`.trim());
    panel.append(
      element("div", "decision-label", `Assessment: ${report.assessment}`),
      heading(2, copy.title, "decision-title"),
      element("p", "", completionCopy(report.completion)),
      element("p", "decision-note", "Evidence references, execution support, coverage, and missing surfaces are separate checks. This is not a safety guarantee or incident-response tool."),
    );
    if (report.assessment === "malicious") {
      panel.append(element("p", "callout callout-warning", "Avoid executing this revision and seek a qualified source/security review. BeforeRun cannot clean an already affected computer."));
    }
    return panel;
  }

  function evidenceDetails(view) {
    const details = element("details", "panel evidence-card");
    const evidence = view.evidence;
    const derived = Boolean(evidence.parent_evidence_id)
      || ["decoded", "string", "diff"].includes(evidence.kind);
    const summary = element("summary", "", `${view.path} · ${evidence.side} · ${derived ? "parent lines" : "lines"} ${evidence.span.first_line}–${evidence.span.last_line}`);
    const caption = element("p", "evidence-caption", derived
      ? `Derived ${evidence.kind} representation from parent ${evidence.parent_evidence_id}; rows are not literal source lines. Parent columns ${evidence.span.first_column}–${evidence.span.last_column}; representation SHA-256 ${evidence.representation_sha256}`
      : `Original columns ${evidence.span.first_column}–${evidence.span.last_column}; ${evidence.kind}; representation SHA-256 ${evidence.representation_sha256}`);
    const pre = element("pre", "actual-source");
    const lines = evidence.representation.split("\n");
    lines.forEach((line, index) => {
      const row = element("div", "actual-source-line");
      row.append(
        element("span", "actual-line-number", derived ? "·" : evidence.span.first_line + index),
        element("code", "actual-line-text", line || " "),
      );
      pre.append(row);
    });
    details.append(summary, caption, pre);
    const link = sourceLink(view.source_url);
    if (link) details.append(link);
    return details;
  }

  function findingCard(validated, evidenceMap) {
    const finding = validated.finding;
    const card = element("article", "panel finding-card");
    const summary = element("div", "finding-summary");
    summary.append(
      element("div", "finding-topline", `${finding.priority} priority · ${finding.behavior_category} · change: ${finding.change_status}`),
      heading(3, finding.title, ""),
      element("p", "", validated.display_summary),
    );
    const facts = element("dl", "finding-facts");
    const entries = [
      ["Potential impact", finding.impact],
      ["Trigger / assumptions", finding.trigger_context],
      ["Priority reason", finding.priority_reason],
      ["Benign explanation considered", finding.benign_explanation_considered || "None supplied; retain uncertainty."],
      ["Unknowns", finding.unknowns.join(" | ") || "See coverage gaps."],
      ["Execution support", validated.validation.execution_context_support],
      ["Change claim support", validated.validation.change_claim_support],
    ];
    for (const [term, description] of entries) {
      facts.append(element("dt", "", term), element("dd", "", description));
    }
    summary.append(facts);
    card.append(summary);
    for (const id of finding.evidence_ids) {
      const view = evidenceMap.get(id);
      card.append(view ? evidenceDetails(view) : element("p", "callout callout-warning", `Evidence ${id} is unavailable; do not treat its reference as displayed checked source.`));
    }
    return card;
  }

  function coveragePanel(report) {
    const coverage = report.coverage;
    const panel = element("aside", "panel coverage-card");
    panel.append(heading(2, "Coverage and exclusions"));
    const counts = element("dl", "coverage-numbers");
    for (const [label, value] of [
      ["Inventory entries", coverage.listed_files],
      ["Selected", coverage.selected_files],
      ["Fetched", coverage.fetched_files],
      ["Actually shown to model", coverage.model_shown_files],
      ["Skipped", coverage.skipped_files],
    ]) counts.append(element("dt", "", label), element("dd", "", value));
    panel.append(counts);
    panel.append(element("p", "", coverage.inventory_complete
      ? "Inventory complete within admitted tree bounds only."
      : "Inventory or required evidence is incomplete; this is not whole-repository coverage."));
    const gaps = element("ul", "coverage-list");
    for (const id of coverage.required_unresolved_files) gaps.append(element("li", "unknown", `Required unresolved file ID: ${id}`));
    for (const surface of coverage.excluded_surfaces) gaps.append(element("li", "", `Excluded surface: ${surface}`));
    for (const error of coverage.errors) gaps.append(element("li", "unknown", `${error.code}: ${error.message}`));
    panel.append(gaps);
    const budget = coverage.budget;
    panel.append(element("p", "coverage-footnote", `Budget observed: ${budget.github_attempts} GitHub attempts, ${budget.model_attempts} model attempts, ${budget.tool_operations} tool operations, ${budget.source_bytes} source bytes. Costs are unknown unless the operator verifies provider billing.`));
    return panel;
  }

  function comparisonPanel(comparison, evidenceMap) {
    if (!comparison?.requested) return null;
    const section = element("section", "panel comparison-panel");
    section.append(heading(2, "Pinned commit comparison"));
    if (comparison.error) section.append(element("p", "callout callout-warning", comparison.error));
    if (!comparison.complete) section.append(element("p", "callout callout-warning", "Comparison evidence or inventory is incomplete. Change novelty may remain unknown."));
    const list = element("div", "comparison-list");
    const changed = comparison.entries.filter((entry) => entry.change !== "unchanged" ||
      entry.target_evidence_ids.length || entry.baseline_evidence_ids.length);
    if (!changed.length) list.append(element("p", "", "No tree/object changes found within the admitted inventories."));
    for (const entry of changed.slice(0, 100)) {
      const card = element("article", "comparison-entry");
      card.append(heading(3, `${entry.path} · ${entry.change}`));
      if (entry.mode_changed) card.append(element("p", "", "The file mode also changed."));
      for (const gap of entry.evidence_gaps || []) card.append(element("p", "unknown", gap));
      if (entry.diff) card.append(element("pre", "diff-view", entry.diff));
      const links = element("div", "report-actions");
      for (const [side, ids] of [["target", entry.target_evidence_ids], ["baseline", entry.baseline_evidence_ids]]) {
        for (const id of ids) {
          const view = evidenceMap.get(id);
          if (view) {
            const link = sourceLink(view.source_url, `${side} line ${view.evidence.span.first_line}`);
            if (link) links.append(link);
          }
        }
      }
      card.append(links);
      list.append(card);
    }
    if (changed.length > 100) list.append(element("p", "", `${changed.length - 100} additional entries bounded from this display; use export.`));
    section.append(list);
    return section;
  }

  function reportDetails(report, modelProcessing) {
    const details = element("details", "panel activity-card");
    details.append(element("summary", "", "Assumptions, provenance, and processing"));
    const body = element("div", "report-provenance");
    if (modelProcessing) body.append(element("p", "", modelProcessing));
    for (const assumption of report.assumptions) body.append(element("p", "", assumption));
    body.append(
      element("p", "", `Configured model route: ${report.model_route}`),
      element("p", "", `Prompt ${report.prompt_version}; tools ${report.tool_policy_version}; analyzer ${report.analyzer_version}; created ${report.created_at}.`),
      element("p", "", "App expiry does not erase Gateway/provider transcripts or copies you export."),
    );
    details.append(body, activityList());
    return details;
  }

  async function renderTerminal(status, ticket) {
    const report = status.report;
    if (!report) {
      renderFailure(status);
      return;
    }
    const evidenceIds = new Set();
    for (const finding of report.findings) {
      for (const id of finding.finding.evidence_ids) evidenceIds.add(id);
    }
    for (const entry of status.comparison?.entries || []) {
      for (const id of [...entry.target_evidence_ids, ...entry.baseline_evidence_ids]) evidenceIds.add(id);
    }
    const evidenceMap = new Map();
    for (const id of [...evidenceIds].slice(0, 500)) {
      try {
        const view = await api(`/api/reviews/${status.review_id}/evidence/${id}`, {}, abortController?.signal);
        evidenceMap.set(id, view);
      } catch (error) {
        if (error.name === "AbortError") return;
        // Missing evidence remains visible; no source is fabricated to fill it.
      }
      if (ticket !== generation || activeJob !== status.review_id) return;
    }

    const wrapper = element("div", "review-live");
    if (status.pipeline_mode === "mock") wrapper.append(element("p", "callout callout-warning",
      "Mocked fixture review. No live GitHub or model request was made."));
    wrapper.append(repositoryHeader(report, status.review_id), decision(report));
    const findings = element("section", "findings-section");
    findings.append(heading(2, report.findings.length ? "Checked findings" : "No checked findings in the reviewed scope"));
    if (!report.findings.length) {
      findings.append(element("p", "callout", report.completion === "complete" && report.assessment === "benign"
        ? "No concerning behavior was supported in the declared bounded scope. Exclusions still apply."
        : "An empty result without complete checked scope is not a benign assessment."));
    }
    for (const finding of report.findings) findings.append(findingCard(finding, evidenceMap));
    const comparison = comparisonPanel(status.comparison, evidenceMap);
    if (comparison) wrapper.append(comparison);
    wrapper.append(findings, coveragePanel(report), reportDetails(report, status.model_processing), actions(null));
    if (ticket !== generation || activeJob !== status.review_id) return;
    output.className = "review-output";
    output.replaceChildren(wrapper);
    announce(`Review terminal. Assessment ${report.assessment}. Completion ${report.completion}.`);
  }

  async function poll(jobId, ticket) {
    try {
      while (ticket === generation && activeJob === jobId) {
        const status = await api(`/api/reviews/${jobId}`, {}, abortController?.signal);
        if (ticket !== generation || activeJob !== jobId) return;
        for (let pages = 0; pages < 6; pages += 1) {
          const previousCursor = eventCursor;
          const page = await api(`/api/reviews/${jobId}/events?after=${eventCursor}&limit=100`, {}, abortController?.signal);
          if (ticket !== generation || activeJob !== jobId) return;
          activity.push(...page.events);
          eventCursor = page.next_cursor;
          if (page.truncated) activity.push({ message: "Older progress events were pruned by the bounded event store.", sequence: eventCursor, event_type: "cursor_notice", timestamp: new Date().toISOString() });
          activity = activity.slice(-500);
          if (status.state !== "terminal" || page.events.length < 100 || eventCursor <= previousCursor) break;
        }
        if (status.state === "terminal") {
          await renderTerminal(status, ticket);
          return;
        }
        renderProgress(status);
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    } catch (error) {
      if (error.name === "AbortError" || ticket !== generation) return;
      renderFailure({ errors: [{ code: error.code, message: error.message }], cancel_requested: false });
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submissionPending) return;
    if (!reviewEnabled) {
      renderFailure({ errors: [{ code: "REVIEW_DISABLED", message: "Review submission is disabled until the checked pipeline and release gates are enabled." }], cancel_requested: false });
      return;
    }
    resetState(false);
    submissionPending = true;
    const ticket = generation;
    output.className = "review-output";
    output.replaceChildren();
    submit.disabled = true;
    const data = new FormData(form);
    const intake = {
      repository_url: String(data.get("repository_url") || ""),
      target_ref: String(data.get("target_ref") || "") || null,
      baseline_ref: String(data.get("baseline_ref") || "") || null,
      command_context: String(data.get("command_context") || "review_only"),
      project_directory: ".",
    };
    const key = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    abortController = new AbortController();
    try {
      const status = await api("/api/reviews", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-BeforeRun-Request": "1",
          "Idempotency-Key": key,
        },
        body: JSON.stringify(intake),
      }, abortController.signal);
      if (ticket !== generation) return;
      activeJob = status.review_id;
      renderProgress(status);
      announce(`Review ${status.review_id} accepted.`);
      await poll(status.review_id, ticket);
    } catch (error) {
      if (error.name === "AbortError" || ticket !== generation) return;
      activeJob = null;
      fieldErrors(error.fields);
      renderFailure({ errors: [{ code: error.code, message: error.message }], cancel_requested: false });
    } finally {
      if (ticket === generation) {
        submissionPending = false;
        submit.disabled = !reviewEnabled;
      }
    }
  });

  async function initializeCapabilities() {
    try {
      const capabilities = await api("/api/capabilities");
      reviewEnabled = capabilities.review_enabled === true;
      if (modelPolicyNote && capabilities.gateway_model_policy?.automatic_fallback_configured === true) {
        modelPolicyNote.hidden = false;
        modelPolicyNote.textContent = "Model processing: Cerebras is primary. Muse Spark Open on Baseten may receive the same selected source when an eligible provider failure triggers fallback. The reviewer alias alone does not verify which upstream answered.";
      }
      submit.disabled = !reviewEnabled;
      if (!reviewEnabled && formNote) {
        formNote.textContent = "Source is never executed. Reviews are unavailable until the required service and validation checks are enabled.";
      }
    } catch {
      reviewEnabled = false;
      submit.disabled = true;
      if (formNote) formNote.textContent = "Review capabilities are unavailable. No review request has been submitted.";
    }
  }

  void initializeCapabilities();
})();
