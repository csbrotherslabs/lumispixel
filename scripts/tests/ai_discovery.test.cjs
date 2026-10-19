const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const source = readFileSync('static/js/photographer_gallery_ai_discovery.js', 'utf8');
function setup() {
  const elements = {};
  for (const id of ['lp-semantic-toggle', 'lp-facial-toggle', 'lp-ai-save', 'lp-ai-reset', 'lp-ai-status']) {
    const label = {};
    elements[id] = {checked: false, disabled: true, listeners: {},
      closest: () => ({querySelector: () => label}),
      addEventListener(event, fn) { this.listeners[event] = fn; }};
  }
  elements['ai-photo-discovery'] = {dataset: {aiDiscoveryUrl: '/settings/'}};
  const requests = [];
  vm.runInNewContext(source, {document: {
    getElementById: id => elements[id], querySelector: () => ({value: 'csrf'})
  }, fetch: (url, options) => new Promise(resolve => requests.push({url, options, resolve}))});
  return {elements, requests};
}
const flush = () => new Promise(resolve => setImmediate(resolve));
test('loading disables reset; reset remains local until explicit save', async () => {
  const {elements: e, requests: r} = setup();
  assert.equal(e['lp-ai-reset'].disabled, true);
  r[0].resolve({ok: true, json: async () => ({semantic_enabled: true, semantic_available: true, facial_enabled: false})});
  await flush();
  assert.equal(e['lp-ai-save'].disabled, true);
  e['lp-ai-reset'].listeners.click();
  assert.equal(e['lp-semantic-toggle'].checked, false);
  assert.equal(e['lp-ai-save'].disabled, false);
  assert.equal(r.length, 1);
  assert.match(e['lp-ai-status'].textContent, /Save to apply/);
  const pending = e['lp-ai-save'].listeners.click();
  assert.equal(e['lp-ai-reset'].disabled, true);
  assert.equal(e['lp-semantic-toggle'].disabled, true);
  assert.deepEqual(JSON.parse(r[1].options.body), {semantic_enabled: false});
  await e['lp-ai-save'].listeners.click();
  assert.equal(r.length, 2);
  r[1].resolve({ok: true, json: async () => ({semantic_enabled: false})});
  await pending;
  assert.equal(e['lp-ai-save'].disabled, true);
  assert.equal(e['lp-facial-toggle'].checked, false);
});
test('failed load cannot enable settings or save', async () => {
  const {elements: e, requests: r} = setup();
  r[0].resolve({ok: false});
  await flush();
  assert.equal(e['lp-ai-save'].disabled, true);
  assert.equal(e['lp-ai-reset'].disabled, true);
  assert.match(e['lp-ai-status'].textContent, /unavailable/);
});
