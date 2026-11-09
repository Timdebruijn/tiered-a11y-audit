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
git clone https://github.com/Timdebruijn/tiered-a11y-audit ~/.claude/skills/tiered-a11y-audit
```

Then, in a repo: "Maak een toegankelijkheidsrapport van deze site" or "how accessible is this app?". The skill asks its questions, runs 20 to 45 minutes depending on mode, and leaves everything in `.a11y-audit/` (it asks to gitignore that folder first).

Requirements: Python 3 (standard library only) for the scripts; for runtime checks, Node and permission to install `playwright` and `@axe-core/playwright` in a throwaway directory (an installed Chrome or Edge avoids the browser download).

## What it costs

From real runs: a full audit is 13 to 15 subagents and 1 to 1.5 million subagent tokens; lean about 10 and 0.5 to 0.7 million; mini about 5 and 0.3 million. Wall-clock 20 to 45 minutes for all of them, because the orchestrator's own verification takes as long as the agents.

## Limitations, honestly

- The personas are AI simulations. They are good at spotting what checklists miss (a colour-blind persona found two "safe" palette tokens collapsing under deuteranopia; nothing else caught it), but they do not replace testing with disabled people. The report says so, and tier 3 asks for that testing.
- Automated tools find a minority of real issues; the experts do the work, and the orchestrator verifies blockers by opening the code or the page.
- Measured accuracy is not yet published. The fixture site has 24 seeded failures and 4 should-pass items with a grader (`scripts/grade_findings.py`); the number that matters is the detection rate on a blind run, and that run has not been done yet. Other projects publish such numbers; this one will once it has them.
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
