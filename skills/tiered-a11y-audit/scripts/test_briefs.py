#!/usr/bin/env python3
"""Self-check for what build_briefs.py leaves out of a brief, and what it must not leave out.

    python3 scripts/test_briefs.py

A brief is all an agent knows. Cutting too much makes an agent guess; so each cut is held against the reader
it is made for, in all three modes. Standard library only, writes to a temp dir.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(HERE))
from build_briefs import without_fields, without_sections  # noqa: E402
ROW = re.compile(r"^\| (\d\.\d\.\d+) \|", re.M)


def build(*flags, skill=SKILL):
    ws = Path(tempfile.mkdtemp())
    (ws / "stack-profile.md").write_text("- Mode: test\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(HERE / "build_briefs.py"), str(skill), str(ws), *flags], capture_output=True, text=True)
    return r, ws / "briefs"


def brief(briefs, name):
    return (briefs / f"{name}.md").read_text(encoding="utf-8")


def test_a_lens_gets_its_own_criterion_rows_and_no_others():
    r, briefs = build()
    assert r.returncode == 0, r.stderr
    kbd = brief(briefs, "keyboard-focus")
    assert ROW.findall(kbd) == ["2.1.1", "2.1.2", "2.1.4", "2.4.1", "2.4.3", "2.4.7", "2.4.11"], ROW.findall(kbd)
    assert "| 2.4.7 | Focus Visible | AA | keyboard-focus |" in kbd, "a row lost its name or level"
    # who owns the rest, and who files a shared pattern, stay: cross-lens notes depend on both
    assert "- **content-media (14):**" in kbd and "## Pattern owners" in kbd and "| Live regions and status messages | dynamic-content |" in kbd


def test_every_criterion_is_in_exactly_one_brief_in_every_mode():
    for flags, n in (((), 6), (("--lean",), 4), (("--mini",), 2)):
        r, briefs = build(*flags)
        assert r.returncode == 0, r.stderr
        experts = json.loads((briefs / "_agents.json").read_text(encoding="utf-8"))["experts"]
        rows = [sc for name in experts for sc in ROW.findall(brief(briefs, name))]
        assert len(experts) == n and len(rows) == len(set(rows)) == 55, (flags, len(rows))
    r, briefs = build("--lean")
    assert {"2.1.1", "4.1.3"} <= set(ROW.findall(brief(briefs, "keyboard-dynamic"))), "a merged agent needs the rows of both its lenses"


def test_what_only_the_orchestrator_uses_is_left_out_and_what_an_expert_needs_stays():
    _, briefs = build()
    for name in ("keyboard-focus", "framework-maximizer"):
        text = brief(briefs, name)
        assert "## Scoring rubric" not in text and "Persona verdicts set a floor" not in text, name
        for needed in ("## The decision test", "## Tier 1", "## Edge cases", "## Severity (independent of tier)", "| blocker |",
                       "an accepted exception is not conformance"):
            assert needed in text, f"{name} lost: {needed}"
    lens, maxi = brief(briefs, "keyboard-focus"), brief(briefs, "framework-maximizer")
    assert "- `sc_coverage` (top level)" in lens and "- `fix.ownership` (required)" in lens and "  - `override`" in lens
    assert "- `leverage` (framework-maximizer only)" not in lens and "- `kind` (optional)" not in lens
    assert "- `leverage` (framework-maximizer only)" in maxi and "- `kind` (optional)" in maxi
    assert ROW.findall(maxi) == [] and "| SC | Name | Level | Owner |" not in maxi, "the maximizer owns no criteria"
    assert "- **keyboard-focus (7):**" in maxi and "## Pattern owners" in maxi


def test_a_persona_gets_the_fields_it_writes_and_not_the_expert_file_rules():
    _, briefs = build()
    text = brief(briefs, "screen-reader-user")
    for gone in ("- `sc_coverage` (top level)", "- `lenses` (top level)", "- `cross_lens_notes` (top level)", "- `fix.ownership` (required)",
                 "  - `override`", "- `leverage`", "- `kind`"):
        assert gone not in text, f"persona brief still carries: {gone}"
    for needed in ("- `fingerprint`", "- `visual_impact`", "- `evidence`", "- `wcag`", "- `severity`", "- `proposed_tier`", "- `fix.location`",
                   "- `effort`", "- `confidence`", "- `verify`", "Contrast findings additionally include"):
        assert needed in text, f"persona brief lost: {needed}"


def test_a_cut_ends_where_the_section_or_the_field_ends():
    # In the references as they are today, every cut happens to be followed by another cut or by the end of the
    # file, so the real briefs cannot show whether a cut stops in time.
    doc = "# T\nintro\n## A\na\n### B\nb\n### C\nc\n## D\nd"
    assert without_sections(doc, ("### B",), "doc") == "# T\nintro\n## A\na\n### C\nc\n## D\nd"
    assert without_sections(doc, ("## A",), "doc") == "# T\nintro\n## D\nd", "a section takes its subsections with it and nothing after"
    rules = "- `a`: one\n  - sub of a\n  more of a\n\nA paragraph after the list.\n- `b`: two\n- `ab`: three"
    assert without_fields(rules, ("a",), "rules") == "\nA paragraph after the list.\n- `b`: two\n- `ab`: three"
    assert without_fields(rules, ("b",), "rules") == "- `a`: one\n  - sub of a\n  more of a\n\nA paragraph after the list.\n- `ab`: three"


def test_a_renamed_section_or_field_stops_the_build():
    for path, old, new, word in (("references/tiering.md", "## Scoring rubric (1–10)", "## Scoring", "has no section"),
                                 ("references/finding-schema.md", "- `leverage` (framework-maximizer only)", "- `lever` (framework-maximizer only)", "no rule for the field")):
        copy = Path(tempfile.mkdtemp()) / "skill"
        shutil.copytree(SKILL, copy, ignore=shutil.ignore_patterns("__pycache__"))
        f = copy / path
        text = f.read_text(encoding="utf-8")
        assert old in text
        f.write_text(text.replace(old, new), encoding="utf-8")
        r, briefs = build(skill=copy)
        assert r.returncode != 0 and word in r.stderr and "build_briefs.py" in r.stderr, f"{path}: {r.returncode} {r.stderr}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} checks passed")
