#!/usr/bin/env python3
"""Self-check for extract_colors.py: which value of a token is the base, and what is only a variant.

    python3 scripts/test_colors.py

Fails if a value declared under a narrower selector is reported as the token's value again, which made every
pair in the table describe a reader setting instead of the default theme. Standard library only, temp dir.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

CSS = """
:root {
  --fg: #1a2530;
  --bg: #ffffff;
  --dim: #5b6a78;
  --text-soft: var(--dim);
  --accent: #0e7fc0;
  --accent-soft: #e3f2fb;
  --good: #0e9a6c;
  --warn: #c07d08;
  --link: light-dark(rgb(14, 127, 192), rgb(86, 196, 236));
  --overlay: rgba(0, 0, 0, 0.5);
  --shadow-pop: 0 10px 30px light-dark(rgba(20, 35, 50, 0.18), rgba(0, 0, 0, 0.6));
}
:root[data-contrast="high"] { --dim: #2e3b47; }
html[data-cb="safe"], body.cb-safe { --warn: #a86e02 }
@media (prefers-contrast: more) { :root { --fg: #000000; } }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg: #10161c; } }
[data-theme="dark"] { --fg: #e8eef4; }
@layer components {
  .btn { --btn-bg: #0e7fc0; }
  .btn.danger { --btn-bg: #c93a3a; }
}
"""


def scan(css, *args):
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "styles.css").write_text(css)
        r = subprocess.run([sys.executable, str(HERE / "extract_colors.py"), d, *args], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return r.stdout


def test_a_narrower_selector_is_a_variant_and_never_the_base():
    out = json.loads(scan(CSS, "--json"))
    tok, var = out["tokens"], out["variants"]
    assert tok["--dim@light"]["hex"] == "#5b6a78" and tok["--warn@light"]["hex"] == "#c07d08", tok
    assert var[':root[data-contrast="high"]']["--dim@light"] == {"hex": "#2e3b47", "base": "#5b6a78", "source": "styles.css"}
    assert var['html[data-cb="safe"], body.cb-safe']["--warn@dark"]["hex"] == "#a86e02"
    # a token that only refers to an overridden one changes with it
    assert var[':root[data-contrast="high"]']["--text-soft@light"]["hex"] == "#2e3b47"
    # a media query other than the colour scheme is a variant too
    assert var["@media (prefers-contrast: more)"]["--fg@light"]["hex"] == "#000000"
    assert tok["--fg@light"]["hex"] == "#1a2530"


def test_light_and_dark_stay_schemes():
    out = json.loads(scan(CSS, "--json"))
    tok = out["tokens"]
    assert tok["--bg@dark"]["hex"] == "#10161c" and tok["--bg@light"]["hex"] == "#ffffff"
    assert tok["--fg@dark"]["hex"] == "#e8eef4"
    assert not any("data-theme" in v or "prefers-color-scheme" in v for v in out["variants"]), list(out["variants"])
    # light-dark() with commas inside its arguments
    assert tok["--link@light"]["hex"] == "#0e7fc0" and tok["--link@dark"]["hex"] == "#56c4ec"


def test_a_token_of_a_component_has_its_first_declaration_as_base():
    out = json.loads(scan(CSS, "--json"))
    assert out["tokens"]["--btn-bg@light"]["hex"] == "#0e7fc0"
    assert out["variants"][".btn.danger"]["--btn-bg@light"]["base"] == "#0e7fc0"
    assert ".btn" not in out["variants"]


def test_pairs_are_of_the_base_and_a_variant_lists_only_what_it_changes():
    out = json.loads(scan(CSS, "--json"))
    base = {(p["scheme"], p["fg"], p["bg"]): p for p in out["pairs"] if not p["variant"]}
    assert base[("light", "--dim", "--bg")]["fg_hex"] == "#5b6a78"
    high = [p for p in out["pairs"] if p["variant"] == ':root[data-contrast="high"]']
    assert high and all("--dim" in (p["fg"], p["bg"]) or "--text-soft" in (p["fg"], p["bg"]) for p in high), high
    assert {p["fg_hex"] for p in high if p["fg"] == "--dim"} == {"#2e3b47"}
    # two signals of different families are not text on a surface; a tint of the same family is
    assert ("light", "--good", "--warn") not in base and ("light", "--warn", "--good") not in base
    assert ("light", "--accent", "--accent-soft") in base
    assert out["cross_family_pairs_left_out"] > 0


def test_only_a_colour_is_reported_as_not_resolved():
    out = json.loads(scan(CSS, "--json"))
    names = {n for n, _, _ in out["unresolved"]}
    assert names == {"--overlay"}, out["unresolved"]


def test_the_table_names_the_variants():
    md = scan(CSS)
    assert "| --dim | #5b6a78 |" in md
    assert '| `:root[data-contrast="high"]` | --dim | light | #5b6a78 | #2e3b47 | styles.css |' in md, md
    assert "under a variant" in md
    assert "## Variants" not in scan(":root { --fg: #111; --bg: #fff }")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
