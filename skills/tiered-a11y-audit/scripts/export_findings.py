#!/usr/bin/env python3
"""Export the audit into formats other tools and people expect.

    python3 export_findings.py <repo>/.a11y-audit --format sarif|acr|csv|accessibility-md [--lang <code>] [--out <path>]

sarif  SARIF 2.1.0 (GitHub code scanning, GitLab, VS Code SARIF viewers): one result per finding with
       file/line, severity mapped to error/warning/note, the WCAG criterion as rule id, help URL.
acr    Conformance table in VPAT / Accessibility Conformance Report style, one row per WCAG 2.2 A/AA
       criterion from coverage.md: Supports / Partially Supports / Does Not Support / Not Applicable /
       Not Evaluated, with the finding IDs as remarks. A draft for the person who signs it, not a VPAT.
csv    One row per finding for spreadsheets and ticket import.
accessibility-md
       A draft of an ACCESSIBILITY.md for a project that has none, in the report language: what the audit covered,
       how many criteria are met, the most severe open problems, what was accepted and what is someone else's to
       fix. What only the owner can say, the commitment and where to report a barrier, is left as a line that
       says so. Written into the workspace as ACCESSIBILITY.draft.md, never into the repository.

Pure standard library. Reads findings/_merged.json, coverage.md and report-ids.json (if present).
"""
from __future__ import annotations

import argparse
import csv
import datetime
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from labels import load_labels  # noqa: E402

SEV_TO_SARIF = {"blocker": "error", "critical": "error", "serious": "error", "moderate": "warning", "minor": "note"}
SEV_RANK = {"blocker": 0, "critical": 1, "serious": 2, "moderate": 3, "minor": 4}


def sc_url(sc: str, name: str) -> str:
    """W3C 'Understanding' page, derived from the criterion name (verify the link when citing it formally)."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"https://www.w3.org/WAI/WCAG22/Understanding/{slug}.html"


def load(ws: Path):
    merged = json.loads((ws / "findings" / "_merged.json").read_text(encoding="utf-8"))
    ids = {}
    p = ws / "report-ids.json"
    if p.exists():
        for rid, v in json.loads(p.read_text(encoding="utf-8")).items():
            for s in v["source"]:
                ids[s] = rid
    return merged, ids


def coverage_rows(ws: Path):
    rows = []
    p = ws / "coverage.md"
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        c = [x.strip() for x in line.strip("|").split("|")]
        if len(c) >= 7 and re.match(r"\d\.\d\.\d+", c[0]):
            rows.append({"sc": c[0], "name": c[1], "level": c[2], "status": c[4], "findings": c[5], "note": c[6]})
    return rows


def to_sarif(merged, ids, root_hint):
    rules, results = {}, []
    for f in merged["findings"]:
        scs = [s for s in f.get("wcag", []) if isinstance(s, dict) and s.get("sc")] or [{"sc": "best-practice", "name": "Best practice", "level": ""}]
        for s in scs:
            rid = f"wcag22/{s['sc']}"
            rules.setdefault(rid, {"id": rid, "name": s.get("name", s["sc"]), "shortDescription": {"text": f"WCAG 2.2 {s['sc']} {s.get('name', '')} ({s.get('level', '')})".strip()},
                                   "helpUri": sc_url(s["sc"], s.get("name", "")) if s["sc"] != "best-practice" else "https://www.w3.org/WAI/WCAG22/quickref/"})
        locs = []
        for e in f.get("evidence") or []:
            if not isinstance(e, dict):
                continue
            if e.get("file"):
                m = re.match(r"\s*(\d+)", str(e.get("lines") or ""))
                locs.append({"physicalLocation": {"artifactLocation": {"uri": e["file"], "uriBaseId": "SRCROOT"},
                                                  "region": {"startLine": int(m.group(1))} if m else {}}})
            elif e.get("url"):
                locs.append({"physicalLocation": {"artifactLocation": {"uri": e["url"]}},
                             "logicalLocations": [{"name": e.get("selector") or "", "kind": "element"}]})
        rep = ids.get(f["id"], f["id"])
        own = f.get("fix", {}).get("ownership", "project")
        results.append({
            "ruleId": f"wcag22/{scs[0]['sc']}",
            "level": SEV_TO_SARIF.get(f.get("severity"), "warning"),
            "message": {"text": f"[{rep}] {f.get('title', '')} — tier {f.get('tier')}, severity {f.get('severity')}, fix ownership {own}. {f.get('fix', {}).get('summary', '')}".strip()},
            "locations": locs or [{"physicalLocation": {"artifactLocation": {"uri": root_hint}}}],
            "partialFingerprints": {"tiered-a11y-audit/v1": f.get("fingerprint", f["id"])},
            "properties": {"tier": f.get("tier"), "severity": f.get("severity"), "ownership": own,
                           "affected_users": f.get("affected_users", []), "report_id": rep, "source_id": f["id"]},
        })
    return {"$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0",
            "runs": [{"tool": {"driver": {"name": "tiered-a11y-audit", "informationUri": "https://github.com/", "rules": list(rules.values())}},
                      "originalUriBaseIds": {"SRCROOT": {"uri": "file:///"}},
                      "results": results}]}


def to_acr(ws, merged, ids, t):
    L = t["acr"]
    sev_of = {f["id"]: f.get("severity") for f in merged["findings"]}
    for f in merged["findings"]:
        for m in f.get("merged_from", []):
            sev_of[m] = f.get("severity")
    out = [f"# {L['title']}", "", L["intro"], "",
           f"| {L['criterion']} | {L['level']} | {L['remarks']} |", "|---|---|---|"]
    for r in coverage_rows(ws):
        fids = [x.strip() for x in r["findings"].split(",") if x.strip()]
        st = r["status"]
        if st.startswith("fail"):
            worst = min((SEV_RANK.get(sev_of.get(i), 9) for i in fids), default=2)
            level = L["partial"] if worst >= 3 else L["does_not"]
        elif st == "pass":
            level = L["supports"]
        elif st == "n/a":
            level = L["not_applicable"]
        else:
            level = L["not_evaluated"]
        parts = [", ".join(ids.get(i, i) for i in fids)] if fids else []
        if r["note"] and r["note"] != "none":
            parts.append(r["note"])
        out.append(f"| {r['sc']} {r['name']} ({r['level']}) | {level} | {'. '.join(parts) or t['none']} |")
    return "\n".join(out) + "\n"


KNOWN_SHOWN = 15


def to_accessibility_md(ws: Path, merged, t) -> str:
    """A draft of the project's own accessibility document, from what the audit established and nothing else."""
    L = t["statement"]
    own = lambda what: f"*{L['owner'].format(what=what)}*"
    counts = merged.get("coverage_counts") or {}
    profile = ws / "stack-profile.md"
    scope = re.search(r"(?m)^- Scope:[ \t]*(.+?)[ \t]*$", profile.read_text(encoding="utf-8", errors="replace")) if profile.is_file() else None
    scope = scope.group(1) if scope and not re.search(r"<[^>]*>|…", scope.group(1)) else None      # a line still holding the template says nothing
    out = [f"# {L['title']}", "", L["intro"].format(date=datetime.date.today().isoformat()), "",
           f"## {L['commitment_h']}", "", own(L["commitment_todo"]), "",
           f"## {L['scope_h']}", ""] + ([L["scope_p"].format(scope=scope), ""] if scope else []) + [own(L["scope_todo"]), "",
           f"## {L['status_h']}", "",
           L["status_p"].format(n=sum(counts.values()), met=counts.get("pass", 0), failed=counts.get("fail", 0), na=counts.get("n/a", 0),
                                untested=counts.get("not-tested", 0)), "",
           L["how_runtime" if (ws / "automated" / "summary.json").is_file() else "how_static"], ""]

    def line(f):
        sc = ", ".join("WCAG " + w["sc"] for w in f.get("wcag") or [] if isinstance(w, dict) and w.get("sc")) or L["best_practice"]
        return f"- {str(f.get('title') or '').strip().rstrip('.')} ({sc}, {t['sev'].get(f.get('severity'), f.get('severity'))})."
    by_owner = {"accepted": [], "upstream": [], "project": []}
    for f in sorted(merged["findings"], key=lambda f: (SEV_RANK.get(f.get("severity"), 9), str(f.get("id")))):
        by_owner.get((f.get("fix") or {}).get("ownership"), by_owner["project"]).append(f)
    mine = by_owner["project"]
    out += [f"## {L['known_h']}", "", L["known_p"].format(n=len(mine), shown=min(len(mine), KNOWN_SHOWN)) if mine else L["known_none"], ""]
    out += [line(f) for f in mine[:KNOWN_SHOWN]] + ([""] if mine else [])
    for key in ("accepted", "upstream"):
        if by_owner[key]:
            reason = lambda f: str(((f.get("fix") or {}).get("exception") or {}).get("reason") or (f.get("fix") or {}).get("summary") or "").strip()
            out += [f"## {L[key + '_h']}", "", L[key + "_p"], ""]
            out += [line(f) + (f" {reason(f)}" if key == "accepted" and reason(f) else "") for f in by_owner[key]] + [""]
    out += [f"## {L['report_h']}", "", own(L["report_todo"]), ""]
    return "\n".join(out)


def to_csv(merged, ids):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["report_id", "source_id", "tier", "severity", "ownership", "title", "wcag", "file", "lines", "url", "selector", "affected_users", "effort", "fix_summary", "fix_location", "fingerprint"])
    for f in merged["findings"]:
        e = next((x for x in (f.get("evidence") or []) if isinstance(x, dict)), {})
        w.writerow([ids.get(f["id"], ""), f["id"], f.get("tier"), f.get("severity"), f.get("fix", {}).get("ownership"), f.get("title"),
                    " ".join(s.get("sc", "") for s in f.get("wcag", []) if isinstance(s, dict)), e.get("file", ""), e.get("lines", ""), e.get("url", ""), e.get("selector", ""),
                    " ".join(f.get("affected_users", [])), f.get("effort"), f.get("fix", {}).get("summary", ""), f.get("fix", {}).get("location", ""), f.get("fingerprint", "")])
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace")
    ap.add_argument("--format", required=True, choices=["sarif", "acr", "csv", "accessibility-md"])
    ap.add_argument("--lang", default="en", help="language code for the conformance table and the draft document; see labels.py")
    ap.add_argument("--out")
    a = ap.parse_args()
    ws = Path(a.workspace)
    merged, ids = load(ws)
    if a.format == "sarif":
        text, default = json.dumps(to_sarif(merged, ids, "."), indent=2), "findings.sarif"
    elif a.format == "acr":
        text, default = to_acr(ws, merged, ids, load_labels(a.lang, ws)), "conformance-table.md"
    elif a.format == "accessibility-md":
        text, default = to_accessibility_md(ws, merged, load_labels(a.lang, ws)), "ACCESSIBILITY.draft.md"
    else:
        text, default = to_csv(merged, ids), "findings.csv"
    out = Path(a.out) if a.out else ws / default
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out} ({len(merged['findings'])} findings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
