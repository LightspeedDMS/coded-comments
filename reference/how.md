# coded-comments: HOW to document

Marker: `marker` in your host file, `hosts/<host>.yaml`, written with its space (`# ^`, `// ^`, `-- ^`).

## Line

`<marker> <tag> <clause>[; <clause>]`. One fact per line, one tag per line; a second fact is a second full line.
Write terse facts, not sentences: keep the verbs that carry meaning ("must parse as", "keeps", "is read last"), drop
filler ("this function", "note that", "we"), no full stop. Name symbols and paths. Never glue ideas with `: `, "so",
"but", "because" or "which": make each idea a clause with an operator, or a second line.

Operators: `=>` leads to (causes, then, returns, requires); `=` is; `!=` is not; `<` `<=` `>` `>=` compare values
only. A clause has at most one `=>` and one comparison per side: `removing X => ints > 4300 digits raise`. Order is written with the words `before` and `after`. Anchors: `path:symbol`, `#123` (issue),
`doc:anchor`, `test:Name` (a test that fails on the wrong edit), symbol names. Quote names that hold operator
characters: `` `Vec<u8>`.len() ``, `` `1-eps` ``. Every line needs an anchor, an operator, or `before`/`after`.

## Tags

| tag | shape |
|---|---|
| `hazard` | `hazard <change> => <failure>[; <ref>]` |
| `coupled` | `coupled <this> with <path:symbol>[; <what must change together>]` |
| `security` | `security <subject> => <guard or exposure>` |
| `invariant` | `invariant <subject> <cmp> <bound or state>` |
| `external` | `external <system> <constraint>[; doc:<anchor>]`, give the anchor whenever a doc exists |
| `order` | `order <first> before <second>[; <rule>]` |
| `why` | `why <choice>, not <alternative>; <reason>`, the first clause always names the rejected alternative |
| `see` | `see <path:symbol or doc:anchor or #n>[; <label>]`, asserts no constraint |
| `perf` | `perf <subject> = <cost or bound>[; <measurement ref>]`, the number is the evidence |
| `todo` | `todo <action>; #<issue>` or `todo <action>; done when <path:symbol> <state>` |

```coded
// ^ hazard missing abi_version must parse as None, not current ABI; #1784
-- ^ coupled token-family tables with src/code_indexer/server/storage/sqlite_backends/refresh_token_backend.py:RefreshTokenSqliteBackend._ensure_schema
// ^ security empty AllowedMcpTools => all tools allowed
// ^ invariant topN <= 1024 before make; slice <= 1MiB
# ^ external playwright --with-deps works on Debian only; doc:playwright-cli#install
# ^ order ensure_key_salt before manager init; failure => abort startup
// ^ why retry 3 times, not backoff; server drops idle conns after 30s
// ^ hazard evicting idle buckets before refill => key gets free tokens; test:TestSweepKeepsPartialBuckets
// ^ see doc:rfc9110#9.3.1; GET semantics
// ^ perf regex_query = linear-time DFA; no backtracking
# ^ todo split parse_config; #412
```

## Placement and freshness

Tests are code: the same gate applies to test files, and a test's name and asserts are its documentation. Put the run
directly above the declaration or statement it governs, or trail the statement it governs; a blank line ends the run. File-wide facts go at the top after any license or shebang. Anchors must resolve: the path exists, the
symbol is declared there, the `doc:` anchor exists. When you rename or move a symbol, search the tree for the old name
and fix every coded line that names it.

## Limits

| key | limit |
|---|---|
| `line_chars` | 160 |
| `line_tokens` | 40 |
| `run_lines` | 3 |
| `coded_per_code` | 0.10 |
| `min_code_lines` | 50 |
| `diff_floor` | 2 |
| `diff_per` | 10 |

`coded_per_code` is coded lines per code line (non-blank, non-comment) in a file with at least `min_code_lines` code
lines; judge the changed region too, not only the whole file. A diff may add `max(diff_floor, ceil(added code lines /
diff_per))` coded lines. Exception for migration: when the file's non-exempt comment lines decrease and every new
coded line passed the gate, the diff allowance does not apply; the file ratio still does. Over a limit: delete the
weakest line.
