---
type: regex
target: { source: file, path: site/.a11y-audit/REPORT.md }
pattern: '\| Flow \| Persona \| Resultaat \|(?=[\s\S]*\n\|[^|\n]*\|[^|\n]*\b(?:Sanne|screen-reader)\b[^|\n]*\|)(?=[\s\S]*\n\|[^|\n]*\|[^|\n]*\b(?:Henk|low-vision)\b[^|\n]*\|)(?=[\s\S]*\n\|[^|\n]*\|[^|\n]*\b(?:Youssef|motor-voice)\b[^|\n]*\|)(?=[\s\S]*\n\|[^|\n]*\|[^|\n]*\b(?:Lotte|cognitive)\b[^|\n]*\|)'
flags: i
---
