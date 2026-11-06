---
type: llm
focus: trace
weight: 1
---

Before creating the .a11y-audit/ workspace, Claude checked whether it was gitignored and asked the user (in its single Phase-1 message) whether to add it to .gitignore, offering to ignore everything or to keep only the report trackable; it did not silently write the folder into an unignored repo.
