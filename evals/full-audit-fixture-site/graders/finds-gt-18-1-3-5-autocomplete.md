---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '#{3,4} T[12]-\d+\. (?=[^\n]*\n\n[^\n]*\b(?:1\.3\.5)\b)(?=(?:(?!\n#{2,4} )[\s\S])*?\nWaar: [^\n]*contact\.html)(?=(?:[^\n]*|(?:(?!\n#{2,4} )[\s\S])*?\nProbleem: [^\n]*|(?:(?!\n#{2,4} )[\s\S])*?\nOplossing: (?:(?!\n#{2,4} )[\s\S])*?)(?:autocomplete|email|type))'
flags: i
---
