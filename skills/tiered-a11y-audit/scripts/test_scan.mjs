#!/usr/bin/env node
// Self-check of axe_scan.mjs against pages served from this process. Needs what the scan needs, so it runs
// where the scan runs: copy both files into the directory that holds node_modules, then
//   node test_scan.mjs [--channel chrome]
// Plain asserts, no test framework. Exits 1 on the first failure.

import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

const page = (body, attrs = '') => `<!doctype html><html lang="en" ${attrs}><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Fixture</title>
<style>body { margin: 0; font: 16px sans-serif; } main { padding: 16px; }</style></head><body><main><h1>Fixture</h1>${body}</main></body></html>`;

const PAGES = {
  // nothing here is cut off: each of these waits outside the page or is hidden on purpose
  '/': page(`
    <a href="#x" style="position:absolute; top:-60px; left:0; height:40px">Skip to content</a>
    <nav style="position:absolute; left:0; top:0; width:200px; transform:translateX(-100%)"><a href="/a">Drawer link</a></nav>
    <span style="position:absolute; left:0; width:1px; height:1px; margin:-1px; overflow:hidden; clip:rect(0,0,0,0)">Hidden label</span>
    <p style="position:absolute; left:-80px; top:200px; width:200px; opacity:0">Faded out</p>
    <div style="position:absolute; left:-80px; top:300px; width:200px; padding-left:100px"><span>Inside a box that sticks out</span></div>
    <p id="x" style="color:#aaa; background:#fff">Grey text on white.</p>
    <p style="color:#bbb; background:#fff">More grey text on white.</p>
    <img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" width="10" height="10">`),
  // the popover of the report: opened by a button, positioned with a negative left
  '/menu': page(`
    <button type="button" onclick="document.getElementById('pop').hidden = false">Open menu</button>
    <button type="button" class="twin">Twin</button> <button type="button" class="twin">Twin</button>
    <input class="q" aria-label="First"> <input class="q" aria-label="Second">
    <div id="pop" hidden style="position:absolute; left:-214px; top:120px; width:258px">
      <p>Reader settings</p><button type="button" class="size" style="width:250px"><span>Larger text</span></button>
    </div>
    <p style="position:absolute; left:20px; top:-10px; margin:0">Cut off at the top</p>`),
  // a button that only a narrow window shows, and one that only a wide window shows
  '/phone': page(`
    <style>#burger { display: none } @media (max-width: 600px) { #burger { display: inline-block } #desk { display: none } }</style>
    <button id="desk" type="button">Desk</button>
    <button id="burger" type="button" onclick="this.insertAdjacentHTML('afterend', '<p id=open>Menu is open</p>')">Menu</button>`),
  '/rtl': page('<p style="position:absolute; left:-80px; top:200px; width:200px">Reachable by scrolling</p>', 'dir="rtl"'),
  '/wide': page('<div id="banner" style="width:2000px">A banner that does not shrink</div>'),
};

const server = http.createServer((req, res) => {
  const body = PAGES[req.url];
  res.writeHead(body ? 200 : 404, { 'content-type': 'text/html; charset=utf-8' });
  res.end(body || 'not found');
});
await new Promise((ok) => server.listen(0, '127.0.0.1', ok));
const origin = `http://127.0.0.1:${server.address().port}`;
const here = path.dirname(fileURLToPath(import.meta.url));
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'scan-check-'));
const extra = process.argv.slice(2);

// not execFileSync: the pages are served from this process, which must keep answering while the scan runs
async function scan(name, args) {
  const out = path.join(tmp, name);
  const { stdout } = await promisify(execFile)(process.execPath,
    [path.join(here, 'axe_scan.mjs'), '--out', out, '--tabs', '5', ...extra, ...args], { timeout: 240000 });
  const rows = JSON.parse(fs.readFileSync(path.join(out, 'summary.json'), 'utf8'));
  const detail = (slug) => JSON.parse(fs.readFileSync(path.join(out, `${slug}.json`), 'utf8'));
  return { out, stdout, rows, detail, row: (key) => rows.find((r) => r.state === key || r.url === origin + key) };
}

let failed = 0;
function check(name, fn) {
  try { fn(); console.log(`ok    ${name}`); } catch (e) { failed++; console.log(`FAIL  ${name}\n      ${String(e.message).split('\n').join('\n      ')}`); }
}

try {
  const steps = path.join(tmp, 'states.json');
  fs.writeFileSync(steps, JSON.stringify([
    { name: 'menu-open', url: `${origin}/menu`, actions: [{ click: 'text=open MENU' }, { click: '.twin' }, { click: "text='Twin' >> nth=1" }] },
    { name: 'menu-by-css-text', url: `${origin}/menu`, actions: [{ click: "button:text-is('Open menu')" }] },
    { name: 'phone-menu', url: `${origin}/phone`, viewport: { width: 390, height: 800 }, actions: [{ click: '#burger' }] },
    { name: 'desk-only', url: `${origin}/phone`, actions: [{ click: '#desk' }] },
    { name: 'type-first', url: `${origin}/menu`, actions: [{ type: '.q >> nth=0', value: 'ab' }] },
    { name: 'type-either', url: `${origin}/menu`, actions: [{ type: '.q', value: 'ab' }] },
    { name: 'no-such-button', url: `${origin}/menu`, actions: [{ click: '#absent' }] },
  ]));
  const s = await scan('all', ['--steps', steps, `${origin}/`, `${origin}/menu`, `${origin}/rtl`, `${origin}/wide`]);

  check('what waits outside the page or is hidden is not reported as cut off', () => {
    assert.deepEqual(s.row('/').offscreenAt, []);
    assert.equal(s.detail(`127-0-0-1-${server.address().port}`).reflow.offscreenCount, 0);
  });
  check('an open popover with a negative left is reported at every width, once per outermost element', () => {
    const row = s.row('menu-open');
    assert.deepEqual(row.offscreenAt, [320, 1280, 768, 1024]);
    assert.equal(row.reflowFails, false, 'it does not widen the page: that is why the reflow check never saw it');
    const at320 = s.detail('menu-open').reflow;
    const names = at320.offscreen.map((o) => o.element);
    assert.deepEqual(names, ['p', 'button.size', 'p'], 'the span inside the button is not listed beside it');
    const pop = at320.offscreen.find((o) => o.text === 'Reader settings');
    assert.equal(pop.left, -214);
    assert.equal(pop.right, 44);
  });
  check('a closed popover is not reported, text cut off at the top is', () => {
    const closed = s.detail(`127-0-0-1-${server.address().port}-menu`).reflow;
    assert.deepEqual(closed.offscreen.map((o) => o.text), ['Cut off at the top']);
    assert.equal(closed.offscreen[0].top, -10);
    assert.deepEqual(s.row('/menu').offscreenAt, [320, 1280, 768, 1024]);
  });
  check('a selector may be text, in either spelling, or the nth match', () => {
    assert.equal(s.row('menu-open').stateReached, true, 'text in any case, the first of two, exact text with nth');
    assert.equal(s.row('type-first').stateReached, true);
    assert.equal(s.row('type-either').stateReached, false, 'type wants one match');
    assert.match(s.detail('type-either').errors.actions, /strict mode violation/);
    assert.equal(s.row('menu-by-css-text').stateReached, true);
    assert.deepEqual(s.row('menu-by-css-text').offscreenAt, [320, 1280, 768, 1024]);
  });
  check('a state that only a narrow window can reach is reached, and the other widths say so', () => {
    const row = s.row('phone-menu');
    assert.equal(row.stateReached, true);
    assert.deepEqual(row.notReachedAt, [768, 1024]);
    assert.equal(row.reflowFails, false);
    assert.deepEqual(row.errors, []);
    const wide = s.detail('phone-menu').widths.find((w) => w.viewportWidth === 768);
    assert.equal(wide.reached, false);
    assert.match(wide.reason, /Timeout.*\{"click":"#burger"\}/, 'the reason names the action that failed');
    assert.ok(!fs.existsSync(path.join(s.out, 'phone-menu.768.png')), 'no screenshot of a state that was not reached');
    assert.ok(fs.existsSync(path.join(s.out, 'phone-menu.320.png')));
  });
  check('a state that 320 pixels cannot reach is reached, and has no reflow verdict', () => {
    const row = s.row('desk-only');
    assert.equal(row.stateReached, true);
    assert.deepEqual(row.notReachedAt, [320]);
    assert.equal(row.reflowFails, null);
    assert.deepEqual(row.errors, []);
  });
  check('a state that is reached nowhere says so, and has no reflow verdict', () => {
    const row = s.row('no-such-button');
    assert.equal(row.stateReached, false);
    assert.deepEqual(row.notReachedAt, [320, 768, 1024]);
    assert.equal(row.reflowFails, null);
    assert.deepEqual(row.errors, ['actions']);
    assert.match(s.detail('no-such-button').errors.actions, /\{"click":"#absent"\}/);
  });
  check('on a right-to-left page what lies to the left is within reach', () => {
    assert.deepEqual(s.row('/rtl').offscreenAt, []);
  });
  check('sideways scrolling at 320 is still the reflow verdict, with what causes it', () => {
    assert.equal(s.row('/wide').reflowFails, true);
    const d = s.detail(`127-0-0-1-${server.address().port}-wide`);
    assert.ok(d.reflow.culprits.includes('div#banner'));
    assert.equal(d.reflow.viewportWidth, 320);
    assert.deepEqual(d.widths.map((w) => w.viewportWidth), [1280, 768, 1024]);
    assert.ok(d.widths.every((w) => w.horizontalOverflowPx > 1 && w.fails === undefined), 'only 320 is a verdict');
    for (const w of [320, 768, 1024]) assert.ok(fs.existsSync(path.join(s.out, `127-0-0-1-${server.address().port}-wide.${w}.png`)));
  });
  check('a row names the rules that failed, with their number of elements, per colour scheme', () => {
    const row = s.row('/');
    assert.equal(row.rules['color-contrast'], 2);
    assert.equal(row.rules['image-alt'], 1);
    assert.equal(Object.keys(row.rules).length, row.axeViolations);
    assert.equal(Object.values(row.rules).reduce((a, b) => a + b, 0), row.axeNodes);
    assert.equal(Object.keys(row.rulesDark).length, row.axeViolationsDark);
  });
  check('every row is printed as it is written', () => {
    assert.deepEqual(s.stdout.trim().split('\n').map((l) => JSON.parse(l)), s.rows);
  });

  const none = await scan('none', ['--widths', '0', `${origin}/menu`]);
  check('--widths 0 leaves the extra widths out, and 320 stays', () => {
    assert.deepEqual(none.detail(`127-0-0-1-${server.address().port}-menu`).widths.map((w) => w.viewportWidth), [1280]);
    assert.deepEqual(none.row('/menu').offscreenAt, [320, 1280]);
  });
  const own = await scan('own', ['--widths', '640,320,1280', `${origin}/menu`]);
  check('--widths takes a list, without 320 and the viewport a second time', () => {
    assert.deepEqual(own.detail(`127-0-0-1-${server.address().port}-menu`).widths.map((w) => w.viewportWidth), [1280, 640]);
  });
} finally {
  server.close();
  fs.rmSync(tmp, { recursive: true, force: true });
}
console.log(failed ? `${failed} failed` : 'all scan checks passed');
process.exit(failed ? 1 : 0);
