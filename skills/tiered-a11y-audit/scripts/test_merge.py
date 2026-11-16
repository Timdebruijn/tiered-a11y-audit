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
        ])
        r = merge(ws)
        merged = json.loads((ws / "findings" / "_merged.json").read_text())
        assert merged["problems"] == [], f"correct findings were flagged: {merged['problems']}"


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
        "triple-A criterion only": (finding("BAD-005", wcag=[{"sc": "2.4.9", "name": "Link Purpose (Link Only)", "level": "AAA"}]),
                                    "not a WCAG 2.2 level A or AA criterion"),
        "no criterion and no best-practice marker": (finding("BAD-006", wcag=[]), "not marked best_practice_only"),
        "contrast ratio from memory": (finding("BAD-007", colours={"fg": "#9a9a9a", "bg": "#ffffff", "ratio": 3.9, "required": 4.5}),
                                       "measures 2.81"),
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


def test_level_and_ratio_are_corrected_in_the_output():
    with tempfile.TemporaryDirectory() as d:
        ws = claims_workspace(d, [finding("FIX-001", wcag=[{"sc": "2.4.4", "name": "Link purpose", "level": "AAA"}],
                                          colours={"fg": "#9a9a9a", "bg": "#ffffff", "ratio": 4.9, "required": 4.5})])
        mine, merged = problems_of(ws, "FIX-001")
        f = merged["findings"][0]
        assert f["wcag"][0] == {"sc": "2.4.4", "name": "Link Purpose (In Context)", "level": "A"}, f["wcag"]
        assert f["colours"]["ratio"] == 2.81, f["colours"]
        assert any("level AAA, it is level A" in p for p in mine), mine


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("all merge checks passed")
