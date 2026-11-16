# Changelog

Rounds of review and real runs, newest first. Each round changed what the report says, not only how it is phrased.

## 1.1.0 (2026-11-16)

Everything merged after 1.0, with the pull request it came in. The numbers in the README are those of the last eval run of 16 November, described in round 13.

### Round 13 — what an audit costs, the report step, and any language (2026-11-16)
- The eval run of round 12, repeated with the fix for runs without a person, showed a working audit at 10 dollars 66 for one more seeded failure than the 2 dollar 59 run of 6 November. Per agent: one subagent that translated the report and cleared linter points wrote 27 percent of all output; every subagent ran on the top model.
- Agents write their findings in the report language from the start, so nothing is translated afterwards. What scripts read stays as the schema spells it. The renderer puts a contrast written as 4.5:1 into words itself (#22).
- Expert, persona and maximizer subagents run on the mid-tier model by default; the orchestrator's own steps stay on the session's model (#23).
- The report is assembled by the renderer from the draft and `report-prose.md`, the one small file the orchestrator writes. `REPORT.md` is never edited by hand. A prose file with a section twice, or with a section that is no gap of the report, is refused (#24).
- `SKILL.md` asks for one shell call per step: a merge with its phase check, the renderer with the linter (#25).
- The description no longer leans on Dutch trigger phrases, and the scan for link texts that say nothing knows seven languages and names them in its row, so a zero in another language reads as not searched (#26).
- `detect_stack.py` counts a hand-written `site/` or `public/` folder as the user interface, as the other two scanners already did; an eval trace showed it reporting no interface for the fixture (#21).
- The last eval run, one run per arm, with all of the above: the lean audit of the fixture cost 4 dollars 28 with ten subagents and found 23 of 24 seeded failures; the one miss was reported under another criterion. No finding lacked a criterion, the merge listed no problems, all four phase checks passed and the report passed the linter. The orchestrator wrote its prose in one file of 72 lines and did not edit the report. The mini audit of the themed site cost 2 dollars 9 with five subagents. The focused review scores 1.00 with the plugin and 0.83 without, with the new description.
- Still true: the case scores of the two audit cases (0.19 and 0.40) do not measure the audit, because their graders read only the first and last twelve messages of a trace. Only Dutch prompts have been measured.

### Round 12 — the second eval run (2026-11-16)
- The suite ran on everything below, three runs per arm. The focused review scores 1.00 with the plugin against 0.83 without, where the first run measured no difference; the grader for the three-tier answer passes only with the plugin. Both audit cases stopped after the Phase 1 questions, because nobody answers in a scripted run: `full-audit-fixture-site` scored 0.19 with the plugin and 0.29 without, `themed-site-fix-ownership` 0.20 either way. The first run had got past that point only by not asking.
- `preflight.py` reports whether a person is there to answer, and when nobody is, Phase 1 goes on with for each question the option that needs no permission: no edit of `.gitignore`, static only, nothing installed (#19).
- One print-mode run with that fix, on the fixture but outside the eval harness: a lean audit with 13 subagent calls where the first run made none, 22 of 24 seeded failures detected, no finding without a criterion, an empty problem list in the merge, all four phase checks passed and a report the linter accepts. It did not state the defaults it took, which the instructions ask for; the wording was made firmer afterwards and has not been measured. It is one run, so it is a sign and not a rate.

### Round 11 — scripts take over what was left to memory (2026-11-16)
- `merge_findings.py` checks what a finding claims: the cited file, lines and snippet exist, the criterion is level A or AA with its name and level from the ownership table, and a stated contrast ratio is recomputed. A finding with no criterion and no best-practice marker is reported; the measured run had 8 of 42 such findings and flagged none (#8).
- `render_report_parts.py` writes the whole report as `REPORT.draft.md`, with every table and finding block filled from `_merged.json` and the prose left as marked gaps, instead of the orchestrator retyping each block (#9).
- The report can be written in any language. The fixed words live in `references/report-labels/<code>.json`; English and Dutch ship, any other language is translated once from a file the renderer writes into the workspace and then validated (#10).
- `lint_report.py` checks the finished report: no gap left, every report ID present once, and the read-aloud rules a script can decide (table width, heading levels, nested lists, symbols, slashes, ratios with a colon). Phase 6 ends when it exits 0 (#11).
- `check_phase.py` checks at the end of phases 3 to 6 that the phase left what the next one builds on: every expert's file, a status for every criterion it owns, a merge newer than its inputs, briefs newer than the stack profile, a report that passes the linter. `build_briefs.py` writes the list of agents it reads, and ends each lens brief with the start of that agent's findings file (#12).
- `preflight.py` does Phase 0 in one read-only command and sets the workspace up in a second. A re-audit moves the whole earlier audit aside, a run in progress stays, nothing is deleted, and `.gitignore` is only appended to (#13).
- The merge separates what it settled itself (`notes`) from what needs a decision (`problems`). Snippets are compared with whitespace next to punctuation removed, a persona's prose is no longer looked up as a quote, and a coverage reason is read from `reason` as well as `note` (#14).
- `SKILL.md` follows the order of the work: the stack profile and the static scans open Phase 2, the persona selection is made in Phase 3, a finding is split into two tiers in 4c. Subagents are stated as the rule for full, lean and mini audits. The description names the focused review. `scan_patterns.py` counts forms and form controls, which decide mini or lean (#16).
- Each brief carries only the reference parts its reader acts on, about 12 percent less text. The cuts stop the build when a reference no longer has the section or field they name (#17).
- `LICENSE` added: MIT, as `plugin.json` and the README already said (#15).
- Eight self-checks next to the scripts (`test_walk`, `test_merge`, `test_grade`, `test_render`, `test_lint`, `test_phase`, `test_preflight`, `test_briefs`), plain asserts, run with `python3 skills/tiered-a11y-audit/scripts/test_<name>.py`.

### Round 10 — the first measured run (2026-11-15)
- The repository is a loadable plugin: `.claude-plugin/plugin.json`, the skill under `skills/tiered-a11y-audit/`, `evals/` at the root. Before this the eval cases could not run at all (#3).
- `grade_findings.py` no longer scores items it cannot grade: a ground-truth item without keywords is reported as ungradable and left out of both denominators, a should-pass item flagged twice is counted once, and three crashes on unusual input are gone (#4).
- The README gives the measured detection rate, 21 of 24 seeded failures, with what the number overstates and understates, instead of a promise to measure (#5).
- README: install link corrected after the move (#6), and the whole text rewritten to the skill's own read-aloud rules (#7).

### Round 9 — two faults found by reading the scripts (2026-11-06)
- The file walk dropped real UI directories: `roles/`, `public/` and `site/` were skipped at any depth, so `src/pages/roles/` or a hand-written `public/` vanished from the audit. Infra and vendor names now count at the top level only, and `public/` and `site/` are build output only next to a static-site generator config. A dangling symlink no longer stops the walk (#1).
- One malformed findings file no longer takes the whole merge down: wrong shapes are coerced where that loses nothing and reported, a file that is not valid JSON is skipped with a message, and two persona findings without an ID no longer collide (#2).

## 1.0 (2026-11-06)

### Round 8 — landscape comparison
- `export_findings.py`: SARIF 2.1.0 (code scanning), draft ACR conformance table (en/nl), CSV.
- `grade_findings.py` with `ground-truth.json` for the fixture: detection rate, misses, unmatched findings.
- `axe_scan.mjs --sitemap <url> --max-pages N` for whole-site scans of static sites.

### Round 7 — final consistency pass
- `fix.ownership` validated by the merge script; accepted exceptions and cross-lens notes surfaced in `_merged.md`; report tables mark upstream and accepted findings and list them per tier.
- Pattern scanner and colour extractor skip build output (gitignored dirs, `public/`, `_site/`…) and keep vendored hits (themes, submodules) in their own bucket.
- Minified CSS without a trailing semicolon parsed correctly.
- Fourth eval case: a themed Hugo site with an off-limits submodule.
- README and this changelog.

### Round 6 — feedback from a themed Hugo site (lean mode)
- **axe no longer runs twice on one page with a colour-scheme flip**: each scheme gets its own browser context and page load. The old behaviour fabricated serious contrast violations near 1.0 to 1 on every page of any site with a `dark` class.
- `--steps` actions type real keystrokes (`type`/`fill` via `pressSequentially`), accept a per-state `viewport` and `force`, and a failed state is reported instead of dropped. Action shapes spelled out.
- Coverage is routed to the criterion's owner regardless of which findings file reported it (lean and mini modes); conflicts only when two files disagree. Persona `wcag` citations are advisory and listed separately instead of overturning the owner's status.
- Detector excludes build output, lists packages found only in vendored code separately, and prints the count of project-owned UI files that drives the mode choice.
- `fix.ownership` (project / override / upstream / accepted) with optional tool exceptions; writable directories established in Phase 2; "Needs an upstream change" and "Accepted exceptions" blocks in the report; prior a11y claims in the repo are re-measured.
- Mini mode (two merged experts, two personas); cost quoted per mode; skill and scratch paths live in the stack profile so subagent prompts are short.
- Hugo playbook expanded (i18n per language, `.IsMenuCurrent`, `--printI18nWarnings`/`--panicOnWarning`, anchors inside headings).
- Cognitive persona names sentences instead of rewriting them.

### Round 5 — efficiency: scripts instead of agent tool calls
- `scan_patterns.py` (some sixty a11y greps with locations), `extract_colors.py` (tokens per scheme, failing pairs), `aria_digest.py` (landmarks, headings, nameless controls per view), `build_briefs.py` (one briefing file per agent), `render_report_parts.py` (all report tables with report IDs).
- Expert tool budget 60 → 40; agents start from the pre-computed inputs.

### Round 4 — self-review of the Hugo run artifacts
- Orchestrator findings file (`ORC` prefix) formalised.
- `lenses` field for merged lean agents.
- Leverage entries no longer counted as findings; ranked leverage list becomes the structural-advice section.
- Node ESM import gotcha: `axe_scan.mjs` is copied into the scratch directory.
- Compact blocks for minor findings; prior-claims line in the stack profile.

### Round 3 — output accessibility
- The skill's own output must be accessible: answer first, short, predictable section shape (paragraph, one announced table or list, detail blocks), tables of at most four columns, words instead of symbols, no decorative characters, headings in strict hierarchy; short report variant for screen-reader users.
- `.a11y-audit/` gitignore question before anything is written.
- Phases reordered: orient → one question message → recon and runtime → automated baseline and stack profile → experts, merge, dedupe, verify → personas and maximizer in parallel → synthesis → wrap-up. Re-audit delta by script (`--previous`).

### Round 2 — feedback from a React SPA and from ESP32 firmware with embedded HTML
- `merge_findings.py`: merge, tiers from `visual_impact`, root-cause clusters, persona verdict links, severity floors from persona key-flow failures, coverage matrix with conflicts, persona findings normalised.
- Framework-maximizer as a post-pass with leverage points; cross-lens filing rule; pattern-owner table.
- Dedupe decided by the orchestrator (`_dedupe.json`) before the personas run; personas walk first and read afterwards; `confirmed` vs `cites`; `n/a` verdicts.
- Runtime read-only by default; working language English, report in the user's language; common false positives and commonly misapplied criteria listed.
- Detector finds UIs embedded in source strings, a CSP, missing routers, and labels infra templates; `axe_scan.mjs` gets `--channel`, `--steps`, `bypassCSP`, per-check try/catch; `contrast.py` gets `auto`, `flatten`, `--large`.
- WCAG ownership per-owner lists with verified counts (55 criteria); `:focus-visible` on text inputs is tier 2.

### Round 1 — first self-review
- Modes (full, focused review, re-audit, apply fixes); stable `fingerprint`; mechanical `visual_impact` → tier; WCAG 2.2 A/AA ownership so the coverage matrix cannot be invented; persona trace table; stack-profile template; `--previous`; runtime script with text-spacing, reduced-motion and colour-blindness checks; fixture site with seeded issues and three eval cases.

### Round 0 — initial design
- Three tiers by visual impact, seven expert lenses, eight personas, framework playbooks, tiering rules with scoring rubric, finding schema, report template, detector and contrast tool.
