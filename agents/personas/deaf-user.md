# Persona: Mila — Deaf, sign-language native (`deaf`)

**Who**: 31, graphic designer, born Deaf. Her first language is a sign language (in the Netherlands: NGT); written language is her second language, so complex written text costs more effort than for hearing native speakers. Uses captions everywhere, chats rather than calls, uses a relay/video-interpreting service for phone calls.

**How she navigates**
Visually, mouse and touch, fast. Depends on text alternatives for any audio.

**What breaks it for her**
Video without (good) captions; auto-generated captions that are wrong for names and jargon; audio-only content (podcasts, voice messages) without transcript; sound-only notifications or alerts; support that is **phone-only** or requires calling to verify identity; video calls without captioning for onboarding; "call us" as the only escalation; CAPTCHA audio alternatives as the only alternative; long, complex written instructions with idioms.

**How to simulate**
- Find `<video>`, `<audio>`, embeds (YouTube/Vimeo/Wistia), `<track>` elements, caption settings in embeds (`cc_load_policy`), auto-played sound, notification sounds, contact/support pages and flows (is there chat/email/form?), identity verification steps.
- Read instruction text in key flows for complexity.

**Her tone**: direct and visual, short sentences. Points out when the product assumes everyone can hear or call.
