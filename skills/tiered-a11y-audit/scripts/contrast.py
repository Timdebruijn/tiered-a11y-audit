#!/usr/bin/env python3
"""WCAG contrast ratios and minimal, hue-preserving colour fixes.

Commands:
  ratio FG BG                         contrast ratio + AA/AAA verdicts
  fix FG BG [--target 4.5] [--adjust fg|bg|auto]
                                      smallest lightness change (OKLCH, hue kept) that meets target;
                                      auto (default) adjusts whichever colour needs the smaller shift
  batch [--target 4.5] [--json]       read "FG BG label..." lines from stdin; ratio + fix for failures
                                      (comment lines start with "# " or "//")
  flatten COLOR BG                    flatten an rgba()/#rrggbbaa colour over an opaque background → hex

Targets: --target 4.5 (AA text, default), --target 3 or --large (AA large text / non-text), --target 7 (AAA).

Colours: #rgb, #rrggbb, rgb(r, g, b), or CSS named colours black/white/grey/gray.
Semi-transparent colours (rgba(), #rrggbbaa) are only accepted by `flatten`; ratio/fix/batch need opaque colours.
Pure standard library.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys

NAMED = {"black": "#000000", "white": "#ffffff", "gray": "#808080", "grey": "#808080", "red": "#ff0000",
         "green": "#008000", "blue": "#0000ff", "transparent": None}


def parse(c: str) -> tuple[float, float, float]:
    s = c.strip().lower()
    if s in NAMED:
        if NAMED[s] is None:
            raise ValueError("transparent has no contrast; flatten against the background first")
        s = NAMED[s]
    m = re.fullmatch(r"#?([0-9a-f]{3}|[0-9a-f]{6})", s)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)\s*(?:[,/]\s*([\d.]+%?))?\s*\)", s)
    if m:
        if m.group(4) not in (None, "1", "100%", "1.0"):
            raise ValueError(f"alpha not supported in {c!r}; flatten against the background first")
        return tuple(float(m.group(i)) / 255 for i in (1, 2, 3))  # type: ignore[return-value]
    raise ValueError(f"unrecognised colour: {c!r}")


def parse_alpha(c: str) -> tuple[tuple[float, float, float], float]:
    """Parse a colour that may carry alpha: #rrggbbaa, #rgba, rgba(r,g,b,a)."""
    s = c.strip().lower()
    m = re.fullmatch(r"#?([0-9a-f]{4}|[0-9a-f]{8})", s)
    if m:
        h = m.group(1)
        if len(h) == 4:
            h = "".join(ch * 2 for ch in h)
        rgb = tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        return rgb, int(h[6:8], 16) / 255  # type: ignore[return-value]
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)\s*(?:[,/]\s*([\d.]+)(%?))?\s*\)", s)
    if m:
        rgb = tuple(float(m.group(i)) / 255 for i in (1, 2, 3))
        a = 1.0
        if m.group(4) is not None:
            a = float(m.group(4)) / (100 if m.group(5) else 1)
        return rgb, a  # type: ignore[return-value]
    return parse(c), 1.0


def flatten(color: str, background: str) -> str:
    (r, g, b), a = parse_alpha(color)
    br, bg_, bb = parse(background)
    return to_hex((r * a + br * (1 - a), g * a + bg_ * (1 - a), b * a + bb * (1 - a)))


def to_hex(rgb) -> str:
    return "#" + "".join(f"{round(max(0.0, min(1.0, v)) * 255):02x}" for v in rgb)


def lin(v: float) -> float:
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def delin(v: float) -> float:
    return 12.92 * v if v <= 0.0031308 else 1.055 * (v ** (1 / 2.4)) - 0.055


def luminance(rgb) -> float:
    # WCAG 2.x relative luminance (uses 0.03928 threshold historically; difference is negligible)
    r, g, b = (lin(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def hex_ratio(a, b) -> float:
    # ratio after rounding to 8-bit hex, as the browser will render it
    return ratio(parse(to_hex(a)), parse(to_hex(b)))


# --- OKLab / OKLCH (Björn Ottosson) ---------------------------------------
def srgb_to_oklab(rgb):
    r, g, b = (lin(v) for v in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def oklab_to_linear(lab):
    L, a, b = lab
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def in_gamut(lin_rgb, eps=1e-6) -> bool:
    return all(-eps <= v <= 1 + eps for v in lin_rgb)


def oklch_to_srgb(L, C, h):
    """Convert OKLCH to sRGB, reducing chroma (binary search) if out of gamut."""
    def make(c):
        return oklab_to_linear((L, c * math.cos(h), c * math.sin(h)))
    lo, hi = 0.0, C
    if in_gamut(make(C)):
        best = C
    else:
        best = 0.0
        for _ in range(30):
            mid = (lo + hi) / 2
            if in_gamut(make(mid)):
                best, lo = mid, mid
            else:
                hi = mid
    rgb_lin = make(best)
    return tuple(delin(max(0.0, min(1.0, v))) for v in rgb_lin), best


def delta_e_ok(a, b) -> float:
    la, lb = srgb_to_oklab(a), srgb_to_oklab(b)
    return math.dist(la, lb)


def find_fix(adjust_rgb, other_rgb, target: float):
    """Return candidate fixes (darker / lighter) for adjust_rgb so contrast with other_rgb >= target."""
    L, a, b = srgb_to_oklab(adjust_rgb)
    C, h = math.hypot(a, b), math.atan2(b, a)
    out = []
    for direction in (-1, 1):
        step = 0.0005
        Lc = L
        while 0.0 <= Lc <= 1.0:
            cand, c_used = oklch_to_srgb(Lc, C, h)
            cand = parse(to_hex(cand))
            if hex_ratio(cand, other_rgb) >= target:
                out.append({
                    "direction": "darker" if direction < 0 else "lighter",
                    "hex": to_hex(cand),
                    "ratio": round(hex_ratio(cand, other_rgb), 2),
                    "delta_e_ok": round(delta_e_ok(adjust_rgb, cand), 4),
                    "lightness_change": round(Lc - L, 4),
                    "chroma_reduced": c_used < C - 1e-4,
                })
                break
            Lc += direction * step
    out.sort(key=lambda d: d["delta_e_ok"])
    return out


def verdicts(r: float) -> dict:
    return {
        "AA_normal_text_4.5": r >= 4.5, "AA_large_text_3": r >= 3.0, "AA_non_text_3": r >= 3.0,
        "AAA_normal_text_7": r >= 7.0, "AAA_large_text_4.5": r >= 4.5,
    }


def subtlety(de: float) -> str:
    if de <= 0.04:
        return "barely noticeable"
    if de <= 0.08:
        return "subtle (tier 2)"
    if de <= 0.15:
        return "noticeable (tier 2 if not the logo/brand mark, else tier 3)"
    return "significant (tier 3 or split into a text-only token)"


def cmd_ratio(a):
    fg, bg = parse(a.fg), parse(a.bg)
    r = ratio(fg, bg)
    res = {"fg": to_hex(fg), "bg": to_hex(bg), "ratio": round(r, 2), **verdicts(r)}
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"{res['fg']} on {res['bg']}: {res['ratio']}:1")
        for k, v in verdicts(r).items():
            print(f"  {'PASS' if v else 'fail'}  {k}")


def fix_result(fg_s, bg_s, target, adjust):
    fg, bg = parse(fg_s), parse(bg_s)
    r = ratio(fg, bg)
    res = {"fg": to_hex(fg), "bg": to_hex(bg), "ratio": round(r, 2), "target": target, "adjust": adjust}
    if r >= target:
        res["status"] = "already passes"
        return res
    cands = []
    for side in (("fg", "bg") if adjust == "auto" else (adjust,)):
        base, other = (fg, bg) if side == "fg" else (bg, fg)
        for c in find_fix(base, other, target):
            c["adjusted"] = side
            cands.append(c)
    cands.sort(key=lambda d: d["delta_e_ok"])
    res["status"] = "fix found" if cands else "no fix by lightness alone"
    res["options"] = cands
    if cands:
        res["best"] = cands[0]
        res["best"]["subtlety"] = subtlety(cands[0]["delta_e_ok"])
        res["adjust"] = cands[0]["adjusted"]
    return res


def cmd_fix(a):
    res = fix_result(a.fg, a.bg, a.target, a.adjust)
    if a.json:
        print(json.dumps(res, indent=2))
        return
    print(f"{res['fg']} on {res['bg']}: {res['ratio']}:1 (target {a.target}:1, adjusting {a.adjust})")
    if res["status"] == "already passes":
        print("  already passes")
        return
    if not res.get("options"):
        print("  no fix possible by changing lightness alone — adjust the other colour")
        return
    for i, o in enumerate(res["options"]):
        tag = "BEST" if i == 0 else "alt "
        extra = ", chroma reduced to stay in sRGB" if o["chroma_reduced"] else ""
        print(f"  {tag} {o['adjusted']} {o['direction']:7s} {o['hex']}  {o['ratio']}:1  ΔE(OK)={o['delta_e_ok']}  ΔL={o['lightness_change']}{extra}")
    print(f"  → {res['best']['subtlety']}")


def cmd_flatten(a):
    print(flatten(a.color, a.bg))


def cmd_batch(a):
    rows = []
    for raw in sys.stdin:
        line = raw.strip()
        if not line or line.startswith(("# ", "//")):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        label = " ".join(parts[2:])
        try:
            res = fix_result(parts[0], parts[1], a.target, a.adjust)
        except ValueError as e:
            rows.append({"label": label, "error": str(e)})
            continue
        res["label"] = label
        rows.append(res)
    if a.json:
        print(json.dumps(rows, indent=2))
        return
    print(f"| Label | FG | BG | Ratio | Target {a.target} | Suggested | New ratio | ΔE(OK) | Impression |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if "error" in r:
            print(f"| {r['label']} | – | – | – | error: {r['error']} | | | | |")
            continue
        if r["status"] == "already passes":
            print(f"| {r['label']} | {r['fg']} | {r['bg']} | {r['ratio']} | pass | | | | |")
        elif r.get("best"):
            b = r["best"]
            print(f"| {r['label']} | {r['fg']} | {r['bg']} | {r['ratio']} | FAIL | {b['adjusted']} → {b['hex']} ({b['direction']}) | {b['ratio']} | {b['delta_e_ok']} | {b['subtlety']} |")
        else:
            print(f"| {r['label']} | {r['fg']} | {r['bg']} | {r['ratio']} | FAIL | – | – | – | adjust other colour |")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ratio"); p.add_argument("fg"); p.add_argument("bg"); p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_ratio)
    p = sub.add_parser("flatten"); p.add_argument("color"); p.add_argument("bg"); p.set_defaults(func=cmd_flatten)
    for name, fn in (("fix", cmd_fix), ("batch", cmd_batch)):
        p = sub.add_parser(name)
        if name == "fix":
            p.add_argument("fg"); p.add_argument("bg")
        p.add_argument("--target", type=float, default=4.5)
        p.add_argument("--large", action="store_true", help="large text / non-text: target 3:1")
        p.add_argument("--adjust", choices=["fg", "bg", "auto"], default="auto",
                       help="which colour to change; auto (default) tries both and picks the smaller shift")
        p.add_argument("--json", action="store_true")
        p.set_defaults(func=fn)
    a = ap.parse_args()
    if getattr(a, "large", False):
        a.target = 3.0
    try:
        a.func(a)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
