---
name: tiered-a11y-audit
description: Full accessibility (a11y) audit of any frontend repository — React, Next.js, Vue, Nuxt, Angular, Svelte, Astro, web components, server-rendered templates (Django, Rails, Laravel, Hugo, Blazor…), React Native, Flutter, or UIs embedded as strings in firmware/source code — producing a three-tier report (1. invisible fixes you can ship today, 2. small non-shocking visual tweaks, 3. everything needed for a "10/10"). Uses parallel expert subagents plus persona subagents simulating people who rely on assistive tech. Use this skill whenever the user asks about accessibility, toegankelijkheid, a11y, WCAG, EN 301 549, European Accessibility Act, a toegankelijkheidsrapport or -verklaring, screen reader support, contrast, keyboard navigation, or wants to know how inclusive/usable their app or site is — even if they only say "check my site for a11y" or "hoe toegankelijk is dit".
---

# Accessibility audit — three-tier report

Produce one evidence-based report that tells a team exactly what to change, ordered by how disruptive the change is:

| Tier | Name | Promise to the team |
|---|---|---|
| 1 | **Invisible improvements** | Ship today. A sighted mouse/touch user with default settings sees no difference. |
| 2 | **Small, non-shocking adjustments** | Visible, but the product is still instantly recognisable. A designer signs off in one sprint. |
| 3 | **The road to a 10** | Everything else: AAA, redesigns, content rewrites, features, user testing, process. |

The tier says *what kind of change* it is, not how severe the problem is. A blocker can be tier 1 (a missing label) and a minor nicety can be tier 3. The precise rules live in `references/tiering.md` — read it before classifying anything.

The value of this skill comes from two things a generic audit misses, so protect them throughout:

1. **Framework-native fixes.** Every fix is written in the idiom of the detected stack and placed at the highest-leverage point (design token, shared component, layout, router hook) — fix once, repair everywhere. Use built-in a11y features of the framework and libraries before hand-rolling anything.
2. **The user's voice.** Persona agents walk the key flows as real AT users would and say what it is actually like. Their task-completion verdicts drive priority.

## Ground rules

- **Read-only by default.** Audit and report; do not edit project code unless the user asks (offer it at the end). The single exception is adding `.a11y-audit/` to `.gitignore`, and only after the user says yes in Phase 1. Never add dependencies to the project or install packages without asking.
- **Evidence or it didn't happen.** Every finding cites file + line, or URL + selector, and a WCAG 2.2 success criterion (or is explicitly marked best practice). Spot-check every blocker/critical finding yourself before it enters the report — subagents sometimes misread code.
- **Be honest about method.** State what was tested statically, what at runtime, what automatically, and what not at all. Personas are simulations by an AI, not a substitute for testing with disabled people; say so in the report and recommend real user testing in tier 3.
- **Never recommend accessibility overlay widgets** (toolbars/plugins that claim to "fix" a site automatically). They do not achieve conformance and often make AT use worse.
- **Report language** = the language the user is talking to you in. Code, selectors and WCAG references stay as-is. The *working* language of all agent files, findings and persona notes is English; only `REPORT.md` and the reply to the user are translated.
- **The runtime is read-only too.** Agents navigate, open and type, but never submit, create, delete or change data — unless the user explicitly offers a disposable instance and says which actions are fine. Put that in every subagent prompt.

## Scripts do the deterministic work

Agents cost tokens and time; scripts cost neither. Everything that is a grep, a parse, a count, a colour calculation or a table is a script in `scripts/`, run once by the orchestrator, and agents start from its output: `detect_stack.py` (stack and tooling), `scan_patterns.py` (every a11y grep), `extract_colors.py` (tokens and failing contrast pairs), `aria_digest.py` (names, headings, landmarks per view), `build_briefs.py` (one briefing file per agent), `merge_findings.py` (merge, tiers, clusters, coverage, persona links, re-audit delta), `render_report_parts.py` (the whole draft report: tables, finding blocks, appendices). If you catch yourself or a subagent doing any of that by hand, stop and use the script.

## Your own output must be accessible

The person running this skill may use a screen reader or text-to-speech, magnification, or have limited energy for reading. Everything you say to them (questions, progress, the final reply, the report) follows these rules, always, not only when someone says they use assistive tech:

- **Answer first, context after.** The first line of any reply is the thing they need (the question, the score, the next step). Never open with what you did.
- **Short.** Questions: one line each, numbered, with the default stated so "ok" is a complete answer. Progress: at most one line per phase, never per tool call. Final reply: at most ~15 lines; the report carries the detail.
- **Predictable structure.** A listener cannot look ahead, so every section has the same shape and every finding has the same fields in the same order. Within a section: one introductory paragraph, then one table or one list, then the detail blocks. Never alternate table, prose, table, prose.
- **Tables: fine, but tidy.** One table per section at most, announced by the sentence before it ("The next table lists the 12 tier-1 findings with ID, title, severity and effort."), at most four columns, the key in the first column, short header words, no empty cells (write "none"), no symbols or emoji as content, and a table is never the only place a fact lives.
- **Readable aloud.** No emoji, arrows, middle dots, slashes or "====" rules in text (write "A and AA", "4.5 to 1", "now 5, after tier 1: 7"); no abbreviations without the full term on first use; no all-caps; headings in a strict hierarchy with no skipped levels; one list level; bold only for a few words.
- **Never paste the report into chat.** Give the path and the essentials.
- If the user says they use a screen reader or asks for brevity, go further: replies of a few lines, questions one at a time, and offer the short report variant.

## Choose the mode first

| Mode | When | What runs |
|---|---|---|
| **Full audit** (default) | "How accessible is this site/app?", a report, a statement, a compliance question about the product | Phases 0–7 with expert and persona subagents |
| **Lean full audit** | Same ask, but the UI is small: ≤ ~25 project-owned UI files (the detector's "Scope" line) or ≤ ~5 views | Same phases, 4 merged expert agents instead of 6 (see Phase 4), the 4 core personas plus triggered ones only on a strong trigger |
| **Mini full audit** | Whole site, but ≤ ~10 project-owned UI files, no forms beyond a search box, at most two interactive widgets (check `pattern-inventory.md`: form controls, modal-like classes, key handlers) | Same phases, 2 merged expert agents (perceive: structure + content + visual; operate: keyboard + dynamic + forms), 2 personas (screen reader + one chosen by the product: low vision for content sites, motor/voice for tools), maximizer post-pass. About a third of the full cost. |
| **Focused review** | One component, page, feature or PR/diff ("check this modal", "review this PR for a11y") | Phase 0, then you apply the relevant expert lenses yourself (read their files, no subagents), one or two personas inline, `contrast.py` for any colour, and a short three-tier answer in chat. Files only if the user wants them. |
| **Re-audit** | `.a11y-audit/` or an older report exists and the user asks what's left, whether fixes worked, or for an update | Full audit; the merge script compares on `fingerprint` and writes `delta.md` (resolved / still open / regressed / new) and the score delta leads the summary |
| **Apply fixes** | The user asks to fix tier 1 (or a specific finding) | Implement from the report, one commit per root cause, add a regression test per fix; re-run the automated scan if available |

The mode is decided after Phase 0 (the detector tells you the UI size and whether there is a UI at all).

## Workspace

Create `.a11y-audit/` in the repo root. It holds screenshots (easily several MB), accessibility trees and code snippets, so it must not land in the user's git history by accident — Phase 0 checks `.gitignore` and Phase 1 asks before writing anything. The workspace is created only after that answer.

```
.a11y-audit/
├── stack-detect.md         # detector output, written by preflight.py --start (Phase 1)
├── stack-profile.md        # shared brief for all agents (end of Phase 3)
├── automated/              # scan output, screenshots, aria trees (Phase 3)
├── pattern-inventory.md    # every a11y grep, done once by script (Phase 3)
├── colour-pairs.md         # colour tokens and failing fg/bg pairs (Phase 3)
├── aria-digest.md          # per view: landmarks, headings, nameless controls (Phase 3, runtime only)
├── briefs/<agent>.md       # one briefing file per subagent (Phase 3)
├── REPORT.draft.md         # generated: the whole report with gaps marked WRITE (Phase 6)
├── report-parts.md         # generated: the tables alone (Phase 6)
├── findings/<agent>.json   # one file per expert agent (Phase 4)
├── findings/_merged.md     # one line per finding + clusters — the brief for personas (Phase 4)
├── findings/_merged.json   # all findings, deduped, tiers derived, persona links (Phases 4–6)
├── findings/_dedupe.json   # your merge decisions: {"CANONICAL": ["DUP", ...]} (Phase 4)
├── coverage.md             # the 55-criterion matrix with conflicts (Phases 4–6)
├── personas/<persona>.md   # one file per persona agent (Phase 5)
├── previous/               # re-audit: the whole earlier audit, moved here by preflight.py --start
├── delta.md                # re-audit: resolved / open / new / regressed (Phase 6)
└── REPORT.md               # the deliverable (Phase 6)
```

`SKILL_DIR` below means the directory containing this SKILL.md. Resolve it to an absolute path (e.g. `~/.claude/skills/tiered-a11y-audit` or the plugin's install path) and quote it everywhere — a plugin path can contain spaces, and subagents cannot guess it.

## Phase 0 — Orient (no questions yet)

Everything here is cheap and needs no input, so do it before asking anything.

1. Run the preflight. It reads only; nothing is written anywhere yet:
   ```
   python3 "SKILL_DIR"/scripts/preflight.py <repo-root>
   ```
   Its first lines answer what Phase 1 needs: whether this is a git repository and whether `.a11y-audit/` is already ignored (then skip question 1), whether an earlier audit is present (then this is a re-audit), the number of project-owned UI files and the audit size that suggests, the run scripts in `package.json`, whether node and an installed browser are available, and a scratch directory outside the repository to offer. Below that comes the detector's output: frameworks, UI/chart/animation libraries, styling, routing (or its absence), i18n, a11y tooling, suppressed a11y lint rules, UIs embedded in source strings, a CSP, and infra templates it ignored.
2. From that output decide: no UI at all → stop and ask what to audit; the "Scope" line gives project-owned UI files (vendored themes and build output excluded): ≤ 10 → mini candidate (confirm after `scan_patterns.py` in Phase 3 shows few interactive widgets), ≤ 25 → lean, otherwise full. Packages listed under "Found only in vendored code" are not the project's stack; read the playbook for the generator or framework the project actually uses. Note the package scripts / compose files / SSG commands that could start a dev server, and whether a browser tool is available in this session (Playwright via a scratch dir, a Playwright or Chrome MCP, or nothing).

## Phase 1 — One message to the user

One message, at most five numbered questions, one line each, each with its default, so that "ok" answers everything. Skip questions the user already answered. Keep the whole message under ~12 lines. Cost line from three real runs: full is 13–15 subagents and 1–1.5 M subagent tokens; lean about 10 subagents and 0.5–0.7 M; mini about 5 and 0.3 M; wall-clock 20–45 minutes for all of them (the orchestrator's own verification takes as long as the agents). Quote the mode you actually propose, not the full-audit numbers. Example (translate into the user's language):

```
I found a React + Vite app with 18 UI files; a lean audit fits (about 7 agents, 15–20 minutes). Questions, defaults in brackets, "ok" accepts all:
1. Add .a11y-audit/ to .gitignore? It holds screenshots and code snippets. [yes, ignore all; or: keep REPORT.md trackable]
2. Runtime: start `npm run dev` myself? [yes; or give me a URL; or static only]
3. Install Playwright + axe in a scratch folder outside the repo (uses your installed Chrome)? [yes]
4. Treat the running app as read-only? [yes; or name a disposable instance and allowed actions]
5. Key flows: overview, graphs, targets editor, alerts, access. [ok]
```

The gitignore line is the one edit this skill makes to a repo, only with this permission (options: `.a11y-audit/` for everything, or `.a11y-audit/*` plus `!.a11y-audit/REPORT.md` and `!.a11y-audit/coverage.md` to keep the report trackable). Mention cost in the first line, not as a paragraph. Only mention legal context (EN 301 549 / EAA / public sector) if the user or the repo brings it up. In question 3 name what the preflight found: the installed browser, or that Playwright downloads one of about 150 MB. Wait for the answer, then set the workspace up in one command, with `--ignore` only if the user agreed to it (`all`, or `report` to keep the report trackable):

```
python3 "SKILL_DIR"/scripts/preflight.py <repo-root> --start [--ignore all|report]
```

It creates `.a11y-audit/`, writes `stack-detect.md`, adds the ignore lines once, and in a re-audit moves the whole earlier audit into `.a11y-audit/previous/` so that none of its files is mistaken for this run's output. Nothing is deleted: an older `previous/` is kept as `previous-<timestamp>/`, and a translated labels file stays where it is.

## Phase 2 — Recon and runtime

1. Read the detected stacks' sections of `references/framework-playbooks.md` — nothing else.
2. Establish what the team may edit: `CLAUDE.md`, contribution docs, design docs, `.gitmodules`, vendor and theme folders. Write the writable directories, the off-limits ones and any policy ("never copy theme templates") into the stack profile — it decides `fix.ownership` for every finding. If the repo documents its own accessibility status (a "0 violations" note, a contrast table, a statement), treat it as a claim to re-measure and report the delta; the owner of such a gate needs to know whether it exists.
3. Locate the leverage points with paths: design tokens/theme and global CSS (focus styles, motion, forced colours); app shell / root layout (`<html lang>`, `<title>`, landmarks, skip link); router or view-switching code; shared components (Button, Link, Icon, Input/Field, Modal, Menu, Tabs, Toast, Table); forms layer (library, validation, error rendering); any announcer/live region; tests, lint, CI.
4. Pick the key flows (3–7): home + primary navigation, the primary task, a form or authentication flow, a content-heavy view, a widget-heavy view. Map each to routes/views/components. For a component library without pages, the flows are the stories/demo pages of the 5–8 most-used components.
5. If agreed, start the dev server as a background process from the repo root, wait until the URL answers (fetch it), and record the command, URL and PID. If it fails, fall back to static-only and say so later in the method section.
6. Create the scratch directory (the session scratchpad if the harness has one, else the one the preflight offered) and, if agreed, install `playwright` and `@axe-core/playwright` there (`references/tooling.md`). Copy `axe_scan.mjs` into it: Node resolves ESM imports from the script's own directory, so a script that stays in the skill folder cannot find the scratch `node_modules`. This directory is the one place for every helper script of the whole audit.

## Phase 3 — Automated baseline, then the shared brief

1. Run the project's own lint/test scripts that carry a11y rules, if any; collect the output.
2. With a runtime: write `states.json` for the key views that have no URL of their own (tabs, wizard steps, dialogs, the mobile menu at a phone viewport — click, type or press to open, never submit; see `references/tooling.md` for the exact action shapes); for a multi-page site add `--sitemap <url>` (default cap 30 pages) instead of listing URLs; then run
   ```
   node "$SCRATCH"/axe_scan.mjs --out <repo>/.a11y-audit/automated --channel chrome --steps states.json <urls…>
   ```
   Read `summary.json`. Automated tools find a minority of real issues — this is input for the experts, not the audit.
3. Pre-compute what every agent would otherwise grep for itself (seconds of script time instead of thirty tool calls per agent):
   ```
   python3 "SKILL_DIR"/scripts/scan_patterns.py <repo> > <repo>/.a11y-audit/pattern-inventory.md
   python3 "SKILL_DIR"/scripts/extract_colors.py <repo> > <repo>/.a11y-audit/colour-pairs.md
   python3 "SKILL_DIR"/scripts/aria_digest.py <repo>/.a11y-audit/automated > <repo>/.a11y-audit/aria-digest.md   # runtime only
   ```
   Skim the three outputs: the inventory's summary table and per-file heading/title/lang table, the failing colour pairs, and the nameless-controls column of the digest. They feed the stack profile's baseline headline.
4. Now write `.a11y-audit/stack-profile.md` following `references/stack-profile-template.md`: mode, runtime (URL, how started), scratch dir, browser tooling available to agents, stack, leverage points, key flows, persona selection, automated-baseline headline, known limits. It is the single brief every subagent reads, so keep it tight, factual and full of paths.
5. Build the briefings, one file per agent, so each subagent reads one file instead of seven (`--lean` for lean mode; `--playbook` takes the section numbers from the stack profile):
   ```
   python3 "SKILL_DIR"/scripts/build_briefs.py "SKILL_DIR" <repo>/.a11y-audit --playbook <sections> [--lean | --mini]
   ```

## Phase 4 — Experts, merge, dedupe, verify

**4a — lenses in parallel.** Spawn the six experts **in a single message** with the Task/Agent tool (general-purpose subagent). In lean mode spawn four, each owning two lens files and both SC sets: structure+content (`semantics-structure` + `content-media`), keyboard+dynamic (`keyboard-focus` + `dynamic-content`), `visual-perception`, `forms-input`. In mini mode spawn two: perceive (structure + content + visual) and operate (keyboard + dynamic + forms). `build_briefs.py --lean` / `--mini` makes the matching briefs; a merged agent writes one findings file with `"lenses": [...]`, and the merge script credits each criterion to its owner regardless of file.

| Agent file | Lens |
|---|---|
| `agents/experts/semantics-structure.md` | HTML semantics, landmarks, headings, accessible names, ARIA correctness, titles, tables |
| `agents/experts/keyboard-focus.md` | Keyboard operability, focus order/visibility/trapping/restoration, APG widget patterns, route focus |
| `agents/experts/visual-perception.md` | Contrast (text + non-text), colour-only cues, resize/reflow/spacing, target size, forced colours, motion |
| `agents/experts/forms-input.md` | Labels, instructions, validation and errors, autocomplete, authentication, pointer/gesture alternatives |
| `agents/experts/dynamic-content.md` | Live regions/status messages, dialogs, toasts, loading, timeouts, SPA navigation announcements |
| `agents/experts/content-media.md` | Alt text, icons/SVG, media alternatives, link text, language, readability, consistency, documents |

Prompt template for each expert (and, with the persona files swapped in, for each persona):

```
You are the <agent> expert in an accessibility audit.
Read first: "<repo>/.a11y-audit/briefs/<agent>.md" — it holds your protocol, lens,
schema, tiering, ownership, the stack profile (runtime URL, browser tool, scratch dir,
skill dir, writable directories, key flows) and the relevant playbook sections.
Then start from "<repo>/.a11y-audit/pattern-inventory.md", "aria-digest.md" and
"colour-pairs.md" as your protocol says; grep only for what they don't cover.
Rules: repo READ-ONLY (no edits, no state-changing git); runtime READ-ONLY (navigate,
open, type; never submit/create/delete) <unless: disposable instance, allowed: …>;
helper scripts only inside the scratch dir named in the profile (Node resolves
imports from the script's own directory); don't npm install. Work in English.
Stay within ~40 tool calls. Write "<repo>/.a11y-audit/findings/<agent>.json" and
reply with at most 8 lines (counts per severity, top 3 issues).
```

Every path the agent needs beyond those two is in the stack profile (skill dir, scratch dir, runtime, browser tool), so the prompt stays short and the plugin path with spaces appears once.

Subagents may run on a smaller/faster model if the tool allows choosing one; your own verification is where the strongest model matters. If subagents are unavailable (plain chat), run each lens yourself sequentially, writing the same files, and say so in the method section.

Tell the user in one line that the experts have started and roughly how long it takes; nothing more until they finish.

**4b — merge and dedupe.** When all lenses are done:

```
python3 "SKILL_DIR"/scripts/merge_findings.py <repo>/.a11y-audit --ownership "SKILL_DIR"/references/wcag-ownership.md
```

It writes `_merged.json`, `_merged.md` (one line per finding plus root-cause clusters — findings citing the same lines), and `coverage.md`; derives tiers from `visual_impact`; flags schema problems and owner conflicts. It also checks every finding's claims against what a script can look up: the cited file, lines and snippet exist (pass `--repo <dir>` when the audit scope is a subdirectory), the criterion is a level A or AA one with its name and level taken from the ownership table, and stated contrast ratios are recomputed and corrected. Everything that does not hold is listed under "Problems to resolve" at the end of `_merged.md`. Resolve that list first, by fixing the findings file or dropping the finding: a citation that does not exist is not evidence, and a finding with only a triple-A criterion or none at all is invisible to the coverage matrix. Then decide the duplicates: for each cluster pick the canonical finding (the pattern owner's, see `references/wcag-ownership.md`), write `findings/_dedupe.json` — `{"DYN-004": ["KBD-003", "SEM-010"], …}` — and re-run the script. Expect a third to a half of raw findings to collapse.

**4c — verify the top before anyone builds on it.** Open the cited code or page for every blocker and critical finding (there are rarely more than ten). Check them against the false-positive list in `agents/experts/_protocol.md`. Drop or downgrade what doesn't hold up. Anything you find yourself while verifying goes into `findings/orchestrator.json` (prefix `ORC`, same schema) — not into the report by hand. Re-run the script. Personas and the maximizer must not inherit a false positive.

## Phase 5 — Personas and framework-maximizer, in parallel

Spawn, **in one message**: the personas and `agents/experts/framework-maximizer.md`. They read the same deduplicated `_merged.md` and don't depend on each other.

- Personas (protocol: `agents/personas/_protocol.md`; same prompt template, persona file instead of lens file, output `.a11y-audit/personas/<persona>.md`): they walk the key flows **first** — at runtime when there is one, that is not optional — and read `_merged.md` only afterwards to reconcile (`confirmed` = seen in their own walk, `cites`, `disputed`). Full and lean: always the four core personas, the others on their trigger. Mini: screen reader plus one (low vision for content sites, motor/voice for tools).

| Persona file | Run when |
|---|---|
| `agents/personas/screen-reader-user.md` | always |
| `agents/personas/low-vision-user.md` | always |
| `agents/personas/motor-voice-user.md` | always |
| `agents/personas/cognitive-user.md` | always |
| `agents/personas/colour-blind-user.md` | colour carries meaning: charts, status, validation, maps, tags |
| `agents/personas/deaf-user.md` | audio/video, voice/phone-only support, audio notifications |
| `agents/personas/vestibular-user.md` | animations, parallax, carousels, autoplay, transitions |
| `agents/personas/older-novice-user.md` | consumer- or citizen-facing products (default on unless clearly dev/internal tooling) |

- Framework-maximizer: attaches leverage points to existing findings (which token, base component, hook or config fixes several at once) and files new findings only for tooling, CI, suppressions and unused platform features.

One progress line when they start, none in between. When all are done, run the merge script once more. It links the persona verdicts, pulls in their new `PER-*` findings (normalised, schema deviations flagged), attaches the maximizer's leverage entries to their targets and lists them ranked (that list is the structural-advice section; the entries are not findings and never go into `_dedupe.json`), and applies the severity floor: a key flow **failed** → the findings it names become blocker; **only with help** → critical. Coverage statuses that rest only on persona findings show as "fail (unverified)" until Phase 6 confirms them.

## Phase 6 — Synthesis and report

1. **Final verification**: persona-new findings and every *serious* finding that is cheap to reproduce at runtime (a click and a look — that is where bugs that hurt everyone surface). Keep the severity floors unless a persona's trace doesn't hold up. Resolve the conflicts listed in `coverage.md`.
2. **Tiers**: the script derived them from `visual_impact`; check them against `references/tiering.md` and overrule only with a stated reason. Where a problem has both a tier-1 and a tier-2 fix (icon-only link: accessible name now, visible text later), split it into two linked findings.
3. **Colours**: the visual lens should already have run `scripts/contrast.py` on every contrast finding; fill any gap (`fix` keeps the hue and reports ΔE) so every tier-2 colour change has before/after values and a ratio.
4. **Re-audit only**: run the merge script with `--previous <repo>/.a11y-audit/previous` to get `delta.md` (resolved / still open / regressed / new by fingerprint); lead the summary with the delta and the score change.
5. **Score** now and after each tier with the rubric in `references/tiering.md`.
6. **Generate the draft, then fill it**:
   ```
   python3 "SKILL_DIR"/scripts/render_report_parts.py <repo>/.a11y-audit --lang <language code of the report>
   ```
   It writes `REPORT.draft.md`: the whole report in the shape of `references/report-template.md`, with every table, every finding block (fields in the fixed order, values straight from `_merged.json`), the proposed token changes, the structural-advice table, the to-verify list and the appendices. `report-ids.json` maps report IDs (`T1-01`…) to source findings. The fixed words of the report (headings, field labels, severity words, the sentences that announce tables) come from a labels file. English and Dutch ship with the skill. For any other language the first run stops and writes `report-labels.<code>.json` into the workspace: translate its values once, keeping the keys and every `{placeholder}`, and run the command again; the script checks the file before it uses it. If it exits non-zero, some findings are in no tier and so in no table: fix their `visual_impact` and merge again before going on. Copy the draft to `.a11y-audit/REPORT.md` and do only two things. First, write what is marked `<!-- WRITE: … -->`: the "In short" and summary prose with the score, the grouping of tier 3, the personas' voice, the advice paragraph, the method summary. Second, translate the finding text into the user's language, keeping IDs, code, selectors, paths and numbers as they are. Never retype, drop or shorten a table or a finding block; edit in place. To reorder within a tier by (severity × reach) ÷ effort, move a block and its table row together and keep the IDs. Delete the comment at the top of the draft. Then check the result:
   ```
   python3 "SKILL_DIR"/scripts/lint_report.py <repo>/.a11y-audit/REPORT.md --workspace <repo>/.a11y-audit
   ```
   It lists, with line numbers, every gap still marked `WRITE`, every report ID that was dropped, duplicated or invented, and every break of the read-aloud rules above that a script can decide: table width and empty cells, a table without an announcing sentence, skipped heading levels, nested lists, emoji, arrows, slashes in running text, ratios written with a colon, long bold. Fix what it lists and run it again. The report is done when it exits 0, not before; do not reply to the user with a report that fails it.
7. **Reply** in at most ~15 plain lines, in this order: the score in words ("now 5 out of 10; after tier 1: 7; after tiers 1 and 2: 8; ceiling 9"), any blocker or `affects_all_users` finding in one line each, the top 5 actions as a numbered list of one line each, the counts per tier in one sentence, the report path, and the method caveat in one sentence. No table, no symbols. If the user uses a screen reader or asked for brevity, stop after the top 5 and offer the rest on request.

## Phase 7 — Wrap up and offer next steps

Stop the dev server you started. Leave the scratch directory and `.a11y-audit/` in place (the next run reuses both). If `.a11y-audit/` is still not gitignored, say so once more in the reply, with the two ignore options.

Exports, on request or when the context calls for them (a team that works from tickets, a CI pipeline, a public-sector or EAA obligation): `python3 "SKILL_DIR"/scripts/export_findings.py <repo>/.a11y-audit --format sarif|acr|csv [--lang <code>]`. SARIF feeds GitHub code scanning and GitLab; the ACR table is a *draft* conformance table from the coverage matrix (Supports / Partially / Does Not / Not Applicable / Not Evaluated) for whoever signs a VPAT, ACR or accessibility statement; CSV is for spreadsheets and ticket import. Say clearly that the ACR draft is not a statement until a human has reviewed it. Then offer, without doing it unasked: apply all tier-1 fixes on a branch, one commit per root cause, with regression tests (`jest-axe`/`vitest-axe`/Playwright+axe/`getByRole` assertions); add a11y lint and a CI gate; turn tier-2 colour changes into a token PR with before/after screenshots for the designer; draft an accessibility statement once tiers 1–2 are done.

## Reference files

- `references/tiering.md` — tier definitions, decision test, examples, edge cases, scoring rubric. **Read before classifying.**
- `references/finding-schema.md` — JSON format for findings (all agents use it), including `fingerprint`, `visual_impact` and `sc_coverage`.
- `references/wcag-ownership.md` — which expert owns which WCAG 2.2 A/AA criterion; source of the coverage matrix.
- `references/stack-profile-template.md` — shape of the shared brief.
- `references/framework-playbooks.md` — per-stack native a11y features, pitfalls and idiomatic fixes (read only the detected stacks; has a table of contents).
- `references/tooling.md` — automated and semi-automated checks, how to run them, their limits.
- `references/report-template.md` — the exact report structure.
- `scripts/detect_stack.py` — stack and tooling detector (also finds UIs embedded in source-code string literals).
- `scripts/scan_patterns.py` — pattern inventory: every a11y grep over templates, styles and UI scripts, with locations.
- `scripts/preflight.py` — Phase 0 in one read-only command (git and ignore status, earlier audit, audit size, tools, detector output); with `--start` the workspace set-up, re-audit rotation and ignore lines.
- `scripts/extract_colors.py` — colour tokens per scheme and failing foreground/background pairs.
- `scripts/aria_digest.py` — per-view digest of the accessibility trees: landmarks, headings, nameless controls, duplicate names.
- `scripts/build_briefs.py` — one briefing file per subagent.
- `scripts/merge_findings.py` — merges findings, derives tiers, clusters root causes, links persona verdicts, builds the coverage matrix, re-audit delta.
- `scripts/render_report_parts.py` — generates the draft report (every table, finding block and appendix, with consistent report IDs and the gaps for prose marked).
- `scripts/lint_report.py` — checks the finished report: no gap left, every report ID present once, the read-aloud rules kept.
- `scripts/export_findings.py` — SARIF 2.1.0, draft ACR conformance table, CSV.
- `scripts/grade_findings.py` — detection rate, misses and unmatched findings against a ground-truth file (used by the evals).
- `scripts/contrast.py` — WCAG contrast ratio, minimal hue-preserving fixes, alpha flattening, palette batch mode.
- `scripts/axe_scan.mjs` — Playwright + axe runtime scan with keyboard walk, reflow, text-spacing, reduced-motion and target-size checks, plus forced-colours / dark / colour-blind screenshots.
- `evals/` (at the repository root, beside this skill's parent `skills/`) — four test cases: a fixture site with seeded issues (with `ground-truth.json` for `grade_findings.py`, which gives a detection rate), a focused review, a non-frontend repo, and a themed site with an off-limits submodule. Run them from the repository root with `claude plugin eval . --scaffold --allow-tools Bash Write Edit`: the cases need those three tools and they are stripped unless granted on the command line. Or run by hand.
- `README.md`, `CHANGELOG.md` — for the repository; not read during a run.
