# Open questions and limitations

All user decisions are settled. What remains below are limits of the evidence and of the installer.

## Decided by the user (2026-10-14)

| # | question | decision |
|---|---|---|
| 1 | Marker sigil `^` or `@` | `^` kept: zero tool collisions, under one token more per comment (`.analysis/numbers.json`, keys `marker.*`) |
| 2 | `todo` target | Both `#issue` and a checkable `done when <path:symbol> <state>` (as in `how.md`) |
| 3 | `examples.md` | Shipped: compact, optional load (`reference/examples.md`, ~330 tokens) |
| 4 | Before→after pairs in `how.md` | Left out; the pairs stay in `docs/evidence.md` |
| 5 | Pascal and C line comments | `//` bindings confirmed (Delphi, Free Pascal, C99+). Strict ISO Pascal and C89 are out of scope |
| 6 | TS/JS exported surface | Libraries: `export`, `export { Local }`, public members of exported classes. App repos (package.json private, or no main/exports/types): only what the package entry point re-exports |
| 7 | Readability (2026-10-21) | Full-word tags, `=>` "leads to", `before`/`after` for order, spaces allowed, verbs kept, `why` names the rejected option. +5.5% tokens on the 12 real lines; Codex reading only `ENTRY.md` explained 50 + 15 snippets with no misreading in two consecutive runs (`.analysis/readability/`) |
| 8 | Marker form and example-build fixes (2026-10-22) | Spaced canonical marker `# ^`, `// ^`, `-- ^`: black 25.9 and ruff 0.14 rewrite `#^` everywhere, and gofmt rewrites `//^` in doc-comment position; the spaced form costs +0 tokens on the 12 evidence lines (230 o200k / 228 cl100k, both forms). Readers accept spaced and legacy unspaced (`markers` regex `# ?\^` in `core.yaml`, written form in `canonical`). New `test:Name` anchor (a test that fails on the wrong edit). S7: a `why` line starts `<choice>, not <alternative>` (`why_form`). `prose_signals` (`: `, so, but, because, which) feed the reviewer's PROSE judgment and are not a grammar failure. Tests are in scope. `ENTRY.md` v2, 210 tokens (target 220). Formatter matrix: `.analysis/formatters/`; corpus rescan: `.analysis/marker_spaced.json` |
| 9 | Clause rule (2026-10-22) | `=>` binds loosest: a clause is `side => side`, one comparison per side. Evidence: the writer probe produced `removing set_int_max_str_digits(0) => printing ints > 4300 digits raises ValueError` in 4 of 4 runs, invalid under one-operator-per-clause. Two `=>` in a clause or two comparisons on a side stay invalid (S5). `ENTRY.md` is now 214 tokens (target 220) |

## Limits of the evidence

- Category labels come from a single labeler; disagreement was measured and counts are a range.
- C, C++ and Pascal had no non-test corpus files, and the four SQL dialects are pooled. Those host files rest on
  syntax knowledge; their `pragma`, `generated` and `block` values were not measured.
- Token counts use tiktoken `o200k_base` and `cl100k_base`, proxies for Claude's tokenizer. The Anthropic counting
  API was unavailable.
- Budget limits (`coded_per_code` 0.10, `run_lines` 3, and the rest) are design choices to tune per project.

## Installer limitation

Replacement removes the old directory before moving the staged copy in. An interruption between those steps leaves
`~/.claude/coded-comments` absent until the next install, and a SIGKILL can leave a hidden `.coded-comments.stage.*`
directory. Neither touches other files.
