# Report template

Write `.a11y-audit/REPORT.md` with exactly this structure. The headings come from the labels file of the report language (the user's language), and the finding text is already in that language; keep code, selectors and WCAG numbers unchanged. Example headings in Dutch are given in brackets.

The report is read by people who may use a screen reader, text-to-speech or magnification. Structure rules, applied to every section without exception:

1. Each H2 section has the same shape: one introductory paragraph, then at most one table or one list, then the H3 detail blocks. No alternating of tables and prose.
2. Every table is announced by the sentence before it, naming what it lists and how many rows; at most four columns; the key (ID) in the first column; no empty cells (write "none"); words, never symbols or emoji.
3. Every finding block has the same fields in the same order (see below); a listener learns the pattern once.
4. Read-aloud wording: "4.5 to 1" not "4.5:1"; "A and AA" not "A/AA"; "not applicable" not "n/a"; full terms before abbreviations; no arrows, middle dots or decorative rules; headings in strict hierarchy (H1, H2, H3) without skipped levels; one list level; bold only for a few words.
5. The short summary comes first, before any table, so a reader who stops early has the essentials. Developer-only material (full list, coverage matrix, method) lives in the appendices.

Report IDs: number the deduplicated findings per tier as `T1-01`, `T2-01`, `T3-01` … and map each to its source IDs (`DYN-001 + FRM-001 + FWK-004`) in appendix C. Readers get a clean sequence; re-audits keep working through the `fingerprint`s in `_merged.json`.

```markdown
# Accessibility report — <project name>            [Toegankelijkheidsrapport]

## In short                                          [In het kort]

Five to eight plain sentences, no table, no list: what was audited, the score now and after each tier in words ("now 5 out of 10, after tier 1 a 7, after tiers 1 and 2 an 8; a 9 is the realistic ceiling"), the single most important thing to fix, and how much tier 1 costs in days. A screen-reader user who stops here has the essentials.

## Summary                                          [Samenvatting]

One paragraph: the score now and after each tier, each with its one-sentence justification, written as prose. Then one sentence announcing the table, and one table with four columns: Tier, Findings, Highest severity, Estimated effort. Then one numbered list, "Top 5 actions", one line per action with ID, tier and effort. Blockers and findings flagged `affects_all_users` are the first items of that list, marked with the word "blocker" or "affects everyone". Close with one short paragraph: date, commit, scope, stack, standard and method (details in appendix A).

## Changes since the previous audit                   [Wijzigingen sinds vorige audit]   (re-audit mode only)
Score then and now in words. Then four short lists: resolved, still open, regressed, new (one line per finding: ID, title). One sentence on what the team got right and what slipped back.

## How to read this report                           [Leeswijzer]
Three short paragraphs: what each tier promises; that severity and tier are independent; that personas are AI simulations and not a substitute for testing with disabled users.

## What already works well                           [Wat al goed gaat]
3–8 bullets from the agents' `positives`, specific.

## Tier 1 — Invisible improvements                    [Niveau 1 — Onzichtbare verbeteringen]

One paragraph: what this tier promises and how many findings it holds. One sentence announcing the table. One table, four columns: ID, Title, Severity, Effort. Then the finding blocks, in the same order as the table, each with exactly these fields in this order:

### <ID>. <title>
Severity, WCAG criterion (number, name, level), users affected, effort, confidence: one sentence.
Problem: one to three sentences.
Where: path and lines (with instance count), or URL and selector.
Fix, framework-native, at the highest-leverage location: one sentence, then one code block with the before and after.
Watch out: side effects, or the word "none".
Verify: the concrete steps.

Fix ownership: the overview table's ID column marks `upstream` and `accepted` findings with that word in brackets after the ID. At the end of each tier, two fixed H3 blocks when they apply: "Needs an upstream change" (one line per finding: ID, upstream file, issue to file) and "Accepted exceptions" (one line per finding: ID, reason, what would reopen it; for tool rules also the rule and selector so the CI gate can be configured to match).

Findings of severity "minor" use the compact block instead, so a long tier-1 list stays readable: the same first sentence, then Problem, Where and Fix each in one line, no code block unless the fix is not obvious from the sentence. A tier with more than fifteen findings puts the compact ones after the full ones under an H3 "Smaller items".

## Tier 2 — Small, non-shocking adjustments          [Niveau 2 — Kleine aanpassingen]

Same shape as tier 1: paragraph, announced four-column table, finding blocks with the same fields plus one extra field "Design impact" after "Problem". Colour changes get one extra H3 block at the end of the section, "Proposed token changes", with one announced table of four columns: Token or usage, Before, After, Contrast before and after. The colour-difference value (ΔE) is mentioned in the sentence before the table, not in a column, so the designer can approve the set in one go.

## Tier 3 — The road to a 10                           [Niveau 3 — Op weg naar een 10]

One paragraph, then five H3 blocks in a fixed order: Design, Content, Features, Validation with users, Process and governance. Each block is one list; each item one line: what, why (which users or criteria), rough effort. No tables in this section.

## Voice of the users                                 [Stem van de gebruikers]

One paragraph stating that the personas are simulations and which ones ran. One sentence announcing the table, then one table with four columns: Flow, Persona, Result, Main obstacle (ID). Results in words only: completed, with difficulty, with help, failed, not applicable. Then one H3 block per persona, same fields in the same order: three or four sentences from their narrative, top frustration with ID, what would make it a 10. Where a persona and an expert disagree, say so; "confirmed" (observed in the walk) outweighs "cites".

## Structural advice: framework & tooling            [Structureel advies: framework en tooling]
One paragraph, then one announced table with four columns taken from the "Leverage points" list in `_merged.md`: Change (location), Resolves (report IDs), Effort, Why here. Then one list for the recommended lint, test and CI setup so fixes don't regress. If the project documents an earlier accessibility claim (a "0 violations" note, a contrast table), say in one sentence what this audit found against it.

## To verify                                          [Nog te verifiëren]
Low-confidence findings that need a runtime or AT check, with what to check.

## Appendix                                           [Bijlagen]
- A. Method and limitations: what was static vs runtime vs automated, what was out of scope, what wasn't examined (from agents' coverage).
- B. WCAG 2.2 A/AA coverage matrix (all 55 criteria from `wcag-ownership.md`), four columns: SC, name, status (pass, fail with IDs, not tested, not applicable), note. Taken from `coverage.md`. Count the four statuses in a sentence above the table.
- C. Full finding list (one line each: ID, tier, severity, title, location).
- D. Legal context (only if relevant to the user: EN 301 549, European Accessibility Act, public-sector requirements, accessibility statement).
```

Style: concise, concrete, no filler. No praise inflation, no doom. The team should be able to start on tier 1 the same afternoon.

Short variant: when the user uses a screen reader or asks for a short report, also write `REPORT-SHORT.md` with only "In short", the summary and the tier-1 findings in their compact form (title, one-sentence problem, fix location, one verify step), and point to `REPORT.md` for the rest.
