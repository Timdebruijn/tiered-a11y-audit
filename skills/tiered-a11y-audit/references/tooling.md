# Automated and semi-automated checks

Automated tools find only a minority of WCAG issues (missing names, contrast of plain text, invalid ARIA, missing lang/title). They cannot judge alt-text quality, focus order logic, meaningful sequence, error-message quality, or whether a flow is usable. Use them as input for the experts.

## Order of preference

1. **What the project already has.** Run its lint script and tests first. Collect a11y-rule output (and count suppressions — `detect_stack.py` lists them).
2. **Framework compilers/dev tools.** `svelte-check` (a11y warnings), Astro dev-toolbar audit, `ng lint` with template a11y rules, `ember-template-lint`.
3. **Runtime scan** (needs a running app): `scripts/axe_scan.mjs`.
4. **Built output** for static sites: `pa11y-ci` or the axe scan against a local static server; `html-validate` for structure.

Never add dependencies to the project's `package.json` without asking. For the runtime scan, use a throwaway directory and ask before installing. Be precise about what the install is: two npm packages, and — unless an installed Google Chrome or Edge is used via `--channel` — a ~150 MB Playwright Chromium download that must match the Playwright version. Prefer the system browser; the script retries with `channel: 'chrome'` on its own when Playwright's Chromium is missing.

## Preflight and workspace set-up (Phases 0 and 1)

```bash
python3 "SKILL_DIR"/scripts/preflight.py <repo-root>                              # reads only
python3 "SKILL_DIR"/scripts/preflight.py <repo-root> --start [--ignore all|report]
```

The first form writes nothing and prints: git repository yes, no, or unknown with the reason (git missing, or git refusing the folder); whether `.a11y-audit/` is ignored, asked of git for a findings file, a screenshot and the stack profile, so `yes` means all three and `partly` means some would be committed (a global ignore file counts, a negated rule does not); the state of the workspace (none, a finished audit, an unfinished run, or not a plain directory); the number of project-owned UI files with the audit size it suggests; run scripts; node; an installed browser; a scratch directory under the system's temp folder; whether a person is there to answer (from `CLAUDE_CODE_SESSION_ATTENDED`, which Claude Code sets to 1 in an interactive session and to 0 in print mode; any other value reads as unknown); and the detector's output.

The second form creates the workspace and writes `stack-detect.md`. A workspace with a `REPORT.md` is a finished audit: everything in it except `report-labels.<code>.json` moves into `previous/`, and an existing `previous/` becomes `previous-<timestamp>/`. A workspace without a `REPORT.md` is a run in progress and stays; `--fresh` moves it aside too. A workspace that is a file or a symbolic link is refused with exit 2.

`--ignore all` appends `.a11y-audit/` to `.gitignore`, `--ignore report` appends `.a11y-audit/*` with exceptions for `REPORT.md` and `coverage.md`. It only appends, in the file's own line endings, and adds a line once. It adds nothing when a line already ignores the whole folder, says so when that makes `report` impossible, and leaves a symlinked `.gitignore` alone. `--ignore` and `--fresh` are refused without `--start`.

The browser check knows a fixed list of names and the macOS application folder, so a browser installed elsewhere reads as not found. `python3 scripts/test_preflight.py` checks all of this.

## Running `scripts/axe_scan.mjs`

```bash
# A throwaway directory — the session scratchpad if the harness has one, else the one preflight.py offered.
# It is the scratch dir for every helper script of this audit; name it in the stack profile.
mkdir -p "$SCRATCH" && cd "$SCRATCH"
npm init -y >/dev/null
npm i playwright @axe-core/playwright
cp "SKILL_DIR"/scripts/axe_scan.mjs .     # must sit next to node_modules: Node resolves ESM imports from the script's directory
# either use the installed browser:   --channel chrome     (or msedge)
# or download Playwright's own:        npx playwright install chromium
node ./axe_scan.mjs \
  --out <repo>/.a11y-audit/automated --channel chrome --tabs 60 \
  --steps states.json \
  http://localhost:3000/ http://localhost:3000/login http://localhost:3000/search?q=test
```

`states.json` covers views that have no URL of their own (tabs, wizard steps, open dialogs) — every key view should get the full battery:

```json
[
  { "name": "health-tab", "url": "http://localhost:3000/", "actions": [{ "click": "button[data-t=health]" }, { "wait": 400 }] },
  { "name": "search-overlay", "url": "http://localhost:3000/", "actions": [{ "press": "Slash" }, { "type": "#search-query", "value": "heliograph" }, { "wait": 500 }] },
  { "name": "mobile-menu", "url": "http://localhost:3000/", "viewport": { "width": 390, "height": 800 }, "actions": [{ "click": "#menu-button", "force": true }] }
]
```

Action objects, exact shapes: `{"click": "<selector>"}` (add `"force": true` when Playwright calls an element invisible, e.g. inside a `hidden md:flex` wrapper — or open it with `press` instead, which is often more reliable), `{"type": "<selector>", "value": "x"}` types real keystrokes so key-event listeners fire (`fill` is an alias that does the same; plain `page.fill()` would set the value without key events and make search-as-you-type look broken), `{"press": "Slash"}`, `{"wait": 400}`, `{"goto": "<url>"}`. `"viewport"` per state reaches mobile-only UI. A state whose actions fail is still scanned and reported with `stateReached: false` and the reason. Actions must not mutate data: open things, don't submit them.

axe runs in both colour schemes, each in its own browser context with a fresh load. Never run axe twice on one page with a colour-scheme flip in between: the second run reports the first scheme's foreground against the second scheme's background and fabricates serious contrast violations near 1.0 to 1 on every page.

The script creates its contexts with `bypassCSP: true`, so apps with a strict Content-Security-Policy (`style-src 'self'`) still get the injected text-spacing stylesheet and axe. Hand-written helpers need the same option. Every check is wrapped individually; a failing check lands in `errors` in the JSON instead of dropping the URL.

Pitfall for hand-written helpers: `AxeBuilder` requires a page from `browser.newContext()` → `newPage()`; a page from `browser.newPage()` throws "Please use browser.newContext()".

Per URL it writes `<slug>.json` with:
- `axe` (light) and `axeDark` (dark scheme): violations (WCAG 2.0/2.1/2.2 A+AA and best-practice tags), with impact, nodes, selectors;
- `tabWalk`: sequence of focused elements (tag, role, accessible name, focus-indicator heuristic, obscured-by-overlay heuristic, bounding box) and trap detection;
- `reflow`: whether horizontal scrolling occurs at 320 CSS px width, with the overflowing elements;
- `targets`: interactive elements smaller than 24×24 CSS px (inline links in text exempted);
- `textSpacing`: elements whose text gets clipped under the SC 1.4.12 override;
- `motion`: running animations/media before and after `reducedMotion: 'reduce'` — `ignoresReducedMotion: true` is a tier-1 finding waiting to happen;
- `<slug>.aria.yml`: the accessibility tree (Playwright ≥ 1.49);
- screenshots: default, 320 px, forced colours, dark scheme, deuteranopia (CDP emulation), text-spacing.

`summary.json` has one line per URL for a quick overview.

Pages behind login: pass `--storage-state auth.json` (a Playwright storage state the user creates by logging in themselves; never type the user's real credentials). For a dev/test app with seeded test accounts the user can point you to them.

## Useful one-off checks with a browser tool

- **Accessibility tree**: `await page.locator('body').ariaSnapshot()` (Playwright ≥ 1.49) gives a YAML outline of roles and names — the best stand-in for "what a screen reader gets".
- **Emulation**: `page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'active', colorScheme: 'dark' })`.
- **Vision deficiency**: via CDP `Emulation.setEmulatedVisionDeficiency({ type: 'deuteranopia' })` (Chromium only).
- **Text spacing** (SC 1.4.12): inject
  ```css
  * { line-height: 1.5 !important; letter-spacing: .12em !important; word-spacing: .16em !important; }
  p { margin-bottom: 2em !important; }
  ```
  and look for clipped/overlapping text.
- **Zoom**: 400 % ≈ viewport 320 px wide; 200 % ≈ 640 px wide (for a 1280 px desktop).

## Pre-computation (run once, before the experts)

```bash
python3 "SKILL_DIR"/scripts/scan_patterns.py <repo> > <repo>/.a11y-audit/pattern-inventory.md
python3 "SKILL_DIR"/scripts/extract_colors.py <repo> > <repo>/.a11y-audit/colour-pairs.md
python3 "SKILL_DIR"/scripts/aria_digest.py <repo>/.a11y-audit/automated > <repo>/.a11y-audit/aria-digest.md
python3 "SKILL_DIR"/scripts/build_briefs.py "SKILL_DIR" <repo>/.a11y-audit --playbook 1,2,16 [--lean]
```

`scan_patterns.py` runs some sixty regex patterns (click handlers on divs, anchors as buttons, images without alt, icon-only buttons, controls without id or label, placeholder-only fields, paste handlers, positive tabindex, live regions, modal-like classes, html without lang, zoom locks, outline removal, infinite animations, px font sizes, setInterval, innerHTML, drag events, suppressed lint rules, and more) over templates, styles and UI scripts, including UIs embedded in source strings, and prints counts plus `file:line` locations with snippets, and a per-file table of headings, titles and lang. Hits are candidates; the expert confirms by opening the file at the line, not by searching again. One pattern depends on the language of the site being audited: link and button texts that say nothing, such as "read more". `scripts/generic_text.py` holds those phrases for English, Dutch, German, French, Spanish, Portuguese and Italian; the row in the inventory names the languages, so a zero on a site in another language means it was not searched. Adding a language is one line in that file.

`extract_colors.py` parses custom properties, SCSS/Less variables and `@theme` blocks (with `light-dark()` and `prefers-color-scheme` handling), resolves `var()` chains, classifies tokens by name and prints every failing foreground/background pair per scheme. A value declared under `:root`, `html`, `body` or `:host` is the base. One declared under a narrower selector or a media query, such as a reader setting on the root (`:root[data-contrast="high"]`), a contrast or print query, or a component, is a variant: the file lists it apart with the value it replaces, and gives the failing pairs that change under it in a table of their own. JS theme objects are not parsed; the visual lens adds those by hand.

`aria_digest.py` reads the `.aria.yml` trees from the runtime scan and prints, per view, landmarks, the heading outline with skipped levels, interactive controls without a name, duplicate button and link names, and unnamed images. It is the authority for "missing accessible name" findings.

`build_briefs.py` concatenates, per agent, its protocol, lens file, the schema, tiering, ownership, the stack profile and only the requested playbook sections into `briefs/<agent>.md`, so a subagent reads one file. Each brief carries only what its reader acts on: a lens gets the criterion rows it owns (who owns the rest is in the per-owner list, which stays, as does the pattern-owner table), nobody gets the persona severity floors or the scoring rubric from `tiering.md`, only the framework-maximizer gets the `kind` and `leverage` rules of the schema, and a persona does not get the rules for `lenses`, `sc_coverage`, `cross_lens_notes` and `fix.ownership`. That takes about 12 percent off the briefs. The cuts are made by heading and by field name. The build stops and says why when a reference no longer has one of those exactly once, or when a criterion's owner is no lens of the run. Headings inside code blocks are not headings. `python3 scripts/test_briefs.py` checks what is cut and what must stay.

## Exports and grading

```bash
python3 "SKILL_DIR"/scripts/export_findings.py <repo>/.a11y-audit --format sarif          # GitHub/GitLab code scanning
python3 "SKILL_DIR"/scripts/export_findings.py <repo>/.a11y-audit --format acr --lang nl  # draft conformance table
python3 "SKILL_DIR"/scripts/export_findings.py <repo>/.a11y-audit --format csv            # tickets, spreadsheets
python3 "SKILL_DIR"/scripts/grade_findings.py <repo>/.a11y-audit/findings/_merged.json <ground-truth.json>
```

The SARIF rule ids are `wcag22/<sc>` with the W3C Understanding page as help URL (derived from the criterion name; verify a link before citing it formally). The grader counts a seeded failure as detected only when a finding cites its criterion, its file and one of its keywords, lists misses, and lists unmatched findings for manual review without deciding whether they are false positives.

## Rendering the draft report (Phase 6)

```bash
python3 "SKILL_DIR"/scripts/render_report_parts.py <repo>/.a11y-audit --lang nl
```

Writes `REPORT.draft.md`, the whole report in the template's shape: every table (within four columns, in words), every finding block with its fields in the fixed order and its values taken from `_merged.json`, the token changes, the structural advice, the to-verify list and the appendices. Places that need judgement or a voice are marked `<!-- WRITE: … -->`; the orchestrator writes the text for those in `report-prose.md`. Also writes `report-ids.json`, and `report-parts.md` with the tables alone. Exits 1, naming the findings, when a finding has no valid tier and would therefore be in no table. `python3 scripts/test_render.py` checks the draft against the template's rules. `--lang` takes any language code: `en` and `nl` ship in `references/report-labels/`, and for another language the first run writes `report-labels.<code>.json` into the workspace to be translated once (keys and `{placeholders}` stay; the script validates the file against the English source). The conformance table of `export_findings.py --format acr` uses the same labels. Finding text goes into the draft as the agents wrote it, which is in the report language, but for three things. A contrast written as `4.5:1` is put into words, outside code spans. The ID a finding had in its findings file (`KBD-003`, `PER-low-vision-001`) becomes the ID the report gives it, wherever an agent wrote it: in a finding, a flow table, a coverage note. Not inside a path or an address, and not in a title of the earlier audit, whose IDs are its own. And a table cell that is cut to length is never cut inside a code span. There is no translation step: a finding in the wrong language is corrected in its findings file and rendered again.

The same command assembles the report. Its first run creates `report-prose.md`, with a line `=== key ===` for each gap of the draft, followed by the gap's hint and any list to choose from, both inside comments. The orchestrator writes its text under those lines. Every later run reads that file, drops what is inside comments, and writes `REPORT.md`: the draft with each gap replaced by the text under its key. An empty section stays a gap marked `WRITE: [key]`, which the linter reports; the optional `legal` section is left out with its heading instead. Every run writes the prose file again, in the order of the report: each section with its hint and its list as the findings are now, and under them the text that was written there, unchanged. Only the first comment under a key is replaced, with the list to choose from when one follows it, since those are the hint; any other comment stays where it is. A prose file that is not saved as UTF-8 is not written again, and the command says so. A gap that is new since the last run (a persona that reported later) gets its section, and an empty section for a gap that is gone is left out. When the hint of a written section is no longer the one its text was written under (a finding moved to another tier, a persona changed its file), the command names that section: read its hint again and check the text. `REPORT.md` is overwritten on every run that has prose to put in, so nothing written into it by hand survives; while every section of the prose file is still empty, an existing `REPORT.md` is left as it is. The command refuses to write the report, with exit 1 and the reason on stderr, when the prose file has a section twice or text in a section that is no gap of this report: a typo in a key, text for something that is gone, or a line of prose that looks like a marker. The prose file is then left exactly as it is. Either would put the wrong text in the report unnoticed. A persona file name with characters a marker line cannot hold gets a key with hyphens in their place.

## Checking the finished report (Phase 6)

```bash
python3 "SKILL_DIR"/scripts/lint_report.py <repo>/.a11y-audit/REPORT.md --workspace <repo>/.a11y-audit
```

Prints one line per problem (`file:line: rule: what`) and exits 1 until the report is clean; exit 2 means it could not run. Rules: `unwritten` (a `WRITE` gap or the draft's header comment), `heading`, `table`, `list`, `symbol`, `bold`, and with `--workspace` also `ids` (every ID of `report-ids.json` present, one block per tier 1 and tier 2 finding, no unknown ID, and outside the full list of appendix C no finding named by the ID of its findings file). Code blocks, code spans and link targets are skipped, so a path or a selector in backticks is never a problem. So is a piece of at most 60 characters between quotation marks, which is text of the interface quoted as the product shows it; a slash in running text is, unless the word is clearly a path. It does not judge abbreviations, all-caps words or whether the prose is true. It works on any Markdown file in any language. Run it on `REPORT-SHORT.md` without `--workspace`, because that file leaves findings out on purpose. `python3 scripts/test_lint.py` holds it against the real draft and against the repository's README.

## Phase checks

```bash
python3 "SKILL_DIR"/scripts/check_phase.py <repo>/.a11y-audit 4
```

Prints one line per gap and exits 1 until phase 3, 4, 5 or 6 is complete; exit 2 means it could not run. Phase 3: the detector output, stack profile, pattern inventory and colour pairs exist, the profile holds no value left at the template's ellipsis, the briefs listed in `briefs/_agents.json` exist and that list (the last file the builder writes) is newer than the profile, a runtime scan left `summary.json`, and `aria-digest.md` is non-empty when the scan captured accessibility trees (an empty digest without trees must be deleted; a scan that died can be run again or its `automated/` folder deleted to go on static-only). Phase 4: every expert in `briefs/_agents.json` wrote readable JSON with a `findings` list and a valid status for each criterion its lenses own, `not-tested` and `n/a` with a reason in `note`, and `_merged.json` is newer than every findings file and `_dedupe.json` and lists no problem to resolve. Phase 5: the four core personas reported (mini mode: the screen reader persona plus one other), the framework-maximizer wrote its file, the merge ran after them, and `coverage.md` exists. Phase 6: `_merged.json` is still newer than every findings file, persona report and `_dedupe.json`, `REPORT.draft.md` is newer than `_merged.json`, a re-audit whose earlier audit reached a merge was merged with `--previous`, and `REPORT.md` passes `lint_report.py` with the report IDs. Freshness is judged by file times, and the check cannot tell this run's files from files an earlier run left in the workspace. From phase 4 on a phase is also incomplete while the merge lists a problem to resolve. That list holds only what needs a decision. On two earlier audits 21 and 25 of its entries were snippets an agent had retyped; since agents are told to copy them, three measured audits ended with an empty list. Whether it was empty at the end of each phase, which is when this check runs, was not measured. `python3 scripts/test_phase.py` walks a mini audit through all four.

## Merging findings

```bash
python3 "SKILL_DIR"/scripts/merge_findings.py <repo>/.a11y-audit --ownership "SKILL_DIR"/references/wcag-ownership.md
```

Run it after the lenses (then again after writing `_dedupe.json` and after dropping false positives), and once more after the personas and the framework-maximizer. It merges duplicates (exact fingerprint + `_dedupe.json`), derives the tier from `visual_impact` (and flags disagreements), lists root-cause clusters (findings citing the same lines), pulls in and normalises persona findings, applies the persona severity floors, attaches leverage points and persona verdicts, and writes `coverage.md` with the 55-criterion matrix, its counts and any owner/cross-lens conflicts. With `--previous <path>` (a re-audit) it also writes `delta.md`: resolved / still open / regressed / new, matched on fingerprint. It is deterministic; doing this by hand costs tokens and introduces errors.

What it has to report comes in two lists, in `_merged.json` as `problems` and `notes` and at the end of `_merged.md` under "Problems to resolve" and "Settled by the merge". A problem needs a decision: a finding or field the merge had to drop, a missing required field, a criterion that is not level A or AA or is absent, a cited file, line or snippet that is not there, a contrast that already passes or a suggested colour that still fails, a proposed tier that contradicts the visual impact, a missing `fix.ownership` (the merge assumes `project`, which is wrong for vendored code), a persona finding in no tier. A note is something the merge settled from data it can look up or by a fixed conversion: a corrected criterion level or contrast ratio, a generated fingerprint or ID, a shape it converted. Snippets are compared with whitespace next to punctuation removed and whitespace between two words kept as one space. A `--previous` path that does not exist or cannot be read is a problem too, in both files and on stderr. A persona's criterion is advisory, so what would be a problem in an expert's finding is settled in a persona's: a criterion that is not level A or AA is left out, a finding without one is kept as an observation outside the coverage matrix, and a place that is not a file ("the contact page") is kept as a place and not looked up. A persona's prose evidence is kept as `observation` and is not looked up as a quote.

## Contrast

`scripts/contrast.py` (pure Python, no deps):

```bash
python3 contrast.py ratio "#767676" "#ffffff"
python3 contrast.py fix "#0a84ff" "#ffffff" --target 4.5          # auto: changes whichever colour needs the smaller shift
python3 contrast.py fix "#ffffff" "#0a84ff" --target 4.5 --adjust bg  # force which side changes
python3 contrast.py batch --target 4.5 < pairs.txt                # lines: "fg bg label…"
python3 contrast.py batch --json < pairs.txt
python3 contrast.py fix "#0a84ff" "#ffffff" --large                # 3:1 for large text / non-text
python3 contrast.py flatten "rgba(0,0,0,0.5)" "#ffffff"           # → #808080, then use ratio/fix
```

`fix` keeps hue (OKLCH), changes lightness (reducing chroma only if needed to stay in sRGB), tries both darker and lighter, and returns the option with the smallest ΔE(OKLab). Semi-transparent colours go through `flatten` first (the result depends on what they sit on, so flatten against each real background).
