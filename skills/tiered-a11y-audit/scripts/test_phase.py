#!/usr/bin/env python3
"""Self-check for check_phase.py: each gate stays shut until its phase really left its output.

    python3 scripts/test_phase.py

Walks one mini audit through phases 3 to 6 with the real scripts (build_briefs, merge_findings,
render_report_parts) and at each step breaks one thing the gate has to notice. Standard library only,
writes to a temp dir.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_phase import PHASES  # noqa: E402
from test_render import finding  # noqa: E402


def script(name, *args):
    r = subprocess.run([sys.executable, str(HERE / name), *map(str, args)], capture_output=True, text=True)
    assert r.returncode == 0, f"{name}: {r.stdout}{r.stderr}"
    return r


def gaps(ws, phase):
    out = []
    PHASES[phase](ws, out)
    return out


def one(ws, phase, word):
    got = gaps(ws, phase)
    assert len(got) == 1 and word in got[0], f"phase {phase}: expected one gap with '{word}', got {got}"


def touch_after(p, other):
    t = other.stat().st_mtime + 5
    os.utime(p, (t, t))


def merge(ws):
    script("merge_findings.py", ws, "--ownership", HERE.parent / "references" / "wcag-ownership.md")


def workspace():
    repo = Path(tempfile.mkdtemp())
    ws = repo / ".a11y-audit"
    ws.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "page.html").write_text("<main>\n<div onclick>\n</div>\n", encoding="utf-8")
    return ws


def through_phase_3(ws):
    for name in ("stack-detect.md", "stack-profile.md", "pattern-inventory.md", "colour-pairs.md"):
        (ws / name).write_text(f"# {name}\n\n- Mode: mini\n", encoding="utf-8")
    script("build_briefs.py", HERE.parent, ws, "--mini")


def skeleton(ws, agent):
    brief = (ws / "briefs" / f"{agent}.md").read_text(encoding="utf-8")
    return json.loads(re.findall(r"```json\n(.*?)\n```", brief, re.S)[-1])


def through_phase_4(ws):
    (ws / "findings").mkdir(exist_ok=True)
    for agent in ("perceive", "operate"):
        data = skeleton(ws, agent)
        for sc in data["sc_coverage"]:
            data["sc_coverage"][sc] = {"status": "not-tested", "note": "static pass only"}
        if agent == "operate":
            data["findings"] = [finding("KBD-001")]
            data["sc_coverage"]["2.1.1"] = {"status": "fail", "findings": ["KBD-001"]}
        (ws / "findings" / f"{agent}.json").write_text(json.dumps(data), encoding="utf-8")
    merge(ws)


def through_phase_5(ws):
    (ws / "personas").mkdir(exist_ok=True)
    for p in ("screen-reader-user", "low-vision-user"):
        (ws / "personas" / f"{p}.md").write_text(f"# {p}\n\nWalked the key flows.\n", encoding="utf-8")
    (ws / "findings" / "framework-maximizer.json").write_text(json.dumps({"agent": "framework-maximizer", "findings": []}), encoding="utf-8")
    merge(ws)


def test_phase_3_wants_the_baseline_the_profile_and_fresh_briefs():
    ws = workspace()
    assert len(gaps(ws, "3")) == 5, gaps(ws, "3")                    # four files and the list of agents
    through_phase_3(ws)
    assert gaps(ws, "3") == [], gaps(ws, "3")
    (ws / "aria-digest.md").write_text("", encoding="utf-8")
    one(ws, "3", "aria-digest.md is empty")
    (ws / "automated").mkdir()                                                 # a scan that died early: no summary, no trees
    assert [g.split(":")[0] for g in gaps(ws, "3")] == ["automated/ has no summary.json", "aria-digest.md is empty (there are no accessibility trees to digest)"]
    (ws / "automated" / "summary.json").write_text("{}", encoding="utf-8")
    (ws / "aria-digest.md").unlink()
    assert gaps(ws, "3") == [], "a scan without trees needs no digest"
    (ws / "automated" / "home.aria.yml").write_text("- main\n", encoding="utf-8")
    one(ws, "3", "although the scan left accessibility trees")
    (ws / "aria-digest.md").write_text("# digest\n", encoding="utf-8")
    assert gaps(ws, "3") == []
    (ws / "briefs" / "operate.md").unlink()
    (ws / "briefs" / "deaf-user.md").unlink()
    (ws / "briefs" / "framework-maximizer.md").unlink()
    one(ws, "3", "briefs missing for operate, framework-maximizer, deaf-user")
    through_phase_3(ws)
    profile = ws / "stack-profile.md"
    profile.write_text(profile.read_text(encoding="utf-8") + "- Router: …        - Styling: Tailwind\n- Scope: <…>\n", encoding="utf-8")
    touch_after(profile, ws / "briefs" / "_agents.json")
    assert {g[:24] for g in gaps(ws, "3")} == {"stack-profile.md changed", "stack-profile.md has 2 l"}, gaps(ws, "3")


def test_phase_4_wants_every_expert_every_criterion_and_a_current_merge():
    ws = workspace()
    through_phase_3(ws)
    assert [g.split(" is ")[0] for g in gaps(ws, "4")] == ["findings/perceive.json", "findings/operate.json", "findings/_merged.json"]
    through_phase_4(ws)
    assert gaps(ws, "4") == [], gaps(ws, "4")
    f = ws / "findings" / "operate.json"
    good = f.read_text(encoding="utf-8")

    f.write_text(json.dumps(skeleton(ws, "operate")), encoding="utf-8")       # the untouched skeleton is not a report
    merge(ws)
    got = gaps(ws, "4")
    assert len(got) == 1 and "gives no status for 23 of its 23 criteria" in got[0], got

    data = json.loads(good)
    del data["sc_coverage"]["2.1.2"]
    f.write_text(json.dumps(data), encoding="utf-8")
    merge(ws)
    one(ws, "4", "no status for 1 of its 23 criteria (2.1.2)")

    data = json.loads(good)
    data["sc_coverage"]["2.1.2"] = {"status": "n/a", "note": " "}
    data["sc_coverage"]["2.1.4"] = {"status": "not-tested", "reason": "needs a runtime"}      # agents also write "reason"
    f.write_text(json.dumps(data), encoding="utf-8")
    merge(ws)
    one(ws, "4", "marks 2.1.2 not-tested or n/a without a reason")

    data = json.loads(good)
    data["findings"][0]["evidence"] = [{"file": "src/gone.html", "lines": "1", "snippet": "<div onclick>"}]      # a citation that does not exist
    f.write_text(json.dumps(data), encoding="utf-8")
    merge(ws)
    one(ws, "4", "the merge lists 1 problem to resolve")
    assert "--repo <dir>" in gaps(ws, "4")[0], "a cited file that is not found can also mean the merge lacked --repo"
    data["findings"][0]["proposed_tier"] = 3                                   # and a tier that contradicts the visual impact
    f.write_text(json.dumps(data), encoding="utf-8")
    merge(ws)
    one(ws, "4", "the merge lists 2 problems to resolve")
    data["findings"][0]["fix"] = "Use a button."                               # a fix as plain text: converting it is a note and does not count,
    f.write_text(json.dumps(data), encoding="utf-8")
    merge(ws)
    assert "the merge lists 3 problems to resolve" in gaps(ws, "4")[0], gaps(ws, "4")
    assert "--repo" in gaps(ws, "4")[0] and gaps(ws, "4")[0].count("not found in the repository") == 1, "only the first problem is quoted"      # but the ownership the merge then has to assume does
    f.write_text(good, encoding="utf-8")
    merge(ws)
    assert gaps(ws, "4") == [], "the phase stays shut after the problems were resolved"

    f.write_text(good, encoding="utf-8")                                       # edited after the merge
    one(ws, "4", "older than operate.json")
    merge(ws)
    (ws / "findings" / "_dedupe.json").write_text("{}", encoding="utf-8")      # a merge decision the merge has not seen
    one(ws, "4", "older than _dedupe.json")
    merge(ws)
    f.write_text(good[:-20], encoding="utf-8")                                 # cut off mid-file
    merge(ws)
    one(ws, "4", "findings/operate.json is not valid JSON")

    data = json.loads(good)
    data["findings"] = {"KBD-001": data["findings"][0]}                        # an object: the merge would read it as no findings
    f.write_text(json.dumps(data), encoding="utf-8")
    merge(ws)
    assert any('has no "findings" list' in g for g in gaps(ws, "4")), gaps(ws, "4")


def test_phase_5_wants_the_personas_of_the_mode_and_a_merge_after_them():
    ws = workspace()
    through_phase_3(ws)
    through_phase_4(ws)
    got = gaps(ws, "5")
    assert len(got) == 3 and "screen-reader-user" in got[0] and "0 reported" in got[1] and "framework-maximizer.json is missing" in got[2], got
    through_phase_5(ws)
    assert gaps(ws, "5") == [], gaps(ws, "5")
    (ws / "personas" / "low-vision-user.md").write_text("", encoding="utf-8")
    assert any("plus one other" in g for g in gaps(ws, "5")), "an empty persona file counts as a report"
    through_phase_5(ws)
    touch_after(ws / "personas" / "low-vision-user.md", ws / "findings" / "_merged.json")
    one(ws, "5", "older than low-vision-user.md")
    through_phase_5(ws)                                                        # writes the files anew, then merges
    new = {"id": "PER-low-vision-001", "title": "The price is too faint", "severity": "serious", "location": "the pricing page", "fix": "Darker."}
    lv = ws / "personas" / "low-vision-user.md"
    lv.write_text("# low-vision-user\n\n## New findings\n```json\n" + json.dumps([new]) + "\n```\n\n## end\n", encoding="utf-8")
    merge(ws)
    one(ws, "5", "PER-low-vision-001: no visual_impact and no tier")           # the one thing the merge cannot settle for a persona
    assert "--repo" not in gaps(ws, "5")[0], "a persona's place is not a file that was not found"
    lv.write_text(lv.read_text(encoding="utf-8").replace('"severity"', '"tier": "T2", "severity"'), encoding="utf-8")
    merge(ws)
    one(ws, "5", "PER-low-vision-001: tier 2 without tier_rationale")          # the report would have no design impact to show
    lv.write_text(lv.read_text(encoding="utf-8").replace('"severity"', '"tier_rationale": "A darker grey.", "severity"'), encoding="utf-8")
    merge(ws)
    assert gaps(ws, "5") == [], gaps(ws, "5")                                  # no criterion, no file: settled, the phase is open
    lv.write_text(lv.read_text(encoding="utf-8").replace("## New findings", "## Flow results\n| Flow | Result | Feel | Main obstacle | Findings |\n|---|---|---|---|---|\n| Pricing | failed | long | the price | |\n\n## New findings"), encoding="utf-8")
    merge(ws)
    one(ws, "5", "flow 'Pricing' is 'failed' but its row names no finding")    # the floor has nothing to act on
    lv.write_text(lv.read_text(encoding="utf-8").replace("| the price | |", "| the price | PER-low-vision-001 |"), encoding="utf-8")
    merge(ws)
    assert gaps(ws, "5") == [], gaps(ws, "5")
    m = ws / "briefs" / "_agents.json"
    m.write_text(m.read_text(encoding="utf-8").replace('"mini"', '"lean"'), encoding="utf-8")
    one(ws, "5", "no persona report from motor-voice-user, cognitive-user")


def test_phase_6_wants_a_current_draft_and_a_report_that_passes_the_linter():
    ws = workspace()
    through_phase_3(ws)
    through_phase_4(ws)
    through_phase_5(ws)
    assert len(gaps(ws, "6")) == 3, gaps(ws, "6")                    # no draft, no ids, no report
    script("render_report_parts.py", ws, "--lang", "en")
    one(ws, "6", "REPORT.md is missing")
    draft = (ws / "REPORT.draft.md").read_text(encoding="utf-8")
    (ws / "REPORT.md").write_text(draft, encoding="utf-8")
    one(ws, "6", "REPORT.md has")
    (ws / "REPORT.md").write_text(re.sub(r"<!-- WRITE:.*?-->", "Written.", draft.split("-->", 1)[1].lstrip(), flags=re.S), encoding="utf-8")
    assert gaps(ws, "6") == [], gaps(ws, "6")
    report, prose_file, drafted = ws / "REPORT.md", ws / "report-prose.md", ws / "REPORT.draft.md"
    stamps = {f: f.stat().st_mtime for f in (report, prose_file, drafted)}

    def restore():
        for f, t in stamps.items():
            os.utime(f, (t, t))
    touch_after(prose_file, report)                                            # prose changed after the report was assembled
    one(ws, "6", "REPORT.md is older than report-prose.md or the draft")
    restore()
    touch_after(drafted, report)                                               # rendered again, report not assembled since
    one(ws, "6", "REPORT.md is older than report-prose.md or the draft")
    restore()
    kept = prose_file.read_text(encoding="utf-8")
    prose_file.unlink()                                                        # an audit from before the prose file existed
    assert gaps(ws, "6") == [], gaps(ws, "6")
    prose_file.write_text(kept, encoding="utf-8")
    restore()
    assert gaps(ws, "6") == [], gaps(ws, "6")
    own = ws / "findings" / "orchestrator.json"                               # found while verifying, not merged yet
    own.write_text(json.dumps({"agent": "orchestrator", "findings": []}), encoding="utf-8")
    one(ws, "6", "older than orchestrator.json")
    own.unlink()
    (ws / "previous" / "findings").mkdir(parents=True)                         # an earlier run that never reached a merge
    assert gaps(ws, "6") == [], "nothing to compare against, so no delta can be demanded"
    (ws / "previous" / "findings" / "_merged.json").write_text((ws / "findings" / "_merged.json").read_text(encoding="utf-8"), encoding="utf-8")
    one(ws, "6", "the last merge ran without --previous")
    script("merge_findings.py", ws, "--ownership", HERE.parent / "references" / "wcag-ownership.md", "--previous", ws / "previous")
    assert (ws / "delta.md").is_file()
    dm = ws / "findings" / "_delta-map.json"                                   # an answer on the delta that the merge has not read yet
    dm.write_text("{}", encoding="utf-8")
    touch_after(dm, ws / "findings" / "_merged.json")
    assert any("older than _delta-map.json" in g for g in gaps(ws, "6")), gaps(ws, "6")
    dm.unlink()
    one(ws, "6", "REPORT.draft.md is older")                                   # the delta is there; the draft predates that merge


def test_lean_mode_holds_a_file_to_the_criteria_of_both_its_lenses():
    ws = workspace()
    for name in ("stack-detect.md", "stack-profile.md", "pattern-inventory.md", "colour-pairs.md"):
        (ws / name).write_text("- Mode: lean\n", encoding="utf-8")
    script("build_briefs.py", HERE.parent, ws, "--lean")
    (ws / "findings").mkdir()
    for agent in ("structure-content", "keyboard-dynamic", "visual-perception", "forms-input"):
        data = skeleton(ws, agent)
        for sc in data["sc_coverage"]:
            data["sc_coverage"][sc] = {"status": "pass", "note": ""}
        (ws / "findings" / f"{agent}.json").write_text(json.dumps(data), encoding="utf-8")
    merge(ws)
    assert gaps(ws, "4") == [], gaps(ws, "4")
    f = ws / "findings" / "keyboard-dynamic.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    del data["sc_coverage"]["4.1.3"]                                           # owned by dynamic-content, the second lens
    f.write_text(json.dumps(data), encoding="utf-8")
    merge(ws)
    one(ws, "4", "no status for 1 of its 11 criteria (4.1.3)")


def test_the_skeletons_of_every_mode_cover_all_55_criteria_once():
    for flag, n in (("--mini", 2), ("--lean", 4), (None, 6)):
        ws = workspace()
        script("build_briefs.py", HERE.parent, ws, *([flag] if flag else []))
        m = json.loads((ws / "briefs" / "_agents.json").read_text(encoding="utf-8"))
        owned = [sc for agent in m["experts"] for sc in skeleton(ws, agent)["sc_coverage"]]
        assert len(m["experts"]) == n and len(owned) == len(set(owned)) == 55, (flag, len(owned))


def test_exit_codes():
    ws = workspace()
    cli = [sys.executable, str(HERE / "check_phase.py")]
    r = subprocess.run([*cli, str(ws), "3"], capture_output=True, text=True)
    assert r.returncode == 1 and "phase 3 is not complete: 5 to resolve" in r.stdout, r.stdout
    through_phase_3(ws)
    r = subprocess.run([*cli, str(ws), "3"], capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "phase 3 complete", r.stdout
    assert subprocess.run([*cli, str(ws / "nowhere"), "3"], capture_output=True, text=True).returncode == 2


if __name__ == "__main__":
    start = time.time()
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} checks passed in {time.time() - start:.1f}s")
