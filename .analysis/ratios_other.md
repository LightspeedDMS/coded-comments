# Remaining host-language comment-to-code sample

Same convention as ratios.md (step 7). Scanner: scanner.py. SHA256-ranked up to 60 current, non-test, non-vendor files per canonical repo from provenance.tsv; scanner.count_lines: comment/code line if it contains that token, mixed lines count in both, blank in neither; shell shebang excluded; strings handled per single-line quote rules (Go backtick multi-line). Not modeled: Rust nested block comments and lifetimes-as-quotes, C# verbatim/raw strings, shell heredocs (counted as code), Pascal compiler directives (counted as comments). Ratio=comment_lines/code_lines, rounded to 6 decimals.

| Language | Repos | Files | Comment lines | Code lines | Ratio |
|---|---|---:|---:|---:|---:|
| shell | claude-server, code-indexer, setup-dev-rocky | 135 | 4603 | 20355 | 0.226136 |
| go | ragflow, roxy, tdd-guard | 134 | 6427 | 35206 | 0.182554 |
| rust | code-indexer | 60 | 6037 | 11888 | 0.507823 |
| csharp | claude-server | 60 | 2750 | 13384 | 0.205469 |
| java | swing-mcp-automation, tdd-guard | 78 | 2247 | 9219 | 0.243736 |
| c | - | 0 | 0 | 0 | n/a |
| cpp | - | 0 | 0 | 0 | n/a |
| pascal | - | 0 | 0 | 0 | n/a |
| sql | claude-server, code-indexer, llm-creds-provider | 80 | 974 | 1325 | 0.735094 |

Thin samples (< 10 files): c, cpp, pascal. SQL dialects are not separated in the corpus.
