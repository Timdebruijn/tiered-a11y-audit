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


def reaudit(ws, previous, delta_map=None):
    prev = ws.parent / "previous"
    (prev / "findings").mkdir(parents=True, exist_ok=True)
    (prev / "findings" / "_merged.json").write_text(json.dumps(previous), encoding="utf-8")
    m = ws / "findings" / "_delta-map.json"
    m.write_text(json.dumps(delta_map), encoding="utf-8") if delta_map is not None else m.unlink() if m.exists() else None
    r = subprocess.run([sys.executable, str(HERE / "merge_findings.py"), str(ws), "--ownership", str(OWNERSHIP), "--previous", str(prev)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    merged = json.loads((ws / "findings" / "_merged.json").read_text())
    return merged.get("delta"), merged, (ws / "delta.md").read_text(encoding="utf-8") if (ws / "delta.md").exists() else ""


def test_an_earlier_finding_nobody_filed_again_is_not_called_resolved():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("KBD-001", fingerprint="keyboard-inoperable@src/page.html"),
                                  finding("SEM-001", fingerprint="missing-h1@src/page.html", wcag=[{"sc": "1.3.1"}]),
                                  finding("VIS-001", fingerprint="contrast-text@src/page.html", wcag=[{"sc": "1.4.3"}])])
        old = [{"id": "KBD-004", "title": "Menu needs a mouse", "fingerprint": "keyboard-inoperable@src/page.html"},
               {"id": "SEM-002", "title": "No main heading", "fingerprint": "missing-heading@src/page.html", "wcag": [{"sc": "1.3.1"}]},
               {"id": "DYN-003", "title": "Toast is not announced", "fingerprint": "no-status-message@src/toast.js", "wcag": [{"sc": "4.1.3"}]},
               {"id": "FRM-001", "title": "Field without a label", "fingerprint": "missing-label@src/form.html", "wcag": [{"sc": "1.3.1"}]}]
        # the earlier audit as a bare list, which is what an early version of the skill wrote
        delta, merged, md = reaudit(ws, old)
        assert delta["resolved"] == [] and delta["still_open"] == ["keyboard-inoperable@src/page.html"], delta
        assert delta["not_reported"] == ["missing-heading@src/page.html", "missing-label@src/form.html", "no-status-message@src/toast.js"], delta
        assert delta["new"] == ["contrast-text@src/page.html", "missing-h1@src/page.html"] and not merged["problems"], (delta, merged["problems"])
        assert delta["earlier"]["no-status-message@src/toast.js"] == {"id": "DYN-003", "title": "Toast is not announced"}
        # the same criterion in the same file: put forward as the same problem under another slug, and nothing else is
        assert "- SEM-002 · No main heading · `missing-heading@src/page.html`\n  - may be SEM-001" in md, md
        assert md.count("  - may be ") == 1, md
        # the orchestrator's answer: one is the same problem, one was checked and is gone, one is left open
        delta, merged, md = reaudit(ws, {"findings": old}, {"missing-heading@src/page.html": "SEM-001", "no-status-message@src/toast.js": "resolved"})
        assert delta["resolved"] == ["no-status-message@src/toast.js"] and delta["not_reported"] == ["missing-label@src/form.html"], delta
        assert delta["still_open"] == ["keyboard-inoperable@src/page.html", "missing-h1@src/page.html"] and delta["new"] == ["contrast-text@src/page.html"], delta
        assert {f["id"]: f["delta"] for f in merged["findings"]} == {"KBD-001": "still open", "SEM-001": "still open", "VIS-001": "new"}
        assert "(earlier `missing-heading@src/page.html`)" in md and not merged["problems"], merged["problems"]
        # a match by fingerprint works as well as one by ID
        delta, _, _ = reaudit(ws, old, {"missing-heading@src/page.html": "missing-h1@src/page.html"})
        assert "missing-h1@src/page.html" in delta["still_open"], delta


def test_a_map_that_does_not_hold_is_a_problem_in_every_file():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("KBD-001", fingerprint="keyboard-inoperable@src/page.html")])
        old = [{"id": "KBD-004", "title": "Menu needs a mouse", "fingerprint": "keyboard-inoperable@src/page.html"},
               {"id": "SEM-002", "title": "No main heading", "fingerprint": "missing-heading@src/page.html"}]
        delta, merged, _ = reaudit(ws, old, {"never-seen@x": "KBD-001", "missing-heading@src/page.html": "KBD-009",
                                             "keyboard-inoperable@src/page.html": "resolved"})
        said = [p for p in merged["problems"] if p.startswith("_delta-map.json")]
        assert len(said) == 3 and "no fingerprint of the earlier audit" in said[0] and "neither a finding of this run" in said[1] and "KBD-001 of this run has that fingerprint" in said[2], said
        assert delta["resolved"] == [] and delta["not_reported"] == ["missing-heading@src/page.html"], delta      # nothing is taken from a wrong entry
        assert "_delta-map.json:" in (ws / "findings" / "_merged.md").read_text(encoding="utf-8"), "the phase check reads the list, and the orchestrator the file"


def test_what_came_back_is_named_for_what_it_was():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("KBD-001", fingerprint="keyboard-inoperable@src/page.html"), finding("SEM-001", fingerprint="missing-h1@src/page.html")])
        # the earlier audit called one resolved after a check, and did not see the other again
        delta, _, _ = reaudit(ws, {"findings": [], "delta": {"resolved": ["keyboard-inoperable@src/page.html"], "not_reported": ["missing-h1@src/page.html"]}})
        assert delta["regressed"] == ["keyboard-inoperable@src/page.html"] and delta["still_open"] == ["missing-h1@src/page.html"] and delta["new"] == [], delta
        # a delta from before "not reported again" existed: its "resolved" was never a check, so what is back did not regress
        delta, _, _ = reaudit(ws, {"findings": [], "delta": {"resolved": ["keyboard-inoperable@src/page.html"]}})
        assert delta["regressed"] == [] and delta["still_open"] == ["keyboard-inoperable@src/page.html"] and delta["new"] == ["missing-h1@src/page.html"], delta


def test_what_was_not_seen_twice_stays_on_the_list_with_its_title():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("KBD-001", fingerprint="keyboard-inoperable@src/page.html")])
        prev = {"findings": [{"id": "KBD-004", "title": "Menu needs a mouse", "fingerprint": "keyboard-inoperable@src/page.html"}],
                "delta": {"resolved": [], "not_reported": ["no-status-message@src/toast.js"],
                          "earlier": {"no-status-message@src/toast.js": {"id": "DYN-003", "title": "Toast is not announced"}}}}
        delta, _, md = reaudit(ws, prev)
        assert delta["not_reported"] == ["no-status-message@src/toast.js"], delta
        assert delta["earlier"]["no-status-message@src/toast.js"]["title"] == "Toast is not announced" and "Toast is not announced" in md
        delta, merged, _ = reaudit(ws, prev, {"no-status-message@src/toast.js": "resolved"})        # and it can be settled like any other
        assert delta["resolved"] == ["no-status-message@src/toast.js"] and delta["not_reported"] == [] and not merged["problems"], (delta, merged["problems"])


def test_the_map_takes_two_earlier_findings_into_one_and_refuses_an_entry_for_what_matched_already():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("KBD-001", fingerprint="keyboard-inoperable@src/page.html"), finding("SEM-001", fingerprint="missing-h1@src/page.html")])
        old = [{"id": "KBD-004", "title": "Menu needs a mouse", "fingerprint": "keyboard-inoperable@src/page.html"},
               {"id": "SEM-002", "title": "No heading on Alerts", "fingerprint": "missing-heading@src/alerts.html"},
               {"id": "SEM-003", "title": "No heading on Agents", "fingerprint": "missing-heading@src/agents.html"}]
        delta, merged, md = reaudit(ws, old, {"missing-heading@src/alerts.html": "SEM-001", " Missing-Heading@src/agents.html ": "SEM-001"})
        assert delta["not_reported"] == [] and not merged["problems"], (delta, merged["problems"])
        assert "(earlier `missing-heading@src/agents.html`, `missing-heading@src/alerts.html`)" in md, md
        delta, merged, _ = reaudit(ws, old, {"keyboard-inoperable@src/page.html": "SEM-001"})
        assert any("needs no entry, KBD-001 of this run has that fingerprint" in p for p in merged["problems"]), merged["problems"]
        assert delta["matched"] == {}, delta


def test_an_earlier_audit_of_any_shape_does_not_stop_the_merge():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("KBD-001", fingerprint="keyboard-inoperable@src/page.html")])
        odd = [{"id": "A", "fingerprint": "a@x", "wcag": 5}, {"id": "B", "fingerprint": "b@x", "wcag": [{"sc": ["1"]}]},
               {"id": "C", "fingerprint": "c@x", "wcag": ["1.1.1"], "evidence": "somewhere"}, "a string", {"id": "D"}, {"id": "E", "fingerprint": 7}]
        delta, merged, _ = reaudit(ws, {"findings": odd, "delta": {"resolved": 5, "not_reported": "x", "earlier": []}})
        assert delta["not_reported"] == ["7", "a@x", "b@x", "c@x"] and delta["new"] == ["keyboard-inoperable@src/page.html"], delta


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
        # text where the IDs belong is no finding either
        _, said, _ = flows(ws, "| Read a chart | failed | long | the chart | the empty chart |")
        assert len(said) == 1 and "names no finding" in said[0], said
        # a finding that was merged into another one still counts, under the ID the persona knew it by
        (ws / "findings" / "_dedupe.json").write_text(json.dumps({"KBD-001": ["KBD-002"]}), encoding="utf-8")
        by, said, _ = flows(ws, "| Read a chart | failed | long | the chart | KBD-002 |")
        assert by["KBD-001"]["severity"] == "blocker" and not said, said
        (ws / "findings" / "_dedupe.json").unlink()


def test_a_flow_result_is_read_by_its_score_and_an_unknown_one_is_asked_about():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("KBD-001"), finding("KBD-002")])
        # a result that completed is no failure, whatever it mentions; the Dutch words are scores too
        by, said, _ = flows(ws, "| A | **completed** after one failed attempt | x | o | KBD-001 |", "| B | n/a (not tested, failed to load) | x | o | |",
                                "| C | **failed** | x | o | KBD-002 |", "| D | completed | x | o | |")
        assert by["KBD-001"]["severity"] == "serious" and by["KBD-002"]["severity"] == "blocker" and not said, (said, by)
        by, said, _ = flows(ws, "| A | mislukt | x | o | KBD-001 |", "| B | alleen met hulp | x | o | KBD-002 |")
        assert by["KBD-001"]["severity"] == "blocker" and by["KBD-002"]["severity"] == "critical" and not said, said
        _, said, _ = flows(ws, "| A | mislukt | x | o | |")
        assert len(said) == 1 and "names no finding" in said[0], said
        # a word that is none of the scores: the floor cannot know, and says so instead of passing
        _, said, _ = flows(ws, "| A | fehlgeschlagen | x | o | KBD-001 |")
        assert len(said) == 1 and "none of the six scores" in said[0] and "screen-reader-user.md" in said[0], said
        # the header row is not a result
        _, said, _ = flows(ws, "| A | completed | x | o | |", header="| Flow | Resultaat | Gevoel | Obstakel | Bevindingen |\n|---|---|---|---|---|\n")
        assert not said, said


def test_a_personas_own_finding_can_be_what_stopped_it():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("KBD-001")])
        (ws / "personas").mkdir()
        (ws / "personas" / "low-vision-user.md").write_text(
            "# Low vision\n\n## Flow results\n| Flow | Result | Feel | Main obstacle | Findings |\n|---|---|---|---|---|\n"
            "| Settings | failed | long | the menu opens off screen | PER-low-vision-001 |\n\n## New findings\n```json\n"
            + json.dumps([{"id": "PER-low-vision-001", "title": "The menu opens off screen", "severity": "serious", "visual_impact": "none",
                           "proposed_tier": 1, "location": "the header", "fix": {"summary": "Keep it in view."}}]) + "\n```\n\n## end\n", encoding="utf-8")
        merge(ws)
        merged = json.loads((ws / "findings" / "_merged.json").read_text())
        by = {f["id"]: f for f in merged["findings"]}
        assert by["PER-low-vision-001"]["severity"] == "blocker" and not [p for p in merged["problems"] if p.startswith("persona ")], merged["problems"]


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
        # not text: the report would print it as it stands
        (ws / "findings" / "orchestrator.json").write_text(json.dumps({"agent": "orchestrator", "findings": [finding("VIS-008", tier_rationale=["x"], **subtle)]}), encoding="utf-8")
        assert problems_of(ws, "VIS-008")[0], "a design impact that is a list was accepted"
        # a duplicate that was merged in keeps its words on what changes
        (ws / "findings" / "orchestrator.json").write_text(json.dumps({"agent": "orchestrator", "findings": [
            finding("VIS-001", **subtle), finding("VIS-002", tier_rationale="A darker border.", **subtle)]}), encoding="utf-8")
        (ws / "findings" / "_dedupe.json").write_text(json.dumps({"VIS-001": ["VIS-002"]}), encoding="utf-8")
        said, merged = problems_of(ws, "VIS-001")
        assert not said and merged["findings"][0]["tier_rationale"] == "A darker border.", (said, merged["findings"][0])


def test_a_note_for_another_lens_is_listed_until_a_finding_covers_it():
    note = lambda sc, where, **more: dict({"sc": sc, "location": where, "note": f"seen at {where}"}, **more)
    lens = lambda name, notes: {"agent": name, "findings": [], "cross_lens_notes": notes}
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("ORC-001")])                       # cites 2.1.1 in src/page.html
        files = {"semantics-structure.json": lens("semantics-structure", [
                     note("2.1.1", "src/page.html:3"),                       # that criterion in that file: covered
                     note("2.1.1", "./src/page.html (the menu)"),            # the same file, written another way
                     note("3.3.2", "src/page.html:3"),                       # the file, another criterion
                     note("2.1.1", "src/other.html:9"),                      # the criterion, another file
                     note("3.3.2", ""), "not a note"]),
                 "content-media.json": lens("content-media", [note("3.3.2", "src/page.html:3")])}
        for name, content in files.items():
            (ws / "findings" / name).write_text(json.dumps(content), encoding="utf-8")
        r = merge(ws)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip().endswith("; 4 cross-lens notes nobody filed"), r.stdout
        notes = json.loads((ws / "findings" / "_merged.json").read_text(encoding="utf-8"))["cross_lens_notes"]
        assert [n["filed_as"] for n in notes] == [[], ["ORC-001"], ["ORC-001"], [], [], []], notes   # content-media comes first
        md = (ws / "findings" / "_merged.md").read_text(encoding="utf-8")
        listed = md.split("## Cross-lens notes nobody filed (4)\n")[1].split("\n\n")[1].splitlines()
        assert [l.split(" · ")[0] + "@" + l.split(" · ")[1] for l in listed] == [
            "- 3.3.2@src/page.html:3", "- 3.3.2@src/page.html:3", "- 2.1.1@src/other.html:9", "- 3.3.2@"], listed
        assert listed[0].endswith("(content-media)") and listed[1].endswith("(semantics-structure)")
        assert "2 more cross-lens notes are covered" in md

        # the orchestrator files what two lenses noted: both notes are covered, and nothing is announced any more
        orc = ws / "findings" / "orchestrator.json"
        data = json.loads(orc.read_text(encoding="utf-8"))
        data["findings"].append(finding("ORC-002", wcag=[{"sc": "3.3.2", "name": "Labels or Instructions", "level": "A"}]))
        orc.write_text(json.dumps(data), encoding="utf-8")
        r = merge(ws)
        assert r.stdout.strip().endswith("; 2 cross-lens notes nobody filed"), r.stdout
        md = (ws / "findings" / "_merged.md").read_text(encoding="utf-8")
        assert "nobody filed (2)" in md and "4 more cross-lens notes are covered" in md

        # an accepted exception on that criterion in that file is not somebody filing the note
        data["findings"][1]["fix"] = {"ownership": "accepted", "summary": "Left as it is.", "exception": {"reason": "By design."}}
        orc.write_text(json.dumps(data), encoding="utf-8")
        r = merge(ws)
        assert r.stdout.strip().endswith("; 4 cross-lens notes nobody filed"), r.stdout

    with tempfile.TemporaryDirectory() as d:                                 # no note at all: no heading, no count
        ws = claims_workspace(d, [finding("ORC-001")])
        r = merge(ws)
        assert "cross-lens" not in r.stdout and "Cross-lens" not in (ws / "findings" / "_merged.md").read_text(encoding="utf-8")


def test_the_maximizer_filing_what_another_finding_has_is_asked_about():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("ORC-001")])                       # 2.1.1 in src/page.html
        other = [{"sc": "4.1.2", "name": "Name, Role, Value", "level": "A"}]
        fwk = lambda fid, **over: finding(fid, **dict({"fingerprint": f"{fid.lower()}@src/page.html"}, **over))
        tooling = fwk("FWK-005", kind="leverage", wcag=[], title="No lint layer",          # fails no criterion, fixes nothing yet
                      leverage={"finding_ids": [], "note": "Keeps it from coming back."})
        mx = ws / "findings" / "framework-maximizer.json"
        nameless = fwk("FWK-006"); del nameless["id"]                         # the merge names it after its file, not FWK
        mx.write_text(json.dumps({"agent": "framework-maximizer", "findings": [
            fwk("FWK-001"),                                                   # the same criterion in the same file
            fwk("FWK-002", wcag=other),                                       # the file, another criterion
            fwk("FWK-003", kind="leverage", leverage={"finding_ids": ["ORC-001"]}),
            fwk("FWK-004"), tooling, nameless]}), encoding="utf-8")           # a second one on that criterion and file
        # a lens cannot get a defect past the criterion check by calling it a leverage entry
        (ws / "findings" / "content-media.json").write_text(json.dumps({"agent": "content-media", "findings": [
            finding("CNT-001", kind="leverage", wcag=[], fingerprint="cnt-001@src/page.html")]}), encoding="utf-8")
        r = merge(ws)
        merged = json.loads((ws / "findings" / "_merged.json").read_text(encoding="utf-8"))
        asked = [p for p in merged["problems"] if "the framework-maximizer filed" in p]
        assert sorted(p.split(":")[0] for p in asked) == ["FRA-x06", "FWK-001", "FWK-004"], merged["problems"]
        assert all("that ORC-001 already has" in p for p in asked), asked                       # its own kind is not a twin
        assert sorted(f["id"] for f in merged["findings"]) == ["FRA-x06", "FWK-001", "FWK-002", "FWK-004", "ORC-001"], merged["findings"]
        assert [(e["id"], e["resolves"]) for e in merged["leverage_entries"]] == [("FWK-003", ["ORC-001"]), ("CNT-001", []), ("FWK-005", [])]
        assert [p for p in merged["problems"] if "no WCAG criterion" in p] == [
            "CNT-001: no WCAG criterion and not marked best_practice_only; cite one or set the marker"], merged["problems"]

        # named a duplicate, or made a leverage entry: nothing is left to ask
        (ws / "findings" / "_dedupe.json").write_text(json.dumps({"ORC-001": ["FWK-001"]}), encoding="utf-8")
        data = json.loads(mx.read_text(encoding="utf-8"))
        data["findings"][3].update(kind="leverage", leverage={"finding_ids": ["ORC-001"]})
        moved = data["findings"].pop()                                        # another problem after all: the orchestrator's now
        mx.write_text(json.dumps(data), encoding="utf-8")
        orc = ws / "findings" / "orchestrator.json"
        mine = json.loads(orc.read_text(encoding="utf-8"))
        mine["findings"].append(dict(moved, id="ORC-002"))
        orc.write_text(json.dumps(mine), encoding="utf-8")
        merge(ws)
        merged = json.loads((ws / "findings" / "_merged.json").read_text(encoding="utf-8"))
        assert not [p for p in merged["problems"] if "the framework-maximizer filed" in p], merged["problems"]
        assert sorted(f["id"] for f in merged["findings"]) == ["FWK-002", "ORC-001", "ORC-002"], [f["id"] for f in merged["findings"]]

    with tempfile.TemporaryDirectory() as d:                                 # an accepted exception is nobody's finding to repeat
        ws = claims_workspace(d, [finding("ORC-001", fix={"ownership": "accepted", "summary": "Left.", "exception": {"reason": "By design."}})])
        (ws / "findings" / "framework-maximizer.json").write_text(json.dumps({"agent": "framework-maximizer", "findings": [
            finding("FWK-001", fingerprint="fwk-001@src/page.html")]}), encoding="utf-8")
        merge(ws)
        merged = json.loads((ws / "findings" / "_merged.json").read_text(encoding="utf-8"))
        assert not [p for p in merged["problems"] if "the framework-maximizer filed" in p], merged["problems"]


def test_a_lens_that_stayed_out_of_a_running_app_is_named():
    lens = lambda name, method=None, lenses=None: dict({"agent": name, "findings": []}, **({"lenses": lenses} if lenses else {}),
                                                       **({"coverage": {"method": method}} if method else {}))
    files = {"forms-input.json": lens("forms-input", "static"), "keyboard-focus.json": lens("keyboard-focus", "both"),
             "visual-perception.json": lens("visual-perception", "Static + Runtime"), "dynamic-content.json": lens("dynamic-content"),
             "structure-content.json": lens("structure-content", "static", ["semantics-structure", "content-media"]),
             "operate.json": lens("operate", "static", ["keyboard-focus", "dynamic-content", "forms-input"]),
             "bad-coverage.json": dict(lens("bad-coverage", lenses=["keyboard-focus"]), coverage="static")}   # not an object
    with tempfile.TemporaryDirectory() as d:
        ws = workspace(d, files)
        r = merge(ws)                                                         # no scan ran: nobody could have used a runtime
        assert "static-only" not in r.stdout and json.loads((ws / "findings" / "_merged.json").read_text())["static_only_lenses"] == []
        (ws / "automated").mkdir()
        (ws / "automated" / "summary.json").write_text("[]", encoding="utf-8")
        r = merge(ws)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip().endswith("; 4 lenses static-only with a runtime there"), r.stdout
        named = json.loads((ws / "findings" / "_merged.json").read_text(encoding="utf-8"))["static_only_lenses"]
        assert [(n["agent"], n["method"]) for n in named] == [("bad-coverage", None), ("dynamic-content", None),
                                                              ("forms-input", "static"), ("operate", "static")], named
        assert named[3]["lenses"] == ["dynamic-content", "forms-input", "keyboard-focus"], named[3]
        md = (ws / "findings" / "_merged.md").read_text(encoding="utf-8")
        assert "## Worked from the code only, with a runtime there (4)" in md
        assert "- forms-input (forms-input): coverage.method is static" in md
        assert "- operate (dynamic-content, forms-input, keyboard-focus): coverage.method is static" in md
        assert "- dynamic-content (dynamic-content): coverage.method is not given" in md


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
