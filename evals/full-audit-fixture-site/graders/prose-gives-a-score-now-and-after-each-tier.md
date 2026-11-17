---
type: llm
focus: { source: file, path: site/.a11y-audit/report-prose.md }
---

This file holds the prose of an accessibility report. Lines of the form `=== key ===` name sections, and text inside `<!-- -->` is a hint for the writer, not part of the report.

PASS if the prose gives a score out of 10 for the site as it is now, and an expected score after tier 1, after tiers 1 and 2, and after tier 3 (the last may be given as a ceiling), with a reason for the scores.
FAIL if one of those four scores is missing, or if scores are given without any reason.
The tiers may be called "niveau 1", "niveau 2" and "niveau 3".
