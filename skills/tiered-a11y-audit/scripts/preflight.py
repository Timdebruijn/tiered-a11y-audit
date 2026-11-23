#!/usr/bin/env python3
"""Phase 0 in one command, and the workspace set-up after the user answered.

    python3 preflight.py <repo-root>                                        # reads only
    python3 preflight.py <repo-root> --start [--ignore all|report] [--fresh]

Without --start nothing is written anywhere. It prints whether this is a git repository, whether
.a11y-audit/ is ignored (asked of git for three kinds of file in it, so "yes" means all of them), whether a
finished earlier audit or an unfinished run is in the workspace, which audit size the number of
project-owned UI files suggests, which run scripts and tools are available, a scratch directory outside the
repository to offer, whether a person is there to answer questions, and then the full output of detect_stack.py.

--start is for after the user's answer. It creates .a11y-audit/ and writes stack-detect.md. A finished
earlier audit (one with a REPORT.md) is moved as a whole into .a11y-audit/previous/; an older previous/ is
kept under previous-<timestamp>/, so nothing is deleted. A run without a REPORT.md is taken to be in
progress and left where it is, so running --start twice is harmless; --fresh moves it aside as well.
--ignore appends the agreed lines to .gitignore, once, in the file's own line endings and without touching
what is there: "all" ignores the workspace, "report" ignores it but keeps REPORT.md and coverage.md
trackable. It does not write through a symbolic link, neither for .gitignore nor for the workspace.
Standard library only.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from detect_stack import RUN_SCRIPTS, analyse, backend_note, finalise, made_up_of, print_human  # noqa: E402

WS = ".a11y-audit"
IGNORE = {"all": [f"{WS}/"], "report": [f"{WS}/*", f"!{WS}/REPORT.md", f"!{WS}/coverage.md"]}
WHOLE = {WS, f"{WS}/", f"/{WS}", f"/{WS}/"}                 # the spellings that ignore the workspace as a whole
PROBES = ("findings/x.json", "automated/x.png", "stack-profile.md")
KEPT = ("previous", "report-labels.")                       # never part of one audit's output
# ponytail: a fixed list of names and the macOS app path; a browser installed elsewhere reads as "not found"
BROWSERS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge", "microsoft-edge")
MAC_BROWSERS = ("/Applications/Google Chrome.app", "/Applications/Microsoft Edge.app", "/Applications/Chromium.app")


def git(root: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10)


def git_state(root: Path) -> str:
    """'yes', 'no', or 'unknown (why)' when git cannot say, which is not the same as no."""
    try:
        r = git(root, "rev-parse", "--is-inside-work-tree")
    except FileNotFoundError:
        return "unknown (git is not installed)"
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"unknown ({type(e).__name__})"
    if r.stdout.strip() == "true":
        return "yes"
    if r.returncode == 0 or "not a git repository" in r.stderr:
        return "no"
    return f"unknown (git refused: {(r.stderr.strip().splitlines() or ['no reason given'])[0]})"


def ignore_state(root: Path) -> str:
    # exit 0 of a plain check-ignore means ignored; with -v it also means "a negation matched", so -v only names the rule
    hit = [git(root, "check-ignore", "-q", f"{WS}/{p}").returncode == 0 for p in PROBES]
    if not any(hit):
        return "no"
    if not all(hit):
        return "partly: some of its files would be committed, so ask question 1"
    rule = git(root, "check-ignore", "-v", f"{WS}/{PROBES[0]}").stdout.split("\t")[0].strip()
    trackable = git(root, "check-ignore", "-q", f"{WS}/REPORT.md").returncode != 0
    return f"yes ({rule})" + (", REPORT.md stays trackable" if trackable else "")


def workspace_state(ws: Path) -> str:
    """none | finished | unfinished | invalid."""
    if ws.is_symlink() or (ws.exists() and not ws.is_dir()):
        return "invalid"
    if not ws.exists():
        return "none"
    if (ws / "REPORT.md").is_file():
        return "finished"
    own = [p for p in ws.iterdir() if not p.name.startswith(KEPT) and p.name != "stack-detect.md"]
    return "unfinished" if own else "none"


EARLIER = {
    "none": "no",
    "finished": "yes, finished (it has a REPORT.md): this is a re-audit, and --start moves it into previous/",
    "unfinished": "an unfinished run is in the workspace (no REPORT.md): --start leaves it in place so it can go on; "
                  "--start --fresh moves it aside to begin again",
    "invalid": f"{WS} exists but is not a plain directory (a file or a symbolic link): --start refuses it, ask the user",
}


def someone_to_answer() -> str:
    """Whether a person is on the other end. Claude Code sets CLAUDE_CODE_SESSION_ATTENDED to 1 in an interactive session
    and to 0 in print mode (measured on 2.1.319; the variable is not documented). Anything else: this script cannot tell."""
    return {"1": "yes", "0": "no"}.get(os.environ.get("CLAUDE_CODE_SESSION_ATTENDED", ""), "unknown")


def mode_for(ui_files: int) -> str:
    if ui_files == 0:
        return "none: no user interface found, ask what to audit"
    if ui_files <= 10:
        return "mini candidate (confirm with the pattern inventory in Phase 2: few forms and widgets)"
    return "lean" if ui_files <= 25 else "full"


def detector_text(r: dict) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_human(r)
    return buf.getvalue()


def report(root: Path, r: dict) -> str:
    in_git = git_state(root)
    ignored = ignore_state(root) if in_git == "yes" else "not applicable" if in_git == "no" else "unknown"
    scripts = sorted({s for p in r["packages"] for s in p["scripts"] if s in RUN_SCRIPTS})
    answer = someone_to_answer()
    reach = {"yes": "yes: ask the Phase 1 questions and wait for the answer",
             "no": "no, this session is unattended. Your next message is the Phase 1 message, written as the list of what you take "
                   "(for each question the option that needs no permission): it is the only record of what was assumed. Then go on without waiting",
             "unknown": "unknown: ask the Phase 1 questions and wait, unless the request itself says to go on without asking"}[answer]
    then = ("Go on with --start once the Phase 1 message is posted, without --ignore: nobody agreed to an edit of .gitignore."
            if answer == "no" else "After the user's answer, run this script again with --start.")
    browser = next((b for b in BROWSERS if shutil.which(b)), None) or next((b for b in MAC_BROWSERS if Path(b).exists()), None)
    lines = [
        f"# Preflight: {root}", "",
        f"- Git repository: {in_git}",
        f"- {WS}/ ignored by git: {ignored}",
        f"- Earlier audit: {EARLIER[workspace_state(root / WS)]}",
        f"- Project-owned UI files: {r['project_ui_files']}{made_up_of(r)}",
        f"- Audit size they suggest: {mode_for(r['project_ui_files'])}",
        f"- Run scripts in package.json: {', '.join(scripts) or 'none found'}",
        *([f"- Backend: {backend_note(r)}"] if r["backend"] else []),
        f"- node: {shutil.which('node') or 'not found'}",
        f"- Installed browser for the scan: {browser or 'not found (Playwright would download one, about 150 MB)'}",
        f"- Scratch directory to offer, outside the repository: {Path(tempfile.gettempdir()) / 'a11y-scan'}",
        f"- Someone to answer questions: {reach}",
        f"- Nothing was written. {then}", "",
    ]
    return "\n".join(lines) + "\n" + detector_text(r)


def rotate(ws: Path) -> None:
    """Move the audit in the workspace as a whole into previous/, so nothing of it is mistaken for this run's output."""
    prev = ws / "previous"
    if prev.exists():
        prev.rename(ws / f"previous-{time.strftime('%Y%m%d-%H%M%S')}")
    prev.mkdir()
    for p in list(ws.iterdir()):
        if not p.name.startswith(KEPT):
            shutil.move(str(p), str(prev / p.name))


def add_ignore(root: Path, choice: str) -> tuple:
    """(lines added, a note when nothing could or needed to be done). Appends only; never rewrites what is there."""
    gi = root / ".gitignore"
    if gi.is_symlink():
        return [], f".gitignore is a symbolic link and was left alone; add where it points: {', '.join(IGNORE[choice])}"
    raw = gi.read_bytes() if gi.exists() else b""
    have = {line.strip() for line in raw.decode("utf-8", errors="replace").split("\n")}
    whole = sorted(have & WHOLE)
    if whole and choice == "report":
        return [], (f".gitignore already ignores the whole workspace with '{whole[0]}', so REPORT.md cannot be made trackable "
                    "until that line is removed: the user's edit to make")
    new = [] if whole else [line for line in IGNORE[choice] if line not in have]
    if new:
        nl = b"\r\n" if b"\r\n" in raw else b"\n"
        with gi.open("ab") as f:
            f.write((b"" if not raw or raw.endswith(b"\n") else nl) + nl.join(line.encode() for line in new) + nl)
    return new, ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--start", action="store_true", help="create the workspace, move a finished earlier audit aside, write stack-detect.md")
    ap.add_argument("--fresh", action="store_true", help="with --start: also move an unfinished run aside and begin again")
    ap.add_argument("--ignore", choices=sorted(IGNORE), help="with --start: add these lines to .gitignore (only with the user's permission)")
    ap.add_argument("--max-files", type=int, default=60_000)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2
    if (a.ignore or a.fresh) and not a.start:
        print("--ignore and --fresh change the repository, so they only work together with --start", file=sys.stderr)
        return 2
    ws = root / WS
    state = workspace_state(ws)
    if a.start and state == "invalid":
        print(f"{ws} exists but is not a plain directory (a file or a symbolic link); nothing was written. Ask the user what it is.", file=sys.stderr)
        return 2
    r = finalise(analyse(root, a.max_files))
    if not a.start:
        print(report(root, r))
        return 0
    ws.mkdir(exist_ok=True)
    moved = state == "finished" or (state == "unfinished" and a.fresh)
    if moved:
        rotate(ws)
    (ws / "stack-detect.md").write_text(detector_text(r), encoding="utf-8")
    added, note = add_ignore(root, a.ignore) if a.ignore else ([], "")
    print(f"workspace ready: {ws}")
    print(f"stack-detect.md written ({r['project_ui_files']} project-owned UI files)")
    if moved:
        prev = ws / "previous"
        print(f"the earlier audit is in {prev}" + ("; this is a re-audit, give that path to merge_findings.py --previous in Phase 6"
              if (prev / "findings" / "_merged.json").is_file() else "; it has no merge, so there is nothing to compare against"))
    elif state == "unfinished":
        print("an unfinished run is in the workspace and was left in place; --start --fresh moves it aside to begin again")
    print(f".gitignore: added {', '.join(added)}" if added else f".gitignore: not changed{'. ' + note if note else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
