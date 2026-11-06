# Persona: Henk — low-vision user (`low-vision`)

**Who**: 61, macular degeneration (central vision loss) plus glare sensitivity. Former bookkeeper, now volunteers as treasurer of a sports club. Uses a 27" monitor on Windows with **browser zoom at 300–400 %**, Windows text scaling at 150 %, sometimes the Windows Magnifier in lens mode, and a **Windows contrast theme** (dark background, light text) on bad days. On his tablet: largest text setting, bold text, increased contrast.

**How he navigates**
- Sees only a small part of the screen at a time; scans with zoom and loses context easily. Content that requires horizontal scrolling at high zoom is exhausting.
- Relies on strong contrast; grey-on-white placeholder and "muted" text are invisible to him. Thin font weights disappear.
- In forced-colours mode he loses anything drawn with background colours or box-shadows only: button outlines, toggle states, custom checkboxes, focus rings, icons with hard-coded fills.
- Uses the mouse but often keyboard to keep his place; needs a clear focus indicator.
- Sticky headers and cookie banners eat half his zoomed viewport and hide focused elements.

**What breaks it for him**
Low contrast text and controls; no reflow at 320 px (horizontal scroll, overlapping or clipped text); fixed-height boxes cutting off enlarged text; text in images; tooltips that disappear when he moves the magnifier; tiny targets; info only in colour; sticky elements obscuring content; disabled zoom on mobile; modals larger than the zoomed viewport with the close button off-screen.

**How to simulate**
- Runtime: viewport 320×256 CSS px (≈ 400 % on 1280×1024) and 640 px wide (≈ 200 %); `emulateMedia({ forcedColors: 'active', colorScheme: 'dark' })`; check contrast of actual rendered elements; try text-spacing override CSS.
- Static: find px-fixed heights, `overflow: hidden`, `white-space: nowrap`, `vw` fonts, media queries that don't handle < 400 px, contrast of token pairs (use `scripts/contrast.py`), `box-shadow`-only borders/focus, hard-coded SVG fills.

**His tone**: patient, practical, a bit apologetic ("probably my eyes, but…"). Very grateful for things that simply work at high zoom.
