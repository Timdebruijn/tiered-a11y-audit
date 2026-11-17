---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '#{3,4} T[12]-\d+\. (?=[^\n]*\n\n[^\n]*\b(?:3\.3\.1)\b)(?=(?:(?!\n#{2,4} )[\s\S])*?\nWaar: [^\n]*app\.js)(?=(?:[^\n]*|(?:(?!\n#{2,4} )[\s\S])*?\nProbleem: [^\n]*)(?:invalid|border|error|rode rand|foutmelding|ongeldig))'
flags: i
---
