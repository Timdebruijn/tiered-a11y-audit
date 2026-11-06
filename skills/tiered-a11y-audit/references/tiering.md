# Tiering rules and scoring

## The decision test

Ask, in this order:

1. **Would a sighted mouse/touch user, with default OS/browser settings, at 100 % zoom, notice anything?** No → **Tier 1**.
   Changes that only show up in the accessibility tree, for keyboard users (`:focus-visible`), under user-preference media queries (`prefers-reduced-motion`, `forced-colors`, `prefers-contrast`), at ≥ 200 % zoom / 320 px reflow, in metadata, or in tooling/CI all count as invisible.
2. **Is the change visible but small enough that the product is instantly recognisable, no layout is restructured, no flow changes, and copy changes are limited to microcopy?** Yes → **Tier 2**.
3. Everything else → **Tier 3**.

When in doubt between two tiers, choose the higher number (more disruptive). A team that is promised "invisible" and then sees a visual change stops trusting the report.

## Tier 1 — Invisible improvements

Typical examples:

- Accessible names: `aria-label`/visually-hidden text on icon-only buttons and links; `alt` on informative images, `alt=""` on decorative ones; `aria-hidden="true"` + `focusable="false"` on decorative SVGs; `<title>` in meaningful inline SVGs.
- Semantics with identical rendering: `<div onclick>` → `<button>` with a style reset; `<a>` without href used as button → `<button>`; correct heading levels while keeping the visual class; landmarks (`<main>`, `<nav aria-label>`, `<header>`, `<footer>`); `<ul>` for lists; `<th scope>` / `<caption>` (caption can be visually hidden); `lang` on `<html>` and on foreign-language parts; unique, descriptive `<title>` per page.
- Labels: programmatic association of existing visible labels (`for`/`id`, `aria-labelledby`), `aria-describedby` for existing help and error text, `aria-invalid`, `aria-required`/`required`, `autocomplete` tokens, correct `type`/`inputmode`.
- Keyboard & focus: making custom widgets operable (Enter/Space/arrows per APG), removing positive `tabindex`, focus trap and focus restore in dialogs, focus moved to new content/route heading, skip link that only appears on focus, `:focus-visible` indicator (shows only for keyboard users — mention this in the finding so the team isn't surprised), removing `outline: none` without replacement in favour of a `:focus-visible` style.
- Announcements: route-change announcer, `role="status"`/`aria-live` for async results, toasts and form-submission feedback; `aria-busy` during loading; `aria-expanded`/`aria-controls`/`aria-current`/`aria-selected`/`aria-pressed` state.
- User-preference support: `prefers-reduced-motion` blocks, `forced-colors` fixes (borders/outlines that disappear in Windows High Contrast), removing `user-scalable=no`/`maximum-scale=1`, using `rem` where it doesn't change the default rendering, fixing reflow at 320 px and text-spacing overflow (only visible at those settings), respecting OS font scaling in native apps.
- Tooling: a11y lint rules on, suppressions removed (where fixed), axe in unit/e2e tests, Storybook a11y addon, CI gate.

Caveat to include where relevant: invisible ≠ risk-free. Wrong ARIA is worse than none; changing an element type can change default styles, form submission (`<button>` defaults to `type="submit"`!) or event handling. Each tier-1 finding states how to verify it.

## Tier 2 — Small, non-shocking adjustments

Guidelines (not hard laws — use judgement and explain):

- **Colour**: lightness-only shifts that keep hue and roughly chroma, computed with `scripts/contrast.py`. Brand colour stays recognisable; as a rule of thumb ΔE(OKLab) ≤ ~0.08 is subtle, 0.08–0.15 noticeable but usually acceptable for non-logo uses; larger → tier 3 or a "use the brand colour only for large text/decoration, a darker variant for text" token split (that split itself is tier 2). Placeholder, disabled-looking-but-enabled, muted/secondary text, borders of inputs (3:1, SC 1.4.11), focus ring colour, link colour, icon colour.
- **Size and space**: body text +1–2 px (or ≤ 12.5 %), line-height to ≥ 1.5 for body, paragraph spacing, letter-spacing removal on long text, target sizes up to the 24×24 CSS px minimum (SC 2.5.8) via padding or hit-area pseudo-elements, slightly larger spacing between adjacent targets.
- **Visual cues**: underline links in running text, an icon or text next to colour-only status/validation, visible focus ring styling refinements, visible required-field indicator, error text below fields, persistent visible label where only a placeholder existed *if the layout has room*.
- **Microcopy**: button/link text that is ambiguous ("Klik hier", "Lees meer") made specific, clearer error messages, a hint below a field.
- **Behaviour, small**: pause button on an auto-rotating carousel, removing autoplay of sound/video, extending or allowing extension of a timeout.

## Tier 3 — The road to a 10

Everything that goes beyond tiers 1–2, grouped in the report as:

- **Design**: AAA contrast (7:1, SC 1.4.6), 44×44 targets (SC 2.5.5), enhanced focus appearance (SC 2.4.13), layout restructuring for reflow, redesign of complex widgets (data grids, drag-and-drop with alternatives, maps, charts with data-table alternatives), a high-contrast/dark theme that is actually tested, a full typographic scale review.
- **Content**: plain-language rewrite (B1 level for general audiences; SC 3.1.5), consistent terminology, help (SC 3.2.6), easy-read summaries, sign-language video for key content (SC 1.2.6), extended audio description, transcripts for everything, accessible PDFs or HTML replacements.
- **Features**: alternatives to CAPTCHA and cognitive-function-test authentication (passkeys, magic links; SC 3.3.8/3.3.9), undo/confirm for consequential actions (SC 3.3.4/3.3.6), saved progress in long forms, in-product preferences that *complement* OS settings (text size, motion, density) — never an overlay widget.
- **Validation**: moderated testing with disabled users (screen reader, magnifier, voice control, switch, cognitive), expert manual audit per EN 301 549 where legally relevant.
- **Process**: Definition of Done with a11y criteria, design-system a11y documentation per component, designer/dev/content training, a11y regression tests in CI per key flow, periodic audits, accessibility statement and feedback channel, ownership (a11y champion).

## Edge cases

- **`px` → `rem` font sizes** — tier 1: renders identically at default settings, only differs when the user changes their font size.
- **`aria-required` vs `required`** — `aria-required="true"` is tier 1; the native `required` attribute is tier 2, because it switches on the browser's validation bubble that mouse users see too.
- **Hidden text that changes visible output on copy/select or in reader mode** — still tier 1.
- **Skip link** — tier 1 if it appears only on focus.
- **Focus indicator** — tier 1 when it uses `:focus-visible` on buttons, links and other non-text controls, where browsers show it only for keyboard focus. On **text inputs, textareas and selects, `:focus-visible` matches on mouse focus too**, so a new or changed ring there is visible to everyone → tier 2 (`visual_impact: subtle`). The same fix can therefore be split: tier 1 for buttons/links, tier 2 for fields.
- **Fix that is tier 1 technically but large in effort** (e.g. rebuilding a custom select with proper keyboard support, same look) — still tier 1; effort is a separate field. Note the effort clearly.
- **Same problem, two fixes** — split into two linked findings (tier 1 accessible name now, tier 2 visible text later).
- **Brand colour itself fails** — tier 2 if a subtle shift or a text-only variant token solves it; tier 3 if the brand needs rework.

## Fix ownership (independent of tier and severity)

Tiers describe how visible a fix is; they say nothing about whether the team may make it. In a themed or vendored UI (Hugo/Jekyll themes, a WordPress theme, a copied design system, a submodule) a third of the findings can sit in code the project must not edit. Each finding therefore carries `fix.ownership`:

- `project` and `override` findings are schedulable work and sit in their tier as usual (an override — a project-side template, render hook, stylesheet or config value — is the fix to write up).
- `upstream` findings keep their tier and severity but are listed in a separate block at the end of the tier, with the upstream location and the issue to file; the team cannot schedule them.
- `accepted` findings go to the tier's "Accepted exceptions" block with the reason and the reopen trigger (an upstream fix, a policy change). They still count in the coverage matrix as fails: an accepted exception is not conformance.

Establish early which directories are writable (CLAUDE.md, design docs, `.gitmodules`, vendor folders) and put it in the stack profile; it changes every fix in the report.

## Severity (independent of tier)

| Severity | Meaning |
|---|---|
| blocker | A user group cannot complete a key flow at all (keyboard trap, unlabeled submit, login impossible with screen reader). |
| critical | Key flow completable only with major effort or outside help; or blocker in a secondary flow. |
| serious | Clear WCAG A/AA failure that causes real friction. |
| moderate | AA failure with limited impact, or best-practice issue with real impact. |
| minor | Polish, AAA, or low-reach best practice. |

### Persona verdicts set a floor on severity

Persona task results are not commentary; they drive priority. The merge script applies this automatically from the personas' flow tables, and the orchestrator keeps it unless a persona's evidence doesn't hold up:

- a key flow marked **failed** by any persona → every root-cause finding it names becomes at least **blocker**;
- **completed only with help or a workaround** → at least **critical**;
- `n/a (platform)` and `n/a (not this user's task)` change nothing.

## Scoring rubric (1–10)

An expert estimate, not a measurement — say so in the report.

| Score | Description |
|---|---|
| 1–2 | Blockers in several key flows for several user groups. |
| 3–4 | Blockers in at least one key flow; many AA failures. |
| 5–6 | No blockers in key flows, but many serious AA failures. |
| 7 | Few serious AA failures; core flows usable with AT, with friction. |
| 8 | WCAG 2.2 AA essentially met in key flows; remaining moderate/minor issues. |
| 9 | AA met across the product, many AAA/best-practice items done, automated a11y tests in CI. |
| 10 | AA met everywhere, relevant AAA met, plain language, validated with disabled users, process in place to keep it there. |

Give: current score, projected after tier 1, after tiers 1+2, after tiers 1+2+3. Justify each in one sentence. Tier 3 fully executed and validated = 10 by definition; if some tier-3 items are not realistic for this product, say what the realistic ceiling is.
