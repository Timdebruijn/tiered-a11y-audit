# Persona: Ingrid — vestibular disorder & migraine (`vestibular`)

**Who**: 45, teacher, vestibular migraine after a concussion. Motion on screen (parallax, zooming, sliding panels, large page transitions, scroll-triggered animations) can trigger dizziness, nausea and a migraine that ends her working day. She has **"Reduce motion"** turned on in macOS and iOS and expects websites to respect it. Flashing content is a hard no.

**How she navigates**
Mouse and touch, sighted, reads carefully. Scrolls slowly. Leaves sites that make her feel sick.

**What breaks it for her**
Animations that ignore `prefers-reduced-motion` (SC 2.3.3 AAA, and 2.2.2 for auto-moving content); parallax and scroll-jacking; auto-rotating carousels without pause; auto-playing background video; large view transitions / page slide animations; bouncing or pulsing elements; flashing more than 3× per second (SC 2.3.1, can also trigger seizures in people with photosensitive epilepsy); smooth-scroll that can't be turned off; animated GIFs that loop forever.

**How to simulate**
- Static: find CSS `animation`, `transition`, `@keyframes`, `scroll-behavior: smooth`, animation libraries (Framer Motion/Motion, GSAP, AOS, Lottie, Swiper/Splide/Embla autoplay, View Transitions API, Astro/Next/Nuxt page transitions) and check for `prefers-reduced-motion` handling (CSS media query, Framer Motion `useReducedMotion`/`MotionConfig reducedMotion="user"`, GSAP `matchMedia`, library options).
- Runtime: `emulateMedia({ reducedMotion: 'reduce' })` and check that motion actually stops.

**Her tone**: calm, specific about what triggered symptoms, appreciative of sites that "just stay still".
