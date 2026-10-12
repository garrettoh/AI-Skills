/* Exercise the actual generated dashboard script without third-party packages.
 * This small DOM harness verifies behavior; it does not validate browser layout.
 * Usage: node incident-response/scripts/verify_dashboard_ui.js CASE/dashboard.html
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const file = process.argv[2];
if (!file) throw new Error('Provide a generated dashboard.html path');
const html = fs.readFileSync(file, 'utf8');
const embedded = html.split('<script id="case-data" type="application/json">')[1].split('</script>')[0];
const data = JSON.parse(embedded);
const script = html.split('</script><script>')[1].split('</script>')[0];
class Element {
    constructor(tag) { this.tagName = tag; this.children = []; this.style = {}; this.dataset = {}; this.value = ''; this.hidden = false; this.attributes = {}; this.textContent = ''; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(key, value) { this.attributes[key] = String(value); }
    addEventListener(type, callback) { this['on' + type] = callback; }
}
const elements = new Map([...html.matchAll(/id="([^"]+)"/g)].map(m => [m[1], new Element('div')]));
elements.get('case-data').textContent = embedded;
elements.get('timing').value = 'all';
const tabs = ['timeline', 'analysis', 'leads', 'coverage'].map(tab => { const e = new Element('button'); e.dataset.tab = tab; return e; });
const context = vm.createContext({document: {
    getElementById: id => elements.get(id),
    createElement: tag => new Element(tag),
    querySelectorAll: selector => { assert.equal(selector, '[data-tab]'); return tabs; },
}, setTimeout, clearTimeout});
vm.runInContext(script, context, {timeout: 10000});
const evaluate = code => vm.runInContext(code, context, {timeout: 10000});
const root = path.dirname(file);
const lines = name => fs.readFileSync(path.join(root, name), 'utf8').split(/\r?\n/).filter(Boolean).map(JSON.parse);
assert.deepEqual(data.events, [...lines('timeline.jsonl'), ...lines('untimed.jsonl')]);
assert.deepEqual(data.leads, JSON.parse(fs.readFileSync(path.join(root, 'leads.json'), 'utf8')).leads);
assert.equal(data.analysis, fs.readFileSync(path.join(root, 'analysis.md'), 'utf8').replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n'));
assert.equal(evaluate('filtered.length'), data.events.length);
assert.equal(elements.get('events').children.length, Math.min(50, data.events.length));
elements.get('search').value = 'fleetdeck';
evaluate('filter()');
assert.equal(evaluate('filtered.length'), data.events.filter(e => JSON.stringify(e).toLowerCase().includes('fleetdeck')).length);
elements.get('reset').onclick();
elements.get('timing').value = 'untimed';
evaluate('filter()');
assert.equal(evaluate('filtered.length'), data.events.filter(e => !e.timestamp_utc).length);
elements.get('reset').onclick();
const source = data.events.find(e => e.orchestrator)?.orchestrator;
if (source) {
    elements.get('source').value = source;
    evaluate('filter()');
    assert.equal(evaluate('filtered.length'), data.events.filter(e => e.orchestrator === source).length);
}
elements.get('reset').onclick();
const day = data.events.find(e => e.timestamp_utc)?.timestamp_utc.slice(0, 10);
if (day) {
    elements.get('start').value = elements.get('end').value = day;
    evaluate('filter()');
    assert.equal(evaluate('filtered.length'), data.events.filter(e => !e.timestamp_utc || e.timestamp_utc.startsWith(day)).length);
}
elements.get('reset').onclick();
if (data.events.length > 50) {
    elements.get('next').onclick();
    assert.equal(evaluate('page'), 1);
    elements.get('prev').onclick();
    assert.equal(evaluate('page'), 0);
}
elements.get('search').value = 'nonexistent-test-value-97f3c';
evaluate('filter()');
assert.equal(evaluate('filtered.length'), 0);
assert.equal(elements.get('events').children[0].textContent, 'No observations match these filters.');
tabs[1].onclick();
assert.equal(elements.get('analysis').hidden, false);
assert.equal(elements.get('timeline').hidden, true);
assert.equal(elements.get('narrative').textContent, data.analysis);
elements.get('leadsearch').value = 'nonexistent-test-value-97f3c';
elements.get('leadsearch').oninput();
assert.equal(elements.get('leadrows').children[0].textContent, '0 leads');
assert.equal(elements.get('coveragerows').children.length, Math.max(1, data.coverage.length));
console.log(`PASS: ${data.events.length} complete observations, ${data.leads.length} leads, ${data.coverage.length} coverage reports; search, source/date/untimed filters, pagination, empty states and analyst tab`);
