---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '\| Flow \| Persona \| Resultaat \|(?=[\s\S]*\| screen-reader \|)(?=[\s\S]*\| low-vision \|)(?=[\s\S]*\| motor-voice \|)(?=[\s\S]*\| cognitive \|)'
flags: i
---
