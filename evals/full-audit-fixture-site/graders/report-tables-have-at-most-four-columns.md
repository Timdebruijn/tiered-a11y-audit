---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '(?:^|\n)\|(?:[^|\n]*\|){5,}[ \t]*(?=\n|$)'
flags: i
match: not_contains
---
