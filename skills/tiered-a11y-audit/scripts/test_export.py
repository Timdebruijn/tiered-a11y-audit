#!/usr/bin/env python3
"""Self-check for the draft of an ACCESSIBILITY.md that export_findings.py writes.

    python3 scripts/test_export.py

The draft may say only what the audit established, and must leave to the owner what only the owner can say.
Standard library only, writes to a temp dir.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lint_report import lint  # noqa: E402
from test_merge import claims_workspace, finding, merge  # noqa: E402


def export(ws, *args):
    r = subprocess.run([sys.executable, str(HERE / "export_findings.py"), str(ws), "--format", "accessibility-md", *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return (ws / "ACCESSIBILITY.draft.md").read_text(encoding="utf-8")


def sections(text):
    parts = re.split(r"(?m)^## (.+)$", text)
    return dict(zip(parts[1::2], (p.strip() for p in parts[2::2])))


def audit(d, n=3):
    fs = [finding("ORC-001", title="Menu cannot be opened with the keyboard.", severity="serious"),
          finding("ORC-002", title="Button without a name", severity="blocker", fingerprint="b@src/page.html",
                  wcag=[{"sc": "4.1.2", "name": "Name, Role, Value", "level": "A"}, {"sc": "2.1.1", "name": "Keyboard", "level": "A"}]),
          finding("ORC-003", title="Line height is tight", severity="minor", wcag=[], best_practice_only=True, fingerprint="c@src/page.html"),
          finding("ORC-004", title="Rule fires on a search button", severity="moderate", fingerprint="d@src/page.html",
                  fix={"ownership": "accepted", "summary": "Left.", "exception": {"reason": "The visible text is in the name."}}),
          finding("ORC-005", title="Theme sets no language", severity="critical", fingerprint="e@src/page.html",
                  fix={"ownership": "upstream", "summary": "Ask the theme."})]
    fs += [finding(f"ORC-{i:03d}", title=f"Problem {i}", severity="moderate", fingerprint=f"p{i}@src/page.html") for i in range(6, 6 + n)]
    ws = claims_workspace(d, fs)
    # a lens with a verdict on three of its criteria, so that met, not met and not applicable are different numbers
    (ws / "findings" / "keyboard-focus.json").write_text(json.dumps({"agent": "keyboard-focus", "lenses": ["keyboard-focus"], "findings": [], "sc_coverage": {
        "2.1.2": {"status": "pass", "note": "No trap."}, "2.4.3": {"status": "pass", "note": "In order."}, "2.1.4": {"status": "n/a", "note": "No shortcuts."}}}), encoding="utf-8")
    assert merge(ws).returncode == 0
    return ws


def test_the_draft_says_what_the_audit_found_and_leaves_the_rest_to_the_owner():
    with tempfile.TemporaryDirectory() as d:
        ws = audit(d)
        (ws / "stack-profile.md").write_text("# Stack profile\n\n- Mode: lean\n- Scope: the two pages of the site\n- Runtime: none\n", encoding="utf-8")
        text = export(ws)
        s = sections(text)
        assert list(s) == ["Commitment", "Scope", "Conformance status", "Known limitations", "Exceptions", "Outside this project", "Reporting a barrier"], list(s)
        assert text.startswith("# Accessibility (draft)\n\nA draft, written on ") and re.search(r"written on \d{4}-\d\d-\d\d from", text)
        assert "not a commitment and not a legal accessibility statement" in text
        # what only the owner can say is a line that says so, and nothing made up stands in for it
        assert s["Commitment"].startswith("*For the owner: ") and s["Reporting a barrier"].startswith("*For the owner: ") and text.count("*For the owner: ") == 3
        assert s["Scope"].startswith("The audit covered, in the words of its own notes: the two pages of the site\n\n*For the owner: ")
        counts = json.loads((ws / "findings" / "_merged.json").read_text(encoding="utf-8"))["coverage_counts"]
        assert counts.get("pass") == 2 and counts.get("n/a") == 1 and sum(counts.values()) == 55, counts
        assert (f"the 55 success criteria of WCAG 2.2 at level A and AA: 2 met, {counts.get('fail', 0)} not met, 1 not applicable, "
                f"{counts['not-tested']} not tested.") in s["Conformance status"], s["Conformance status"]
        assert counts.get("fail", 0) != 2, "met and not met are the same number, so swapping them would not show"
        assert "Nobody tried the running application" in s["Conformance status"], "a static audit must not read as one that tried the application"
        # this project's own problems, the most severe first, with the criterion or the word for none, and no ID of the audit
        known = [l for l in s["Known limitations"].splitlines() if l.startswith("- ")]
        assert known[:3] == ["- Button without a name (WCAG 4.1.2, WCAG 2.1.1, blocker).", "- Menu cannot be opened with the keyboard (WCAG 2.1.1, serious).",
                             "- Problem 6 (WCAG 2.1.1, moderate)."], known[:3]
        assert known[-1] == "- Line height is tight (best practice, minor)." and len(known) == 6
        assert "The audit found 6 problems that are this project's to fix. The 6 most severe follow" in s["Known limitations"]
        assert s["Exceptions"].splitlines()[-1] == "- Rule fires on a search button (WCAG 2.1.1, moderate). The visible text is in the name."
        assert s["Outside this project"].splitlines()[-1] == "- Theme sets no language (WCAG 2.1.1, critical)."
        assert "ORC-" not in text and "T1-" not in text, "an ID of the audit means nothing in the project's own document"
        assert lint(text) == [], lint(text)                                    # it is read aloud like the report

        (ws / "automated").mkdir()
        (ws / "automated" / "summary.json").write_text("[]", encoding="utf-8")
        assert "and tried the running application" in export(ws) and "Nobody tried" not in export(ws)


def test_the_draft_keeps_to_fifteen_problems_and_says_how_many_there_are():
    with tempfile.TemporaryDirectory() as d:
        ws = audit(d, n=20)
        s = sections(export(ws))
        known = [l for l in s["Known limitations"].splitlines() if l.startswith("- ")]
        assert len(known) == 15 and "found 23 problems" in s["Known limitations"] and "The 15 most severe follow" in s["Known limitations"]
        assert "Line height" not in s["Known limitations"], "the least severe is listed while more severe ones are cut"


def test_without_findings_or_a_scope_the_draft_makes_nothing_up():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [])
        assert merge(ws).returncode == 0
        (ws / "stack-profile.md").write_text("- Scope: <whole repo | apps/web only | routes /checkout/* | PR #123 diff>\n", encoding="utf-8")   # the template, never filled in
        s = sections(export(ws))
        assert list(s) == ["Commitment", "Scope", "Conformance status", "Known limitations", "Reporting a barrier"], list(s)
        assert s["Scope"].startswith("*For the owner: ") and s["Known limitations"] == "The audit found no problem that is this project's to fix."


def test_the_draft_is_written_in_the_language_of_the_report():
    with tempfile.TemporaryDirectory() as d:
        ws = audit(d)
        text = export(ws, "--lang", "nl")
        assert text.startswith("# Toegankelijkheid (concept)") and "*Voor de eigenaar: " in text and "(WCAG 4.1.2, WCAG 2.1.1, blokkerend)." in text
        assert "For the owner" not in text and "best practice, klein" in text


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok ", name)
    print("all export checks passed")
