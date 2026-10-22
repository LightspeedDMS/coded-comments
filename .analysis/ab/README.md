# A/B and probe runs: does the rule set change what an agent writes?

Run 2026-10-22, after the example builds in `examples/` showed agents keeping their usual prose next to coded lines.
Each run is a headless `claude -p --setting-sources project` session: it loads only the run directory's `CLAUDE.md`
(the entry snippet, with `~/.claude/coded-comments/` rewritten to the variant's rule tree) and no user-level
instructions or hooks. v1 is `reference/` at commit 06c14d0, v2 is the 2026-10-22 working tree. The harness (scripts,
comment-stripped bases, transcripts) stayed in a session scratch directory and is not published; this file keeps the
results.

## Edit runs (12)

Each project from `examples/` was copied with every comment stripped, and the agent was given one feature task with no
mention of comments: fib-cli `--format dec|hex`; ratelimiter-go per-request `cost` on `POST /check`; ledger-ts
`ledger reverse <id> --key <k>`. Two runs per project and variant.

| project / variant | coded lines (prod) | prose lines | tests pass | read `index.md` | also read |
|---|---|---|---|---|---|
| fib-cli v1, v2 | 0, 0 | 0 | 4/4 | 4/4 | - |
| ratelimiter-go v1, v2 | 0, 0 | 0 | 4/4 | 4/4 | `what.md`, `how.md`, host file |
| ledger-ts v1, v2 | 1 per run, 0 | 0 | 4/4 | 4/4 | `what.md`, `how.md`, host file |

The two coded lines (v1, ledger-ts) were both valid: `//^ security where is interpolated into SQL => keep it a
literal union, never caller input` and `//^ hazard widening column beyond literal names => SQL injection; it is
interpolated, not bound`. No run wrote prose or a docstring. Reading: with a clean context the snippet already
suppresses prose; the prose in the example builds came from their context (a TDD persona and a large global
instruction file), not from the snippet. The edit runs cannot separate v1 from v2.

## Reviewer probe (4)

The agent reviewed the ratelimiter-go test files as built (prose comments kept) against the rules. All four runs, v1
and v2, flagged the prose as `FREE`, 50 to 51 findings each, verdict BLOCK. The reviewer path catches what the writers
let through.

## Writer probe (8)

Seven facts from the example builds (`FACTS.txt`, the same facts as readability snippets 51-57), each to be recorded
as a comment in a named file.

| variant | runs | grammar-valid | `why` in S7 form | prose signals | over budget |
|---|---|---|---|---|---|
| v1 | 2 | 6/7, 6/7 | 3/3 | 0 | 0 |
| v2 | 2 | 6/7, 6/7 | 3/3 | 0 | 0 |
| v2, relaxed `=>` | 2 | 7/7, 7/7 | 3/3 | 0 | 0 |

The line that failed in all four first runs was `removing set_int_max_str_digits(0) => printing ints > 4300 digits
raises ValueError`: a comparison inside the result of `=>`, invalid under one operator per clause. The grammar now
lets `=>` bind loosest, one comparison per side (`reference/grammar.md` S5); under it all eight runs are valid. v2 runs
used the `test:` anchor and backtick literals (`` `1-eps` ``). One relaxed run wrote a second tag word inside a clause
(`; external CPython >= 3.9.14`), grammar-valid but against one tag per line; only a reviewer catches it.
