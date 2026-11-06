#!/usr/bin/env python3
"""Pattern inventory: every grep an expert would otherwise run, done once, deterministically.

    python3 scan_patterns.py <repo-root> [--json] [--max-hits 25] [--include-infra]

Scans templates (HTML, JSX/TSX, Vue, Svelte, Astro, server templates, UIs embedded in source strings),
stylesheets and UI scripts for accessibility-relevant patterns and prints a markdown inventory:
per pattern the count and up to --max-hits `file:line` locations with a one-line snippet, plus a per-file
summary of headings, titles and lang. Hits are CANDIDATES (regex, not a parser): experts verify and judge.
Pure standard library, read-only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", ".output", ".svelte-kit", ".astro", "out",
             "coverage", "vendor", ".venv", "venv", "__pycache__", "target", ".turbo", ".cache", "storybook-static",
             ".a11y-audit", "Pods", ".dart_tool", "bin", "obj", "public/build", "resources/_gen"}
INFRA_DIRS = {"ansible", "terraform", "infra", "infrastructure", "deploy", "deployment", "k8s", "kubernetes", "helm",
              "playbooks", "roles", "ops", "docker", "nginx", "systemd"}
BUILD_DIRS = {"public", "_site", "out", "dist", "build", "site", "resources/_gen"}
VENDOR_DIRS = {"vendor", "themes", "third_party", "third-party", "external"}


def gitignored_dirs(root: Path):
    out = set()
    gi = root / ".gitignore"
    if gi.exists():
        for line in gi.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith(("#", "!")) and not any(c in line for c in "*?["):
                out.add(line.strip("/"))
    return out


def submodule_paths(root: Path):
    gm = root / ".gitmodules"
    if not gm.exists():
        return set()
    return {m.group(1).strip().strip("/") for m in re.finditer(r"^\s*path\s*=\s*(.+)$", gm.read_text(encoding="utf-8", errors="ignore"), re.M)}
MARKUP_EXT = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro", ".erb", ".haml", ".slim", ".php",
              ".twig", ".jinja", ".jinja2", ".j2", ".hbs", ".handlebars", ".njk", ".liquid", ".razor", ".cshtml",
              ".heex", ".gohtml", ".tmpl", ".md", ".mdx"}
STYLE_EXT = {".css", ".scss", ".sass", ".less"}
SCRIPT_EXT = {".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx", ".vue", ".svelte", ".astro"}
EMBED_EXT = {".h", ".hpp", ".c", ".cc", ".cpp", ".ino", ".go", ".rs", ".py", ".rb", ".java", ".kt", ".swift", ".cs", ".ex", ".exs"}
EMBED_RE = re.compile(r"<!DOCTYPE html|<html[\s>]|<body[\s>]", re.I)
TAG = r"[^>]*?"  # inside a tag, may span lines

# (key, regex, flags, title, lens, note)
MARKUP_PATTERNS = [
    ("click_on_non_interactive", r"<(div|span|li|p|td|tr|img|svg|i|section|article|label)\b" + TAG + r"\b(onclick|onClick|@click|\(click\)|on:click|v-on:click)\s*=", re.I,
     "Click handler on a non-interactive element", "semantics/keyboard", "Should be <button> or <a href>; needs role, tabindex and key handling otherwise (2.1.1, 4.1.2)."),
    ("anchor_as_button", r"<a\b" + TAG + r"\bhref\s*=\s*[\"'](#|javascript:[^\"']*)[\"']", re.I,
     "Anchor with href=\"#\" or javascript: used as a button", "semantics", "Use <button>; links navigate, buttons act."),
    ("anchor_without_href", r"<a\b(?![^>]*\bhref\s*=)(?![^>]*\b(to|routerLink|href)\s*=)[^>]*>", re.I,
     "Anchor without href (not focusable, no link role)", "semantics", "Add href or make it a button; framework Link components with to= are excluded."),
    ("img_without_alt", r"<(img|Image|NuxtImg|next-image)\b(?![^>]*\balt\s*=)[^>]*>", re.I,
     "Image without alt attribute", "content", "alt=\"\" for decorative, descriptive alt otherwise (1.1.1)."),
    ("icon_only_button", r"<button\b(?![^>]*\baria-label(ledby)?\s*=)(?![^>]*\btitle\s*=)[^>]*>\s*(<(svg|i|span|Icon|FontAwesomeIcon|[A-Z]\w*Icon)\b[\s\S]{0,400}?(</\3>|/>))\s*</button>", re.I,
     "Button containing only an icon and no aria-label", "semantics", "Needs an accessible name (visually-hidden text or aria-label) (4.1.2)."),
    ("icon_only_link", r"<a\b(?![^>]*\baria-label(ledby)?\s*=)[^>]*>\s*(<(svg|i|span|Icon|[A-Z]\w*Icon)\b[\s\S]{0,400}?(</\3>|/>))\s*</a>", re.I,
     "Link containing only an icon and no aria-label", "semantics/content", "Needs an accessible name (2.4.4, 4.1.2)."),
    ("input_without_id_or_label", r"<(input|select|textarea)\b(?![^>]*\btype\s*=\s*[\"'](hidden|submit|button|reset|image)[\"'])(?![^>]*\b(id|aria-label|aria-labelledby|v-model:id|:id)\s*=)[^>]*>", re.I,
     "Form control without id and without aria-label (no way to associate a <label for>)", "forms", "Verify whether a wrapping <label> exists; otherwise unlabeled (3.3.2, 4.1.2)."),
    ("placeholder_present", r"<(input|textarea)\b[^>]*\bplaceholder\s*=", re.I,
     "Control with a placeholder (check that a real label exists too)", "forms", "Placeholder is not a label (3.3.2)."),
    ("password_or_otp_field", r"<input\b[^>]*\btype\s*=\s*[\"'](password|tel|number)[\"'][^>]*>|autocomplete\s*=\s*[\"']one-time-code[\"']", re.I,
     "Password / OTP / numeric fields (check autocomplete tokens and paste)", "forms", "3.3.8, 1.3.5."),
    ("paste_blocked", r"\bon[Pp]aste\s*=|addEventListener\(\s*[\"']paste[\"']|@paste|\(paste\)", re.I,
     "Paste handler (often blocks pasting into password/code fields)", "forms", "Blocking paste fails 3.3.8 in practice."),
    ("positive_tabindex", r"\btab[Ii]ndex\s*=\s*[\"'{]?\s*[1-9]", 0,
     "Positive tabindex", "keyboard", "Breaks natural focus order (2.4.3); use 0 or -1."),
    ("aria_hidden_focusable", r"<(a|button|input|select|textarea)\b[^>]*\baria-hidden\s*=\s*[\"']true[\"']", re.I,
     "aria-hidden=\"true\" on a focusable element", "semantics", "Focusable but hidden from AT (4.1.2)."),
    ("role_attribute", r"\brole\s*=\s*[\"'](\w+)[\"']", re.I,
     "role= attributes (review for correctness and required states)", "semantics", "Native elements first; check required owned elements and keyboard behaviour."),
    ("live_region", r"\baria-live\s*=|\brole\s*=\s*[\"'](status|alert|log)[\"']", re.I,
     "Live regions present", "dynamic", "Must exist before the content changes (4.1.3)."),
    ("target_blank", r"\btarget\s*=\s*[\"']_blank[\"']", re.I,
     "Links opening a new tab/window", "content", "Announce it (visually hidden text) and consider rel=noopener (2.4.4 best practice)."),
    ("autoplay", r"\bautoplay\b|\bautoPlay\b", re.I,
     "autoplay on media", "dynamic/visual", "No autoplay with sound (1.4.2); provide pause (2.2.2)."),
    ("iframe_without_title", r"<iframe\b(?![^>]*\btitle\s*=)[^>]*>", re.I,
     "iframe without title", "semantics", "4.1.2."),
    ("table_tag", r"<table\b", re.I, "Tables (check <th scope>, <caption>)", "semantics", "1.3.1."),
    ("native_dialog", r"<dialog\b|\.showModal\(", re.I, "Native <dialog> usage (good; check name and focus restore)", "dynamic", ""),
    ("modal_like_class", r"class(Name)?\s*=\s*[\"'][^\"']*\b(modal|dialog|drawer|popover|overlay|sheet)\b", re.I,
     "Modal-like classes without native dialog (check role, focus trap, Esc, inert)", "dynamic", "4.1.2, 2.1.2, 2.4.3."),
    ("html_without_lang", r"<html\b(?![^>]*\blang\s*=)[^>]*>", re.I, "<html> without lang", "semantics", "3.1.1."),
    ("viewport_zoom_lock", r"user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(\.0)?\b|userScalable:\s*false|maximumScale:\s*1\b", re.I,
     "Viewport blocks zoom", "visual", "1.4.4."),
    ("skip_link", r"(?i)skip[-_ ]?(to[-_ ]?)?(main|content|nav)|SkipNavLink|visually-hidden-focusable", 0,
     "Skip link present", "keyboard", "2.4.1."),
    ("mousedown_handler", r"\b(onmousedown|onMouseDown|@mousedown|\(mousedown\)|on:mousedown|onpointerdown|onPointerDown|ontouchstart|onTouchStart)\s*=", re.I,
     "Action bound to the down-event", "forms", "Pointer cancellation (2.5.2): act on up-event or allow abort."),
    ("hover_only_handler", r"\b(onmouseover|onMouseEnter|onmouseenter|@mouseenter|\(mouseenter\)|on:mouseenter)\s*=", re.I,
     "Hover handlers (check for focus equivalents)", "keyboard", "Hover-only content fails 2.1.1 / 1.4.13."),
    ("key_handler", r"\b(onkeydown|onKeyDown|@keydown|\(keydown\)|on:keydown|onkeyup|onKeyUp)\s*=", re.I,
     "Key handlers (custom widget keyboard support exists here)", "keyboard", ""),
    ("heading_tags", r"<h([1-6])\b", re.I, "Heading tags", "semantics", "Counted per file in the summary table."),
    ("title_tag", r"<title>([^<]*)</title>", re.I, "Page titles", "semantics", "Listed per file; identical titles fail 2.4.2 in multi-page sites."),
    ("svg_inline", r"<svg\b(?![^>]*\b(aria-hidden|role|aria-label|aria-labelledby)\s*=)[^>]*>", re.I,
     "Inline SVG without aria-hidden/role/name", "content", "Decorative: aria-hidden=\"true\" focusable=\"false\"; meaningful: role=\"img\" + title/aria-label (1.1.1)."),
    ("canvas", r"<canvas\b", re.I, "Canvas elements (need a text alternative)", "content", "1.1.1."),
    ("generic_link_text", r">\s*(lees meer|read more|meer info|more|klik hier|click here|here|hier|learn more|details)\s*<", re.I,
     "Generic link/button text", "content", "2.4.4: make the purpose clear from the text."),
    ("required_marker_only", r"<[^>]*\brequired\b[^>]*>|\baria-required\s*=", re.I, "Required controls (check visible and programmatic indication)", "forms", "3.3.2."),
    ("autocomplete_attr", r"\bautocomplete\s*=\s*[\"'](?!off)", re.I, "autocomplete tokens present (good)", "forms", "1.3.5."),
    ("suppressed_a11y_rule", r"eslint-disable[^\n]*?(jsx-a11y|vuejs-accessibility|@angular-eslint/template)/[\w-]+|svelte-ignore\s+a11y[\w-]*|template-lint-disable\s+[\w-]+", 0,
     "Suppressed accessibility lint rule", "framework", "Each one hides a known issue."),
]

STYLE_PATTERNS = [
    ("outline_removed", r"outline\s*:\s*(none|0)\b|\boutline-none\b|focus:outline-none", re.I, "Focus outline removed", "keyboard", "Needs a :focus-visible replacement (2.4.7)."),
    ("focus_visible_rule", r":focus-visible\b|focus-visible:", re.I, "Custom :focus-visible styles present", "keyboard", ""),
    ("reduced_motion", r"prefers-reduced-motion|motion-reduce:|motion-safe:", re.I, "Reduced-motion handling present", "visual", ""),
    ("forced_colors", r"forced-colors|-ms-high-contrast", re.I, "Forced-colours handling present", "visual", ""),
    ("animation_infinite", r"animation[^;]*\binfinite\b|animation-iteration-count\s*:\s*infinite", re.I, "Infinite animations", "visual/dynamic", "2.2.2 pause/stop/hide; 2.3.3."),
    ("keyframes", r"@keyframes\s+[\w-]+", re.I, "Keyframe animations", "visual", "Check reduced-motion."),
    ("small_font_px", r"font-size\s*:\s*(1[0-3]|[0-9])(\.\d+)?px\b", re.I, "Font sizes under 14px", "visual", "Readability; and px blocks user font settings when on html/body (1.4.4)."),
    ("font_px_root", r"\b(html|body|:root)\b[^{]*\{[^}]*font-size\s*:\s*\d+(\.\d+)?px", re.I, "Root/body font-size in px", "visual", "Use rem or % so user font settings apply (1.4.4)."),
    ("line_height_low", r"line-height\s*:\s*(0?\.\d+|1(\.[0-3]\d*)?)\s*;", re.I, "line-height below 1.4", "visual", "1.4.12 text spacing; readability."),
    ("nowrap_ellipsis", r"white-space\s*:\s*nowrap|text-overflow\s*:\s*ellipsis", re.I, "nowrap / ellipsis (text may clip at zoom or text spacing)", "visual", "1.4.10, 1.4.12."),
    ("fixed_height_overflow_hidden", r"height\s*:\s*\d+px[^}]*overflow(-y)?\s*:\s*hidden|overflow(-y)?\s*:\s*hidden[^}]*height\s*:\s*\d+px", re.I | re.S, "Fixed height with overflow hidden (clips enlarged text)", "visual", "1.4.4, 1.4.12."),
    ("uppercase_text", r"text-transform\s*:\s*uppercase", re.I, "Uppercase transforms", "visual/content", "Readability for long runs of text; screen readers may spell out."),
    ("pointer_events_none", r"pointer-events\s*:\s*none", re.I, "pointer-events: none", "keyboard", "Check keyboard equivalent still works."),
    ("hover_without_focus", r":hover\b", re.I, ":hover rules (count; compare with :focus/:focus-visible count)", "keyboard", ""),
    ("box_shadow_border", r"box-shadow\s*:[^;]*\b(0\s+0\s+0\s+\d+px)", re.I, "Borders/rings drawn with box-shadow (disappear in forced colours)", "visual", "Add outline or border fallback under forced-colors."),
    ("important_count", r"!important", re.I, "!important (count)", "framework", ""),
]

SCRIPT_PATTERNS = [
    ("set_interval", r"\bsetInterval\s*\(", 0, "setInterval (auto-updating content)", "dynamic", "2.2.2; focus loss on repaint."),
    ("set_timeout_long", r"\bsetTimeout\s*\([^,]+,\s*(\d{4,})", 0, "setTimeout ≥ 1 s (toasts, auto-dismiss, timeouts)", "dynamic", "2.2.1; toast duration."),
    ("document_title", r"document\.title\s*=", 0, "document.title updates (route/view change support)", "dynamic", ""),
    ("focus_calls", r"\.focus\(\s*\)", 0, "Programmatic focus() calls (focus management exists here)", "keyboard", ""),
    ("inner_html", r"\.innerHTML\s*=|dangerouslySetInnerHTML|v-html\s*=|\{@html", 0, "innerHTML / v-html / @html repaints", "dynamic", "Destroys focus and live-region state inside; check."),
    ("history_api", r"history\.pushState|location\.hash\s*=|router\.(push|replace)|navigate\(", 0, "Navigation calls (check title, focus, announcement)", "dynamic", ""),
    ("window_open", r"window\.open\s*\(", 0, "window.open", "content", "Announce new window (3.2.5 AAA / best practice)."),
    ("native_alerts", r"\b(alert|confirm|prompt)\s*\(", 0, "Native alert/confirm/prompt (accessible by default)", "dynamic", ""),
    ("drag_events", r"\b(ondragstart|onDragStart|draggable\s*=\s*[\"'{]?true|useDraggable|useSortable|DndContext)", 0, "Drag and drop (needs a non-drag alternative)", "forms", "2.5.7."),
    ("key_code_single", r"\bkey\s*===?\s*[\"'][a-zA-Z0-9][\"']", 0, "Single-character key shortcuts", "keyboard", "2.1.4: must be remappable or active only on focus."),
]


def iter_files(root: Path, include_infra: bool):
    build = gitignored_dirs(root) | BUILD_DIRS
    vendor = submodule_paths(root) | VENDOR_DIRS
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root).as_posix()
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and (not d.startswith(".") or d == ".storybook")
                       and (f"{rel}/{d}".lstrip("./") not in build) and (rel != "." and rel != "" or d not in build)]
        if not include_infra and any(seg in INFRA_DIRS for seg in rel.split("/") if seg):
            continue
        segs = [s for s in rel.split("/") if s and s != "."]
        is_vendor = any("/".join(segs[:i]) in vendor or segs[i - 1] in VENDOR_DIRS for i in range(1, len(segs) + 1))
        for f in filenames:
            yield Path(dirpath) / f, is_vendor


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-hits", type=int, default=25)
    ap.add_argument("--include-infra", action="store_true")
    a = ap.parse_args()
    root = Path(a.root).resolve()

    hits = defaultdict(list)          # key -> [(rel, line, snippet)]
    counts = Counter()
    vhits = defaultdict(list)         # same, for vendored code (theme, submodule): fix ownership override/upstream/accepted
    vcounts = Counter()
    per_file = {}                     # rel -> {headings:{}, titles:[], lang:bool|None}
    files_scanned = Counter()
    for p, is_vendor in iter_files(root, a.include_infra):
        ext = p.suffix.lower()
        kind = None
        if ext in MARKUP_EXT:
            kind = "markup"
        elif ext in STYLE_EXT:
            kind = "style"
        elif ext in SCRIPT_EXT:
            kind = "script"
        elif ext in EMBED_EXT:
            txt = read(p)
            if EMBED_RE.search(txt):
                kind = "markup"
        if not kind or p.stat().st_size > 3_000_000:
            continue
        txt = read(p)
        rel = p.relative_to(root).as_posix()
        files_scanned[kind] += 1
        pattern_sets = []
        if kind == "markup":
            pattern_sets.append(MARKUP_PATTERNS)
            if ext in SCRIPT_EXT or ext in EMBED_EXT or ext in {".html", ".htm"}:
                pattern_sets.append(SCRIPT_PATTERNS)
            if ext in EMBED_EXT or ext in {".html", ".htm", ".vue", ".svelte", ".astro"}:
                pattern_sets.append(STYLE_PATTERNS)
        elif kind == "style":
            pattern_sets.append(STYLE_PATTERNS)
        elif kind == "script":
            pattern_sets.append(SCRIPT_PATTERNS)
            if ext in {".jsx", ".tsx"}:
                pattern_sets.append(MARKUP_PATTERNS)
        for pats in pattern_sets:
            for key, rx, flags, *_ in pats:
                for m in re.finditer(rx, txt, flags):
                    line = txt.count("\n", 0, m.start()) + 1
                    snippet = txt[m.start():m.start() + 110].split("\n")[0].strip()
                    bucket_c, bucket_h = (vcounts, vhits) if is_vendor else (counts, hits)
                    bucket_c[key] += 1
                    if len(bucket_h[key]) < a.max_hits:
                        bucket_h[key].append((rel, line, snippet))
        if kind == "markup" and not is_vendor:
            heads = Counter(m.group(1) for m in re.finditer(r"<h([1-6])\b", txt, re.I))
            titles = [t.strip() for t in re.findall(r"<title>([^<]*)</title>", txt, re.I)]
            lang = None
            if re.search(r"<html\b", txt, re.I):
                lang = bool(re.search(r"<html\b[^>]*\blang\s*=", txt, re.I))
            if heads or titles or lang is not None:
                per_file[rel] = {"headings": {f"h{k}": v for k, v in sorted(heads.items())}, "titles": titles, "html_lang": lang}

    all_patterns = {k: (t, lens, note) for k, _, _, t, lens, note in MARKUP_PATTERNS + STYLE_PATTERNS + SCRIPT_PATTERNS}
    if a.json:
        print(json.dumps({"files_scanned": dict(files_scanned), "counts": dict(counts), "vendored_counts": dict(vcounts),
                          "hits": {k: [{"file": f, "line": l, "snippet": s} for f, l, s in v] for k, v in hits.items()},
                          "vendored_hits": {k: [{"file": f, "line": l, "snippet": s} for f, l, s in v] for k, v in vhits.items()},
                          "per_file": per_file}, indent=2))
        return 0

    print(f"# Pattern inventory — {root}\n")
    print(f"Files scanned: " + ", ".join(f"{k}: {v}" for k, v in files_scanned.items()) + ". Hits are regex candidates; verify before filing.\n")
    print("## Summary\n")
    print("| Pattern | Project hits | Vendored hits | Lens |")
    print("|---|---|---|---|")
    for key, (title, lens, _) in all_patterns.items():
        print(f"| {title} | {counts.get(key, 0)} | {vcounts.get(key, 0)} | {lens} |")
    if vcounts:
        print("\nVendored hits sit in a theme, submodule or vendor directory: fix ownership is override, upstream or accepted, never a direct edit.")
    print("\n## Per-file: headings, titles, lang\n")
    print("| File | Headings | Title(s) | html lang |")
    print("|---|---|---|---|")
    for rel, info in sorted(per_file.items()):
        h = ", ".join(f"{k}:{v}" for k, v in info["headings"].items()) or "none"
        t = "; ".join(info["titles"]) or "none"
        l = {True: "yes", False: "MISSING", None: "n/a"}[info["html_lang"]]
        print(f"| {rel} | {h} | {t[:60]} | {l} |")
    titles_all = [t for info in per_file.values() for t in info["titles"]]
    dup = [t for t, c in Counter(titles_all).items() if c > 1]
    if dup:
        print(f"\nIdentical titles across files: {dup}")
    print("\n## Locations\n")
    for key, (title, lens, note) in all_patterns.items():
        if not counts.get(key):
            continue
        print(f"### {title} ({counts[key]}) — {lens}")
        if note:
            print(note)
        for rel, line, snippet in hits[key]:
            print(f"- `{rel}:{line}` {snippet}")
        if counts[key] > len(hits[key]):
            print(f"- … {counts[key] - len(hits[key])} more (grep for it)")
        print()
    if vcounts:
        print("## Locations in vendored code\n")
        for key, (title, lens, note) in all_patterns.items():
            if not vcounts.get(key):
                continue
            print(f"### {title} ({vcounts[key]}, vendored) — {lens}")
            for rel, line, snippet in vhits[key]:
                print(f"- `{rel}:{line}` {snippet}")
            if vcounts[key] > len(vhits[key]):
                print(f"- … {vcounts[key] - len(vhits[key])} more")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
