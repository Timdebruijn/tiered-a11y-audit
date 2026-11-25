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
from build_briefs import PERSONAS, chosen_personas, own_rows, without_fields, without_sections  # noqa: E402
ROW = re.compile(r"^\| (\d\.\d\.\d+) \|", re.M)


def build(*flags, skill=SKILL, profile="- Mode: test\n", ws=None):
    ws = ws or Path(tempfile.mkdtemp())
    (ws / "stack-profile.md").write_text(profile, encoding="utf-8")
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


def test_in_a_re_audit_each_agent_gets_the_earlier_fingerprints_of_its_own_area():
    earlier = [{"id": "KBD-004", "title": "Menu needs\n a mouse", "fingerprint": "keyboard-inoperable@src/Menu.tsx"},
               {"id": "VIS-002", "title": "Grey text", "fingerprint": "contrast-text@src/app.css"},
               {"id": "ORC-001", "title": "No page title", "fingerprint": "no-title@index.html", "wcag": [{"sc": "2.4.2"}]},   # by the owner of its criterion
               {"id": "FWK-001", "title": "No lint", "fingerprint": "no-a11y-lint@package.json"},
               {"id": "PER-low-vision-001", "title": "Menu off screen", "fingerprint": "popover-off-screen@header"},
               {"id": "KBD-009", "title": "No fingerprint"}, {"id": "ZZZ-001", "title": "Nobody's", "fingerprint": "odd@x"}]
    for flags, kbd in (((), "keyboard-focus"), (("--lean",), "keyboard-dynamic"), (("--mini",), "operate")):
        ws = Path(tempfile.mkdtemp())
        (ws / "stack-profile.md").write_text("- Mode: test\n", encoding="utf-8")
        (ws / "previous" / "findings").mkdir(parents=True)
        # the earlier audit as a bare list in one run, as an object in the others
        (ws / "previous" / "findings" / "_merged.json").write_text(json.dumps(earlier if flags else {"findings": earlier}), encoding="utf-8")
        r = subprocess.run([sys.executable, str(HERE / "build_briefs.py"), str(SKILL), str(ws), *flags], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        text = brief(ws / "briefs", kbd)
        assert "# Findings of the earlier audit" in text and "- `keyboard-inoperable@src/Menu.tsx`: Menu needs a mouse" in text, flags
        assert "contrast-text@" not in text and "popover-off-screen@" not in text and "odd@x" not in text, "a finding of another lens is not this agent's to refile"
        assert text.index("# Findings of the earlier audit") < text.index("# Start of your findings file"), "the skeleton stays the last thing an expert reads"
        assert "- `no-a11y-lint@package.json`: No lint" in brief(ws / "briefs", "framework-maximizer")
        assert "# Findings of the earlier audit" not in brief(ws / "briefs", "low-vision-user"), "a persona walks before it reads any finding"
        owner_of_title = [n for n in json.loads((ws / "briefs" / "_agents.json").read_text())["experts"] if "no-title@index.html" in brief(ws / "briefs", n)]
        assert len(owner_of_title) == 1, owner_of_title
    r, briefs = build()
    assert "# Findings of the earlier audit" not in brief(briefs, "keyboard-focus"), "a first audit has no earlier findings"


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
    for needed in ("- `id`", "- `instances`", "- `affected_users`", "best_practice_only", "- `fingerprint`", "- `visual_impact`", "- `evidence`", "- `wcag`", "- `severity`", "- `proposed_tier`", "- `fix.location`",
                   "- `effort`", "- `confidence`", "- `verify`", "Contrast findings additionally include"):
        assert needed in text, f"persona brief lost: {needed}"


def test_persona_briefs_are_written_for_the_personas_that_are_named():
    want = ["screen-reader-user", "low-vision-user", "motor-voice-user", "cognitive-user", "colour-blind-user"]
    r, briefs = build("--lean", "--playbook", "1,3", "--personas", "colour-blind, cognitive,Screen-Reader,low-vision-user,motor-voice")
    assert r.returncode == 0, r.stderr
    manifest = json.loads((briefs / "_agents.json").read_text(encoding="utf-8"))
    assert manifest["personas"] == want and manifest["personas_selected"] is True, manifest
    assert manifest["flags"] == ["--lean", "--playbook", "1,3", "--personas", "colour-blind, cognitive,Screen-Reader,low-vision-user,motor-voice"], manifest["flags"]
    assert sorted(p.stem for p in briefs.glob("*-user.md")) == sorted(want), "a brief for a persona that does not run is one somebody may spawn"
    assert "5 persona" in r.stdout and "personas: " + ", ".join(want) + "\n" in r.stdout, r.stdout

    # a selection made narrower afterwards takes the brief of the persona that fell out with it, and says so
    r, briefs = build("--personas", "screen-reader,low-vision,motor-voice,cognitive", ws=briefs.parent)
    assert sorted(p.stem for p in briefs.glob("*-user.md")) == sorted(want[:4]), sorted(briefs.glob("*-user.md"))
    assert "removed the brief of colour-blind-user" in r.stdout, r.stdout

    # without the flag nothing is guessed: all eight, as before, and the manifest says nobody chose
    r, briefs = build()
    manifest = json.loads((briefs / "_agents.json").read_text(encoding="utf-8"))
    assert manifest["personas"] == PERSONAS and manifest["personas_selected"] is False and manifest["flags"] == [], manifest
    assert len(list(briefs.glob("*-user.md"))) == 8 and "no --personas given" in r.stdout and "removed" not in r.stdout, r.stdout


def test_a_list_that_would_run_fewer_personas_than_the_mode_asks_for_is_refused():
    core = "screen-reader,low-vision,motor-voice,cognitive"
    for flags, why in ((("--personas", "screen-reader,low-vision,cognitive"), "leaves out motor-voice"),
                       (("--lean", "--personas", "older-novice"), "leaves out screen-reader, low-vision, motor-voice, cognitive"),
                       (("--mini", "--personas", "screen-reader"), "plus at least one other"),
                       (("--mini", "--personas", "low-vision,motor-voice"), "the screen reader persona plus"),
                       (("--personas", core + ",colourblind"), "not colourblind"),
                       (("--personas", " , "), "not an empty list")):
        r, briefs = build(*flags)
        assert r.returncode != 0 and why in r.stderr and r.stderr.startswith("build_briefs: "), (flags, r.stderr)
        assert not (briefs / "_agents.json").exists(), "a refused run must not leave a manifest the phase check would read"
    assert chosen_personas(core + ",deaf", "full") == PERSONAS[:4] + ["deaf-user"]
    assert chosen_personas("motor-voice,screen-reader", "mini") == ["screen-reader-user", "motor-voice-user"]
    r, briefs = build("--mini", "--personas", "screen-reader,low-vision")
    assert r.returncode == 0 and sorted(p.stem for p in briefs.glob("*-user.md")) == ["low-vision-user", "screen-reader-user"], r.stderr


def test_a_persona_gets_the_tiering_rules_it_proposes_a_tier_by():
    r, briefs = build()
    p, lens = brief(briefs, "cognitive-user"), brief(briefs, "forms-input")
    for heading in ("## The decision test", "## Tier 3 — The road to a 10", "## Edge cases", "## Severity (independent of tier)"):
        assert heading in p, f"a persona proposes a tier and a severity without {heading}"
    assert "## Fix ownership" not in p and "## Scoring rubric" not in p and "### Persona verdicts set a floor" not in p
    assert "## Fix ownership" in lens, "the cut for personas must not reach the experts"
    # a persona cites criteria too, so it gets the list of the ones that are cited wrongly, once, and nothing else of the experts' protocol
    assert p.count("## Commonly misapplied criteria") == 1 and "**3.2.3 Consistent Navigation**" in p and "**4.1.3 Status Messages**" in p
    assert "## Fix ownership" not in p.split("## Commonly misapplied criteria")[1].split("# Stack profile")[0]
    assert "## Common false positives" not in p and "Own your criteria" not in p


def test_a_cut_ends_where_the_section_or_the_field_ends():
    # In the references as they are today, every cut happens to be followed by another cut or by the end of the
    # file, so the real briefs cannot show whether a cut stops in time.
    doc = "# T\nintro\n## A\na\n### B\nb\n### C\nc\n## D\nd"
    assert without_sections(doc, ("### B",), "doc") == "# T\nintro\n## A\na\n### C\nc\n## D\nd"
    assert without_sections(doc, ("## A",), "doc") == "# T\nintro\n## D\nd", "a section takes its subsections with it and nothing after"
    rules = "- `a`: one\n  - sub of a\n  more of a\n\nA paragraph after the list.\n- `b`: two\n- `ab`: three"
    assert without_fields(rules, ("a",), "rules") == "\nA paragraph after the list.\n- `b`: two\n- `ab`: three"
    assert without_fields(rules, ("b",), "rules") == "- `a`: one\n  - sub of a\n  more of a\n\nA paragraph after the list.\n- `ab`: three"
    spaced = "- `a`: one\n\n  still a, after a blank line\n\nA paragraph.\n- `b`: two"
    assert without_fields(spaced, ("a",), "rules") == "\nA paragraph.\n- `b`: two", "indented text after a blank line was left behind without its rule"
    code = "# T\n## A\n```sh\n# a comment, not a heading\n```\nstill A\n## B\nb"
    assert without_sections(code, ("## A",), "doc") == "# T\n## B\nb", "a comment in a code block ended the cut"
    assert without_sections("# T\n```\n## A\n```\n## A\na", ("## A",), "doc") == "# T\n```\n## A\n```", "a heading shown inside a code block is not the section"


def test_a_cut_that_cannot_be_made_exactly_once_stops_instead_of_guessing():
    for call, text in ((without_sections, "# T\n## A\na\n## A\nagain"), (without_sections, "# T\n## B\nb"),
                       (without_fields, "- `x`: one\n- `x`: again"), (without_fields, "- `y`: one")):
        try:
            call(text, ("## A",) if call is without_sections else ("x",), "doc")
        except SystemExit as e:
            assert "update build_briefs.py" in str(e), e
        else:
            raise AssertionError(f"{call.__name__} went on with {text!r}")
    owners = {"1.1.1": {"owner": "content-media"}, "2.1.1": {"owner": "keyboard-focus"}}
    table = "| SC | Name | Level | Owner |\n|---|---|---|---|\n| 1.1.1 | Non-text Content | A | content-media |\n| 2.1.1 | Keyboard | A | keyboard-focus |\n| 9.9.9 | Not a criterion | A | nobody |"
    assert own_rows(table, ["keyboard-focus"], owners).count("\n") == 3 and "| 1.1.1 |" not in own_rows(table, ["keyboard-focus"], owners)
    assert "| 9.9.9 |" in own_rows(table, ["keyboard-focus"], owners), "a line that is not a known criterion is not a row to cut"


def test_a_renamed_section_or_field_stops_the_build():
    for path, old, new, word in (("references/tiering.md", "## Scoring rubric (1–10)", "## Scoring", "has 0 sections"),
                                 ("references/finding-schema.md", "- `leverage` (framework-maximizer only)", "- `lever` (framework-maximizer only)", "no single rule for the field"),
                                 ("references/finding-schema.md", "- `cross_lens_notes` (top level)", "- `notes_across` (top level)", "no single rule for the field"),
                                 ("references/wcag-ownership.md", "| 2.1.1 | Keyboard | A | keyboard-focus |", "| 2.1.1 | Keyboard | A | keyboard |", "no lens of this run")):
        copy = Path(tempfile.mkdtemp()) / "skill"
        shutil.copytree(SKILL, copy, ignore=shutil.ignore_patterns("__pycache__"))
        f = copy / path
        text = f.read_text(encoding="utf-8")
        assert old in text
        f.write_text(text.replace(old, new), encoding="utf-8")
        r, briefs = build(skill=copy)
        assert r.returncode != 0 and word in r.stderr and r.stderr.startswith("build_briefs: "), f"{path}: {r.returncode} {r.stderr}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} checks passed")
