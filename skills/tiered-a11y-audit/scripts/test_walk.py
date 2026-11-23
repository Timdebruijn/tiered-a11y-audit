#!/usr/bin/env python3
"""Self-check for the file walk of detect_stack, scan_patterns and extract_colors.

    python3 scripts/test_walk.py

Fails if a real UI directory is silently excluded again, or if one dangling symlink
takes down a whole scan. Standard library only, writes to a temp dir, no fixtures.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(script, root, *args):
    r = subprocess.run([sys.executable, str(HERE / script), str(root), *args],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"{script} exited {r.returncode}:\n{r.stderr}"
    return r.stdout


def make_app(root: Path, ssg=False):
    (root / "public").mkdir(parents=True)
    (root / "src/pages/roles").mkdir(parents=True)
    (root / "src/styles").mkdir(parents=True)
    (root / "public/index.html").write_text(
        '<html><head><title>t</title></head><body><div onclick="x()">go</div></body></html>')
    (root / "src/pages/roles/Admin.jsx").write_text('<img src="a.png">\n')
    (root / "src/styles/app.css").write_text(":root{--muted:#9a9a9a}\n*:focus{outline:none}\n")
    (root / "package.json").write_text('{"name":"app","dependencies":{"react":"18.2.0"}}')
    if ssg:
        (root / "hugo.toml").write_text('baseURL = "https://example.org"\n')


def test_app_dirs_are_counted():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        make_app(root)
        detect = run("detect_stack.py", root)
        assert "Project-owned UI files: 0" not in detect, "whole UI counted as infra or build output"
        assert "roles" not in detect.split("Not counted")[-1][:200], "src/pages/roles/ dropped as Ansible roles"
        patterns = run("scan_patterns.py", root)
        assert "| Click handler on a non-interactive element | 1 |" in patterns, \
            "public/index.html not scanned (it holds <html lang>, title and viewport)"
        assert "| Image without alt attribute | 1 |" in patterns, "src/pages/roles/ not scanned"
        colors = run("extract_colors.py", root)
        assert "#9a9a9a" in colors, "src/styles/ not scanned"


def test_ssg_output_is_still_excluded():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        make_app(root, ssg=True)
        patterns = run("scan_patterns.py", root)
        assert "| Click handler on a non-interactive element | 0 |" in patterns, \
            "public/ scanned although a static-site generator writes it"


def test_top_level_infra_is_still_excluded():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        make_app(root)
        (root / "ansible/roles/web/templates").mkdir(parents=True)
        (root / "ansible/roles/web/templates/vhost.html.j2").write_text('<img src="a.png">\n')
        patterns = run("scan_patterns.py", root)
        assert "| Image without alt attribute | 1 |" in patterns, "top-level ansible/ no longer excluded"


def test_dangling_symlink_survives():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        make_app(root)
        os.symlink("/nonexistent/target", root / "src/pages/Broken.jsx")
        os.symlink("/nonexistent/target", root / "src/styles/broken.css")
        assert "Project-owned UI files" in run("detect_stack.py", root)
        assert "| Image without alt attribute | 1 |" in run("scan_patterns.py", root)
        assert "#9a9a9a" in run("extract_colors.py", root)


def test_a_hand_written_site_or_public_folder_is_the_ui_for_all_three_scanners():
    # The fixture of the other tests has UI outside public/ as well, so a detector that dropped public/ still
    # counted something. Here the folder is all there is.
    for folder in ("site", "public"):
        for ssg, ui in ((False, True), (True, False)):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)
                (root / folder).mkdir()
                (root / folder / "index.html").write_text('<html><head><title>t</title></head><body><img src="a.png"></body></html>')
                (root / folder / "app.css").write_text(":root{--muted:#9a9a9a}\n")
                if ssg:
                    (root / "hugo.toml").write_text('baseURL = "https://example.org"\n')
                detect, patterns = run("detect_stack.py", root), run("scan_patterns.py", root)
                # the colour extractor exits 1 when it finds no tokens at all, which is the expected outcome next to a generator
                colours = subprocess.run([sys.executable, str(HERE / "extract_colors.py"), str(root)], capture_output=True, text=True).stdout
                what = f"{folder}/ {'next to' if ssg else 'without'} a generator config"
                assert ("Project-owned UI files: 0" not in detect) == ui, f"detector, {what}: {detect.split('## Scope')[1][:160]}"
                assert (f"Build output excluded: {folder}" in detect) != ui, f"detector, {what}"
                assert ("| Image without alt attribute | 1 |" in patterns) == ui, f"pattern scanner, {what}"
                assert ("#9a9a9a" in colours) == ui, f"colour extractor, {what}"


def test_generic_link_text_is_found_in_every_listed_language_and_the_row_says_which():
    samples = {"en": "Read more", "nl": "Lees meer", "de": "Weiterlesen", "fr": "En savoir plus", "es": "Leer m\u00e1s", "pt": "Saiba mais", "it": "Leggi di pi\u00f9"}
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "index.html").write_text("<html><body>" + "".join(f'<a href="/{k}">{v}</a>\n' for k, v in samples.items())
                                         + '<a href="/pricing">Pricing for teams</a><a href="/more-about-us">More about our team</a></body></html>', encoding="utf-8")
        out = run("scan_patterns.py", root)
        row = next(line for line in out.splitlines() if line.startswith("| Generic link/button text"))
        assert f"| {len(samples)} |" in row, f"expected {len(samples)} generic links, one per language: {row}"
        assert "phrases in en, nl, de, fr, es, pt, it; other languages not searched" in row, "a zero must not read as none for a language that was never searched"


def test_a_mention_of_a_page_is_no_page_and_test_code_is_no_interface():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "web/src").mkdir(parents=True)
        (root / "internal/api").mkdir(parents=True)
        (root / "firmware").mkdir()
        (root / "web/index.html").write_text('<!doctype html>\n<html lang="en"><head><title>x</title></head><body><div id="root"></div></body></html>')
        # a comment that names the element, in a component file
        (root / "web/src/A11y.tsx").write_text("/** Reader settings live as attributes on <html>, which is where the stylesheet reads them. */\n"
                                               "export function A11y() { return <button aria-label=\"Options\">Aa</button> }\n")
        # a whole page in a string, but in a test: a fixture, not the product
        (root / "internal/api/hardening_test.go").write_text('package api\nfunc TestCSP(t *testing.T) { body := "<html><body>hello</body></html>"; _ = body }\n')
        (root / "internal/api/doc.go").write_text("package api\n// Handler writes the <body> of the status page.\n")
        # a real page in source code, one tag per call as firmware writes it, without lang
        (root / "firmware/web.cpp").write_text('void page() {\n  client.println("<html>");\n  client.println("<head><title>Relay</title></head>");\n'
                                               '  client.println("<body><h1>Relay</h1></body></html>");\n}\n')
        # and the top of a page only: the rest is written by another function
        (root / "firmware/header.cpp").write_text('void head() {\n  client.println("<html lang=\\"en\\">");\n  client.println("<head><title>Relay</title></head>");\n}\n')
        detect, patterns = run("detect_stack.py", root), run("scan_patterns.py", root)
        embedded = detect.split("## Embedded HTML")[1].split("##")[0]
        assert "firmware/web.cpp" in embedded and "firmware/header.cpp" in embedded, embedded
        assert "hardening_test.go" not in embedded and "doc.go" not in embedded, embedded
        assert "1 test files with HTML in them" in detect, detect
        assert "| <html> without lang | 1 |" in patterns, [l for l in patterns.splitlines() if "without lang" in l]
        lang_rows = patterns.split("## Per-file: headings, titles, lang")[1]
        assert "| firmware/web.cpp |" in lang_rows and "MISSING" in lang_rows and "| web/index.html |" in lang_rows, lang_rows
        assert "A11y.tsx" not in lang_rows and "hardening_test.go" not in patterns and "doc.go" not in lang_rows, lang_rows


def test_the_count_that_picks_the_audit_size_says_what_it_is_made_of():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "web/src").mkdir(parents=True)
        (root / "docs").mkdir()
        (root / "web/index.html").write_text('<!doctype html><html lang="en"><head><title>x</title></head><body></body></html>')
        (root / "web/src/App.tsx").write_text("export const App = () => <main>hi</main>\n")
        (root / "web/src/styles.css").write_text(":root { --fg: #111 }\n")
        (root / "web/src/format.ts").write_text("export const ms = (n: number): string => `${n} ms`\nexport const ok = (a: number, b: number) => a < b\n")
        (root / "web/src/api.ts").write_text("export async function load(): Promise<Array<number>> { return (await fetch('/api')).json() }\n")
        (root / "web/src/render.worker.ts").write_text("const ctx = new OffscreenCanvas(1, 1).getContext('2d')\n")
        (root / "web/src/menu.js").write_text("document.querySelector('nav').addEventListener('click', toggle)\n")
        (root / "web/src/format.test.ts").write_text("import { ms } from './format'\n")
        (root / "web/vite.config.ts").write_text("export default {}\n")
        (root / "docs/guide.md").write_text("# Guide\n")
        (root / "web/package.json").write_text('{"scripts": {"dev": "vite"}, "dependencies": {"react": "19.0.0"}}')
        detect = run("detect_stack.py", root)
        scope = next(l for l in detect.splitlines() if l.startswith("Project-owned UI files:"))
        assert scope.startswith("Project-owned UI files: 5 ("), scope                    # html, tsx, css and the two scripts that touch the page
        for part in ("scripts that touch the page 2", "TSX 1", "HTML 1", "CSS 1", "2 scripts without DOM or markup", "2 test and config scripts", "1 Markdown"):
            assert part in scope, (part, scope)
        assert "backend" not in detect.lower(), "no backend marker in this tree"
        (root / "go.mod").write_text("module example.test/app\n")
        detect = run("detect_stack.py", root)
        assert "A backend sits beside the frontend (go.mod)" in detect and "ask how the whole application is started" in detect, detect[-900:]
        (root / "web/package.json").unlink()                                              # a backend alone has no dev server to mistake for the app
        assert "A backend sits beside" not in run("detect_stack.py", root)


def test_forms_and_controls_are_counted_for_the_audit_size():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "index.html").write_text('<form><label for="q">Search</label><input id="q" type="search"><input type="hidden" name="t">'
                                         '<select id="s"></select><input type="submit"></form>')
        out = run("scan_patterns.py", root)
        assert "| Forms (for the audit size: one search box is not a form flow) | 1 |" in out, out[:900]
        assert "| Form controls, labelled or not (for the audit size) | 2 |" in out, "hidden and submit inputs are not controls to fill in"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("all walk checks passed")
