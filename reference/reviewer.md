# coded-comments: reviewer

Check the comments added or changed in a diff, test files included, plus unchanged coded lines that name a symbol
renamed in it. Report; do not edit code. Rules: `rules/core.yaml`, `grammar.md`, `exemptions.md`, your host file.

## Classify each comment (first match wins)

0. Find comments by the host file's `line` and `block` tokens. Text inside a string literal or a doc body is not a comment line.
1. The whole comment is a recognized pragma, legal text or generated marker: EXEMPT. Prose after a pragma is FREE.
2. Carries the host marker: CODED. If `grammar.md` fails: SYNTAX. Else check S1 (PROSE), anchors (STALE), a blank or
   uncoded gap before the target (SCOPE), the WHAT gate (REDUNDANT, VACUOUS), evidence (UNSUPPORTED), the same fact
   twice (DUP). At the end of the diff: BUDGET.
3. A doc comment on a declaration: truly exported (host file) is EXEMPT-DOC, check DOCCAP; not exported is FREE;
   undecidable is UNKNOWN. Never assume exempt.
4. Anything else, every block comment included: FREE.

## Findings

| class | sev | act | when |
|---|---|---|---|
| `FREE` | H | block | prose that is neither coded nor exempt; any block comment |
| `SYNTAX` | H | block | has the marker but fails the grammar, S5 (operator count) or S7 (`why` without `not`) |
| `PROSE` | H | block | no anchor or operator (S1), a `prose_signals` hit, or a clause that reads as a sentence |
| `STALE` | H | block | an anchor does not resolve, or a symbol-shaped word is not a symbol |
| `UNKNOWN` | M | warn | a required check cannot be decided: doc export status, unreadable repository |
| `VACUOUS` | M | warn | reads as a fact but asserts nothing checkable (`why retry_count works`) |
| `REDUNDANT` | M | warn | restates code, narrates, paraphrases, or is history |
| `UNSUPPORTED` | M | warn | `hazard` the compiler or tests flag; `perf` with no number or bound; `see` to adjacent code; `todo` with no target |
| `SCOPE` | M | warn | a blank or uncoded line between a coded run and its target |
| `DUP` | L | warn | the same fact twice |
| `DOCCAP` | L | warn | exempt doc over its cap, or only repeats the name |
| `BUDGET` | L | warn | over a `budgets` limit in `rules/core.yaml` |

A well-formed `#n` is accepted; tracker state is not checked.

## Output

```
<path>:<line> <CLASS> <H|M|L> <block|warn> <detail, 12 words at most>
VERDICT <BLOCK|WARN|PASS> H=<n> M=<n> L=<n>
```

BLOCK if any H; else WARN if any M or L; else PASS. Cheapest fix first: delete, recode, resolve.

```report
db/025.sql:5 STALE H block RefreshTokenBackend._ensure_schema has no such method
api/user.go:40 UNKNOWN M warn doc on Load; export status undecided
VERDICT BLOCK H=1 M=1 L=0
```
