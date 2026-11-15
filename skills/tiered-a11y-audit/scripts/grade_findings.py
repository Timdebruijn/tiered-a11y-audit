#!/usr/bin/env python3
"""Grade an audit against a ground-truth file: detection rate, misses, suspected false positives.

    python3 grade_findings.py <repo>/.a11y-audit/findings/_merged.json <ground-truth.json>

A known failure counts as detected when one finding cites its criterion, cites its file, and mentions one
of its keywords. Findings that match no known failure are listed as "unmatched" for manual review — they
may be genuine extras or false positives; the script does not decide. Should-pass items are violated when
a finding cites the criterion AND one of the item's keywords in its title or description -- not in its
fix, where correct markup for some other problem legitimately mentions the same element.

An item without `keywords` cannot be graded either way -- a known failure could never be matched, a
should-pass item could never be flagged -- so it is reported as ungradable and left out of both
denominators rather than counted as a miss or a silent pass. Pure standard library.
"""
import json
import sys
from pathlib import Path


def text_of(f):
    return " ".join([str(f.get("title", "")), str(f.get("description", "")), json.dumps(f.get("fix", {}), ensure_ascii=False)]).lower()


def claim_text_of(f):
    """Only what the finding CLAIMS is wrong -- title and description, never the fix.

    A should-pass item is violated when a finding asserts the thing is broken. The fix is
    where correct markup legitimately appears: a repair for a heading problem contains
    `<main>`, a repair for a menu button names the nav it controls. Searching the fix for
    an element name therefore flags findings that never claimed anything about that element.
    """
    return " ".join([str(f.get("title", "")), str(f.get("description", ""))]).lower()


def note_of(gt, sp_id):
    for sp in gt.get("should_pass", []):
        if sp.get("id") == sp_id:
            return sp.get("note", "no note")
    return "no note"


def files_of(f):
    ev = f.get("evidence") or []
    return " ".join(str(e.get("file", "")) for e in ev if isinstance(e, dict)).lower()


def main():
    if len(sys.argv) != 3:
        print(__doc__); return 2
    merged = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    gt = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    findings = merged if isinstance(merged, list) else merged.get("findings", [])
    findings = [f for f in findings if isinstance(f, dict) and f.get("id")]
    matched_findings = set()
    detected, missed, tier_mismatch = [], [], []
    ungradable = []
    for k in gt.get("known_failures", []):
        if not k.get("keywords"):
            # No keywords means no finding can ever match: a missing detection would be
            # reported as a miss that no audit could avoid. Say so instead of scoring it.
            ungradable.append(f"{k.get('id', '?')} (known failure, no keywords)")
            continue
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
    violated_sp, graded_sp = {}, 0
    for sp in gt.get("should_pass", []):
        kws = [w.lower() for w in sp.get("keywords", [])]
        if not kws:
            # Without keywords the criterion alone would flag any finding that cites it,
            # so the item can only ever pass. That is not a result; it is an untested item.
            ungradable.append(f"{sp.get('id', '?')} (should-pass, no keywords)")
            continue
        graded_sp += 1
        for f in findings:
            scs = {s.get("sc") for s in f.get("wcag", []) if isinstance(s, dict)}
            if sp["sc"] in scs and any(w in claim_text_of(f) for w in kws):
                violated_sp.setdefault(sp["id"], []).append(f["id"])
    unmatched = [f for f in findings if f["id"] not in matched_findings]
    n = len(detected) + len(missed)
    rate = f" ({100 * len(detected) / n:.0f}%)" if n else ""
    print(f"Detection: {len(detected)}/{n}{rate}")
    print(f"Missed: {', '.join(missed) or 'none'}")
    sp_detail = "; ".join(f"{i} ({note_of(gt, i)}) flagged by {', '.join(ids)}" for i, ids in violated_sp.items())
    print(f"Should-pass violated: {len(violated_sp)}/{graded_sp}" + (": " + sp_detail if sp_detail else ""))
    print(f"Tier mismatches: {len(tier_mismatch)}" + (": " + "; ".join(tier_mismatch) if tier_mismatch else ""))
    if ungradable:
        print(f"Ungradable ground-truth items (fix the ground truth): {'; '.join(ungradable)}")
    print(f"Unmatched findings (review: genuine extra or false positive): {len(unmatched)}")
    for f in unmatched[:40]:
        print(f"  - {f['id']} · {f.get('severity')} · {str(f.get('title', ''))[:70]} · {files_of(f)[:40]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
