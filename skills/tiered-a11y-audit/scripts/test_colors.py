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
import time
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
  --text-primary: #1a2530;
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
  .btn.danger { --btn-bg: #c93a3a; }
  .btn { --btn-bg: #0e7fc0; }
  .card { --dim: #cccccc; }
}
"""


def scan(css, *args, name="styles.css"):
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / name).write_text(css)
        r = subprocess.run([sys.executable, str(HERE / "extract_colors.py"), d, *args], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return r.stdout


def test_a_narrower_selector_is_a_variant_and_never_the_base():
    out = json.loads(scan(CSS, "--json"))
    tok, var = out["tokens"], out["variants"]
    assert tok["--dim@light"]["hex"] == "#5b6a78" and tok["--warn@light"]["hex"] == "#c07d08", tok
    assert var[':root[data-contrast="high"]']["--dim@light"] == {"hex": "#2e3b47", "base": "#5b6a78", "source": "styles.css"}
    assert var['html[data-cb="safe"], body.cb-safe']["--warn@dark"]["hex"] == "#a86e02"
    # a token that only refers to an overridden one changes with it when the variant is on the root itself,
    # and keeps the value it inherits when the variant is a component
    assert var[':root[data-contrast="high"]']["--text-soft@light"]["hex"] == "#2e3b47"
    assert set(var[".card"]) == {"--dim@light", "--dim@dark"}, var[".card"]
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
    # the same words in other spellings are schemes as well, and a class that merely starts with them is not
    out = json.loads(scan(":root{--fg:#111;--bg:#fff} .dark-mode{--fg:#eee;--bg:#111} [data-theme=dark]{--fg:#ddd} .darker{--bg:#333}", "--json"))
    assert out["tokens"]["--bg@dark"]["hex"] == "#111111" and out["tokens"]["--fg@dark"]["hex"] == "#dddddd", out["tokens"]
    assert list(out["variants"]) == [".darker"], list(out["variants"])


def test_a_token_of_a_component_has_its_plainest_declaration_as_base():
    out = json.loads(scan(CSS, "--json"))       # .btn.danger comes first in the file and is still the variant
    assert out["tokens"]["--btn-bg@light"]["hex"] == "#0e7fc0"
    assert out["variants"][".btn.danger"]["--btn-bg@light"]["base"] == "#0e7fc0"
    assert ".btn" not in out["variants"]


def test_a_selector_is_read_whole_however_it_is_laid_out():
    # the brace on a line of its own, a selector list over two lines, a value over two lines
    css = ":root\n{ --fg: #111; --bg:\n  #fff; }\n@media (prefers-contrast: more)\n{ :root { --fg: #000 } }\n.card,\n.panel\n{ --bg: #eee }\n"
    out = json.loads(scan(css, "--json"))
    assert out["tokens"]["--fg@default"]["hex"] == "#111111" and out["tokens"]["--bg@default"]["hex"] == "#ffffff", out["tokens"]
    assert set(out["variants"]) == {"@media (prefers-contrast: more)", ".card, .panel"}, list(out["variants"])
    # :is() with a comma inside it is one selector, and it is the base
    out = json.loads(scan(":root { --fg: #222 } :is(:root, html) { --fg: #111; --bg: #fff }", "--json"))
    assert out["tokens"]["--fg@default"]["hex"] == "#111111" and not out["variants"], out
    # minified, no last semicolon
    out = json.loads(scan(":root{--fg:#111;--bg:#fff}.card{--bg:#eee}", "--json"))
    assert out["tokens"]["--bg@default"]["hex"] == "#ffffff" and out["variants"][".card"]["--bg@default"]["hex"] == "#eeeeee"
    # Sass without braces or semicolons: every line that is a declaration still counts
    out = json.loads(scan("@use 'sass:math'\n$fg: #111\n.card\n  color: red\n$bg: #fff\n", "--json", name="styles.sass"))
    assert out["tokens"]["$fg@default"]["hex"] == "#111111" and out["tokens"]["$bg@default"]["hex"] == "#ffffff", out["tokens"]


def test_a_style_element_for_print_is_a_variant():
    html = '<style>:root { --fg: #111; --bg: #fff }</style><style media="print">:root { --fg: #000 }</style>'
    out = json.loads(scan(html, "--json", name="index.html"))
    assert out["tokens"]["--fg@default"]["hex"] == "#111111"
    assert out["variants"]["@media print"]["--fg@default"]["hex"] == "#000000"


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
    # text is not a signal, whatever it is called: body text on an accent surface is a pair
    assert ("light", "--text-primary", "--accent") in base and ("light", "--text-primary", "--good") in base
    assert out["cross_family_pairs_left_out"] > 0


def test_many_component_scopes_do_not_multiply_the_work():
    css = (":root {" + "".join(f"--text-{i}: #111; --bg-{i}: #fff;" for i in range(300)) + "}\n"
           + "".join(f".c{i} {{ --bg-{i}: #eee }}\n" for i in range(300)))
    start = time.time()
    out = json.loads(scan(css, "--json"))
    assert len(out["variants"]) == 300
    assert time.time() - start < 10, "every variant is paired against every token again"     # about 1 s; it was over 20


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
