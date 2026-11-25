#!/usr/bin/env python3
"""Detect the frontend stack and existing accessibility tooling of a repository.

Usage:
    python3 detect_stack.py <repo-root> [--json] [--max-files N]

Pure standard library. Read-only. Prints a human summary (default) or JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", ".nuxt", ".output", ".svelte-kit",
    ".astro", "out", "coverage", ".venv", "venv", "__pycache__", "target",
    "public/build", ".turbo", ".cache", ".parcel-cache", "storybook-static", ".a11y-audit",
    "Pods", ".dart_tool", "bin", "obj", "resources/_gen", "_site", ".jekyll-cache", ".hugo_build.lock",
}
# Build output of static site generators: never part of the stack the team edits.
BUILD_DIRS = {"public", "_site", "out", "dist", "build", "docs/_build", "site"}
# Vendored code: a theme, a submodule, a copied design system. Counted separately, never as "your stack".
VENDOR_DIRS = {"vendor", "themes", "third_party", "third-party", "external", "libs", "lib/vendor"}

SSG_CONFIGS = ("hugo.toml", "hugo.yaml", "hugo.json", "_config.yml", ".eleventy.js",
               "eleventy.config.js", "mkdocs.yml")
# public/ and site/ hold generated output for a static-site generator, but source for
# CRA, Vite and Next: public/index.html carries <html lang>, the title and the viewport meta.
GENERATED_ONLY_BY_SSG = {"public", "site"}


# A document in which the project states its own accessibility: ACCESSIBILITY.md (after SECURITY.md), a11y.md, a
# statement. By its name, in the languages listed; add a language by adding a word. Documents only: a page of the
# product with such a name is interface, and the scanners count it as that.
A11Y_DOC = re.compile(r"(?i)^(?:accessibility|a11y|toegankelijkheid|barrierefreiheit|accessibilit[eé]|accesibilidad|accessibilit[aà])"
                      r"[\w .-]*\.(?:md|mdx|markdown|txt|rst|adoc)$")


def ssg_generates_public(root):
    """True when a static-site generator in this repo writes into public/ or site/."""
    # ponytail: marker sniff, not a full SSG probe; add generators as they turn up.
    if any((root / name).exists() for name in SSG_CONFIGS):
        return True
    cfg = root / "config.toml"
    try:
        return cfg.exists() and "baseURL" in cfg.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def file_size(p):
    """Size in bytes, or None when the path cannot be stat'ed (dangling symlink, permissions)."""
    try:
        return p.stat().st_size
    except OSError:
        return None


# Infrastructure directories: templates in here are not UI — counted separately, otherwise ignored.
INFRA_DIRS = {"ansible", "terraform", "infra", "infrastructure", "deploy", "deployment", "k8s", "kubernetes", "helm",
              "playbooks", "roles", "ops", "docker", "nginx", "systemd"}
CSP_RE = re.compile(r"Content-Security-Policy|contentSecurityPolicy|helmet\(|csp\s*[:=]", re.IGNORECASE)
CONFIG_NAMES = {"Caddyfile", "_headers", "netlify.toml", "vercel.json", "nginx.conf", "default.conf", "haproxy.cfg"}

# dependency name (exact or prefix ending in '/') -> (category, label)
DEPS: dict[str, tuple[str, str]] = {
    # frameworks / meta-frameworks
    "react": ("framework", "React"), "react-dom": ("framework", "React DOM"),
    "next": ("framework", "Next.js"), "@remix-run/react": ("framework", "Remix"),
    "react-router": ("router", "React Router"), "react-router-dom": ("router", "React Router"),
    "@react-router/dev": ("framework", "React Router (framework mode)"),
    "@tanstack/react-router": ("router", "TanStack Router"), "@tanstack/start": ("framework", "TanStack Start"),
    "@tanstack/react-start": ("framework", "TanStack Start"),
    "vue": ("framework", "Vue"), "nuxt": ("framework", "Nuxt"), "vue-router": ("router", "Vue Router"),
    "@angular/core": ("framework", "Angular"), "@angular/router": ("router", "Angular Router"),
    "@angular/cdk": ("ui", "Angular CDK"), "@angular/material": ("ui", "Angular Material"),
    "svelte": ("framework", "Svelte"), "@sveltejs/kit": ("framework", "SvelteKit"),
    "astro": ("framework", "Astro"), "solid-js": ("framework", "SolidJS"), "@solidjs/router": ("router", "Solid Router"),
    "preact": ("framework", "Preact"), "@builder.io/qwik": ("framework", "Qwik"), "@qwik.dev/core": ("framework", "Qwik"),
    "lit": ("framework", "Lit (web components)"), "@stencil/core": ("framework", "Stencil (web components)"),
    "ember-source": ("framework", "Ember"), "@hotwired/turbo": ("framework", "Hotwire Turbo"),
    "@hotwired/stimulus": ("framework", "Stimulus"), "htmx.org": ("framework", "htmx"), "alpinejs": ("framework", "Alpine.js"),
    "@inertiajs/react": ("framework", "Inertia"), "@inertiajs/vue3": ("framework", "Inertia"),
    "jquery": ("framework", "jQuery"), "react-native": ("framework", "React Native"), "expo": ("framework", "Expo"),
    "@ionic/core": ("framework", "Ionic"), "@ionic/react": ("framework", "Ionic"), "@ionic/angular": ("framework", "Ionic"),
    "@ionic/vue": ("framework", "Ionic"), "@capacitor/core": ("framework", "Capacitor"),
    "@11ty/eleventy": ("framework", "Eleventy"), "gatsby": ("framework", "Gatsby"), "vite": ("build", "Vite"),
    # UI / headless libraries
    "@radix-ui/": ("ui", "Radix UI"), "radix-ui": ("ui", "Radix UI"), "react-aria": ("ui", "React Aria"),
    "react-aria-components": ("ui", "React Aria Components"), "@react-aria/": ("ui", "React Aria"),
    "@headlessui/react": ("ui", "Headless UI"), "@headlessui/vue": ("ui", "Headless UI"),
    "@ariakit/react": ("ui", "Ariakit"), "ariakit": ("ui", "Ariakit"), "@reach/": ("ui", "Reach UI (unmaintained)"),
    "@mui/material": ("ui", "MUI"), "@material-ui/core": ("ui", "Material UI v4 (legacy)"),
    "@chakra-ui/react": ("ui", "Chakra UI"), "@mantine/core": ("ui", "Mantine"), "antd": ("ui", "Ant Design"),
    "bootstrap": ("ui", "Bootstrap"), "react-bootstrap": ("ui", "React Bootstrap"), "bootstrap-vue-next": ("ui", "BootstrapVueNext"),
    "vuetify": ("ui", "Vuetify"), "primevue": ("ui", "PrimeVue"), "primeng": ("ui", "PrimeNG"), "primereact": ("ui", "PrimeReact"),
    "element-plus": ("ui", "Element Plus"), "quasar": ("ui", "Quasar"), "reka-ui": ("ui", "Reka UI"), "radix-vue": ("ui", "Radix Vue"),
    "@ark-ui/": ("ui", "Ark UI"), "bits-ui": ("ui", "Bits UI"), "@melt-ui/svelte": ("ui", "Melt UI"), "@kobalte/core": ("ui", "Kobalte"),
    "@nextui-org/react": ("ui", "NextUI"), "@heroui/react": ("ui", "HeroUI"), "daisyui": ("ui", "daisyUI"),
    "@fluentui/react-components": ("ui", "Fluent UI"), "@carbon/react": ("ui", "Carbon"), "@shoelace-style/shoelace": ("ui", "Shoelace"),
    "@nl-design-system/": ("ui", "NL Design System"), "@utrecht/": ("ui", "NL Design System (Utrecht)"),
    "@vue-a11y/announcer": ("a11y", "vue-announcer"), "focus-trap": ("a11y", "focus-trap"), "focus-trap-react": ("a11y", "focus-trap-react"),
    "@react-aria/live-announcer": ("a11y", "React Aria live announcer"),
    # styling
    "tailwindcss": ("styling", "Tailwind CSS"), "sass": ("styling", "Sass"), "styled-components": ("styling", "styled-components"),
    "@emotion/react": ("styling", "Emotion"), "@vanilla-extract/css": ("styling", "vanilla-extract"),
    "@pandacss/dev": ("styling", "Panda CSS"), "@stitches/react": ("styling", "Stitches"), "unocss": ("styling", "UnoCSS"),
    # forms
    "react-hook-form": ("forms", "React Hook Form"), "formik": ("forms", "Formik"), "@tanstack/react-form": ("forms", "TanStack Form"),
    "vee-validate": ("forms", "VeeValidate"), "@vuelidate/core": ("forms", "Vuelidate"), "sveltekit-superforms": ("forms", "Superforms"),
    "zod": ("forms", "Zod"), "yup": ("forms", "Yup"),
    # charts / maps / carousels / editors / dnd
    "chart.js": ("charts", "Chart.js"), "react-chartjs-2": ("charts", "Chart.js (react)"), "recharts": ("charts", "Recharts"),
    "highcharts": ("charts", "Highcharts"), "echarts": ("charts", "ECharts"), "d3": ("charts", "D3"), "apexcharts": ("charts", "ApexCharts"),
    "@nivo/": ("charts", "Nivo"), "victory": ("charts", "Victory"), "plotly.js": ("charts", "Plotly"),
    "leaflet": ("maps", "Leaflet"), "mapbox-gl": ("maps", "Mapbox GL"), "maplibre-gl": ("maps", "MapLibre"),
    "@googlemaps/js-api-loader": ("maps", "Google Maps"), "@vis.gl/react-google-maps": ("maps", "Google Maps"),
    "swiper": ("carousel", "Swiper"), "@splidejs/splide": ("carousel", "Splide"), "embla-carousel": ("carousel", "Embla"),
    "slick-carousel": ("carousel", "Slick"), "react-slick": ("carousel", "Slick"), "keen-slider": ("carousel", "Keen Slider"),
    "@tiptap/core": ("editor", "TipTap"), "lexical": ("editor", "Lexical"), "quill": ("editor", "Quill"),
    "@ckeditor/ckeditor5-build-classic": ("editor", "CKEditor"), "tinymce": ("editor", "TinyMCE"),
    "@dnd-kit/core": ("dnd", "dnd-kit"), "react-beautiful-dnd": ("dnd", "react-beautiful-dnd (deprecated)"),
    "@hello-pangea/dnd": ("dnd", "hello-pangea/dnd"), "@atlaskit/pragmatic-drag-and-drop": ("dnd", "Pragmatic DnD"),
    "sortablejs": ("dnd", "SortableJS"), "vuedraggable": ("dnd", "vuedraggable"),
    # animation / media / toasts
    "framer-motion": ("animation", "Framer Motion"), "motion": ("animation", "Motion"), "gsap": ("animation", "GSAP"),
    "aos": ("animation", "AOS"), "lottie-web": ("animation", "Lottie"), "lottie-react": ("animation", "Lottie"),
    "@lottiefiles/": ("animation", "Lottie"), "video.js": ("media", "Video.js"), "plyr": ("media", "Plyr"),
    "react-player": ("media", "react-player"), "hls.js": ("media", "hls.js"),
    "sonner": ("toast", "sonner"), "react-toastify": ("toast", "react-toastify"), "react-hot-toast": ("toast", "react-hot-toast"),
    "notistack": ("toast", "notistack"), "vue-toastification": ("toast", "vue-toastification"), "ngx-toastr": ("toast", "ngx-toastr"),
    "svelte-french-toast": ("toast", "svelte-french-toast"),
    # i18n
    "i18next": ("i18n", "i18next"), "react-i18next": ("i18n", "react-i18next"), "next-intl": ("i18n", "next-intl"),
    "vue-i18n": ("i18n", "vue-i18n"), "@nuxtjs/i18n": ("i18n", "Nuxt i18n"), "@ngx-translate/core": ("i18n", "ngx-translate"),
    "@angular/localize": ("i18n", "Angular i18n"), "react-intl": ("i18n", "react-intl"), "@lingui/core": ("i18n", "Lingui"),
    "svelte-i18n": ("i18n", "svelte-i18n"), "@inlang/paraglide-js": ("i18n", "Paraglide"),
    # a11y tooling
    "eslint-plugin-jsx-a11y": ("a11y-tooling", "eslint-plugin-jsx-a11y"),
    "eslint-plugin-vuejs-accessibility": ("a11y-tooling", "eslint-plugin-vuejs-accessibility"),
    "@angular-eslint/eslint-plugin-template": ("a11y-tooling", "angular-eslint template (a11y rules)"),
    "angular-eslint": ("a11y-tooling", "angular-eslint"), "eslint-plugin-svelte": ("a11y-tooling", "eslint-plugin-svelte"),
    "svelte-check": ("a11y-tooling", "svelte-check"), "ember-template-lint": ("a11y-tooling", "ember-template-lint"),
    "ember-a11y-testing": ("a11y-tooling", "ember-a11y-testing"), "ember-a11y-refocus": ("a11y", "ember-a11y-refocus"),
    "eslint-plugin-react-native-a11y": ("a11y-tooling", "eslint-plugin-react-native-a11y"),
    "eslint-plugin-lit-a11y": ("a11y-tooling", "eslint-plugin-lit-a11y"),
    "axe-core": ("a11y-tooling", "axe-core"), "@axe-core/playwright": ("a11y-tooling", "@axe-core/playwright"),
    "@axe-core/react": ("a11y-tooling", "@axe-core/react"), "@axe-core/puppeteer": ("a11y-tooling", "@axe-core/puppeteer"),
    "@axe-core/webdriverjs": ("a11y-tooling", "@axe-core/webdriverjs"), "cypress-axe": ("a11y-tooling", "cypress-axe"),
    "jest-axe": ("a11y-tooling", "jest-axe"), "vitest-axe": ("a11y-tooling", "vitest-axe"), "pa11y": ("a11y-tooling", "pa11y"),
    "pa11y-ci": ("a11y-tooling", "pa11y-ci"), "@lhci/cli": ("a11y-tooling", "Lighthouse CI"), "lighthouse": ("a11y-tooling", "Lighthouse"),
    "@storybook/addon-a11y": ("a11y-tooling", "Storybook a11y addon"), "html-validate": ("a11y-tooling", "html-validate"),
    "@testing-library/": ("testing", "Testing Library"), "playwright": ("testing", "Playwright"), "@playwright/test": ("testing", "Playwright"),
    "cypress": ("testing", "Cypress"), "jest": ("testing", "Jest"), "vitest": ("testing", "Vitest"), "storybook": ("testing", "Storybook"),
}

MARKER_FILES = {
    "angular.json": "Angular workspace", "nx.json": "Nx monorepo", "turbo.json": "Turborepo",
    "pnpm-workspace.yaml": "pnpm workspace", "lerna.json": "Lerna monorepo",
    "hugo.toml": "Hugo", "hugo.yaml": "Hugo", "hugo.json": "Hugo", "_config.yml": "Jekyll (possibly)",
    "Gemfile": "Ruby (Rails?)", "composer.json": "PHP (Laravel?)", "manage.py": "Django",
    "pyproject.toml": "Python project", "requirements.txt": "Python project", "pubspec.yaml": "Flutter/Dart",
    "go.mod": "Go", "mix.exs": "Elixir (Phoenix?)", "Cargo.toml": "Rust",
    ".storybook": "Storybook config", "playwright.config.ts": "Playwright config", "playwright.config.js": "Playwright config",
    "cypress.config.ts": "Cypress config", "cypress.config.js": "Cypress config", ".pa11yci": "pa11y-ci config",
    ".pa11yci.json": "pa11y-ci config", "lighthouserc.js": "Lighthouse CI config", "lighthouserc.json": "Lighthouse CI config",
    ".template-lintrc.js": "ember-template-lint config", ".gitlab-ci.yml": "GitLab CI",
}
MARKER_DIRS = {".storybook": "Storybook config", ".github/workflows": "GitHub Actions", "layouts/_default/_markup": "Hugo render hooks",
               "layouts": "Hugo/SSG layouts (project-level overrides)", "themes": "Hugo themes dir (check it is not an empty submodule)",
               "src/components/ui": "shadcn-style UI folder", "components/ui": "shadcn-style UI folder",
               "src/stories": "Storybook stories", "stories": "Storybook stories"}

CONFIG_GLOBS = {
    "next.config": "Next.js", "nuxt.config": "Nuxt", "svelte.config": "Svelte/SvelteKit", "astro.config": "Astro",
    "vite.config": "Vite", "tailwind.config": "Tailwind (v3-style config)", "remix.config": "Remix",
    "react-router.config": "React Router framework", "quasar.config": "Quasar", "eleventy.config": "Eleventy", ".eleventy": "Eleventy",
    "gatsby-config": "Gatsby", "ember-cli-build": "Ember", "stencil.config": "Stencil", "app.config": "Vinxi/Start (possibly)",
}

TEMPLATE_EXT = {
    ".jsx": "JSX", ".tsx": "TSX", ".vue": "Vue SFC", ".svelte": "Svelte", ".astro": "Astro", ".html": "HTML",
    ".erb": "ERB (Rails)", ".haml": "HAML", ".slim": "Slim", ".php": "PHP", ".twig": "Twig", ".jinja": "Jinja",
    ".jinja2": "Jinja", ".j2": "Jinja", ".hbs": "Handlebars", ".handlebars": "Handlebars", ".njk": "Nunjucks",
    ".liquid": "Liquid", ".razor": "Razor (Blazor)", ".cshtml": "Razor (MVC)", ".heex": "HEEx (Phoenix)", ".gohtml": "Go templates",
    ".tmpl": "Go/other templates", ".dart": "Dart", ".md": "Markdown", ".mdx": "MDX",
    ".css": "CSS", ".scss": "SCSS", ".sass": "Sass", ".less": "Less",
}

SUPPRESSION_PATTERNS = [
    (re.compile(r"eslint-disable[^\n]*?(jsx-a11y/[\w-]+)"), "eslint-disable"),
    (re.compile(r"eslint-disable[^\n]*?(vuejs-accessibility/[\w-]+)"), "eslint-disable"),
    (re.compile(r"eslint-disable[^\n]*?(@angular-eslint/template/[\w-]+)"), "eslint-disable"),
    (re.compile(r"eslint-disable[^\n]*?(react-native-a11y/[\w-]+)"), "eslint-disable"),
    (re.compile(r"svelte-ignore\s+(a11y[\w-]+)"), "svelte-ignore"),
    (re.compile(r"template-lint-disable\s+([\w-]+)"), "template-lint-disable"),
]

A11Y_SIGNALS = {
    "aria_live": re.compile(r"aria-live|role=[\"'](status|alert)[\"']|LiveAnnouncer|announceForAccessibility|useAnnouncer|NuxtRouteAnnouncer|RouteAnnouncer"),
    "reduced_motion": re.compile(r"prefers-reduced-motion|motion-reduce:|motion-safe:|useReducedMotion|reducedMotion|isReduceMotionEnabled|disableAnimations"),
    "forced_colors": re.compile(r"forced-colors|-ms-high-contrast|HighContrastModeDetector"),
    "focus_visible": re.compile(r"focus-visible|cdk-keyboard-focused|data-focus-visible"),
    "outline_removed": re.compile(r"outline:\s*(none|0)\b|focus:outline-none|\boutline-none\b"),
    "skip_link": re.compile(r"(?i)skip[-_ ]?(to[-_ ]?)?(main|content|nav)|SkipNavLink|visually-hidden-focusable"),
    "positive_tabindex": re.compile(r"tabindex=[\"']?[1-9]|tabIndex=\{?[\"']?[1-9]"),
    "user_scalable_no": re.compile(r"user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(\.0)?\b|userScalable:\s*false|maximumScale:\s*1\b"),
    "dialog_native": re.compile(r"<dialog\b|showModal\("),
    "font_scaling_disabled": re.compile(r"allowFontScaling=\{false\}|textScaleFactor:\s*1(\.0)?\b|TextScaler\.noScaling|TextScaler\.linear\(1(\.0)?\)"),
}

TEXT_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro", ".html", ".css", ".scss",
            ".sass", ".less", ".erb", ".php", ".twig", ".jinja", ".jinja2", ".j2", ".hbs", ".njk", ".liquid",
            ".razor", ".cshtml", ".heex", ".gohtml", ".tmpl", ".dart", ".json", ".yml", ".yaml", ".toml"}
# Source files that may EMBED a UI as a string literal (C++ raw strings, Go embed, Rust include_str!, Python templates…).
EMBED_EXT = {".h", ".hpp", ".c", ".cc", ".cpp", ".ino", ".go", ".rs", ".py", ".rb", ".java", ".kt", ".swift", ".cs",
             ".ex", ".exs", ".lua", ".pl", ".sh", ".txt"}
# The parts of a document that show a page is being written and not merely named.
PAGE_PARTS = re.compile(r"<!doctype html|<(?:html|head|body)[\s>]|</(?:html|body)>", re.IGNORECASE)


def is_page(text: str) -> bool:
    """A page, not a mention of one: a doctype, or two different parts of a document somewhere in the file (an <html> and
    a <head>, a <body> and its end). A comment that says "set on <html>" has one. One pass, whatever the size of the file."""
    seen = set()
    for m in PAGE_PARTS.finditer(text):
        part = m.group(0).lower().rstrip(" \t\r\n>")
        if part.startswith("<!doctype"):
            return True
        seen.add(part)
        if len(seen) > 1:
            return True
    return False


# Test code holds HTML as fixtures, not as the product's interface.
TEST_FILE = re.compile(r"(^|/)(__tests__|tests?|testdata|spec)/|_test\.\w+$|(^|/)test_[^/]+$|\.(test|spec)\.\w+$|_spec\.rb$"
                       r"|[a-z0-9]Tests?\.(java|kt|swift|cs)$|(^|/)(tests|conftest)\.py$")
# A sign that a script touches the page: the DOM, a canvas, or markup of its own (a closing tag or an attribute, which a
# type argument such as Array<number> has not). Only looked at where the interface lives in component files: there a
# plain module is usually logic. In a project without components the scripts are the interface, and all of them count.
DOM_RE = re.compile(r"\bdocument\.|\bwindow\.|querySelector|getElementById|addEventListener|innerHTML|insertAdjacent|createElement|customElements"
                    r"|getContext\(|OffscreenCanvas|</[A-Za-z][\w-]*>|<[a-z][\w-]*\s+[\w:-]+=")
COMPONENT_TYPES = {"JSX", "TSX", "Vue SFC", "Svelte", "Astro"}
RUN_SCRIPTS = ("dev", "start", "serve", "preview", "storybook")     # package.json scripts that start something to look at
# A backend that may serve the pages or their data: with one of these beside a package.json, its dev server alone shows less.
BACKEND_MARKERS = {"go.mod", "Cargo.toml", "manage.py", "Gemfile", "composer.json", "mix.exs", "pom.xml", "build.gradle", "build.gradle.kts"}


def gitignored_dirs(root: Path):
    """Directory names/paths from .gitignore that are plain (no wildcards) — build output is usually here."""
    out = set()
    gi = root / ".gitignore"
    if gi.exists():
        for line in gi.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("!") or any(c in line for c in "*?["):
                continue
            out.add(line.strip("/"))
    return out


def submodule_paths(root: Path):
    gm = root / ".gitmodules"
    if not gm.exists():
        return set()
    return {m.group(1).strip().strip("/") for m in re.finditer(r"^\s*path\s*=\s*(.+)$", gm.read_text(encoding="utf-8", errors="ignore"), re.M)}


def classify_path(rel: str, build: set, vendor: set) -> str:
    """'build' | 'vendor' | 'project'."""
    parts = rel.split("/")
    for i in range(1, len(parts)):
        prefix = "/".join(parts[:i])
        if prefix in build:
            return "build"
        # Top level only: the project's own themes/ is not vendored code.
        if prefix in vendor or (i == 1 and parts[0] in VENDOR_DIRS):
            return "vendor"
    return "project"


def iter_files(root: Path, max_files: int):
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root).as_posix()
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and f"{rel}/{d}".lstrip("./") not in SKIP_DIRS
                       and (not d.startswith(".") or d in {".storybook", ".github"})]
        for f in filenames:
            yield Path(dirpath) / f
            count += 1
            if count >= max_files:
                return


def dep_match(name: str):
    if name in DEPS:
        return DEPS[name]
    for key, val in DEPS.items():
        if key.endswith("/") and name.startswith(key):
            return val
    return None


def read_text(p: Path, limit: int = 400_000) -> str:
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def analyse(root: Path, max_files: int) -> dict:
    # public/ and site/ are build output only next to a static-site generator; without one they are hand-written UI
    generated = BUILD_DIRS if ssg_generates_public(root) else BUILD_DIRS - GENERATED_ONLY_BY_SSG
    build = gitignored_dirs(root) | {d for d in generated if (root / d).is_dir()}
    vendor = submodule_paths(root) | {d for d in VENDOR_DIRS if (root / d).is_dir()}
    result: dict = {
        "root": str(root), "packages": [], "detected": defaultdict(dict), "vendored": defaultdict(dict),
        "build_dirs": sorted(build), "vendor_dirs": sorted(vendor), "project_ui_files": 0, "counted": Counter(), "not_counted": Counter(), "scripts": Counter(),
        "backend": [], "markers": [], "configs": [],
        "file_types": Counter(), "suppressions": Counter(), "suppression_examples": [],
        "signals": {k: 0 for k in A11Y_SIGNALS}, "signal_examples": defaultdict(list),
        "lint_configs": [], "ci_files": [], "other_ecosystems": [], "embedded_html": [], "signal_files_scanned": 0,
        "infra_templates": Counter(), "csp": [], "a11y_docs": [],
    }
    for p in iter_files(root, max_files):
        size = file_size(p)
        if size is None:          # dangling symlink or unreadable: count nothing, read nothing
            continue
        rel = p.relative_to(root).as_posix()
        name = p.name
        ext = p.suffix.lower()
        where = classify_path(rel, build, vendor)
        if where == "build":
            continue
        # ponytail: at the root or one folder down (docs/, .github/), where such a file is kept; deeper ones are not looked for
        if where == "project" and rel.count("/") <= 1 and A11Y_DOC.match(name):
            heads = [h.strip() for h in re.findall(r"(?m)^#{1,3} +(.+?)[ #]*$", read_text(p, 60_000))]
            result["a11y_docs"].append({"path": rel, "headings": heads[:12]})
        if name == "package.json" and where == "vendor":
            try:
                data = json.loads(read_text(p))
            except json.JSONDecodeError:
                continue
            deps = {}
            for k in ("dependencies", "devDependencies", "peerDependencies"):
                deps.update(data.get(k) or {})
            for dep, ver in deps.items():
                m = dep_match(dep)
                if m:
                    result["vendored"][m[0]].setdefault(m[1], set()).add(f"{dep}@{ver} ({rel})")
            continue
        if where == "vendor":
            # vendored templates/styles count in a separate bucket; signals are not searched there
            if ext in TEMPLATE_EXT:
                result["infra_templates"][f"vendored {TEMPLATE_EXT[ext]}"] += 1
            continue
        if name == "package.json":
            try:
                data = json.loads(read_text(p))
            except json.JSONDecodeError:
                continue
            deps = {}
            for k in ("dependencies", "devDependencies", "peerDependencies"):
                deps.update(data.get(k) or {})
            result["packages"].append({"path": rel, "name": data.get("name"), "scripts": sorted((data.get("scripts") or {}).keys())})
            for dep, ver in deps.items():
                m = dep_match(dep)
                if m:
                    cat, label = m
                    result["detected"][cat].setdefault(label, set()).add(f"{dep}@{ver} ({rel})")
            continue
        if name in MARKER_FILES:
            result["markers"].append(f"{MARKER_FILES[name]}: {rel}")
        for stem, label in CONFIG_GLOBS.items():
            if name.startswith(stem + ".") or name == stem:
                result["configs"].append(f"{label}: {rel}")
        if re.match(r"(\.eslintrc|eslint\.config|\.stylelintrc|\.template-lintrc|biome\.json)", name):
            result["lint_configs"].append(rel)
        if rel.startswith(".github/workflows/") or name in {".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile", "bitbucket-pipelines.yml"}:
            result["ci_files"].append(rel)
        if name in {"Gemfile", "composer.json", "requirements.txt", "pyproject.toml", "pubspec.yaml"}:
            txt = read_text(p, 100_000).lower()
            for needle, label in (("rails", "Rails"), ("laravel/framework", "Laravel"), ("livewire", "Livewire"),
                                  ("django", "Django"), ("flask", "Flask"), ("jinja2", "Jinja"), ("flutter", "Flutter"),
                                  ("turbo-rails", "Turbo (Rails)"), ("inertiajs", "Inertia")):
                if needle in txt:
                    result["other_ecosystems"].append(f"{label} ({rel})")
        if ext == ".csproj":
            txt = read_text(p, 100_000)
            if "Microsoft.NET.Sdk.BlazorWebAssembly" in txt or "Components" in txt:
                result["other_ecosystems"].append(f".NET web (Blazor/Razor?) ({rel})")
        dirs_of = rel.split("/")[:-1]
        # Top level only: src/pages/roles/ is an RBAC screen, not Ansible roles.
        is_infra = bool(dirs_of) and dirs_of[0] in INFRA_DIRS
        if is_infra:
            if ext in TEMPLATE_EXT:
                result["infra_templates"][TEMPLATE_EXT[ext]] += 1
            if ext in {".conf", ".yml", ".yaml", ".toml", ".j2"} or name in CONFIG_NAMES:
                if CSP_RE.search(read_text(p, 200_000)):
                    result["csp"].append(rel)
            continue
        if name in BACKEND_MARKERS:
            result["backend"].append(rel)
        if ext in TEMPLATE_EXT:
            result["file_types"][TEMPLATE_EXT[ext]] += 1
            if ext in {".md", ".mdx"}:
                result["not_counted"]["Markdown"] += 1
            elif TEST_FILE.search(rel):
                result["not_counted"]["test files"] += 1
            else:
                result["project_ui_files"] += 1
                result["counted"][TEMPLATE_EXT[ext]] += 1
        elif ext in {".js", ".ts", ".mjs", ".cjs"}:
            if TEST_FILE.search(rel) or re.search(r"\.config\.", name):
                result["not_counted"]["test and config scripts"] += 1
            else:       # which of the two it is, is decided in finalise(), once it is known where the interface lives
                result["scripts"]["page" if size >= 2_000_000 or DOM_RE.search(read_text(p)) else "other"] += 1
        if re.search(r"\.stories\.(jsx?|tsx?|mdx|svelte|vue)$", name):
            result["file_types"]["Storybook stories"] += 1
        scan_for_signals = ext in TEXT_EXT
        if (ext in EMBED_EXT or ext == ".conf" or name in CONFIG_NAMES) and size < 2_000_000:
            txt = read_text(p)
            if CSP_RE.search(txt):
                result["csp"].append(rel)
            if is_page(txt) and TEST_FILE.search(rel):
                result["not_counted"]["test files with a page in a string"] += 1
            elif is_page(txt):
                lines = txt.count("\n") + 1
                result["embedded_html"].append(f"{rel} ({lines} lines)")
                result["file_types"]["Embedded HTML (string literal)"] += 1
                scan_for_signals = True
        if scan_for_signals and size < 2_000_000 and name not in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}:
            txt = read_text(p)
            result["signal_files_scanned"] += 1
            for pat, kind in SUPPRESSION_PATTERNS:
                for m in pat.finditer(txt):
                    result["suppressions"][f"{kind}: {m.group(1)}"] += 1
                    if len(result["suppression_examples"]) < 15:
                        line = txt.count("\n", 0, m.start()) + 1
                        result["suppression_examples"].append(f"{rel}:{line} {m.group(1)}")
            if ext in {".css", ".scss"} and re.search(r'@import\s+["\']tailwindcss["\']|@theme\b', txt):
                result["configs"].append(f"Tailwind v4 CSS config: {rel}")
            if CSP_RE.search(txt) and rel not in result["csp"]:
                result["csp"].append(rel)
            for key, pat in A11Y_SIGNALS.items():
                hits = len(pat.findall(txt))
                if hits:
                    result["signals"][key] += hits
                    if len(result["signal_examples"][key]) < 5:
                        result["signal_examples"][key].append(rel)
    for d, label in MARKER_DIRS.items():
        if (root / d).is_dir():
            result["markers"].append(f"{label}: {d}/")
    return result


def finalise(r: dict) -> dict:
    r["detected"] = {cat: {label: sorted(v) for label, v in labels.items()} for cat, labels in r["detected"].items()}
    r["vendored"] = {cat: {label: sorted(v) for label, v in labels.items()} for cat, labels in r["vendored"].items()}
    r["file_types"] = dict(r["file_types"].most_common())
    r["infra_templates"] = dict(r["infra_templates"].most_common())
    r["csp"] = sorted(set(r["csp"]))[:10]
    r["a11y_docs"] = sorted(r["a11y_docs"], key=lambda d: d["path"])
    r["suppressions"] = dict(r["suppressions"].most_common())
    r["signal_examples"] = dict(r["signal_examples"])
    r["other_ecosystems"] = sorted(set(r["other_ecosystems"]))
    hints = []
    d = r["detected"]
    if r["vendor_dirs"]:
        hints.append(f"Vendored/submodule code in {r['vendor_dirs']}: usually off-limits for edits — fixes go in project overrides; its packages are listed separately and are NOT the project's stack.")
    # Plain scripts: in a project with component files only those that touch the page are interface; elsewhere all are.
    page, other = r["scripts"]["page"], r["scripts"]["other"]
    if COMPONENT_TYPES & set(r["counted"]):
        r["counted"]["scripts that touch the page"] += page
        r["not_counted"]["scripts of logic beside the components"] += other
    else:
        r["counted"]["scripts"] += page + other
    r["counted"], r["not_counted"] = (Counter({k: v for k, v in c.items() if v}) for c in (r["counted"], r["not_counted"]))
    r["project_ui_files"] = sum(r["counted"].values())
    # A backend at the root of the repository, or in the folder of a package.json that has something to start. A Gemfile
    # beside a Jekyll config and a go.mod beside a Hugo config belong to the site generator, not to a backend.
    ssg = {"Gemfile"} if any(m.startswith("Jekyll") for m in r["markers"]) else set()
    ssg |= {"go.mod"} if any(m.startswith("Hugo") for m in r["markers"]) else set()
    startable = {str(Path(p["path"]).parent.as_posix()) for p in r["packages"] if set(p["scripts"]) & set(RUN_SCRIPTS)}
    r["backend"] = sorted(b for b in r["backend"] if startable and Path(b).name not in ssg and (str(Path(b).parent.as_posix()) in startable | {"."}))
    n = r["project_ui_files"]
    hints.append(f"Project-owned UI files: {n} (templates, styles and scripts; vendored code, build output, tests and Markdown excluded; the Scope line says what the number is made of) → {'mini' if n <= 10 else 'lean' if n <= 25 else 'full'} audit by file count; check the interactive-widget count in pattern-inventory.md before settling on mini.")
    if r["embedded_html"]:
        hints.append(f"UI embedded in {len(r['embedded_html'])} source file(s) as string literals: there is no framework to lean on; audit the literals directly and cite their line numbers.")
    if r["backend"]:
        hints.append(backend_note(r))
    labels = {lab for cat in d.values() for lab in cat}
    if "React" in labels and not {"Next.js", "Remix", "React Router (framework mode)", "TanStack Start"} & labels:
        if "React Router" in labels or "TanStack Router" in labels:
            hints.append("Client-side React routing without built-in route announcer: check focus/announcement on navigation.")
    spa_fw = {"React", "Vue", "Preact", "SolidJS", "Svelte", "Lit (web components)", "Qwik"} & labels
    meta_fw = {"Next.js", "Remix", "React Router (framework mode)", "TanStack Start", "Nuxt", "SvelteKit", "Astro", "Gatsby", "Angular"} & labels
    if spa_fw and not meta_fw and "router" not in d:
        hints.append(f"No router detected with {sorted(spa_fw)}: navigation is probably state-based (useState view switching). Check document.title, focus and announcement on view change, and browser back/forward.")
    if r["csp"]:
        hints.append(f"Content-Security-Policy configured ({', '.join(r['csp'][:3])}): injected styles/scripts from tooling may be blocked — axe_scan.mjs uses bypassCSP, hand-written helpers must too.")
    if "Vue Router" in labels and "Nuxt" not in labels:
        hints.append("Vue Router: no built-in route announcer; check router.afterEach for title/focus/announce.")
    if "Nuxt" in labels and r["signals"]["aria_live"] == 0:
        hints.append("Nuxt detected but no route announcer found: consider <NuxtRouteAnnouncer />.")
    if "Angular" in labels and "Angular CDK" not in labels:
        hints.append("Angular without @angular/cdk: CDK a11y utilities (FocusTrap, LiveAnnouncer, key managers) are unused.")
    if "MUI" in labels:
        hints.append("MUI: check createTheme palette.contrastThreshold (default 3).")
    if r["signals"]["outline_removed"] and not r["signals"]["focus_visible"]:
        hints.append("Outlines removed but no :focus-visible styles found: likely invisible keyboard focus.")
    if r["signals"]["reduced_motion"] == 0 and ("animation" in d or "carousel" in d):
        hints.append("Animation/carousel libraries present but no reduced-motion handling found.")
    if r["signals"]["user_scalable_no"]:
        hints.append("Zoom appears to be restricted in a viewport setting (SC 1.4.4).")
    if r["signals"]["font_scaling_disabled"]:
        hints.append("Native font scaling appears to be disabled somewhere.")
    stories = r["file_types"].get("Storybook stories", 0)
    if stories and not any(k in r["file_types"] for k in ("HTML",)) and not r["configs"]:
        hints.append(f"Looks like a component library ({stories} stories, no app config): use stories as the key flows.")
    if any(m.startswith("Hugo themes dir") for m in r["markers"]):
        themes = Path(r["root"]) / "themes"
        empty = [t.name for t in themes.iterdir() if t.is_dir() and not any(t.iterdir())]
        if empty:
            hints.append(f"Empty theme folder(s) {empty}: git submodule not initialised — run `git submodule update --init` before auditing.")
    if "a11y-tooling" not in d:
        hints.append("No accessibility lint/test tooling detected.")
    if r["suppressions"]:
        hints.append(f"{sum(r['suppressions'].values())} suppressed a11y lint warnings found.")
    if r["a11y_docs"]:
        hints.append(f"The project documents its own accessibility in {', '.join(d['path'] for d in r['a11y_docs'])}: read it before the stack profile "
                     "is written. What it says about conformance is a claim to re-measure; what it says about scope, known limitations "
                     "and exceptions belongs in the profile, with the path.")
    r["hints"] = hints
    return r


def backend_note(r: dict) -> str:
    return (f"A backend may sit beside the frontend ({', '.join(r['backend'][:3])}). If it serves the pages or their data, a dev server started from "
            "package.json shows the interface without it: ask how the whole application is started before offering to run one.")


def made_up_of(r: dict) -> str:
    """What the count that picks the audit size is made of, and what was left out of it."""
    # largest first, and by name where two are as large: the order of the walk differs from one machine to the next
    counted = ", ".join(f"{k} {v}" for k, v in sorted(r["counted"].items(), key=lambda kv: (-kv[1], kv[0])))
    left = ", ".join(f"{v} {k}" for k, v in sorted(r["not_counted"].items(), key=lambda kv: (-kv[1], kv[0])))
    return (f" ({counted})" if counted else "") + (f"; not counted: {left}" if left else "")


def print_human(r: dict) -> None:
    print(f"# Stack detection — {r['root']}\n")
    if r["packages"]:
        print("## package.json files")
        for p in r["packages"]:
            print(f"- {p['path']} ({p['name']}) scripts: {', '.join(p['scripts'][:12])}")
        print()
    for cat in ["framework", "router", "build", "ui", "styling", "forms", "charts", "maps", "carousel", "editor",
                "dnd", "animation", "media", "toast", "i18n", "a11y", "a11y-tooling", "testing"]:
        if cat in r["detected"]:
            print(f"## {cat}")
            for label, where in r["detected"][cat].items():
                print(f"- {label}: {'; '.join(where[:3])}{' …' if len(where) > 3 else ''}")
            print()
    if r["vendored"]:
        print("## Found only in vendored code (theme, submodule, vendor dir) — probably NOT your stack, often not even shipped")
        for cat, labels in r["vendored"].items():
            for label, where in labels.items():
                print(f"- {cat}: {label}: {'; '.join(where[:2])}")
        print()
    print(f"## Scope\nProject-owned UI files: {r['project_ui_files']}{made_up_of(r)}. Build output excluded: {', '.join(r['build_dirs']) or 'none found'}. "
          f"Vendored/submodules: {', '.join(r['vendor_dirs']) or 'none'}.\n")
    for title, key in (("Other ecosystems", "other_ecosystems"), ("Marker files", "markers"), ("Framework configs", "configs"),
                       ("Lint configs", "lint_configs"), ("CI files", "ci_files")):
        if r[key]:
            print(f"## {title}")
            for x in r[key][:20]:
                print(f"- {x}")
            print()
    print("## File types (UI)")
    print(", ".join(f"{k}: {v}" for k, v in list(r["file_types"].items())[:15]) or "(none)")
    if r["infra_templates"]:
        print("Not counted (infra or vendored): " + ", ".join(f"{k}: {v}" for k, v in r["infra_templates"].items()))
    if r["a11y_docs"]:
        print("\n## Accessibility documents of the project (its own claims: re-measure them, never take them over)")
        for d in r["a11y_docs"]:
            print(f"- {d['path']}" + (f" — sections: {'; '.join(d['headings'])}" if d["headings"] else ""))
    if r["csp"]:
        print("\n## Content-Security-Policy found in: " + ", ".join(r["csp"]))
    if r["embedded_html"]:
        print("\n## Embedded HTML in source files (UI lives inside string literals — audit these files)")
        for x in r["embedded_html"][:20]:
            print(f"- {x}")
    print(f"\n## A11y signals (occurrences, searched in {r['signal_files_scanned']} text/template/embedded files)")
    if r["signal_files_scanned"] < 5:
        print("(very few files scanned — treat zeros as 'not measured', not as 'clean')")
    for k, v in r["signals"].items():
        ex = ", ".join(r["signal_examples"].get(k, [])[:3])
        print(f"- {k}: {v}{'  e.g. ' + ex if ex else ''}")
    if r["suppressions"]:
        print("\n## Suppressed a11y rules")
        for k, v in r["suppressions"].items():
            print(f"- {k} ×{v}")
        for ex in r["suppression_examples"][:10]:
            print(f"  · {ex}")
    if r["hints"]:
        print("\n## Hints for the audit")
        for h in r["hints"]:
            print(f"- {h}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a human summary")
    ap.add_argument("--max-files", type=int, default=60_000)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2
    r = finalise(analyse(root, a.max_files))
    if a.json:
        print(json.dumps(r, indent=2, default=list))
    else:
        print_human(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
