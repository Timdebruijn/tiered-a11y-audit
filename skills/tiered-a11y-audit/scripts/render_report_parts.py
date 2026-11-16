#!/usr/bin/env python3
"""Render the deterministic parts of the report so the orchestrator only writes prose and fix blocks.

    python3 render_report_parts.py <repo>/.a11y-audit [--lang <code>]

Reads findings/_merged.json, findings/<agent>.json, coverage.md and personas/*.md. Writes:
  REPORT.draft.md   the whole report in the shape of references/report-template.md: every table, every
                    finding block with its fields in the fixed order, the token changes, the structural
                    advice, the to-verify list and the appendices. What needs judgement or a human voice
                    is left as a marked gap: <!-- WRITE: … -->. Copy it to REPORT.md and fill the gaps.
  report-parts.md   the tables alone (tier counts, per-tier overviews with report IDs T1-01 …, persona
                    results, appendix B and C), kept for anything that still reads it
  report-ids.json   report ID → source finding (so IDs stay consistent while writing)
Every value in a finding block comes from _merged.json, so nothing is retyped and nothing can be dropped
or altered on the way into the report. The agents write their finding text in the report language, so it
goes in as it is; a contrast written as 4.5:1 is put into words on the way. The fixed words of the report come from a labels file, so any
language works: en and nl ship with the skill, and for another one the first run writes
report-labels.<code>.json into the workspace to be translated once (see labels.py).
Findings are ordered within a tier by severity, then effort (S before L); reorder in the report if
impact-per-effort says otherwise, but keep the IDs. Tables stay within four columns and use words only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from labels import load_labels  # noqa: E402

SEV = {"blocker": 0, "critical": 1, "serious": 2, "moderate": 3, "minor": 4}
EFF = {"S": 0, "M": 1, "L": 2}
WRITE = "<!-- WRITE: {} -->"


def loc(f):
    ev = (f.get("evidence") or [{}])[0] if isinstance(f.get("evidence"), list) else {}
    if ev.get("file"):
        return f"{ev['file']}:{ev.get('lines') or ''}".rstrip(":")
    return ev.get("url") or "?"


def effort_total(fs, t):
    c = Counter(f.get("effort") for f in fs)
    return ", ".join(f"{c[k]} {t['effort_unit'][k]}" for k in ("S", "M", "L") if c[k]) or ("?" if fs else t["none"])


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



TO1 = "{r} to 1"        # main() sets it from the labels of the report language


def spoken(s: str) -> str:
    """A contrast written as 4.5:1 put into words, outside code spans. Agents are told to write it in words; this catches the rest."""
    parts = re.split(r"(`[^`]*`)", s)
    return "".join(p if p.startswith("`") else re.sub(r"(?<![\w.,:])(\d+(?:[.,]\d+)?):1(?![\w:])", lambda m: TO1.format(r=m.group(1)), p) for p in parts)


def one(x, what):
    """Text on one line, or a marked gap when the finding does not have it."""
    s = re.sub(r"\s+", " ", str(x or "")).strip()
    return spoken(s) or WRITE.format(f"{what} is missing in the finding")


def cell(x):
    # a pipe would open a fifth column
    return spoken(re.sub(r"\s+", " ", re.sub(r"\s*\|\s*", ", ", str(x if x is not None else ""))).strip())


def where(f, t):
    spots = []
    for ev in [e for e in (f.get("evidence") or []) if isinstance(e, dict)][:3]:
        if ev.get("file"):
            s = f"`{ev['file']}`"
            m = re.match(r"\s*(\d+)\s*(?:-\s*(\d+))?", str(ev.get("lines") or ""))
            if m:
                s += " " + (t["lines"].format(a=m.group(1), b=m.group(2)) if m.group(2) else t["line"].format(a=m.group(1)))
        elif ev.get("url"):
            s = str(ev["url"]) + (f", {t['selector']} `{ev['selector']}`" if ev.get("selector") else "")
        else:
            continue
        spots.append(s)
    out = "; ".join(spots) or WRITE.format("location is missing in the finding")
    inst = f.get("instances")
    if isinstance(inst, dict) and isinstance(inst.get("count"), int) and inst["count"] > 1:
        out += ", " + t["instances"].format(n=inst["count"])
    return out


def first_sentence(f, t):
    crit = ", ".join(t["crit"].format(sc=w.get("sc"), name=w.get("name") or "", level=w.get("level") or "?")
                     for w in f.get("wcag") or [] if isinstance(w, dict)) or t["bp"]
    users = t["everyone"] if f.get("affects_all_users") else \
        ", ".join(t["users"].get(u, str(u)) for u in f.get("affected_users") or []) or "?"
    return t["first"].format(sev=t["sev"].get(f.get("severity"), f.get("severity") or "?"), crit=crit, users=users,
                             eff=t["effort_unit"].get(f.get("effort"), f.get("effort") or "?"),
                             conf=t["conf"].get(f.get("confidence"), f.get("confidence") or "?"))


def block(f, t, level="###", compact=False):
    """One finding, fields in the fixed order of the report template. Blank lines keep each field its own paragraph."""
    fix = f.get("fix") if isinstance(f.get("fix"), dict) else {}
    fixline = one(fix.get("summary"), "fix")
    if fix.get("location"):
        fixline += f" ({t['at']} {cell(fix['location'])})"
    if fix.get("framework_idiom") and not compact:
        fixline += " " + one(fix["framework_idiom"], "idiom")
    lines = [f"{level} {f['report_id']}. {cell(f.get('title'))}", "", first_sentence(f, t), "",
             f"{t['f_problem']}: {one(f.get('description'), 'problem')}", ""]
    if f["tier"] == 2 and not compact:
        lines += [f"{t['f_impact']}: {one(f.get('tier_rationale'), 'design impact')}", ""]
    lines += [f"{t['f_where']}: {where(f, t)}", "", f"{t['f_fix']}: {fixline}", ""]
    if compact:
        return lines
    if fix.get("code_before") or fix.get("code_after"):
        lines += ["```", f"[{t['before']}]", str(fix.get("code_before") or "").rstrip(),
                  f"[{t['after']}]", str(fix.get("code_after") or "").rstrip(), "```", ""]
    lines += [f"{t['f_watch']}: {one(fix['side_effects'], 'side effects') if fix.get('side_effects') else t['none']}", "",
              f"{t['f_verify']}: {one(f.get('verify'), 'verification steps')}", ""]
    return lines


def persona_notes(pdir: Path, src_to_rep: dict):
    """Per persona file: its title and the raw material for the three fields the template asks for."""
    notes = []
    for p in sorted(pdir.glob("*.md")) if pdir.is_dir() else []:
        title, sections, cur = p.stem, defaultdict(list), None
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("# ") and cur is None and title == p.stem:
                title = re.sub(r"\s+[—–-]\s+", ", ", line[2:].strip())
            elif line.startswith("## "):
                cur = line[3:].strip().lower()
            elif cur and line.strip():
                sections[cur].append(line.strip())
        pick = lambda key: " ".join(v for k, vs in sections.items() if key in k for v in vs)
        raw = f"narrative: {pick('own words')} / top frustrations: {pick('frustration')} / a 10 for me: {pick('make this a 10')}"
        raw = re.sub(r"\b([A-Z]{3}-\d{3})\b", lambda m: src_to_rep.get(m.group(1), m.group(1)), raw).replace("--", "-")
        notes.append((title, raw))
    return notes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace")
    ap.add_argument("--lang", default="en", help="report language code: en and nl ship with the skill, any other is "
                                                 "translated once from a labels file written into the workspace")
    a = ap.parse_args()
    ws = Path(a.workspace)
    t = load_labels(a.lang, ws)
    global TO1
    TO1 = t["to1"]
    data = json.loads((ws / "findings" / "_merged.json").read_text(encoding="utf-8"))
    dropped = [f.get("id") for f in data["findings"] if f.get("tier") not in (1, 2, 3)]
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
    src_to_rep = {s: rid for rid, v in ids.items() for s in v["source"]}
    to_rep = lambda text: re.sub(r"\b([A-Z]{3}-\d{3})\b", lambda m: src_to_rep.get(m.group(1), m.group(1)), text)
    sev = lambda f: t["sev"].get(f.get("severity"), f.get("severity"))
    eff = lambda f: t["effort_unit"].get(f.get("effort"), f.get("effort") or "?")
    by_tier = {tier: [f for f in findings if f["tier"] == tier] for tier in (1, 2, 3)}
    flag_of = lambda f: f" ({t['flag_blocker']})" if f.get("severity") == "blocker" else f" ({t['flag_all']})" if f.get("affects_all_users") else ""
    status_word = lambda s: re.sub(r"^(not-tested|pass|fail)\b", lambda m: t["status_word"].get(m.group(1), m.group(1)), s).replace("n/a", t["results"]["na"])

    # ---- the tables, built once and used by both outputs ----------------------------------
    counts_table = [f"| {t['tier']} | {t['findings']} | {t['highest']} | {t['effort']} |", "|---|---|---|---|"]
    for tier, fs in by_tier.items():
        highest = min(fs, key=lambda f: SEV.get(f.get("severity"), 9), default=None)
        counts_table.append(f"| {tier} | {len(fs)} | {sev(highest) if highest else t['none']} | {effort_total(fs, t)} |")
    overview, ownership = {}, {}
    for tier, fs in by_tier.items():
        rows = [f"| {t['id']} | {t['title']} | {t['severity']} | {t['effort']} |", "|---|---|---|---|"]
        for f in fs:
            flag = flag_of(f)
            own = f.get("fix", {}).get("ownership")
            mark = f" ({t['own'][own]})" if own in ("upstream", "accepted") else ""
            rows.append(f"| {f['report_id']}{mark} | {cell(f.get('title'))[:80]}{flag} | {sev(f)} | {eff(f)} |")
        overview[tier] = rows
        own_lines = []
        ups = [f for f in fs if f.get("fix", {}).get("ownership") == "upstream"]
        acc = [f for f in fs if f.get("fix", {}).get("ownership") == "accepted"]
        if ups:
            own_lines += [f"### {t['upstream_h']} ({len(ups)})", ""] + [f"- {f['report_id']}: {f.get('fix', {}).get('location') or '?'}" for f in ups] + [""]
        if acc:
            own_lines += [f"### {t['accepted_h']} ({len(acc)})", ""]
            for f in acc:
                ex = f.get("fix", {}).get("exception") or {}
                tool = f" ({ex.get('tool')} {ex.get('rule')} on {ex.get('selector')})" if ex.get("rule") else ""
                own_lines.append(f"- {f['report_id']}{tool}: {ex.get('reason') or f.get('fix', {}).get('summary') or '?'}")
            own_lines.append("")
        ownership[tier] = own_lines
    rows = persona_rows(ws / "personas", t)
    persona_table = [f"| {t['flow']} | {t['persona']} | {t['result']} | {t['obstacle']} |", "|---|---|---|---|"] + \
        [f"| {cell(flow)[:50]} | {name} | {res} | {cell(to_rep(obst))[:60]} |" for flow, name, res, obst in rows]
    cov, cov_counts, cov_table = ws / "coverage.md", "", []
    if cov.exists():
        lines = cov.read_text(encoding="utf-8").splitlines()
        cov_counts = next((l for l in lines if l.startswith("Counts:")), "")
        cov_table = [f"| {t['sc']} | {t['name']} | {t['status']} | {t['note']} |", "|---|---|---|---|"]
        for l in [l for l in lines if l.startswith("|")][2:]:
            c = [x.strip() for x in l.strip("|").split("|")]
            if len(c) >= 7:
                status = to_rep(c[4] + (f" ({c[5]})" if c[5] else ""))
                cov_table.append(f"| {c[0]} | {c[1]} | {status_word(status)} | {(c[6] or t['none'])[:70]} |")
    full_table = [f"| {t['id']} | {t['source']} | {t['severity']} | {t['location']} |", "|---|---|---|---|"] + \
        [f"| {f['report_id']} | {', '.join(ids[f['report_id']]['source'])} | {sev(f)} | {loc(f)[:70]} |" for f in findings]

    # ---- report-parts.md: the tables alone -------------------------------------------------
    out = ["# Report parts (generated; paste, don't retype)", "", "## Tier counts", ""] + counts_table
    for tier, fs in by_tier.items():
        out += ["", f"## Tier {tier} overview ({len(fs)})", ""] + overview[tier]
        if ownership[tier]:
            out += [""] + ownership[tier][:-1]
    if rows:
        out += ["", f"## Persona results ({len(rows)} rows)", ""] + persona_table
    if cov_table:
        out += ["", "## Appendix B: WCAG 2.2 A and AA coverage", "", cov_counts, ""] + cov_table
    out += ["", f"## Appendix C: full list ({len(findings)})", ""] + full_table
    (ws / "report-parts.md").write_text("\n".join(out) + "\n", encoding="utf-8")

    # ---- REPORT.draft.md: the whole report, gaps marked ------------------------------------
    project = ws.resolve().parent.name
    d = ["<!-- GENERATED DRAFT of the report. Copy it to REPORT.md, then:",
         "     1. write every part marked WRITE and delete the marker;",
         "     2. leave the finding text as it is: the agents wrote it in the report language. A finding in another language",
         "        is corrected in its findings file and rendered again, not translated here;",
         "     3. do not retype or reorder tables and finding blocks: edit them in place, and keep every report ID;",
         "     4. delete this comment and run lint_report.py on the report until it exits 0.",
         f"     Facts: generated {date.today().isoformat()}; {len(findings)} findings; "
         f"{len(data.get('problems') or [])} problems still listed in findings/_merged.md. -->", "",
         f"# {t['report']}: {project}", "",
         f"## {t['short']}", "",
         WRITE.format("five to eight plain sentences, no table and no list: what was audited, the score now and after each tier in words, "
                      "the single most important thing to fix, and how many days tier 1 costs"), "",
         f"## {t['summary']}", "",
         WRITE.format("one paragraph: the score now and after each tier, each with a one-sentence justification"), "",
         t["ann_counts"], ""] + counts_table + ["", f"**{t['top5']}**", ""]
    top = sorted(findings, key=lambda f: (f.get("severity") != "blocker", not f.get("affects_all_users"),
                                          SEV.get(f.get("severity"), 9), f["tier"], EFF.get(f.get("effort"), 9)))[:5]
    d += [f"{i}. " + t["top_line"].format(rid=f["report_id"], tier=f["tier"], eff=eff(f), title=cell(f.get("title"))) + flag_of(f)
          for i, f in enumerate(top, 1)]
    d += ["", WRITE.format("reorder the five above only if impact per effort says otherwise; then one closing paragraph: "
                           "date, commit, scope, stack, standard (WCAG 2.2 level A and AA) and method"), ""]
    delta = data.get("delta")
    if isinstance(delta, dict):
        fp_to = {str(f.get("fingerprint", "")).strip().lower(): f for f in findings}
        d += [f"## {t['changes']}", "", WRITE.format("the score then and now in words, and one sentence on what the team got right and what slipped back"), ""]
        for key in ("resolved", "still_open", "regressed", "new"):
            d += [f"### {t['delta_h'][key]} ({len(delta.get(key) or [])})", ""]
            d += [f"- {fp_to[fp]['report_id']}: {cell(fp_to[fp].get('title'))}" if fp in fp_to else f"- {fp}" for fp in delta.get(key) or []] or [t["nothing"]]
            d.append("")
    d += [f"## {t['howto']}", ""]
    for para in t["howto_p"]:
        d += [para, ""]
    positives = [x for xs in (data.get("positives") or {}).values() for x in xs if isinstance(x, str)]
    d += [f"## {t['works']}", "", WRITE.format("keep the three to eight most specific of these"), ""]
    d += [f"- {cell(x)}" for x in positives] or [t["nothing"]]
    d.append("")

    for tier in (1, 2):
        fs = by_tier[tier]
        d += [f"## {t['t' + str(tier)]}", "", t["tier_p"][str(tier)].format(n=len(fs)), ""]
        if not fs:
            continue
        d += [t["ann_tier"].format(n=len(fs)), ""] + overview[tier] + [""]
        full = [f for f in fs if f.get("severity") != "minor"]
        minor = [f for f in fs if f.get("severity") == "minor"]
        for f in full:
            d += block(f, t)
        if minor and len(fs) > 15:        # a long tier keeps its small items together, one heading level down
            d += [f"### {t['smaller']}", ""]
            for f in minor:
                d += block(f, t, level="####", compact=True)
        else:
            for f in minor:
                d += block(f, t, compact=True)
        colour = [f for f in fs if isinstance(f.get("colours"), dict) and f["colours"].get("fg")]
        if tier == 2 and colour:
            biggest = max((f["colours"].get("delta_e_ok") or 0 for f in colour), default=0)
            d += [f"### {t['tokens']}", "", t["delta_e"].format(d=biggest), "", t["ann_tokens"].format(n=len(colour)), "",
                  "| " + " | ".join(t["tok_cols"]) + " |", "|---|---|---|---|"]
            for f in colour:
                c = f["colours"]
                d.append(f"| {f['report_id']}: {cell(f.get('title'))[:50]} | {c.get('fg')} | {c.get('suggested_fg') or t['none']} | "
                         + t["and_then"].format(a=t["to1"].format(r=c.get("ratio", "?")), b=t["to1"].format(r=c.get("suggested_ratio", "?"))) + " |")
            d.append("")
        d += ownership[tier]

    fs = by_tier[3]
    d += [f"## {t['t3']}", "", t["tier_p"]["3"].format(n=len(fs)), "",
          WRITE.format("sort the items below into five H3 blocks in this fixed order: Design, Content, Features, Validation with users, "
                       "Process and governance. One list per block, one line per item: what, why (which users or criteria), rough effort. "
                       "Add the standing tier-3 advice (testing with disabled users, CI gate) where no finding covers it. No tables here"), ""]
    d += [f"- {f['report_id']}: {cell(f.get('title'))} ({sev(f)}; {eff(f)})" for f in fs] or [t["nothing"]]
    d += [""] + ownership[3]

    notes = persona_notes(ws / "personas", src_to_rep)
    d += [f"## {t['voice']}", "", t["voice_p"].format(names=", ".join(n for n, _ in notes) or t["none"]), ""]
    if rows:
        d += [t["ann_personas"].format(n=len(rows)), ""] + persona_table + [""]
    for name, raw in notes:
        d += [f"### {name}", "", WRITE.format("three or four sentences from the narrative, the top frustration with its report ID, and what would "
                                             "make it a 10; say so where this persona and an expert disagree. Source: " + raw), ""]

    lev = data.get("leverage_entries") or []
    d += [f"## {t['advice']}", ""]
    if lev:
        d += [WRITE.format("one introductory paragraph"), "", t["ann_advice"].format(n=len(lev)), "",
              "| " + " | ".join(t["adv_cols"]) + " |", "|---|---|---|---|"]
        d += [f"| {cell(e.get('location') or e.get('title'))[:60]} | {', '.join(sorted({src_to_rep.get(s, s) for s in e.get('resolves') or []}))} | "
              f"{t['effort_unit'].get(e.get('effort'), e.get('effort') or '?')} | {cell(e.get('note') or t['none'])[:90]} |" for e in lev]
    else:
        d.append(t["no_advice"])
    d += ["", WRITE.format("one list with the recommended lint, test and CI setup so fixes do not regress; and, if the project documents "
                           "an earlier accessibility claim, one sentence on what this audit found against it"), ""]

    low = [f for f in findings if f.get("confidence") == "low"]
    d += [f"## {t['verify_h']}", ""]
    d += [f"- {f['report_id']}: {cell(f.get('title'))}. {one(f.get('verify'), 'what to check')}" for f in low] or [t["nothing"]]

    d += ["", f"## {t['appendix']}", "", f"### {t['appx']['a']}", "",
          WRITE.format("what was static, what ran at runtime, what was automated, what was out of scope; use the lines below"), ""]
    for p in sorted((ws / "findings").glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            meta = json.loads(p.read_text(encoding="utf-8")).get("coverage") or {}
        except (ValueError, OSError, AttributeError):
            continue
        if isinstance(meta, dict) and meta:
            d.append("- " + t["method"].format(agent=p.stem, method=meta.get("method") or "?", n=len(meta.get("examined") or []),
                                               skipped="; ".join(str(x) for x in meta.get("not_examined") or []) or t["none"]))
    cc = data.get("coverage_counts") or {}
    d += ["", f"### {t['appx']['b']}", "", t["cov_counts"].format(p=cc.get("pass", 0), f=cc.get("fail", 0), nt=cc.get("not-tested", 0),
                                                              na=cc.get("n/a", 0)), "", t["ann_cov"], ""] + cov_table
    d += ["", f"### {t['appx']['c']}", "", t["ann_full"].format(n=len(findings)), ""] + full_table
    d += ["", f"### {t['appx']['d']}", "",
          WRITE.format("only if the user or the repository raised it (EN 301 549, European Accessibility Act, public sector); otherwise delete this block"), ""]
    draft = "\n".join(d) + "\n"
    (ws / "REPORT.draft.md").write_text(draft, encoding="utf-8")

    if dropped:
        print(f"!! {len(dropped)} findings have no valid tier and are in NO table or block: {', '.join(map(str, dropped))}; "
              "fix visual_impact in their findings file and merge again", file=sys.stderr)
    print(f"REPORT.draft.md: {len(findings)} finding blocks ({', '.join(f'T{k}: {v}' for k, v in sorted(counters.items()))}), "
          f"{draft.count('<!-- WRITE')} gaps left to write, {len(rows)} persona rows, coverage {'included' if cov.exists() else 'missing'}; "
          "report-parts.md and report-ids.json written")
    return 1 if dropped else 0


if __name__ == "__main__":
    sys.exit(main())
