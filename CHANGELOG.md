# Changelog

Rounds of review and real runs, newest first. Each round changed what the report says, not only how it is phrased.

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
