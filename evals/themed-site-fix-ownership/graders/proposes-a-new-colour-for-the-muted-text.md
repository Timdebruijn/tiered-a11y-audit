---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '\| T2-\d+: [^|\n]*\| #9a9a9a \| #(?!9a9a9a)[0-9a-f]{3,8} \|'
flags: i
---
