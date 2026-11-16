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
