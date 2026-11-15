#!/usr/bin/env python3
"""Digest of Playwright accessibility-tree snapshots (the *.aria.yml files axe_scan.mjs writes).

    python3 aria_digest.py <repo>/.a11y-audit/automated [--json]

For every view: landmarks, the heading outline (with skipped levels, missing or multiple h1), interactive
elements WITHOUT an accessible name (the single most common false-positive area — check here before filing
"missing accessible name"), duplicate button/link names, images without names, and counts. This is what a
screen-reader user "sees" first: headings list, landmarks list, links list, form fields list.
Pure standard library, read-only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

LINE = re.compile(r"^(\s*)- ([a-z]+)(?:\s+\"((?:[^\"\\]|\\.)*)\")?(?:\s*\[([^\]]*)\])?(?::\s*(.*))?$")
LANDMARKS = {"banner", "navigation", "main", "contentinfo", "complementary", "search", "region", "form"}
INTERACTIVE = {"button", "link", "textbox", "combobox", "checkbox", "radio", "slider", "switch", "tab", "menuitem",
               "menuitemcheckbox", "menuitemradio", "searchbox", "spinbutton", "listbox", "option", "treeitem"}
NAMELESS_OK = {"option", "listbox"}  # options often carry text as value; listbox named by its combobox
GENERIC = {"edit", "delete", "remove", "more", "read more", "lees meer", "details", "open", "close", "view", "save",
           "revert", "add", "ok", "x", "×", "click here", "here", "meer", "bekijk", "wijzig"}


def parse(text: str):
    nodes = []
    for raw in text.splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        indent, role, name, attrs, rest = m.groups()
        nodes.append({"depth": len(indent) // 2, "role": role, "name": (name or "").strip(),
                      "attrs": attrs or "", "rest": (rest or "").strip()})
    return nodes


def digest_view(nodes):
    d = {"landmarks": [], "headings": [], "nameless": [], "duplicates": {}, "images_unnamed": 0, "counts": Counter()}
    names = defaultdict(Counter)
    for n in nodes:
        role, name = n["role"], n["name"]
        d["counts"][role] += 1
        if role in LANDMARKS:
            d["landmarks"].append(f"{role}" + (f' "{name}"' if name else "") + (f" ({n['rest'][:40]})" if n["rest"] and role != "main" else ""))
        if role == "heading":
            lvl = re.search(r"level=(\d)", n["attrs"])
            d["headings"].append((int(lvl.group(1)) if lvl else 0, name))
        if role in INTERACTIVE:
            if not name and role not in NAMELESS_OK:
                d["nameless"].append(f"{role}" + (f" (value {n['rest'][:30]})" if n["rest"] else ""))
            if name and role in {"button", "link"}:
                names[role][name.lower()] += 1
        if role == "img" and not name:
            d["images_unnamed"] += 1
    for role, c in names.items():
        dups = {k: v for k, v in c.items() if v > 1}
        if dups:
            d["duplicates"][role] = dups
    # heading analysis
    levels = [l for l, _ in d["headings"]]
    issues = []
    if not levels:
        issues.append("no headings at all")
    else:
        if 1 not in levels:
            issues.append("no h1")
        if levels.count(1) > 1:
            issues.append(f"{levels.count(1)} h1 elements")
        prev = 0
        for l in levels:
            if prev and l > prev + 1:
                issues.append(f"skipped level h{prev} to h{l}")
            prev = l
        if levels and levels[0] > 1:
            issues.append(f"first heading is h{levels[0]}")
    d["heading_issues"] = sorted(set(issues))
    if "main" not in {x.split()[0] for x in d["landmarks"]}:
        d["landmark_issues"] = ["no main landmark"]
    else:
        d["landmark_issues"] = []
    d["counts"] = dict(d["counts"])
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("automated_dir")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    adir = Path(a.automated_dir)
    files = sorted(adir.glob("*.aria.yml"))
    if not files:
        print("no *.aria.yml files found", file=sys.stderr)
        return 2
    out = {}
    for f in files:
        view = f.name[:-len(".aria.yml")]
        meta = {}
        jf = adir / f"{view}.json"
        if jf.exists():
            try:
                j = json.loads(jf.read_text(encoding="utf-8"))
                meta = {"title": j.get("title"), "lang": j.get("lang"), "url": j.get("url"), "state": j.get("state")}
            except json.JSONDecodeError:
                pass
        out[view] = {"meta": meta, **digest_view(parse(f.read_text(encoding="utf-8")))}
    if a.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    print(f"# Accessibility-tree digest — {adir}\n")
    print("What a screen-reader user gets per view: landmarks, headings, nameless controls, duplicate names. "
          "Check this before filing any 'missing accessible name' finding.\n")
    titles = Counter(v["meta"].get("title") for v in out.values() if v["meta"].get("title"))
    dup_titles = [t for t, c in titles.items() if c > 1]
    print("## Overview\n")
    print("| View | Title | Headings | Nameless controls |")
    print("|---|---|---|---|")
    for view, d in out.items():
        print(f"| {view} | {(d['meta'].get('title') or 'unknown')[:40]} | {len(d['headings'])} ({', '.join(d['heading_issues']) or 'ok'}) | {len(d['nameless'])} |")
    if dup_titles:
        print(f"\nViews sharing the same title: {dup_titles} (announcers read the title on view change).")
    for view, d in out.items():
        print(f"\n## {view}\n")
        if d["meta"]:
            print(f"Title: {d['meta'].get('title')!r}. Lang: {d['meta'].get('lang')!r}. URL: {d['meta'].get('url')}" + (f", state {d['meta'].get('state')}" if d['meta'].get('state') else "") + "\n")
        print("Landmarks: " + ("; ".join(d["landmarks"]) if d["landmarks"] else "none") + (" — " + ", ".join(d["landmark_issues"]) if d["landmark_issues"] else "") + "\n")
        if d["headings"]:
            print("Headings: " + " | ".join(f"h{l} {n[:40]}" for l, n in d["headings"]) + (" — " + ", ".join(d["heading_issues"]) if d["heading_issues"] else "") + "\n")
        else:
            print("Headings: none\n")
        print("Nameless interactive controls: " + (", ".join(d["nameless"]) if d["nameless"] else "none") + "\n")
        if d["duplicates"]:
            for role, dups in d["duplicates"].items():
                gen = [f"{k} ×{v}" for k, v in dups.items()]
                print(f"Duplicate {role} names: " + ", ".join(gen) + ("  (generic names: " + ", ".join(k for k in dups if k in GENERIC) + ")" if any(k in GENERIC for k in dups) else "") + "\n")
        if d["images_unnamed"]:
            print(f"Images without a name: {d['images_unnamed']}\n")
        inter = {k: v for k, v in d["counts"].items() if k in INTERACTIVE}
        print("Interactive elements: " + (", ".join(f"{k} {v}" for k, v in sorted(inter.items())) or "none") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
