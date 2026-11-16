#!/usr/bin/env python3
"""Phase 0 in one command, and the workspace set-up after the user answered.

    python3 preflight.py <repo-root>                             # reads only, prints everything Phase 1 needs
    python3 preflight.py <repo-root> --start [--ignore all|report]

Without --start nothing is written anywhere. It prints whether this is a git repository, whether
.a11y-audit/ is already ignored, whether an earlier audit is present, which audit size the number of
project-owned UI files suggests, which run scripts and tools are available, a scratch directory outside the
repository to offer, and then the full output of detect_stack.py.

--start is for after the user's answer. It creates .a11y-audit/, moves an earlier audit as a whole into
.a11y-audit/previous/ (an older previous/ is kept under previous-<timestamp>/, nothing is deleted), and
writes stack-detect.md. --ignore adds the agreed lines to .gitignore, once: "all" ignores the workspace,
"report" ignores it but keeps REPORT.md and coverage.md trackable. Standard library only.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from detect_stack import analyse, finalise, print_human  # noqa: E402

WS = ".a11y-audit"
IGNORE = {"all": [f"{WS}/"], "report": [f"{WS}/*", f"!{WS}/REPORT.md", f"!{WS}/coverage.md"]}
RUN_SCRIPTS = ("dev", "start", "serve", "preview", "storybook")
# ponytail: a fixed list of names and the macOS app path; a browser installed elsewhere reads as "not found"
BROWSERS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge", "microsoft-edge")
MAC_BROWSERS = ("/Applications/Google Chrome.app", "/Applications/Microsoft Edge.app", "/Applications/Chromium.app")


def git(root: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10)


def is_git(root: Path) -> bool:
    try:
        return git(root, "rev-parse", "--is-inside-work-tree").stdout.strip() == "true"
    except (OSError, subprocess.TimeoutExpired):
        return False


def mode_for(ui_files: int) -> str:
    if ui_files == 0:
        return "none: no user interface found, ask what to audit"
    if ui_files <= 10:
        return "mini candidate (confirm with the pattern inventory in Phase 3: few forms and widgets)"
    return "lean" if ui_files <= 25 else "full"


def detector_text(r: dict) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_human(r)
    return buf.getvalue()


def report(root: Path, r: dict) -> str:
    ws = root / WS
    in_git = is_git(root)
    if not in_git:
        ignored = "not applicable"
    else:
        # ask about a file both ignore choices cover; REPORT.md is deliberately trackable under "report"
        ci = git(root, "check-ignore", "-v", f"{WS}/findings/x.json")
        ignored = f"yes ({ci.stdout.split(chr(9))[0].strip()})" if ci.returncode == 0 else "no"
        if ci.returncode == 0 and git(root, "check-ignore", "-q", f"{WS}/REPORT.md").returncode != 0:
            ignored += ", REPORT.md stays trackable"
    earlier = sorted(p.name for p in (ws / "findings").glob("*.json")) if (ws / "findings").is_dir() else []
    scripts = sorted({s for p in r["packages"] for s in p["scripts"] if s in RUN_SCRIPTS})
    browser = next((b for b in BROWSERS if shutil.which(b)), None) or next((b for b in MAC_BROWSERS if Path(b).exists()), None)
    lines = [
        f"# Preflight: {root}", "",
        f"- Git repository: {'yes' if in_git else 'no'}",
        f"- {WS}/ ignored by git: {ignored}",
        f"- Earlier audit: {'yes, ' + str(len(earlier)) + ' findings files: this is a re-audit' if earlier else 'no'}",
        f"- Project-owned UI files: {r['project_ui_files']}",
        f"- Audit size they suggest: {mode_for(r['project_ui_files'])}",
        f"- Run scripts in package.json: {', '.join(scripts) or 'none found'}",
        f"- node: {shutil.which('node') or 'not found'}",
        f"- Installed browser for the scan: {browser or 'not found (Playwright would download one, about 150 MB)'}",
        f"- Scratch directory to offer, outside the repository: {Path(tempfile.gettempdir()) / 'a11y-scan'}",
        "- Nothing was written. After the user's answer, run this script again with --start.", "",
    ]
    return "\n".join(lines) + "\n" + detector_text(r)


def rotate(ws: Path) -> bool:
    """Move an earlier audit as a whole into previous/, so nothing of it is mistaken for this run's output."""
    if not (ws / "findings").is_dir():
        return False
    prev = ws / "previous"
    if prev.exists():
        prev.rename(ws / f"previous-{time.strftime('%Y%m%d-%H%M%S')}")
    prev.mkdir()
    for p in list(ws.iterdir()):
        # the labels of a translated report stay: they are the user's wording, not output of one audit
        if not p.name.startswith("previous") and not p.name.startswith("report-labels."):
            shutil.move(str(p), str(prev / p.name))
    return True


def add_ignore(root: Path, choice: str) -> list:
    gi = root / ".gitignore"
    have = gi.read_text(encoding="utf-8", errors="replace").splitlines() if gi.exists() else []
    new = [line for line in IGNORE[choice] if line not in have]
    if new:
        text = "\n".join(have + new) + "\n"
        gi.write_text(text, encoding="utf-8")
    return new


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--start", action="store_true", help="create the workspace, move an earlier audit aside, write stack-detect.md")
    ap.add_argument("--ignore", choices=sorted(IGNORE), help="with --start: add these lines to .gitignore (only with the user's permission)")
    ap.add_argument("--max-files", type=int, default=60_000)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2
    if a.ignore and not a.start:
        print("--ignore writes to the repository, so it only works together with --start", file=sys.stderr)
        return 2
    r = finalise(analyse(root, a.max_files))
    if not a.start:
        print(report(root, r))
        return 0
    ws = root / WS
    ws.mkdir(exist_ok=True)
    re_audit = rotate(ws)
    (ws / "stack-detect.md").write_text(detector_text(r), encoding="utf-8")
    added = add_ignore(root, a.ignore) if a.ignore else []
    print(f"workspace ready: {ws}")
    print(f"stack-detect.md written ({r['project_ui_files']} project-owned UI files)")
    if re_audit:
        print(f"re-audit: the earlier audit is in {ws / 'previous'}; give that path to merge_findings.py --previous in Phase 6")
    print(f".gitignore: added {', '.join(added)}" if added else ".gitignore: not changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
