#!/usr/bin/env python3
"""Self-check for preflight.py: Phase 0 writes nothing, and --start sets the workspace up without losing anything.

    python3 scripts/test_preflight.py

Standard library and git only, writes to a temp dir.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from preflight import mode_for  # noqa: E402

EMPTY = Path(tempfile.mkdtemp())


def repo(git=True):
    root = Path(tempfile.mkdtemp()).resolve()
    (root / "index.html").write_text("<!doctype html><html lang=en><title>x</title><main><h1>x</h1></main></html>", encoding="utf-8")
    if git:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def run(root, *args):
    # no global git config or global ignore file: the answer must come from the repository alone
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "XDG_CONFIG_HOME": str(EMPTY)}
    return subprocess.run([sys.executable, str(HERE / "preflight.py"), str(root), *args], capture_output=True, text=True, env=env)


def tree(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if ".git/" not in str(p.relative_to(root)) + "/")


def test_phase_0_reports_and_writes_nothing():
    root = repo()
    before = tree(root)
    r = run(root)
    assert r.returncode == 0, r.stderr
    assert tree(root) == before, "the read-only run wrote into the repository"
    for line in ("- Git repository: yes", "- .a11y-audit/ ignored by git: no", "- Earlier audit: no", "- Project-owned UI files: 1",
                 "mini candidate", "# Stack detection"):
        assert line in r.stdout, f"missing: {line}\n{r.stdout[:600]}"
    plain = run(repo(git=False))
    assert "- Git repository: no" in plain.stdout and "ignored by git: not applicable" in plain.stdout


def test_audit_size_follows_the_thresholds_of_the_skill():
    assert [mode_for(n).split()[0] for n in (0, 1, 10, 11, 25, 26)] == ["none:", "mini", "mini", "lean", "lean", "full"]


def test_start_creates_the_workspace_and_leaves_gitignore_alone():
    root = repo()
    r = run(root, "--start")
    assert r.returncode == 0, r.stderr
    assert (root / ".a11y-audit" / "stack-detect.md").read_text(encoding="utf-8").startswith("# Stack detection")
    assert not (root / ".gitignore").exists() and ".gitignore: not changed" in r.stdout
    assert "re-audit" not in r.stdout and not (root / ".a11y-audit" / "previous").exists(), "a first audit is not a re-audit"


def test_ignore_adds_the_agreed_lines_once_and_keeps_what_was_there():
    root = repo()
    (root / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    assert run(root, "--ignore", "all").returncode == 2, "--ignore without --start must not write"
    assert (root / ".gitignore").read_text(encoding="utf-8") == "node_modules/\n"
    run(root, "--start", "--ignore", "report")
    run(root, "--start", "--ignore", "report")
    assert (root / ".gitignore").read_text(encoding="utf-8") == "node_modules/\n.a11y-audit/*\n!.a11y-audit/REPORT.md\n!.a11y-audit/coverage.md\n"
    assert "ignored by git: yes (.gitignore:2:.a11y-audit/*), REPORT.md stays trackable" in run(root).stdout
    other = repo()
    run(other, "--start", "--ignore", "all")
    assert (other / ".gitignore").read_text(encoding="utf-8") == ".a11y-audit/\n"
    assert "ignored by git: yes (.gitignore:1:.a11y-audit/)\n" in run(other).stdout


def test_a_re_audit_moves_the_earlier_audit_aside_as_a_whole():
    root = repo()
    ws = root / ".a11y-audit"
    for rel in ("findings/keyboard-focus.json", "personas/screen-reader-user.md", "briefs/_agents.json", "automated/summary.json",
                "REPORT.md", "coverage.md", "report-ids.json", "report-labels.de.json", "previous/REPORT.md"):
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(rel, encoding="utf-8")
    assert "- Earlier audit: yes, 1 findings files: this is a re-audit" in run(root).stdout
    r = run(root, "--start")
    assert r.returncode == 0 and "re-audit: the earlier audit is in" in r.stdout, r.stdout + r.stderr
    now = sorted(p.name for p in ws.iterdir())
    older = [n for n in now if n.startswith("previous-")]
    assert len(older) == 1 and (ws / older[0] / "REPORT.md").read_text(encoding="utf-8") == "previous/REPORT.md", "the older audit was lost"
    assert sorted(set(now) - set(older)) == ["previous", "report-labels.de.json", "stack-detect.md"], now
    assert sorted(p.name for p in (ws / "previous").iterdir()) == ["REPORT.md", "automated", "briefs", "coverage.md", "findings", "personas", "report-ids.json"]
    assert (ws / "previous" / "findings" / "keyboard-focus.json").read_text(encoding="utf-8") == "findings/keyboard-focus.json"
    again = run(root, "--start")
    assert "re-audit" not in again.stdout and (ws / "previous" / "REPORT.md").exists(), "a second start must not rotate an audit that has not begun"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} checks passed")
