#!/usr/bin/env python3
"""Colour tokens → contrast pairs, so the visual lens starts from numbers instead of grepping.

    python3 extract_colors.py <repo-root> [--json] [--max-pairs 80]

Reads CSS/SCSS/Less (and <style> blocks in HTML, Vue, Svelte, Astro and UIs embedded in source strings):
custom properties (--token: value), SCSS/Less variables ($x / @x), Tailwind v4 @theme blocks. Detects the
colour scheme of each definition (default, dark via prefers-color-scheme / [data-theme=dark] / .dark,
light-dark(a, b)) and the scope it is declared under. A declaration under :root, html, body or :host is the
base. One under a narrower selector or a media query (:root[data-contrast="high"], @media (prefers-contrast:
more), .card) is a variant: it is listed apart with what it changes, and never replaces the base value.
Resolves var() and variable references. Classifies tokens by NAME as foreground-like or background-like and
computes the WCAG ratio for every fg×bg pair per scheme, failing pairs first, and again under each variant
for the pairs that variant changes. Pairs are candidates: the expert checks which combinations are actually
used together. A pair of two status or brand colours of different families (--good on --warn) is left out.
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

# One colour function and nothing else: what is worth reporting when it cannot be turned into sRGB. A shadow or a
# gradient that merely contains a colour is not a colour token.
COLOUR_FUNCTION = re.compile(r"(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix)\((?:[^()]|\([^()]*\))*\)", re.I)
SCHEME_QUALIFIER = re.compile(r"""\[data-theme=["'](?:dark|light)["']\]|\[dark\]|\.(?:theme-)?(?:dark|light)(?![\w-])""", re.I)
BASE_SELECTOR = re.compile(r":root|:host|(?<![\w.#-])(?:html|body)(?![\w-])|\*|&|:(?:not|where|is)\(\s*\)|[\s>+~]", re.I)
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


def variant_of(selector_stack):
    """'' for a declaration in the base scope, otherwise the narrower scope it sits in, as written.

    The base is :root, html, body, :host or *, with or without what scheme_of reads as light or dark. Anything
    else narrows it: an attribute or class on the root (a reader setting), a component selector, a media or
    container query other than the colour scheme. A selector list is base when one of its selectors is.
    """
    parts = []
    for sel in selector_stack:
        sel = " ".join(sel.split())
        if sel.startswith("@"):
            m = re.match(r"@(?:media|container)\b(.*)", sel, re.I)
            if m and re.sub(r"\(\s*prefers-color-scheme\s*:\s*\w+\s*\)|\b(?:and|only|screen|all)\b|\s", "", m.group(1), flags=re.I):
                parts.append(sel)
            continue        # @layer, @supports, @theme and the like do not change which value applies
        # ponytail: a comma inside :is() or :where() splits too; parse the selector if that ever misfiles a token
        if sel and all(BASE_SELECTOR.sub("", SCHEME_QUALIFIER.sub("", part)) for part in sel.split(",")):
            parts.append(sel)
    return " ".join(parts)


def split_top(s: str):
    """Split at commas that are not inside parentheses: light-dark(rgb(1, 2, 3), #fff) has two arguments."""
    out, depth, cur = [], 0, ""
    for ch in s:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    return out + [cur.strip()]


def extract_from_css(css: str, rel: str, tokens):
    """tokens[name][(variant, scheme)] = (value, rel). Walks blocks tracking selector/at-rule nesting."""
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
                sch, var = scheme_of(stack), variant_of(stack)
                ld = re.match(r"light-dark\((.+)\)$", val, re.I)
                ld = split_top(ld.group(1)) if ld else []
                if len(ld) == 2:
                    tokens[name][(var, "light")] = (ld[0], rel)
                    tokens[name][(var, "dark")] = (ld[1], rel)
                else:
                    tokens[name][(var, sch)] = (val, rel)
            continue
        buf += ch
        i += 1


def entry_for(tokens, name, scheme, variant=""):
    """The declaration that applies: the variant's own for this scheme or for every scheme, otherwise the base."""
    t = tokens.get(name) or {}
    own = [(variant, scheme), (variant, "default")] + ([(variant, "light")] if scheme == "default" else []) if variant else []
    return next((t[k] for k in own + [("", scheme), ("", "default"), ("", "light")] if k in t), None)


def resolve(tokens, name, scheme, variant="", depth=0):
    """Resolve a token to a colour value for a scheme under a variant; a reference is followed under that variant too."""
    entry = entry_for(tokens, name, scheme, variant) if depth <= 8 else None
    if not entry:
        return None
    val = entry[0]
    m = re.match(r"var\(\s*(--[\w-]+)\s*(?:,\s*(.+))?\)$", val)
    if m:
        r = resolve(tokens, m.group(1), scheme, variant, depth + 1)
        return r if r is not None else (m.group(2).strip() if m.group(2) else None)
    m = re.match(r"(\$[\w-]+|@[\w-]+)$", val)
    if m:
        return resolve(tokens, m.group(1), scheme, variant, depth + 1)
    return val


def is_root_wide(variant: str) -> bool:
    return variant.startswith(("@", ":root", "html", "body", ":host"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-pairs", type=int, default=80)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    tokens = defaultdict(dict)
    build = {"public", "site", "_site", "out", "dist", "build", "resources/_gen"}      # the same set as the other two scanners
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
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
                             and not (at_root and d in INFRA_DIRS)
                             and f"{rel}/{d}".lstrip("./") not in build and (not at_root or d not in build))
        for f in sorted(filenames):     # sorted, so that "the first declaration" below means the same on every machine
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

    # A token declared only under narrower selectors (a component's own --btn-bg) has no base to differ from:
    # its first declaration is its base, and any later scope is a variant of that.
    for t in tokens.values():
        if not any(v == "" for v, _ in t):
            first = next(iter(t))[0]
            for v, s in [k for k in t if k[0] == first]:
                t[("", s)] = t.pop((v, s))
    variants = sorted({v for t in tokens.values() for v, _ in t} - {""}, key=lambda v: (not is_root_wide(v), v))

    # resolve to colours per scheme, for the base and for what each variant changes
    schemes = sorted({s for t in tokens.values() for _, s in t} | {"default"})
    if "default" in schemes and "light" in schemes:
        schemes.remove("default")  # treat default as light when a light scheme exists
    colours = {}  # (name, scheme, variant) -> (rgb, hex, source); a variant holds only what differs from the base
    unresolved = []
    for var in [""] + variants:
        for name in tokens:
            for sch in schemes:
                val = resolve(tokens, name, sch, var)
                if val is None:
                    continue
                rgb = to_rgb(val)
                if rgb is None:
                    if COLOUR_FUNCTION.fullmatch(val) and (name, sch, val[:60]) not in unresolved:
                        unresolved.append((name, sch, val[:60]))
                    continue
                base = colours.get((name, sch, ""))
                if not var or base is None or base[1] != to_hex(rgb):
                    colours[(name, sch, var)] = (rgb, to_hex(rgb), entry_for(tokens, name, sch, var)[1])
    if not colours:
        print("No colour tokens found (custom properties / SCSS variables). Parse theme objects by hand.", file=sys.stderr)
        return 1

    def colour(name, sch, var):
        return colours.get((name, sch, var)) or colours.get((name, sch, ""))

    def family(name):
        m = BOTH_WORDS.search(name)
        return m.group(2).lower() if m else None

    names = sorted({n for n, _, _ in colours})
    fg = [n for n in names if FG_WORDS.search(n) and not (BG_WORDS.search(n) and not BOTH_WORDS.search(n))]
    bg = [n for n in names if BG_WORDS.search(n) or BOTH_WORDS.search(n)]
    pairs, cross_family = [], 0
    for var in [""] + variants:
        for sch in schemes:
            touched = {n for n in names if (n, sch, var) in colours}    # under a variant: only the pairs it changes
            for f in fg if touched else []:
                for b in bg:
                    cf, cb = colour(f, sch, var), colour(b, sch, var)
                    if f == b or not cf or not cb or (var and f not in touched and b not in touched):
                        continue
                    if family(f) and family(b) and family(f) != family(b) and not BG_WORDS.search(b):
                        cross_family += not var     # --good on --warn: two signals, not text on a surface
                        continue
                    r = ratio(cf[0], cb[0])
                    pairs.append({"variant": var, "scheme": sch, "fg": f, "fg_hex": cf[1], "bg": b, "bg_hex": cb[1],
                                  "ratio": round(r, 2), "aa_text": r >= 4.5, "aa_large_or_nontext": r >= 3.0})
    pairs.sort(key=lambda p: (p["aa_text"], p["aa_large_or_nontext"], p["ratio"]))
    changed = [(v, n, s) for v in variants for n in names for s in schemes if (n, s, v) in colours]
    if a.json:
        print(json.dumps({"tokens": {f"{n}@{s}": {"hex": h, "source": src} for (n, s, v), (_, h, src) in colours.items() if not v},
                          "variants": {v: {f"{n}@{s}": {"hex": colours[(n, s, v)][1], "base": (colours.get((n, s, "")) or (0, None))[1],
                                                        "source": colours[(n, s, v)][2]} for vv, n, s in changed if vv == v}
                                       for v in variants},
                          "pairs": pairs, "unresolved": unresolved, "cross_family_pairs_left_out": cross_family}, indent=2))
        return 0

    def code(text):     # a selector in a table cell
        return "`" + text.replace("|", "\\|") + "`"

    base_names = sorted({n for n, _, v in colours if not v})
    print(f"# Colour tokens and contrast pairs — {root}\n")
    print(f"{len(base_names)} colour tokens, schemes: {', '.join(schemes)}. Pairs are name-based candidates (foreground-like × background-like); "
          "the expert confirms which are used together and adds pairs the names don't reveal."
          + (f" {cross_family} pairs of two status or brand colours of different families are left out." if cross_family else "") + "\n")
    print("## Tokens\n")
    print("| Token | " + " | ".join(schemes) + " | Source |")
    print("|---|" + "---|" * len(schemes) + "---|")
    for n in base_names:
        row = [colours[(n, s, "")][1] if (n, s, "") in colours else "—" for s in schemes]
        src = next((colours[(n, s, "")][2] for s in schemes if (n, s, "") in colours), "")
        print(f"| {n} | " + " | ".join(row) + f" | {src} |")
    if unresolved:
        print("\nNot resolved (alpha or non-sRGB — flatten with contrast.py flatten): " + ", ".join(f"{n}@{s}={v}" for n, s, v in unresolved[:15]))

    def pair_table(rows, with_variant):
        print("| " + ("Variant | " if with_variant else "") + "Scheme | Foreground | Background | Ratio |")
        print("|---|---|---|---|" + ("---|" if with_variant else ""))
        for p in rows[:a.max_pairs]:
            tag = "" if p["aa_large_or_nontext"] else " (also fails 3 to 1)"
            print("| " + (code(p["variant"]) + " | " if with_variant else "")
                  + f"{p['scheme']} | {p['fg']} {p['fg_hex']} | {p['bg']} {p['bg_hex']} | {p['ratio']}{tag} |")

    base_pairs = [p for p in pairs if not p["variant"]]
    fails = [p for p in base_pairs if not p["aa_text"]]
    print(f"\n## Pairs failing 4.5 to 1 ({len(fails)} of {len(base_pairs)}; showing up to {a.max_pairs})\n")
    pair_table(fails, False)
    if variants:
        print(f"\n## Variants ({len(variants)})\n")
        print("A variant is a narrower selector or a media query that gives tokens another value: a reader setting on the root, "
              "a print or contrast query, a component. Everything above is the base, which is what a visitor gets without it. "
              "Below is what each variant changes, with a referenced token followed under the variant.\n")
        print("| Variant | Token | Scheme | Base | Under the variant | Source |")
        print("|---|---|---|---|---|---|")
        for v, n, s in changed[:a.max_pairs]:
            base = colours.get((n, s, ""))
            print(f"| {code(v)} | {n} | {s} | {base[1] if base else '—'} | {colours[(n, s, v)][1]} | {colours[(n, s, v)][2]} |")
        if len(changed) > a.max_pairs:
            print(f"\n{len(changed) - a.max_pairs} more changed values are not shown; `--json` lists all of them.")
        var_pairs = [p for p in pairs if p["variant"]]
        var_fails = [p for p in var_pairs if not p["aa_text"]]
        print(f"\n## Pairs failing 4.5 to 1 under a variant ({len(var_fails)} of {len(var_pairs)} that a variant changes; showing up to {a.max_pairs})\n")
        pair_table(var_fails, True)
    print("\nNext step for real failures: `python3 contrast.py fix <fg> <bg>` gives the minimal hue-preserving change and its ΔE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
