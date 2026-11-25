#!/usr/bin/env python3
"""Deterministic bookkeeping for the audit workspace.

    python3 merge_findings.py <repo>/.a11y-audit --ownership <SKILL_DIR>/references/wcag-ownership.md [--previous <repo>/.a11y-audit/previous]

Reads  findings/<agent>.json (all experts), optionally personas/*.md (verdicts, flow results, new findings)
       and findings/_dedupe.json — the orchestrator's merge decisions: {"CANONICAL-ID": ["DUP-ID", ...], ...}
Writes findings/_merged.json   all findings, duplicates merged (exact fingerprint + _dedupe.json), tiers derived,
                               persona links and key-flow failures attached, leverage points attached, clusters listed
       findings/_merged.md     one line per finding (ID · tier · severity · title · location) + candidate-duplicate groups
       coverage.md             WCAG 2.2 A/AA matrix (55 criteria) from owners' sc_coverage, with counts and conflicts
       delta.md                with --previous: resolved / not reported again / still open / regressed / new, matched on
                               fingerprint and on findings/_delta-map.json
Checks what a finding claims against what a script can look up: the cited file, lines and snippet
exist in the repository; the criterion is a WCAG 2.2 A or AA one, with its name and level taken from the
ownership table; stated contrast ratios are recomputed. What does not hold and needs a decision goes into
"problems"; what the merge could settle itself (a level corrected, a shape converted, a default assumed)
goes into "notes", so that the length of the problem list means something.
Prints a short summary. Pure standard library; reads the repo, never writes to it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contrast import parse as parse_colour, ratio as contrast_ratio  # noqa: E402
from labels import flow_result  # noqa: E402

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


def load_previous(prev_dir: Path):
    """(the merge of the earlier audit as an object, why not) for a re-audit; the object is None when it cannot be used.
    A bare list of findings, which is what an early version of this skill wrote, is that audit's findings without a delta."""
    path = prev_dir / "findings" / "_merged.json"
    if not path.exists():
        path = prev_dir / "_merged.json"
    if not path.exists():
        return None, f"--previous given but {path} not found; no delta written"
    data = read_json(path)
    if isinstance(data, list):
        data = {"findings": data}
    if not isinstance(data, dict):
        return None, f"previous {path.name} unreadable or not an object; no delta written"
    data["findings"] = [f for f in data.get("findings") or [] if isinstance(f, dict)] if isinstance(data.get("findings"), list) else []
    return data, ""


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


def tiers_of(f: dict):
    """(tier that follows from visual_impact, tier the agent proposed): each 1, 2, 3 or None.
    Agents write "T2" or "2" for a tier; left as text it used to crash the sort further down."""
    vi, pt = f.get("visual_impact"), f.get("proposed_tier")
    return (TIER_FROM_IMPACT.get(vi) if isinstance(vi, str) else None,
            TIER_WORD.get(pt) if isinstance(pt, (str, int)) else None)


# the lenses whose file has a "With a runtime" list: checks that reading code does not answer
RUNTIME_LENSES = {"keyboard-focus", "visual-perception", "forms-input", "dynamic-content"}


def cites(f: dict, sc, path: str) -> bool:
    """True when the finding cites this criterion with evidence in this file."""
    return (any(isinstance(w, dict) and str(w.get("sc")) == str(sc) for w in f.get("wcag") or [])
            and any(isinstance(e, dict) and str(e.get("file") or "").removeprefix("./") == path for e in f.get("evidence") or []))


def from_maximizer(f: dict) -> bool:
    # by its file, and by the prefix its brief gives it: an entry without an ID gets one made from the file name
    return f.get("agent") == "framework-maximizer" or str(f.get("id")).startswith("FWK")


class Log(list):
    """What the merge reports back. append() is for what needs a decision from the orchestrator: content was
    lost, a claim does not hold, two fields contradict each other, or a value had to be guessed. note() is for
    what the merge settled itself, from data it could look up or by a fixed conversion, and only wants to be seen."""

    def __init__(self):
        super().__init__()
        self.notes = []

    def note(self, msg: str) -> None:
        self.notes.append(msg)


def coerce_shape(f, agent: str, seq: int, problems: Log):
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
        problems.note(f"{agent}: finding {seq} has no usable id; filed as {f['id']}")
    f["id"] = f["id"].strip()
    if "fingerprint" in f and not isinstance(f["fingerprint"], str):
        problems.note(f"{f['id']}: fingerprint is {type(f['fingerprint']).__name__}; converted to text")
        f["fingerprint"] = str(f["fingerprint"])
    if not isinstance(f.get("title"), str):
        f["title"] = str(f.get("title") or "(no title)")
    if not isinstance(f.get("fix"), dict):
        if f.get("fix") is not None:
            problems.note(f"{f['id']}: fix is {type(f['fix']).__name__}, not an object; kept as fix.summary")
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
            problems.note(f"{f['id']}: wcag entry {sc!r} is a bare string; read as a criterion number")
        elif sc is not None:
            problems.append(f"{f['id']}: wcag entry {sc!r} unusable; ignored")
    f["wcag"] = fixed
    for key in ("evidence", "affected_users"):
        if not isinstance(f.get(key, []), list):
            problems.append(f"{f['id']}: {key} is {type(f[key]).__name__}, not a list; ignored")
            f[key] = []
    return f


def title_fingerprint(f: dict) -> str:
    """A fingerprint for a finding that came without one: a slug of its title at its file. A title in a script without
    Latin letters leaves no slug; the finding's own ID stands in then, so that two such findings are not taken for one."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(f.get("title") or "").lower()).strip("-")[:40]
    return (slug or str(f.get("id") or "finding").lower()) + "@" + norm_file(f)


def squash(s: str) -> str:
    """Backslashes dropped, so a snippet quoted from HTML inside a C++ or JS string still matches the escaped
    source. Whitespace dropped next to punctuation, so code an agent reflowed onto one line still matches the
    wrapped original, but kept as one space between two words: class="a b" is not class="ab"."""
    s = re.sub(r"\s+", " ", s.replace("\\", "")).strip()
    return re.sub(r"(?<=\W) | (?=\W)", "", s)


def verify_claims(f: dict, owners: dict, repo: Path, problems: Log) -> None:
    """Hold a finding against what can be looked up instead of trusted.

    A language model wrote these fields. It misremembers levels (2.4.9 as level A), cites
    lines it never opened and does contrast arithmetic in its head. None of that needs
    judgement to catch, so none of it should reach the orchestrator unflagged."""
    fid = f["id"]
    persona = bool(f.get("persona_origin"))     # its criteria are advisory (personas/_protocol.md): settled here, not asked about

    # Criterion: the ownership table is the authority on which criteria count and on their names.
    for sc in f["wcag"]:
        m = re.search(r"\d\.\d\.\d+", str(sc.get("sc") or ""))
        num = m.group(0) if m else str(sc.get("sc") or "?")
        sc["sc"] = num
        meta = owners.get(num)
        if meta is None and persona:
            problems.note(f"{fid}: {num} is not a WCAG 2.2 level A or AA criterion; a persona's citation is advisory, left out")
            continue
        if meta is None:
            problems.append(f"{fid}: {num} is not a WCAG 2.2 level A or AA criterion (AAA, obsolete or mistyped); "
                            "cite the A or AA criterion if one applies, it is what the coverage matrix counts")
            continue
        if sc.get("level") not in (None, meta["level"]):
            problems.note(f"{fid}: {num} given as level {sc['level']}, it is level {meta['level']}; corrected")
        sc["name"], sc["level"] = meta["name"], meta["level"]
    if persona:
        f["wcag"] = [sc for sc in f["wcag"] if sc["sc"] in owners]
        if not f["wcag"] and f.get("best_practice_only") is not True:
            f["best_practice_only"] = True
            problems.note(f"{fid}: a persona finding without a level A or AA criterion; kept as an observation outside the coverage matrix")
    # a leverage entry of the maximizer is a place to fix things, not a finding: a lint layer or a CI job fails no criterion
    if not f["wcag"] and f.get("best_practice_only") is not True and not (f.get("kind") == "leverage" and from_maximizer(f)):
        problems.append(f"{fid}: no WCAG criterion and not marked best_practice_only; cite one or set the marker")

    # Evidence: the file, the lines and the snippet have to exist. URL-and-selector evidence is runtime, not checked.
    for ev in f.get("evidence") or []:
        if not isinstance(ev, dict) or not ev.get("file"):
            continue
        rel = re.sub(r":\d+(-\d+)?$", "", str(ev["file"]).strip())   # "index.html:12" is a common slip
        path = (repo / rel).resolve()
        if not path.is_relative_to(repo) or not path.is_file():
            problems.append(f"{fid}: evidence file {rel!r} not found in the repository")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        total = text.count("\n") + 1
        m = re.match(r"\s*(\d+)\s*(?:-\s*(\d+))?", str(ev.get("lines") or ""))
        if m and max(int(m.group(1)), int(m.group(2) or 0)) > total:
            problems.append(f"{fid}: evidence lines {ev['lines']} are past the end of {rel} ({total} lines)")
        if isinstance(ev.get("snippet"), str):
            hay = squash(text)
            # an agent may abbreviate with an ellipsis; every part it did quote must be there
            # (fragments under 8 characters as written say too little to look up)
            parts = [squash(part) for part in re.split(r"…|\.\.\.", ev["snippet"]) if len(" ".join(part.split())) >= 8]
            gone = [part for part in parts if part not in hay]
            if gone:
                problems.append(f"{fid}: snippet not found in {rel}: {gone[0][:60]!r}")

    # Contrast: recompute, never trust the stated ratio.
    col = f.get("colours")
    if isinstance(col, dict) and col.get("fg") and col.get("bg"):
        for fg_key, ratio_key in (("fg", "ratio"), ("suggested_fg", "suggested_ratio")):
            if not col.get(fg_key):
                continue
            try:
                real = round(contrast_ratio(parse_colour(str(col[fg_key])), parse_colour(str(col["bg"]))), 2)
            except ValueError as e:
                problems.append(f"{fid}: colours.{fg_key} cannot be measured ({e})")
                continue
            stated = col.get(ratio_key)
            if isinstance(stated, (int, float)) and abs(stated - real) > 0.05:
                problems.note(f"{fid}: colours.{ratio_key} stated as {stated}, {col[fg_key]} on {col['bg']} "
                                f"measures {real}; corrected")
            col[ratio_key] = real
        need = col.get("required")
        if isinstance(need, (int, float)):
            if isinstance(col.get("ratio"), float) and col["ratio"] >= need:
                problems.append(f"{fid}: measured contrast {col['ratio']} already meets the required {need}; "
                                "this may not be a failure")
            if isinstance(col.get("suggested_ratio"), float) and col["suggested_ratio"] < need:
                problems.append(f"{fid}: the suggested colour reaches {col['suggested_ratio']}, short of the required {need}")


def normalise_persona_finding(raw: dict, persona: str, problems: Log, seq: int = 0) -> dict:
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
            ev = {"file": m.group(1), "lines": m.group(2)} if m else {"url": str(loc)}   # a place ("the contact page"), not a file to look up
        if f.get("evidence_text"):
            ev["observation"] = str(f.pop("evidence_text"))    # a persona's words, not a quote the claim check can look up
        f["evidence"] = [ev] if ev else []
        problems.note(f"{pid}: persona finding used 'location' instead of evidence[]; converted")
    if isinstance(f.get("wcag"), str):
        f["wcag"] = [{"sc": sc} for sc in re.findall(r"\d\.\d\.\d+", f["wcag"])]
        problems.note(f"{pid}: wcag given as a string; converted")
    if isinstance(f.get("fix"), str):
        f["fix"] = {"summary": f["fix"]}
    if "visual_impact" not in f:
        t = TIER_WORD.get(f.pop("tier", None) or f.get("proposed_tier"))
        if t:
            f["visual_impact"] = {1: "none", 2: "subtle", 3: "significant"}[t]
            f["proposed_tier"] = t
            problems.note(f"{pid}: no visual_impact; derived from tier {t}")
        else:
            problems.append(f"{pid}: no visual_impact and no tier")
    f.setdefault("fingerprint", title_fingerprint(f))
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


def parse_personas(pdir: Path, problems: Log):
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
                elif "flow results" in h: section, rows_seen = "flows", 0
                else: section = None
                continue
            if section == "new":
                buf.append(line); continue
            if section == "flows" and line.startswith("|"):
                rows_seen += 1
                cells = [c.strip() for c in line.strip("|").split("|")]
                if rows_seen <= 2 or len(cells) < 2:    # the header row and the rule under it
                    continue
                kind = flow_result(cells[1])
                if kind in ("failed", "help"):
                    ids = re.findall(r"\b[A-Z]{3}-\d{3}\b|\bPER-[a-z-]+-\d{3}\b", line)
                    flow_failures.append({"persona": name, "flow": cells[0], "result": cells[1], "ids": ids, "floor": "blocker" if kind == "failed" else "critical"})
                elif kind is None:
                    problems.append(f"persona {name}: flow '{cells[0]}' has the result '{cells[1]}', which is none of the six scores of the persona "
                                    f"protocol, so it cannot be told whether the flow failed; write the score in that row of personas/{p.name} as the protocol spells it")
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
    ap.add_argument("--repo", help="directory that evidence paths are relative to (default: the parent of the workspace); "
                                   "set it when the audit scope is a subdirectory such as apps/web")
    a = ap.parse_args()
    ws = Path(a.workspace)
    repo = Path(a.repo).resolve() if a.repo else ws.resolve().parent
    fdir = ws / "findings"
    agents = load_findings(fdir)
    if not agents:
        print("no findings files found", file=sys.stderr)
        return 2
    owners = parse_ownership(Path(a.ownership))
    if not owners:
        print("no criteria parsed from --ownership; cannot build the coverage matrix", file=sys.stderr)
        return 2
    problems = Log()
    prev = None
    if a.previous:      # looked at before anything is written, so that a problem with it is in the files and not only on stderr
        prev, why_not = load_previous(Path(a.previous))
        if prev is None:
            problems.append(why_not)
            print(f"!! {why_not}", file=sys.stderr)
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
                    problems.note(f"_dedupe.json[{canon!r}]: a single id, expected a list; read as one duplicate")
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
            verify_claims(f, owners, repo, problems)
            vi = f.get("visual_impact")
            derived, proposed = tiers_of(f)
            if derived is None:
                problems.append(f"{f.get('id')}: visual_impact missing/invalid ({vi!r}); tier left as proposed"
                                + ("" if proposed else f", but proposed_tier {f.get('proposed_tier')!r} is not a tier either: "
                                                       "this finding is in no tier and will be in no table"))
                f["tier"] = proposed
            else:
                f["tier"] = derived
                if proposed not in (None, derived):
                    problems.append(f"{f.get('id')}: proposed_tier {f.get('proposed_tier')} != tier {derived} from visual_impact {vi!r}; using {derived}, but one of the two fields is wrong: correct it")
            own = f["fix"].get("ownership")
            if own not in ("project", "override", "upstream", "accepted"):
                problems.append(f"{f['id']}: fix.ownership missing or invalid ({own!r}); 'project' is assumed, which is wrong for vendored code: state it")
                f["fix"]["ownership"] = "project"
            if not f.get("fingerprint"):
                problems.note(f"{f['id']}: no fingerprint; generated from title+file")
                f["fingerprint"] = title_fingerprint(f)
            all_findings.append(f)
    for seq, raw in enumerate(persona_findings, 1):
        f = coerce_shape(raw, raw.get("agent", "persona"), seq, problems)
        if f is None:
            continue
        verify_claims(f, owners, repo, problems)
        derived, proposed = tiers_of(f)
        f["tier"] = derived or proposed
        if not f.get("fingerprint"):
            problems.note(f"{f['id']}: no fingerprint; generated from title+file")
            f["fingerprint"] = title_fingerprint(f)
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
                if not str(keep.get("tier_rationale") or "").strip() and g.get("tier_rationale"):
                    keep["tier_rationale"] = g["tier_rationale"]     # the duplicate said what changes visibly; keep its words
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
                                 "resolves": sorted(set(resolved_targets)), "note": lev.get("note"),
                                 "effort": f.get("effort")})
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
        floor = ff["floor"]
        # The floor reaches a finding only through the IDs in the flow's row. A row without one that exists used to
        # pass in silence, and the finding that stopped the persona kept the severity its expert gave it.
        for fid in ff["ids"]:
            if fid not in id_index:
                problems.append(f"persona {ff['persona']}: the row of flow '{ff['flow']}' names {fid}, which is not a finding (dropped, or "
                                f"mistyped); take it out of that row in personas/ or put the right ID there")
        if not any(fid in id_index for fid in ff["ids"]):
            problems.append(f"persona {ff['persona']}: flow '{ff['flow']}' is '{ff['result']}' but its row names no finding, so no severity "
                            f"floor is applied; put the ID of the finding that stopped the persona in the last column of that row "
                            f"in personas/, taken from its trace, or file the finding if nobody did, or correct the result if the "
                            f"trace does not hold up")
        for fid in ff["ids"]:
            f = id_index.get(fid)
            if not f:
                continue
            f.setdefault("key_flow_failures", []).append({"persona": ff["persona"], "flow": ff["flow"], "result": ff["result"]})
            if SEVERITY_ORDER.get(f.get("severity"), 9) > SEVERITY_ORDER[floor]:
                severity_upgrades.append(f"{f['id']}: {f.get('severity')} → {floor} ({ff['persona']} {ff['result']} on '{ff['flow']}')")
                f["severity_before_persona"] = f.get("severity")
                f["severity"] = floor

    # The report gives a tier-2 finding a line on what changes visibly, except in the short blocks of minor ones. Asked
    # for here, after the floors have set the severity, and not found at the end as a gap in the rendered report.
    for f in merged:
        rationale = f.get("tier_rationale")
        if f.get("tier") == 2 and f.get("severity") != "minor" and not (isinstance(rationale, str) and rationale.strip()):
            problems.append(f"{f['id']}: tier 2 without tier_rationale, so the report has no design impact to show; "
                            f"say in its findings file what a sighted user will see change")

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
            note = rep[src].get("note") or rep[src].get("reason") or ""     # agents write either key
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

    # --- re-audit delta -------------------------------------------------------------------
    # A fingerprint is a slug an agent chose, so the same problem can come back under another one. Only an exact
    # match is settled here. The rest is put to the orchestrator: an earlier finding that nobody filed again is "not
    # reported again" until findings/_delta-map.json says which finding of this run it is, or that it is fixed.
    delta = None        # worked out before anything is written, so that what is wrong with the map is in the files
    if a.previous:
        if prev is not None:
            def key(fp):
                return str(fp).strip().lower()
            earlier = {key(f["fingerprint"]): f for f in prev["findings"] if f.get("fingerprint")}
            was = prev.get("delta") if isinstance(prev.get("delta"), dict) else {}
            was_resolved, was_unreported = ({key(fp) for fp in (was.get(k) if isinstance(was.get(k), list) else [])} for k in ("resolved", "not_reported"))
            if "not_reported" not in was:       # a delta from before that list existed: its "resolved" only meant "not filed again"
                was_resolved, was_unchecked = set(), was_resolved
            else:
                was_unchecked = set()
            # What the earlier audit already did not see again is still not seen until it is matched, found or checked:
            # it stays on the list, with the title that audit kept for it.
            titles = was.get("earlier") if isinstance(was.get("earlier"), dict) else {}
            for fp in sorted(was_unreported - set(earlier)):
                kept = titles.get(fp) if isinstance(titles.get(fp), dict) else {}
                earlier[fp] = {"fingerprint": fp, "id": kept.get("id"), "title": kept.get("title")}
            cur = {key(f["fingerprint"]): f for f in merged}
            same, fixed = {}, set()         # earlier fingerprint -> the finding of this run it is; the ones checked to be fixed
            raw_map = read_json(fdir / "_delta-map.json") if (fdir / "_delta-map.json").exists() else {}
            if not isinstance(raw_map, dict):
                problems.append("_delta-map.json unreadable or not an object; no match from it applied")
                raw_map = {}
            for old, target in raw_map.items():
                hit = cur.get(key(target)) or id_index.get(str(target).strip())
                if key(old) not in earlier:
                    problems.append(f"_delta-map.json: {old!r} is no fingerprint of the earlier audit")
                elif key(target) == "resolved" and key(old) in cur:
                    problems.append(f"_delta-map.json: {old!r} is called resolved, but {cur[key(old)]['id']} of this run has that fingerprint")
                elif key(target) == "resolved":
                    fixed.add(key(old))
                elif key(old) in cur:
                    problems.append(f"_delta-map.json: {old!r} needs no entry, {cur[key(old)]['id']} of this run has that fingerprint; take it out")
                elif hit is None:
                    problems.append(f"_delta-map.json: {old!r} points at {target!r}, which is neither a finding of this run nor \"resolved\"")
                else:
                    same[key(old)] = hit
            open_now = {fp for fp in cur if fp in earlier or fp in was_unchecked} | {key(f["fingerprint"]) for f in same.values()}
            regressed = sorted(fp for fp in cur if fp in was_resolved and fp not in open_now)
            still_open = sorted(open_now)
            new = sorted(fp for fp in cur if fp not in open_now and fp not in regressed)
            gone = [fp for fp in earlier if fp not in cur and fp not in same]
            resolved, not_reported = sorted(fp for fp in gone if fp in fixed), sorted(fp for fp in gone if fp not in fixed)
            for f in merged:
                fp = key(f["fingerprint"])
                f["delta"] = "regressed" if fp in regressed else "still open" if fp in open_now else "new"
            delta = {"resolved": resolved, "not_reported": not_reported, "still_open": still_open, "regressed": regressed, "new": new,
                            "earlier": {fp: {"id": earlier[fp].get("id"), "title": earlier[fp].get("title")} for fp in resolved + not_reported},
                            "matched": {old: key(f["fingerprint"]) for old, f in sorted(same.items())}}

            def place(f, fp):
                try:
                    return norm_file(f) or fp.split("@", 1)[-1].split(":")[0]
                except (AttributeError, TypeError):
                    return fp.split("@", 1)[-1].split(":")[0]

            def criteria(f):        # of a finding that may come from any earlier version, so of any shape
                cited = f.get("wcag") if isinstance(f.get("wcag"), list) else []
                return {w["sc"] for w in cited if isinstance(w, dict) and isinstance(w.get("sc"), str)}

            def words(fp):
                return set(re.split(r"[^a-z0-9]+", fp.split("@")[0])) - {"", "no", "not", "missing", "without", "the", "a", "of", "and", "for", "in", "on"}

            def candidates(old_fp):
                """Findings of this run that nobody matched yet and that may be the same problem under another slug:
                they share two of criterion, file and a word of the slug. At most three, the likeliest first."""
                o, found = earlier[old_fp], []
                for fp in new:
                    why = [w for w, yes in (("same criterion", criteria(o) & criteria(cur[fp])), ("same file", place(o, old_fp) == place(cur[fp], fp)),
                                            ("a slug word in common", words(old_fp) & words(fp))) if yes]
                    if len(why) >= 2:
                        found.append((-len(why), fp, why))
                return sorted(found)[:3]

            def line(f, fp):
                return f"- {f.get('id')} · {f.get('title')} · `{fp}`"
            was_called = defaultdict(list)     # two earlier findings may have become one
            for old_fp, fp in delta["matched"].items():
                was_called[fp].append(old_fp)
            dl = ["# Re-audit delta", "",
                  f"resolved: {len(resolved)} · not reported again: {len(not_reported)} · still open: {len(still_open)} · regressed: {len(regressed)} · new: {len(new)}", "",
                  f"## Not reported again ({len(not_reported)})", ""]
            if not_reported:
                dl += ["Nobody filed these this time. That is not the same as fixed: an agent may have chosen another slug for the same problem, or not have looked. "
                       "Decide each one and write it in `findings/_delta-map.json`, an object with the earlier fingerprint as key, then merge again:", "",
                       "- the same problem as a finding of this run: the value is that finding's ID or fingerprint;",
                       "- checked in the code and gone: the value is `\"resolved\"`;",
                       "- neither: leave it out, and it stays in this list and is reported as not reported again.", "",
                       "A line starting with \"may be\" is a finding of this run that shares two of criterion, file and a word of the slug with the entry "
                       "above it. Most entries have none; then look yourself. The merge checks the map: an entry that does not hold comes back as a problem to resolve.", ""]
            for fp in not_reported:
                dl.append(line(earlier[fp], fp))
                dl += [f"  - may be {cur[c].get('id')} · {cur[c].get('title')} · `{c}` ({', '.join(why)})" for _, c, why in candidates(fp)]
            dl += ["", f"## Resolved ({len(resolved)})", "", "Called resolved in `_delta-map.json`.", ""] + [line(earlier[fp], fp) for fp in resolved]
            dl += ["", f"## Regressed ({len(regressed)})", ""] + [line(cur[fp], fp) for fp in regressed]
            dl += ["", f"## Still open ({len(still_open)})", ""] + [line(cur[fp], fp) + (" (earlier " + ", ".join(f"`{o}`" for o in was_called[fp]) + ")" if fp in was_called else "") for fp in still_open]
            dl += ["", f"## New ({len(new)})", ""] + [line(cur[fp], fp) for fp in new] + [""]
            (ws / "delta.md").write_text("\n".join(dl), encoding="utf-8")
            print(f"delta: resolved {len(resolved)}, not reported again {len(not_reported)}, still open {len(still_open)}, regressed {len(regressed)}, new {len(new)}")

    # --- write outputs --------------------------------------------------------------------
    cross_notes = [dict(n, agent=ag) for ag, d in agents.items() for n in (d.get("cross_lens_notes") or []) if isinstance(n, dict)]
    # Lenses run side by side, so the owner a note points at never reads it. A note counts as filed when some
    # finding cites its criterion in its file; what is left is nobody's until the orchestrator looks.
    # An accepted exception is no filing: it says a tool's hit is left as it is, not that someone looked at the note.
    # ponytail: the same file, not the same lines, so a second problem under one criterion in one file hides behind
    # the first; and only the first path of a location that names two files is looked at
    for n in cross_notes:
        path = re.split(r"[:\s(]", str(n.get("location") or "").strip())[0].removeprefix("./")
        n["filed_as"] = [f["id"] for f in merged if path and (f.get("fix") or {}).get("ownership") != "accepted"
                         and cites(f, n.get("sc"), path)]
    unfiled = [n for n in cross_notes if not n["filed_as"]]

    # The maximizer runs after the lenses and is told to file only what no lens can see. A finding of its own on a
    # criterion and in a file that another finding already has is, as a rule, that finding filed a second time.
    for f in merged:
        if not from_maximizer(f):
            continue
        spots = {(str(w.get("sc")), str(e.get("file")).removeprefix("./")) for w in f.get("wcag") or [] if isinstance(w, dict)
                 for e in f.get("evidence") or [] if isinstance(e, dict) and e.get("file")}
        twins = sorted({o["id"] for o in merged if not from_maximizer(o) and (o.get("fix") or {}).get("ownership") != "accepted"
                        and any(cites(o, sc, path) for sc, path in spots)})
        if twins:
            problems.append(f"{f['id']}: the framework-maximizer filed a finding on a criterion and in a file that {', '.join(twins)} "
                            f"already has. If it is the same problem, name it a duplicate in _dedupe.json, or make it a leverage entry "
                            f"(\"kind\": \"leverage\", leverage.finding_ids) when it is the one place that fixes it; if it is "
                            f"another problem, move it to findings/orchestrator.json under an ORC id and take it out of the maximizer's file")

    # A lens that read only the code while the app was running left out what only the running app answers.
    static_only = []
    if (ws / "automated" / "summary.json").is_file():
        for ag, d in agents.items():
            cov = d.get("coverage") if isinstance(d.get("coverage"), dict) else {}
            how = str(cov.get("method") or "").strip().lower()
            mine = sorted(RUNTIME_LENSES & set(d.get("lenses") or [ag]))
            if mine and "runtime" not in how and how != "both":            # agents also write "static + runtime"
                static_only.append({"agent": ag, "lenses": mine, "method": how or None})
    exceptions = [{"id": f["id"], "title": f.get("title"), **(f.get("fix", {}).get("exception") or {}),
                   "reason": (f.get("fix", {}).get("exception") or {}).get("reason") or f.get("fix", {}).get("summary")}
                  for f in merged if f.get("fix", {}).get("ownership") == "accepted"]
    out = {"findings": merged, "leverage_entries": leverage_entries, "root_cause_clusters": cand, "problems": problems, "notes": problems.notes,
           "cross_lens_notes": cross_notes, "static_only_lenses": static_only, "accepted_exceptions": exceptions,
           "key_flow_failures": flow_failures, "severity_upgrades": severity_upgrades,
           "positives": {ag: d.get("positives", []) for ag, d in agents.items()},
           "coverage": {r[0]: {"status": r[4], "findings": r[5].split(", ") if r[5] else [], "owner": r[3]} for r in cov_rows},
           "coverage_counts": dict(counts), "coverage_conflicts": conflicts, "persona_citations": persona_notes}
    if delta:
        out["delta"] = delta
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
    if unfiled:
        lines += ["", f"## Cross-lens notes nobody filed ({len(unfiled)})", "",
                  "No finding cites that criterion in that file, and the lens that owns it never saw the note. "
                  "Open each location; what holds goes into findings/orchestrator.json.", ""]
        lines += [f"- {n.get('sc', '?')} · {n.get('location', '?')} · {n.get('note', '')} ({n['agent']})" for n in unfiled]
    if len(unfiled) < len(cross_notes):
        lines += ["", f"{len(cross_notes) - len(unfiled)} more cross-lens notes are covered: a finding cites the same criterion in the same file "
                      "(`filed_as` in `_merged.json`)."]
    if static_only:
        lines += ["", f"## Worked from the code only, with a runtime there ({len(static_only)})", "",
                  "The scan ran, so the app was running. Each of these has a \"With a runtime\" list in its lens file: checks that "
                  "reading code does not answer. Send the agent back once for those, unless agents have no browser tool.", ""]
        lines += [f"- {s['agent']} ({', '.join(s['lenses'])}): coverage.method is {s['method'] or 'not given'}" for s in static_only]
    if exceptions:
        lines += ["", "## Accepted exceptions (ownership: accepted)", ""]
        lines += [f"- {e['id']} · {e.get('tool', '')} {e.get('rule', '')} {e.get('selector', '')} · {e.get('reason', '')}".replace("  ", " ") for e in exceptions]
    if problems:
        lines += ["", f"## Problems to resolve ({len(problems)}: lost content and claims that do not hold)", ""] + [f"- {p}" for p in problems]
    if problems.notes:
        lines += ["", f"## Settled by the merge ({len(problems.notes)}: for your information, nothing to do)", ""] + [f"- {n}" for n in problems.notes]
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


    print(f"{len(all_findings)} raw findings from {len(agents)} agents (+{len(persona_findings)} from personas) → {len(merged)} merged; "
          f"{len(cand)} root-cause clusters; coverage {dict(counts)}; {len(conflicts)} conflicts; {len(problems)} problems to resolve, {len(problems.notes)} settled by the merge"
          + (f"; {len(unfiled)} cross-lens notes nobody filed" if unfiled else "")
          + (f"; {len(static_only)} lenses static-only with a runtime there" if static_only else ""))
    all_users = [f["id"] for f in merged if f.get("affects_all_users")]
    if all_users:
        print("affects all users: " + ", ".join(all_users))
    if severity_upgrades:
        print(f"{len(severity_upgrades)} severity floor(s) applied from persona key-flow failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
