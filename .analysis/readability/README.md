# Readability test: can an agent read coded comments from the entry snippet alone?

Codex (`gpt-6-sol`, `codex exec -s read-only --ephemeral`, empty working directory) received only the text of
`reference/ENTRY.md`, the part an agent always has in its CLAUDE.md, plus code snippets. It was told not to read files
or run commands; every run's `events.jsonl` shows 0 command executions and 0 tool calls. For each snippet it explained
every coded comment in prose and named anything ambiguous. Each explanation was graded against the snippet's answer key
(`key` in `snippets.jsonl` and `holdout.jsonl`).

## Rubric

PASS when every key point is stated or unmistakably implied and nothing is misread: operator direction, order,
condition, anchor kind, governed code. For a `why` line the answer must also present the choice as required
(imperative, "deliberately", "instead of", "rather than") or name the rejected option; describing the behavior alone is
WEAK. FAIL is any misreading. `unsure` notes asking for facts the snippet does not show are not counted. Acceptance:
two consecutive runs at 100% on both sets.

## Runs

| run | change before the run | 50-snippet set | 15-snippet holdout |
|---|---|---|---|
| 1 | readable syntax: full-word tags, `=>` "leads to", `before`/`after`, spaces | 48 (22 weak; 45 snippet defect) | - |
| 2 | ENTRY: "`why` marks a deliberate choice to keep, `see` only points"; snippet 45 fixed | 49 (28 weak) | - |
| 3 | todo completion form `done when <path:symbol> <state>` | 50 | 15 |
| 4 | ENTRY trimmed to 150 tokens: why gloss "(deliberate choice, keep)" | 49 (22) | 15 |
| 5 | why gloss "(a deliberate choice to keep)" | 49 (22) | 15 |
| 6, 7 | why gloss "(deliberate choice, do not change)", `#n` gloss dropped | 48, 48 (7, 22) | 15, 15 |
| 8, 9 | writing rule: a `why` line names the rejected option (`why <choice>, not <alt>; <reason>`); snippets 7 and 22 rewritten to it | 49 (22), 50 | 15, 15 |
| 10, 11 | why gloss "(deliberate choice; `not X` is the rejected option)", `see` gloss dropped | **50, 50** | **15, 15** |

Weak items were always `why` lines that only described the behavior, never a misreading. Lines that named the rejected
option (24, 38, 46, 103, 114) passed in every run. Run 1 also exposed a factual error in snippet 45 (SQLite's
999-variable limit does not bound an `executemany` batch); the snippet was corrected, not the notation. Notation
misreadings across all 11 runs and 9 holdout runs: 0.

Final `ENTRY.md` (148 o200k tokens) is the one in `round_10/entry_used.md` and `round_11/entry_used.md`.

Coverage: 10 tags, 14 hosts, every operator, `before`/`after`, multi-fact `;` lines, `#n`, `path:symbol`, `doc:`
anchors, backtick literals, trailing comments and runs of two lines. The holdout was written after run 3 and never
used to change the notation.

## Files

`prompt.md` (template), `snippets.jsonl`, `holdout.jsonl` (snippets and answer keys, current versions), and per run
`round_NN/`, `holdout_NN/`: `prompt.txt` (exactly what was sent), `entry_used.md`, `answers.jsonl`, `events.jsonl`.
