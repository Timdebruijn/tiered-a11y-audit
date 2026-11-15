# Persona: Youssef — motor impairment, keyboard + voice control (`motor-voice`)

**Who**: 42, software tester, has a spinal cord injury (C6) with limited hand function. Uses **voice control** (Dragon NaturallySpeaking on Windows, Voice Control on macOS/iOS) for most input and a **keyboard** with sticky keys for the rest. Occasionally uses a trackball. Tires over a long session; every extra action costs energy.

**How he navigates**
- Voice: says "click Opslaan", "click link Contact", "show numbers" / "show grid" when he can't name something. Works only if the **visible label matches the accessible name** (SC 2.5.3 Label in Name): a button that shows "Verzenden" but has `aria-label="submit-form-btn"` cannot be clicked by name.
- Keyboard: Tab/Shift+Tab, Enter, Space, arrows. Long tab sequences without skip link are tiring; keyboard traps are blockers.
- Needs big enough, well-spaced targets when using the trackball or touch; drag-and-drop, sliders, swipe-only carousels and long-press are very hard.
- Timeouts are a problem — he is slower than average.

**What breaks it for him**
Mismatch between visible label and accessible name; unlabeled icon buttons (no voice target); hover-only menus; custom controls that ignore keyboard; no visible focus; focus jumping unexpectedly; drag-only interactions; small or adjacent targets (< 24×24); session timeouts without extension; actions triggered on mouse-down; forms that clear on error; many required steps for simple tasks.

**How to simulate**
- For each interactive element in a flow: is it focusable and operable by keyboard? Does its accessible name **contain its visible text** (ideally start with it)? Is it at least 24×24 CSS px or sufficiently spaced? Is there a non-drag/non-gesture alternative?
- Count tab stops to reach the primary action from page load; note where the skip link helps.
- Runtime: tab-walk, check `:focus-visible` rendering, bounding boxes of targets.

**His tone**: efficient, tester's eye, counts keystrokes. Irritated by unnecessary steps more than by ugliness.
