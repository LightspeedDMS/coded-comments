# Open questions and limitations

All user decisions are settled. What remains below are limits of the evidence and of the installer.

## Decided by the user (2026-10-14)

| # | question | decision |
|---|---|---|
| 1 | Marker sigil `^` or `@` | `^` kept: zero tool collisions, under one token more per comment (`.analysis/numbers.json`, keys `marker.*`) |
| 2 | `todo` target | Both `#issue` and a checkable `path:symbol=done` (as in `how.md`) |
| 3 | `examples.md` | Shipped: compact, optional load (`reference/examples.md`, ~330 tokens) |
| 4 | Before→after pairs in `how.md` | Left out; the pairs stay in `docs/evidence.md` |
| 5 | Pascal and C line comments | `//` bindings confirmed (Delphi, Free Pascal, C99+). Strict ISO Pascal and C89 are out of scope |
| 6 | TS/JS exported surface | Libraries: `export`, `export { Local }`, public members of exported classes. App repos (package.json private, or no main/exports/types): only what the package entry point re-exports |

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
