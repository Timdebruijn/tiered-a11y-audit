---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '#{3,4} T1-\d+\. (?=[^\n]*\n\n[^\n]*\b(?:3\.1\.1)\b)(?=(?:[^\n]*|(?:(?!\n#{2,4} )[\s\S])*?\nProbleem: [^\n]*)(?:lang))'
flags: i
---
