#!/usr/bin/env python3
"""Render the deterministic parts of the report so the orchestrator only writes prose and fix blocks.

    python3 render_report_parts.py <repo>/.a11y-audit [--lang en|nl]

Reads findings/_merged.json, coverage.md and personas/*.md. Writes:
  report-parts.md   tier count table, per-tier overview tables (report IDs T1-01 …), the persona results
                    table, appendix B (coverage) and appendix C (full list with source IDs), ready to paste
  report-ids.json   report ID → source finding (so IDs stay consistent while writing)
Findings are ordered within a tier by severity, then effort (S before L); reorder in the report if
impact-per-effort says otherwise, but keep the IDs. Tables stay within four columns and use words only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

SEV = {"blocker": 0, "critical": 1, "serious": 2, "moderate": 3, "minor": 4}
EFF = {"S": 0, "M": 1, "L": 2}
L = {
    "en": {"tier": "Tier", "findings": "Findings", "highest": "Highest severity", "effort": "Estimated effort", "id": "ID",
           "title": "Title", "severity": "Severity", "flow": "Flow", "persona": "Persona", "result": "Result",
           "obstacle": "Main obstacle", "sc": "Criterion", "name": "Name", "status": "Status", "note": "Note",
           "source": "Source IDs", "location": "Location", "none": "none", "effort_unit": {"S": "small", "M": "medium", "L": "large"},
           "results": {"completed": "completed", "difficulty": "with difficulty", "help": "with help", "failed": "failed", "na": "not applicable"},
           "own": {"upstream": "upstream", "accepted": "accepted"}, "upstream_h": "Needs an upstream change", "accepted_h": "Accepted exceptions"},
    "nl": {"tier": "Niveau", "findings": "Bevindingen", "highest": "Hoogste ernst", "effort": "Geschatte moeite", "id": "ID",
           "title": "Titel", "severity": "Ernst", "flow": "Flow", "persona": "Persona", "result": "Resultaat",
           "obstacle": "Belangrijkste obstakel", "sc": "Criterium", "name": "Naam", "status": "Status", "note": "Toelichting",
           "source": "Bron-ID's", "location": "Locatie", "none": "geen", "effort_unit": {"S": "klein", "M": "middel", "L": "groot"},
           "results": {"completed": "voltooid", "difficulty": "met moeite", "help": "met hulp", "failed": "mislukt", "na": "niet van toepassing"},
           "own": {"upstream": "upstream", "accepted": "geaccepteerd"}, "upstream_h": "Vraagt een wijziging upstream", "accepted_h": "Geaccepteerde uitzonderingen"},
}


def loc(f):
    ev = (f.get("evidence") or [{}])[0] if isinstance(f.get("evidence"), list) else {}
    if ev.get("file"):
        return f"{ev['file']}:{ev.get('lines') or ''}".rstrip(":")
    return ev.get("url") or "?"


def effort_total(fs):
    c = Counter(f.get("effort") for f in fs)
    return ", ".join(f"{c[k]} {k}" for k in ("S", "M", "L") if c[k]) or "?"


def classify_result(text, t):
    s = text.lower()
    if "n/a" in s or "not applicable" in s or "niet van toepassing" in s: return t["results"]["na"]
    if "fail" in s or "mislukt" in s: return t["results"]["failed"]
    if "help" in s or "workaround" in s or "hulp" in s: return t["results"]["help"]
    if "difficult" in s or "moeite" in s: return t["results"]["difficulty"]
    if "complet" in s or "voltooid" in s: return t["results"]["completed"]
    return text.strip()


def persona_rows(pdir: Path, t):
    rows = []
    for p in sorted(pdir.glob("*.md")) if pdir.is_dir() else []:
        name = p.stem.replace("-user", "")
        section = None
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                section = "flows" if "flow results" in line.lower() else None
                continue
            if section == "flows" and line.startswith("|") and not re.match(r"\|\s*-", line) and "Flow" not in line.split("|")[1]:
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) >= 4:
                    rows.append((cells[0], name, classify_result(cells[1], t), cells[3] or t["none"]))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace")
    ap.add_argument("--lang", default="en", choices=sorted(L))
    a = ap.parse_args()
    ws = Path(a.workspace)
    t = L[a.lang]
    data = json.loads((ws / "findings" / "_merged.json").read_text(encoding="utf-8"))
    findings = [f for f in data["findings"] if f.get("tier") in (1, 2, 3)]
    findings.sort(key=lambda f: (f["tier"], SEV.get(f.get("severity"), 9), EFF.get(f.get("effort"), 9), f["id"]))
    ids = {}
    counters = Counter()
    for f in findings:
        counters[f["tier"]] += 1
        f["report_id"] = f"T{f['tier']}-{counters[f['tier']]:02d}"
        ids[f["report_id"]] = {"source": [f["id"]] + f.get("merged_from", []), "fingerprint": f.get("fingerprint"),
                               "title": f.get("title"), "severity": f.get("severity"), "tier": f["tier"]}
    (ws / "report-ids.json").write_text(json.dumps(ids, indent=2, ensure_ascii=False), encoding="utf-8")

    out = ["# Report parts (generated; paste, don't retype)", ""]
    out += ["## Tier counts", "", f"| {t['tier']} | {t['findings']} | {t['highest']} | {t['effort']} |", "|---|---|---|---|"]
    for tier in (1, 2, 3):
        fs = [f for f in findings if f["tier"] == tier]
        highest = min((f.get("severity") for f in fs), key=lambda s: SEV.get(s, 9), default=t["none"])
        out.append(f"| {tier} | {len(fs)} | {highest} | {effort_total(fs)} |")
    for tier in (1, 2, 3):
        fs = [f for f in findings if f["tier"] == tier]
        out += ["", f"## Tier {tier} overview ({len(fs)})", "", f"| {t['id']} | {t['title']} | {t['severity']} | {t['effort']} |", "|---|---|---|---|"]
        for f in fs:
            flag = " (blocker)" if f.get("severity") == "blocker" else " (affects everyone)" if f.get("affects_all_users") else ""
            own = f.get("fix", {}).get("ownership")
            mark = f" ({t['own'][own]})" if own in ("upstream", "accepted") else ""
            out.append(f"| {f['report_id']}{mark} | {f.get('title', '')[:80]}{flag} | {f.get('severity')} | {t['effort_unit'].get(f.get('effort'), f.get('effort') or '?')} |")
        ups = [f for f in fs if f.get("fix", {}).get("ownership") == "upstream"]
        acc = [f for f in fs if f.get("fix", {}).get("ownership") == "accepted"]
        if ups:
            out += ["", f"### {t['upstream_h']} ({len(ups)})", ""] + [f"- {f['report_id']}: {f.get('fix', {}).get('location') or '?'}" for f in ups]
        if acc:
            out += ["", f"### {t['accepted_h']} ({len(acc)})", ""]
            for f in acc:
                ex = f.get("fix", {}).get("exception") or {}
                tool = f" ({ex.get('tool')} {ex.get('rule')} on {ex.get('selector')})" if ex.get("rule") else ""
                out.append(f"- {f['report_id']}{tool}: {ex.get('reason') or f.get('fix', {}).get('summary') or '?'}")
    rows = persona_rows(ws / "personas", t)
    if rows:
        out += ["", f"## Persona results ({len(rows)} rows)", "", f"| {t['flow']} | {t['persona']} | {t['result']} | {t['obstacle']} |", "|---|---|---|---|"]
        src_to_rep = {s: rid for rid, v in ids.items() for s in v["source"]}
        for flow, name, res, obst in rows:
            obst2 = re.sub(r"\b([A-Z]{3}-\d{3})\b", lambda m: src_to_rep.get(m.group(1), m.group(1)), obst)
            out.append(f"| {flow[:50]} | {name} | {res} | {obst2[:60]} |")
    cov = ws / "coverage.md"
    if cov.exists():
        lines = cov.read_text(encoding="utf-8").splitlines()
        table = [l for l in lines if l.startswith("|")]
        counts = next((l for l in lines if l.startswith("Counts:")), "")
        out += ["", "## Appendix B: WCAG 2.2 A and AA coverage", "", counts, "",
                f"| {t['sc']} | {t['name']} | {t['status']} | {t['note']} |", "|---|---|---|---|"]
        for l in table[2:]:
            c = [x.strip() for x in l.strip("|").split("|")]
            if len(c) >= 7:
                status = c[4] + (f" ({c[5]})" if c[5] else "")
                status = re.sub(r"\b([A-Z]{3}-\d{3})\b", lambda m: next((rid for rid, v in ids.items() if m.group(1) in v["source"]), m.group(1)), status)
                out.append(f"| {c[0]} | {c[1]} | {status.replace('n/a', t['results']['na'])} | {(c[6] or t['none'])[:70]} |")
    out += ["", f"## Appendix C: full list ({len(findings)})", "", f"| {t['id']} | {t['source']} | {t['severity']} | {t['location']} |", "|---|---|---|---|"]
    for f in findings:
        out.append(f"| {f['report_id']} | {', '.join(ids[f['report_id']]['source'])} | {f.get('severity')} | {loc(f)[:70]} |")
    (ws / "report-parts.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"report-parts.md: {len(findings)} findings ({', '.join(f'T{k}: {v}' for k, v in sorted(counters.items()))}), "
          f"{len(rows)} persona rows, coverage {'included' if cov.exists() else 'missing'}; report-ids.json written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
