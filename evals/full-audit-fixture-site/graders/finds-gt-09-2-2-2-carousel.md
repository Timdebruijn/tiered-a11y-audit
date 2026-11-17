---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '#{3,4} T[12]-\d+\. (?=[^\n]*\n\n[^\n]*\b(?:2\.2\.2)\b)(?=(?:(?!\n#{2,4} )[\s\S])*?\nWaar: [^\n]*app\.js)(?=(?:[^\n]*|(?:(?!\n#{2,4} )[\s\S])*?\nProbleem: [^\n]*|(?:(?!\n#{2,4} )[\s\S])*?\nOplossing: (?:(?!\n#{2,4} )[\s\S])*?)(?:carousel|setInterval|autoplay|auto-advanc|pause|carrousel|pauze))'
flags: i
---
