#!/usr/bin/env python3
"""Self-check for grade_findings.py.

    python3 scripts/test_grade.py

The grader turns a run into a published number, so a defect here does not break a run,
it quietly publishes a wrong one. The cases below are the ways it can lie: an item that
cannot be graded counted as a pass, an empty ground truth crashing instead of reporting,
one should-pass item counted twice because two findings flagged it, and a merged file
that is a bare list. Standard library only, writes to a temp dir.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GRADER = HERE / "grade_findings.py"


def ground_truth():
    """Find the fixture's ground truth from either repository layout.

    `evals/` sits at the repository root while this script moves with the skill, so walk up
    rather than assume a fixed number of levels between the two.
    """
    for d in [HERE, *HERE.parents]:
        p = d / "evals" / "full-audit-fixture-site" / "ground-truth.json"
        if p.exists():
            return p
    raise AssertionError("evals/full-audit-fixture-site/ground-truth.json not found above " + str(HERE))


def finding(fid, sc, file, title):
    return {
        "id": fid,
        "title": title,
        "description": "",
        "severity": "serious",
        "tier": 1,
        "evidence": [{"file": file, "lines": "1"}],
        "wcag": [{"sc": sc, "name": "x", "level": "A"}],
        "fix": {},
    }


def grade(merged, gt):
    with tempfile.TemporaryDirectory() as d:
        m, g = Path(d) / "merged.json", Path(d) / "gt.json"
        m.write_text(json.dumps(merged), encoding="utf-8")
        g.write_text(json.dumps(gt), encoding="utf-8")
        return subprocess.run([sys.executable, str(GRADER), str(m), str(g)],
                              capture_output=True, text=True)


def test_keywordless_should_pass_is_not_a_silent_pass():
    """An item with no keywords can never be flagged, so reporting it as passed is a lie."""
    r = grade(
        {"findings": [finding("SEM-001", "1.3.1", "index.html", "No main landmark on the page")]},
        {"known_failures": [{"id": "GT-01", "sc": "9.9.9", "file": "nope.html", "keywords": ["x"]}],
         "should_pass": [{"id": "SP-01", "sc": "1.3.1", "note": "main is present"}]},
    )
    assert r.returncode == 0, r.stderr
    assert "Should-pass violated: 0/0" in r.stdout, r.stdout
    assert "Ungradable" in r.stdout and "SP-01" in r.stdout, r.stdout


def test_keywordless_known_failure_is_not_a_miss():
    """Nor may an ungradable known failure be scored as a detection miss."""
    r = grade(
        {"findings": []},
        {"known_failures": [{"id": "GT-01", "sc": "1.3.1", "file": "index.html"}]},
    )
    assert r.returncode == 0, r.stderr
    assert "Detection: 0/0" in r.stdout, r.stdout
    assert "Missed: none" in r.stdout, r.stdout
    assert "GT-01" in r.stdout and "Ungradable" in r.stdout, r.stdout


def test_empty_known_failures_reports_instead_of_crashing():
    r = grade({"findings": []}, {"known_failures": []})
    assert r.returncode == 0, r.stderr
    assert "ZeroDivisionError" not in r.stderr, r.stderr
    assert "Detection: 0/0" in r.stdout, r.stdout


def test_should_pass_without_note_does_not_crash():
    r = grade(
        {"findings": [finding("SEM-001", "1.3.1", "index.html", "The main landmark is missing")]},
        {"known_failures": [], "should_pass": [{"id": "SP-01", "sc": "1.3.1", "keywords": ["main landmark"]}]},
    )
    assert r.returncode == 0, r.stderr
    assert "KeyError" not in r.stderr, r.stderr
    assert "Should-pass violated: 1/1" in r.stdout, r.stdout


def test_one_item_flagged_twice_counts_once():
    """The denominator counts items, so the numerator must too, or it can exceed it."""
    r = grade(
        {"findings": [finding("SEM-001", "1.3.1", "index.html", "No main landmark"),
                      finding("ORC-001", "1.3.1", "contact.html", "main landmark absent here too")]},
        {"known_failures": [],
         "should_pass": [{"id": "SP-01", "sc": "1.3.1", "note": "main present", "keywords": ["main landmark"]}]},
    )
    assert r.returncode == 0, r.stderr
    assert "Should-pass violated: 1/1" in r.stdout, r.stdout
    assert "SEM-001" in r.stdout and "ORC-001" in r.stdout, r.stdout


def test_a_fix_snippet_mentioning_main_is_not_a_should_pass_violation():
    """A heading repair whose fix wraps content in <main> claims nothing about the landmark."""
    f = finding("SEM-007", "1.3.1", "index.html", "Home page has no h1 and skips to h4")
    f["fix"] = {"summary": "Wrap the content and add a heading",
                "code": "<main>\n  <h1>Example B.V.</h1>\n</main>"}
    r = grade({"findings": [f]}, json.loads(ground_truth().read_text(encoding="utf-8")))
    assert r.returncode == 0, r.stderr
    assert "SP-01" not in r.stdout, r.stdout


def test_a_fix_snippet_naming_the_nav_is_not_a_should_pass_violation():
    """A hamburger-control fix names the nav it controls; that is not a claim the nav is unnamed."""
    f = finding("SEM-008", "4.1.2", "index.html", "Hamburger control has no accessible name or state")
    f["fix"] = {"summary": "Give the button aria-expanded and aria-controls",
                "code": '<button aria-expanded="false" aria-controls="menu">Hoofdmenu</button>'}
    r = grade({"findings": [f]}, json.loads(ground_truth().read_text(encoding="utf-8")))
    assert r.returncode == 0, r.stderr
    assert "SP-02" not in r.stdout, r.stdout


def test_a_real_should_pass_violation_is_still_caught():
    """Narrowing the match must not stop a genuine false claim from being flagged."""
    f = finding("SEM-009", "1.3.1", "index.html", "No main landmark on either page")
    r = grade({"findings": [f]}, json.loads(ground_truth().read_text(encoding="utf-8")))
    assert r.returncode == 0, r.stderr
    assert "SP-01" in r.stdout and "SEM-009" in r.stdout, r.stdout


def test_merged_file_may_be_a_bare_list():
    """The documented fallback for a merged file that is a list, not an object."""
    r = grade(
        [finding("SEM-001", "3.1.1", "index.html", "html element has no lang attribute")],
        {"known_failures": [{"id": "GT-01", "sc": "3.1.1", "file": "index.html", "keywords": ["lang"]}]},
    )
    assert r.returncode == 0, r.stderr
    assert "AttributeError" not in r.stderr, r.stderr
    assert "Detection: 1/1 (100%)" in r.stdout, r.stdout


def test_a_real_detection_still_matches():
    r = grade(
        {"findings": [finding("SEM-001", "3.1.1", "index.html", "html element has no lang attribute")]},
        {"known_failures": [{"id": "GT-01", "sc": "3.1.1", "file": "index.html", "keywords": ["lang"], "tier": 1}],
         "should_pass": [{"id": "SP-01", "sc": "4.1.2", "note": "nav named", "keywords": ["hoofdmenu"]}]},
    )
    assert r.returncode == 0, r.stderr
    assert "Detection: 1/1 (100%)" in r.stdout, r.stdout
    assert "Should-pass violated: 0/1" in r.stdout, r.stdout
    assert "Ungradable" not in r.stdout, r.stdout


def test_an_item_that_lists_criteria_is_found_under_any_one_of_them():
    gt = {"known_failures": [{"id": "GT-01", "sc": ["4.1.2", "2.4.4"], "file": "index.html", "keywords": ["social"]}],
          "should_pass": [{"id": "SP-01", "sc": ["1.3.1", "4.1.2"], "note": "nav named", "keywords": ["hoofdmenu"]}]}
    for sc, found in (("4.1.2", True), ("2.4.4", True), ("1.1.1", False)):
        r = grade({"findings": [finding("CNT-001", sc, "index.html", "social links have no name")]}, gt)
        assert r.returncode == 0, r.stderr
        assert f"Detection: {int(found)}/1" in r.stdout, (sc, r.stdout)
    r = grade({"findings": [finding("SEM-001", "4.1.2", "index.html", "hoofdmenu has no name")]}, gt)
    assert "Should-pass violated: 1/1" in r.stdout, r.stdout


def test_shipped_ground_truth_has_no_ungradable_items():
    """Every item in the fixture's ground truth must be gradable, or the rate is not the rate."""
    gt = json.loads(ground_truth().read_text(encoding="utf-8"))
    bad = [i["id"] for i in gt["known_failures"] + gt["should_pass"] if not i.get("keywords")]
    assert not bad, f"ground-truth items without keywords: {bad}"
    assert len(gt["known_failures"]) == 24, len(gt["known_failures"])


def main():
    failed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_"):
            continue
        try:
            fn()
            print(f"ok {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e}")
    print("all grader checks passed" if not failed else f"{failed} grader check(s) failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
