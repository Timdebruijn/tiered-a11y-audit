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
sys.path.insert(0, str(HERE))
from lint_report import lint  # noqa: E402


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


LAST_WS = None        # the workspace of the latest run() that built one


def run(findings, lang="en", ws=None, extra=None, personas=None):
    if ws is not None:
        r = subprocess.run([sys.executable, str(HERE / "render_report_parts.py"), str(ws), "--lang", lang], capture_output=True, text=True)
        draft = (ws / "REPORT.draft.md").read_text(encoding="utf-8") if (ws / "REPORT.draft.md").exists() else ""
        return r, draft, ws
    global LAST_WS
    d = tempfile.mkdtemp()
    ws = LAST_WS = Path(d) / ".a11y-audit"
    (ws / "findings").mkdir(parents=True)
    (Path(d) / "src").mkdir()
    (Path(d) / "src" / "page.html").write_text("<main>\n<div onclick>\n</div>\n", encoding="utf-8")
    (ws / "findings" / "experts.json").write_text(json.dumps({"agent": "experts", "positives": ["One main landmark."],
                                                             "findings": findings, **(extra or {})}), encoding="utf-8")
    for name, text in (personas or {}).items():
        (ws / "personas").mkdir(exist_ok=True)
        (ws / "personas" / f"{name}.md").write_text(text, encoding="utf-8")
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
        _, draft, ids = run(FINDINGS, lang)
        rules = {rule for _, rule, _ in lint(draft, ids)}       # the linter that the finished report has to pass
        assert rules == {"unwritten"}, f"{lang}: the draft breaks the read-aloud rules by itself: {rules}"


def test_a_tier_without_findings_says_none_instead_of_a_symbol():
    _, draft, _ = run([FINDINGS[0]])
    assert "| 2 | 0 | none | none |" in draft and "| 3 | 0 | none | none |" in draft, "an empty tier leaves a symbol-only cell"


def test_a_contrast_with_a_colon_is_put_into_words_and_code_is_left_alone():
    f = finding("KBD-009", title="Grey text at 2.81:1", description="The ratio is 2.81:1 where 4.5:1 is needed; see `ratio(4.5:1)` and file.css:12:1.",
                verify="Measure 4,5:1 or better.")
    for lang, to in (("en", "to"), ("nl", "op")):
        _, draft, ids = run([f], lang)
        assert f"Grey text at 2.81 {to} 1" in draft and f"The ratio is 2.81 {to} 1 where 4.5 {to} 1 is needed" in draft, f"{lang}: ratio left with a colon"
        assert f"Measure 4,5 {to} 1 or better." in draft, f"{lang}: a decimal comma is a ratio too"
        assert "`ratio(4.5:1)`" in draft and "file.css:12:1" in draft, f"{lang}: code or a line and column reference was rewritten"
        assert not [m for _, rule, m in lint(draft, ids) if "ratio" in m], f"{lang}: the linter still finds a ratio"


def test_agent_text_outside_the_finding_blocks_is_put_into_words_too():
    accepted = finding("KBD-010", fix={"ownership": "accepted", "summary": "None.", "exception": {"tool": "axe", "rule": "x", "selector": "#a",
                                                                                              "reason": "A ratio of 3:1 is allowed here."}})
    cov = {"lenses": ["keyboard-focus"], "sc_coverage": {"2.1.2": {"status": "pass", "note": "Ring measures 3.2:1."}}}
    _, draft, _ = run([accepted, finding("KBD-011", description="\u30b3\u30f3\u30c8\u30e9\u30b9\u30c8\u6bd44.5:1\u3067\u3059, at 12:15, on a 16:9 screen.")], extra=cov)
    assert "A ratio of 3 to 1 is allowed here." in draft, "the reason of an accepted exception kept its colon"
    assert "Ring measures 3.2 to 1." in draft, "a coverage note kept its colon"
    assert "\u6bd44.5 to 1\u3067\u3059" in draft, "a ratio next to kana or kanji was not recognised"
    assert "at 12:15, on a 16:9 screen" in draft, "a time or an aspect ratio was rewritten"


def test_the_flow_table_of_a_persona_is_read_by_position_not_by_english_words():
    persona = ("# Schermlezer\n\n## Flow results\n| Taak | Resultaat | Gevoel | Obstakel |\n|---|---|---|---|\n"
               "| Flow bestellen | failed | traag | Knop zonder naam |\n| Contact | completed | vlot | geen |\n\n## In my own words\nTekst.\n")
    _, draft, _ = run(FINDINGS, "nl", personas={"screen-reader-user": persona})
    assert "| Taak | screen-reader |" not in draft, "the translated header row became a result row"
    assert "| Flow bestellen | screen-reader | mislukt | Knop zonder naam |" in draft, "a flow whose name starts with Flow was dropped"
    assert "| Contact | screen-reader | voltooid | geen |" in draft


PERSONA = ("# Screen reader user\n\n## Flow results\n| Flow | Result | Feel | Main obstacle |\n|---|---|---|---|\n"
           "| Contact | failed | slow | KBD-001 |\n\n## In my own words\nI could not send the form.\n\n## Top 3 frustrations\n1. The button.\n")


def write_prose(ws, texts):
    (ws / "report-prose.md").write_text("<!-- a hint that must not reach the report -->\n\n"
                                        + "".join(f"=== {k} ===\n<!-- hint -->\n{v}\n\n" for k, v in texts.items()), encoding="utf-8")


def test_the_report_is_assembled_from_the_prose_file_and_never_edited_by_hand():
    r, draft, ids = run(FINDINGS, "en", personas={"screen-reader-user": PERSONA})
    ws = LAST_WS
    prose_file = ws / "report-prose.md"
    keys = re.findall(r"(?m)^=== (.+) ===$", prose_file.read_text(encoding="utf-8"))
    assert keys == ["in-short", "summary", "top5-closing", "works-well", "tier3", "persona-screen-reader-user", "advice-tooling", "method", "legal"], keys
    assert all(f"[{k}]" in draft for k in keys), "a gap in the draft does not name its key"
    assert not (ws / "REPORT.md").exists() and "report-prose.md created" in r.stdout, "a report was written before anyone wrote its prose"

    t3 = next(rid for rid, m in ids.items() if m["tier"] == 3)
    texts = {k: f"Text for {k}." for k in keys if k != "legal"}
    texts["works-well"] = "- The one positive that was chosen."
    texts["tier3"] = f"### Design\n\n- {t3}: redo it, for everyone, a week."
    write_prose(ws, texts)
    r, _, _ = run(None, "en", ws)
    report = (ws / "REPORT.md").read_text(encoding="utf-8")
    assert "every gap has its text" in r.stdout, r.stdout
    assert "<!--" not in report, "a comment or an unfilled gap reached the report"
    for k, v in texts.items():
        assert v in report, f"the text for {k} is not in the report"
    assert "- One main landmark." not in report and "Title of CNT-001 (serious; small)" not in report, "the list to choose from was kept next to the choice"
    assert "Legal context" not in report, "an optional block without text kept its heading"
    for rid, meta in ids.items():
        if meta["tier"] != 3:
            assert block_of(report, rid) == block_of(draft, rid), f"{rid}: the finding block changed between draft and report"
    assert lint(report, ids) == [], lint(report, ids)

    texts["summary"], texts["legal"] = "", "The public sector rules apply."
    write_prose(ws, texts)
    r, _, _ = run(None, "en", ws)
    report = (ws / "REPORT.md").read_text(encoding="utf-8")
    assert "still to write: summary" in r.stdout and "<!-- WRITE: [summary]" in report, "an empty section did not stay a gap"
    unwritten = [m for _, rule, m in lint(report, ids) if rule == "unwritten"]
    assert len(unwritten) == 1 and unwritten[0].startswith("still to write: [summary]"), unwritten
    assert "### D. Legal context\n\nThe public sector rules apply." in report


def test_the_prose_file_is_only_ever_added_to():
    run(FINDINGS, "en", personas={"screen-reader-user": PERSONA})
    ws = LAST_WS
    write_prose(ws, {"in-short": "My own words, which took an hour."})
    (ws / "personas" / "low-vision-user.md").write_text(PERSONA.replace("Screen reader", "Low vision"), encoding="utf-8")
    r, _, _ = run(None, "en", ws)
    text = (ws / "report-prose.md").read_text(encoding="utf-8")
    assert text.startswith("<!-- a hint that must not reach the report -->") and "My own words, which took an hour." in text, "written prose was overwritten"
    assert text.count("=== in-short ===") == 1 and "=== persona-low-vision-user ===" in text and "=== summary ===" in text, "missing sections were not added"
    assert "new sections were added" in r.stdout
    before = text
    run(None, "en", ws)
    assert (ws / "report-prose.md").read_text(encoding="utf-8") == before, "a run with nothing new changed the prose file"


def test_a_prose_file_that_would_put_the_wrong_text_in_the_report_is_refused():
    run(FINDINGS, "en")
    ws = LAST_WS
    write_prose(ws, {"in-short": "The first version."})
    run(None, "en", ws)
    first = (ws / "REPORT.md").read_text(encoding="utf-8")
    assert "The first version." in first
    for label, texts, word in (("a line of prose that looks like a marker", {"in-short": "Start.\n=== note ===\nThe rest, which would vanish."}, "note"),
                               ("a key with a typo", {"in-short": "Fine.", "sumary": "Lost."}, "sumary")):
        write_prose(ws, texts)
        r, _, _ = run(None, "en", ws)
        assert r.returncode != 0 and word in r.stderr and "REPORT.md was not written" in r.stderr, f"{label}: {r.returncode} {r.stderr}"
        assert (ws / "REPORT.md").read_text(encoding="utf-8") == first, f"{label}: a report was written anyway"
    (ws / "report-prose.md").write_text("=== summary ===\nThe real one.\n\n=== summary ===\n\n", encoding="utf-8")
    r, _, _ = run(None, "en", ws)
    assert r.returncode != 0 and "summary more than once" in r.stderr, r.stderr


def test_a_report_is_left_alone_until_some_prose_is_written():
    run(FINDINGS, "en")
    ws = LAST_WS
    (ws / "REPORT.md").write_text("A report someone made by hand, before this file existed.\n", encoding="utf-8")
    r, _, _ = run(None, "en", ws)                      # the prose file exists now, with every section still empty
    assert (ws / "REPORT.md").read_text(encoding="utf-8").startswith("A report someone made by hand"), "an existing report was replaced by a draft full of gaps"
    assert "has no text yet" in r.stdout and r.returncode == 0, r.stdout


def test_new_sections_land_on_their_own_line_and_odd_persona_names_get_a_usable_key():
    spaced = PERSONA.replace("Screen reader", "Low vision")
    run(FINDINGS, "en", personas={"low vision user": spaced})
    ws = LAST_WS
    assert "=== persona-low-vision-user ===" in (ws / "report-prose.md").read_text(encoding="utf-8"), "a space in a file name made a key no marker line can hold"
    (ws / "report-prose.md").write_text("=== in-short ===\nNo newline after this", encoding="utf-8")
    for _ in range(3):
        run(None, "en", ws)
    text = (ws / "report-prose.md").read_text(encoding="utf-8")
    assert "No newline after this\n=== summary ===" in text, "a new section was glued to the last line of the text before it"
    assert text.count("=== summary ===") == 1 and text.count("=== persona-low-vision-user ===") == 1, "sections were added again on a later run"
    assert "No newline after this\n" in (ws / "REPORT.md").read_text(encoding="utf-8") and "===" not in (ws / "REPORT.md").read_text(encoding="utf-8")


def test_a_tier_without_findings_still_asks_for_the_standing_advice():
    _, draft, _ = run([FINDINGS[0]])
    assert "[tier3] no finding landed in this tier" in draft and "sort the items into five H3 blocks" not in draft


def test_the_draft_no_longer_asks_for_a_translation():
    _, draft, _ = run(FINDINGS, "nl")
    assert "translate the finding text" not in draft and "the agents wrote it in the report language" in draft
    assert "translated" not in draft.split("-->", 1)[1], "a gap further down still asks for a translation"


def test_dutch_uses_one_word_per_severity():
    _, draft, ids = run(FINDINGS, "nl")
    assert "| blokkerend |" in draft and "Ernst blokkerend," in draft, "table and block disagree on the severity word"
    assert "| serious |" not in draft and "| blocker |" not in draft


def test_a_finding_without_a_tier_is_reported_not_dropped():
    r, draft, _ = run(FINDINGS + [finding("KBD-009", visual_impact="huge", proposed_tier="T9")])
    assert r.returncode == 1, "a finding that is in no table must fail the run"
    assert "KBD-009" in r.stderr, r.stderr


def translate(x):
    """Stand-in for a real translation: every value changes, every {placeholder} survives."""
    if isinstance(x, dict):
        return {k: translate(v) for k, v in x.items()}
    if isinstance(x, list):
        return [translate(v) for v in x]
    return "Ü " + x


def test_any_language_works_after_one_translation():
    d = tempfile.mkdtemp()
    ws = Path(d) / ".a11y-audit"
    (ws / "findings").mkdir(parents=True)
    (Path(d) / "src").mkdir()
    (Path(d) / "src" / "page.html").write_text("<main>\n<div onclick>\n</div>\n", encoding="utf-8")
    (ws / "findings" / "experts.json").write_text(json.dumps({"agent": "experts", "findings": FINDINGS}), encoding="utf-8")
    subprocess.run([sys.executable, str(HERE / "merge_findings.py"), str(ws), "--ownership", str(OWNERSHIP)], capture_output=True, check=True)

    first, _, _ = run(None, "de", ws)             # a language the skill does not ship
    labels = ws / "report-labels.de.json"
    assert first.returncode == 2 and labels.exists(), "an unknown language must stop and hand over a labels file"
    assert "translate" in first.stderr.lower()

    data = json.loads(labels.read_text(encoding="utf-8"))
    labels.write_text(json.dumps(translate({k: v for k, v in data.items() if not k.startswith("_")}), ensure_ascii=False), encoding="utf-8")
    second, draft, _ = run(None, "de", ws)
    assert second.returncode == 0, second.stderr
    assert "## Ü In short" in draft and "| Ü serious |" in draft and "Ü Problem:" in draft, "translated labels are not what the draft uses"

    broken = translate({k: v for k, v in data.items() if not k.startswith("_")})
    broken["ann_tier"] = "no placeholder left"
    del broken["f_problem"]
    labels.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
    third, _, _ = run(None, "de", ws)
    assert third.returncode == 2 and "f_problem" in third.stderr and "ann_tier" in third.stderr, third.stderr


def test_shipped_languages_match_the_english_source():
    sys.path.insert(0, str(HERE))
    from labels import SHIPPED, check
    source = json.loads((SHIPPED / "en.json").read_text(encoding="utf-8"))
    shipped = sorted(SHIPPED.glob("*.json"))
    assert len(shipped) >= 2
    for path in shipped:
        problems = check(json.loads(path.read_text(encoding="utf-8")), source)
        assert not problems, f"{path.name}: {problems}"


def test_a_language_code_cannot_leave_the_workspace():
    r, _, _ = run(None, "../../etc/x", Path(tempfile.mkdtemp()))
    assert r.returncode != 0 and "language code" in r.stderr, r.stderr


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("all render checks passed")
