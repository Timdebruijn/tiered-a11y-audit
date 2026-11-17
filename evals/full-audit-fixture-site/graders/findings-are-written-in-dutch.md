---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '\nProbleem: [^\n]*\b(?:het|een|niet|geen|wordt|zijn|deze)\b'
flags: i
---
