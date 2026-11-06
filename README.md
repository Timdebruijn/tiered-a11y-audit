# tiered-a11y-audit

Three-tier accessibility audits for [Claude Code](https://docs.claude.com/en/docs/claude-code): invisible fixes you can ship today, small visual tweaks a designer signs off in one sprint, and the road to a 10.

Most accessibility audits produce a long list sorted by WCAG criterion. Teams read it, nod, and ship nothing, because every item looks like a design decision. This skill sorts by **how disruptive the fix is**:

| Tier | Promise to the team |
|---|---|
| 1. Invisible improvements | A sighted mouse user with default settings sees no difference. Accessible names, semantics, focus management, announcements, reduced-motion and forced-colours support, tooling. Ship today. |
| 2. Small, non-shocking adjustments | Visible, but the product is instantly recognisable: a lightness-only shift of a brand colour (computed, with the perceptual difference stated), underlined links, +1 px of text, a 24 px target. |
| 3. The road to a 10 | AAA criteria, redesigns, plain-language rewrites, features, testing with disabled users, process and CI. |

Severity is tracked separately: a blocker can be tier 1 (a missing label) and a nicety can be tier 3.

## What a run does

1. **Orient**: a detector reads the repo (frameworks, UI libraries, styling, routing, i18n, a11y tooling, suppressed lint rules, UIs embedded in source strings, vendored themes, build output) and picks the audit size.
2. **One question message** (gitignore, runtime, install permission, read-only runtime, flows), with defaults so "ok" answers everything.
3. **Pre-computation by scripts**: every a11y grep, colour tokens and failing contrast pairs, and, with a runtime, axe-core in both colour schemes, a keyboard tab-walk, 320 px reflow, text spacing, reduced motion, target sizes, and per-view digests of the accessibility tree.
4. **Expert subagents in parallel**: semantics and structure, keyboard and focus, visual perception, forms and input, dynamic content, content and media. Each owns a fixed set of WCAG 2.2 A and AA criteria and reports pass / fail / not tested / not applicable for every one of them, so the coverage matrix is real.
5. **Merge, dedupe, verify**: a script merges, derives tiers from visual impact, clusters root causes and builds the coverage matrix; the orchestrator decides duplicates and verifies every blocker before anyone builds on it.
6. **Persona subagents** that simulate people who rely on assistive technology: a screen-reader user, a low-vision user at 400 % zoom, a voice-control and keyboard user, a user with dyslexia and ADHD, a colour-blind user, a Deaf user, a user with a vestibular disorder, an older novice. They walk the key flows **before** reading the expert findings, keep an evidence trace per step, and their task verdicts set severity floors. A framework-maximizer runs alongside them and finds the one token, base component or hook that fixes several findings at once.
7. **Report**, in the user's language, with a summary a screen-reader user can stop at, per-tier tables, a fix per finding in the stack's own idiom, the personas' voice, structural advice, and appendices (coverage matrix, full list, method). Re-audits compare on stable fingerprints and report resolved / open / regressed / new.

Modes: full, lean (small UI), mini (a handful of files, no forms), focused review (one component or PR), re-audit, apply fixes.

Exports: SARIF 2.1.0 for GitHub and GitLab code scanning, a draft ACR/VPAT-style conformance table from the coverage matrix, CSV for tickets.

## Install

As a personal skill:

```bash
git clone https://github.com/<you>/tiered-a11y-audit ~/.claude/skills/tiered-a11y-audit
```

Then, in a repo: "Maak een toegankelijkheidsrapport van deze site" or "how accessible is this app?". The skill asks its questions, runs 20 to 45 minutes depending on mode, and leaves everything in `.a11y-audit/` (it asks to gitignore that folder first).

Requirements: Python 3 (standard library only) for the scripts; for runtime checks, Node and permission to install `playwright` and `@axe-core/playwright` in a throwaway directory (an installed Chrome or Edge avoids the browser download).

## What it costs

From real runs: a full audit is 13 to 15 subagents and 1 to 1.5 million subagent tokens; lean about 10 and 0.5 to 0.7 million; mini about 5 and 0.3 million. Wall-clock 20 to 45 minutes for all of them, because the orchestrator's own verification takes as long as the agents.

Measured on the eval cases (2026-11-06, Claude Code 2.1.319, Opus, one run per arm, `--ablation with-without`, so each figure is the with-arm only). Tokens are the run total including cache reads, which is most of it:

| Case | Tokens | Cost | Turns | Wall-clock |
|---|---|---|---|---|
| `full-audit-fixture-site` | 1.29 million | $2.59 plus $0.24 judge | 18 | 12 minutes |
| `focused-review-contact-form` | 43 thousand | $0.21 plus $0.04 judge | 4 | 1 minute |
| `declines-non-frontend-repo` | 110 thousand | $0.25 plus $0.02 judge | 5 | 34 seconds |

The full audit lands in the 1-to-1.5-million range above, but on a 252-line fixture and with **no subagents at all** — the orchestrator did every lens itself. A real repository spreads that token count over 13 to 15 agents instead of one context. Note also that `--ablation` defaults to `with-without` and `--runs` defaults to 3, so the full suite is six full audits unless you pass `--runs 1`.

## Limitations, honestly

- The personas are AI simulations. They are good at spotting what checklists miss (a colour-blind persona found two "safe" palette tokens collapsing under deuteranopia; nothing else caught it), but they do not replace testing with disabled people. The report says so, and tier 3 asks for that testing.
- Automated tools find a minority of real issues; the experts do the work, and the orchestrator verifies blockers by opening the code or the page.
- **Measured detection rate: 21 of 24 (88%) on the fixture site, one run, 2026-11-06.** Claude Code 2.1.319, Opus, static analysis only. Scored by `scripts/grade_findings.py` against `evals/full-audit-fixture-site/ground-truth.json`. What the number hides, in both directions:
  - **All 24 seeded failures were actually found.** The three the grader counts as missed are criterion-attribution failures, not blind spots: the generic "Lees meer" links cite 2.4.9 (AAA) where the ground truth expects 2.4.4 (AA), and the missing skip link and the blocked paste on the password field were reported with an **empty WCAG list**. By substance it is 24 of 24; by the grader's rule, which requires the criterion to match, it is 21.
  - **19% of findings (8 of 42) carried no WCAG criterion**, and `merge_findings.py` did not flag it — its `problems` list came back empty. The skill's own ground rules require a criterion or an explicit best-practice marker on every finding, so this is a real schema gap, and it is what cost two of the three detections.
  - 4 of the 24 landed in the wrong tier, all adjacent (carousel autoplay, colour-only status dots and the 13px root size placed in tier 1 instead of 2; placeholder-only labels in tier 2 instead of 1).
  - Should-pass: 1 of 4 violated. The carousel slides were flagged for having alt text of "Slide 1", "Slide 2", "Slide 3" — arguably a fair finding about non-descriptive alt text rather than a false positive, but it counts against the fixture as written.
- The fixture does not measure the subagent pipeline. It is four files and 252 lines, and on that the orchestrator ran all six expert lenses and five personas itself rather than spawning subagents — **zero `Task` calls**, although `Task` was available. It said so plainly in the report, so this is a disclosed shortcut and not fabrication, but it means the 88% is an orchestrator-only number. The 13-to-15-subagent workflow has no measurement behind it yet.
- **The eval case's own score (7 of 21 graders) is not a usable signal, and the suite is mis-designed for this case.** Every grader is `type: llm` with `focus: trace`, and an LLM judge sees only the first 12 and the last 12 trace messages — a documented limit, not a defect. A full audit is 160 messages, so the judge got 24 of them with `[…136 messages elided…]` in the middle, and graders then fail on evidence they never saw: the report does contain the four score values, the persona matrix and the `#9a9a9a` to `#767676` contrast fix that `13-scores-four-values`, `14-persona-matrix` and `06-muted-contrast-tier2-with-colour` were marked down for. The fix is to grade the artefacts instead of the trace — `focus: { source: file, path: .a11y-audit/REPORT.md }` for the report's content, and the free deterministic types (`file_exists`, `tool_used`, `regex` with `target: trace`, which has no window limit) for "this script ran" and "this file was written". Until then, read the detection rate, not the case score.
- On the focused-review case the skill does not fire at all. In both arms the only tool calls are three `Read`s and no `Skill` call, so the three-tier structure that `02-three-tiers-still-used` checks is simply absent and the ablation delta is 0 — nothing was measured rather than nothing gained. The prompt does contain "toegankelijk", which is in the skill's trigger list; for a single form the model answers directly instead.
- Validated on three codebases so far: ESP32 firmware with HTML in C++ strings, a React SPA with canvas charts and a strict CSP, and a themed bilingual Hugo site. Other stacks have playbooks but no run behind them yet. Run it first on something you can afford to be wrong about, and read `SKILL-FEEDBACK` style notes it leaves when something looked off.
- The runtime scan needs the scripts copied into the scratch directory (Node resolves imports from the script's own location); the skill does that, hand-written helpers must too.

## Repository layout

```
SKILL.md                    the workflow (read by Claude Code)
agents/experts/             six lenses + the framework-maximizer + their shared protocol
agents/personas/            eight personas + their shared protocol
references/                 tiering rules, finding schema, WCAG ownership, framework playbooks, report template, tooling
scripts/                    detector, pattern scanner, colour extractor, contrast tool, aria digest, runtime scan,
                            briefing builder, merge/coverage, report-table renderer
evals/                      four test cases with fixture sites (claude plugin eval .)
```

## Contributing

The most useful contribution is a run on a stack that has no run behind it yet, plus the `SKILL-FEEDBACK.md` the orchestrator writes when asked to review the skill. Playbook corrections (version-gated features, library quirks) are the second most useful. Keep the three tiers and the orthogonal severity; those are the point.

## License

MIT
