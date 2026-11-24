#!/usr/bin/env node
// Runtime accessibility scan: axe-core + keyboard tab-walk + reflow + content cut off at the edge + target size
// + emulation screenshots.
//
// Requires (install in a throwaway dir, NOT in the audited project, and only with the user's consent):
//   npm i playwright @axe-core/playwright && npx playwright install chromium
// Copy this file INTO that directory before running it: Node resolves the imports below relative to the
// script's own location, so it must sit next to node_modules.
//
// Usage:
//   node axe_scan.mjs --out <dir> [--tabs 60] [--storage-state auth.json] [--width 1280] [--height 900]
//                     [--widths 768,1024] [--channel chrome|msedge] [--steps steps.json] <url> [<url> ...]
//
// --widths names the widths a view is loaded at besides its own viewport and 320: what a 1280 pixel window shows
//   at 125 and 167 percent zoom by default. Each one is a fresh load, so each adds a load per view; --widths 0
//   leaves them out. At every width the scan measures sideways scrolling and what lies partly left of or above
//   the start of the page, where no scrolling reaches it (a popover with a negative left).
//
// --sitemap <url> adds every <loc> from a sitemap.xml (and nested sitemap indexes) up to --max-pages (default 30),
//   so a static site is scanned whole without listing URLs by hand. Combine with --steps for stateful views.
// --channel uses an installed Google Chrome / Edge instead of Playwright's own Chromium (no extra download).
//   Without --channel, a missing Playwright browser triggers one automatic retry with channel "chrome".
// --steps runs the whole battery per named UI state that has no URL of its own (tabs, wizards, dialogs):
//   [{ "name": "health-tab", "url": "http://127.0.0.1:8000/", "viewport": { "width": 390, "height": 800 },
//      "actions": [{ "click": "button[data-t=health]" }, { "wait": 400 }] }, ...]
//   Action objects (exact shapes):
//     { "click": "<selector>" }            optional "force": true when Playwright calls the element invisible;
//                                          any Playwright selector, so also "text=Graphs" or "button:text-is('Graphs')"
//     { "type": "<selector>", "value": "x" } types real keystrokes (key events fire; use for search-as-you-type)
//     { "fill": "<selector>", "value": "x" } same as type (kept as an alias; fill() alone does NOT fire key events)
//     { "press": "Slash" }                  keyboard key (often the most reliable way to open a palette or menu)
//     { "wait": 400 }                        milliseconds
//     { "goto": "<url>" }
//   "viewport" per state is optional; mobile-only UI (hamburger menus) needs it.
//   A state whose actions fail is still recorded: summary.json gets "stateReached": false and the reason.
//   A state that is reached at its own viewport but not at another width (a menu button that only a phone
//   shows) is reached: the width is listed under "notReachedAt" and has no measurement.
// Axe runs in BOTH colour schemes, each in its OWN browser context with a fresh page load. Never run axe
// twice on the same page with a media flip in between: the second run reports colours from the first
// scheme against backgrounds of the second and fabricates "serious" contrast violations near 1.0:1.
//
// Contexts are created with bypassCSP: true, so the injected text-spacing stylesheet and axe itself work on
// apps with a strict Content-Security-Policy. Each check runs in its own try/catch; a failing check is recorded
// under result.errors instead of aborting the URL.
//
// Pitfall when writing your own helper: AxeBuilder needs a page from browser.newContext().newPage(),
// not browser.newPage() — otherwise it throws "Please use browser.newContext()".
//
// Writes per URL: <slug>.json (axe, tabWalk, reflow, widths, targets, textSpacing, motion), <slug>.aria.yml
// (accessibility tree, if supported), and screenshots <slug>.{default,320,forced-colors,dark,deuteranopia,
// text-spacing}.png plus one per width of --widths.
// Heuristics are labelled as such in the output.

import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

function parseArgs(argv) {
  const opts = { out: '.a11y-audit/automated', tabs: 60, storageState: undefined, width: 1280, height: 900, urls: [],
    widths: [768, 1024], channel: undefined, steps: undefined, sitemap: undefined, maxPages: 30 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--out') opts.out = argv[++i];
    else if (a === '--tabs') opts.tabs = Number(argv[++i]);
    else if (a === '--storage-state') opts.storageState = argv[++i];
    else if (a === '--width') opts.width = Number(argv[++i]);
    else if (a === '--height') opts.height = Number(argv[++i]);
    else if (a === '--widths') opts.widths = argv[++i].split(',').map(Number).filter((w) => w > 0 && w !== 320);
    else if (a === '--channel') opts.channel = argv[++i];
    else if (a === '--steps') opts.steps = argv[++i];
    else if (a === '--sitemap') opts.sitemap = argv[++i];
    else if (a === '--max-pages') opts.maxPages = Number(argv[++i]);
    else if (a.startsWith('http')) opts.urls.push(a);
    else { console.error(`Unknown argument: ${a}`); process.exit(2); }
  }
  if (!opts.urls.length && !opts.steps && !opts.sitemap) { console.error('Provide at least one URL, --sitemap or --steps file.'); process.exit(2); }
  return opts;
}

const slugify = (u) => {
  const { host, pathname, search } = new URL(u);
  return (host + pathname + search).replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').slice(0, 80) || 'root';
};

async function settle(page) {
  try { await page.waitForLoadState('networkidle', { timeout: 8000 }); } catch { /* long-polling apps */ }
  await page.waitForTimeout(400);
}

async function axeScan(page) {
  const r = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'])
    .analyze();
  return {
    violations: r.violations.map((v) => ({
      id: v.id, impact: v.impact, tags: v.tags.filter((t) => t.startsWith('wcag') || t === 'best-practice'),
      help: v.help, helpUrl: v.helpUrl,
      nodes: v.nodes.slice(0, 15).map((n) => ({ target: n.target, html: n.html.slice(0, 200), summary: n.failureSummary })),
      nodeCount: v.nodes.length,
    })),
    incompleteCount: r.incomplete.length,
    incomplete: r.incomplete.map((v) => ({ id: v.id, help: v.help, nodeCount: v.nodes.length })),
    passesCount: r.passes.length,
  };
}

async function tabWalk(page, maxTabs) {
  await page.evaluate(() => { document.activeElement?.blur?.(); window.scrollTo(0, 0); });
  const steps = [];
  for (let i = 0; i < maxTabs; i++) {
    await page.keyboard.press('Tab');
    await page.waitForTimeout(60);
    const info = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return { tag: 'body' };
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      const labelledby = el.getAttribute('aria-labelledby');
      const lbText = labelledby ? labelledby.split(/\s+/).map((id) => document.getElementById(id)?.textContent?.trim() || '').join(' ').trim() : '';
      const labelEl = el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`) : el.closest('label');
      const name = (el.getAttribute('aria-label') || lbText || labelEl?.textContent || el.getAttribute('alt') ||
        el.innerText || el.getAttribute('title') || el.getAttribute('placeholder') || el.value || '').toString().trim().replace(/\s+/g, ' ').slice(0, 80);
      const outline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0 && cs.outlineColor !== 'rgba(0, 0, 0, 0)';
      const shadow = cs.boxShadow && cs.boxShadow !== 'none';
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const hit = (cx >= 0 && cy >= 0 && cx <= innerWidth && cy <= innerHeight) ? document.elementFromPoint(cx, cy) : null;
      const obscured = hit ? !(el === hit || el.contains(hit) || hit.contains(el)) : null;
      let sel = el.tagName.toLowerCase();
      if (el.id) sel += `#${el.id}`; else if (el.classList.length) sel += '.' + [...el.classList].slice(0, 2).join('.');
      return {
        tag: el.tagName.toLowerCase(), role: el.getAttribute('role'), type: el.getAttribute('type'), name, selector: sel,
        focusIndicatorHeuristic: outline || shadow ? 'likely-visible' : 'possibly-invisible',
        obscuredHeuristic: obscured, inViewport: hit !== null,
        box: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
      };
    });
    steps.push(info);
    if (info.tag === 'body' && i > 0) break; // wrapped around to the start
  }
  // Trap heuristic: last 12 steps cycle through <= 3 distinct elements while more were available earlier.
  const tail = steps.slice(-12).map((s) => s.selector + '|' + s.name);
  const possibleTrap = steps.length >= maxTabs && new Set(tail).size <= 3;
  return {
    steps,
    possibleTrap,
    invisibleFocusCount: steps.filter((s) => s.focusIndicatorHeuristic === 'possibly-invisible').length,
    obscuredCount: steps.filter((s) => s.obscuredHeuristic === true).length,
    note: 'Focus-visibility and obscured checks are heuristics; verify visually with the screenshots or manually.',
  };
}

async function smallTargets(page) {
  return page.evaluate(() => {
    const sel = 'a[href], button, input:not([type=hidden]), select, textarea, [role=button], [role=link], [role=checkbox], [role=radio], [role=switch], [role=tab], [role=menuitem], [tabindex]:not([tabindex="-1"])';
    const out = [];
    for (const el of document.querySelectorAll(sel)) {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      if (r.width === 0 || r.height === 0 || cs.visibility === 'hidden' || cs.display === 'none') continue;
      if (el.closest('p, li') && el.tagName === 'A' && cs.display === 'inline') continue; // inline links are exempt
      if (r.width < 24 || r.height < 24) {
        out.push({ tag: el.tagName.toLowerCase(), text: (el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 40),
          w: Math.round(r.width), h: Math.round(r.height), id: el.id || null, cls: [...el.classList].slice(0, 3).join(' ') });
      }
    }
    return { count: out.length, items: out.slice(0, 50),
      note: 'Candidates for SC 2.5.8; the spacing exception may still make some compliant.' };
  });
}

// SC 1.4.12: inject the text-spacing override and look for text that gets clipped.
async function textSpacing(page) {
  const before = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.addStyleTag({ content: `* { line-height: 1.5 !important; letter-spacing: .12em !important; word-spacing: .16em !important; }
    p { margin-bottom: 2em !important; }` });
  await page.waitForTimeout(200);
  const res = await page.evaluate(() => {
    const clipped = [];
    for (const el of document.querySelectorAll('body *')) {
      if (!el.innerText || !el.innerText.trim()) continue;
      const cs = getComputedStyle(el);
      const hides = cs.overflow === 'hidden' || cs.overflowY === 'hidden' || cs.overflowX === 'hidden' || cs.textOverflow === 'ellipsis';
      if (hides && (el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 2)) {
        clipped.push(el.tagName.toLowerCase() + (el.id ? '#' + el.id : el.classList.length ? '.' + [...el.classList].slice(0, 2).join('.') : ''));
        if (clipped.length >= 20) break;
      }
    }
    return { clippedCandidates: clipped, scrollHeightAfter: document.documentElement.scrollHeight };
  });
  return { scrollHeightBefore: before, ...res, note: 'Elements with overflow hidden/ellipsis whose content grew past their box after the override; check the text-spacing screenshot.' };
}

// SC 2.3.3 / 2.2.2: do animations keep running when the user asks for reduced motion?
async function motionCheck(page) {
  const count = () => page.evaluate(() => {
    const anims = document.getAnimations ? document.getAnimations() : [];
    const running = anims.filter((a) => a.playState === 'running');
    const infinite = running.filter((a) => a.effect?.getTiming?.().iterations === Infinity).length;
    const media = [...document.querySelectorAll('video, audio')].filter((m) => !m.paused).length;
    return { running: running.length, infinite, playingMedia: media };
  });
  const normal = await count();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.waitForTimeout(500);
  const reduced = await count();
  await page.emulateMedia({ reducedMotion: null });
  return { normal, reduced,
    ignoresReducedMotion: reduced.running > 0 && reduced.running >= normal.running * 0.8,
    note: 'Counts CSS/Web Animations and playing media; JS-driven (requestAnimationFrame) animation is not detected.' };
}

async function visionDeficiencyShot(ctx, page, file, type) {
  try {
    const client = await ctx.newCDPSession(page);
    await client.send('Emulation.setEmulatedVisionDeficiency', { type });
    await page.screenshot({ path: file, fullPage: true });
    await client.send('Emulation.setEmulatedVisionDeficiency', { type: 'none' });
    await client.detach();
    return true;
  } catch { return false; }
}

// Sideways scrolling at the width the page has now, and content that is cut off where no scrolling reaches it.
// ponytail: the box of an element that holds text of its own or is a control, not the glyphs, so padding that
// sticks out counts too; and a carousel that clips its slides is reported like a popover. The orchestrator looks.
const measureWidth = (page) => page.evaluate(() => {
  const de = document.documentElement;
  const overflow = Math.max(0, de.scrollWidth - de.clientWidth);
  // a right-to-left page scrolls to the left, so what lies left of its start can be reached
  const rtl = [de, document.body].some((el) => getComputedStyle(el).direction === 'rtl');
  const control = 'a[href], button, input:not([type=hidden]), select, textarea, [role=button], [role=link], [role=menuitem], [role=tab]';
  const name = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : el.classList.length ? '.' + [...el.classList].slice(0, 2).join('.') : '');
  const culprits = [], offscreen = [], cut = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width <= 0) continue;
    if (overflow > 1 && culprits.length < 15 && r.right > de.clientWidth + 1 && !el.closest('table, pre, [role=grid]')) culprits.push(name(el));
    const left = Math.round(r.left + scrollX), top = Math.round(r.top + scrollY);
    const right = Math.round(r.right + scrollX), bottom = Math.round(r.bottom + scrollY);
    // partly outside: wholly outside is how a skip link or an off-canvas drawer waits, and 1 pixel is a visually hidden label
    const partly = bottom > 1 && (rtl || right > 1) && ((!rtl && left < -1) || top < -1);
    if (!partly || r.height <= 0 || cut.some((c) => c.contains(el))) continue;
    if (!el.matches(control) && ![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
    if (el.checkVisibility && !el.checkVisibility({ opacityProperty: true, visibilityProperty: true })) continue;
    cut.push(el);
    if (offscreen.length < 15) offscreen.push({ element: name(el), left, top, right, bottom,
      text: (el.getAttribute('aria-label') || el.innerText || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 40) });
  }
  return { viewportWidth: innerWidth, horizontalOverflowPx: overflow, culprits, offscreenCount: cut.length, offscreen };
});

async function runActions(page, actions) {
  for (const a of actions || []) try {
    if (a.goto) await page.goto(a.goto, { waitUntil: 'load', timeout: 45000 });
    else if (a.click) await page.click(a.click, { timeout: 10000, force: !!a.force });
    else if (a.type || a.fill) {
      const sel = a.type || a.fill;
      await page.locator(sel).click({ timeout: 10000, force: !!a.force });
      await page.locator(sel).pressSequentially(String(a.value ?? ''), { delay: 40 });
    }
    else if (a.press) await page.keyboard.press(a.press);
    else if (a.wait) await page.waitForTimeout(a.wait);
  } catch (e) { throw new Error(`${String(e).split('\n')[0]} in ${JSON.stringify(a)}`); }   // which action, for the one who fixes it
}

async function scanUrl(browser, url, opts, state) {
  const slug = state ? state.name.replace(/[^a-z0-9]+/gi, '-') : slugify(url);
  const base = path.join(opts.out, slug);
  const viewport = state?.viewport || { width: opts.width, height: opts.height };
  const ctxOpts = { viewport, storageState: opts.storageState, bypassCSP: true };
  const result = { url, state: state?.name, actions: state?.actions, viewport, scannedAt: new Date().toISOString(), errors: {}, stateReached: true };
  const safe = async (name, fn, fallback = null) => {
    try { return await fn(); } catch (e) { result.errors[name] = String(e).split('\n')[0]; return fallback; }
  };
  // load the URL and apply the state's actions; gives the reason when they fail instead of aborting
  const reach = async (page) => {
    await page.goto(url, { waitUntil: 'load', timeout: 45000 });
    await settle(page);
    if (!state?.actions?.length) return null;
    try { await runActions(page, state.actions); await settle(page); return null; }
    catch (e) { return String(e).split('\n')[0]; }
  };
  // at the state's own viewport a failure means the state was not scanned at all
  const reachOwn = async (page) => {
    const why = await reach(page);
    if (why) { result.stateReached = false; result.errors.actions = why; }
  };
  // a fresh load at another width, as a zoomed or a narrow window gives it
  const atWidth = async (width) => {
    // not reached at its own viewport: another width would only wait out the same timeout
    if (!result.stateReached) return { viewportWidth: width, reached: false, reason: result.errors.actions };
    const c = await browser.newContext({ ...ctxOpts, viewport: { width, height: 800 } });
    try {
      const p = await c.newPage();
      const why = await reach(p);
      if (why) return { viewportWidth: width, reached: false, reason: why };
      const m = await measureWidth(p);
      await safe(`shot${width}`, () => p.screenshot({ path: `${base}.${width}.png`, fullPage: true }));
      return m;
    } finally { await c.close(); }
  };

  // Dark scheme first, in its own context: axe must see a page that loaded in that scheme.
  const dark = await browser.newContext({ ...ctxOpts, colorScheme: 'dark' });
  const pd = await dark.newPage();
  await reachOwn(pd);
  result.axeDark = await safe('axeDark', () => axeScan(pd), { violations: [], incomplete: [], passesCount: 0 });
  await safe('darkShot', () => pd.screenshot({ path: `${base}.dark.png`, fullPage: true }));
  await dark.close();

  const ctx = await browser.newContext({ ...ctxOpts, colorScheme: 'light' });
  const page = await ctx.newPage();
  await reachOwn(page);
  result.title = await page.title();
  result.lang = await page.evaluate(() => document.documentElement.lang || null);
  result.axe = await safe('axe', () => axeScan(page), { violations: [], incomplete: [], passesCount: 0 });   // light scheme
  const own = await safe('width', () => measureWidth(page));   // before the tab walk moves focus and scrolls
  result.targets = await safe('targets', () => smallTargets(page), { count: 0, items: [] });
  await safe('screenshot', () => page.screenshot({ path: `${base}.default.png`, fullPage: true }));
  await safe('ariaSnapshot', async () => fs.writeFile(`${base}.aria.yml`, await page.locator('body').ariaSnapshot()));
  result.tabWalk = await safe('tabWalk', () => tabWalk(page, opts.tabs), { steps: [], invisibleFocusCount: 0, possibleTrap: false, obscuredCount: 0 });
  result.motion = await safe('motion', () => motionCheck(page), { ignoresReducedMotion: null });
  result.visionDeficiencyScreenshot = await visionDeficiencyShot(ctx, page, `${base}.deuteranopia.png`, 'deuteranopia');

  await safe('forcedColorsShot', async () => {
    await page.emulateMedia({ forcedColors: 'active' });
    await page.screenshot({ path: `${base}.forced-colors.png`, fullPage: true });
    await page.emulateMedia({ forcedColors: 'none' });
  });
  result.textSpacing = await safe('textSpacing', () => textSpacing(page), { clippedCandidates: [] });
  await safe('textSpacingShot', () => page.screenshot({ path: `${base}.text-spacing.png`, fullPage: true }));
  await ctx.close();

  const r320 = await safe('reflow', () => atWidth(320), { viewportWidth: 320 });
  result.reflow = { ...r320, fails: r320.horizontalOverflowPx === undefined ? null : r320.horizontalOverflowPx > 1,
    note: 'Data tables, maps and code blocks may legitimately scroll (SC 1.4.10 exception).' };
  result.widths = own ? [own] : [];
  for (const w of opts.widths.filter((x) => x !== viewport.width)) {
    const m = await safe(`width${w}`, () => atWidth(w));
    if (m) result.widths.push(m);
  }
  const measured = [result.reflow, ...result.widths];
  result.offscreenNote = 'offscreen lists text and controls whose box lies partly left of or above the start of the page: '
    + 'no scrolling reaches that part. A heuristic: a carousel that clips its slides looks the same.';

  await fs.writeFile(`${base}.json`, JSON.stringify(result, null, 2));
  return {
    url, state: state?.name, stateReached: result.stateReached,
    axeViolations: result.axe.violations.length, axeNodes: result.axe.violations.reduce((n, v) => n + v.nodeCount, 0),
    axeViolationsDark: result.axeDark.violations.length,
    rules: Object.fromEntries(result.axe.violations.map((v) => [v.id, v.nodeCount])),
    rulesDark: Object.fromEntries(result.axeDark.violations.map((v) => [v.id, v.nodeCount])),
    invisibleFocus: result.tabWalk.invisibleFocusCount, possibleTrap: result.tabWalk.possibleTrap,
    reflowFails: result.reflow.fails, smallTargets: result.targets.count,
    offscreenAt: [...new Set(measured.filter((m) => m.offscreenCount).map((m) => m.viewportWidth))],
    notReachedAt: [...new Set(measured.filter((m) => m.reached === false).map((m) => m.viewportWidth))],
    textSpacingClipped: result.textSpacing.clippedCandidates.length, ignoresReducedMotion: result.motion.ignoresReducedMotion,
    errors: Object.keys(result.errors),
  };
}

async function launch(opts) {
  try {
    return await chromium.launch(opts.channel ? { channel: opts.channel } : {});
  } catch (e) {
    if (!opts.channel && /Executable doesn't exist|browserType.launch/.test(String(e))) {
      console.error('Playwright Chromium not installed for this version; retrying with the installed Google Chrome (channel "chrome").');
      return chromium.launch({ channel: 'chrome' });
    }
    throw e;
  }
}

async function sitemapUrls(url, max, seen = new Set()) {
  const out = [];
  let xml;
  try { xml = await (await fetch(url)).text(); } catch (e) { console.error(`sitemap ${url}: ${e}`); return out; }
  const locs = [...xml.matchAll(/<loc>\s*([^<\s]+)\s*<\/loc>/g)].map((m) => m[1]);
  const isIndex = /<sitemapindex/i.test(xml);
  for (const loc of locs) {
    if (out.length >= max) break;
    if (seen.has(loc)) continue;
    seen.add(loc);
    if (isIndex || /sitemap[^/]*\.xml$/i.test(loc)) out.push(...await sitemapUrls(loc, max - out.length, seen));
    else out.push(loc);
  }
  return out.slice(0, max);
}

const opts = parseArgs(process.argv.slice(2));
await fs.mkdir(opts.out, { recursive: true });
if (opts.sitemap) {
  const found = await sitemapUrls(opts.sitemap, opts.maxPages);
  console.error(`sitemap: ${found.length} URLs (max ${opts.maxPages})`);
  for (const u of found) if (!opts.urls.includes(u)) opts.urls.push(u);
}
const browser = await launch(opts);
const summary = [];
const jobs = opts.urls.map((url) => ({ url }));
if (opts.steps) {
  const states = JSON.parse(await fs.readFile(opts.steps, 'utf8'));
  for (const st of states) jobs.push({ url: st.url, state: st });
}
for (const job of jobs) {
  try {
    const s = await scanUrl(browser, job.url, opts, job.state);
    summary.push(s);
    console.log(JSON.stringify(s));
  } catch (e) {
    summary.push({ url: job.url, state: job.state?.name, error: String(e) });
    console.error(`Failed ${job.state?.name || job.url}: ${e}`);
  }
}
await browser.close();
await fs.writeFile(path.join(opts.out, 'summary.json'), JSON.stringify(summary, null, 2));
