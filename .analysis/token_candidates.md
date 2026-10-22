# Candidate marker and tag token costs

Counts use tiktoken proxies, not Claude token counts. The candidate strings are exploratory; the marker and grammar are chosen after the corpus before/after measurement. Standalone tag costs may differ when a tokenizer merges them with adjacent syntax.

| Group | Host | Candidate | o200k | cl100k |
|---|---|---|---:|---:|
| marker | python_shell | `#@` | 2 [m:tok.cand.hash_at.o200k_base] | 1 [m:tok.cand.hash_at.cl100k_base] |
| marker | python_shell | `# @` | 2 [m:tok.cand.hash_space_at.o200k_base] | 2 [m:tok.cand.hash_space_at.cl100k_base] |
| marker | python_shell | `#§` | 2 [m:tok.cand.hash_section.o200k_base] | 2 [m:tok.cand.hash_section.cl100k_base] |
| marker | python_shell | `#△` | 2 [m:tok.cand.hash_triangle.o200k_base] | 3 [m:tok.cand.hash_triangle.cl100k_base] |
| marker | python_shell | `# CC:` | 3 [m:tok.cand.hash_cc.o200k_base] | 3 [m:tok.cand.hash_cc.cl100k_base] |
| marker | python_shell | `# ai:` | 3 [m:tok.cand.hash_ai.o200k_base] | 3 [m:tok.cand.hash_ai.cl100k_base] |
| marker | slash_line | `//@` | 1 [m:tok.cand.slash_at.o200k_base] | 1 [m:tok.cand.slash_at.cl100k_base] |
| marker | slash_line | `// @` | 2 [m:tok.cand.slash_space_at.o200k_base] | 2 [m:tok.cand.slash_space_at.cl100k_base] |
| marker | slash_line | `//§` | 2 [m:tok.cand.slash_section.o200k_base] | 2 [m:tok.cand.slash_section.cl100k_base] |
| marker | slash_line | `// CC:` | 3 [m:tok.cand.slash_cc.o200k_base] | 3 [m:tok.cand.slash_cc.cl100k_base] |
| marker | sql_line | `--@` | 2 [m:tok.cand.dash_at.o200k_base] | 2 [m:tok.cand.dash_at.cl100k_base] |
| marker | sql_line | `-- @` | 2 [m:tok.cand.dash_space_at.o200k_base] | 2 [m:tok.cand.dash_space_at.cl100k_base] |
| marker | sql_line | `--§` | 2 [m:tok.cand.dash_section.o200k_base] | 2 [m:tok.cand.dash_section.cl100k_base] |
| marker | sql_line | `-- CC:` | 3 [m:tok.cand.dash_cc.o200k_base] | 3 [m:tok.cand.dash_cc.cl100k_base] |
| marker | c_style_block | `/*@` | 2 [m:tok.cand.block_at.o200k_base] | 1 [m:tok.cand.block_at.cl100k_base] |
| marker | c_style_block | `/*§` | 2 [m:tok.cand.block_section.o200k_base] | 2 [m:tok.cand.block_section.cl100k_base] |
| marker | pascal_brace | `{@` | 1 [m:tok.cand.pascal_brace_at.o200k_base] | 1 [m:tok.cand.pascal_brace_at.cl100k_base] |
| marker | pascal_star | `(*@` | 2 [m:tok.cand.pascal_star_at.o200k_base] | 2 [m:tok.cand.pascal_star_at.cl100k_base] |
| marker | pascal_line | `//@` | 1 [m:tok.cand.pascal_slash_at.o200k_base] | 1 [m:tok.cand.pascal_slash_at.cl100k_base] |
| tag | all | `inv` | 1 [m:tok.cand.tag_inv.o200k_base] | 1 [m:tok.cand.tag_inv.cl100k_base] |
| tag | all | `invariant` | 2 [m:tok.cand.tag_invariant.o200k_base] | 2 [m:tok.cand.tag_invariant.cl100k_base] |
| tag | all | `△` | 1 [m:tok.cand.tag_triangle.o200k_base] | 2 [m:tok.cand.tag_triangle.cl100k_base] |
| tag | all | `haz` | 1 [m:tok.cand.tag_haz.o200k_base] | 2 [m:tok.cand.tag_haz.cl100k_base] |
| tag | all | `hazard` | 2 [m:tok.cand.tag_hazard.o200k_base] | 2 [m:tok.cand.tag_hazard.cl100k_base] |
| tag | all | `⚠` | 2 [m:tok.cand.tag_warning.o200k_base] | 3 [m:tok.cand.tag_warning.cl100k_base] |
| tag | all | `cpl` | 2 [m:tok.cand.tag_cpl.o200k_base] | 2 [m:tok.cand.tag_cpl.cl100k_base] |
| tag | all | `coupling` | 2 [m:tok.cand.tag_coupling.o200k_base] | 2 [m:tok.cand.tag_coupling.cl100k_base] |
| tag | all | `↔` | 2 [m:tok.cand.tag_arrow_bi.o200k_base] | 2 [m:tok.cand.tag_arrow_bi.cl100k_base] |
| tag | all | `ext` | 1 [m:tok.cand.tag_ext.o200k_base] | 1 [m:tok.cand.tag_ext.cl100k_base] |
| tag | all | `external` | 1 [m:tok.cand.tag_external.o200k_base] | 1 [m:tok.cand.tag_external.cl100k_base] |
| tag | all | `■` | 1 [m:tok.cand.tag_square.o200k_base] | 1 [m:tok.cand.tag_square.cl100k_base] |
| tag | all | `ord` | 1 [m:tok.cand.tag_ord.o200k_base] | 1 [m:tok.cand.tag_ord.cl100k_base] |
| tag | all | `order` | 1 [m:tok.cand.tag_order.o200k_base] | 1 [m:tok.cand.tag_order.cl100k_base] |
| tag | all | `↻` | 2 [m:tok.cand.tag_cycle.o200k_base] | 2 [m:tok.cand.tag_cycle.cl100k_base] |
| tag | all | `sec` | 1 [m:tok.cand.tag_sec.o200k_base] | 1 [m:tok.cand.tag_sec.cl100k_base] |
| tag | all | `security` | 1 [m:tok.cand.tag_security.o200k_base] | 1 [m:tok.cand.tag_security.cl100k_base] |
| tag | all | `◎` | 1 [m:tok.cand.tag_circle.o200k_base] | 2 [m:tok.cand.tag_circle.cl100k_base] |
| tag | all | `why` | 1 [m:tok.cand.tag_why.o200k_base] | 1 [m:tok.cand.tag_why.cl100k_base] |
| tag | all | `because` | 1 [m:tok.cand.tag_because.o200k_base] | 1 [m:tok.cand.tag_because.cl100k_base] |
| tag | all | `◇` | 1 [m:tok.cand.tag_diamond.o200k_base] | 2 [m:tok.cand.tag_diamond.cl100k_base] |
| tag | all | `ref` | 1 [m:tok.cand.tag_ref.o200k_base] | 1 [m:tok.cand.tag_ref.cl100k_base] |
| tag | all | `reference` | 1 [m:tok.cand.tag_reference.o200k_base] | 1 [m:tok.cand.tag_reference.cl100k_base] |
| tag | all | `→` | 1 [m:tok.cand.tag_arrow.o200k_base] | 1 [m:tok.cand.tag_arrow.cl100k_base] |
| tag | all | `perf` | 1 [m:tok.cand.tag_perf.o200k_base] | 1 [m:tok.cand.tag_perf.cl100k_base] |
| tag | all | `performance` | 1 [m:tok.cand.tag_performance.o200k_base] | 1 [m:tok.cand.tag_performance.cl100k_base] |
| tag | all | `⚡` | 2 [m:tok.cand.tag_bolt.o200k_base] | 3 [m:tok.cand.tag_bolt.cl100k_base] |
| tag | all | `todo` | 1 [m:tok.cand.tag_todo.o200k_base] | 1 [m:tok.cand.tag_todo.cl100k_base] |
| tag | all | `TODO` | 1 [m:tok.cand.tag_todo_upper.o200k_base] | 1 [m:tok.cand.tag_todo_upper.cl100k_base] |
| tag | all | `□` | 1 [m:tok.cand.tag_box.o200k_base] | 2 [m:tok.cand.tag_box.cl100k_base] |
| line | python_shell | `#@ inv:len<=cap` | 7 [m:tok.cand.line_hash_ascii.o200k_base] | 5 [m:tok.cand.line_hash_ascii.cl100k_base] |
| line | python_shell | `#§ △len<=cap` | 6 [m:tok.cand.line_hash_unicode.o200k_base] | 7 [m:tok.cand.line_hash_unicode.cl100k_base] |
| line | python_shell | `# invariant: len<=cap` | 6 [m:tok.cand.line_hash_words.o200k_base] | 6 [m:tok.cand.line_hash_words.cl100k_base] |
| line | slash_line | `//@ haz:keep timeout` | 5 [m:tok.cand.line_slash_ascii.o200k_base] | 5 [m:tok.cand.line_slash_ascii.cl100k_base] |
| line | slash_line | `//§ ⚠keep timeout` | 6 [m:tok.cand.line_slash_unicode.o200k_base] | 7 [m:tok.cand.line_slash_unicode.cl100k_base] |
| line | sql_line | `--@ cpl:db/schema.sql:users` | 10 [m:tok.cand.line_dash_ascii.o200k_base] | 10 [m:tok.cand.line_dash_ascii.cl100k_base] |
| line | sql_line | `--§ ↔db/schema.sql:users` | 9 [m:tok.cand.line_dash_unicode.o200k_base] | 8 [m:tok.cand.line_dash_unicode.cl100k_base] |
| line | c_style_block | `/*@ sec:check auth */` | 7 [m:tok.cand.line_block_ascii.o200k_base] | 6 [m:tok.cand.line_block_ascii.cl100k_base] |
| line | c_style_block | `/*§ ◎check auth */` | 6 [m:tok.cand.line_block_unicode.o200k_base] | 7 [m:tok.cand.line_block_unicode.cl100k_base] |
| line | pascal_brace | `{@ inv:len<=cap }` | 7 [m:tok.cand.line_pascal_brace.o200k_base] | 6 [m:tok.cand.line_pascal_brace.cl100k_base] |
| line | pascal_star | `(*@ inv:len<=cap *)` | 8 [m:tok.cand.line_pascal_star.o200k_base] | 7 [m:tok.cand.line_pascal_star.cl100k_base] |
