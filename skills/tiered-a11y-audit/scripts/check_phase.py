#!/usr/bin/env python3
"""Check that a phase left behind everything the next one builds on, before moving on.

    python3 check_phase.py <repo>/.a11y-audit <phase>        # phase: 3, 4, 5 or 6

Prints one line per gap and exits 1 while there is any, 0 when the phase is complete, 2 when it cannot run.
Run it at the end of the phase with that number:

  3  the baseline files and the stack profile are written, the briefs were built after the profile,
     and a runtime scan (if there was one) left its summary and, where it captured trees, a digest
  4  every expert named in briefs/_agents.json wrote a readable findings file with a status for each
     criterion it owns (not-tested and n/a with a reason), and the merge is newer than every findings file
     and has no problem left to resolve
  5  the personas for this mode and the framework-maximizer reported, and the merge was run after them and
     again has no problem left
  6  the merge is still newer than its inputs and without problems, the draft was rendered after it, a re-audit whose earlier
     audit has a merge was merged with --previous, and REPORT.md was assembled after the last change to the
     prose file and passes lint_report.py

It cannot tell this run's files from files an earlier run left in the workspace: moving an earlier audit
aside before the run starts is what keeps the answers honest.

A gate only looks at files: whether a finding is true is still for the orchestrator to verify. What the merge
could not verify or had to guess is its list of problems, and a phase is not complete while that list has
an entry; what the merge settled itself is in its notes and does not count.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lint_report import lint  # noqa: E402
from merge_findings import parse_ownership  # noqa: E402

OWNERSHIP = HERE.parent / "references" / "wcag-ownership.md"
STATUSES = ("pass", "fail", "not-tested", "n/a")
CORE = ["screen-reader-user", "low-vision-user", "motor-voice-user", "cognitive-user"]


def filled(p: Path) -> bool:
    return p.is_file() and bool(p.read_text(encoding="utf-8", errors="replace").strip())


def load(p: Path, gaps: list):
    """Parsed JSON object, or None with the reason added to gaps."""
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except OSError:
        gaps.append(f"{p.parent.name}/{p.name} is missing")
        return None
    except ValueError as e:
        gaps.append(f"{p.parent.name}/{p.name} is not valid JSON ({e}): the merge skips such a file without its findings")
        return None
    if not isinstance(data, dict):
        gaps.append(f"{p.parent.name}/{p.name} holds a {type(data).__name__}, not an object")
        return None
    return data


def older(p: Path, than: Path) -> bool:
    # ponytail: file times, so a file copied or touched by hand can fool it; good enough within one run
    return p.stat().st_mtime_ns < than.stat().st_mtime_ns


def manifest(ws: Path, gaps: list):
    why: list = []
    m = load(ws / "briefs" / "_agents.json", why)
    if m is None:
        gaps.append(f"{why[0]}: run build_briefs.py, which writes this list of the agents the audit runs")
    return m


def merged_is_current(ws: Path, gaps: list):
    """The parsed merge, or None; a gap when it is missing, older than something it should contain, or still lists problems."""
    mp = ws / "findings" / "_merged.json"
    merged = load(mp, gaps)
    if merged is None:
        return None
    inputs = [p for p in (ws / "findings").glob("*.json") if p.name == "_dedupe.json" or not p.name.startswith("_")]
    stale = sorted(p.name for p in inputs + list((ws / "personas").glob("*.md")) if older(mp, p))
    if stale:
        gaps.append(f"findings/_merged.json is older than {', '.join(stale)}: run merge_findings.py again")
    problems = merged.get("problems") or []
    if problems:
        # what the merge settled itself is under "notes"; this list is only what needs a decision
        gaps.append(f"the merge lists {len(problems)} problems to resolve (findings/_merged.md, at the end), the first: "
                    f"{' '.join(str(problems[0]).split())[:120]}. Correct the findings file or drop the finding, then merge again")
    return merged


def phase3(ws: Path, gaps: list) -> None:
    for name in ("stack-detect.md", "stack-profile.md", "pattern-inventory.md", "colour-pairs.md"):
        if not filled(ws / name):
            gaps.append(f"{name} is missing or empty")
    profile = ws / "stack-profile.md"
    if filled(profile):
        blank = [line.strip()[:60] for line in profile.read_text(encoding="utf-8", errors="replace").splitlines()
                 if re.search(r": …(\s{2,}|$)|<…>", line)]
        if blank:
            gaps.append(f"stack-profile.md has {len(blank)} lines still holding the template's …, the first: {blank[0]}")
    m = manifest(ws, gaps)
    if m:
        names = list(m.get("experts") or {}) + [m.get("maximizer")] + list(m.get("personas") or [])
        missing = [n for n in names if not filled(ws / "briefs" / f"{n}.md")]
        if missing:
            gaps.append(f"briefs missing for {', '.join(map(str, missing))}: run build_briefs.py again")
        if profile.is_file() and older(ws / "briefs" / "_agents.json", profile):
            gaps.append("stack-profile.md changed after the briefs were built: run build_briefs.py again, the briefs carry a copy of it")
    digest, auto = ws / "aria-digest.md", ws / "automated"
    if auto.is_dir() and not (auto / "summary.json").is_file():
        gaps.append("automated/ has no summary.json: the runtime scan did not finish. Run it again, or delete automated/ "
                    "and go on static-only (say so in the method section)")
    trees = auto.is_dir() and any(auto.glob("*.aria.yml"))
    if trees and not filled(digest):
        gaps.append("aria-digest.md is missing or empty although the scan left accessibility trees: run aria_digest.py")
    elif not trees and digest.exists() and not filled(digest):
        gaps.append("aria-digest.md is empty (there are no accessibility trees to digest): delete it and build the briefs again, "
                    "or they point every agent at an empty file")


def phase4(ws: Path, gaps: list) -> None:
    m = manifest(ws, gaps)
    owners = parse_ownership(OWNERSHIP)
    for name, lenses in ((m or {}).get("experts") or {}).items():
        data = load(ws / "findings" / f"{name}.json", gaps)
        if data is None:
            continue
        if not isinstance(data.get("findings"), list):
            gaps.append(f"findings/{name}.json has no \"findings\" list (write [] when the lens found nothing)")
        cov = data.get("sc_coverage") if isinstance(data.get("sc_coverage"), dict) else {}
        owned = [sc for sc, meta in owners.items() if meta["owner"] in lenses]
        open_ = [sc for sc in owned if not isinstance(cov.get(sc), dict) or cov[sc].get("status") not in STATUSES]
        if open_:
            gaps.append(f"findings/{name}.json gives no status for {len(open_)} of its {len(owned)} criteria ({', '.join(open_)}): "
                        f"each needs one of {', '.join(STATUSES)}")
        bare = [sc for sc in owned if sc not in open_ and cov[sc]["status"] in ("not-tested", "n/a") and not str(cov[sc].get("note") or cov[sc].get("reason") or "").strip()]   # agents also write "reason"
        if bare:
            gaps.append(f"findings/{name}.json marks {', '.join(bare)} not-tested or n/a without a reason in the note")
    merged_is_current(ws, gaps)


def phase5(ws: Path, gaps: list) -> None:
    m = manifest(ws, gaps) or {}
    done = [p.stem for p in (ws / "personas").glob("*.md") if filled(p)]
    need = ["screen-reader-user"] if m.get("mode") == "mini" else CORE
    missing = [p for p in need if p not in done]
    if missing:
        gaps.append(f"no persona report from {', '.join(missing)} in personas/")
    if m.get("mode") == "mini" and len(done) < 2:
        gaps.append(f"mini mode runs the screen reader persona plus one other: {len(done)} reported")
    load(ws / "findings" / f"{m.get('maximizer') or 'framework-maximizer'}.json", gaps)
    merged_is_current(ws, gaps)
    if not filled(ws / "coverage.md"):
        gaps.append("coverage.md is missing or empty")


def phase6(ws: Path, gaps: list) -> None:
    mp, draft, report, prev = ws / "findings" / "_merged.json", ws / "REPORT.draft.md", ws / "REPORT.md", ws / "previous"
    merged = merged_is_current(ws, gaps)
    if not draft.is_file():
        gaps.append("REPORT.draft.md is missing: run render_report_parts.py")
    elif mp.is_file() and older(draft, mp):
        gaps.append("REPORT.draft.md is older than findings/_merged.json: render again, the report would miss the last merge")
    # only an earlier audit that got as far as a merge can be compared against
    if merged and ((prev / "findings" / "_merged.json").is_file() or (prev / "_merged.json").is_file()):
        if not merged.get("delta") or not filled(ws / "delta.md"):
            gaps.append("this is a re-audit (previous/ holds a merge) but the last merge ran without --previous: "
                        "merge again with it, so the delta is written")
    ids = load(ws / "report-ids.json", gaps)
    prose_file = ws / "report-prose.md"
    if not report.is_file():
        gaps.append("REPORT.md is missing: write your text in report-prose.md and run render_report_parts.py again")
    elif (prose_file.is_file() and older(report, prose_file)) or (draft.is_file() and older(report, draft)):
        gaps.append("REPORT.md is older than report-prose.md or the draft: run render_report_parts.py again, it assembles the report from both")
    elif ids is not None:
        n = len(lint(report.read_text(encoding="utf-8", errors="replace"), ids))
        if n:
            gaps.append(f"REPORT.md has {n} problems: run lint_report.py on it with --workspace for the list")


PHASES = {"3": phase3, "4": phase4, "5": phase5, "6": phase6}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="path to .a11y-audit")
    ap.add_argument("phase", choices=sorted(PHASES), help="the phase that should now be complete")
    a = ap.parse_args()
    ws = Path(a.workspace)
    if not ws.is_dir():
        print(f"check_phase: {ws} is not a directory", file=sys.stderr)
        return 2
    gaps: list = []
    PHASES[a.phase](ws, gaps)
    for g in gaps:
        print(f"phase {a.phase}: {g}")
    print(f"phase {a.phase} is not complete: {len(gaps)} to resolve" if gaps else f"phase {a.phase} complete")
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
