#!/usr/bin/env python3
"""Self-check for lint_report.py: a finished report passes, and each broken rule is named.

    python3 scripts/test_lint.py

The report starts from the real draft of render_report_parts.py with its gaps filled, so the linter is held
against what the skill actually produces. Standard library only, writes to a temp dir.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lint_report import lint  # noqa: E402
from test_render import FINDINGS, run  # noqa: E402

_, DRAFT, IDS = run(FINDINGS)
DONE = re.sub(r"<!-- WRITE:.*?-->", "Text written by the orchestrator.", DRAFT.split("-->", 1)[1].lstrip(), flags=re.S)
TABLE = "The next table lists two things with their value.\n\n| Thing | Value |\n|---|---|\n| one | 1 |\n| two | 2 |\n"


def rules(text, ids=None):
    return {rule for _, rule, _ in lint(text, ids)}


def extra(snippet):
    return DONE + "\n## Extra section\n\n" + snippet + "\n"


def test_a_finished_report_is_clean():
    assert lint(DONE, IDS) == [], lint(DONE, IDS)
    assert lint(extra(TABLE)) == []


def test_the_draft_itself_is_not_finished():
    problems = lint(DRAFT, IDS)
    assert {r for _, r, _ in problems} == {"unwritten"}
    assert len(problems) == DRAFT.count("<!--"), "every gap and the draft header are listed, each once"
    assert problems[0][0] == 1 and "a comment is left in the report" in problems[0][2], "the draft header is reported on its own line"


def test_each_broken_rule_is_named():
    cases = [
        ("unwritten", "<!-- WRITE: the summary -->"),
        ("heading", "#### Two levels down at once"),
        ("heading", "# A second title"),
        ("table", TABLE.replace("| Thing | Value |\n|---|---|", "| A | B | C | D | E |\n|---|---|---|---|---|")
                       .replace("| one | 1 |", "| a | b | c | d | e |").replace("| two | 2 |\n", "")),
        ("table", TABLE.replace("| two | 2 |", "| two | 2 | 3 |")),
        ("table", TABLE.replace("| two | 2 |", "| two | |")),
        ("table", TABLE.replace("| two | 2 |", "| two | - |")),
        ("table", TABLE.split("\n\n", 1)[1]),                                  # no sentence before it
        ("table", TABLE + "\n" + TABLE),                                         # two in one section
        ("list", "- first\n  - nested"),
        ("symbol", "Press Tab → the menu opens."),
        ("symbol", "Press Tab -> the menu opens."),
        ("symbol", "Fixed ✅"),
        ("symbol", "Home · About"),
        ("symbol", "The contrast is 4.5:1."),
        ("symbol", "Het contrast is 4,5:1."),
        ("symbol", "Level A/AA and/or more."),
        ("symbol", "Before / after."),
        ("symbol", "Text.\n\n----\n\nText."),
        ("symbol", "Title\n====="),
        ("bold", "**This whole sentence is bold and too long.**"),
    ]
    for rule, snippet in cases:
        assert rules(extra(snippet)) == {rule}, f"{snippet!r}: expected only {rule}, got {lint(extra(snippet))}"


def test_code_paths_and_links_are_not_text():
    fine = ("See `src/a/b`, src/page.html:12, docs/start.md:231,244, ./local, @scope/pkg, https://example.org/a/b and "
            "[the spec](https://example.org/a/b). Use `a -> b`, `4.5:1` or `<!-- x -->` in code. "
            "aria-labelledby at 12:30, a ratio of 4.5 to 1, **six words in bold are fine**.\n\n"
            "```html\n# not a heading\n<!-- not a gap -->\n| not | a | table | of | five |\n  - not nested => ✅ and/or 4.5:1\n```\n\n1. A step with its code:\n   ```js\n   // a comment -> here\n   <!-- and here -->\n   ```")
    assert lint(extra(fine)) == [], lint(extra(fine))


def test_text_of_the_interface_in_quotation_marks_is_a_quotation():
    fine = ("Four buttons are called 'Detail \u2192' and one 'Don't save \u2192'. The label \"Yes/No\" and the hint \"4.5:1\" stay as the product shows them, "
            "like \u201cNext \u2192\u201d, \u2018Back \u2190\u2019 and \u201eVerder \u2192\u201d.")
    assert lint(extra(fine)) == [], lint(extra(fine))
    for broken in ("The user's menu \u2192 the admin's page.",                       # apostrophes, no quotation
                   "De foto's \u2192 de auto's.",
                   "You can't go back \u2192 'Cancel' is gone.",
                   "The 12\" screen \u2192 the 24\" one.",
                   "'A whole sentence in quotation marks, which is prose and no label of the interface \u2192 so it is read.'",
                   "The label 'Detail' \u2192 opens the page.",                       # the arrow is beside the quotation, not in it
                   "'Detail \u2192 and nothing closes it.",
                   TABLE.replace("| one | 1 |", "| say \"Next | \u2192 Done\" |")):   # no quotation runs from one cell into the next
        assert rules(extra(broken)) == {"symbol"}, f"{broken!r}: {lint(extra(broken))}"


def test_an_id_of_a_findings_file_is_no_name_for_a_finding():
    rid = next(r for r, m in IDS.items() if m["source"] == ["KBD-002"])
    assert f"| {rid} | KBD-002 |" in DONE, "appendix C lists the source IDs, and that is where they belong"
    for text, word in (("Fix KBD-002 before the rest.", f"the report calls this finding {rid}"),
                       ("See `KBD-002` for the cause.", f"the report calls this finding {rid}"),
                       ("The same as KBD-077, which was rejected.", "no finding of this report has it")):
        got = [m for _, r, m in lint(extra(text), IDS) if r == "ids"]
        assert len(got) == 1 and word in got[0], f"{text!r}: {lint(extra(text), IDS)}"
    row = TABLE.replace("| one | 1 |", f"| {rid} | KBD-002 broke the page |")
    got = [m for _, r, m in lint(extra(row), IDS) if r == "ids"]
    assert len(got) == 1 and "KBD-002" in got[0], f"a table row that starts with a report ID is not appendix C for that reason: {got}"
    made_up = dict(IDS, **{"T3-09": {"source": ["PER-low-vision-x001"], "tier": 3}})
    got = [m for _, r, m in lint(extra("T3-09 is the same as PER-low-vision-x001."), made_up) if r == "ids"]
    assert len(got) == 1 and "the report calls this finding T3-09" in got[0], f"an ID the merge made up for a persona is not seen: {got}"
    quiet = "The hash is SHA-256, the standard ISO-639, the files docs/KBD-002.md and KBD-002.png, and KBD-0021 or XKBD-002 are no IDs of this audit."
    assert lint(extra(quiet), IDS) == [], lint(extra(quiet), IDS)
    assert lint(extra("Fix KBD-002 before the rest.")) == [], "without the workspace there is nothing to hold an ID against"


def test_report_ids_must_all_be_there_once():
    rid = next(r for r, m in IDS.items() if m["tier"] == 1)
    block = re.search(rf"^### {rid}\. .*?(?=^#{{2,3}} )", DONE, re.S | re.M).group(0)
    for broken, word in ((DONE.replace(block, ""), "0 finding blocks"), (DONE.replace(block, block + block), "2 finding blocks"),
                         (re.sub(rf".*\b{rid}\b.*\n", "", DONE.replace(block, "")), "was dropped"),
                         (DONE + "\nSee T1-99.\n", "T1-99 is used")):
        got = [m for _, r, m in lint(broken, IDS) if r == "ids"]
        assert len(got) == 1 and word in got[0], f"expected '{word}', got {lint(broken, IDS)}"
    t3 = next(r for r, m in IDS.items() if m["tier"] == 3)
    assert any("was dropped" in m for _, _, m in lint(DONE.replace(t3, ""), IDS)), "a tier 3 item can vanish unseen"


def cli(*a):
    return subprocess.run([sys.executable, str(HERE / "lint_report.py"), *map(str, a)], capture_output=True, text=True)


def test_exit_codes():
    with tempfile.TemporaryDirectory() as d:
        ok, bad = Path(d) / "ok.md", Path(d) / "bad.md"
        ok.write_text(DONE, encoding="utf-8")
        bad.write_text(DRAFT, encoding="utf-8")
        assert cli(ok).returncode == 0 and "clean" in cli(ok).stdout
        r = cli(bad)
        assert r.returncode == 1 and f"{bad}:1: unwritten:" in r.stdout
        assert cli(Path(d) / "missing.md").returncode == 2
        assert cli(ok, "--workspace", d).returncode == 2, "an ID check without report-ids.json must not pass silently"


def test_the_readme_keeps_the_same_rules():
    readme = HERE.parents[2] / "README.md"
    if readme.exists():                                         # absent when only the skill folder is installed
        assert lint(readme.read_text(encoding="utf-8")) == [], lint(readme.read_text(encoding="utf-8"))


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} checks passed")
