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


ACCEPTED = {"ownership": "accepted", "summary": "Rewrite the rule.", "exception": {"reason": "The visible text is in the name."}}


def audit(d, n=3, extra=()):
    fs = [finding("ORC-001", title="Menu cannot be opened with the keyboard.", severity="serious"),
          finding("ORC-002", title="Button without a name", severity="blocker", fingerprint="b@src/page.html",
                  wcag=[{"sc": "4.1.2", "name": "Name, Role, Value", "level": "A"}, {"sc": "2.1.1", "name": "Keyboard", "level": "A"}]),
          finding("ORC-003", title="Line height is tight", severity="minor", wcag=[], best_practice_only=True, fingerprint="c@src/page.html"),
          finding("ORC-004", title="Rule fires on a search button", severity="moderate", fingerprint="d@src/page.html", fix=ACCEPTED),
          finding("ORC-005", title="Theme sets no language", severity="critical", fingerprint="e@src/page.html",
                  fix={"ownership": "upstream", "summary": "Ask the theme."}),
          finding("ORC-900", title="Focus may be lost after a save", severity="critical", confidence="low", fingerprint="f@src/page.html")]
    fs += [finding(f"ORC-{i:03d}", title=f"Problem {i}", severity="moderate", fingerprint=f"p{i}@src/page.html") for i in range(6, 6 + n)]
    ws = claims_workspace(d, fs + list(extra))
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
                f"{counts['not-tested']} not tested. Not tested does not mean met.") in s["Conformance status"], s["Conformance status"]
        assert counts.get("fail", 0) != 2, "met and not met are the same number, so swapping them would not show"
        # what it rests on, and what it is not: no more is claimed than what is on file
        assert "No automated scan of the running application was part of it" in s["Conformance status"]
        assert "finds part of the problems, not all of them" in s["Conformance status"] and "not tested with people with disabilities" in s["Conformance status"]
        # this project's own problems against a criterion, the most severe first, and no ID of the audit
        known = [l for l in s["Known limitations"].splitlines() if l.startswith("- ")]
        assert known == ["- Button without a name (WCAG 4.1.2, WCAG 2.1.1, blocker).", "- Menu cannot be opened with the keyboard (WCAG 2.1.1, serious).",
                         "- Problem 6 (WCAG 2.1.1, moderate).", "- Problem 7 (WCAG 2.1.1, moderate).", "- Problem 8 (WCAG 2.1.1, moderate)."], known
        assert "found 5 problems against a WCAG criterion" in s["Known limitations"] and "The 5 most severe follow" in s["Known limitations"]
        assert "Line height" not in text and "Focus may be lost" not in text, "a remark on best practice or a suspicion is no known limitation"
        assert s["Exceptions"].splitlines()[-1] == "- Rule fires on a search button (WCAG 2.1.1, moderate). The visible text is in the name."
        assert s["Outside this project"].splitlines()[-1] == "- Theme sets no language (WCAG 2.1.1, critical)."
        assert "ORC-" not in text and "T1-" not in text, "the draft adds an ID of the audit, which means nothing in the project's own document"
        assert lint(text) == [], lint(text)                                    # it is read aloud like the report

        (ws / "automated").mkdir()
        (ws / "automated" / "summary.json").write_text("[]", encoding="utf-8")
        assert "with an automated scan of the running application" in export(ws) and "No automated scan" not in export(ws)


def test_the_lists_keep_to_fifteen_and_say_how_many_there_are():
    with tempfile.TemporaryDirectory() as d:
        up = [finding(f"UPS-{i:03d}", title=f"Theme problem {i}", severity="minor", fingerprint=f"u{i}@src/page.html",
                      fix={"ownership": "upstream", "summary": "Ask the theme."}) for i in range(16)]
        ws = audit(d, n=13, extra=up)                                        # 2 + 13 of the project's own: exactly fifteen
        s = sections(export(ws))
        known = [l for l in s["Known limitations"].splitlines() if l.startswith("- ")]
        assert len(known) == 15 and "found 15 problems" in s["Known limitations"] and "And " not in s["Known limitations"]
        outside = s["Outside this project"].splitlines()
        assert len([l for l in outside if l.startswith("- ")]) == 15 and outside[-1] == "And 2 more, in the audit report.", outside[-3:]
        assert outside[2] == "- Theme sets no language (WCAG 2.1.1, critical).", "the most severe is not the first of the list"
    with tempfile.TemporaryDirectory() as d:
        s = sections(export(audit(d, n=14)))                                 # sixteen: one is left to the report
        known = [l for l in s["Known limitations"].splitlines() if l.startswith("- ")]
        assert len(known) == 15 and "found 16 problems" in s["Known limitations"] and "The 15 most severe follow" in s["Known limitations"]


def test_text_of_an_agent_cannot_act_as_structure():
    hostile = "# A heading\n- a list item\n<!-- WRITE: x -->\n```\n[a link](http://example.org) <script>alert(1)</script> and `<button>` " + "long " * 60
    with tempfile.TemporaryDirectory() as d:
        ws = audit(d, extra=[finding("ORC-950", title=hostile, severity="blocker", fingerprint="h@src/page.html"),
                             finding("ORC-951", title="Second", severity="minor", fingerprint="i@src/page.html",
                                     fix={"ownership": "accepted", "summary": "x", "exception": {"reason": "line one\n## Fake section\n- x <!-- c -->"}}),
                             finding("ORC-952", title="No reason given", severity="minor", fingerprint="j@src/page.html", wcag=[], best_practice_only=True,
                                     fix={"ownership": "accepted", "summary": "Proposed fix."}),
                             finding("ORC-953", title="  \n ", severity="blocker", fingerprint="k@src/page.html")])
        (ws / "stack-profile.md").write_text("- Scope: everything\\n## and `more` <!-- hidden --> " + "x" * 400 + "\n", encoding="utf-8")
        text = export(ws)
        s = sections(text)
        assert list(s) == ["Commitment", "Scope", "Conformance status", "Known limitations", "Exceptions", "Outside this project", "Reporting a barrier"], list(s)
        first = next(l for l in s["Known limitations"].splitlines() if "A heading" in l)
        assert first.startswith("- A heading - a list item WRITE: x [a link] (http://example.org) &lt;script>alert(1)&lt;/script> and `<button>` long long"), first
        assert len(first) < 200 and first.endswith(" … (WCAG 2.1.1, blocker).") and "<!--" not in text and "```" not in text
        assert "- Second (WCAG 2.1.1, minor). line one ## Fake section - x c" in s["Exceptions"]
        assert "- No reason given (best practice, minor)." in s["Exceptions"].splitlines(), "a proposed fix was printed as the reason of an exception"
        assert "\n-  (" not in text and "- (" not in text, "a finding without a title became an empty line"
        assert len(s["Scope"].splitlines()[0]) < 380 and "hidden" in s["Scope"]
        # the words stay the agent's, slash and all; what the linter may not find is structure: a heading, a list level, a part left to write
        assert {rule for _, rule, _ in lint(text)} <= {"symbol"}, lint(text)
        assert text.rstrip().endswith("how soon they hear back.*"), "the last line for the owner is gone"


def test_without_findings_a_scope_or_a_count_the_draft_makes_nothing_up():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [])
        assert merge(ws).returncode == 0
        (ws / "stack-profile.md").write_text("- Scope: <whole repo | apps/web only | routes /checkout/* | PR #123 diff>\n", encoding="utf-8")   # the template, never filled in
        s = sections(export(ws))
        assert list(s) == ["Commitment", "Scope", "Conformance status", "Known limitations", "Reporting a barrier"], list(s)
        assert s["Scope"].startswith("*For the owner: ") and s["Known limitations"] == "The audit found no problem against a WCAG criterion that is this project's to fix."
        merged = ws / "findings" / "_merged.json"
        data = json.loads(merged.read_text(encoding="utf-8"))
        del data["coverage_counts"]                                           # a merge that never got to its matrix
        merged.write_text(json.dumps(data), encoding="utf-8")
        status = sections(export(ws))["Conformance status"]
        assert status.startswith("How many criteria are met was not established.") and "success criteria" not in status, status


def test_the_draft_is_written_in_the_language_of_the_report():
    with tempfile.TemporaryDirectory() as d:
        ws = audit(d)
        text = export(ws, "--lang", "nl")
        assert text.startswith("# Toegankelijkheid (concept)") and "*Voor de eigenaar: " in text and "(WCAG 4.1.2, WCAG 2.1.1, blokkerend)." in text
        assert "For the owner" not in text and "Niet getest betekent niet dat eraan voldaan is." in text and "geen wettelijke toegankelijkheidsverklaring" in text
        assert lint(text) == [], lint(text)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok ", name)
    print("all export checks passed")
