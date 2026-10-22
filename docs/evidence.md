# Evidence behind the reference tree

Not installed. The files in `reference/` are instructions only; every measurement, count and justification behind
them is here, keyed to `.analysis/numbers.json` by bracketed m:ID keys. Token counts use tiktoken (o200k and cl100k) as a PROXY
for Claude's tokenizer; the Anthropic count API was not available.

The labeled samples, scripts and results are in `.analysis/`. The per-file manifests (`provenance.tsv`,
`marker_scan_files.tsv`, `ratio_files*.tsv`) are not published, and re-running the scripts needs the original
repositories.

## Corpus and ratios

Source files touched by Claude-coauthored commits across 27 local repository checkouts (`.analysis/provenance.md`). Comment-to-code line
ratios per host: `.analysis/ratios.md`, `ratios_other.md`, docstring-inclusive `doc_volume_*.md`. Python rises from
0.148 to 0.546 when docstrings count as non-code [m:ratio.python.comment_to_code] [m:doc.python.inclusive_ratio].
C, C++ and Pascal had no non-test corpus files; SQL dialects are pooled.

## The WHAT gate

Redundant comments were 34 of 72 sampled [m:disp.all.redundant] against 24 valuable [m:disp.all.valuable]; 14 of 36
sampled docs were redundant [m:docsample.disp.redundant] against 14 valuable [m:docsample.disp.valuable].

| kind | in 72 / in 36 docs | example, now deleted |
|---|---|---|
| restates code | 22 / 9 | `Parse subcommand` above `subcommand.split(...)` |
| narrates steps | 7 / 2 | `Cleanup` above `rm -rf "$temp_dir"` |
| history, review round, story id | 4 / 0 | `Issue #151 round 3, CHANGE 1:` |
| business paraphrase | 1 / 2 | `one record per method with a known return type` |
| duplicates a doc | 0 / 1 | a return-value table copied from another function's doc |

Sources [m:cat.all.restates_code] [m:cat.all.narrates_steps] [m:cat.all.history_changelog]
[m:cat.all.business_paraphrase] [m:docsample.cat.restates_code] [m:docsample.cat.narrates_steps]
[m:docsample.cat.business_paraphrase] [m:docsample.cat.duplicates_docs]. Small samples, one labeler; a second
labeler agreed on 5 of 10 categories and 8 of 10 export judgments.

## Tags

Hits in the 72 comments / 36 docs: `hazard` 7/0, `coupled` 4/2, `security` 4/1, `invariant` 3/5, `external` 2/0,
`order` 2/2, `why` 2/1, `see` 0/3 [m:cat.all.hazard_guard] [m:cat.all.cross_file_coupling] [m:cat.all.security_boundary] [m:cat.all.invariant]
[m:cat.all.external_constraint] [m:cat.all.ordering_lifecycle] [m:cat.all.rationale_alternative]
[m:docsample.cat.reference]. `perf` and `todo` had none in the frozen samples; a later keyword search of the sampled
files found [m:search.todo_lines] `TODO` lines and at least [m:search.perf_keyword_lines] perf-keyword lines (a lower
bound), and real pairs below. The tags were first abbreviated (`inv`, `haz`, `cpl`...; `cpl` cost 2 tokens
[m:tok.cand.tag_cpl.o200k_base]). The full words used now (`hazard coupled security invariant external order why see
perf todo`) each cost 1 token in o200k and cl100k (`.analysis/readability/`), so readability costs nothing here.

Marker `^` was chosen by measured overhead and zero corpus collisions (`.analysis/marker_decision.json`). The
pace-maker glyph intel style cost 5,271 o200k tokens against 3,998 for positional ASCII over 300 real lines, so it
was rejected [m:intel.total.glyph.o200k_base] [m:intel.total.positional.o200k_base]. The clause separator `;` was
chosen over alternatives that differ by at most 6 tokens [m:sep.total.semi.o200k_base]
[m:sep.total.comma.o200k_base]. The backtick literal costs 30 tokens bare against 42 quoted for eight items
[m:bt.total.raw.o200k_base] [m:bt.total.quoted.o200k_base].

## Before and after (real comments)

Original text against kept lines plus coded lines; a pragma or shebang the case kept stays.

```coded
--^ coupled token-family tables with src/code_indexer/server/storage/sqlite_backends/refresh_token_backend.py:RefreshTokenSqliteBackend._ensure_schema
#^ order ensure_encryption_key_salt before manager init; failure => abort startup
//^ invariant topN <= maxSimpleTopN; slice <= 1MiB
//^ hazard missing abi_version must parse as None, not current ABI; #1784
#^ external /etc/tlp.conf is read last => wins over /etc/tlp.d/*.conf
#^ external TLP >= 1.10 required; _AC/_BAT/_SAV are profile suffixes
#^ external leaving _AC unset keeps GNOME Performance toggle working
//^ why return null, not throw; parse error => caller logs warning
//^ security allowed-tools list set => strip --dangerously-skip-permissions; that flag bypasses --allowedTools
//^ see rust/xray-core/src/compiler/graph_preamble.rs:is_definitely_dead_code; verdict table
#^ todo derive repos_skipped from domains-to-repos mapping; #874
#^ perf regex_query = linear-time DFA; no backtracking
```

The per-case counts below were measured on the earlier compact form of these lines (abbreviated tags, `<` for
"before", no spaces). The readable form above costs 230 o200k / 228 cl100k tokens against 218 / 217 compact (+5.5%),
still 73% below the 868-token originals.

| tag | original | tokens before -> after, compact form (o200k / cl100k) |
|---|---|---|
| `coupled` | 3-line SQL banner naming the creator | 21 -> 32 / 20 -> 32 |
| `order` | 2-line story note on seeding a key file | 35 -> 17 / 33 -> 16 |
| `invariant` | 3-line CodeQL false-positive note (pragma kept) | 53 -> 26 / 53 -> 27 |
| `hazard` | 3-line bug note on legacy metadata | 54 -> 15 / 53 -> 15 |
| `external` | 21-line shell header on TLP precedence (shebang kept) | 350 -> 59 / 351 -> 59 |
| `why` | 1-line error-handling note | 15 -> 12 / 15 -> 12 |
| `security` | 6-line XML doc on a private helper | 91 -> 23 / 91 -> 23 |
| `see` | 7-line private doc restating another function | 128 -> 23 / 128 -> 23 |
| `todo` | 2-line TODO with a deferral note (an `invariant` for the contract was dropped: the call passes literal 0) | 43 -> 16 / 43 -> 16 |
| `perf` | 4-line note on a DFA regex engine | 78 -> 13 / 79 -> 13 |
| all 10 | | 868 -> 236 / 866 -> 236 |

Totals [m:pair.total.orig.o200k_base] -> [m:pair.total.after.o200k_base] (o200k), [m:pair.total.orig.cl100k_base] ->
[m:pair.total.after.cl100k_base] (cl100k): about 71% fewer on this hand-picked set, not a corpus rate. `coupled` grew
because a resolvable path costs more than the stale short name it replaced. Real stale-reference case: a migration
comment named `RefreshTokenBackend._ensure_schema`; the protocol class has no such method, the method is declared on
`RefreshTokenSqliteBackend`.

## Exemptions

Of 18 lexically public doc spans in the sample, 6 were truly exported and 7 were not [m:docsample.lex.public.export.yes]
[m:docsample.lex.public.export.no]; 5 stayed undecided. In Rust (tests excluded) 2,860 lexically private against 1,450
lexically public doc lines [m:doc.rust.excl_tests.private_lines] [m:doc.rust.excl_tests.public_lines]; the truly
exported share is smaller still. Corpus case behind the pragma rule: a Go comment `// codeql[...] False positive: topN
is bounded ...` kept its pragma and moved the explanation to `//^ invariant topN <= maxSimpleTopN; slice <= 1MiB`.

## Budgets

Measured, 12 coded lines in the ten pairs: mean [m:budget.coded.chars_mean] and maximum [m:budget.coded.chars_max]
characters, mean [m:budget.coded.tokens_mean] and maximum [m:budget.coded.tokens_max] o200k tokens, longest run
[m:budget.coded.run_max] lines; the ten originals had [m:budget.pairs.orig_lines] lines and became
[m:budget.pairs.coded_lines] ([m:budget.pairs.line_keep_ratio] kept). Limits are design choices: `line_chars` 160 is
about 14% above the longest line; `line_tokens` 40 is above the longest 32; `run_lines` 3 equals the longest run;
`coded_per_code` 0.10 is a conservative ceiling to tune per project.

Illustration, not a prediction: baseline x (24/72 valuable share) x 0.231 line-keep gives 0.013 (TS/JS)
[m:budget.projected.typescript_js] to 0.057 (SQL) [m:budget.projected.sql] coded lines per code line, highest
[m:budget.projected.max]. It multiplies a share from 72 sampled records by a retention fraction from ten hand-picked
valuable spans, so it is a scenario and not an expected density.

Percent a 0.10 ceiling lowers each measured baseline (a scale comparison: the baselines include exempt prose docs and
other comments, so these are not predicted cuts in total comment volume): Python [m:budget.cut_to_ceiling.python]%,
TS/JS [m:budget.cut_to_ceiling.typescript_js]%, shell [m:budget.cut_to_ceiling.shell]%, Go
[m:budget.cut_to_ceiling.go]%, Rust [m:budget.cut_to_ceiling.rust]%, C# [m:budget.cut_to_ceiling.csharp]%, Java
[m:budget.cut_to_ceiling.java]%, SQL [m:budget.cut_to_ceiling.sql]%. A large generated or table-like section dilutes a
whole-file ratio, so a reviewer also inspects density in the changed region.

## Removed rules

Stopword, operand-length and label-length checks (old S2-S4) were dropped under Amendment 6: they only patched prose
bypasses with syntax. The WHAT gate, the line caps and the reviewer's judgment cover meaning. Examples that shaped
that choice are in `grammar-examples.md`.

## Load paths (Amendment 6 targets)

Before the restructure the installed tree was about 10,100 o200k tokens in 8 files with 64 citation keys. After the
restructure and the readability change it is 6,072 tokens in 24 files with 0 citation keys
(`.analysis/measure_paths.py`, `numbers.json` keys `path.*`). Files, o200k: ENTRY 148, index 178, what 671, how 969,
grammar 556, reviewer 754, exemptions 320, core.yaml 795, migrate 234, examples 337, hosts 53 (shell) to 133
(typescript_javascript), all 14 under the 150 target.

| path | files | tokens | cap | target |
|---|---|---|---|---|
| writer | what + how + a host file | 1,790 | with a 150 allowance | 2,000 |
| writer, largest host | the same with typescript_javascript (133) | 1,773 | measured | 2,000 |
| reviewer | reviewer + what + core.yaml + grammar + exemptions + a host file | 3,246 | with a 150 allowance | 3,500 |
| reviewer, largest host | the same with typescript_javascript (133) | 3,229 | measured | 3,500 |
| entry snippet | `ENTRY.md` | 148 (cl100k 147) | measured | 150 |

Counts are tiktoken o200k, a proxy for Claude's tokenizer; the Anthropic counting API was unavailable.
