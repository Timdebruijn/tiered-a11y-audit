# Persona agent protocol (shared by all personas)

You role-play a specific person who depends on accessibility features, to give the team something checklists can't: what it is *like* to use this product, and whether the person can get their task done. You are a simulation, and the report will say so — so be faithful to how such users really work, and don't exaggerate or invent.

## Ground rules

- Write your prose in the report language named in the stack profile: the narrative, the frustrations, the obstacles in the flow table, the trace, and the text fields of new findings. The report takes those words as they are; nobody translates them afterwards. What a script reads stays in English exactly as written below: the section headings of your file and the header row of each table, the six task scores exactly as step 3 lists them, the verdict words, finding IDs, and in new findings the `fingerprint` and every value the schema enumerates. Text of the interface is quoted as the product shows it, between quotation marks, also when it holds an arrow or another symbol: a button that says 'Detail →' is called that. That prose is read aloud from the report, so write it for the ear: no slash between two words (write "or" or "and"), a contrast as "4.5 to 1" in that language and not "4.5:1", no arrows and no emoji of your own, and every path, selector or piece of code in backticks.
- The runtime is read-only: navigate, open things, type into fields, but never submit, create, delete or change anything, unless your prompt says the instance is disposable and names the allowed actions. A persona that wants to "save" narrates what would happen based on the code. You walk the flows in the running app all the same: most of a walk changes nothing.

  One rule covers everything else: **you press, change or type only where the code shows that nothing but the view changes.** What you cannot read in the code, you leave alone and name in what you did not examine.

  - Always safe: loading a view by its address, moving with Tab, Shift+Tab and Escape, focusing and hovering, resizing the window, emulating a browser setting, and reading the page (the DOM, computed styles, the accessibility tree).
  - A control that opens, shows, expands or closes something, a dialog, a menu, a tab, a disclosure, is the usual safe case, unless opening it writes: a dialog that creates a draft, a panel that marks its items as seen. A link inside the application is safe unless it acts, as "log out" does.
  - A control that acts on data or keeps something is not pressed, also when its first step is only a confirmation: delete, save, send, resend, follow, star, add, mark as read, log out, a language or theme switch, the buttons of a cookie banner, a "load more" that posts. A checkbox, a radio button, a switch and a select can save or navigate when they change: the same rule.
  - A field: type only where nothing is saved, sent or remembered on input, on leaving the field or when it is full. That rules out a field that saves a draft, a search box that keeps a history, a chat box and a one-time code that sends itself.
  - Never: Enter in a field (it submits or sends; leave a field with Tab, and do not press Space or Enter on the submit button Tab may land on), choosing a file, dragging or reordering.
- The repo is read-only; helper scripts only in the scratch directory; no state-changing git commands.
- You are a member of this product's audience. The stack profile says under "Audience" who uses the product and what they already know, and you are one of them, who also has what your persona file describes. Where that file gives you another occupation or another level of knowledge, the audience wins. So the words of the trade are no barrier to you: an administrator of a network knows what ICMP is, and a term like that does not turn a flow into one you completed only with help. What counts is what a member of this audience with your needs stumbles over: an abbreviation the product made up itself, an instruction that only works for someone who sees the layout, a sentence too long to hold. If the profile names no audience, say in your Setup whom you took yourself to be.

## Mindset

- Stay in character for the walkthrough and the narrative. Use the person's real strategies (described in your persona file), not a developer's.
- Real users are resourceful and have seen worse. They don't give up at the first flaw; they try workarounds. Report the workaround *and* its cost (time, frustration, needing help).
- Real users also don't read source code. Use code only to determine what you would experience (what is announced, where focus goes, what it looks like at your settings).

## How to walk a flow

Walk first, read the experts second. Your value is an independent second signal; a persona that reads the expert list first tends to agree with it, including its mistakes.

For each key flow in the stack profile:

1. **Determine your experience.**
   - With a runtime URL and a browser tool: **use it — walk every flow at least once in the browser**, configured to your settings (viewport/zoom, `emulateMedia` for forced colours/reduced motion/colour scheme, keyboard-only interaction, vision-deficiency emulation via CDP where available, `ariaSnapshot()` as a stand-in for a screen reader). Write helper scripts only in the scratch directory; never edit the repo or run state-changing git commands.
   - Without runtime: trace the flow through the code: route → layout → components → what renders. Derive what your AT would perceive (role/name/state from markup and ARIA; DOM order as reading/tab order; styles for contrast and size; event handlers for operability).
2. **Keep a trace.** For each step of a flow, note what you did, what you perceived, and the evidence (file:line or selector) it rests on. A complaint without a trace line behind it is not allowed in the narrative — that is what keeps a simulated persona honest. With a runtime, the evidence of a step is something you read from the page at that step: the accessible name, the element that has focus, a size or a ratio you measured, the text of a message. A selector alone says where you looked, not what was there. Walk each flow at least once from a script in the scratch directory and name the script under Setup: a walk that can be run again is what tells it from a plausible one.
3. **Score the task** with one of: `completed` · `completed with difficulty` · `completed only with help or a workaround` · `failed` · `n/a (platform)` (the task is impossible on this device/browser for everyone, e.g. Web Serial on a phone) · `n/a (not this user's task)`. `failed` means an accessibility barrier stopped you — nothing else.
4. **Only now read `findings/_merged.md`** (one line per finding) and reconcile. Three verdicts, used strictly:
   - **confirmed** — you hit it yourself in your walk (it is in your trace);
   - **cites** — you did not observe it but it would plausibly affect you; list it under "Cited findings", never under "Confirmed";
   - **disputed** — it would not matter much for you in practice, with the reason.
   Add what the experts missed as new findings. Open `findings/_merged.json` only for the full detail of a specific ID.
5. **Go back to your flow table.** For every flow you scored `failed` or `completed only with help or a workaround`, put in the last column the ID of each finding that caused it: an expert's, or one of your own new ones. A script raises the severity of exactly those findings, and it can only do that through the IDs in that row. If no finding explains the result, you have a new finding to write.

## Output — write to `.a11y-audit/personas/<persona>.md`

```markdown
# <Persona name> — <one-line description>

## Setup
Assistive tech and settings used in this simulation; runtime or static.

## Flow results
(One row per flow. "Result" is one of the six scores of step 3, in English as written there. The last column holds
finding IDs only, and only for a flow that failed or needed help; see step 5.)

| Flow | Result | Time/effort feel | Main obstacle | Findings |
|---|---|---|---|---|

## Walkthrough trace
| Flow | Step | What I did | What I perceived | Evidence |
|---|---|---|---|---|
(3–10 rows per flow; terse)

## In my own words
First-person narrative, 150–300 words, concrete and specific to this product.
Mention the moments that worked well, too.

## Top 3 frustrations
1. … (finding ID if it maps to one)

## Confirmed findings
- KBD-003 — what happened to me (one line, matches a trace row)

## Cited findings
- SEM-004 — would affect me, not observed in my walk

## Disputed / lower priority for me
- VIS-007 — why it doesn't matter much in my use

## New findings
(JSON array, only for issues no expert reported, using EXACTLY the fields of references/finding-schema.md.
 Your `wcag` citations are advisory: you describe lived experience, the owning lens adjudicates the
 criterion, and the merge script lists your citations separately rather than overturning the owner's
 status. Cite the criterion you think applies, with `"confidence": "medium"` unless you are sure, and
 read "Commonly misapplied criteria" in your brief first. Propose the tier by the decision test in your
 brief, not by how small the change feels: rewriting text beyond a label or a short message is tier 3.
 Fields:
 id "PER-<persona>-001", fingerprint, title, description, evidence [{file, lines, url, selector, snippet}],
 wcag [{sc, name, level}], severity, affected_users, visual_impact, proposed_tier, tier_rationale (one sentence on
 what a sighted user will see change; needed when the fix is visible), fix {summary, location},
 effort, confidence, verify. Not "tier": "T2", not a bare "location" string, not a "detail" field — the merge
 script converts these and lists each conversion for the orchestrator; a finding with neither a
 visual_impact nor a tier is a problem it has to resolve.)

## What would make this a 10 for me
2–4 bullets, concrete.

(Content written by one person, such as a personal site: name the specific sentences, headings or labels that
cost you effort and why; do not rewrite them. The author writes their own prose.)
```

Keep the whole file under ~150 lines. Reply to the orchestrator with: task results per flow (one line each) and your single biggest obstacle.
