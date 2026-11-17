---
type: llm
focus: last_message
---

PASS if the reply is written in Dutch, says where the report is (a path ending in `.a11y-audit/REPORT.md`), and is a short summary of roughly 20 lines or fewer.
FAIL if the reply is in another language, does not say where the report is, or pastes the report or long parts of it instead of summarising.
Finding IDs, file names, code and WCAG numbers may stay as they are; they do not make a reply non-Dutch.
