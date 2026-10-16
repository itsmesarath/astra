/* Offline review state and UI. Browser checks are not a replacement for the Python audit. */
(function () {
  "use strict";
  const checks = ["rationale_supported", "citations_sufficient", "uncertainty_preserved", "no_execution_authority"];
  const labels = [
    "The rationale is supported by the supplied evidence",
    "The citations cover the claims in the answer",
    "Uncertainty and missing information are preserved",
    "The answer grants no authority to place orders"
  ];
  const clone = value => JSON.parse(JSON.stringify(value));
  const stable = value => {
    if (Array.isArray(value)) return "[" + value.map(stable).join(",") + "]";
    if (value !== null && typeof value === "object") {
      return "{" + Object.keys(value).sort().map(k => JSON.stringify(k) + ":" + stable(value[k])).join(",") + "}";
    }
    return JSON.stringify(value);
  };
  function fields(value, expected) {
    if (!value || Array.isArray(value) || typeof value !== "object" ||
        stable(Object.keys(value).sort()) !== stable([...expected].sort())) {
      throw new Error("Unexpected review fields.");
    }
  }
  function identity(value) {
    return typeof value === "string" && /^[A-Za-z0-9_.:-]{1,128}$/.test(value);
  }
  function utc(value) {
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value)) return false;
    const parsed = new Date(value);
    return Number(value.slice(0, 4)) > 0 && Number.isFinite(parsed.valueOf()) && parsed.toISOString() === value.slice(0, -1) + ".000Z";
  }
  function restore(payload, imported) {
    const base = payload.review;
    fields(imported, Object.keys(base));
    for (const key of Object.keys(base).filter(k => !["attestation", "cases"].includes(k))) {
      if (stable(imported[key]) !== stable(base[key])) throw new Error("Review source/prompt binding changed.");
    }
    const attestation = imported.attestation;
    fields(attestation, Object.keys(base.attestation));
    if (attestation.reviewer_type !== "operator" || typeof attestation.confirmed !== "boolean") {
      throw new Error("Only an operator review may be resumed; agent findings are not your approvals.");
    }
    if (attestation.confirmed ? !identity(attestation.reviewer_id) || !utc(attestation.reviewed_at_utc)
      : attestation.reviewer_id !== null || attestation.reviewed_at_utc !== null) {
      throw new Error("Malformed operator attestation.");
    }
    if (!Array.isArray(imported.cases) || imported.cases.length !== base.cases.length) {
      throw new Error("The review must contain exactly this page's cases.");
    }
    const byId = new Map();
    for (const row of imported.cases) {
      fields(row, Object.keys(base.cases[0]));
      if (typeof row.case_id !== "string" || byId.has(row.case_id)) throw new Error("Duplicate/invalid case.");
      byId.set(row.case_id, row);
    }
    const result = clone(base);
    for (const row of result.cases) {
      const other = byId.get(row.case_id);
      if (!other || other.binding_sha256 !== row.binding_sha256 || other.target_response !== row.target_response) {
        throw new Error("Case evidence or proposed target changed. Generate a newly pinned page for revised targets.");
      }
      if (!["pending", "approve", "reject"].includes(other.decision) ||
          typeof other.note !== "string" || other.note.length > 1024) {
        throw new Error("Invalid decision or oversized note.");
      }
      fields(other.checks, checks);
      if (checks.some(k => other.checks[k] !== null && typeof other.checks[k] !== "boolean")) {
        throw new Error("Case confirmations must be yes, no, or not reviewed.");
      }
      row.decision = other.decision;
      row.note = other.note;
      row.checks = clone(other.checks);
    }
    // Never import an agent's findings or inherit an earlier final operator confirmation.
    result.attestation = {reviewer_type: "operator", reviewer_id: null, reviewed_at_utc: null, confirmed: false};
    return result;
  }
  function parseImport(payload, raw) {
    if (typeof raw !== "string" || new TextEncoder().encode(raw).length > 1024 * 1024) {
      throw new Error("Review file is larger than 1 MiB.");
    }
    return restore(payload, JSON.parse(raw));
  }
  function assess(payload, review) {
    const validated = restore(payload, review);
    const verdicts = new Set();
    const rows = validated.cases.map(row => {
      const issues = [];
      if (row.decision === "pending") issues.push("Choose approve or reject.");
      else if (!row.note.trim()) issues.push("Add a reason for your decision.");
      if (row.decision === "approve" && checks.some(k => row.checks[k] !== true)) {
        issues.push("Approval needs all four case confirmations set to Yes.");
      }
      if (row.decision === "approve" && !issues.length) verdicts.add(JSON.parse(row.target_response).verdict);
      return {case_id: row.case_id, issues};
    });
    const resolved = rows.filter(row => !row.issues.length).length;
    const balanced = verdicts.has("support") && verdicts.has("veto");
    return {rows, resolved, balanced, complete: resolved === rows.length};
  }
  function makeExport(payload, review, options = {}) {
    const result = restore(payload, review);
    if (options.confirmed !== undefined && typeof options.confirmed !== "boolean") {
      throw new Error("Operator confirmation must be an explicit boolean.");
    }
    if (options.confirmed === true) {
      if (!assess(payload, result).complete) throw new Error("Resolve all cases first. Rejection is a valid decision.");
      if (!identity(options.reviewerId) || !utc(options.timestamp)) throw new Error("Valid reviewer ID and UTC timestamp required.");
      result.attestation = {
        reviewer_type: "operator", reviewer_id: options.reviewerId,
        reviewed_at_utc: options.timestamp, confirmed: true
      };
    }
    return result;
  }
  const api = {checks, restore, parseImport, assess, makeExport};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document === "undefined") return;

  const el = id => document.getElementById(id);
  const pretty = value => JSON.stringify(value, null, 2);
  function start() {
    const payload = JSON.parse(el("workbench-data").textContent);
    let review = clone(payload.review), index = 0;
    // Browsers can restore form values on history navigation; never inherit confirmation.
    el("confirm").checked = false;
    el("reviewer-id").value = "";
    const picker = el("case-picker");
    for (const row of review.cases) {
      const option = document.createElement("option");
      option.value = row.case_id;
      option.textContent = row.case_id;
      picker.append(option);
    }
    for (let i = 0; i < checks.length; i++) {
      const label = document.createElement("label");
      label.textContent = labels[i];
      const select = document.createElement("select");
      select.id = checks[i];
      for (const [value, text] of [["", "Not reviewed"], ["yes", "Yes"], ["no", "No"]]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = text;
        select.append(option);
      }
      select.addEventListener("change", saveCase);
      label.append(select);
      el("checks").append(label);
    }
    el("provenance").textContent = pretty({
      suite_raw_sha256: review.suite_sha256,
      proposal_raw_sha256: payload.proposal_raw_sha256,
      proposal_canonical_sha256: payload.proposal_canonical_sha256,
      packet_sha256: review.packet_sha256, prompt_sha256: review.prompt_sha256,
      system_prompt: payload.system_prompt
    });
    function status() {
      const state = assess(payload, review);
      el("progress").textContent = `${state.resolved} / ${review.cases.length} cases resolved`;
      el("case-status").textContent = state.rows[index].issues.join(" ") || "Case resolved in this tab. Save a draft to keep it.";
      const ready = state.complete && identity(el("reviewer-id").value) && el("confirm").checked;
      el("export").disabled = !ready;
      el("export-status").textContent = !state.complete
        ? "Final export is locked until every case is resolved. You may reject any or all targets."
        : ready ? "Ready to download your attested review. Python audit is still required."
        : "Enter your reviewer ID and personally confirm the review to enable final export.";
      if (state.complete && !state.balanced) el("export-status").textContent +=
        " This review lacks approved support/veto coverage, so training-candidate export will remain blocked.";
      for (let i = 0; i < picker.options.length; i++) {
        picker.options[i].textContent = review.cases[i].case_id + " · " + review.cases[i].decision;
      }
    }
    function render() {
      const row = review.cases[index], fact = payload.material[index];
      const target = JSON.parse(row.target_response);
      picker.value = row.case_id;
      el("case-title").textContent = row.case_id;
      el("case-source").textContent = `Family: ${fact.family} · Session: ${fact.source_session}`;
      el("numeric").textContent = pretty(fact.numerical_assessment);
      el("evidence").textContent = pretty(fact.input);
      el("verdict").textContent = target.verdict === "support" ? "Conditional support" : "Veto / no trade";
      el("rationale").textContent = target.rationale;
      el("citations").textContent = target.evidence_ids.join(", ");
      el("agent-note").textContent = fact.proposal_note;
      el("original").textContent = pretty({draft: fact.draft_reference_response, required_citation_groups: fact.draft_citation_groups});
      el("target").textContent = row.target_response;
      el("decision").value = row.decision;
      el("note").value = row.note;
      for (const key of checks) el(key).value = row.checks[key] === null ? "" : row.checks[key] ? "yes" : "no";
      el("previous").disabled = index === 0;
      el("next").disabled = index === review.cases.length - 1;
      status();
    }
    function saveCase() {
      const row = review.cases[index];
      row.decision = el("decision").value;
      row.note = el("note").value;
      for (const key of checks) row.checks[key] = el(key).value === "" ? null : el(key).value === "yes";
      el("confirm").checked = false;
      status();
    }
    function download(confirmed) {
      try {
        const result = makeExport(payload, review, {
          confirmed, reviewerId: el("reviewer-id").value,
          timestamp: new Date().toISOString().slice(0, 19) + "Z"
        });
        const blob = new Blob([pretty(result) + "\n"], {type: "application/json"});
        const url = URL.createObjectURL(blob), anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = confirmed ? "qwen_operator_review.json" : "qwen_operator_review_draft.json";
        document.body.append(anchor);
        anchor.click();
        anchor.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        el("message").textContent = "Download requested. Keep the saved JSON; this page cannot verify the browser saved it. No training was started.";
      } catch (error) { el("message").textContent = error.message; }
    }
    picker.addEventListener("change", () => {index = picker.selectedIndex; render();});
    el("previous").addEventListener("click", () => {if (index > 0) {index--; render();}});
    el("next").addEventListener("click", () => {if (index + 1 < review.cases.length) {index++; render();}});
    el("decision").addEventListener("change", saveCase);
    el("note").addEventListener("input", saveCase);
    el("reviewer-id").addEventListener("input", () => {el("confirm").checked = false; status();});
    el("confirm").addEventListener("change", status);
    el("save-draft").addEventListener("click", () => download(false));
    el("export").addEventListener("click", () => {if (!el("export").disabled && el("confirm").checked) download(true);});
    el("resume").addEventListener("change", async event => {
      try {
        const file = event.target.files[0];
        if (!file) return;
        if (file.size > 1024 * 1024) throw new Error("Review file is larger than 1 MiB.");
        const restored = parseImport(payload, await file.text());
        review = restored;
        index = 0;
        el("confirm").checked = false;
        el("reviewer-id").value = "";
        render();
        el("message").textContent = "Restored case decisions. Reviewer identity and final confirmation have been reset.";
      } catch (error) { el("message").textContent = "Review not restored: " + error.message; }
      finally { event.target.value = ""; }
    });
    render();
  }
  try { start(); }
  catch (error) {
    el("export").disabled = true;
    el("save-draft").disabled = true;
    el("message").textContent = "Review page could not initialize: " + error.message;
  }
}());
