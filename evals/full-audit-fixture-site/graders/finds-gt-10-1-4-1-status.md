---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '#{3,4} T[12]-\d+\. (?=[^\n]*\n\n[^\n]*\b(?:1\.4\.1)\b)(?=(?:(?!\n#{2,4} )[\s\S])*?\nWaar: [^\n]*index\.html)(?=(?:[^\n]*|(?:(?!\n#{2,4} )[\s\S])*?\nProbleem: [^\n]*)(?:status|dot|colour|color|kleur|stip))'
flags: i
---
