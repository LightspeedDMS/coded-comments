# Design: coded comments

Overview and rationale only. The normative text is in `reference/`; this file links to it and does not repeat it.
Numbers come from `.analysis/numbers.json`; the narrative evidence is in `evidence.md`. Open choices:
`open-questions.md`.

## Problem and objective

AI-written code often carries about as much comment as code (the sampled ratios are in `evidence.md`). Much of it
restates code, narrates steps, copies docs or records history, and every installed instruction and every generated
comment costs context on each load. The objective is less junk in both: the instruction corpus an agent loads, and
the comments it writes. So the installed tree is instructions only, with token targets (entry <= 150, writer path
<= 2,000, reviewer path <= 3,500, host file <= 150), and evidence stays in `docs/` and `.analysis/`.

## Decisions

| decision | rationale | normative file |
|---|---|---|
| Admit a fact only through an ordered gate; the first question is whether an AI can derive it from this file or one hop away | most corpus comments failed that test; ten tags cover what carried value | `reference/what.md` |
| Coded line `<marker> <tag> <clause>[;<clause>]`, one fact per physical line | one regex classifies a line; no continuation lines | `reference/how.md`, `grammar.md` |
| Markers `#^`, `//^`, `--^` | chosen by measured token overhead and zero corpus collisions; `@` rejected for tool collisions | `reference/hosts/*.yaml` |
| Positional ASCII, not the pace-maker glyph style | glyph style cost 5,271 tokens against 3,998 over 300 real lines | `evidence.md` |
| Anchors (path, symbol, `#n`, `doc:`) or an operator on every line | references replace prose and can go stale detectably | `reference/grammar.md` |
| Backtick literal, no other escapes | operators inside names such as `Vec<u8>` | `reference/grammar.md` |
| Budgets: 160 chars, 40 tokens, 3-line runs, 0.10 coded lines per code line, diff allowance | design limits, tuned per project; real compression of ten pairs went from 868 to 236 tokens | `reference/how.md`, `rules/core.yaml` |
| Reviewer = spec plus rule data, no shipped validator | pace-maker can consume the YAML later; judgment classes only warn | `reference/reviewer.md`, `rules/core.yaml` |

## Protocol

- Writer: `what.md` gate, then `how.md` line shape and limits, then one host file for the marker.
- Reviewer: classify each comment (exempt, coded, exempt doc, free), then twelve finding classes with severity and
  block/warn, a one-line-per-finding report and a VERDICT line. `reviewer.md`.
- Migration: five steps and two real cases. `migrate.md`.
- Freshness: an anchor that stops resolving makes the line STALE (block); the writer fixes every coded line naming a
  symbol it renames. `how.md`, `grammar.md` rule S4.

## Exemptions and hosts

Prose stays only for pragmas, legal text and metadata, generated markers, and docs on the truly exported surface
(Amendment 3: not merely a non-underscore name), capped in length. `reference/exemptions.md` holds the kinds; each
host file holds its export test, block-comment forms, pragmas and generated markers. Fourteen hosts: Python, TS/JS,
Shell, Go, Rust, C#, Java, Pascal, C, C++, PL/SQL, PostgreSQL, T-SQL, SQLite. In the doc sample, 6 of 18 lexically
public docs were truly exported.

## Topology

`ENTRY.md` (in CLAUDE.md) points to `index.md`, which routes writing, reviewing, migrating and exemption questions to
the smallest file set. Installed by `install.sh` into `~/.claude/coded-comments/`.

## Verification

`.analysis/grammar_check.py` and `rules_check.py` validate every fenced coded example against the grammar and the rule
regexes, the reviewer table against `core.yaml`, and the 14 host files; `measure_paths.py` records sizes;
the installer was run twice on a fake HOME (log kept locally). Re-running the corpus scripts needs the original
repositories; their results are in `.analysis/numbers.json`.
