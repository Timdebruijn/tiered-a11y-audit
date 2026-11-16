# Stack profile template

Write `.a11y-audit/stack-profile.md` in this shape. It is the single shared brief for every subagent, so every line must be factual and point to a path. Keep it under ~150 lines.

```markdown
# Stack profile — <repo name>

## Mode and scope
- Skill dir (absolute, quoted in commands): "<path>"
- Mode: full | lean | mini | focused-review | re-audit (and why: project-owned UI files <n>, interactive widgets <n>, forms <yes/no>)
- Writable directories (fix ownership): <e.g. layouts/, assets/css/, i18n/, hugo.toml>; off-limits: <themes/blowfish (submodule), per CLAUDE.md>; policy notes: <e.g. "no copying theme templates into layouts/" from docs/design.md>
- Scope: <whole repo | apps/web only | routes /checkout/* | PR #123 diff>
- Runtime: <URL> (started by the orchestrator with `<command>`, PID <n>, stop at the end) | <URL> (user-provided) | none — static analysis only
- Runtime mutations: read-only | disposable instance, allowed actions: <…>
- Browser tooling for agents: node + Playwright in the scratch dir | Playwright MCP | Chrome MCP | none
- Automated results: .a11y-audit/automated/ (per view: <slug>.json, .aria.yml, screenshots; states in states.json) | none
- Scratch dir for helper scripts (has node_modules): <path> | none
- Previous audit: .a11y-audit/previous/ | none
- Prior accessibility claims in the repo (design docs, README, statement): <path and claim> | none — re-test, never trust
- Report language: <language> (every agent writes its prose in it; nothing is translated afterwards)
- Legal context (only if the user raised it): <EN 301 549 / EAA / public sector / none>

## Stack (from detect_stack.py + verification)
- Framework(s) + versions from lockfile: …
- Router: …                              - Styling: …
- UI/headless libraries: …               - Forms layer: …
- Charts/maps/carousels/editors/dnd: …   - Animation: …
- i18n: … (a11y strings translated? y/n)  - Toasts/notifications: …
- Existing a11y tooling: …               - Suppressed a11y rules: <count> (see detector output)
- Playbook sections to read: <numbers/names>

## Leverage points (paths)
- Design tokens / theme: …
- Global CSS / reset / focus styles: …
- App shell / root layout (html lang, title, landmarks, skip link): …
- Router setup / navigation hooks: …
- Shared components: Button … Link … Icon/IconButton … Input/Field … Modal … Menu … Tabs … Toast … Table …
- Forms layer (validation + error rendering): …
- Live region / announcer (if any): …
- Tests, lint config, CI: …

## Key flows
| # | Flow | Entry route/URL | Main files/components | Why it matters |
|---|---|---|---|---|
| 1 | Home + primary navigation | / | … | every user starts here |
| 2 | <primary task> | … | … | conversion / core purpose |
| 3 | <form or auth> | … | … | … |
| 4 | <content-heavy page> | … | … | … |
| 5 | <widget-heavy page> | … | … | … |

For component-library / design-system repos: flows = the stories or demo pages of the 5–8 most-used components.

## Automated baseline (headline)
- axe (light/dark): <counts and the notable rule ids per view>
- Tab walk: <traps? invisible focus? obscured?>   - Reflow 320 px: <ok | culprits>
- Small targets: <n candidates>   - Text spacing: <clipped?>   - Reduced motion respected: <yes/no>
- Project lint/test output with a11y rules: <summary | none>

## Persona selection
- Core: screen-reader, low-vision, motor-voice, cognitive   (mini audit: screen-reader plus <low-vision | motor-voice> only)
- Added: <colour-blind | deaf | vestibular | older-novice> because <trigger> | none

## Known limits of this run
- …
```
