#!/usr/bin/env python3
"""Self-check for merge_findings.py against imperfect agent output.

    python3 scripts/test_merge.py

Its input is written by language models, so malformed findings are the expected case,
not an exceptional one: one bad file must never cost the other agents their work.
Standard library only, writes to a temp dir.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OWNERSHIP = HERE.parent / "references" / "wcag-ownership.md"

GOOD = {
    "agent": "keyboard-focus",
    "sc_coverage": {"2.1.1": {"status": "fail", "findings": ["KBD-001"]}},
    "findings": [{
        "id": "KBD-001", "fingerprint": "keyboard-inoperable@src/Dropdown.tsx",
        "title": "Dropdown cannot be opened with the keyboard", "severity": "blocker",
        "evidence": [{"file": "src/Dropdown.tsx", "lines": "42-58", "snippet": "<div onClick>"}],
        "wcag": [{"sc": "2.1.1", "name": "Keyboard", "level": "A"}],
        "visual_impact": "none", "proposed_tier": 1,
        "fix": {"ownership": "project", "summary": "Use a button."},
        "effort": "M", "confidence": "high", "verify": "Tab to it.",
    }],
}


def merge(ws: Path):
    r = subprocess.run([sys.executable, str(HERE / "merge_findings.py"), str(ws),
                        "--ownership", str(OWNERSHIP)], capture_output=True, text=True)
    return r


def workspace(d, files):
    ws = Path(d) / ".a11y-audit"
    (ws / "findings").mkdir(parents=True)
    for name, content in files.items():
        p = ws / "findings" / name
        p.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return ws


def assert_good_survived(ws, r, what):
    assert r.returncode == 0, f"{what}: exited {r.returncode}\n{r.stderr}"
    merged = json.loads((ws / "findings" / "_merged.json").read_text())
    ids = [f["id"] for f in merged["findings"]]
    assert "KBD-001" in ids, f"{what}: the valid finding was lost (got {ids})"
    return merged


def test_malformed_shapes_do_not_abort_the_run():
    cases = {
        "no id": {"agent": "a", "findings": [{"title": "x", "visual_impact": "none"}]},
        "fix is a string": {"agent": "a", "findings": [{"id": "A-1", "fix": "just do it",
                                                        "title": "x", "visual_impact": "none"}]},
        "fix is null": {"agent": "a", "findings": [{"id": "A-2", "fix": None, "title": "x",
                                                    "visual_impact": "none"}]},
        "wcag as strings": {"agent": "a", "findings": [{"id": "A-3", "wcag": ["1.1.1"], "title": "x",
                                                        "visual_impact": "none", "fix": {}}]},
        "fingerprint is a number": {"agent": "a", "findings": [{"id": "A-4", "fingerprint": 42,
                                                                "title": "x", "visual_impact": "none", "fix": {}}]},
        "finding is a string": {"agent": "a", "findings": ["a missing label somewhere"]},
        "tier written as text": {"agent": "a", "findings": [{"id": "A-7", "title": "x", "visual_impact": "huge",
                                                              "proposed_tier": "T9", "fix": {}}]},
        "tier as a list": {"agent": "a", "findings": [{"id": "A-8", "title": "x", "visual_impact": ["none"],
                                                        "proposed_tier": [1], "fix": {}}]},
        "findings is an object": {"agent": "a", "findings": {"id": "A-5"}},
        "sc_coverage is a list": {"agent": "a", "sc_coverage": [{"2.1.1": "fail"}], "findings": []},
        "top level is a list": [{"id": "A-6"}],
        "invalid JSON": "{not json at all",
    }
    for label, payload in cases.items():
        with tempfile.TemporaryDirectory() as d:
            ws = workspace(d, {"keyboard-focus.json": GOOD, "broken.json": payload})
            assert_good_survived(ws, merge(ws), label)
        print("   survived:", label)


def test_dedupe_file_shapes():
    for label, payload in {"a list": ["KBD-001"], "a bare string value": {"KBD-001": "KBD-002"},
                           "invalid JSON": "{,"}.items():
        with tempfile.TemporaryDirectory() as d:
            ws = workspace(d, {"keyboard-focus.json": GOOD})
            p = ws / "findings" / "_dedupe.json"
            p.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
            assert_good_survived(ws, merge(ws), f"_dedupe.json {label}")
        print("   survived: _dedupe.json", label)


def test_non_utf8_file_is_skipped():
    with tempfile.TemporaryDirectory() as d:
        ws = workspace(d, {"keyboard-focus.json": GOOD})
        (ws / "findings" / "latin1.json").write_bytes(b'{"agent":"a","findings":[{"id":"L-1",'
                                                      b'"title":"caf\xe9","visual_impact":"none","fix":{}}]}')
        assert_good_survived(ws, merge(ws), "non-UTF8 findings file")


def test_persona_ids_do_not_collide():
    with tempfile.TemporaryDirectory() as d:
        ws = workspace(d, {"keyboard-focus.json": GOOD})
        (ws / "personas").mkdir()
        (ws / "personas" / "screen-reader-user.md").write_text(
            "# Screen reader\n\n## New findings\n"
            '```json\n[{"title": "first", "visual_impact": "none", "fix": {}},\n'
            ' {"title": "second", "visual_impact": "none", "fix": {}}]\n```\n'
            "\n## end\n", encoding="utf-8")
        merged = assert_good_survived(ws, merge(ws), "two id-less persona findings")
        pids = [f["id"] for f in merged["findings"] if f["id"].startswith("PER-")]
        assert len(set(pids)) == len(pids) == 2, f"persona ids collided: {pids}"


def test_missing_ownership_file_is_reported():
    with tempfile.TemporaryDirectory() as d:
        ws = workspace(d, {"keyboard-focus.json": GOOD})
        r = subprocess.run([sys.executable, str(HERE / "merge_findings.py"), str(ws),
                            "--ownership", str(Path(d) / "nope.md")], capture_output=True, text=True)
        assert r.returncode == 2, f"expected exit 2, got {r.returncode}"
        assert "does not exist" in r.stderr, r.stderr


SOURCE = """<header>
  <a class="more" href="/news">Lees meer</a>
  <div class="menu" onclick="toggle()">Menu</div>
</header>
"""


def finding(fid, **over):
    """A finding that is true of SOURCE; each test case overrides the one field it gets wrong."""
    f = {"id": fid, "fingerprint": f"{fid.lower()}@src/page.html", "title": f"Finding {fid}", "severity": "serious",
         "evidence": [{"file": "src/page.html", "lines": "3", "snippet": '<div class="menu" onclick="toggle()">'}],
         "wcag": [{"sc": "2.1.1", "name": "Keyboard", "level": "A"}],
         "visual_impact": "none", "proposed_tier": 1, "fix": {"ownership": "project", "summary": "Use a button."},
         "effort": "S", "confidence": "high", "verify": "Tab to it."}
    f.update(over)
    return f


def claims_workspace(d, findings):
    ws = workspace(d, {"orchestrator.json": {"agent": "orchestrator", "findings": findings}})
    (Path(d) / "src").mkdir()
    (Path(d) / "src" / "page.html").write_text(SOURCE, encoding="utf-8")
    return ws


def problems_of(ws, fid):
    r = merge(ws)
    assert r.returncode == 0, r.stderr
    merged = json.loads((ws / "findings" / "_merged.json").read_text())
    return [p for p in merged["problems"] if p.startswith(fid + ":")], merged


def test_true_claims_raise_no_problems():
    # The checks are only worth having if a correct finding passes them silently.
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [
            finding("OK-001"),
            finding("OK-002", wcag=[], best_practice_only=True),
            finding("OK-003", evidence=[{"file": "src/page.html", "lines": "2-3",
                                         "snippet": '<a class="more" ... Lees meer</a>'}]),
            finding("OK-004", wcag=[{"sc": "1.4.3", "name": "Contrast (Minimum)", "level": "AA"}],
                    colours={"fg": "#9a9a9a", "bg": "#ffffff", "ratio": 2.81, "required": 4.5,
                             "suggested_fg": "#767676", "suggested_ratio": 4.54}),
            finding("OK-005", evidence=[{"url": "http://localhost:3000/", "selector": "#menu"}]),
            # the agent put two source lines on one and dropped the indentation
            finding("OK-006", evidence=[{"file": "src/page.html", "lines": "2-3",
                                         "snippet": '<a class="more" href="/news">Lees meer</a><div class="menu"'}]),
        ])
        r = merge(ws)
        merged = json.loads((ws / "findings" / "_merged.json").read_text())
        assert merged["problems"] == [], f"correct findings were flagged: {merged['problems']}"
        assert merged["notes"] == [], f"correct findings were annotated: {merged['notes']}"


def test_false_claims_are_flagged():
    cases = {
        "evidence file that does not exist": (finding("BAD-001", evidence=[{"file": "nope/missing.tsx", "lines": "9"}]),
                                              "not found in the repository"),
        "evidence outside the repository": (finding("BAD-002", evidence=[{"file": "../../etc/hosts", "lines": "1"}]),
                                            "not found in the repository"),
        "lines past the end of the file": (finding("BAD-003", evidence=[{"file": "src/page.html", "lines": "900-950"}]),
                                           "past the end"),
        "snippet that is not in the file": (finding("BAD-004", evidence=[{"file": "src/page.html", "lines": "3",
                                                                          "snippet": "<button disabled>Send</button>"}]),
                                            "snippet not found"),
        "snippet with two words run together": (finding("BAD-010", evidence=[{"file": "src/page.html", "lines": "2",
                                                                              "snippet": '<a class="more" href="/news">Leesmeer</a>'}]),
                                                "snippet not found"),
        "short invented snippet": (finding("BAD-011", evidence=[{"file": "src/page.html", "lines": "2", "snippet": "x = 1 + 2;"}]),
                                   "snippet not found"),
        "tier that contradicts the visual impact": (finding("BAD-012", proposed_tier=3), "one of the two fields is wrong"),
        "no fix ownership": (finding("BAD-013", fix={"summary": "Use a button."}), "'project' is assumed"),
        "triple-A criterion only": (finding("BAD-005", wcag=[{"sc": "2.4.9", "name": "Link Purpose (Link Only)", "level": "AAA"}]),
                                    "not a WCAG 2.2 level A or AA criterion"),
        "no criterion and no best-practice marker": (finding("BAD-006", wcag=[]), "not marked best_practice_only"),
        "contrast that already passes": (finding("BAD-008", colours={"fg": "#595959", "bg": "#ffffff", "ratio": 3.0, "required": 4.5}),
                                         "may not be a failure"),
        "suggested colour that still fails": (finding("BAD-009", colours={"fg": "#9a9a9a", "bg": "#ffffff", "ratio": 2.81,
                                                                           "required": 4.5, "suggested_fg": "#8a8a8a"}),
                                              "short of the required"),
    }
    for label, (bad, expect) in cases.items():
        with tempfile.TemporaryDirectory() as d:
            ws = claims_workspace(d, [bad])
            mine, _ = problems_of(ws, bad["id"])
            assert any(expect in p for p in mine), f"{label}: expected {expect!r}, got {mine}"
        print("   flagged:", label)


def test_what_the_merge_settles_itself_is_a_note_not_a_problem():
    # A problem asks the orchestrator for a decision. If the list also holds everything the merge already
    # corrected, its length says nothing and nobody reads it.
    cases = {
        "level from memory": (finding("FIX-001", wcag=[{"sc": "2.4.4", "name": "Link purpose", "level": "AAA"}]), "level AAA, it is level A"),
        "contrast ratio from memory, still a failure": (finding("FIX-002", colours={"fg": "#9a9a9a", "bg": "#ffffff", "ratio": 3.9,
                                                                                    "required": 4.5}), "measures 2.81"),
        "criterion as a bare string": (finding("FIX-003", wcag=["2.1.1"]), "read as a criterion number"),
        "no fingerprint": (finding("FIX-006", fingerprint=""), "generated from title+file"),
    }
    for label, (f, expect) in cases.items():
        with tempfile.TemporaryDirectory() as d:
            ws = claims_workspace(d, [f])
            r = merge(ws)
            merged = json.loads((ws / "findings" / "_merged.json").read_text())
            assert any(expect in n for n in merged["notes"]), f"{label}: expected a note with {expect!r}, got {merged['notes']}"
            assert merged["problems"] == [], f"{label}: listed as a problem: {merged['problems']}"
            assert "0 problems to resolve, " in r.stdout, r.stdout
            text = (ws / "findings" / "_merged.md").read_text()
            assert "## Settled by the merge (" in text and "## Problems to resolve" not in text, label
        print("   noted:", label)


def test_a_fix_given_as_text_is_kept_but_its_ownership_is_asked_for():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("FIX-004", fix="Use a button.")])
        merge(ws)
        merged = json.loads((ws / "findings" / "_merged.json").read_text())
        assert merged["findings"][0]["fix"]["summary"] == "Use a button." and any("kept as fix.summary" in n for n in merged["notes"])
        assert len(merged["problems"]) == 1 and "'project' is assumed" in merged["problems"][0], merged["problems"]


def test_two_findings_without_a_latin_title_are_not_merged_into_one():
    # Agents write in the report language. A title in Japanese leaves no slug to build a fingerprint from,
    # and two such findings on one file used to end up with the same one and be merged.
    with tempfile.TemporaryDirectory() as d:
        a = finding("JPN-001", fingerprint="", title="\u30b3\u30f3\u30c8\u30e9\u30b9\u30c8\u4e0d\u8db3")
        b = finding("JPN-002", fingerprint="", title="\u30d5\u30a9\u30fc\u30ab\u30b9\u4e0d\u53ef")
        ws = claims_workspace(d, [a, b])
        merge(ws)
        merged = json.loads((ws / "findings" / "_merged.json").read_text())
        assert sorted(f["id"] for f in merged["findings"]) == ["JPN-001", "JPN-002"], [f["id"] for f in merged["findings"]]
        assert len({f["fingerprint"] for f in merged["findings"]}) == 2, [f["fingerprint"] for f in merged["findings"]]


def test_level_and_ratio_are_corrected_in_the_output():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("FIX-001", wcag=[{"sc": "2.4.4", "name": "Link purpose", "level": "AAA"}],
                                          colours={"fg": "#9a9a9a", "bg": "#ffffff", "ratio": 4.9, "required": 4.5})])
        merge(ws)
        f = json.loads((ws / "findings" / "_merged.json").read_text())["findings"][0]
        assert f["wcag"][0] == {"sc": "2.4.4", "name": "Link Purpose (In Context)", "level": "A"}, f["wcag"]
        assert f["colours"]["ratio"] == 2.81, f["colours"]


def test_a_personas_words_are_not_checked_as_a_quote_from_the_file():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("OK-001")])
        (ws / "personas").mkdir()
        (ws / "personas" / "screen-reader-user.md").write_text("# Screen reader user\n\n## New findings\n```json\n" + json.dumps([
            {"title": "Menu is skipped", "severity": "serious", "location": "src/page.html:3", "evidence": "Tab went past the menu.",
             "wcag": "2.1.1", "tier": 1, "fix": "Use a button."}]) + "\n```\n\n## end\n", encoding="utf-8")
        r = merge(ws)
        merged = json.loads((ws / "findings" / "_merged.json").read_text())
        per = [f for f in merged["findings"] if str(f["id"]).startswith("PER-")]
        assert len(per) == 1, f"the persona finding did not arrive: {r.stdout}{r.stderr}"
        assert per[0]["evidence"][0] == {"file": "src/page.html", "lines": "3", "observation": "Tab went past the menu."}, per[0]["evidence"]
        assert not [p for p in merged["problems"] if "snippet" in p], merged["problems"]
        assert any("'location' instead of evidence" in n for n in merged["notes"]), merged["notes"]
        assert not [p for p in merged["problems"] if "location" in p], merged["problems"]


def test_a_previous_audit_that_is_not_there_is_a_problem_in_the_files_and_on_stderr():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("OK-001")])
        gone, broken = Path(d) / "nowhere", Path(d) / "broken"
        broken.mkdir()
        (broken / "_merged.json").write_text("[1, 2", encoding="utf-8")
        for prev, word in ((gone, "--previous given but"), (broken, "unreadable or not an object")):
            r = subprocess.run([sys.executable, str(HERE / "merge_findings.py"), str(ws), "--ownership", str(OWNERSHIP),
                                "--previous", str(prev)], capture_output=True, text=True)
            assert "1 problems to resolve" in r.stdout and word in r.stderr, r.stdout + r.stderr
            listed = json.loads((ws / "findings" / "_merged.json").read_text())["problems"]
            assert len(listed) == 1 and word in listed[0], listed          # the phase check reads this list, not stderr
            assert word in (ws / "findings" / "_merged.md").read_text(encoding="utf-8")


def test_a_personas_criterion_is_settled_and_an_experts_is_asked_about():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("OK-001"), finding("AAA-001", wcag=[{"sc": "2.4.9"}]), finding("NONE-001", wcag=[])])
        (ws / "personas").mkdir()
        base = {"severity": "serious", "visual_impact": "none", "proposed_tier": 1, "fix": {"summary": "Say where I am."}}
        (ws / "personas" / "cognitive-user.md").write_text("# Cognitive user\n\n## New findings\n```json\n" + json.dumps([
            {**base, "id": "PER-cognitive-001", "title": "No criterion", "location": "the contact page"},
            {**base, "id": "PER-cognitive-002", "title": "Triple A only", "wcag": [{"sc": "2.4.9"}],
             "evidence": [{"file": "src/page.html", "lines": "3"}]},
            {**base, "id": "PER-cognitive-003", "title": "One of each", "wcag": [{"sc": "2.4.9"}, {"sc": "2.1.1"}],
             "evidence": [{"file": "src/page.html", "lines": "3"}]}]) + "\n```\n\n## end\n", encoding="utf-8")
        r = merge(ws)
        merged = json.loads((ws / "findings" / "_merged.json").read_text())
        by = {f["id"]: f for f in merged["findings"]}
        assert not [p for p in merged["problems"] if p.startswith("PER-")], merged["problems"]
        assert by["PER-cognitive-001"]["best_practice_only"] is True and by["PER-cognitive-001"]["evidence"] == [{"url": "the contact page"}], by["PER-cognitive-001"]
        assert by["PER-cognitive-002"]["wcag"] == [] and by["PER-cognitive-002"]["best_practice_only"] is True, by["PER-cognitive-002"]
        assert [w["sc"] for w in by["PER-cognitive-003"]["wcag"]] == ["2.1.1"] and not by["PER-cognitive-003"].get("best_practice_only"), by["PER-cognitive-003"]
        said = " | ".join(merged["notes"])
        assert "PER-cognitive-002: 2.4.9 is not" in said and "PER-cognitive-001: a persona finding without" in said, merged["notes"]
        # the same two faults in an expert's finding still need a decision
        assert [p for p in merged["problems"] if p.startswith("AAA-001: 2.4.9 is not")], merged["problems"]
        assert [p for p in merged["problems"] if p.startswith("NONE-001: no WCAG criterion")], merged["problems"]


def flows(ws, *rows, header="| Flow | Result | Feel | Main obstacle | Findings |\n|---|---|---|---|---|\n"):
    (ws / "personas").mkdir(exist_ok=True)
    (ws / "personas" / "screen-reader-user.md").write_text("# Screen reader user\n\n## Flow results\n" + header + "\n".join(rows) + "\n\n## end\n", encoding="utf-8")
    r = merge(ws)
    assert r.returncode == 0, r.stderr
    merged = json.loads((ws / "findings" / "_merged.json").read_text())
    return {f["id"]: f for f in merged["findings"]}, [p for p in merged["problems"] if p.startswith("persona ")], merged


def test_a_flow_that_failed_raises_the_findings_its_row_names_and_says_so_when_it_names_none():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("KBD-001"), finding("KBD-002"), finding("KBD-003", severity="minor")])
        by, said, merged = flows(ws, "| Read a chart | failed | long | the chart is empty for me | KBD-001 |",
                                     "| Add a rule | completed only with help | long | focus is lost | KBD-003 |",
                                     "| Search | completed with difficulty | fine | nothing | |")
        assert by["KBD-001"]["severity"] == "blocker" and by["KBD-003"]["severity"] == "critical" and by["KBD-002"]["severity"] == "serious", by
        assert by["KBD-003"]["severity_before_persona"] == "minor" and len(merged["severity_upgrades"]) == 2
        assert not said, said                                   # a flow that went well needs no finding
        # the row as it was written before the table had a column for the IDs
        by, said, _ = flows(ws, "| Read a chart | failed | long | the chart is empty (KBD-001) |", header="| Flow | Result | Feel | Main obstacle |\n|---|---|---|---|\n")
        assert by["KBD-001"]["severity"] == "blocker" and not said, said
        # no ID: the flow failed and nothing was raised
        by, said, merged = flows(ws, "| Read a chart | failed | long | the chart is empty for me | |")
        assert by["KBD-001"]["severity"] == "serious" and not merged["severity_upgrades"]
        assert len(said) == 1 and "flow 'Read a chart' is 'failed' but its row names no finding" in said[0], said
        by, said, _ = flows(ws, "| Add a rule | completed only with help or a workaround | long | focus is lost | |")
        assert len(said) == 1 and "names no finding" in said[0], said
        # an ID that is no finding is the same silence, and is named
        by, said, _ = flows(ws, "| Read a chart | failed | long | the chart | KBD-009 |")
        assert any("names KBD-009, which is not a finding" in p for p in said) and any("names no finding" in p for p in said), said
        by, said, _ = flows(ws, "| Read a chart | failed | long | the chart | KBD-001, KBD-009 |")
        assert by["KBD-001"]["severity"] == "blocker" and len(said) == 1 and "KBD-009" in said[0], said


def test_a_visible_fix_without_its_design_impact_is_asked_for():
    with tempfile.TemporaryDirectory() as d:
        subtle = dict(visual_impact="subtle", proposed_tier=2)
        ws = claims_workspace(d, [finding("VIS-001", **subtle), finding("VIS-002", tier_rationale="A darker border.", **subtle),
                                  finding("VIS-003", tier_rationale="  ", **subtle), finding("VIS-004", severity="minor", **subtle),
                                  finding("VIS-005", severity="minor", **subtle), finding("VIS-006"),
                                  finding("VIS-007", visual_impact="significant", proposed_tier=3)])
        by, _, merged = flows(ws, "| Read a chart | failed | long | the chart | VIS-005 |")
        asked = sorted(p.split(":")[0] for p in merged["problems"] if "without tier_rationale" in p)
        # the minor one the report prints short; the one a failed flow raised is no longer minor
        assert asked == ["VIS-001", "VIS-003", "VIS-005"], merged["problems"]     # not VIS-002 (has one), VIS-004 (minor), VIS-006 (tier 1), VIS-007 (tier 3)
        assert by["VIS-005"]["severity"] == "blocker"


def test_a_coverage_reason_is_kept_under_either_key():
    with tempfile.TemporaryDirectory() as d:
        ws = workspace(d, {"keyboard-focus.json": {"agent": "keyboard-focus", "lenses": ["keyboard-focus"], "findings": [], "sc_coverage": {
            "2.1.4": {"status": "n/a", "reason": "No single-key shortcuts."}, "2.1.2": {"status": "pass", "note": "No traps found."}}}})
        merge(ws)
        cov = (ws / "coverage.md").read_text()
        assert "No single-key shortcuts." in cov and "No traps found." in cov, "a reason given as 'reason' was dropped from the matrix"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("all merge checks passed")
