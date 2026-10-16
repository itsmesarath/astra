/* Synthetic state tests only; no real user review or browser download occurs. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const asset = path.join(__dirname, '../src/ai_trader/training/assets/review_workbench.js');
const api = require(asset);
const clone = value => JSON.parse(JSON.stringify(value));

function fixture() {
  const review = {
    schema_version: 1, kind: 'advisory_curriculum_review_v1', suite_sha256: 'a'.repeat(64),
    packet_sha256: 'b'.repeat(64), prompt_sha256: 'c'.repeat(64),
    review_contract: 'synthetic', check_version: 'synthetic',
    attestation: {reviewer_type: 'operator', reviewer_id: null, reviewed_at_utc: null, confirmed: false},
    cases: ['veto', 'support'].map((verdict, i) => ({
      case_id: 'synthetic_' + i, binding_sha256: String(i).repeat(64), decision: 'pending',
      target_response: JSON.stringify({verdict, evidence_ids: ['e' + i], rationale: 'Synthetic test only.'}),
      checks: Object.fromEntries(api.checks.map(key => [key, null])), note: ''
    }))
  };
  return {review, material: review.cases.map(row => ({
    case_id: row.case_id, family: 'synthetic', source_session: 'test', input: {synthetic: true},
    numerical_assessment: {status: 'test'}, proposal_note: '</script><img onerror="not executed">',
    draft_reference_response: row.target_response, draft_citation_groups: [['e']]
  })), system_prompt: 'Synthetic prompt', proposal_raw_sha256: 'd'.repeat(64), proposal_canonical_sha256: 'e'.repeat(64)};
}
function approved(payload) {
  const review = clone(payload.review);
  for (const row of review.cases) {
    row.decision = 'approve'; row.note = 'Synthetic test decision, not a real review.';
    for (const key of api.checks) row.checks[key] = true;
  }
  return review;
}
const attestation = {confirmed: true, reviewerId: 'synthetic-test', timestamp: '2026-09-24T12:00:00Z'};

test('defaults remain pending, blank and unconfirmed', () => {
  const data = fixture(), before = clone(data);
  const draft = api.makeExport(data, data.review);
  assert.deepEqual(data, before);
  assert.equal(api.assess(data, draft).resolved, 0);
  assert.equal(draft.attestation.confirmed, false);
  assert.throws(() => api.makeExport(data, draft, attestation));
});
test('synthetic complete approvals export only with explicit identity and confirmation', () => {
  const data = fixture(), review = approved(data);
  assert.equal(api.assess(data, review).complete, true);
  assert.equal(api.makeExport(data, review).attestation.confirmed, false);
  assert.equal(api.makeExport(data, review, attestation).attestation.confirmed, true);
});
for (const value of [1, 'true', null]) test('non-boolean confirmation refuses: ' + value, () => {
  const data = fixture();
  assert.throws(() => api.makeExport(data, approved(data), {...attestation, confirmed: value}));
});
for (const value of ['', 'name with spaces', 'x'.repeat(129), null]) test('bad identity refuses: ' + value, () => {
  const data = fixture();
  assert.throws(() => api.makeExport(data, approved(data), {...attestation, reviewerId: value}));
});
for (const value of ['0000-01-01T12:00:00Z', '2026-02-30T12:00:00Z', '2026-09-24', '2026-09-24T12:00:00+00:00']) {
  test('bad UTC time refuses: ' + value, () => {
    const data = fixture();
    assert.throws(() => api.makeExport(data, approved(data), {...attestation, timestamp: value}));
  });
}
for (const mutate of [
  r => r.suite_sha256 = 'changed', r => r.schema_version = true, r => r.extra = 1,
  r => r.cases.pop(), r => r.cases[1].case_id = r.cases[0].case_id,
  r => r.cases[0].binding_sha256 = 'changed', r => r.cases[0].target_response = '{}',
  r => r.cases[0].decision = 'unknown', r => r.cases[0].note = 'x'.repeat(1025),
  r => r.cases[0].checks.rationale_supported = 1, r => r.cases[0].checks.extra = true,
  r => r.attestation.reviewer_type = 'agent', r => r.attestation.reviewer_id = 'claimed-without-confirmation'
]) test('malformed/drifted resume refuses: ' + mutate.toString(), () => {
  const data = fixture(), review = approved(data);
  mutate(review);
  assert.throws(() => api.restore(data, review));
});
test('resume preserves case decisions, resets global attestation, and does not mutate input', () => {
  const data = fixture(), review = api.makeExport(data, approved(data), attestation), before = clone(review);
  const restored = api.parseImport(data, JSON.stringify(review));
  assert.equal(restored.cases[0].decision, 'approve');
  assert.deepEqual(restored.attestation, data.review.attestation);
  assert.deepEqual(review, before);
});
test('resumed case order is normalized to the frozen page', () => {
  const data = fixture(), review = approved(data);
  review.cases.reverse();
  assert.equal(api.restore(data, review).cases[0].case_id, 'synthetic_0');
});
test('oversized, null and malformed import refuse', () => {
  for (const raw of ['x'.repeat(1024 * 1024 + 1), 'null', '{', '[]']) {
    assert.throws(() => api.parseImport(fixture(), raw));
  }
});
test('approval needs notes and four positive checks, not merely selecting approve', () => {
  const data = fixture(), review = approved(data);
  review.cases[0].note = '  ';
  assert.equal(api.assess(data, review).complete, false);
  review.cases[0].note = 'reason';
  for (const key of api.checks) {
    review.cases[0].checks[key] = false;
    assert.equal(api.assess(data, review).complete, false);
    review.cases[0].checks[key] = true;
  }
});
test('rejections require a reason and cannot supply the missing verdict class', () => {
  const data = fixture(), review = approved(data);
  review.cases[0].decision = 'reject';
  review.cases[0].checks = Object.fromEntries(api.checks.map(key => [key, null]));
  assert.equal(api.assess(data, review).resolved, 2);
  assert.equal(api.assess(data, review).balanced, false);
  assert.equal(api.makeExport(data, review, attestation).attestation.confirmed, true);
  assert.equal(api.assess(data, review).complete, true);
});
test('all-rejected review can be attested without inventing positive approvals', () => {
  const data = fixture(), review = clone(data.review);
  for (const row of review.cases) { row.decision = 'reject'; row.note = 'Synthetic rejection.'; }
  const result = api.makeExport(data, review, attestation);
  assert.equal(result.attestation.confirmed, true);
  assert.equal(api.assess(data, review).balanced, false);
  assert.ok(result.cases.every(row => row.decision === 'reject'));
});

// Minimal DOM event fixture, not a browser or visual rendering workaround.
function ui(restoredForm = false) {
  const elements = new Map(), downloads = [], blobs = [];
  class Element {
    constructor(tag = '') { this.tag = tag; this.children = []; this.events = {}; this.value = ''; this.checked = false; this.disabled = false; this.textContent = ''; }
    set id(value) { this._id = value; elements.set(value, this); }
    get id() { return this._id; }
    get options() { return this.children; }
    get selectedIndex() { return this.children.findIndex(child => child.value === this.value); }
    append(child) { this.children.push(child); }
    addEventListener(name, handler) { this.events[name] = handler; }
    async dispatch(name) { return this.events[name]({target: this}); }
    click() { downloads.push({filename: this.download, href: this.href}); }
    remove() {}
  }
  const html = fs.readFileSync(path.join(path.dirname(asset), 'review_workbench.html'), 'utf8');
  for (const match of html.matchAll(/<([a-z]+)[^>]* id="([^"]+)"/g)) {
    const element = new Element(match[1]); element.id = match[2];
  }
  const payload = fixture();
  elements.get('workbench-data').textContent = JSON.stringify(payload);
  if (restoredForm) {
    elements.get('confirm').checked = true;
    elements.get('reviewer-id').value = 'stale-identity';
  }
  const document = {getElementById: id => elements.get(id), createElement: tag => new Element(tag), body: new Element('body')};
  vm.runInNewContext(fs.readFileSync(asset, 'utf8'), {
    document, TextEncoder, Blob, Date, setTimeout: callback => { callback(); },
    URL: {createObjectURL: blob => {blobs.push(blob); return 'blob:synthetic';}, revokeObjectURL() {}}
  });
  return {get: id => elements.get(id), downloads, blobs, payload};
}
test('UI initializes 0/2, blank human checks and disabled final export', () => {
  const view = ui();
  assert.equal(view.get('message').textContent, '');
  assert.equal(view.get('progress').textContent, '0 / 2 cases resolved');
  assert.equal(view.get('export').disabled, true);
  for (const key of api.checks) assert.equal(view.get(key).value, '');
  assert.equal(view.get('agent-note').textContent, view.payload.material[0].proposal_note);
});
test('browser-restored identity and confirmation are cleared on initialization', () => {
  const view = ui(true);
  assert.equal(view.get('confirm').checked, false);
  assert.equal(view.get('reviewer-id').value, '');
  assert.equal(view.get('export').disabled, true);
});
test('UI synthetic completed review requires final confirmation and exports expected JSON', async () => {
  const view = ui();
  for (let index = 0; index < 2; index++) {
    view.get('decision').value = 'approve'; await view.get('decision').dispatch('change');
    view.get('note').value = 'Synthetic UI test only.'; await view.get('note').dispatch('input');
    for (const key of api.checks) { view.get(key).value = 'yes'; await view.get(key).dispatch('change'); }
    if (index === 0) await view.get('next').dispatch('click');
  }
  assert.equal(view.get('progress').textContent, '2 / 2 cases resolved');
  assert.equal(view.get('export').disabled, true);
  view.get('reviewer-id').value = 'synthetic-ui-test'; await view.get('reviewer-id').dispatch('input');
  view.get('confirm').checked = true; await view.get('confirm').dispatch('change');
  assert.equal(view.get('export').disabled, false);
  await view.get('export').dispatch('click');
  assert.equal(view.downloads[0].filename, 'qwen_operator_review.json');
  const result = JSON.parse(await view.blobs[0].text());
  assert.equal(result.attestation.confirmed, true);
  assert.equal(result.attestation.reviewer_id, 'synthetic-ui-test');
  assert.equal(result.cases[0].decision, 'approve');
});
test('navigation preserves decisions, edits clear confirmation, draft stays unconfirmed', async () => {
  const view = ui();
  view.get('decision').value = 'reject'; await view.get('decision').dispatch('change');
  view.get('note').value = 'Synthetic rejection.'; await view.get('note').dispatch('input');
  await view.get('next').dispatch('click');
  assert.equal(view.get('case-title').textContent, 'synthetic_1');
  await view.get('previous').dispatch('click');
  assert.equal(view.get('note').value, 'Synthetic rejection.');
  view.get('confirm').checked = true;
  await view.get('note').dispatch('input');
  assert.equal(view.get('confirm').checked, false);
  await view.get('save-draft').dispatch('click');
  assert.equal(view.downloads[0].filename, 'qwen_operator_review_draft.json');
  assert.equal(JSON.parse(await view.blobs[0].text()).attestation.confirmed, false);
});
test('final export click while locked makes no download', async () => {
  const view = ui();
  await view.get('export').dispatch('click');
  assert.equal(view.downloads.length, 0);
});
test('UI resume clears identity/confirmation and invalid import retains previous state', async () => {
  const view = ui(), review = api.makeExport(view.payload, approved(view.payload), attestation);
  view.get('reviewer-id').value = 'old'; view.get('confirm').checked = true;
  view.get('resume').files = [{size: 1000, text: async () => JSON.stringify(review)}];
  await view.get('resume').dispatch('change');
  assert.equal(view.get('reviewer-id').value, '');
  assert.equal(view.get('confirm').checked, false);
  assert.equal(view.get('progress').textContent, '2 / 2 cases resolved');
  const changed = clone(review); changed.cases[0].target_response = '{}';
  view.get('resume').files = [{size: 1000, text: async () => JSON.stringify(changed)}];
  await view.get('resume').dispatch('change');
  assert.match(view.get('message').textContent, /not restored/);
  assert.equal(view.get('progress').textContent, '2 / 2 cases resolved');
});
