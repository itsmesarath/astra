# Offline operator target-review page

Status (2026-09-24): implemented and tested with Python and synthetic JavaScript state/event
fixtures. **Visual browser verification remains incomplete**: the browser tool blocked the local
file URL. No alternate browser, local server or security-policy workaround was attempted.

The user has since delegated target decisions to the agent. The [completed V2 review and
candidate](QWEN_DELEGATED_REVIEW.md) remove the need to use this manual page for the current
curriculum. This page remains an optional, unchanged V1 human-review interface; it does not
accept V2 agent records or claim that a human reviewed them.

The page helps the actual operator review the 14 proposed curriculum targets without hand-editing
a large JSON document. It does not authenticate the reviewer, approve targets automatically,
export a training candidate, reserve held-out data, load a model, train or place orders.

## Current local review file

`logs/qwen_operator_workbench_v1_20260924.html` (68,005 bytes), raw SHA256:
`106de7abfeb390f5bedd787a65a1b2cc3c85ea1c0be4596a7ee0e50ef3a7ab55`.

It binds the unchanged frozen suite and agent-reviewed proposal:

- Suite: `configs/qwen_review_cases_v1.json`, raw SHA256
  `5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659`.
- Proposal: `logs/qwen_curriculum_agent_review_20260924.json`, raw SHA256
  `ebbc3b756b651e70f9fb04b005b351c1c09f4b9054ffdc0fd69f74e7e7f0fb60`.

The earlier `logs/qwen_operator_review_20260924.html` and
`logs/qwen_operator_review_ready_20260924.html` are superseded development builds, retained
without overwriting them. Use the **workbench_v1** file above. The HTML and downloaded review JSON are
local research artifacts, not published project data or human approvals made by this agent.

## Operator workflow

1. Open the HTML file in your own browser. It is self-contained and needs no server or internet.
   Its real browser layout/download behavior still needs your check; report any rendering issue.
2. For each case, inspect the full model-visible evidence, independent arithmetic assessment,
   proposed answer/citations, original draft and agent review note. The prompt and source pins
   are available at the bottom. A mechanical check is not proof that the explanation is sound.
3. Choose **approve** or **reject** and write a reason. Approval requires all four semantic checks
   to be **Yes**; rejection requires a reason but does not need positive attestations.
4. Use **Download draft** before closing the tab. There is no autosave, local storage or server.
   Resume with a previously downloaded operator review for the same pinned cases/targets.
5. Once all cases are resolved, enter your own reviewer ID and personally confirm the review.
   You can complete a review even if you reject every target. Download the confirmed review and
   return that JSON for a separate Python audit. Candidate export (not review export) additionally
   needs approved support and veto examples; the page warns if that coverage is absent.

Every new page resets **all** decisions to pending, semantic checks to null, notes to blank, and
operator identity/time/confirmation to unset. Agent findings are displayed separately; they never
pre-fill your confirmations. There is no approve-all control. Proposed targets are read-only in
this page: reject incorrect wording and explain the needed change, then generate a newly pinned
proposal/page after revision. Do not change the frozen source suite to force an approval.

Resume verifies envelope/case/prompt/target bindings, exact case coverage, types and bounded notes.
Agent attestations are refused. Prior operator case decisions may be restored, but reviewer ID and
final confirmation are always cleared. Any case edit clears final confirmation. Browser-restored
identity/checkbox values are explicitly reset on initialization as well.

Downloading a draft does not attest an identity/time, even if some case decisions are complete.
The final UTC timestamp is generated only during explicit confirmed export. JSON downloads remain
the existing `advisory_curriculum_review_v1` format. The browser's file picker reads only a file
you choose; no files are uploaded. A download request does not prove that the browser saved it.

## Independent audit after download

Keep the saved review unchanged once its hash is recorded. Use a fresh audit output path:

```powershell
$operatorReviewPath = 'C:/path/to/your/qwen_operator_review.json'
$operatorReviewSha = (Get-FileHash -LiteralPath $operatorReviewPath -Algorithm SHA256).Hash.ToLowerInvariant()
.venv\Scripts\python.exe -m ai_trader.training.advisory_curriculum audit --suite configs/qwen_review_cases_v1.json --suite-sha256 5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659 --review $operatorReviewPath --review-sha256 $operatorReviewSha --output logs/YOUR_NEW_operator_review_audit.json
```

The Python audit remains authoritative for eligibility and reconstructs the original bindings,
numeric checks, required citations and target schema. Browser state validation is a usability
check, not a security boundary or semantic oracle. Browser JSON parsing normalizes imported JSON;
it is not the Python strict raw-file reader. Only the pinned downloaded output is audited.

Even a passing review audit does not start training. [Candidate verification](QWEN_CURRICULUM_APPROVAL.md),
a genuinely independent [protected evaluation reservation](QWEN_TRAINING_PREFLIGHT.md) and a pinned
[bounded Qwen launch](QWEN_LORA_WORKER.md) remain separate requirements. The current reservation
is still empty. Do not reuse exposed development examples as a sealed holdout.

## Build and test

```powershell
.venv\Scripts\python.exe -m ai_trader.training.review_workbench --suite configs/qwen_review_cases_v1.json --suite-sha256 5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659 --proposal logs/qwen_curriculum_agent_review_20260924.json --proposal-sha256 ebbc3b756b651e70f9fb04b005b351c1c09f4b9054ffdc0fd69f74e7e7f0fb60 --output logs/YOUR_NEW_operator_review.html
.venv\Scripts\python.exe -m pytest tests/test_review_workbench.py -q
node --test tests_js/review_workbench.test.cjs
```

Building requires both raw input pins, validates the proposal and mechanically checks every target
even if it is still pending. Only curriculum cases are embedded; no development or protected
evaluation payloads are added. The HTML output must be new, is capped at 1 MiB and is fsynced;
a failed write can leave an incomplete file, never a completed approval. Native dependencies
are not imported. Node is needed only for JavaScript tests, not page generation or browser use.
The Python bridge test also runs the JavaScript suite when Node is available; otherwise that one
optional bridge test skips. It never persists a synthetic approval as a real review artifact.

The generator embeds JSON using escaped HTML delimiters and the UI uses `textContent`, not HTML
interpolation, for evidence and notes. A hash-based Content Security Policy permits only the
bundled script/style and denies external resources, connections and form submissions. There are
no external libraries, fonts, telemetry, cookies, service workers or server processes. This is
defense in depth, not an OS sandbox or protection against a deliberately modified local HTML file.

The HTML/CSS/JS are package resources and were verified byte-for-byte in the final locally built
wheel at `logs/review_workbench_package_verified_20260924/ai_trader-0.1.0-py3-none-any.whl`
(SHA256 `d2e6e224c9a576add1ce0c9c10aa33f6ca90140ef16ef8192673c151f65d5cfa`).
Tests cover blank/reset approvals, source drift, invalid proposals, injection escaping, CSP hashes,
output limits/exclusivity, resume, final confirmation, synthetic DOM events and Python export
compatibility, including an all-rejected review remaining ineligible for candidate export. Node
v24.19.0 was used. Synthetic DOM fixtures do **not** prove browser rendering or CSP/download behavior.

Validation: 19 new Python cases, 38 JavaScript tests; full suite **2,004 passed, one optional
Nautilus skip**. Ruff lint and formatting checks pass. No real operator decisions were entered.
