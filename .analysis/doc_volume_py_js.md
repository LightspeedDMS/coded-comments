# Docstring-inclusive volume: Python and TS/JS

Frozen ratio_files.tsv sample. Python: AST first-statement docstrings on module/class/function; module public; top-level names public unless leading underscore, except __all__; nested names public only under public ancestor; dunder names public. Count docstring span once as non-code and subtract docstring-only token lines from code. TS/JS: /** */ lexical spans; public iff next nonblank text starts export, declare public or public; otherwise private. JSDoc already included in baseline comment lines. Lexical JS scanner can misclassify strings or detached JSDoc. Ratio=inclusive comment lines / inclusive code lines, rounded to 6 decimals.

| Language | Files | Doc spans | Public lines | Private lines | Inclusive comment/code | Ratio |
|---|---:|---:|---:|---:|---:|---:|
| python | 120 | 1303 | 9159 | 3524 | 19958/36525 | 0.54642 |
| typescript_js | 83 | 254 | 298 | 1091 | 2415/14015 | 0.172315 |

These are line counts, not token counts. The current file may have changed since the Claude-coauthored commit.
