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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("all merge checks passed")
