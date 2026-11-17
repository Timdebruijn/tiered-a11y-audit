---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '#{3,4} T[12]-\d+\. (?=[^\n]*\n\n[^\n]*\b(?:1\.4\.3)\b)(?=(?:(?!\n#{2,4} )[\s\S])*?\nWaar: [^\n]*custom\.css)(?=(?:(?!\n#{2,4} )[\s\S])*?(?:muted))(?=(?:(?!\n#{2,4} )[\s\S])*?(?:#[0-9a-f]{6}\b))'
flags: i
---
