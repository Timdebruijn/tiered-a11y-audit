---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '#{3,4} T2-\d+\. (?=[^\n]*\n\n[^\n]*\b(?:1\.4\.3)\b)(?=(?:(?!\n#{2,4} )[\s\S])*?\nWaar: [^\n]*styles\.css)(?=(?:(?!\n#{2,4} )[\s\S])*?(?:#9a9a9a))(?=(?:(?!\n#{2,4} )[\s\S])*?(?:#(?!9a9a9a|ffffff\b)[0-9a-f]{6}\b))'
flags: i
---
