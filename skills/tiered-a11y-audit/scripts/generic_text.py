#!/usr/bin/env python3
"""Link and button texts that say nothing about where they lead, per language of the site being audited.

A scanner can only count the phrases it knows. LANGUAGES is printed next to the count, so that a zero on a site
in another language reads as "not searched" and not as "none there". Add a language by adding a line; the expert
lens still judges link text itself, in any language.
"""
PHRASES = {
    "en": ("read more", "more", "more info", "learn more", "click here", "here", "details"),
    "nl": ("lees meer", "meer", "meer info", "klik hier", "hier", "bekijk"),
    "de": ("mehr lesen", "weiterlesen", "mehr", "mehr erfahren", "hier klicken"),
    "fr": ("lire la suite", "en savoir plus", "plus", "cliquez ici", "ici"),
    "es": ("leer más", "ver más", "más", "más información", "haga clic aquí", "aquí"),
    "pt": ("leia mais", "ver mais", "mais", "saiba mais", "clique aqui", "aqui"),
    "it": ("leggi di più", "leggi tutto", "scopri di più", "clicca qui", "qui"),
}
LANGUAGES = ", ".join(PHRASES)
ALL = sorted({p for phrases in PHRASES.values() for p in phrases}, key=len, reverse=True)      # longest first, for a regex
