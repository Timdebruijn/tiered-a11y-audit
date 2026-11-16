# Finding schema

Every expert agent writes one JSON file: `.a11y-audit/findings/<agent>.json`.

```json
{
  "agent": "keyboard-focus",
  "lenses": ["keyboard-focus"],
  "coverage": {
    "method": "static | runtime | both",
    "examined": ["src/components/Modal.tsx", "src/app/layout.tsx", "flow: checkout"],
    "not_examined": ["admin/ — out of scope"],
    "notes": "Free text about limits of this pass."
  },
  "positives": [
    "Dialogs use Radix Dialog, which traps and restores focus correctly."
  ],
  "cross_lens_notes": [
    { "sc": "1.4.11", "location": "src/components/Input.tsx:30", "note": "Border colour looks weak; visual lens to measure." }
  ],
  "sc_coverage": {
    "2.1.1": { "status": "fail", "findings": ["KBD-001"] },
    "2.1.2": { "status": "pass", "note": "No traps found in key flows; cookie banner verified at runtime." },
    "2.1.4": { "status": "n/a", "note": "No single-key shortcuts implemented." },
    "2.4.11": { "status": "not-tested", "note": "Needs runtime; sticky header present (src/app/layout.tsx) — check scroll-padding." }
  },
  "findings": [
    {
      "id": "KBD-001",
      "fingerprint": "keyboard-inoperable@src/components/Dropdown.tsx",
      "title": "Custom dropdown cannot be opened with the keyboard",
      "description": "What is wrong and who it affects, in 1–4 sentences.",
      "evidence": [
        {
          "file": "src/components/Dropdown.tsx",
          "lines": "42-58",
          "url": null,
          "selector": null,
          "snippet": "<div className=\"trigger\" onClick={toggle}>"
        }
      ],
      "instances": { "count": 14, "how_counted": "grep for <Dropdown in src/", "scope": "component" },
      "wcag": [ { "sc": "2.1.1", "name": "Keyboard", "level": "A" } ],
      "best_practice_only": false,
      "severity": "blocker",
      "affected_users": ["screen-reader", "motor-voice", "low-vision"],
      "visual_impact": "none",
      "affects_all_users": false,
      "proposed_tier": 1,
      "tier_rationale": "Same visuals; adds button semantics and key handling.",
      "fix": {
        "ownership": "project",
        "summary": "Replace the div trigger with the library's accessible Menu, or a <button> with aria-expanded and APG menu-button keyboard handling.",
        "location": "src/components/Dropdown.tsx (fixes all 14 usages)",
        "framework_idiom": "Use @radix-ui/react-dropdown-menu already in package.json.",
        "code_before": "<div className=\"trigger\" onClick={toggle}>",
        "code_after": "<DropdownMenu.Trigger className=\"trigger\">",
        "side_effects": "Check that the trigger style resets button defaults."
      },
      "effort": "M",
      "confidence": "high",
      "verify": "Tab to the trigger, press Enter/Space/ArrowDown; menu opens and focus moves into it; Esc closes and returns focus."
    }
  ]
}
```

## Field rules

- `id`: agent prefix + three digits. Prefixes: `SEM` semantics-structure, `KBD` keyboard-focus, `VIS` visual-perception, `FRM` forms-input, `DYN` dynamic-content, `CNT` content-media, `FWK` framework-maximizer, `PER-<persona>` for new findings from personas, `ORC` for findings the orchestrator makes itself during verification (written to `findings/orchestrator.json`, same schema). IDs are per run; use `fingerprint` to match across runs.
- `fingerprint`: `<problem-slug>@<root-cause path or selector>`, stable across runs: lowercase slug of the problem type (`missing-accessible-name`, `contrast-text`, `focus-not-visible`, `no-route-announcement`, `placeholder-only-label`, `keyboard-inoperable`, …) plus the highest-leverage location. Two findings with the same fingerprint are the same finding. Re-audits compare on this field.
- `lenses` (top level): the owner names this file speaks for. One for a normal expert; two for a merged lean-mode agent (`["keyboard-focus", "dynamic-content"]`), which then writes ONE file named after its briefing and reports `sc_coverage` for both lenses' criteria. The merge script credits each criterion to the right owner.
- `sc_coverage` (top level): status for every SC the agent owns in `references/wcag-ownership.md`: `pass` | `fail` (list finding IDs) | `not-tested` (reason) | `n/a` (reason). The brief of each expert ends with the start of this file, listing exactly the criteria it owns. The merge treats an omitted SC as `not-tested`, but `check_phase.py` refuses the file until every owned SC has one of the four statuses.
- `visual_impact`: what a sighted mouse/touch user with default settings would notice after the fix — `none` (accessibility tree, metadata, tooling only), `keyboard-only` (appears only on keyboard focus), `preference-only` (appears only under reduced-motion / forced-colours / high zoom / text spacing), `subtle` (visible but product stays instantly recognisable; no layout restructure, microcopy only), `significant` (anything bigger). The tier follows mechanically: `none`/`keyboard-only`/`preference-only` → 1, `subtle` → 2, `significant` → 3. `proposed_tier` must agree with this; the rationale explains the `visual_impact` choice.
- `evidence`: at least one item. Static: `file` + `lines` + `snippet` (≤ 5 lines). Runtime: `url` + `selector`. Never cite a file you did not open. Copy the snippet from the file instead of retyping it: the merge looks every snippet up in the cited file. Line breaks and indentation do not matter and you may leave a stretch out with `…`, but every part you do quote has to be there character for character, so no comments of your own inside it.
- `instances`: count with grep/search when a pattern repeats; `scope` is `global` (token/layout/reset), `component`, `page`, or `instance`.
- `wcag`: WCAG 2.2 success criteria with number, name, level. If none applies, `[]` and `best_practice_only: true`.
- `severity`: blocker | critical | serious | moderate | minor (see tiering.md).
- `affected_users`: any of `screen-reader`, `low-vision`, `colour-blind`, `motor-voice`, `cognitive`, `deaf`, `vestibular`, `older-novice`.
- `proposed_tier`: 1 | 2 | 3, using tiering.md. The orchestrator makes the final call.
- `fix.ownership` (required): who can make the fix under this project's rules, as recorded in the stack profile's "writable directories" line:
  - `project` — the team edits this code;
  - `override` — the defect is in vendored code (theme, submodule, design system) but the project can fix or mask it from its own files (an override template, a render hook, its own CSS, a config value); `fix.location` is then the project-side file;
  - `upstream` — only the dependency can fix it; name the upstream file and, if known, an issue;
  - `accepted` — no fix is available under this project's rules (for example "never copy theme templates"); give the reason and the trigger that would reopen it. Keep the severity honest; the report lists these separately as accepted exceptions.
  An `accepted` entry for a tool rule (an axe rule firing on a selector with no real user impact) adds `"exception": {"tool": "axe", "rule": "label-content-name-mismatch", "selector": "#search-button", "reason": "…"}` so a CI gate can be configured to match.
- `fix.location`: the highest-leverage place to fix it. Prefer token > shared component > layout > page > instance.
- `fix.code_after`: idiomatic for the detected stack; minimal; compiles in principle. Omit code for tier-3 process items.
- `affects_all_users`: `true` when the problem also hits sighted mouse users (a plain functional bug found along the way). Such findings go to the top of the summary.
- `cross_lens_notes` (top level): observations outside your lens whose fix the owning lens would write the same way — one line each, no finding.
- `kind` (optional): `defect` (default) or `leverage`. A `leverage` entry is not a finding: it names one place where several findings get fixed.
- `leverage` (framework-maximizer only): `{ "finding_ids": [...], "location": "...", "note": "..." }` on an entry that resolves several existing findings at one spot. The merge script attaches it to each target as `leverage_points`, lists all entries ranked by findings resolved (that list is the report's structural-advice section), and does NOT count the entry as a finding. Never put such an entry in `_dedupe.json`.
- `effort`: S (< 1 h), M (≤ 1 day), L (> 1 day).
- `confidence`: high (verified in code/runtime), medium (strong indication), low (suspicion — needs runtime check). Low-confidence findings are listed separately in the report as "to verify".
- `verify`: concrete steps a developer can follow to confirm the fix.

Contrast findings additionally include `"colours": {"fg": "#hex", "bg": "#hex", "ratio": 3.2, "required": 4.5, "suggested_fg": "#hex", "suggested_ratio": 4.6, "delta_e_ok": 0.05}` produced with `scripts/contrast.py`.
