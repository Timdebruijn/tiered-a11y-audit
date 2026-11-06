#!/usr/bin/env python3
"""Grade an audit against a ground-truth file: detection rate, misses, suspected false positives.

    python3 grade_findings.py <repo>/.a11y-audit/findings/_merged.json <ground-truth.json>

A known failure counts as detected when one finding cites its criterion, cites its file, and mentions one
of its keywords. Findings that match no known failure are listed as "unmatched" for manual review — they
may be genuine extras or false positives; the script does not decide. Should-pass items are violated when
a finding cites the criterion AND one of the item's keywords. Pure standard library.
"""
import json
import sys
from pathlib import Path


def text_of(f):
    return " ".join([str(f.get("title", "")), str(f.get("description", "")), json.dumps(f.get("fix", {}), ensure_ascii=False)]).lower()


def files_of(f):
    ev = f.get("evidence") or []
    return " ".join(str(e.get("file", "")) for e in ev if isinstance(e, dict)).lower()


def main():
    if len(sys.argv) != 3:
        print(__doc__); return 2
    merged = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    gt = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    findings = merged.get("findings", merged if isinstance(merged, list) else [])
    matched_findings = set()
    detected, missed, tier_mismatch = [], [], []
    for k in gt["known_failures"]:
        hit = None
        for f in findings:
            scs = {s.get("sc") for s in f.get("wcag", []) if isinstance(s, dict)}
            if k["sc"] in scs and k["file"].lower() in files_of(f) and any(w.lower() in text_of(f) for w in k["keywords"]):
                hit = f; break
        if hit:
            detected.append((k["id"], hit["id"]))
            matched_findings.add(hit["id"])
            if k.get("tier") and hit.get("tier") and k["tier"] != hit["tier"]:
                tier_mismatch.append(f"{k['id']} expected tier {k['tier']}, got {hit['tier']} ({hit['id']})")
        else:
            missed.append(k["id"])
    violated_sp = []
    for sp in gt.get("should_pass", []):
        kws = [w.lower() for w in sp.get("keywords", [])]
        for f in findings:
            scs = {s.get("sc") for s in f.get("wcag", []) if isinstance(s, dict)}
            if sp["sc"] in scs and kws and any(w in text_of(f) for w in kws):
                violated_sp.append(f"{sp['id']} ({sp['note']}) flagged by {f['id']}")
    unmatched = [f for f in findings if f["id"] not in matched_findings]
    n = len(gt["known_failures"])
    print(f"Detection: {len(detected)}/{n} ({100 * len(detected) / n:.0f}%)")
    print(f"Missed: {', '.join(missed) or 'none'}")
    print(f"Should-pass violated: {len(violated_sp)}/{len(gt.get('should_pass', []))}" + (": " + "; ".join(violated_sp) if violated_sp else ""))
    print(f"Tier mismatches: {len(tier_mismatch)}" + (": " + "; ".join(tier_mismatch) if tier_mismatch else ""))
    print(f"Unmatched findings (review: genuine extra or false positive): {len(unmatched)}")
    for f in unmatched[:40]:
        print(f"  - {f['id']} · {f.get('severity')} · {f.get('title', '')[:70]} · {files_of(f)[:40]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
