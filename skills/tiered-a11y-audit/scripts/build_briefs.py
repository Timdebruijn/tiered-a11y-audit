#!/usr/bin/env python3
"""Build one briefing file per subagent, so each agent reads a single file instead of seven.

    python3 build_briefs.py <SKILL_DIR> <repo>/.a11y-audit --playbook 1,2,16,18 [--lean]

Writes .a11y-audit/briefs/<agent>.md for every expert and persona: protocol + agent file + finding schema +
tiering + ownership + stack profile + only the requested playbook sections. --lean writes four merged expert
briefs (structure-content, keyboard-dynamic, visual-perception, forms-input); --mini writes two (perceive, operate).
Saves six to twelve tool calls per agent and keeps agents from reading the whole playbook.

Each expert brief ends with the start of its findings file: its name, its lenses and every criterion it owns.
briefs/_agents.json lists the agents of this run; check_phase.py reads it to know whose output to expect.

A brief carries only what its reader acts on. From the references it leaves out: the rows of the criterion
table that belong to other lenses, the parts of tiering.md that only the orchestrator and the merge use (the
persona severity floors, the scoring rubric), and the schema fields that agent never writes. A section or field named here that the reference no longer has exactly once stops the
build, and so does a criterion whose owner is no lens of the run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from merge_findings import load_previous, parse_ownership  # noqa: E402

EXPERTS = ["semantics-structure", "keyboard-focus", "visual-perception", "forms-input", "dynamic-content", "content-media"]
LEAN = {"structure-content": ["semantics-structure", "content-media"], "keyboard-dynamic": ["keyboard-focus", "dynamic-content"],
        "visual-perception": ["visual-perception"], "forms-input": ["forms-input"]}
MINI = {"perceive": ["semantics-structure", "content-media", "visual-perception"],
        "operate": ["keyboard-focus", "dynamic-content", "forms-input"]}
PERSONAS = ["screen-reader-user", "low-vision-user", "motor-voice-user", "cognitive-user", "colour-blind-user",
            "deaf-user", "vestibular-user", "older-novice-user"]


def playbook_sections(text: str, wanted):
    parts = re.split(r"(?m)^## (\d+)\. ", text)
    out = []
    for i in range(1, len(parts), 2):
        if parts[i] in wanted:
            out.append(f"## {parts[i]}. " + parts[i + 1])
    return "\n".join(out)


# "Fix ownership" stays in: it is the only place that says an accepted exception still counts as a fail in the matrix.
ORCHESTRATOR_ONLY = ("### Persona verdicts set a floor on severity", "## Scoring rubric (1–10)")
MAXIMIZER_FIELDS = ("kind", "leverage")
EXPERT_FILE_FIELDS = ("lenses", "sc_coverage", "cross_lens_notes", "fix.ownership")     # a persona writes none of these


def without_sections(text: str, headings, source: str) -> str:
    """The document minus each named section: its heading line and everything up to the next heading of the same or a higher level."""
    lines, levels, fenced = text.split("\n"), [], False
    for line in lines:                                          # a "# comment" in a code block is not a heading
        if line.lstrip().startswith("```"):
            fenced = not fenced
        heading = not fenced and line.startswith("#") and line.lstrip("#").startswith(" ")
        levels.append(len(line) - len(line.lstrip("#")) if heading else 0)
    for h in headings:
        n = sum(1 for line, level in zip(lines, levels) if level and line == h)
        if n != 1:
            sys.exit(f"build_briefs: {source} has {n} sections {h!r}, expected one; it was renamed, removed or repeated, update build_briefs.py")
    out, skip = [], 0
    for line, level in zip(lines, levels):
        if level and line in headings:
            skip = level
            continue
        if skip and level and level <= skip:
            skip = 0
        if not skip:
            out.append(line)
    return "\n".join(out)


def without_fields(text: str, fields, source: str) -> str:
    """The schema minus the rule of each named field: its bullet and what is indented under it, blank lines in between included."""
    lines, out, skipping = text.split("\n"), [], False
    for f in fields:
        if sum(line.startswith(f"- `{f}`") for line in lines) != 1:
            sys.exit(f"build_briefs: {source} has no single rule for the field `{f}`; it was renamed, removed or repeated, update build_briefs.py")
    for i, line in enumerate(lines):
        if line.startswith("- `"):
            skipping = any(line.startswith(f"- `{f}`") for f in fields)
        elif skipping and not line.strip():
            # a blank line belongs to the cut rule only when indented text follows it
            skipping = next((later for later in lines[i + 1:] if later.strip()), "").startswith(" ")
        elif skipping and not line.startswith(" "):
            skipping = False
        if not skipping:
            out.append(line)
    return "\n".join(out)


def own_rows(text: str, lenses: list, owners: dict) -> str:
    """The ownership document with only the criterion rows of these lenses; who owns the rest is in its per-owner list.
    A row is a table line whose first cell is a criterion parse_ownership() knows, so the two cannot disagree on the format."""
    def keep(line: str) -> bool:
        m = re.match(r"\|\s*(\d\.\d\.\d+)\s*\|", line)
        return not (m and m.group(1) in owners) or owners[m.group(1)]["owner"] in lenses
    kept = [line for line in text.split("\n") if keep(line)]
    if not lenses:                                              # no rows left: drop the table's header as well
        kept = [line for i, line in enumerate(kept) if not (line.startswith("| SC | Name |") or (i and kept[i - 1].startswith("| SC | Name |")))]
    return "\n".join(kept)


PREFIX_LENS = {"SEM": "semantics-structure", "KBD": "keyboard-focus", "VIS": "visual-perception", "FRM": "forms-input",
               "DYN": "dynamic-content", "CNT": "content-media", "FWK": "framework-maximizer"}


def earlier_findings(prev, owners: dict) -> dict:
    """reader -> the lines of the earlier audit's findings that are its own: a lens by ID prefix, or else by the owner of
    the first criterion; a persona by its PER- prefix. A finding that fits neither goes to nobody."""
    out = {}
    for f in (prev or {}).get("findings") or []:
        fid, fp = str(f.get("id") or ""), str(f.get("fingerprint") or "").strip()
        if not fp:
            continue
        per = re.match(r"PER-([a-z-]+?)-x?\d+$", fid)
        scs = [w.get("sc") for w in f.get("wcag") or [] if isinstance(w, dict)]
        reader = (per.group(1) + "-user" if per else PREFIX_LENS.get(fid[:3])
                  or next((owners[sc]["owner"] for sc in scs if sc in owners), None))
        if reader:
            out.setdefault(reader, []).append(f"- `{fp}`: {' '.join(str(f.get('title') or '').split())}")
    return out


def earlier_section(lines: list) -> str:
    if not lines:
        return ""
    return ("# Findings of the earlier audit\n\nThis is a re-audit. The earlier audit filed the findings below in your area, one line each: its "
            "fingerprint, then its title. They are not findings of this run: judge the product as it is now, and file nothing you did not see "
            "yourself. When you do find one of these problems again, give your finding the same `fingerprint`, character for character, whatever "
            "slug you would have chosen yourself. That is how the two audits are compared, and a problem filed under a new slug counts as "
            "a new one beside an old one that nobody reported again.\n\n" + "\n".join(sorted(lines)))


def skeleton(brief: str, lenses: list, owners: dict) -> str:
    """The start of the agent's findings file, so it fills in statuses instead of recalling which criteria are its own."""
    own = [sc for sc, meta in owners.items() if meta["owner"] in lenses]
    cov = ",\n".join(f'    "{sc}": {{"status": "TODO", "note": ""}}' for sc in own)
    return (f"# Start of your findings file\n\nBegin `findings/{brief}.json` from the JSON below. It lists the {len(own)} criteria you own. "
            "Replace every TODO: a status is one of pass, fail (add \"findings\": [ids]), not-tested or n/a, the last two with the reason "
            "in the note. The orchestrator's phase check refuses a file in which a criterion is missing, still says TODO, or is not-tested or n/a without a note.\n\n```json\n"
            f'{{\n  "agent": "{brief}",\n  "lenses": {json.dumps(lenses)},\n'
            '  "coverage": {"method": "TODO", "examined": [], "not_examined": [], "notes": ""},\n'
            '  "positives": [],\n  "cross_lens_notes": [],\n'
            f'  "sc_coverage": {{\n{cov}\n  }},\n  "findings": []\n}}\n```')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill_dir")
    ap.add_argument("workspace")
    ap.add_argument("--playbook", default="1", help="comma-separated section numbers of framework-playbooks.md")
    ap.add_argument("--lean", action="store_true")
    ap.add_argument("--mini", action="store_true", help="two merged expert agents (perceive / operate)")
    a = ap.parse_args()
    sd, ws = Path(a.skill_dir), Path(a.workspace)
    rd = lambda p: p.read_text(encoding="utf-8")
    refs = sd / "references"
    schema, ownership = rd(refs / "finding-schema.md"), rd(refs / "wcag-ownership.md")
    tiering = without_sections(rd(refs / "tiering.md"), ORCHESTRATOR_ONLY, "tiering.md")
    lens_schema = without_fields(schema, MAXIMIZER_FIELDS, "finding-schema.md")
    persona_schema = without_fields(schema, MAXIMIZER_FIELDS + EXPERT_FILE_FIELDS, "finding-schema.md")
    profile = rd(ws / "stack-profile.md") if (ws / "stack-profile.md").exists() else "(stack profile missing)"
    wanted = {s.strip() for s in a.playbook.split(",") if s.strip()}
    pb = playbook_sections(rd(refs / "framework-playbooks.md"), wanted)
    extras = ""
    for name in ("pattern-inventory.md", "aria-digest.md", "colour-pairs.md"):
        if (ws / name).exists():
            extras += f"\n\nAlso available in the workspace (read when your lens needs it): {name}"
    out = ws / "briefs"
    out.mkdir(exist_ok=True)
    expert_proto = rd(sd / "agents" / "experts" / "_protocol.md")
    persona_proto = rd(sd / "agents" / "personas" / "_protocol.md")
    agents = MINI if a.mini else LEAN if a.lean else {e: [e] for e in EXPERTS}
    owners = parse_ownership(refs / "wcag-ownership.md")
    homeless = sorted(sc for sc, meta in owners.items() if not any(meta["owner"] in lenses for lenses in agents.values()))
    if not owners or homeless:
        sys.exit(f"build_briefs: wcag-ownership.md gives {len(owners)} criteria, of which {', '.join(homeless) or 'none'} have an owner "
                 "that is no lens of this run; no brief would carry them")
    prev = load_previous(ws / "previous")[0] if (ws / "previous").is_dir() else None       # a re-audit: preflight.py --start put it there
    known = earlier_findings(prev, owners)

    def with_earlier(parts, readers):
        section = earlier_section([line for r in readers for line in known.get(r, [])])
        return "\n\n---\n\n".join(parts + [section] if section else parts)
    for brief, lenses in agents.items():
        body = "\n\n".join(rd(sd / "agents" / "experts" / f"{l}.md") for l in lenses)
        if len(lenses) > 1:
            body = (f"You cover {len(lenses)} lenses in this run and own the WCAG criteria and patterns of all of them: {', '.join(lenses)}. "
                    f"Write ONE findings file, named {brief}.json, with \"lenses\": {json.dumps(lenses)} at the top level and sc_coverage for both lenses; "
                    f"use the ID prefixes of whichever lens a finding belongs to.\n\n") + body
        # the earlier findings go before the skeleton, which stays the last thing an expert reads
        (out / f"{brief}.md").write_text(with_earlier([
            f"# Briefing: {brief}", expert_proto, body, lens_schema, tiering, own_rows(ownership, lenses, owners), "# Stack profile\n\n" + profile + extras,
            "# Framework playbook (relevant sections)\n\n" + pb], lenses) + "\n\n---\n\n" + skeleton(brief, lenses, owners), encoding="utf-8")
    (out / "framework-maximizer.md").write_text(with_earlier([
        "# Briefing: framework-maximizer", expert_proto, rd(sd / "agents" / "experts" / "framework-maximizer.md"),
        schema, tiering, own_rows(ownership, [], owners), "# Stack profile\n\n" + profile + extras, "# Framework playbook (relevant sections)\n\n" + pb],
        ["framework-maximizer"]), encoding="utf-8")
    for p in PERSONAS:
        (out / f"{p}.md").write_text(with_earlier([
            f"# Briefing: {p}", persona_proto, rd(sd / "agents" / "personas" / f"{p}.md"), persona_schema,
            "# Stack profile\n\n" + profile + extras], [p]), encoding="utf-8")
    (out / "_agents.json").write_text(json.dumps({"mode": "mini" if a.mini else "lean" if a.lean else "full", "experts": agents,
                                                  "maximizer": "framework-maximizer", "personas": PERSONAS}, indent=2), encoding="utf-8")
    print(f"briefs written to {out} ({len(agents)} expert, 1 maximizer, {len(PERSONAS)} persona); playbook sections {sorted(wanted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
