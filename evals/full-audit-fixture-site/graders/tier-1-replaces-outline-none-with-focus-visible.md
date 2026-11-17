---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '#{3,4} T1-\d+\. (?=[^\n]*\n\n[^\n]*\b(?:2\.4\.7)\b)(?=(?:(?!\n#{2,4} )[\s\S])*?\nWaar: [^\n]*styles\.css)(?=(?:(?!\n#{2,4} )[\s\S])*?(?:focus-visible))'
flags: i
---
