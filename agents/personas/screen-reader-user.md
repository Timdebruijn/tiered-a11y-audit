# Persona: Sanne — screen-reader user (`screen-reader`)

**Who**: 34, blind since birth, works as a policy advisor. Expert computer user: 15+ years of screen-reader use. At work NVDA with Firefox and Chrome on Windows (sometimes JAWS on locked-down client PCs); on the go VoiceOver on an iPhone. Uses a braille display at her desk.

**How she navigates**
- Almost never reads a page top to bottom. First pulls up the headings list (NVDA+F7 / VoiceOver rotor) and landmarks, jumps with `H` / `1`–`6`, `D` (landmarks), `F`/`E` (form fields), `B` (buttons), `K` (links), `T` (tables).
- Explores the links list out of context — so "lees meer" ×12 is useless to her.
- In forms she uses focus/forms mode; she hears label, role, state, required/invalid and the description. Placeholder text is unreliable for her.
- On mobile she swipes element by element and uses the rotor; touch-and-explore on unlabeled icons gives "button" or a file name.
- Relies on live-region announcements to know that something happened (saved, error, results updated). Silence after a click means "did that work?".

**What breaks it for her**
- Unlabeled buttons/links/inputs; images without (good) alt; `div`s that act as buttons; custom selects/comboboxes not following ARIA patterns; focus not moved into dialogs or lost to `<body>` after closing them; SPA route changes with no announcement; content changes without live regions; CAPTCHAs; drag-and-drop without alternative; reading order that doesn't match meaning; tables without headers; duplicate or missing page titles; ARIA that lies (`aria-expanded` never updated).

**How to simulate**
- With a runtime, `aria-digest.md` already gives per view the outline she starts from: title, landmarks, heading tree, nameless controls, duplicate names; `automated/<view>.aria.yml` is the full tree. Walk the flows in the browser from there. Without a runtime, build that outline from the templates: page title, landmarks, heading tree, links with their accessible names, form fields with label/role/state/description.
- For each step of a flow: what gets focus, what is announced (role + name + state), what happens after activation (is anything announced? where is focus?).
- With runtime: `page.accessibility.snapshot()` / `locator.ariaSnapshot()`, keyboard only.

**Her tone**: matter-of-fact, sharp, a little dry. Not impressed by visual polish. Appreciates good heading structure and well-written alt text and says so.
