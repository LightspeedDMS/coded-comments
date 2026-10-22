# coded-comments: HOW to document

Marker: `marker` in your host file, `hosts/<host>.yaml`.

## Line

`<marker> <tag> <clause>[;<clause>]`. One fact per line, one tag per line; a second fact is a second full line.
Write facts, not sentences: `a op b`, or an anchor. Name symbols and paths, not "this function". Operators: `=>` then,
`<` before, `>` after, `<=` `>=` bounds, `=` is, `!=` differs; one per clause. Anchors: `path:symbol`, `#123`,
`doc:anchor`, symbol names. Quote names that hold operator characters: `` `Vec<u8>`.len() ``. Every line needs an
anchor or an operator. No space after `;`.

## Tags

| tag | shape |
|---|---|
| `haz` | `haz <change>=><failure>[;<ref>]` |
| `cpl` | `cpl <this>=<path:symbol>[;<more>]` |
| `sec` | `sec <subject>=><guard or exposure>` |
| `inv` | `inv <subject><op><bound or state>` |
| `ext` | `ext <system>=<constraint>[;doc:<anchor>]`, give the anchor whenever a doc exists |
| `ord` | `ord FIRST<SECOND[;<rule>]` |
| `why` | `why <cause>=><choice>` or `why <symbol> not <alternative>` |
| `ref` | `ref <path:symbol or doc:anchor or #n>[;<label>]`, asserts no constraint |
| `perf` | `perf <subject>=<cost or bound>[;<measurement ref>]`, the number is the evidence |
| `todo` | `todo <action>;#<issue>` or `todo <action>;<path:symbol>=<done>` |

```coded
//^ haz missing abi_version=>None not current ABI;#1784
--^ cpl token-family tables=src/code_indexer/server/storage/sqlite_backends/refresh_token_backend.py:RefreshTokenSqliteBackend._ensure_schema
//^ sec AllowedMcpTools empty=>open
//^ inv topN<=1024 before make;slice<=1MiB
#^ ext playwright --with-deps=Debian only;doc:playwright-cli#install
#^ ord ensure_key_salt<manager init;failure=>abort startup
//^ why retry=3 not backoff;server drops idle conns>30s
//^ ref doc:rfc9110#9.3.1;GET semantics
//^ perf regex_query=linear time DFA;no backtracking
#^ todo split parse_config;#412
```

## Placement and freshness

Put the run directly above the declaration or statement it governs, or trail the statement it governs; a blank line
ends the run. File-wide facts go at the top after any license or shebang. Anchors must resolve: the path exists, the
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
