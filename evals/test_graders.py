#!/usr/bin/env python3
"""The graders of the two audit cases that read what a run wrote, and their self-check.

`claude plugin eval` has no grader that runs a script, and a language model that judges the trace sees only
its first and last twelve messages. So what can be read off a file is a regex grader on that file: free,
the same every time, and it sees the whole file. This script is the one place those graders are defined.

  python3 evals/test_graders.py            check: the grader files are the ones defined here, and each pattern
                                           holds against a report the real merge and renderer produce
  python3 evals/test_graders.py --write    write the grader files anew

A seeded failure counts as found by the rule of grade_findings.py: a finding block cites the criterion, its
"where" line names the file, and its title or problem text holds one of the keywords. One thing is stricter
here: only tiers 1 and 2 have finding blocks in the report, so a seeded failure filed in tier 3 is not found.
Every seeded failure is a tier 1 or 2 one, so that is a miss worth seeing. Whether it is 1 or 2 is not part
of the rule; three graders below hold a finding to its tier where the tier is not a matter of taste.
The graders written by hand (type llm, on the closing reply and on the short prose file) are left alone.

Patterns stay inside what JavaScript and Python regular expressions share, because the runner uses the first
and this check the second. Standard library only.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "skills" / "tiered-a11y-audit"
SCRIPTS, OWNERSHIP = SKILL / "scripts", SKILL / "references" / "wcag-ownership.md"
FULL, THEMED = HERE / "full-audit-fixture-site", HERE / "themed-site-fix-ownership"
L = json.loads((SKILL / "references" / "report-labels" / "nl.json").read_text(encoding="utf-8"))   # both prompts are Dutch
WS = "site/.a11y-audit"
REPORT = f"{WS}/REPORT.md"
HEAD = r"#{3,4} T%s-\d+\. "                 # the heading of a finding block; the report ID carries the tier
REST = r"(?:(?!\n#{2,4} )[\s\S])*?"         # on to somewhere in the same block


def esc(s):
    return re.sub(r"[.*+?^${}()|\[\]\\]", lambda m: "\\" + m.group(0), s)


def block(tier="[12]", sc=None, file=None, words=(), anywhere=()):
    """A finding block of this tier that cites the criterion, names the file and uses one of the words."""
    p = HEAD % tier
    if sc:
        p += rf"(?=[^\n]*\n\n[^\n]*\b(?:{sc})\b)"                                    # the sentence under the heading
    if file:
        p += rf"(?={REST}\n{esc(L['f_where'])}: [^\n]*{esc(file)})"
    if words:
        p += rf"(?=(?:[^\n]*|{REST}\n{esc(L['f_problem'])}: [^\n]*)(?:{'|'.join(map(esc, words))}))"   # title or problem
    return p + "".join(rf"(?={REST}(?:{a}))" for a in anywhere)


def regex(pattern, path=REPORT, match=None):
    return {"type": "regex", "target": f"{{ source: file, path: {path} }}", "pattern": pattern, "flags": "i", **({"match": match} if match else {})}


def ran(script):
    return {"type": "tool_used", "tool": "Bash", "input_match": script}


OWNED = rf"### (?:{esc(L['upstream_h'])}|{esc(L['accepted_h'])}) \(\d+\)"
HEX = r"#(?!%s\b)[0-9a-f]{6}\b"


def full():
    g = {
        "report-is-written": {"type": "file_exists", "path": REPORT},
        "report-has-three-tiers-in-dutch": regex(rf"\n## {esc(L['t1'])}\n[\s\S]*\n## {esc(L['t2'])}\n[\s\S]*\n## {esc(L['t3'])}\n"),
        "report-opens-in-short-before-any-table": regex(rf"^# [^\n]+\n+## {esc(L['short'])}\n+[^|#\s]"),
        "report-tables-have-at-most-four-columns": regex(r"(?:^|\n)\|(?:[^|\n]*\|){5,}[ \t]*(?=\n|$)", match="not_contains"),
        "report-has-all-four-core-personas-in-the-matrix": regex(
            rf"\| {esc(L['flow'])} \| {esc(L['persona'])} \| {esc(L['result'])} \|" + "".join(
                rf"(?=[\s\S]*\| {p} \|)" for p in ("screen-reader", "low-vision", "motor-voice", "cognitive"))),
        "report-says-personas-are-simulations": regex("simulatie"),
        "coverage-leaves-a-runtime-criterion-untested": regex(r"\| 2\.4\.11 \|[^\n]*\| not-tested \|", path=f"{WS}/coverage.md"),
        "site-html-is-left-as-it-was": regex(r"<html>", path="site/index.html"),
        "site-css-is-left-as-it-was": regex(r"\*:focus \{ outline: none; \}", path="site/styles.css"),
        "ran-the-merge-script": ran(r"merge_findings\.py"),
        "ran-the-last-phase-check": ran(r"check_phase\.py.* 6\b"),
        "tier-1-holds-the-missing-lang": regex(block("1", r"3\.1\.1", words=["lang"])),
        "tier-1-replaces-outline-none-with-focus-visible": regex(block("1", r"2\.4\.7", "styles.css", anywhere=["focus-visible"])),
        "tier-2-gives-the-muted-text-a-new-colour": regex(block("2", r"1\.4\.3", "styles.css", anywhere=["#9a9a9a", HEX % "9a9a9a|ffffff"])),
    }
    for i in json.loads((FULL / "ground-truth.json").read_text(encoding="utf-8"))["known_failures"]:
        slug = re.sub(r"[^a-z0-9]+", "-", i["keywords"][0].lower()).strip("-") or "x"
        g[f"finds-{i['id'].lower()}-{i['sc'].replace('.', '-')}-{slug}"] = regex(block(sc=esc(i["sc"]), file=i["file"], words=i["keywords"]))
    return g


def themed():
    return {
        "report-is-written": {"type": "file_exists", "path": REPORT},
        "profile-names-the-theme": regex(r"themes/paper", path=f"{WS}/stack-profile.md"),
        "chose-the-mini-or-the-lean-mode": regex(r'"mode": "(?:mini|lean)"', path=f"{WS}/briefs/_agents.json"),
        "report-lists-what-is-not-the-projects-to-fix": regex(OWNED),
        # a finding located in the theme whose report ID stands in one of those two lists
        "a-theme-defect-is-upstream-or-accepted": regex(
            r"#{3,4} (T\d-\d+)\. " + rf"(?={REST}\n{esc(L['f_where'])}: [^\n]*themes/paper)" + rf"(?=[\s\S]*?{OWNED}\n\n(?:- [^\n]*\n)*?- \1[ :(])"),
        "theme-file-is-left-as-it-was": regex(r"<html>", path="site/themes/paper/layouts/_default/baseof.html"),
        "finds-the-anchor-in-the-heading-hook": regex(block(file="render-heading")),
        "finds-outline-none-in-the-project-css": regex(block(file="custom.css", anywhere=["outline"])),
        "finds-the-link-colour-or-missing-underline": regex(block(file="custom.css", anywhere=[r"--link|underline|onderstre"])),
        "gives-the-muted-colour-a-replacement": regex(block(sc=r"1\.4\.3", file="custom.css", anywhere=["muted", r"#[0-9a-f]{6}\b"])),
    }


CASES = {FULL: full, THEMED: themed}


def text_of(spec):
    lines = [f"{k}: {v}" if k != "pattern" and k != "input_match" else f"{k}: '{v.replace(chr(39), chr(39) * 2)}'" for k, v in spec.items()]
    return "---\n" + "\n".join(lines) + "\n---\n"


def passes(spec, root: Path):
    """What the runner would decide for a regex grader on a file; None for the types this check cannot run."""
    if spec["type"] != "regex":
        return None
    p = root / re.search(r"path: (\S+)", spec["target"]).group(1)
    n = len(re.findall(spec["pattern"], p.read_text(encoding="utf-8"), re.I)) if p.is_file() else 0
    return n == 0 if spec.get("match") == "not_contains" else n > 0


# ---- a workspace made by the real scripts ------------------------------------------------------------------

def finding(n, sc, file, tier, word, **over):
    f = {"id": f"ORC-{n:03d}", "fingerprint": f"seeded-{n}@{file}", "title": f"{word}", "description": f"Beschrijving {word}.",
         "severity": "serious", "evidence": [{"file": file, "lines": "1"}], "wcag": [{"sc": sc}], "affected_users": ["screen-reader"],
         "visual_impact": {1: "none", 2: "subtle", 3: "significant"}[tier], "proposed_tier": tier, "tier_rationale": "Klein.",
         "fix": {"ownership": "project", "summary": "Herstel."}, "effort": "S", "confidence": "high", "verify": "Kijk."}
    f.update(over)
    return f


def audit(case: Path, findings, personas=("screen-reader", "low-vision", "motor-voice", "cognitive")):
    """Copy the fixture, file the findings as the orchestrator's, and run merge, render, prose, render."""
    root = Path(tempfile.mkdtemp())
    shutil.copytree(case / "files" / "site", root / "site")
    ws = root / WS
    (ws / "findings").mkdir(parents=True)
    (ws / "personas").mkdir()
    (ws / "findings" / "orchestrator.json").write_text(json.dumps({"agent": "orchestrator", "findings": findings}), encoding="utf-8")
    for p in personas:
        (ws / "personas" / f"{p}-user.md").write_text(f"# {p}\n\n## Flow results\n| Flow | Result | Feel | Main obstacle |\n|---|---|---|---|\n"
                                                      "| Contact | failed | slow | none |\n", encoding="utf-8")

    def run(name, *args):
        r = subprocess.run([sys.executable, str(SCRIPTS / name), str(ws), *args], capture_output=True, text=True)
        assert r.returncode == 0, f"{name}: {r.stdout}{r.stderr}"
    run("merge_findings.py", "--ownership", str(OWNERSHIP))
    problems = json.loads((ws / "findings" / "_merged.json").read_text(encoding="utf-8"))["problems"]
    assert not problems, problems
    run("render_report_parts.py", "--lang", "nl")
    prose = ws / "report-prose.md"
    keys = re.findall(r"^=== (.+) ===$", prose.read_text(encoding="utf-8"), re.M)
    prose.write_text("".join(f"=== {k} ===\nDe personas zijn simulaties.\n\n" for k in keys), encoding="utf-8")
    run("render_report_parts.py", "--lang", "nl")
    return root


def test_the_grader_files_are_the_ones_defined_here():
    for case, specs in CASES.items():
        want = {f"{name}.md": text_of(spec) for name, spec in specs().items()}
        have = {p.name: p.read_text(encoding="utf-8") for p in (case / "graders").glob("*.md") if "type: llm" not in p.read_text(encoding="utf-8")}
        assert have == want, f"{case.name}: run this script with --write (differs: {sorted(set(have) ^ set(want)) or [n for n in want if have[n] != want[n]]})"
        for p in (case / "graders").glob("*.md"):
            assert "focus: trace" not in p.read_text(encoding="utf-8"), f"{p.name} lets a judge read the trace, of which it sees only the ends"


def test_every_seeded_failure_is_found_by_its_own_grader_and_by_no_other():
    items = json.loads((FULL / "ground-truth.json").read_text(encoding="utf-8"))["known_failures"]
    finds = {n: s for n, s in full().items() if n.startswith("finds-")}
    assert len(finds) == len(items) == 24, (len(finds), len(items))
    seeded = [finding(n, i["sc"], i["file"], i["tier"], i["keywords"][0]) for n, i in enumerate(items, 1)]
    for n, i in enumerate(items):
        root = audit(FULL, [seeded[n]])
        got = [name for name, spec in finds.items() if passes(spec, root)]
        own = [name for name in finds if name.startswith(f"finds-{i['id'].lower()}-")]
        assert got == own, f"{i['id']} alone satisfies {got}"
        shutil.rmtree(root)
        other_file = next(j["file"] for j in items if j["file"] != i["file"])
        for what, f in (("another criterion", dict(seeded[n], wcag=[{"sc": "1.2.1"}])),
                        ("another file", dict(seeded[n], evidence=[{"file": other_file, "lines": "1"}])),
                        ("the keyword only in the fix", dict(seeded[n], title="Iets", description="Beschrijving.",
                                                             fix={"ownership": "project", "summary": i["keywords"][0]}))):
            root = audit(FULL, [f])
            assert not passes(finds[own[0]], root), f"{i['id']} counts as found with {what}"
            shutil.rmtree(root)


def test_a_complete_audit_passes_every_grader_and_an_empty_one_fails_the_ones_about_findings():
    items = json.loads((FULL / "ground-truth.json").read_text(encoding="utf-8"))["known_failures"]
    seeded = [finding(n, i["sc"], i["file"], i["tier"], i["keywords"][0]) for n, i in enumerate(items, 1)]
    plain = audit(FULL, [dict(f) for f in seeded])
    seeded = [dict(f, fix=dict(f["fix"])) for f in seeded]
    seeded[12]["fix"]["summary"] = "Gebruik :focus-visible."                    # GT-13, outline none
    seeded[10]["description"] = "De kleur #9a9a9a is te licht."                 # GT-11, muted text
    seeded[10]["fix"]["summary"] = "Maak er #767676 van."
    good, empty = audit(FULL, seeded), audit(FULL, [], personas=())
    assert [n for n, s in full().items() if n.startswith("tier-") and passes(s, plain)] == ["tier-1-holds-the-missing-lang"], \
        "a fix without :focus-visible or without a new colour passes its grader"
    shutil.rmtree(plain)
    same = [dict(f) for f in seeded]
    same[10] = dict(same[10], fix={"ownership": "project", "summary": "Maak #9a9a9a donkerder, niet #ffffff."})
    same = audit(FULL, same)
    assert not passes(full()["tier-2-gives-the-muted-text-a-new-colour"], same), "naming the old colour again counts as a replacement"
    with (same / REPORT).open("a", encoding="utf-8") as f:
        f.write("\n| a | b | c | d | e |\n|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 |\n")
    assert not passes(full()["report-tables-have-at-most-four-columns"], same), "a table of five columns passes"
    shutil.rmtree(same)
    for name, spec in full().items():
        if spec["type"] != "regex":
            continue
        assert passes(spec, good), f"{name} fails on a complete audit"
        about_findings = name.startswith(("finds-", "tier-", "report-has-all-four"))
        assert passes(spec, empty) is not about_findings, f"{name} {'passes' if about_findings else 'fails'} on an audit without findings or personas"
    other = audit(FULL, [dict(f, **({"visual_impact": "subtle", "proposed_tier": 2} if f["proposed_tier"] == 1 else
                                    {"visual_impact": "none", "proposed_tier": 1})) for f in seeded])
    assert not [n for n, s in full().items() if n.startswith("tier-") and passes(s, other)], "a tier grader passes with tiers 1 and 2 swapped"
    assert all(passes(s, other) for n, s in full().items() if n.startswith("finds-")), "being found depends on tier 1 against tier 2"
    third = audit(FULL, [dict(f, visual_impact="significant", proposed_tier=3) for f in seeded])
    assert not [n for n, s in full().items() if n.startswith(("finds-", "tier-")) and passes(s, third)], "a finding without a block in the report counts as found"
    for r in (good, empty, other, third):
        shutil.rmtree(r)


def test_the_themed_site_graders_tell_ownership_apart():
    theme, css = "themes/paper/layouts/_default/baseof.html", "assets/css/custom.css"
    def fs(own):
        return [finding(1, "3.1.1", theme, 1, "lang", fix={"ownership": own, "summary": "Vraag het de themamaker.", "location": theme,
                                                          "exception": {"reason": "Het thema is niet van ons."}}),
                finding(2, "1.3.1", "layouts/_default/_markup/render-heading.html", 1, "anker"),
                finding(3, "2.4.7", css, 1, "focus", description="outline: none haalt de focusring weg."),
                finding(4, "1.4.1", css, 2, "links", description="De kleur --link valt weg zonder onderstreping."),
                finding(5, "1.4.3", css, 2, "muted", description="--muted is te licht.", fix={"ownership": "project", "summary": "Maak er #5f5f5f van."})]
    for own in ("upstream", "accepted", "project"):
        root = audit(THEMED, fs(own), personas=("screen-reader", "low-vision"))
        (root / WS / "stack-profile.md").write_text("Vendored: themes/paper\n", encoding="utf-8")
        (root / WS / "briefs").mkdir()
        (root / WS / "briefs" / "_agents.json").write_text(json.dumps({"mode": "mini"}), encoding="utf-8")
        failed = [n for n, s in themed().items() if passes(s, root) is False]
        want = [] if own != "project" else ["report-lists-what-is-not-the-projects-to-fix", "a-theme-defect-is-upstream-or-accepted"]
        assert failed == want, f"theme defect marked {own}: failed {failed}"
        shutil.rmtree(root)
    root = audit(THEMED, fs("upstream")[1:] + [finding(6, "1.1.1", css, 1, "logo", fix={"ownership": "upstream", "summary": "x", "location": css})],
                 personas=("screen-reader", "low-vision"))
    assert passes(themed()["a-theme-defect-is-upstream-or-accepted"], root) is False, "an upstream finding outside the theme counts as a theme defect"
    shutil.rmtree(root)
    root = audit(THEMED, fs("project") + [finding(6, "1.1.1", css, 1, "logo", fix={"ownership": "upstream", "summary": "x", "location": css})],
                 personas=("screen-reader", "low-vision"))
    assert passes(themed()["a-theme-defect-is-upstream-or-accepted"], root) is False, "a theme defect left to the project passes because another finding is upstream"
    shutil.rmtree(root)


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        for case, specs in CASES.items():
            for p in (case / "graders").glob("*.md"):
                if "type: llm" not in p.read_text(encoding="utf-8") or "focus: trace" in p.read_text(encoding="utf-8"):
                    p.unlink()
            for name, spec in specs().items():
                (case / "graders" / f"{name}.md").write_text(text_of(spec), encoding="utf-8")
            print(f"{case.name}: {len(specs())} graders written")
        sys.exit(0)
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
