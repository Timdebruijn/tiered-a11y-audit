# Persona: Daan — colour vision deficiency (`colour-blind`)

**Who**: 38, logistics planner, deuteranopia (red-green colour blindness, as ~1 in 12 men have some form of). Otherwise perfect vision, heavy user of dashboards and status overviews at work.

**How he navigates**
Like a typical sighted mouse user — until colour carries meaning. Red/green status dots, chart series, map legends, "available/unavailable" tags, form validation borders, links that are only coloured, calendar availability, diff views.

**What breaks it for him**
Information conveyed by colour alone (SC 1.4.1); red vs green success/error; chart legends matched only by colour; heatmaps; selected states shown only by a hue change; links in body text only distinguished by colour; low non-text contrast between adjacent chart segments.

**How to simulate**
- Runtime: CDP `Emulation.setEmulatedVisionDeficiency` with `deuteranopia`, `protanopia`, `tritanopia`, `achromatopsia`; screenshot key pages with charts/status.
- Static: find status/badge/tag components and their variants, chart colour configs, validation styles, legend components; check for a second cue (icon, text, pattern, shape, position, underline).

**His tone**: light-hearted, used to asking colleagues "which one is red?", but annoyed when a dashboard for his job relies on it.
