#!/usr/bin/env python3
"""Deterministic bookkeeping for the audit workspace.

    python3 merge_findings.py <repo>/.a11y-audit --ownership <SKILL_DIR>/references/wcag-ownership.md [--previous <repo>/.a11y-audit/previous]

Reads  findings/<agent>.json (all experts), optionally personas/*.md (verdicts, flow results, new findings)
       and findings/_dedupe.json — the orchestrator's merge decisions: {"CANONICAL-ID": ["DUP-ID", ...], ...}
Writes findings/_merged.json   all findings, duplicates merged (exact fingerprint + _dedupe.json), tiers derived,
                               persona links and key-flow failures attached, leverage points attached, clusters listed
       findings/_merged.md     one line per finding (ID · tier · severity · title · location) + candidate-duplicate groups
       coverage.md             WCAG 2.2 A/AA matrix (55 criteria) from owners' sc_coverage, with counts and conflicts
       delta.md                with --previous: resolved / still open / regressed / new, matched on fingerprint
Prints a short summary. Pure standard library; never touches the repo.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SEVERITY_ORDER = {"blocker": 0, "critical": 1, "serious": 2, "moderate": 3, "minor": 4}
TIER_FROM_IMPACT = {"none": 1, "keyboard-only": 1, "preference-only": 1, "subtle": 2, "significant": 3}
REQUIRED = ("id", "title", "severity", "evidence", "fix")


def read_json(p: Path):
    """Parsed JSON, or None with a message on stderr. Agent output is machine-written text,
    so every shape of breakage here is expected rather than exceptional."""
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        print(f"!! {p.name}: unreadable ({type(e).__name__}: {e}); skipped", file=sys.stderr)
        return None


def load_findings(fdir: Path):
    agents = {}
    for p in sorted(fdir.glob("*.json")):
        if p.name.startswith("_"):
            continue
        data = read_json(p)
        if data is None:
            continue
        if not isinstance(data, dict):
            print(f"!! {p.name}: top level is {type(data).__name__}, expected an object; skipped", file=sys.stderr)
            continue
        if not isinstance(data.get("findings", []), list):
            print(f"!! {p.name}: 'findings' is not a list; treated as empty", file=sys.stderr)
            data["findings"] = []
        agents[p.stem] = data
    return agents


def parse_ownership(path: Path):
    owners = {}
    if not path.is_file():
        print(f"!! --ownership {path} does not exist; expected references/wcag-ownership.md", file=sys.stderr)
        return owners
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\|\s*(\d\.\d\.\d+)\s*\|\s*([^|]+?)\s*\|\s*(A{1,3})\s*\|\s*([\w-]+)\s*\|", line)
        if m:
            owners[m.group(1)] = {"name": m.group(2), "level": m.group(3), "owner": m.group(4)}
    return owners


def first_evidence(f):
    ev = f.get("evidence") or [{}]
    if isinstance(ev, str):
        return {"snippet": ev}
    if isinstance(ev, dict):
        return ev
    return ev[0] if ev and isinstance(ev[0], dict) else {}


def evidence_loc(f):
    ev = first_evidence(f)
    if ev.get("file"):
        return f"{ev['file']}:{ev.get('lines') or '?'}"
    if ev.get("url"):
        return f"{ev['url']} {ev.get('selector') or ''}".strip()
    return "?"


def norm_file(f):
    ev = first_evidence(f)
    return (ev.get("file") or ev.get("url") or "").strip().lower()


def line_range(f):
    ev = first_evidence(f)
    m = re.match(r"\s*(\d+)\s*(?:-\s*(\d+))?", str(ev.get("lines") or ""))
    if not m:
        return None
    a = int(m.group(1)); b = int(m.group(2) or a)
    return (min(a, b), max(a, b))


TIER_WORD = {"T1": 1, "T2": 2, "T3": 3, "1": 1, "2": 2, "3": 3, 1: 1, 2: 2, 3: 3}


def coerce_shape(f, agent: str, seq: int, problems: list):
    """Make one finding safe for every later stage, or return None to drop it.

    Everything here is a deviation an agent has actually produced: fix as a string,
    wcag as plain strings, a missing id. Each one used to end the whole merge in a
    traceback, which loses the other agents' work too."""
    if not isinstance(f, dict):
        problems.append(f"{agent}: finding {seq} is {type(f).__name__}, not an object; dropped")
        return None
    missing = [k for k in REQUIRED if k not in f]
    if missing:
        problems.append(f"{f.get('id') or '?'} ({agent}): missing {missing}")
    f = dict(f)
    if not isinstance(f.get("id"), str) or not f["id"].strip():
        f["id"] = f"{agent.upper()[:3] or 'UNK'}-x{seq:02d}"
        problems.append(f"{agent}: finding {seq} has no usable id; filed as {f['id']}")
    f["id"] = f["id"].strip()
    if "fingerprint" in f and not isinstance(f["fingerprint"], str):
        problems.append(f"{f['id']}: fingerprint is {type(f['fingerprint']).__name__}; converted to text")
        f["fingerprint"] = str(f["fingerprint"])
    if not isinstance(f.get("title"), str):
        f["title"] = str(f.get("title") or "(no title)")
    if not isinstance(f.get("fix"), dict):
        if f.get("fix") is not None:
            problems.append(f"{f['id']}: fix is {type(f['fix']).__name__}, not an object; kept as fix.summary")
            f["fix"] = {"summary": str(f["fix"])}
        else:
            f["fix"] = {}
    wcag = f.get("wcag")
    if isinstance(wcag, (str, dict)):
        wcag = [wcag]
    if not isinstance(wcag, list):
        if wcag is not None:
            problems.append(f"{f['id']}: wcag is {type(wcag).__name__}; ignored")
        wcag = []
    fixed = []
    for sc in wcag:
        if isinstance(sc, dict):
            fixed.append(sc)
        elif isinstance(sc, str) and re.match(r"\s*\d\.\d\.\d+", sc):
            fixed.append({"sc": sc.strip().split()[0]})
            problems.append(f"{f['id']}: wcag entry {sc!r} is a bare string; read as a criterion number")
        elif sc is not None:
            problems.append(f"{f['id']}: wcag entry {sc!r} unusable; ignored")
    f["wcag"] = fixed
    for key in ("evidence", "affected_users"):
        if not isinstance(f.get(key, []), list):
            problems.append(f"{f['id']}: {key} is {type(f[key]).__name__}, not a list; ignored")
            f[key] = []
    return f


def normalise_persona_finding(raw: dict, persona: str, problems: list, seq: int = 0) -> dict:
    """Personas drift from the schema; map the common deviations and flag them."""
    f = dict(raw)
    # seq, not len(problems): two id-less findings used to collide on one id, and the
    # clustering is keyed on id, so their links and severity floors hit the wrong finding.
    pid = f.get("id") or f"PER-{persona}-x{seq:03d}"
    f["id"] = pid
    f["agent"] = f"persona:{persona}"
    if isinstance(f.get("evidence"), str):
        f["evidence_text"] = f.pop("evidence")
    if "evidence" not in f or not f["evidence"]:
        ev = {}
        loc = f.pop("location", None)
        if loc:
            m = re.match(r"([^\s:(]+\.[a-z0-9]+)(?::(\d+(?:-\d+)?))?", str(loc))
            ev = {"file": m.group(1), "lines": m.group(2)} if m else {"file": str(loc)}
        if f.get("evidence_text"):
            ev["snippet"] = str(f.pop("evidence_text"))
        f["evidence"] = [ev] if ev else []
        problems.append(f"{pid}: persona finding used 'location' instead of evidence[]; converted")
    if isinstance(f.get("wcag"), str):
        f["wcag"] = [{"sc": sc} for sc in re.findall(r"\d\.\d\.\d+", f["wcag"])]
        problems.append(f"{pid}: wcag given as a string; converted")
    if isinstance(f.get("fix"), str):
        f["fix"] = {"summary": f["fix"]}
    if "visual_impact" not in f:
        t = TIER_WORD.get(f.pop("tier", None) or f.get("proposed_tier"))
        if t:
            f["visual_impact"] = {1: "none", 2: "subtle", 3: "significant"}[t]
            f["proposed_tier"] = t
            problems.append(f"{pid}: no visual_impact; derived from tier {t} — verify")
        else:
            problems.append(f"{pid}: no visual_impact and no tier")
    f.setdefault("fingerprint", re.sub(r"[^a-z0-9]+", "-", f.get("title", "").lower())[:40] + "@" + norm_file(f))
    f.setdefault("affected_users", [persona])
    f.setdefault("confidence", "medium")
    f["persona_origin"] = persona
    return f


def extract_json_blocks(text: str):
    """Pull JSON objects/arrays out of a markdown section, tolerating fences and trailing commas."""
    text = re.sub(r"```(?:json)?", "", text)
    text = text.strip()
    for candidate in (text, "[" + text.rstrip().rstrip(",") + "]"):
        try:
            data = json.loads(candidate)
            return data if isinstance(data, list) else [data]
        except json.JSONDecodeError:
            pass
    out = []
    for m in re.finditer(r"\{(?:[^{}]|\{[^{}]*\})*\}", text):
        try:
            out.append(json.loads(m.group(0)))
        except json.JSONDecodeError:
            pass
    return out


def parse_personas(pdir: Path, problems: list):
    """Return (links, new_findings, flow_failures).
    links: {finding_id: {"confirmed": [persona], "cited": [...], "disputed": [...]}}
    flow_failures: [{persona, flow, result, ids}] for failed / only-with-help rows."""
    links = defaultdict(lambda: {"confirmed": [], "cited": [], "disputed": []})
    new_findings, flow_failures = [], []
    if not pdir.is_dir():
        return links, new_findings, flow_failures
    for p in sorted(pdir.glob("*.md")):
        name = p.stem.replace("-user", "")
        section, buf = None, []
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines() + ["## end"]
        except OSError as e:
            problems.append(f"persona {name}: unreadable ({e}); skipped")
            continue
        for line in lines:
            h = line.strip().lower()
            if h.startswith("## "):
                if section == "new":
                    for seq, raw in enumerate(extract_json_blocks("\n".join(buf)), 1):
                        if isinstance(raw, dict):
                            new_findings.append(normalise_persona_finding(raw, name, problems, seq))
                buf = []
                if "confirmed" in h: section = "confirmed"
                elif "cited" in h or "cites" in h: section = "cited"
                elif "disputed" in h: section = "disputed"
                elif "new findings" in h: section = "new"
                elif "flow results" in h: section = "flows"
                else: section = None
                continue
            if section == "new":
                buf.append(line); continue
            if section == "flows" and line.startswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) >= 2 and re.search(r"\bfailed\b|only with help", cells[1], re.I):
                    ids = re.findall(r"\b[A-Z]{3}-\d{3}\b|\bPER-[a-z-]+-\d{3}\b", line)
                    flow_failures.append({"persona": name, "flow": cells[0], "result": cells[1], "ids": ids})
                continue
            if section in ("confirmed", "cited", "disputed") and line.lstrip().startswith("-"):
                m = re.search(r"\b[A-Z]{3}-\d{3}\b", line)   # first ID on the bullet is the subject
                if not m:
                    continue
                fid, kind = m.group(0), section
                if section == "confirmed" and re.search(r"\(cite[sd]?\)|\bcites\b", line, re.I):
                    kind = "cited"
                if name not in links[fid][kind]:
                    links[fid][kind].append(name)
    return links, new_findings, flow_failures


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="path to .a11y-audit")
    ap.add_argument("--ownership", required=True, help="path to references/wcag-ownership.md")
    ap.add_argument("--previous", help="re-audit: path holding the previous findings/_merged.json (e.g. .a11y-audit/previous)")
    a = ap.parse_args()
    ws = Path(a.workspace)
    fdir = ws / "findings"
    agents = load_findings(fdir)
    if not agents:
        print("no findings files found", file=sys.stderr)
        return 2
    owners = parse_ownership(Path(a.ownership))
    if not owners:
        print("no criteria parsed from --ownership; cannot build the coverage matrix", file=sys.stderr)
        return 2
    problems = []
    persona_links, persona_findings, flow_failures = parse_personas(ws / "personas", problems)
    dedupe = {}
    if (fdir / "_dedupe.json").exists():
        raw_dedupe = read_json(fdir / "_dedupe.json")
        if raw_dedupe is None:
            problems.append("_dedupe.json unreadable; no manual dedupe applied")
        elif not isinstance(raw_dedupe, dict):
            problems.append(f"_dedupe.json is {type(raw_dedupe).__name__}, expected "
                            '{"CANONICAL": ["DUP", ...]}; ignored')
        else:
            for canon, dups in raw_dedupe.items():
                if isinstance(dups, str):          # one id instead of a list of ids
                    dups = [dups]
                    problems.append(f"_dedupe.json[{canon!r}]: a single id, expected a list; read as one duplicate")
                if not isinstance(dups, list):
                    problems.append(f"_dedupe.json[{canon!r}] is {type(dups).__name__}; ignored")
                    continue
                dedupe[canon] = [str(d) for d in dups if isinstance(d, (str, int))]
    dup_to_canon = {d: c for c, ds in dedupe.items() for d in ds}

    all_findings = []
    for agent, data in agents.items():
        for seq, raw in enumerate(data.get("findings", []), 1):
            f = coerce_shape(raw, agent, seq, problems)
            if f is None:
                continue
            f["agent"] = agent
            vi = f.get("visual_impact")
            derived = TIER_FROM_IMPACT.get(vi)
            if derived is None:
                problems.append(f"{f.get('id')}: visual_impact missing/invalid ({vi!r}); tier left as proposed")
                f["tier"] = f.get("proposed_tier")
            else:
                f["tier"] = derived
                if f.get("proposed_tier") not in (None, derived):
                    problems.append(f"{f.get('id')}: proposed_tier {f.get('proposed_tier')} != tier {derived} from visual_impact {vi!r}; using {derived}")
            own = f["fix"].get("ownership")
            if own not in ("project", "override", "upstream", "accepted"):
                problems.append(f"{f['id']}: fix.ownership missing or invalid ({own!r}); assuming 'project'")
                f["fix"]["ownership"] = "project"
            if not f.get("fingerprint"):
                problems.append(f"{f['id']}: no fingerprint; generated from title+file")
                f["fingerprint"] = re.sub(r"[^a-z0-9]+", "-", f["title"].lower())[:40] + "@" + norm_file(f)
            all_findings.append(f)
    for seq, raw in enumerate(persona_findings, 1):
        f = coerce_shape(raw, raw.get("agent", "persona"), seq, problems)
        if f is None:
            continue
        f["tier"] = TIER_FROM_IMPACT.get(f.get("visual_impact")) or f.get("proposed_tier")
        if not f.get("fingerprint"):
            problems.append(f"{f['id']}: no fingerprint; generated from title+file")
            f["fingerprint"] = re.sub(r"[^a-z0-9]+", "-", f["title"].lower())[:40] + "@" + norm_file(f)
        all_findings.append(f)

    # --- merge: exact fingerprint, plus the orchestrator's _dedupe.json ---------------------
    by_fp = defaultdict(list)
    for f in all_findings:
        key = f["fingerprint"].strip().lower()
        canon = dup_to_canon.get(f["id"])
        if canon:
            key = "dedupe:" + canon
        elif f["id"] in dedupe:
            key = "dedupe:" + f["id"]
        by_fp[key].append(f)
    merged = []
    for fp, group in by_fp.items():
        canon_id = fp[len("dedupe:"):] if fp.startswith("dedupe:") else None
        group.sort(key=lambda x: (0 if x["id"] == canon_id else 1, SEVERITY_ORDER.get(x.get("severity"), 9), x["id"]))
        keep = dict(group[0])
        if len(group) > 1:
            keep["merged_from"] = [g["id"] for g in group[1:]]
            seen = {json.dumps(e, sort_keys=True) for e in keep.get("evidence", [])}
            for g in group[1:]:
                for e in g.get("evidence", []):
                    if json.dumps(e, sort_keys=True) not in seen:
                        keep.setdefault("evidence", []).append(e); seen.add(json.dumps(e, sort_keys=True))
                keep["affected_users"] = sorted(set(keep.get("affected_users", [])) | set(g.get("affected_users", [])))
                for sc in g.get("wcag", []):
                    if sc not in keep.get("wcag", []):
                        keep.setdefault("wcag", []).append(sc)
        merged.append(keep)

    # --- root-cause clusters: same file and line ranges overlapping or within PROXIMITY lines --
    PROXIMITY = 2
    parent = {f["id"]: f["id"] for f in merged}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    for i, f in enumerate(merged):
        for g in merged[i + 1:]:
            if not norm_file(f) or norm_file(f) != norm_file(g):
                continue
            r1, r2 = line_range(f), line_range(g)
            if r1 and r2 and (r1[0] <= r2[1] + PROXIMITY and r2[0] <= r1[1] + PROXIMITY):
                parent[find(f["id"])] = find(g["id"])
    clusters = defaultdict(list)
    for f in merged:
        clusters[find(f["id"])].append(f)
    cand = []
    for members in clusters.values():
        if len(members) > 1:
            members.sort(key=lambda x: (SEVERITY_ORDER.get(x.get("severity"), 9), x["id"]))
            cand.append({"ids": [m["id"] for m in members], "location": evidence_loc(members[0]),
                         "titles": [m["title"][:70] for m in members]})

    # --- leverage points from framework-maximizer: attached to their targets, not counted as findings --
    by_id = {f["id"]: f for f in merged}
    leverage_entries = []
    for f in merged:
        lev = f.get("leverage") or {}
        targets = [t for t in lev.get("finding_ids", []) if t in by_id or t in dup_to_canon]
        if not targets and f.get("kind") != "leverage":
            continue
        resolved_targets = []
        for t in targets:
            canon = dup_to_canon.get(t, t)
            if canon in by_id:
                by_id[canon].setdefault("leverage_points", []).append(
                    {"from": f["id"], "location": lev.get("location") or f.get("fix", {}).get("location"), "note": lev.get("note")})
                resolved_targets.append(canon)
        f["is_leverage_entry"] = True
        leverage_entries.append({"id": f["id"], "title": f.get("title"), "location": lev.get("location") or f.get("fix", {}).get("location"),
                                 "resolves": sorted(set(resolved_targets)), "note": lev.get("note")})
    merged = [f for f in merged if not f.get("is_leverage_entry")]
    leverage_entries.sort(key=lambda e: -len(e["resolves"]))

    # --- persona links --------------------------------------------------------------------
    for f in merged:
        ids = [f["id"]] + f.get("merged_from", [])
        for fid in ids:
            if fid in persona_links:
                for k, v in persona_links[fid].items():
                    if v:
                        f.setdefault("personas", {}).setdefault(k, [])
                        f["personas"][k] = sorted(set(f["personas"][k]) | set(v))

    # --- key-flow failures → severity floor (failed → blocker, only-with-help → critical) --------
    id_index = {}
    for f in merged:
        for fid in [f["id"]] + f.get("merged_from", []):
            id_index[fid] = f
    severity_upgrades = []
    for ff in flow_failures:
        floor = "blocker" if re.search(r"\bfailed\b", ff["result"], re.I) else "critical"
        for fid in ff["ids"]:
            f = id_index.get(fid)
            if not f:
                continue
            f.setdefault("key_flow_failures", []).append({"persona": ff["persona"], "flow": ff["flow"], "result": ff["result"]})
            if SEVERITY_ORDER.get(f.get("severity"), 9) > SEVERITY_ORDER[floor]:
                severity_upgrades.append(f"{f['id']}: {f.get('severity')} → {floor} ({ff['persona']} {ff['result']} on '{ff['flow']}')")
                f["severity_before_persona"] = f.get("severity")
                f["severity"] = floor

    merged.sort(key=lambda x: (x.get("tier") or 9, SEVERITY_ORDER.get(x.get("severity"), 9), x["id"]))

    # --- coverage matrix ------------------------------------------------------------------
    # Every file's sc_coverage is routed to the criterion's owner regardless of which file it arrived in
    # (lean mode merges lenses). A conflict is only two files disagreeing about the same criterion.
    cov_rows, conflicts, persona_notes = [], [], []
    reports = defaultdict(dict)          # sc -> {agent_file: status_dict}
    for agent, data in agents.items():
        sc_cov = data.get("sc_coverage") or {}
        if not isinstance(sc_cov, dict):
            problems.append(f"{agent}: sc_coverage is {type(sc_cov).__name__}, not an object; no coverage credited")
            continue
        for sc, st in sc_cov.items():
            if isinstance(st, dict):
                reports[sc][agent] = st
            else:
                problems.append(f"{agent}: sc_coverage[{sc!r}] is {type(st).__name__}, not an object; ignored")
    expert_fails, persona_cites = defaultdict(list), defaultdict(list)
    for f in merged:
        is_persona = str(f["id"]).startswith("PER-") or str(f.get("agent", "")).startswith("persona")
        for sc in f.get("wcag", []):
            if sc.get("sc"):
                (persona_cites if is_persona else expert_fails)[sc["sc"]].append(f["id"])
    counts = Counter()
    for sc, meta in owners.items():
        rep = reports.get(sc, {})
        statuses = {ag: st.get("status") for ag, st in rep.items() if st.get("status")}
        if not statuses:
            status, note, src = "not-tested", "no lens reported it", ""
        else:
            owner_file = next((ag for ag in rep if ag == meta["owner"] or meta["owner"] in (agents[ag].get("lenses") or [])), None)
            src = owner_file or next(iter(rep))
            status = statuses[src]
            note = rep[src].get("note", "")
            distinct = set(statuses.values())
            if len(distinct) > 1:
                conflicts.append(f"{sc}: files disagree — " + ", ".join(f"{ag}: {st}" for ag, st in statuses.items()) + f"; using {src}")
        ids = list((rep.get(src) or {}).get("findings", [])) if src else []
        for fid in expert_fails.get(sc, []):
            if fid not in ids:
                ids.append(fid)
        if ids and status in ("pass", "n/a"):
            conflicts.append(f"{sc}: owner says {status} but expert findings cite it: {ids}")
            status = "fail"
        if status == "fail" and not ids:
            conflicts.append(f"{sc}: owner marks fail but lists no finding IDs")
        if persona_cites.get(sc) and status != "fail":
            persona_notes.append(f"{sc} ({status}): cited by {', '.join(persona_cites[sc])} — the observation may be right while the criterion is not; the owner decides")
        counts[status] += 1
        cov_rows.append((sc, meta["name"], meta["level"], meta["owner"], status, ", ".join(ids), note))

    # --- write outputs --------------------------------------------------------------------
    cross_notes = [dict(n, agent=ag) for ag, d in agents.items() for n in (d.get("cross_lens_notes") or []) if isinstance(n, dict)]
    exceptions = [{"id": f["id"], "title": f.get("title"), **(f.get("fix", {}).get("exception") or {}),
                   "reason": (f.get("fix", {}).get("exception") or {}).get("reason") or f.get("fix", {}).get("summary")}
                  for f in merged if f.get("fix", {}).get("ownership") == "accepted"]
    out = {"findings": merged, "leverage_entries": leverage_entries, "root_cause_clusters": cand, "problems": problems,
           "cross_lens_notes": cross_notes, "accepted_exceptions": exceptions,
           "key_flow_failures": flow_failures, "severity_upgrades": severity_upgrades,
           "positives": {ag: d.get("positives", []) for ag, d in agents.items()},
           "coverage": {r[0]: {"status": r[4], "findings": r[5].split(", ") if r[5] else [], "owner": r[3]} for r in cov_rows},
           "coverage_counts": dict(counts), "coverage_conflicts": conflicts, "persona_citations": persona_notes}
    (fdir / "_merged.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    sev = Counter(f.get("severity") for f in merged)
    tiers = Counter(f.get("tier") for f in merged)
    lines = ["# Merged findings (one line each; open _merged.json for detail)", "",
             f"{len(all_findings)} raw → {len(merged)} after exact-fingerprint merge · tiers: " +
             ", ".join(f"T{t}: {n}" for t, n in sorted(tiers.items(), key=lambda x: str(x[0]))) +
             " · severity: " + ", ".join(f"{k}: {v}" for k, v in sorted(sev.items(), key=lambda x: SEVERITY_ORDER.get(x[0], 9))), ""]
    for f in merged:
        flags = []
        if f.get("affects_all_users"): flags.append("ALL-USERS")
        if f.get("merged_from"): flags.append("merged:" + "+".join(f["merged_from"]))
        p = f.get("personas", {})
        if p.get("confirmed"): flags.append("confirmed:" + "/".join(p["confirmed"]))
        if p.get("disputed"): flags.append("disputed:" + "/".join(p["disputed"]))
        if f.get("key_flow_failures"): flags.append("KEY-FLOW-" + ("FAILED" if f["severity"] == "blocker" else "HELP"))
        own = f.get("fix", {}).get("ownership")
        if own in ("upstream", "accepted"): flags.append(own.upper())
        if f.get("persona_origin"): flags.append("persona-new")
        lines.append(f"{f['id']} · T{f.get('tier')} · {f.get('severity')} · {f.get('title')} · {evidence_loc(f)}"
                     + (f" · [{' '.join(flags)}]" if flags else ""))
    if leverage_entries:
        lines += ["", "## Leverage points (framework-maximizer; ranked by findings resolved; not counted as findings)", ""]
        lines += [f"- {e['id']} · resolves {', '.join(e['resolves']) or 'none'} · {e['location']} · {e['title'][:70]}" for e in leverage_entries]
    if cand:
        lines += ["", f"## Root-cause clusters (same file, lines within {PROXIMITY}; orchestrator decides what to merge)", ""]
        for c in cand:
            lines.append(f"- {' + '.join(c['ids'])} @ {c['location']}")
            lines += [f"    · {t}" for t in c["titles"]]
    if severity_upgrades:
        lines += ["", "## Severity floors from persona key-flow results", ""] + [f"- {u}" for u in severity_upgrades]
    if cross_notes:
        lines += ["", "## Cross-lens notes (observations outside a lens; the owner decides whether they are findings)", ""]
        lines += [f"- {n.get('sc', '?')} · {n.get('location', '?')} · {n.get('note', '')} ({n['agent']})" for n in cross_notes]
    if exceptions:
        lines += ["", "## Accepted exceptions (ownership: accepted)", ""]
        lines += [f"- {e['id']} · {e.get('tool', '')} {e.get('rule', '')} {e.get('selector', '')} · {e.get('reason', '')}".replace("  ", " ") for e in exceptions]
    if problems:
        lines += ["", "## Schema problems", ""] + [f"- {p}" for p in problems]
    (fdir / "_merged.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    cov = ["# WCAG 2.2 A/AA coverage (55 criteria)", "",
           "Counts: " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())), "",
           "| SC | Name | Level | Owner | Status | Findings | Note |", "|---|---|---|---|---|---|---|"]
    cov += [f"| {sc} | {n} | {lv} | {ow} | {st} | {ids} | {note} |" for sc, n, lv, ow, st, ids, note in cov_rows]
    if conflicts:
        cov += ["", "## Conflicts to resolve", ""] + [f"- {c}" for c in conflicts]
    if persona_notes:
        cov += ["", "## Persona observations touching criteria the owner passed (advisory, not conflicts)", ""] + [f"- {n}" for n in persona_notes]
    (ws / "coverage.md").write_text("\n".join(cov) + "\n", encoding="utf-8")

    # --- re-audit delta -------------------------------------------------------------------
    if a.previous:
        prev_path = Path(a.previous) / "findings" / "_merged.json"
        if not prev_path.exists():
            prev_path = Path(a.previous) / "_merged.json"
        if prev_path.exists():
            prev = read_json(prev_path)
            if not isinstance(prev, dict):
                problems.append(f"previous {prev_path.name} unreadable or not an object; no delta written")
                prev = None
        if prev_path.exists() and prev is not None:
            prev_fps = {f["fingerprint"].strip().lower(): f for f in prev.get("findings", []) if f.get("fingerprint")}
            prev_resolved = {fp.lower() for fp in (prev.get("delta") or {}).get("resolved", [])}
            cur_fps = {f["fingerprint"].strip().lower(): f for f in merged}
            resolved = sorted(fp for fp in prev_fps if fp not in cur_fps)
            still_open = sorted(fp for fp in prev_fps if fp in cur_fps)
            new = sorted(fp for fp in cur_fps if fp not in prev_fps and fp not in prev_resolved)
            regressed = sorted(fp for fp in cur_fps if fp in prev_resolved)
            for f in merged:
                fp = f["fingerprint"].strip().lower()
                f["delta"] = "regressed" if fp in regressed else "still open" if fp in still_open else "new"
            out["delta"] = {"resolved": resolved, "still_open": still_open, "regressed": regressed, "new": new}
            (fdir / "_merged.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
            dl = ["# Re-audit delta (matched on fingerprint)", "",
                  f"resolved: {len(resolved)} · still open: {len(still_open)} · regressed: {len(regressed)} · new: {len(new)}", ""]
            for title, fps, src in (("Resolved", resolved, prev_fps), ("Regressed", regressed, cur_fps),
                                    ("Still open", still_open, cur_fps), ("New", new, cur_fps)):
                dl += [f"## {title}", ""] + [f"- {src[fp]['id']} · {src[fp].get('title')} · `{fp}`" for fp in fps] + [""]
            dl += ["Verify every 'resolved' entry in code before reporting it: an absent fingerprint can also mean the agent chose a different slug this run."]
            (ws / "delta.md").write_text("\n".join(dl), encoding="utf-8")
            print(f"delta: resolved {len(resolved)}, still open {len(still_open)}, regressed {len(regressed)}, new {len(new)}")
        else:
            problems.append(f"--previous given but {prev_path} not found")

    print(f"{len(all_findings)} raw findings from {len(agents)} agents (+{len(persona_findings)} from personas) → {len(merged)} merged; "
          f"{len(cand)} root-cause clusters; coverage {dict(counts)}; {len(conflicts)} conflicts; {len(problems)} schema problems")
    all_users = [f["id"] for f in merged if f.get("affects_all_users")]
    if all_users:
        print("affects all users: " + ", ".join(all_users))
    if severity_upgrades:
        print(f"{len(severity_upgrades)} severity floor(s) applied from persona key-flow failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
