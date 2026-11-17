---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '#{3,4} T[12]-\d+\. (?=[^\n]*\n\n[^\n]*\b(?:1\.4\.3)\b)(?=(?:(?!\n#{2,4} )[\s\S])*?\nWaar: [^\n]*styles\.css)(?=(?:[^\n]*|(?:(?!\n#{2,4} )[\s\S])*?\nProbleem: [^\n]*)(?:muted|9a9a9a))'
flags: i
---
