---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '#{3,4} T[12]-\d+\. (?=(?:(?!\n#{2,4} )[\s\S])*?\nWaar: [^\n]*custom\.css)(?=(?:(?!\n#{2,4} )[\s\S])*?(?:--link|underline|onderstre))'
flags: i
---
