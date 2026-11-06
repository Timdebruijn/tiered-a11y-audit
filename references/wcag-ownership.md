# WCAG 2.2 A/AA ownership

All 55 Level A and AA success criteria of WCAG 2.2, each with exactly one owning expert. The owner reports `sc_coverage` for its criteria — `pass`, `fail` (with finding IDs), `not-tested` (with reason), or `n/a` (with reason) — so the report's coverage matrix is real, not guessed. Other experts may still file findings against any SC; the owner's status must then reflect them after the orchestrator merges.

Not in the matrix: the former criterion "Parsing" (4.1.1) is obsolete in WCAG 2.2 and is never reported.

## Per owner (use this list; the count is exact)

- **semantics-structure (8):** 1.3.1 · 1.3.2 · 2.4.2 · 2.4.5 · 2.4.6 · 2.5.3 · 3.1.1 · 4.1.2
- **keyboard-focus (7):** 2.1.1 · 2.1.2 · 2.1.4 · 2.4.1 · 2.4.3 · 2.4.7 · 2.4.11
- **visual-perception (10):** 1.3.4 · 1.4.1 · 1.4.3 · 1.4.4 · 1.4.10 · 1.4.11 · 1.4.12 · 1.4.13 · 2.3.1 · 2.5.8
- **forms-input (12):** 1.3.5 · 2.5.1 · 2.5.2 · 2.5.4 · 2.5.7 · 3.2.2 · 3.3.1 · 3.3.2 · 3.3.3 · 3.3.4 · 3.3.7 · 3.3.8
- **dynamic-content (4):** 2.2.1 · 2.2.2 · 3.2.1 · 4.1.3
- **content-media (14):** 1.1.1 · 1.2.1 · 1.2.2 · 1.2.3 · 1.2.4 · 1.2.5 · 1.3.3 · 1.4.2 · 1.4.5 · 2.4.4 · 3.1.2 · 3.2.3 · 3.2.4 · 3.2.6

8 + 7 + 10 + 12 + 4 + 14 = 55.

## Pattern owners (who files the finding for a recurring pattern)

The SC table says who reports status; this table says who writes the finding when several lenses notice the same thing. Other lenses reference the owner's ID in `cross_lens_notes` instead of filing their own.

| Pattern | Files the finding | Others add |
|---|---|---|
| Dialogs, drawers, popovers, command palettes (role, focus trap/restore, Esc, inert) | dynamic-content | keyboard-focus: a note if the key handling differs |
| Route / view / tab change (title, focus, announcement, back button) | dynamic-content | semantics-structure: `aria-current`/selected state on the control |
| Live regions and status messages | dynamic-content | forms-input: a note for form feedback |
| Form labels, descriptions, errors, autocomplete | forms-input | semantics-structure: nothing (it is the same finding) |
| Accessible names of non-form controls (icon buttons, links, custom widgets) | semantics-structure | — |
| Headings, landmarks, lists, tables | semantics-structure | — |
| Focus visibility, order, traps, skip link | keyboard-focus | visual-perception: contrast of the indicator |
| Custom widgets' keyboard behaviour (tabs, menus, combobox, slider, drag) | keyboard-focus | forms-input: non-pointer alternative if it is an input |
| Contrast, colour-only cues, target size, reflow, spacing, forced colours, motion | visual-perception | — |
| Canvas/SVG charts, images, icons, media alternatives | content-media | semantics-structure: nothing |
| Link text, language, readability, consistency | content-media | — |
| Tooling, lint suppressions, CI, unused platform features, leverage across findings | framework-maximizer (post-pass) | — |

| SC | Name | Level | Owner |
|---|---|---|---|
| 1.1.1 | Non-text Content | A | content-media |
| 1.2.1 | Audio-only and Video-only (Prerecorded) | A | content-media |
| 1.2.2 | Captions (Prerecorded) | A | content-media |
| 1.2.3 | Audio Description or Media Alternative (Prerecorded) | A | content-media |
| 1.2.4 | Captions (Live) | AA | content-media |
| 1.2.5 | Audio Description (Prerecorded) | AA | content-media |
| 1.3.1 | Info and Relationships | A | semantics-structure |
| 1.3.2 | Meaningful Sequence | A | semantics-structure |
| 1.3.3 | Sensory Characteristics | A | content-media |
| 1.3.4 | Orientation | AA | visual-perception |
| 1.3.5 | Identify Input Purpose | AA | forms-input |
| 1.4.1 | Use of Color | A | visual-perception |
| 1.4.2 | Audio Control | A | content-media |
| 1.4.3 | Contrast (Minimum) | AA | visual-perception |
| 1.4.4 | Resize Text | AA | visual-perception |
| 1.4.5 | Images of Text | AA | content-media |
| 1.4.10 | Reflow | AA | visual-perception |
| 1.4.11 | Non-text Contrast | AA | visual-perception |
| 1.4.12 | Text Spacing | AA | visual-perception |
| 1.4.13 | Content on Hover or Focus | AA | visual-perception |
| 2.1.1 | Keyboard | A | keyboard-focus |
| 2.1.2 | No Keyboard Trap | A | keyboard-focus |
| 2.1.4 | Character Key Shortcuts | A | keyboard-focus |
| 2.2.1 | Timing Adjustable | A | dynamic-content |
| 2.2.2 | Pause, Stop, Hide | A | dynamic-content |
| 2.3.1 | Three Flashes or Below Threshold | A | visual-perception |
| 2.4.1 | Bypass Blocks | A | keyboard-focus |
| 2.4.2 | Page Titled | A | semantics-structure |
| 2.4.3 | Focus Order | A | keyboard-focus |
| 2.4.4 | Link Purpose (In Context) | A | content-media |
| 2.4.5 | Multiple Ways | AA | semantics-structure |
| 2.4.6 | Headings and Labels | AA | semantics-structure |
| 2.4.7 | Focus Visible | AA | keyboard-focus |
| 2.4.11 | Focus Not Obscured (Minimum) | AA | keyboard-focus |
| 2.5.1 | Pointer Gestures | A | forms-input |
| 2.5.2 | Pointer Cancellation | A | forms-input |
| 2.5.3 | Label in Name | A | semantics-structure |
| 2.5.4 | Motion Actuation | A | forms-input |
| 2.5.7 | Dragging Movements | AA | forms-input |
| 2.5.8 | Target Size (Minimum) | AA | visual-perception |
| 3.1.1 | Language of Page | A | semantics-structure |
| 3.1.2 | Language of Parts | AA | content-media |
| 3.2.1 | On Focus | A | dynamic-content |
| 3.2.2 | On Input | A | forms-input |
| 3.2.3 | Consistent Navigation | AA | content-media |
| 3.2.4 | Consistent Identification | AA | content-media |
| 3.2.6 | Consistent Help | A | content-media |
| 3.3.1 | Error Identification | A | forms-input |
| 3.3.2 | Labels or Instructions | A | forms-input |
| 3.3.3 | Error Suggestion | AA | forms-input |
| 3.3.4 | Error Prevention (Legal, Financial, Data) | AA | forms-input |
| 3.3.7 | Redundant Entry | A | forms-input |
| 3.3.8 | Accessible Authentication (Minimum) | AA | forms-input |
| 4.1.2 | Name, Role, Value | A | semantics-structure |
| 4.1.3 | Status Messages | AA | dynamic-content |

The framework-maximizer owns no criteria; it reports leverage, suppressions and tooling.

AAA criteria are not tracked in the matrix; experts cite them in findings where relevant (they land in tier 3).
