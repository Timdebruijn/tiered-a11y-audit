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
EMBED_RE = re.compile(r"<!DOCTYPE html|<html[\s>]|<body[\s>]", re.IGNORECASE)


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
        if prefix in build or parts[i - 1] in BUILD_DIRS and i == 1:
            return "build"
        if prefix in vendor or parts[i - 1] in VENDOR_DIRS:
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
    build = gitignored_dirs(root) | {d for d in BUILD_DIRS if (root / d).is_dir()}
    vendor = submodule_paths(root) | {d for d in VENDOR_DIRS if (root / d).is_dir()}
    result: dict = {
        "root": str(root), "packages": [], "detected": defaultdict(dict), "vendored": defaultdict(dict),
        "build_dirs": sorted(build), "vendor_dirs": sorted(vendor), "project_ui_files": 0, "markers": [], "configs": [],
        "file_types": Counter(), "suppressions": Counter(), "suppression_examples": [],
        "signals": {k: 0 for k in A11Y_SIGNALS}, "signal_examples": defaultdict(list),
        "lint_configs": [], "ci_files": [], "other_ecosystems": [], "embedded_html": [], "signal_files_scanned": 0,
        "infra_templates": Counter(), "csp": [],
    }
    for p in iter_files(root, max_files):
        rel = p.relative_to(root).as_posix()
        name = p.name
        ext = p.suffix.lower()
        where = classify_path(rel, build, vendor)
        if where == "build":
            continue
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
        is_infra = any(seg in INFRA_DIRS for seg in rel.split("/")[:-1])
        if is_infra:
            if ext in TEMPLATE_EXT:
                result["infra_templates"][TEMPLATE_EXT[ext]] += 1
            if ext in {".conf", ".yml", ".yaml", ".toml", ".j2"} or name in CONFIG_NAMES:
                if CSP_RE.search(read_text(p, 200_000)):
                    result["csp"].append(rel)
            continue
        if ext in TEMPLATE_EXT:
            result["file_types"][TEMPLATE_EXT[ext]] += 1
            if ext not in {".md", ".mdx"}:
                result["project_ui_files"] += 1
        elif ext in {".js", ".ts", ".mjs", ".cjs"} and not re.search(r"\.(test|spec|config)\.", name):
            result["project_ui_files"] += 1
        if re.search(r"\.stories\.(jsx?|tsx?|mdx|svelte|vue)$", name):
            result["file_types"]["Storybook stories"] += 1
        scan_for_signals = ext in TEXT_EXT
        if (ext in EMBED_EXT or ext == ".conf" or name in CONFIG_NAMES) and p.stat().st_size < 2_000_000:
            txt = read_text(p)
            if CSP_RE.search(txt):
                result["csp"].append(rel)
            if EMBED_RE.search(txt):
                lines = txt.count("\n") + 1
                result["embedded_html"].append(f"{rel} ({lines} lines)")
                result["file_types"]["Embedded HTML (string literal)"] += 1
                scan_for_signals = True
        if scan_for_signals and p.stat().st_size < 2_000_000 and name not in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}:
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
    r["suppressions"] = dict(r["suppressions"].most_common())
    r["signal_examples"] = dict(r["signal_examples"])
    r["other_ecosystems"] = sorted(set(r["other_ecosystems"]))
    hints = []
    d = r["detected"]
    if r["vendor_dirs"]:
        hints.append(f"Vendored/submodule code in {r['vendor_dirs']}: usually off-limits for edits — fixes go in project overrides; its packages are listed separately and are NOT the project's stack.")
    n = r["project_ui_files"]
    hints.append(f"Project-owned UI files: {n} (templates, styles, scripts; vendored and build output excluded) → {'mini' if n <= 10 else 'lean' if n <= 25 else 'full'} audit by file count; check the interactive-widget count in pattern-inventory.md before settling on mini.")
    if r["embedded_html"]:
        hints.append(f"UI embedded in {len(r['embedded_html'])} source file(s) as string literals: there is no framework to lean on; audit the literals directly and cite their line numbers.")
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
    r["hints"] = hints
    return r


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
    print(f"## Scope\nProject-owned UI files: {r['project_ui_files']}. Build output excluded: {', '.join(r['build_dirs']) or 'none found'}. "
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
