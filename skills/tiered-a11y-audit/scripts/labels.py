#!/usr/bin/env python3
"""Report labels in any language: the fixed words of the report and the conformance table.

Shipped: references/report-labels/en.json (the source) and nl.json. For any other language the
first run writes <workspace>/report-labels.<lang>.json, a copy of the English file, and stops:
translate its values, keep its keys and {placeholders}, run again. A workspace file wins over a
shipped one, so a team can also adjust the wording of a shipped language.

A translated file is checked against the English one before it is used: a missing key or a lost
{placeholder} would otherwise surface as a KeyError halfway through a report.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SHIPPED = Path(__file__).resolve().parent.parent / "references" / "report-labels"
LANG_RE = re.compile(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*")      # en, nl, pt-BR, zh-Hant; also keeps it a safe file name


def leaves(x, pre=""):
    if isinstance(x, dict):
        return {k2: v2 for k, v in x.items() if not str(k).startswith("_") for k2, v2 in leaves(v, f"{pre}.{k}" if pre else str(k)).items()}
    if isinstance(x, list):
        return {k2: v2 for i, v in enumerate(x) for k2, v2 in leaves(v, f"{pre}[{i}]").items()}
    return {pre: x}


def check(labels: dict, source: dict) -> list:
    """What a translation lost: keys, and the {placeholders} the scripts fill in."""
    got, want = leaves(labels), leaves(source)
    problems = [f"missing: {k}" for k in sorted(want.keys() - got.keys())]
    for k in sorted(want.keys() & got.keys()):
        a, b = set(re.findall(r"\{(\w+)\}", str(want[k]))), set(re.findall(r"\{(\w+)\}", str(got[k])))
        if a != b:
            problems.append(f"{k}: placeholders {sorted(b)} differ from the source {sorted(a)}")
    return problems


def load_labels(lang: str, ws: Path) -> dict:
    """Labels for `lang`, or exit 2 with what to do."""
    if not LANG_RE.fullmatch(lang):
        sys.exit(f"--lang {lang!r} is not a language code (en, nl, de, pt-BR …)")
    source = json.loads((SHIPPED / "en.json").read_text(encoding="utf-8"))
    local, shipped = ws / f"report-labels.{lang}.json", SHIPPED / f"{lang.lower()}.json"
    path = local if local.exists() else shipped
    if not path.exists():
        template = {"_translate": f"Translate every value below into {lang}. Keep the keys and every {{placeholder}} exactly as they are. "
                                  "Keep it plain: these words are read aloud by screen readers. Then run the command again."}
        template.update(source)
        local.write_text(json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"No labels for {lang!r} yet. Wrote {local} with the English labels: translate its values into {lang} "
              "(keys and {placeholders} stay), then run this command again.", file=sys.stderr)
        sys.exit(2)
    try:
        labels = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        sys.exit(f"{path}: cannot be read as JSON ({e})")
    problems = check(labels, source) if isinstance(labels, dict) else ["the file is not a JSON object"]
    if problems:
        print(f"{path}: {len(problems)} problem(s), fix them and run again:\n  " + "\n  ".join(problems[:20]), file=sys.stderr)
        sys.exit(2)
    return labels


def flow_result(text):
    """Which of the persona protocol's scores a cell of the flow table holds: 'na', 'failed', 'help', 'difficulty',
    'completed', or None when it is none of them. English as the protocol asks, and the Dutch a persona may write.

    A result that starts with "completed" is never a failure, whatever it goes on to mention."""
    s = str(text).strip(" *_`").lower()
    if "n/a" in s or "not applicable" in s or "niet van toepassing" in s:
        return "na"
    if not s.startswith(("complet", "voltooid")) and ("fail" in s or "mislukt" in s):
        return "failed"
    if "help" in s or "workaround" in s or "hulp" in s:
        return "help"
    if "difficult" in s or "moeite" in s:
        return "difficulty"
    return "completed" if "complet" in s or "voltooid" in s else None
