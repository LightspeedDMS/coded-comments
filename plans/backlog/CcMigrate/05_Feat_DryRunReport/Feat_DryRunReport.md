# Feature 05: Dry-Run Report

## Description

`cc-migrate migrate <path>` is a dry run by default. It never edits the target repo. This feature turns the
proposals and the run state into what a human decides on: a Markdown summary (`report.md`) and a machine-readable
`summary.json`, both in the run directory, with the headline printed to stdout. The proposals file from F4 is the
machine-readable per-unit record (original, decision, result, reason); the report aggregates it per file and in
total. `migrate` renders the report for every run that reaches F4, complete or incomplete (Decision D11): an
incomplete run has a `complete:false` manifest and no proposals, and its report shows which units are incomplete.

## Report contents

| section | figures |
|---|---|
| run | run id, repo, HEAD, model, effort, cache TTL, completion state, timestamps; for an incomplete run, every unjudged key with its cause and its units (`path:line`) |
| totals | units by disposition `KEEP` (by exemption kind), `DROP` (deterministic by reason, judge, malformed by cause, validator, budget), `REWRITE`, `CAP`; files scanned, files skipped by reason |
| tokens | comment tokens before and after (tiktoken `o200k_base` proxy, Decision D10); comment lines before and after; code lines |
| per file | path, host, units, DROP/REWRITE/CAP/KEEP, comment tokens before → after, coded lines after, `coded_per_code` and budget status (`ok`, `trimmed N`, `n/a <min_code_lines`) |
| API cost (actual) | from stored `usage` of every request: `input_tokens`, `cache_creation_input_tokens` (by TTL), `cache_read_input_tokens`, `output_tokens`, priced per channel (warm-up at standard price, batch at `batch_mult`); cache-hit share; estimated vs actual input-token ratio |
| validation | lines returned, kept, dropped by class |
| attention | the 20 largest DROPs by tokens, every `KEEP pragma` added via `extra_pragmas`, every malformed key, and every pragma kept unchanged because its prose boundary could not be determined, listed as a `FREE` warning (`<path>:<line> FREE pragma_boundary_unknown`, Decision D7), so the user can eyeball risk before `--apply` |

## Dependencies

- F4 (`proposals.jsonl`, `manifest.json`), F3 (`RunState` usage), F1 (line counts).

## Stories

1. **01_Story_MigrationReportAndCostAccounting**: everything above. One story: the report is one user outcome.

## Integration Points

- F6 prints an apply report in the same format, with an extra section for files applied, reverted and skipped.
- F7's acceptance checks reconcile `summary.json` against the proposals and against the files on disk after apply.
