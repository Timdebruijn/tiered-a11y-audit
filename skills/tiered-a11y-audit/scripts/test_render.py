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
    tag = fid.lower()            # not the ID itself: an ID in the text of a finding becomes the ID of the report
    f = {"id": fid, "fingerprint": f"{tag}@src/page.html", "title": f"Title of {tag}", "description": f"Problem text of {tag}.",
         "severity": "serious", "evidence": [{"file": "src/page.html", "lines": "2-3", "snippet": "<div onclick>"}],
         "wcag": [{"sc": "2.1.1"}], "affected_users": ["screen-reader"], "visual_impact": "none", "proposed_tier": 1,
         "fix": {"ownership": "project", "summary": f"Fix text of {tag}.", "location": "src/page.html",
                 "code_before": f"<before-{fid}>", "code_after": f"<after-{fid}>", "side_effects": "Check the styles."},
         "effort": "S", "confidence": "high", "verify": f"Verify text of {tag}."}
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
        src = meta["source"][0].lower()
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
    for lang, to in (("en", "to"), ("nl", "tot")):
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
    assert "| Taak | Schermlezer |" not in draft, "the translated header row became a result row"
    assert "| Flow bestellen | Schermlezer | mislukt | Knop zonder naam |" in draft, "a flow whose name starts with Flow was dropped"
    assert "| Contact | Schermlezer | voltooid | geen |" in draft


def test_the_flow_table_names_a_persona_as_the_report_does_below_it():
    named = PERSONA.replace("# Screen reader user", "# Sanne \u2014 schermlezergebruiker, blind, expert")
    _, draft, _ = run(FINDINGS, "nl", personas={"screen-reader-user": named, "low-vision-user": PERSONA.split("\n", 1)[1]})
    assert "| Contact | Sanne | mislukt |" in draft and "### Sanne, schermlezergebruiker, blind, expert" in draft, "table and heading name the persona differently"
    assert "| Contact | low-vision | mislukt |" in draft, "a persona file without a title lost its rows or its name"


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
    assert "- One main landmark." not in report and "Title of cnt-001 (serious; small)" not in report, "the list to choose from was kept next to the choice"
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


def test_written_prose_is_kept_and_sections_that_are_new_are_added():
    run(FINDINGS, "en", personas={"screen-reader-user": PERSONA})
    ws = LAST_WS
    mine = "My own words, which took an hour.\n\n<!-- my own note, further down -->\n\n```\n=== not a key, it is indented\n```\n   A last line."
    write_prose(ws, {"in-short": mine.replace("=== not", " === not"), "summary": "<!-- my own note, above my text -->\nThe summary.",
                     "method": "<!-- a note and no text yet -->"})
    (ws / "personas" / "low-vision-user.md").write_text(PERSONA.replace("Screen reader", "Low vision"), encoding="utf-8")
    r, _, _ = run(None, "en", ws)
    assert r.returncode == 0, r.stderr
    text = (ws / "report-prose.md").read_text(encoding="utf-8")
    assert text.startswith("<!-- a hint that must not reach the report -->"), "what stood above the first section was replaced"
    assert mine.replace("=== not", " === not") in text, "written prose was changed"
    assert "<!-- my own note, above my text -->\nThe summary." in text and "<!-- a note and no text yet -->" in text, "a comment of the orchestrator's own was taken for the hint"
    assert "The hint of in-short, summary is not the one" in r.stdout, "a section with a note and no text is called out of date, or one with text is not: " + r.stdout
    assert text.count("=== in-short ===") == 1 and "=== persona-low-vision-user ===" in text and "=== top5-closing ===" in text, "missing sections were not added"
    assert "new sections were added" in r.stdout
    keys = re.findall(r"(?m)^=== (.+) ===$", text)
    assert keys.index("persona-low-vision-user") < keys.index("persona-screen-reader-user") < keys.index("method"), "sections are not in the order of the report"
    before = text
    run(None, "en", ws)
    assert (ws / "report-prose.md").read_text(encoding="utf-8") == before, "a run with nothing new changed the prose file"


def test_a_prose_file_that_is_not_utf8_is_left_as_it_is():
    run(FINDINGS, "en")
    ws = LAST_WS
    raw = b"=== in-short ===\n<!-- an old hint -->\nCaf\xe9 voor iedereen.\n"
    (ws / "report-prose.md").write_bytes(raw)
    r, _, _ = run(None, "en", ws)
    assert (ws / "report-prose.md").read_bytes() == raw, "a letter that could not be read was written back as a replacement sign"
    assert "not saved as UTF-8" in r.stderr, r.stderr


def test_a_hint_is_written_again_when_the_findings_behind_it_change():
    run([FINDINGS[0]], "en")                               # nothing in tier 3 yet
    ws = LAST_WS
    prose_file = ws / "report-prose.md"
    first = prose_file.read_text(encoding="utf-8")
    assert "no finding landed in this tier" in first
    text = first
    hint_end = text.index("-->", text.index("=== tier3 ===")) + 3
    prose_file.write_text(text[:hint_end] + "\n- Test with people who use a screen reader.\n" + text[hint_end:], encoding="utf-8")
    (ws / "findings" / "experts.json").write_text(json.dumps({"agent": "experts", "findings": [FINDINGS[0], FINDINGS[5]]}), encoding="utf-8")
    m = subprocess.run([sys.executable, str(HERE / "merge_findings.py"), str(ws), "--ownership", str(OWNERSHIP)], capture_output=True, text=True)
    assert m.returncode == 0, m.stderr
    r, _, _ = run(None, "en", ws)
    assert r.returncode == 0, r.stderr
    text = prose_file.read_text(encoding="utf-8")
    section = text.split("=== tier3 ===")[1].split("\n=== ")[0]
    assert "no finding landed in this tier" not in text, "the hint still describes the findings of the run before"
    assert "=== works-well ===" not in text, "an empty section for a gap that is gone (the positives) was kept, and would be refused"
    assert "sort the items into five H3 blocks" in section and "- T3-01: Title of cnt-001" in section, section
    assert section.rstrip().endswith("- Test with people who use a screen reader."), "the text under the hint was lost or moved"
    assert "The hint of tier3 is not the one its text was written under" in r.stdout, r.stdout
    r, _, _ = run(None, "en", ws)
    assert "is not the one its text was written under" not in r.stdout, "a hint that did not change again is still called changed"


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
        as_written = (ws / "report-prose.md").read_text(encoding="utf-8")
        r, _, _ = run(None, "en", ws)
        assert r.returncode != 0 and word in r.stderr and "REPORT.md was not written" in r.stderr, f"{label}: {r.returncode} {r.stderr}"
        assert (ws / "report-prose.md").read_text(encoding="utf-8") == as_written, f"{label}: a prose file that was refused was written again all the same"
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
    assert "No newline after this\n\n=== summary ===" in text, "a new section was glued to the last line of the text before it"
    assert text.count("=== summary ===") == 1 and text.count("=== persona-low-vision-user ===") == 1, "sections were added again on a later run"
    assert "No newline after this\n" in (ws / "REPORT.md").read_text(encoding="utf-8") and "===" not in (ws / "REPORT.md").read_text(encoding="utf-8")


def test_a_tier_without_findings_still_asks_for_the_standing_advice():
    _, draft, _ = run([FINDINGS[0]])
    assert "[tier3] no finding landed in this tier" in draft and "sort the items into five H3 blocks" not in draft


def test_the_draft_no_longer_asks_for_a_translation():
    _, draft, _ = run(FINDINGS, "nl")
    assert "translate the finding text" not in draft and "the agents wrote it in the report language" in draft
    assert "translated" not in draft.split("-->", 1)[1], "a gap further down still asks for a translation"


def test_a_re_audit_lists_what_nobody_filed_again_apart_from_what_is_resolved_and_by_its_title():
    run([finding("KBD-001")])
    ws = LAST_WS
    prev = ws.parent / "previous" / "findings"
    prev.mkdir(parents=True)
    prev.joinpath("_merged.json").write_text(json.dumps([
        {"id": "KBD-004", "title": "Menu needs a mouse", "fingerprint": "kbd-001@src/page.html"},
        {"id": "SEM-002", "title": "No main heading, like KBD-001 then", "fingerprint": "missing-heading@src/page.html"},
        {"id": "DYN-003", "title": "Toast is not announced", "fingerprint": "no-status-message@src/toast.js"}]), encoding="utf-8")
    (ws / "findings" / "_delta-map.json").write_text(json.dumps({"no-status-message@src/toast.js": "resolved"}), encoding="utf-8")
    m = subprocess.run([sys.executable, str(HERE / "merge_findings.py"), str(ws), "--ownership", str(OWNERSHIP), "--previous", str(prev.parent)], capture_output=True, text=True)
    assert m.returncode == 0, m.stderr
    for lang, heads in (("en", ("### Resolved (1)", "### Not reported again (1)", "### Still open (1)")), ("nl", ("### Opgelost (1)", "### Niet opnieuw gemeld (1)", "### Nog open (1)"))):
        r, draft, _ = run(None, lang=lang, ws=ws)
        assert r.returncode == 0, r.stderr
        for h in heads:
            assert h in draft, (h, draft[:1500])
        resolved = draft.split(heads[0])[1].split("###")[0]
        unreported = draft.split(heads[1])[1].split("###")[0]
        assert "- Toast is not announced" in resolved and "No main heading" not in resolved, resolved
        assert "- No main heading, like KBD-001 then" in unreported, "an ID of the earlier audit was given to a finding of this one: " + unreported
        assert "missing-heading@" not in draft and "no-status-message@" not in draft, "a fingerprint is not a line a reader can use"
        assert "- T1-01: Title of kbd-001" in draft.split(heads[2])[1].split("###")[0]


def test_a_path_without_an_extension_still_passes_the_linter():
    """A directory, a folder of content or a selector has no file extension, so the linter reads it as a word with a
    slash in it and refuses the report. Every place where the renderer prints one has to put it in a code span: the fix
    line of a finding, the upstream and the accepted list, the structural advice, appendix C, and the fingerprint of a
    finding of the earlier audit that nobody gave a title."""
    upstream = finding("SEM-001", fix={"ownership": "upstream", "summary": "The theme does it.", "location": "themes/paper"})
    accepted = finding("VIS-002", fix={"ownership": "accepted", "summary": "Kept as it is.", "location": "assets/css",
                                       "exception": {"tool": "axe", "rule": "color-contrast", "selector": "main > .quote", "reason": "Decorative only."}})
    whole = finding("VIS-003", fix={"ownership": "accepted", "summary": "Kept as it is.", "location": "assets/css",
                                    "exception": {"tool": "axe", "rule": "region", "reason": "The whole page."}})
    lever = finding("FWK-001", kind="leverage", wcag=[], title="One layout for every page",
                    leverage={"finding_ids": ["KBD-001"], "note": "One place.", "location": "layouts/_default"},
                    fix={"ownership": "project", "summary": "Edit the layout.", "location": "layouts/_default"})
    here = finding("CNT-001", fingerprint="index-without-summary@content/projects",
                   evidence=[{"file": "content/projects", "lines": ""}], fix={"ownership": "project", "summary": "Add a summary.", "location": "content/projects"})
    run([finding("KBD-001"), upstream, accepted, whole, lever, here], personas={"screen-reader-user": PERSONA})
    ws = LAST_WS
    prev = ws.parent / "previous" / "findings"
    prev.mkdir(parents=True)
    # the earlier audit as the first version of this skill wrote it: a fingerprint and no title to read aloud instead
    prev.joinpath("_merged.json").write_text(json.dumps({"findings": [{"id": "SEM-009", "fingerprint": "index-without-summary@content/pages"}]}), encoding="utf-8")
    (ws / "findings" / "_delta-map.json").write_text(json.dumps({"index-without-summary@content/pages": "resolved"}), encoding="utf-8")
    m = subprocess.run([sys.executable, str(HERE / "merge_findings.py"), str(ws), "--ownership", str(OWNERSHIP), "--previous", str(prev.parent)], capture_output=True, text=True)
    assert m.returncode == 0, m.stderr
    r, draft, _ = run(None, "en", ws)
    assert r.returncode == 0, r.stderr
    ids = json.loads((ws / "report-ids.json").read_text(encoding="utf-8"))
    assert "- `index-without-summary@content/pages`" in draft, "a bare fingerprint of the earlier audit is in the report"
    rid = {meta["source"][0]: r for r, meta in ids.items()}
    assert "(at `content/projects`)" in draft and f"- {rid['SEM-001']}: `themes/paper`" in draft, draft
    assert "(axe `color-contrast`, `main > .quote`)" in draft, "a tool rule or a selector is not in a code span"
    assert "(axe `region`):" in draft, "an exception that was taken for the whole page named a selector it does not have"
    assert "| `layouts/_default` |" in draft and "| `content/projects` |" in draft, "a place in a table is not in a code span"
    assert {rule for _, rule, _ in lint(draft, ids)} == {"unwritten"}, lint(draft, ids)

    keys = re.findall(r"(?m)^=== (.+) ===$", (ws / "report-prose.md").read_text(encoding="utf-8"))
    texts = {k: f"Text for {k}." for k in keys if k != "legal"}
    texts["works-well"] = "- The one positive that was chosen."
    texts["tier3"] = "- Test with disabled users once a quarter."
    write_prose(ws, texts)
    run(None, "en", ws)
    r = subprocess.run([sys.executable, str(HERE / "lint_report.py"), str(ws / "REPORT.md"), "--workspace", str(ws)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_cell_is_never_cut_inside_a_code_span():
    from render_report_parts import clip
    assert clip("see `src/app/page.tsx` there", 12) == "see `src/app`", "a span cut open was not closed"
    assert clip("see `src/app/page.tsx` there", 5) == "see", "a span cut right after its opening leaves a lone backtick"
    assert clip("see `a` and `b`", 9) == "see `a` a" and clip("short", 80) == "short"
    long_title = "The table of all targets and their history, in the component `web/src/views/targets/TargetHistoryTable.tsx`, has no headers"
    lever = finding("FWK-001", kind="leverage", leverage={"finding_ids": ["KBD-001", "KBD-002"], "note": "One place: `ApplicationShellWithSidebar` renders every page, so one landmark there reaches all of them at once.",
                                                         "location": "the shared layout in `web/src/components/layout/ApplicationShellWithSidebar.tsx`, once"})
    _, draft, ids = run([finding("KBD-001", title=long_title), finding("KBD-002"), lever])
    rows = [l for l in draft.splitlines() if l.startswith("|")]
    assert sum("`" in l for l in rows) >= 2, "the title and the place of the lever are both cut inside a code span, or this checks nothing"
    assert all(l.count("`") % 2 == 0 for l in rows), [l for l in rows if l.count("`") % 2]
    assert {rule for _, rule, _ in lint(draft, ids)} == {"unwritten"}, lint(draft, ids)


def test_a_proposal_that_resolves_no_finding_yet_says_none():
    lint_layer = finding("FWK-001", kind="leverage", wcag=[], title="No lint layer", leverage={"finding_ids": [], "note": "Keeps a fixed finding from coming back."},
                         fix={"ownership": "project", "summary": "Add a lint step.", "location": "`package.json`"})
    _, draft, ids = run([finding("KBD-001"), lint_layer])
    row = next(l for l in draft.splitlines() if l.startswith("| `package.json`"))
    assert [c.strip() for c in row.split("|")[1:-1]][1] == "none", row          # an empty cell is what the linter refuses
    assert "FWK-001" not in ids.values() and "No lint layer" not in draft.split("## Structural advice")[0], "a proposal is not a finding"
    assert {rule for _, rule, _ in lint(draft, ids)} == {"unwritten"}, lint(draft, ids)


def test_a_finding_is_named_by_the_id_the_report_gives_it():
    persona = PERSONA.replace("| KBD-001 |", "| Stuck, see PER-screen-reader-001 and KBD-002 |").replace("1. The button.", "1. The button of PER-screen-reader-001.")
    cov = {"lenses": ["keyboard-focus"], "sc_coverage": {"2.1.2": {"status": "pass", "note": "Other than KBD-002."}}}
    fs = [finding("KBD-001", description="The same cause as `KBD-002` and PER-screen-reader-001, unlike KBD-0021 and XKBD-002.", verify="Fix KBD-002 first.",
                  fix={"ownership": "project", "summary": "See docs/KBD-002.md, KBD-002.png, https://example.org/KBD-002 and KBD-002.", "location": "docs/KBD-002.md"}),
          finding("KBD-002", severity="moderate"), finding("PER-screen-reader-001", severity="minor")]
    _, draft, ids = run(fs, personas={"screen-reader-user": persona}, extra=cov)
    rid = {m["source"][0]: r for r, m in ids.items()}
    a, b, per = rid["KBD-001"], rid["KBD-002"], rid["PER-screen-reader-001"]
    block = block_of(draft, a)
    assert f"The same cause as `{b}` and {per}, unlike KBD-0021 and XKBD-002." in block and f"Fix {b} first." in block, block
    assert f"See docs/KBD-002.md, KBD-002.png, https://example.org/KBD-002 and {b}. (at `docs/KBD-002.md`)" in block, "a file name or an address was rewritten"
    assert f"| Stuck, see {per} and {b} |" in draft, "the flow table names a finding by an ID the reader cannot look up"
    assert f"The button of {per}." in draft and f"Other than {b}." in draft, "a persona hint or a coverage note kept the ID of the findings file"
    assert f"| {a} | KBD-001 |" in draft and f"| {per} | PER-screen-reader-001 |" in draft, "appendix C lost the IDs it is there to list"
    assert not [m for _, rule, m in lint(draft, ids) if rule == "ids"], lint(draft, ids)


def test_dutch_writes_its_numbers_and_its_agents_in_dutch():
    _, draft, _ = run(FINDINGS, "nl")
    ws = LAST_WS
    assert "2,81 tot 1, daarna 4,54 tot 1" in draft and "is 0,06 (" in draft, "a number printed by the script kept its decimal point"
    (ws / "findings" / "keyboard-focus.json").write_text(json.dumps({"agent": "keyboard-focus", "findings": [],
                                                                     "coverage": {"method": "both", "examined": ["a", "b"], "not_examined": []}}), encoding="utf-8")
    (ws / "findings" / "my-own-lens.json").write_text(json.dumps({"agent": "my-own-lens", "findings": [], "coverage": {"method": "by ear", "examined": ["a"]}}), encoding="utf-8")
    (ws / "findings" / "odd.json").write_text(json.dumps({"agent": "odd", "findings": [], "coverage": {"method": ["static", "runtime"], "examined": []}}), encoding="utf-8")
    r, draft, _ = run(None, "nl", ws)
    assert r.returncode == 0 and "- odd: ['static', 'runtime'];" in draft, "a method that is no word of the schema stopped the report: " + r.stderr[-300:]
    assert "- toetsenbord en focus: gelezen in de code en geprobeerd in de draaiende applicatie; 2 bestanden of flows onderzocht" in draft, draft.split("### A.")[1][:600]
    assert "- my-own-lens: by ear; 1 bestanden" in draft, "an agent or a method the labels do not know was dropped"


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
