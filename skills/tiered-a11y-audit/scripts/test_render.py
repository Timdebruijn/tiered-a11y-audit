#!/usr/bin/env python3
"""Self-check for render_report_parts.py: the draft report must carry every finding, unchanged.

    python3 scripts/test_render.py

The orchestrator used to retype each finding block from _merged.json by hand, which is where findings
were dropped or altered. The draft takes that step away, so what has to hold is: one block per finding,
fields in the fixed order of the report template, values untouched, and a structure that meets the
skill's own read-aloud rules. Standard library only, writes to a temp dir.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OWNERSHIP = HERE.parent / "references" / "wcag-ownership.md"


def finding(fid, **over):
    f = {"id": fid, "fingerprint": f"{fid.lower()}@src/page.html", "title": f"Title of {fid}", "description": f"Problem text of {fid}.",
         "severity": "serious", "evidence": [{"file": "src/page.html", "lines": "2-3", "snippet": "<div onclick>"}],
         "wcag": [{"sc": "2.1.1"}], "affected_users": ["screen-reader"], "visual_impact": "none", "proposed_tier": 1,
         "fix": {"ownership": "project", "summary": f"Fix text of {fid}.", "location": "src/page.html",
                 "code_before": f"<before-{fid}>", "code_after": f"<after-{fid}>", "side_effects": "Check the styles."},
         "effort": "S", "confidence": "high", "verify": f"Verify text of {fid}."}
    f.update(over)
    return f


FINDINGS = [
    finding("KBD-001", severity="blocker"),
    finding("KBD-002", title="A title | with a pipe in it"),
    finding("KBD-003", severity="minor"),
    finding("KBD-004", confidence="low"),
    finding("VIS-001", visual_impact="subtle", proposed_tier=2, tier_rationale="Lightness only.", wcag=[{"sc": "1.4.3"}],
            colours={"fg": "#9a9a9a", "bg": "#ffffff", "ratio": 2.81, "required": 4.5, "suggested_fg": "#767676", "delta_e_ok": 0.06}),
    finding("CNT-001", visual_impact="significant", proposed_tier=3),
]


def run(findings, lang="en"):
    d = tempfile.mkdtemp()
    ws = Path(d) / ".a11y-audit"
    (ws / "findings").mkdir(parents=True)
    (Path(d) / "src").mkdir()
    (Path(d) / "src" / "page.html").write_text("<main>\n<div onclick>\n</div>\n", encoding="utf-8")
    (ws / "findings" / "experts.json").write_text(json.dumps({"agent": "experts", "positives": ["One main landmark."],
                                                             "findings": findings}), encoding="utf-8")
    m = subprocess.run([sys.executable, str(HERE / "merge_findings.py"), str(ws), "--ownership", str(OWNERSHIP)],
                       capture_output=True, text=True)
    assert m.returncode == 0, m.stderr
    r = subprocess.run([sys.executable, str(HERE / "render_report_parts.py"), str(ws), "--lang", lang], capture_output=True, text=True)
    draft = (ws / "REPORT.draft.md").read_text(encoding="utf-8") if (ws / "REPORT.draft.md").exists() else ""
    return r, draft, json.loads((ws / "report-ids.json").read_text(encoding="utf-8"))


def block_of(draft, rid):
    m = re.search(rf"^#{{3,4}} {rid}\. .*?(?=^#{{2,4}} |\Z)", draft, re.S | re.M)
    assert m, f"no block for {rid}"
    return m.group(0)


def test_every_finding_has_one_block_with_its_own_values():
    r, draft, ids = run(FINDINGS)
    assert r.returncode == 0, r.stderr
    assert len(ids) == len(FINDINGS)
    for rid, meta in ids.items():
        src = meta["source"][0]
        if meta["tier"] == 3:                       # tier 3 is a list the orchestrator sorts into five blocks
            assert f"- {rid}: Title of {src}" in draft, f"{rid} missing from the tier 3 list"
            continue
        assert len(re.findall(rf"^#{{3,4}} {rid}\. ", draft, re.M)) == 1, f"{rid} does not have exactly one block"
        b = block_of(draft, rid)
        assert f"Problem text of {src}." in b and f"Fix text of {src}." in b, f"{rid}: text altered or missing"
        assert "`src/page.html` lines 2 to 3" in b, f"{rid}: location altered or missing"


def test_fields_come_in_the_fixed_order():
    _, draft, ids = run(FINDINGS)
    rid = next(r for r, m in ids.items() if m["source"] == ["KBD-001"])
    b = block_of(draft, rid)
    order = [b.index(label) for label in ("Severity blocker", "Problem:", "Where:", "Fix:", "[before]", "<before-KBD-001>",
                                          "[after]", "<after-KBD-001>", "Watch out:", "Verify:")]
    assert order == sorted(order), "fields are out of the template's order"
    rid2 = next(r for r, m in ids.items() if m["source"] == ["VIS-001"])
    b2 = block_of(draft, rid2)
    assert b2.index("Problem:") < b2.index("Design impact: Lightness only.") < b2.index("Where:"), "tier 2 lacks design impact after problem"
    assert "2.81 to 1, then 4.54 to 1" in draft, "token table lacks the measured contrast before and after"


def test_minor_findings_get_the_compact_block():
    _, draft, ids = run(FINDINGS)
    b = block_of(draft, next(r for r, m in ids.items() if m["source"] == ["KBD-003"]))
    assert "Problem:" in b and "Fix:" in b and "Verify:" not in b and "```" not in b


def test_structure_meets_the_read_aloud_rules():
    for lang in ("en", "nl"):
        _, draft, _ = run(FINDINGS, lang)
        lines = re.sub(r"```.*?```", "", draft, flags=re.S).splitlines()     # code is not structure
        for i, line in enumerate(lines):
            if re.match(r"^\|[-: |]+\|$", line):
                width = line.count("|") - 1
                assert width <= 4, f"{lang}: table with {width} columns"
                j = i + 1
                while j < len(lines) and lines[j].startswith("|"):
                    assert lines[j].count("|") - 1 == width, f"{lang}: a row breaks its table: {lines[j][:70]}"
                    j += 1
        levels = [len(l) - len(l.lstrip("#")) for l in lines if re.match(r"^#+ ", l)]
        assert levels[0] == 1 and all(b <= a + 1 for a, b in zip(levels, levels[1:])), f"{lang}: heading level skipped"
        assert not any(re.match(r"^\s{2,}[-*\d]", l) for l in lines if not l.startswith("     ")), f"{lang}: nested list"
        assert "<!-- WRITE:" in draft, "no gaps marked for the orchestrator"


def test_dutch_uses_one_word_per_severity():
    _, draft, ids = run(FINDINGS, "nl")
    assert "| blokkerend |" in draft and "Ernst blokkerend," in draft, "table and block disagree on the severity word"
    assert "| serious |" not in draft and "| blocker |" not in draft


def test_a_finding_without_a_tier_is_reported_not_dropped():
    r, draft, _ = run(FINDINGS + [finding("KBD-009", visual_impact="huge", proposed_tier="T9")])
    assert r.returncode == 1, "a finding that is in no table must fail the run"
    assert "KBD-009" in r.stderr, r.stderr


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("all render checks passed")
