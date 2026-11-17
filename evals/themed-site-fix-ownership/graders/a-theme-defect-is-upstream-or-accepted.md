---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '#{3,4} (T\d-\d+)\. (?=(?:(?!\n#{2,4} )[\s\S])*?\nWaar: [^\n]*themes/paper)(?=[\s\S]*?### (?:Vraagt een wijziging upstream|Geaccepteerde uitzonderingen) \(\d+\)\n\n(?:- [^\n]*\n)*?- \1[ :(])'
flags: i
---
