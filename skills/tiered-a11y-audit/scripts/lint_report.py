#!/usr/bin/env python3
"""Check a finished report against the skill's own read-aloud rules, so "done" is measured instead of claimed.

    python3 lint_report.py <repo>/.a11y-audit/REPORT.md [--workspace <repo>/.a11y-audit]

Prints one line per problem (file:line: rule: what) and exits 1 when there is any, 0 when the report is clean,
2 when it cannot run. The rules are the ones in SKILL.md under "Your own output must be accessible", as far as a
script can decide them in any language:

  unwritten  a <!-- WRITE: … --> gap, or any other comment left over from the draft
  heading    one H1, on the first heading, and no skipped level
  table      at most four columns, every row as wide as its header, no empty or symbol-only cell,
             announced by the sentence before it, one table per section
  list       one list level
  symbol     emoji, arrows, middle dots, rule lines, a ratio written as 4.5:1, a slash in running text
  bold       more than six words in bold
  ids        with --workspace: every ID of report-ids.json is in the report, tier 1 and 2 IDs have exactly one
             block, the report uses no ID that does not exist, and outside the full list of appendix C no
             finding is named by the ID it had in its findings file (KBD-003), which a reader cannot look up

Code blocks, code spans and link targets are not text and are skipped. So is a short piece of text between
quotation marks: that is a button label or a message quoted as the product shows it, arrow and all. Not checked, because no script can tell:
abbreviations without their full term, all-caps words (acronyms look the same), and whether the prose is true.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MAX_COLS, MAX_BOLD_WORDS = 4, 6
ARROWS = [(0x2190, 0x21FF), (0x27F0, 0x27FF), (0x2900, 0x297F), (0x2B00, 0x2B11)]
EMOJI = [(0x2600, 0x27BF), (0x2B50, 0x2B55), (0xFE0F, 0xFE0F), (0x1F000, 0x1FFFF)]
DOTS = "·•‧∙⋅"
ID_RE = re.compile(r"\bT[123]-\d{2,}\b")
# ponytail: a slash is taken for a path when the word has a file extension, a second slash, or a path-like start;
# anything else ("and/or", "src/components") is reported and belongs in words or in a code span.
PATH_RE = re.compile(r"^([./~@]|\w+://)|/.*/|\.\w{1,5}(:[\d,-]+)?$")
# Text of the interface, quoted: at most 60 characters between two quotation marks of a kind, on one line. A mark inside
# a word is an apostrophe (don't, foto's) and neither opens nor closes a quotation.
# ponytail: by the marks alone, so a sentence of that length in quotation marks is skipped too; code spans stay the sure way.
QUOTED = (r"""(?<!\w)(?:"(?=\S)[^"\n]{0,58}\S"|'(?=\S)(?:[^'\n]|'(?=\w)){0,58}?\S'|[“„](?=\S)[^”\n]{0,58}\S”"""
          r"""|‘(?=\S)(?:[^’\n]|’(?=\w)){0,58}?\S’)(?!\w)""")
SOURCE_ID = r"(?<![\w-])(?:[A-Z]{3}|PER-[a-z-]+)-\d{3}(?![\w-])"


def in_ranges(ch: str, ranges) -> bool:
    return any(a <= ord(ch) <= b for a, b in ranges)


def blank_out(text: str, pattern: str, flags=0) -> str:
    """Replace every match by spaces, keeping newlines, so line numbers stay true."""
    return re.sub(pattern, lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=flags)


def cells(row: str) -> list:
    return [c.strip() for c in re.split(r"(?<!\\)\|", row.strip())[1:-1]]


def lint(text: str, ids: dict | None = None) -> list:
    """Return [(line number, rule, message)], in line order."""
    out = []
    nofence = blank_out(text, r"^[ \t]*```.*?^[ \t]*```[^\n]*$", re.S | re.M)   # also a fence inside a list item
    for m in re.finditer(r"<!--(.*?)-->", nofence, re.S):
        if nofence[nofence.rfind("\n", 0, m.start()) + 1:m.start()].count("`") % 2:
            continue                                            # inside a code span: an example, not a gap
        what = " ".join(m.group(1).split())
        out.append((nofence.count("\n", 0, m.start()) + 1, "unwritten",
                    f"still to write: {what[6:70].strip()}" if what.startswith("WRITE:") else "a comment is left in the report: take it out of report-prose.md and render again (in a report made by hand: delete it)"))
    structure = blank_out(nofence, r"<!--.*?-->", re.S)
    prose = blank_out(blank_out(blank_out(blank_out(structure, r"`[^`\n]*`"), r"\]\([^)\n]*\)"), r"\w+://\S+"), QUOTED)
    lines, plines = structure.split("\n"), prose.split("\n")

    last_level, seen_table, i = 0, False, 0
    while i < len(lines):
        line, n = lines[i], i + 1
        h = re.match(r"^(#+) ", line)
        if h:
            level = len(h.group(1))
            if last_level == 0 and level != 1:
                out.append((n, "heading", "the first heading must be level 1"))
            elif last_level and level == 1:
                out.append((n, "heading", "a second level 1 heading: a report has one"))
            elif level > last_level + 1 and last_level:
                out.append((n, "heading", f"level {level} follows level {last_level}: a level is skipped"))
            last_level, seen_table = level, False
        if re.match(r"^\s{2,}([-*+]|\d+[.)])\s", line):
            out.append((n, "list", "nested list item: use one list level"))
        # ponytail: only tables written with leading pipes are seen, which is how the draft writes them
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[-: |]+\|\s*$", lines[i + 1]):
            width = len(cells(line))
            if width > MAX_COLS:
                out.append((n, "table", f"{width} columns: at most {MAX_COLS}"))
            if seen_table:
                out.append((n, "table", "a second table in one section: one table per section"))
            seen_table = True
            before = next((prev for prev in reversed(lines[:i]) if prev.strip()), "")
            if not before or re.match(r"^(#|\||\s*([-*+]|\d+[.)])\s)", before):
                out.append((n, "table", "not announced: the line before a table is a sentence that says what it lists"))
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                row = cells(lines[j])
                if len(row) != width:
                    out.append((j + 1, "table", f"row has {len(row)} cells, its header has {width}"))
                elif any(not re.search(r"\w", c) for c in row):
                    out.append((j + 1, "table", 'empty or symbol-only cell: write "none" in the report language'))
                j += 1
            i = j
            continue
        i += 1

    for n, line in enumerate(plines, 1):
        if re.match(r"^\s*(={3,}|-{3,}|\*{3,}|_{3,})\s*$", line):
            out.append((n, "symbol", "a rule line: use a heading to separate sections"))
            continue
        if line.startswith("|") and re.match(r"^\|[-: |]+\|\s*$", line):
            continue
        for kind, bad in (("emoji or pictograph", [c for c in line if in_ranges(c, EMOJI)]),
                          ("arrow", [c for c in line if in_ranges(c, ARROWS)] + re.findall(r"(?<![-=<])[-=]+>|<-+(?![->])", line)),
                          ("middle dot", [c for c in line if c in DOTS])):
            if bad:
                out.append((n, "symbol", f"{kind} ({' '.join(sorted(set(bad)))}): say it in words"))
        for r in re.findall(r"(?<![A-Za-z0-9_.,:])\d+(?:[.,]\d+)?:1(?![A-Za-z0-9_:])", line):
            out.append((n, "symbol", f'ratio written as {r}: write "{r[:-2]} to 1" in the report language'))
        for word in line.split():
            w = word.strip("()[]{}<>\"'*_,;:.!?|")
            if "/" in w and (not re.search(r"\w", w) or not PATH_RE.search(w)):
                out.append((n, "symbol", f'slash in "{w}": write it out, or put a path or code in backticks'))
        for b in re.findall(r"\*\*(.+?)\*\*", line):
            if len(b.split()) > MAX_BOLD_WORDS:
                out.append((n, "bold", f'{len(b.split())} words in bold ("{b[:40]}…"): at most {MAX_BOLD_WORDS}'))

    if ids is not None:
        used = set(ID_RE.findall(structure))
        for rid, meta in ids.items():
            blocks = len(re.findall(rf"^#+ {re.escape(rid)}\. ", structure, re.M))
            if rid not in used:
                out.append((0, "ids", f"{rid} is in report-ids.json but not in the report: a finding was dropped"))
            elif meta.get("tier") in (1, 2) and blocks != 1:
                out.append((0, "ids", f"{rid} has {blocks} finding blocks: exactly one, with the heading \"{rid}. <title>\""))
        for rid in sorted(used - set(ids)):
            out.append((0, "ids", f"{rid} is used in the report but is not in report-ids.json"))
        # The ID a finding had in its findings file means nothing to a reader. The renderer replaces the ones it knows, so
        # what is left is in the orchestrator's own text, or names a finding that is not in the report. Only the shapes
        # this audit uses are looked for, so that SHA-256 in a sentence is not taken for a finding.
        sources = {s: rid for rid, meta in ids.items() for s in meta.get("source") or []}
        stems = {s.rsplit("-", 1)[0] for s in sources}
        for n, line in enumerate(structure.split("\n"), 1):
            if re.match(r"\|\s*T[123]-\d{2,}\s*\|", line):
                continue                                        # a row of appendix C, where the source IDs belong
            for s in sorted(set(re.findall(SOURCE_ID, line))):
                if s in sources:
                    out.append((n, "ids", f"{s} is the ID of a findings file: the report calls this finding {sources[s]}"))
                elif s.rsplit("-", 1)[0] in stems:
                    out.append((n, "ids", f"{s} is the ID of a findings file and no finding of this report has it: describe what is meant, or leave it out"))
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report")
    ap.add_argument("--workspace", help="the .a11y-audit folder: also checks the report IDs against report-ids.json")
    a = ap.parse_args()
    path = Path(a.report)
    ids = None
    try:
        text = path.read_text(encoding="utf-8")
        if a.workspace:
            ids = json.loads((Path(a.workspace) / "report-ids.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"lint_report: cannot run: {e}", file=sys.stderr)
        return 2
    problems = lint(text, ids)
    for n, rule, msg in problems:
        print(f"{path}:{n}: {rule}: {msg}" if n else f"{path}: {rule}: {msg}")
    print(f"{len(problems)} problems in {path}" if problems else f"clean: {path}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
