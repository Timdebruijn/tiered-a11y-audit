# Framework playbooks

Read only the sections for the detected stack. Each section lists: **native features to use**, **common pitfalls**, **idiomatic fix patterns**, **lint & test**. Versions matter: before recommending a version-gated feature, check the installed version in the lockfile; if unsure whether the installed version has it, say "verify for your version".

## Contents

1. Universal web baseline (applies to every web stack)
2. React
3. Next.js
4. Remix / React Router (framework mode) / TanStack Router
5. Vue
6. Nuxt
7. Angular
8. Svelte & SvelteKit
9. Astro
10. Solid, Preact, Qwik
11. Web components (Lit, Stencil, vanilla custom elements)
12. Ember
13. Server-rendered templates (Django, Rails, Laravel, PHP, Jinja/Twig, Go templates)
14. Static site generators (Hugo, Eleventy, Jekyll)
15. .NET (Blazor, Razor Pages/MVC)
16. Styling: Tailwind, CSS/SCSS, CSS-in-JS
17. Component libraries (Radix/shadcn, React Aria, Headless UI, MUI, Chakra, Bootstrap, Angular Material, Vuetify, PrimeX, Ant Design, Element Plus, Quasar)
18. Charts, maps, carousels, editors, drag-and-drop
19. Animation libraries
20. Native & hybrid: React Native, Flutter, Ionic/Capacitor
21. Testing tools per stack

---

## 1. Universal web baseline

- **Native first**: `<button>`, `<a href>`, `<input>`, `<select>`, `<dialog>` + `showModal()` (built-in focus handling, Esc, top layer, `inert` background), `<details>/<summary>`, Popover API (`popover` attribute) for non-modal popups, `inert` attribute for background content.
- **Visually hidden utility** (if the stack has none):
  ```css
  .visually-hidden:not(:focus):not(:active) {
    clip-path: inset(50%); height: 1px; width: 1px;
    overflow: hidden; position: absolute; white-space: nowrap;
  }
  ```
- **Focus**: `:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }`; never remove outlines without replacement; `scroll-padding-top` equal to sticky header height (SC 2.4.11).
- **Preferences**: `@media (prefers-reduced-motion: reduce)`, `@media (forced-colors: active)` with system colours (`CanvasText`, `ButtonText`, `Highlight`, `LinkText`), `@media (prefers-contrast: more)`, `color-scheme`.
- **Document**: `<html lang>`, unique `<title>`, viewport meta without `maximum-scale`/`user-scalable=no`.
- **Live regions**: one polite and one assertive region rendered at app start, updated by a central announce function.

## 2. React

**Native features**: `useId()` (React 18+) for `id`/`htmlFor`/`aria-describedby` pairing — replaces counters and avoids SSR id mismatches; refs + effects for focus management; `ref` as a regular prop in React 19 (no `forwardRef` needed) — make sure wrapper components pass `ref` and `...rest` to the actual interactive element.

**Pitfalls**: `onClick` on `div`/`span`; prop spreading onto a wrapper instead of the input (`aria-*` and `id` lost); icon components without accessible name; `key`-based remounts that destroy focus; conditional rendering of live regions (region must exist before content); portals for modals without focus trap/`inert`; `dangerouslySetInnerHTML` CMS content without alt/heading control; client-side routing without announcement (React Router, TanStack Router have no built-in announcer).

**Idiomatic fixes**: accessible primitives already in deps (React Aria / react-aria-components, Radix, Headless UI, Ariakit) instead of hand-rolled widgets; a `<VisuallyHidden>` component; an `AnnouncerProvider` with `useAnnounce()`; a `<Field>` component that generates ids with `useId()` and wires `label`/`description`/`error` + `aria-invalid`; TypeScript props that require `aria-label` when there are no text children.

**Lint & test**: `eslint-plugin-jsx-a11y` (use `strict` or at least `recommended`; with flat config `jsxA11y.flatConfigs.recommended`); Testing Library `getByRole`/`getByLabelText`; `jest-axe` or `vitest-axe`; `@axe-core/playwright`; Storybook `@storybook/addon-a11y`.

## 3. Next.js

**Native features**:
- **Route announcer** built in (App Router and Pages Router): on client navigation it announces `document.title`, falling back to the first `<h1>`, then the pathname. So **unique, descriptive titles per route** via the Metadata API (`export const metadata` / `generateMetadata`, `title.template` in the root layout) are the fix for most "navigation not announced" issues. It does *not* move focus — add focus management to `<h1>`/`<main>` if the persona walkthroughs show disorientation.
- `next/link` renders a real `<a>`; don't wrap it around buttons.
- `next/image` requires `alt` — use `alt=""` for decorative images, never filler like "image".
- `<html lang>` is set in the root layout: with i18n (`app/[lang]/layout.tsx`), set `lang={params.lang}`.
- `eslint-config-next` includes a subset of `jsx-a11y` rules; add the full `jsx-a11y` recommended/strict config for more coverage.

**Pitfalls**: same title on every page (announcer then says the same thing); `loading.tsx` spinners without accessible text; Server Actions form feedback not announced (`useActionState`/`useFormStatus` results need a live region); `metadata.viewport` with `maximumScale: 1` or `userScalable: false`.

## 4. Remix / React Router (framework mode) / TanStack Router

No built-in route announcer or focus management — verify for the installed version. Implement once in the root: on location change, set focus to the page `<h1>` (with `tabIndex={-1}`) or announce the new title via a live region. React Router's `<ScrollRestoration>` handles scroll, not focus. Use `<Form>`/`useNavigation` state to announce pending/complete; render action errors next to fields with `aria-describedby`.

## 5. Vue

**Native features**: `useId()` (Vue 3.5+) for stable ids; `<Teleport to="body">` for modals (then add focus trap, `inert` on app root, restore focus); template refs + `nextTick` for focus management; `v-bind="$attrs"` with `inheritAttrs: false` to place `aria-*`/`id` on the actual input in wrapper components.

**Pitfalls**: `@click` on non-interactive elements; attribute fallthrough putting `aria-label` on a wrapper `div`; `v-if` live regions; `v-html` CMS content; Vue Router navigations without focus/announcement.

**Idiomatic fixes**: `router.afterEach` hook that updates `document.title` (from `meta.title`) and moves focus to the main heading or announces via `@vue-a11y/announcer`; a composable `useAnnouncer()`; accessible primitives (Reka UI — formerly Radix Vue —, Headless UI for Vue, Ark UI) where present.

**Lint & test**: `eslint-plugin-vuejs-accessibility`; `@testing-library/vue`; `vitest-axe`; Playwright + axe.

## 6. Nuxt

**Native features**: `<NuxtRouteAnnouncer />` component and `useRouteAnnouncer()` composable (Nuxt 3.12+) — put it in `app.vue`/the default layout; `useHead`/`useSeoMeta` for per-page titles and `htmlAttrs: { lang }`; `@nuxtjs/i18n` provides `useLocaleHead()` to set `lang`/`dir`/`hreflang`; `<NuxtImg>` (Nuxt Image) passes `alt`.

**Pitfalls**: route announcer not added; titles identical; page transitions without reduced-motion handling (`app.pageTransition` — disable or shorten under `prefers-reduced-motion`).

## 7. Angular

**Native features** (`@angular/cdk/a11y`):
- `FocusTrap` / `cdkTrapFocus` (with `cdkTrapFocusAutoCapture`), `FocusMonitor` (focus origin: keyboard/mouse/touch/program — for `cdk-keyboard-focused` styling), `LiveAnnouncer` (central announcements), `ListKeyManager` / `FocusKeyManager` / `ActiveDescendantKeyManager` (roving focus and arrow-key navigation for custom lists/menus), `InteractivityChecker`, `AriaDescriber`, `HighContrastModeDetector` (adds `cdk-high-contrast-*` classes), `cdk-visually-hidden` class (`@include cdk.a11y-visually-hidden()`).
- CDK `Dialog`/`Overlay` and Angular Material dialogs handle focus capture and restore.
- Router: `TitleStrategy` (custom strategy for consistent unique titles, or `title` in route config); on `NavigationEnd` move focus to the main heading and/or use `LiveAnnouncer`.

**Pitfalls**: `(click)` on `div`; ARIA bindings with `[aria-label]` instead of `[attr.aria-label]` in versions without direct ARIA property binding — verify for the installed version; `mat-icon-button` without `aria-label`; `mat-icon` not `aria-hidden` when decorative; custom form controls (`ControlValueAccessor`) that don't expose label/`aria-invalid`; `*ngIf` on live regions; `OnPush` updates that never reach the announcer.

**Lint & test**: `@angular-eslint/template` accessibility rules (e.g. `alt-text`, `elements-content`, `label-has-associated-control`, `click-events-have-key-events`, `interactive-supports-focus`, `role-has-required-aria`, `valid-aria`, `table-scope`, `no-autofocus`, `no-distracting-elements`; recent versions bundle these in an `accessibility` config); Angular Material component harnesses; Testing Library for Angular; Playwright/Cypress + axe.

## 8. Svelte & SvelteKit

**Native features**:
- The **Svelte compiler emits a11y warnings** (`a11y_*` codes in Svelte 5, `a11y-*` in Svelte 4). They are a free audit: run the build/`svelte-check` and collect them. Look for suppression: `<!-- svelte-ignore a11y… -->`, `warningFilter`/`onwarn` in `svelte.config.js`/Vite config.
- **SvelteKit** after client-side navigation resets focus to `<body>` and announces the new page via a live region using the page `<title>` → set a unique `<title>` in `<svelte:head>` on every page. `afterNavigate` for custom focus behaviour; `data-sveltekit-keepfocus` on forms/links where focus must stay (e.g. search-as-you-type).
- Form actions + `use:enhance`: render returned errors with `aria-describedby`/`aria-invalid` and announce results.

**Pitfalls**: suppressed warnings; missing per-page titles (announcement then says nothing useful); `on:click`/`onclick` on `div`s with suppressed `a11y_click_events_have_key_events`; transitions without reduced-motion (Svelte's `transition:` — use `prefersReducedMotion` from `svelte/motion` in Svelte 5 versions that provide it — verify — or a media-query store).

**Lint & test**: `svelte-check`, `eslint-plugin-svelte`, `@testing-library/svelte`, Playwright + axe; Bits UI / Melt UI primitives where present.

## 9. Astro

**Native features**: dev toolbar **Audit** app (flags a11y issues in dev — look for it being disabled via `devToolbar: { enabled: false }`); `<ClientRouter />` (formerly `<ViewTransitions />`) includes a route announcer and has fallbacks for reduced motion — verify for the installed version; `astro:assets` `<Image>` requires `alt`; islands use their own framework's rules (apply the React/Vue/Svelte sections for each island).

**Pitfalls**: `lang` not set in the base layout; custom view-transition animations ignoring `prefers-reduced-motion`; islands hydrated `client:visible` that steal or lose focus.

## 10. Solid, Preact, Qwik

No built-in route announcers that you should assume — check the router (`@solidjs/router`, `preact-iso`, Qwik City) for the installed version. Apply the React patterns (central announcer, focus to `<h1>` on navigation, `<Field>` with generated ids). Lint: `eslint-plugin-jsx-a11y` works for JSX-based stacks; Qwik and Solid have their own ESLint plugins with some rules. Kobalte (Solid) and Ark UI provide accessible primitives.

## 11. Web components (Lit, Stencil, vanilla)

- **Shadow DOM boundary**: `aria-labelledby`/`aria-describedby`/`for` cannot reference ids across shadow roots. Fix: keep label and control in the same root, use slots, or `ElementInternals` (`attachInternals()`) to set `role`/`ariaLabel`/states on the host; form-associated custom elements (`static formAssociated = true`) for custom inputs.
- `delegatesFocus: true` on `attachShadow` for components wrapping a focusable element.
- Don't put `role` on the host *and* the inner element.
- Test with axe (it pierces open shadow roots) and Playwright role locators.

## 12. Ember

`ember-template-lint` (recommended config includes many a11y rules — check for disabled ones), `ember-a11y-testing` (axe in tests), `ember-a11y-refocus` (route-change focus and announcement), `ember-page-title` for unique titles.

## 13. Server-rendered templates (Django, Rails, Laravel, PHP, Jinja/Twig, Go templates)

Leverage is in **base layouts and partials/includes** (one fix → all pages) and in **form helpers**:
- **Django**: form rendering (`{{ form }}`, `as_div`, field templates) generates `<label for>`; recent versions add `aria-describedby` for help text and `aria-invalid` for errors — verify for the installed version and check custom widget templates override them. Set `<html lang="{{ LANGUAGE_CODE }}">`; `{% translate %}` for a11y strings too.
- **Rails**: `form_with` + `f.label`; `aria:` hash (`aria: { describedby: … }`); `content_for :title` per page; `I18n.locale` for `lang`; Turbo navigation — Turbo Drive replaces the body: handle focus/announcement on `turbo:load` (verify current behaviour for the installed Turbo version).
- **Laravel**: Blade components for form fields with error wiring (`@error`), `app()->getLocale()` for `lang`; Livewire/Inertia: apply SPA rules (announce/focus on navigation, live regions for updates).
- **htmx**: swapped content is not announced and focus may be lost — add `hx-swap` focus handling (`focus-scroll`, or `htmx:afterSwap` handler to focus/announce), live regions on swap targets.

## 14. Static site generators (Hugo, Eleventy, Jekyll)

- **Hugo**: in a themed site the theme directory (`themes/<name>/`, usually a submodule) is off limits, so the project's levers are `layouts/` overrides (same relative path wins), Markdown **render hooks**, its own CSS/JS assets, `i18n/`, front matter and `hugo.toml`. Render hooks: `layouts/_default/_markup/render-image.html` (enforce/propagate alt from Markdown or page-resource front matter `params.alt`, `figure`/`figcaption`, lazy loading), `render-link.html` (mark external links/downloads with visually-hidden text; prefer `[params.article] externalLinkForceNewTab = false`-style theme options to new tabs), `render-heading.html` (an anchor link placed *inside* the heading element becomes part of the heading's accessible name — "Title Anchor" — so put it after the text and give it `aria-hidden="true"` plus `tabindex="-1"`, or a visually-hidden label of its own outside the heading). Accessibility strings (search placeholder, skip-link text, menu toggle label, "opens in new tab") live in `i18n/<lang>.yaml` and must exist **per language** — an untranslated key silently shows the English string or the key name on the other language; `hugo --printI18nWarnings` finds them and `--panicOnWarning` turns that into a CI gate the a11y checks can hang on. `aria-current="page"` on menu items from `.IsMenuCurrent` / `.HasMenuCurrent` (also for ancestors). `lang` from `.Site.Language.LanguageCode` (`.Site.LanguageCode` in older versions) in `baseof.html`; per-page `<title>` via `.Title`; `hreflang` alternates for multilingual sites. Build output (`public/`) and `resources/_gen/` are never the thing to audit or edit.
- **Eleventy**: `@11ty/eleventy-img` errors when `alt` is missing (good — don't work around it); Markdown-it plugins for attributes; `lang` in base layout from data cascade.
- **Jekyll**: includes and layouts; `jekyll-seo-tag` for titles; kramdown attribute lists for alt/lang.
- For all: test the **built output** with `pa11y-ci` or Playwright + axe against the generated HTML, and `html-validate` for structural errors.

## 15. .NET (Blazor, Razor Pages/MVC)

- **Blazor**: `<FocusOnNavigate RouteData="@routeData" Selector="h1" />` in the `Router` (included in the templates — check it wasn't removed); `<PageTitle>` per page; `InputText`/`InputSelect` + `<label for>`; `ValidationMessage` with `aria-describedby` wiring (not automatic — wrap in a field component); `ElementReference.FocusAsync()` for focus management; JS interop for live regions.
- **Razor Pages/MVC**: tag helpers (`asp-for` on `<label>` and `<input>`) produce associations; `asp-validation-for` spans need `aria-describedby` links; `<html lang>` from request culture.

## 16. Styling

- **Tailwind**: `sr-only`/`not-sr-only`; `focus-visible:` variants; `motion-safe:`/`motion-reduce:`; `forced-colors:` variant; `contrast-more:`; `aria-*:` and `data-*:` variants to style by state (keeps state and visuals in sync). Colours live in `tailwind.config.*` (v3) or `@theme` in CSS (v4) — fix contrast there once. **Outline gotcha**: in v3 `outline-none` sets a transparent outline (still visible in forced-colours mode); in v4 that behaviour is `outline-hidden` and `outline-none` truly removes the outline — check the version before judging focus styles. Arbitrary values (`text-[#9ca3af]`) bypass tokens: grep for them.
- **CSS/SCSS/CSS modules**: custom properties / SCSS variables as the token layer; a global focus style; `rem` for font sizes and spacing that should scale; avoid `height` on text containers; `@media (forced-colors: active)` fixes in the reset.
- **CSS-in-JS** (styled-components, Emotion, vanilla-extract, Stitches, Panda): theme object is the token layer; global styles for focus and motion; `shouldForwardProp` issues dropping `aria-*` props on styled wrappers — check.

## 17. Component libraries

- **Radix / shadcn/ui**: accessible primitives with keyboard and focus handling. `Dialog`/`AlertDialog`/`Sheet` require a `DialogTitle` (wrap in `VisuallyHidden` if no visible title) and should have a description or `aria-describedby={undefined}` deliberately; `asChild` must wrap an interactive element; icon-only triggers need `aria-label`. shadcn copies source into the repo — fixes go in `components/ui/*`.
- **React Aria / react-aria-components**: strongest built-in behaviour (interactions, i18n, announcements via `@react-aria/live-announcer`). Check labels are passed (`aria-label` or `<Label>`), and that custom styling keeps focus rings (`data-focus-visible`).
- **Headless UI** (React/Vue): built-in keyboard handling and ARIA; provide labels (`Label`, `Description` components); don't break `as` props.
- **MUI**: `createTheme({ palette: { contrastThreshold: 4.5 } })` — default is 3, raising it makes auto-computed text-on-colour meet AA (tier 2, visible). `IconButton` needs `aria-label`; `TextField` uses `label` (not placeholder only) and `helperText`/`error` (wired to `aria-describedby`); `Tooltip` is not a label. `disableRipple`/`disableFocusRipple` can remove the only focus cue — check `focusVisible` styles.
- **Chakra UI**: `VisuallyHidden`, `FormControl`/`Field` wiring, `SkipNavLink` (v2); theme tokens for contrast.
- **Bootstrap 5**: `.visually-hidden`, `.visually-hidden-focusable` (skip links); `$min-contrast-ratio` (default 4.5) used by `color-contrast()` to pick text colour on theme colours; `$enable-reduced-motion` (default true). Brand overrides of `$primary` often break contrast of `.btn-primary` and links — check `$link-color`.
- **Angular Material**: see Angular; theme palettes and `mat.theme` tokens; `MatIconRegistry` icons need labels.
- **Vuetify / PrimeVue / PrimeNG / PrimeReact / Ant Design / Element Plus / Quasar**: each has per-component accessibility docs — check the components used against them. Most expose `aria-label` props and theme tokens for colours; data tables and date pickers are the usual weak spots (verify keyboard behaviour at runtime).

## 18. Charts, maps, carousels, editors, drag-and-drop

- **Highcharts**: accessibility module (`highcharts/modules/accessibility`) — enable it; keyboard navigation, screen-reader summaries, sonification; `accessibility.description`.
- **ECharts**: `aria: { enabled: true }` generates descriptions; `aria.decal.show: true` adds patterns for colour-blind users.
- **Recharts**: `accessibilityLayer` prop adds keyboard navigation and ARIA (default on in Recharts 3 — verify version).
- **Chart.js / D3 / canvas charts**: no built-in text alternative — provide a summary + data table (visually hidden or toggleable), `role="img"` + `aria-label` on the canvas, patterns via plugins.
- **Maps** (Leaflet, Mapbox, Google Maps): provide a list/table alternative of locations; keyboard pan/zoom; marker names.
- **Carousels**: Swiper has an `a11y` module (on by default; localise messages) — add pause/autoplay control; Splide has accessibility options; avoid Slick for new work.
- **Rich-text editors** (TipTap/ProseMirror, Lexical, Quill, CKEditor, TinyMCE): toolbar buttons labelled, editor labelled (`aria-label`/`aria-labelledby`), Esc/Tab behaviour documented.
- **Drag-and-drop**: dnd-kit (keyboard sensor + `announcements`/`screenReaderInstructions`, localise them), `@atlaskit/pragmatic-drag-and-drop` (has accessibility guidelines and a live-region helper) — always add a non-drag alternative (move up/down buttons, "move to…" menu).

## 19. Animation libraries

- **Framer Motion / Motion**: `<MotionConfig reducedMotion="user">` at app root; `useReducedMotion()` for custom logic.
- **GSAP**: `gsap.matchMedia()` with `(prefers-reduced-motion: reduce)`.
- **AOS / ScrollReveal / Lottie**: disable or render final state under reduced motion; Lottie: `autoplay` false and show static frame.
- **View Transitions API**: wrap `::view-transition-*` animations in `@media (prefers-reduced-motion: no-preference)`.

## 20. Native & hybrid

- **React Native**: `accessible`, `accessibilityLabel`/`aria-label`, `accessibilityRole`/`role`, `accessibilityState`/`aria-*` state props, `accessibilityHint`, `importantForAccessibility`, `accessibilityLiveRegion` (Android) / `AccessibilityInfo.announceForAccessibility`, `AccessibilityInfo.isReduceMotionEnabled`/`isScreenReaderEnabled`. **Never** set `allowFontScaling={false}` globally; use `maxFontSizeMultiplier` sparingly. Touch targets ≥ 44×44 pt (iOS) / 48×48 dp (Android) via `hitSlop` or size. Test with `@testing-library/react-native` `getByRole`, and real VoiceOver/TalkBack. `eslint-plugin-react-native-a11y`.
- **Flutter**: `Semantics`, `MergeSemantics`, `ExcludeSemantics`, `Tooltip`/`semanticLabel` on icons and images; respect `MediaQuery.textScalerOf` (don't clamp text scaling); `MediaQuery.disableAnimationsOf`; min tap target 48×48 (`MaterialTapTargetSize.padded`). Widget tests: `expect(tester, meetsGuideline(androidTapTargetGuideline))`, `iOSTapTargetGuideline`, `labeledTapTargetGuideline`, `textContrastGuideline`; `SemanticsDebugger` for manual review.
- **Ionic / Capacitor**: web rules apply inside the WebView; Ionic components carry ARIA but need labels (`aria-label` on `ion-button` with icon only); respect the device text size via Dynamic Type support (`--ion-dynamic-font`/Capacitor Text Zoom plugin — verify).
- Native apps are evaluated against WCAG via EN 301 549 clause 11 / WCAG2ICT.

## 21. Testing tools per stack

| Need | Tools |
|---|---|
| Lint | jsx-a11y (React/Preact/Solid JSX), vuejs-accessibility, @angular-eslint/template, eslint-plugin-svelte + compiler warnings, ember-template-lint, eslint-plugin-react-native-a11y, html-validate (any HTML output) |
| Unit/component | jest-axe / vitest-axe, Testing Library role queries, Storybook addon-a11y + test-runner, Angular Material harnesses, Flutter guideline matchers |
| E2E/runtime | @axe-core/playwright, cypress-axe, pa11y / pa11y-ci, Lighthouse CI (axe subset) |
| Manual | Screen readers (NVDA, VoiceOver, TalkBack), keyboard, 400 % zoom, Windows contrast themes, OS reduce-motion, text-spacing bookmarklet |
