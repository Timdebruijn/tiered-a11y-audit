---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '#{3,4} T[12]-\d+\. (?=[^\n]*\n\n[^\n]*\b(?:4\.1\.2)\b)(?=(?:(?!\n#{2,4} )[\s\S])*?\nWaar: [^\n]*contact\.html)(?=(?:[^\n]*|(?:(?!\n#{2,4} )[\s\S])*?\nProbleem: [^\n]*)(?:checkbox|fake-checkbox|agree|selectievakje|aanvinkvak))'
flags: i
---
