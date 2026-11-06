#!/usr/bin/env python3
"""Colour tokens → contrast pairs, so the visual lens starts from numbers instead of grepping.

    python3 extract_colors.py <repo-root> [--json] [--max-pairs 80]

Reads CSS/SCSS/Less (and <style> blocks in HTML, Vue, Svelte, Astro and UIs embedded in source strings):
custom properties (--token: value), SCSS/Less variables ($x / @x), Tailwind v4 @theme blocks. Detects the
colour scheme of each definition (default, dark via prefers-color-scheme / [data-theme=dark] / .dark,
light-dark(a, b)). Resolves var() and variable references. Classifies tokens by NAME as foreground-like or
background-like and computes the WCAG ratio for every fg×bg pair per scheme, failing pairs first.
Pairs are candidates: the expert checks which combinations are actually used together.
Tailwind v3 JS config, CSS-in-JS theme objects and MUI/Chakra themes are not parsed — read those by hand.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contrast import parse as parse_colour, ratio, to_hex  # noqa: E402

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", ".output", ".svelte-kit", ".astro", "out",
             "coverage", "vendor", ".venv", "venv", "__pycache__", "target", ".a11y-audit", "storybook-static"}
# Infrastructure, skipped at the top level only: src/deploy/ may well be UI.
INFRA_DIRS = {"ansible", "terraform", "infra", "deploy", "k8s", "kubernetes", "helm"}
STYLE_EXT = {".css", ".scss", ".sass", ".less"}
EMBED_EXT = {".html", ".htm", ".vue", ".svelte", ".astro", ".h", ".hpp", ".c", ".cpp", ".go", ".rs", ".py", ".rb", ".php"}

SSG_CONFIGS = ("hugo.toml", "hugo.yaml", "hugo.json", "_config.yml", ".eleventy.js",
               "eleventy.config.js", "mkdocs.yml")
# public/ and site/ hold generated output for a static-site generator, but source for
# CRA, Vite and Next: public/index.html carries <html lang>, the title and the viewport meta.
GENERATED_ONLY_BY_SSG = {"public", "site"}


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


BG_WORDS = re.compile(r"(^|[-_])(bg|background|surface|card|panel|canvas|base|paper|page|body|sheet|well|elevated|overlay|backdrop|fill)([-_0-9]|$)", re.I)
FG_WORDS = re.compile(r"(^|[-_])(fg|text|ink|foreground|on|muted|dim|dimmed|subtle|secondary|tertiary|link|accent|primary|brand|good|ok|success|warn|warning|bad|danger|error|info|placeholder|heading|label|caption|icon)([-_0-9]|$)", re.I)
BOTH_WORDS = re.compile(r"(^|[-_])(accent|primary|brand|good|ok|success|warn|warning|bad|danger|error|info)([-_0-9]|$)", re.I)

COLOUR_VALUE = re.compile(r"^(#[0-9a-f]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\)|oklch\([^)]*\)|oklab\([^)]*\)|[a-z]+)$", re.I)
HSL = re.compile(r"hsla?\(\s*([\d.]+)(deg)?[\s,]+([\d.]+)%[\s,]+([\d.]+)%", re.I)


def hsl_to_hex(h, s, l):
    h, s, l = float(h) % 360 / 360, float(s) / 100, float(l) / 100
    if s == 0:
        r = g = b = l
    else:
        def f(p, q, t):
            t = t % 1
            if t < 1 / 6: return p + (q - p) * 6 * t
            if t < 1 / 2: return q
            if t < 2 / 3: return p + (q - p) * (2 / 3 - t) * 6
            return p
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r, g, b = f(p, q, h + 1 / 3), f(p, q, h), f(p, q, h - 1 / 3)
    return to_hex((r, g, b))


def to_rgb(value: str):
    """Return an sRGB tuple or None (alpha, oklch, unknown)."""
    v = value.strip()
    m = HSL.match(v)
    if m:
        return parse_colour(hsl_to_hex(m.group(1), m.group(3), m.group(4)))
    try:
        return parse_colour(v)
    except ValueError:
        return None


def scheme_of(selector_stack):
    s = " ".join(selector_stack).lower()
    if "prefers-color-scheme: dark" in s or "prefers-color-scheme:dark" in s or "data-theme=\"dark\"" in s or "data-theme='dark'" in s or ".dark" in s or "[dark]" in s or "theme-dark" in s:
        return "dark"
    if "prefers-color-scheme: light" in s or "data-theme=\"light\"" in s or ".light" in s:
        return "light"
    return "default"


def extract_from_css(css: str, rel: str, tokens):
    """tokens[name][scheme] = (value, rel). Walks blocks tracking selector/at-rule nesting."""
    stack = []
    i, n = 0, len(css)
    buf = ""
    while i < n:
        ch = css[i]
        if css.startswith("/*", i):
            j = css.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if ch == "{":
            stack.append(buf.strip())
            buf = ""
            i += 1
            continue
        elif ch == "}":
            # a declaration without a trailing semicolon (minified CSS): flush it before closing the block
            css = css[:i] + ";" + css[i:] if buf.strip() else css
            if buf.strip():
                n += 1
                continue
            if stack:
                stack.pop()
            buf = ""
            i += 1
            continue
        elif ch == ";" or ch == "\n":
            i += 1
            line = buf.strip()
            buf = ""
            m = re.match(r"(--[\w-]+|\$[\w-]+|@[\w-]+)\s*:\s*([^;]+)$", line)
            if m and not line.startswith("@media") and not line.startswith("@import"):
                name, val = m.group(1), re.sub(r"\s*!(default|important)\s*$", "", m.group(2).strip())
                sch = scheme_of(stack)
                ld = re.match(r"light-dark\(\s*(.+?)\s*,\s*(.+?)\s*\)$", val)
                if ld:
                    tokens[name]["light"] = (ld.group(1), rel)
                    tokens[name]["dark"] = (ld.group(2), rel)
                else:
                    tokens[name][sch] = (val, rel)
            continue
        buf += ch
        i += 1


def resolve(tokens, name, scheme, depth=0):
    """Resolve a token to a colour value for a scheme (fallback to default)."""
    if depth > 8 or name not in tokens:
        return None
    entry = tokens[name].get(scheme) or tokens[name].get("default") or tokens[name].get("light")
    if not entry:
        return None
    val = entry[0]
    m = re.match(r"var\(\s*(--[\w-]+)\s*(?:,\s*(.+))?\)$", val)
    if m:
        r = resolve(tokens, m.group(1), scheme, depth + 1)
        return r if r is not None else (m.group(2).strip() if m.group(2) else None)
    m = re.match(r"(\$[\w-]+|@[\w-]+)$", val)
    if m:
        return resolve(tokens, m.group(1), scheme, depth + 1)
    return val


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-pairs", type=int, default=80)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    tokens = defaultdict(dict)
    build = {"public", "_site", "out", "dist", "build", "resources/_gen"}
    if not ssg_generates_public(root):
        build -= GENERATED_ONLY_BY_SSG
    gi = root / ".gitignore"
    if gi.exists():
        for line in gi.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith(("#", "!")) and not any(c in line for c in "*?["):
                build.add(line.strip("/"))
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root).as_posix()
        at_root = rel in (".", "")
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
                       and not (at_root and d in INFRA_DIRS)
                       and f"{rel}/{d}".lstrip("./") not in build and (not at_root or d not in build)]
        for f in filenames:
            p = Path(dirpath) / f
            ext = p.suffix.lower()
            if ext not in STYLE_EXT and ext not in EMBED_EXT:
                continue
            size = file_size(p)
            if size is None or size > 3_000_000:
                continue
            txt = p.read_text(encoding="utf-8", errors="ignore")
            rel = p.relative_to(root).as_posix()
            if ext in STYLE_EXT:
                extract_from_css(txt, rel, tokens)
            else:
                for m in re.finditer(r"<style[^>]*>([\s\S]*?)</style>", txt, re.I):
                    extract_from_css(m.group(1), rel, tokens)

    # resolve to colours per scheme
    schemes = sorted({s for t in tokens.values() for s in t} | {"default"})
    if "default" in schemes and "light" in schemes:
        schemes.remove("default")  # treat default as light when a light scheme exists
    colours = {}  # (name, scheme) -> (rgb, hex, source)
    unresolved = []
    for name in tokens:
        for sch in schemes:
            val = resolve(tokens, name, sch)
            if val is None:
                continue
            rgb = to_rgb(val)
            if rgb is None:
                if any(k in val for k in ("rgba", "hsla", "oklch", "oklab", "/")):
                    unresolved.append((name, sch, val[:40]))
                continue
            src = (tokens[name].get(sch) or tokens[name].get("default") or tokens[name].get("light"))[1]
            colours[(name, sch)] = (rgb, to_hex(rgb), src)
    if not colours:
        print("No colour tokens found (custom properties / SCSS variables). Parse theme objects by hand.", file=sys.stderr)
        return 1

    names = sorted({n for n, _ in colours})
    fg = [n for n in names if FG_WORDS.search(n) and not (BG_WORDS.search(n) and not BOTH_WORDS.search(n))]
    bg = [n for n in names if BG_WORDS.search(n) or BOTH_WORDS.search(n)]
    pairs = []
    for sch in schemes:
        for f in fg:
            for b in bg:
                if f == b or (f, sch) not in colours or (b, sch) not in colours:
                    continue
                r = ratio(colours[(f, sch)][0], colours[(b, sch)][0])
                pairs.append({"scheme": sch, "fg": f, "fg_hex": colours[(f, sch)][1], "bg": b, "bg_hex": colours[(b, sch)][1],
                              "ratio": round(r, 2), "aa_text": r >= 4.5, "aa_large_or_nontext": r >= 3.0})
    pairs.sort(key=lambda p: (p["aa_text"], p["aa_large_or_nontext"], p["ratio"]))
    if a.json:
        print(json.dumps({"tokens": {f"{n}@{s}": {"hex": h, "source": src} for (n, s), (_, h, src) in colours.items()},
                          "pairs": pairs, "unresolved": unresolved}, indent=2))
        return 0

    print(f"# Colour tokens and contrast pairs — {root}\n")
    print(f"{len(names)} colour tokens, schemes: {', '.join(schemes)}. Pairs are name-based candidates (foreground-like × background-like); "
          "the expert confirms which are used together and adds pairs the names don't reveal.\n")
    print("## Tokens\n")
    print("| Token | " + " | ".join(schemes) + " | Source |")
    print("|---|" + "---|" * len(schemes) + "---|")
    for n in names:
        row = [colours[(n, s)][1] if (n, s) in colours else "—" for s in schemes]
        src = next((colours[(n, s)][2] for s in schemes if (n, s) in colours), "")
        print(f"| {n} | " + " | ".join(row) + f" | {src} |")
    if unresolved:
        print("\nNot resolved (alpha or non-sRGB — flatten with contrast.py flatten): " + ", ".join(f"{n}@{s}={v}" for n, s, v in unresolved[:15]))
    fails = [p for p in pairs if not p["aa_text"]]
    print(f"\n## Pairs failing 4.5 to 1 ({len(fails)} of {len(pairs)}; showing up to {a.max_pairs})\n")
    print("| Scheme | Foreground | Background | Ratio |")
    print("|---|---|---|---|")
    for p in fails[:a.max_pairs]:
        tag = "" if p["aa_large_or_nontext"] else " (also fails 3 to 1)"
        print(f"| {p['scheme']} | {p['fg']} {p['fg_hex']} | {p['bg']} {p['bg_hex']} | {p['ratio']}{tag} |")
    print("\nNext step for real failures: `python3 contrast.py fix <fg> <bg>` gives the minimal hue-preserving change and its ΔE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
