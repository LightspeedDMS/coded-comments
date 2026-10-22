You are a coding agent working in a repository. The block below is part of your standing instructions (it sits in
your CLAUDE.md / AGENTS.md); it is everything you have been told about this comment style.

<standing_instructions>
{{ENTRY}}
</standing_instructions>

Rules for this task:
- Answer only from this message. Do not read any files, do not run any commands, do not search.
- Below are code snippets from the repository. For each snippet, explain in plain English what every comment that
  starts with `# ^`, `// ^` or `-- ^` tells a developer: what it warns about, requires, explains or points to, which
  code it applies to, and what each reference in it is (issue numbers, file paths, symbols, doc anchors).
- Be concrete and complete; do not just restate the comment.
- If any part of a comment's notation is ambiguous to you, say exactly what and why in `unsure` (empty string if
  nothing).

Output: one JSON object per line, nothing else, in snippet order:
{"id": <number>, "explanation": "<prose>", "unsure": "<what was ambiguous, or empty>"}

{{SNIPPETS}}
