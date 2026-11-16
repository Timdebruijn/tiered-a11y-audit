#!/usr/bin/env python3
"""Build one briefing file per subagent, so each agent reads a single file instead of seven.

    python3 build_briefs.py <SKILL_DIR> <repo>/.a11y-audit --playbook 1,2,16,18 [--lean]

Writes .a11y-audit/briefs/<agent>.md for every expert and persona: protocol + agent file + finding schema +
tiering + ownership + stack profile + only the requested playbook sections. --lean writes four merged expert
briefs (structure-content, keyboard-dynamic, visual-perception, forms-input); --mini writes two (perceive, operate).
Saves six to twelve tool calls per agent and keeps agents from reading the whole playbook.

Each expert brief ends with the start of its findings file: its name, its lenses and every criterion it owns.
briefs/_agents.json lists the agents of this run; check_phase.py reads it to know whose output to expect.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from merge_findings import parse_ownership  # noqa: E402

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


def skeleton(brief: str, lenses: list, owners: dict) -> str:
    """The start of the agent's findings file, so it fills in statuses instead of recalling which criteria are its own."""
    own = [sc for sc, meta in owners.items() if meta["owner"] in lenses]
    cov = ",\n".join(f'    "{sc}": {{"status": "TODO", "note": ""}}' for sc in own)
    return (f"# Start of your findings file\n\nBegin `findings/{brief}.json` from the JSON below. It lists the {len(own)} criteria you own. "
            "Replace every TODO: a status is one of pass, fail (add \"findings\": [ids]), not-tested or n/a, the last two with the reason "
            "in the note. The orchestrator's phase check refuses a file with a TODO or a missing criterion.\n\n```json\n"
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
    common_refs = "\n\n".join([rd(refs / "finding-schema.md"), rd(refs / "tiering.md"), rd(refs / "wcag-ownership.md")])
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
    for brief, lenses in agents.items():
        body = "\n\n".join(rd(sd / "agents" / "experts" / f"{l}.md") for l in lenses)
        if len(lenses) > 1:
            body = (f"You cover {len(lenses)} lenses in this run and own the WCAG criteria and patterns of all of them: {', '.join(lenses)}. "
                    f"Write ONE findings file, named {brief}.json, with \"lenses\": {json.dumps(lenses)} at the top level and sc_coverage for both lenses; "
                    f"use the ID prefixes of whichever lens a finding belongs to.\n\n") + body
        (out / f"{brief}.md").write_text("\n\n---\n\n".join([
            f"# Briefing: {brief}", expert_proto, body, common_refs, "# Stack profile\n\n" + profile + extras,
            "# Framework playbook (relevant sections)\n\n" + pb, skeleton(brief, lenses, owners)]), encoding="utf-8")
    (out / "framework-maximizer.md").write_text("\n\n---\n\n".join([
        "# Briefing: framework-maximizer", expert_proto, rd(sd / "agents" / "experts" / "framework-maximizer.md"),
        common_refs, "# Stack profile\n\n" + profile + extras, "# Framework playbook (relevant sections)\n\n" + pb]), encoding="utf-8")
    for p in PERSONAS:
        (out / f"{p}.md").write_text("\n\n---\n\n".join([
            f"# Briefing: {p}", persona_proto, rd(sd / "agents" / "personas" / f"{p}.md"), rd(refs / "finding-schema.md"),
            "# Stack profile\n\n" + profile + extras]), encoding="utf-8")
    (out / "_agents.json").write_text(json.dumps({"mode": "mini" if a.mini else "lean" if a.lean else "full", "experts": agents,
                                                  "maximizer": "framework-maximizer", "personas": PERSONAS}, indent=2), encoding="utf-8")
    print(f"briefs written to {out} ({len(agents)} expert, 1 maximizer, {len(PERSONAS)} persona); playbook sections {sorted(wanted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
