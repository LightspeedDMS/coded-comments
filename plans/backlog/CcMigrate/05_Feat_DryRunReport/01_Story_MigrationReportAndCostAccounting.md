# Story 01: Migration Report and Cost Accounting

## User Story

**As a** developer deciding whether to apply a migration
**I want** a dry-run report with per-file and total counts (DROP, REWRITE, CAP, KEEP by kind, skipped), comment
tokens before and after, the API cost actually incurred, and each file's budget status
**So that** I can see exactly what the migration will do and what it cost before any file changes

**What the user can do after this story:** after `cc-migrate migrate <path>`, read the headline on stdout
(units, DROP/REWRITE/CAP/KEEP, comment tokens before → after with the % reduction, actual $ cost, and the report path),
then open `report.md` and `summary.json` in the run directory. `migrate` writes both itself, for complete and
incomplete runs.

## Scope

- `TokenCounter`: o200k count of the comment bytes **before** (sum over all units' `original_text`) and **after**
  (KEEP units' original text + composed lines of REWRITE + CAP text + CAP lines). Comment lines are counted the same
  way. Every token figure is labeled "o200k proxy" in the output.
- `CostAccountant`: reads every stored `usage` from `RunState`. Per channel: `cost = rate_mult × (input_tokens ×
  in_rate + cache_creation_5m × in_rate × w5 + cache_creation_1h × in_rate × w1 + cache_read × in_rate × r +
  output_tokens × out_rate)`, with `rate_mult = 1` for warm-up and `batch_mult` for batch. Rates come from
  `[pricing.<model>]`; the long-prompt rate applies per request when its total input exceeds the threshold. If
  `usage.cache_creation` has no per-TTL breakdown, the configured `cache_ttl` multiplier is applied and the report
  says so.
- `SummaryWriter`: `report.md` (sections from `Feat_DryRunReport.md`), `summary.json` (the same numbers,
  machine-readable, schema-versioned), and the stdout headline. An **incomplete** run still gets a report, rendered
  from `manifest.json` (`complete:false`, `incomplete_keys`) and `state.json`: `complete: false`, each unjudged key with
  its cause and its units (`path:line`), the deterministic dispositions, and the actual API cost so far; proposals are
  not built for an incomplete run, so per-file token figures are omitted.
- `report(run_dir)` is called by `migrate` after F4; there is no separate report command.

## Algorithm

```
report(run_dir):                                         # called by migrate after F4 wrote manifest.json
  manifest  = load manifest.json                         # always present here (F4 writes it for complete and incomplete runs)
  state     = load state.json
  cost      = CostAccountant(state.usages, settings.pricing[manifest.model])
  IF NOT manifest.complete:
    incomplete = [(k.judgment_key, k.cause, [path:line of u for u in k.unit_ids]) for k in manifest.incomplete_keys]
    write report.md, summary.json (complete=false, incomplete, deterministic dispositions, cost so far) atomically
    print headline "incomplete: <n> keys unjudged; re-run migrate to resume"; RETURN    # migrate exits 3
  proposals = load proposals.jsonl
  totals = Counter(); per_file = {}
  FOR p IN proposals:
    before = o200k(p.original_text); lines_before = line_count(p.original_text)
    after_text = (p.original_text IF p.disposition == KEEP
                  ELSE "\n".join(p.lines) + ("\n" + p.cap_text IF p.disposition == CAP ELSE ""))
    after = o200k(after_text) IF after_text ELSE 0
    totals[p.disposition, p.source, p.reason_kind] += 1
    per_file[p.path].add(p, before, after)
  ratio_est_actual = state.estimate.input_tokens / cost.input_tokens_total
                     # RunState.estimate (F3 Story 02); total = input + cache_creation_input + cache_read_input tokens
  attention = top 20 DROP by before-tokens ∪ KEEP via extra_pragmas ∪ malformed keys
              ∪ proposals with warning "FREE pragma_boundary_unknown"   # listed as "<path>:<line> FREE pragma_boundary_unknown"
  write report.md, summary.json (atomic); print headline
  ASSERT sum(per_file units) == len(proposals)                           # reconciliation invariant
  ASSERT totals.KEEP + totals.DROP + totals.REWRITE + totals.CAP == len(proposals)
```

## Acceptance Criteria

```gherkin
Feature: dry-run report

  Scenario: Report after a completed dry run
    Given a completed dry run on a scratch repo
    When I open report.md and summary.json in the run directory
    Then they show totals by disposition that sum to the number of proposals
    And comment tokens before and after labeled "o200k proxy" with the % reduction
    And a per-file table with coded_per_code and budget status for each file
    And an actual cost section computed from stored usage, split into warm-up and batch
    And the target repo's git status is unchanged

  Scenario: Cost equals the sum of usage at configured prices
    Given recorded real usage records for one warm-up and 10 batch requests
    When the report is rendered
    Then the total cost equals the hand-computed sum using the pricing table and batch_mult to the cent

  Scenario: Incomplete runs are reported honestly
    Given a run with 3 unjudged keys, so manifest.json has complete false and no proposals.jsonl exists
    When migrate renders the report
    Then summary.json has complete false and lists the 3 keys
    And report.md lists each unjudged key with its units as path:line
    And the actual cost so far is shown
    And the exit code of migrate is 3

  Scenario: Pragmas with an undetermined prose boundary are listed as FREE warnings
    Given a completed dry run on a repo with the java comment "// CHECKSTYLE:OFF legacy mapping table follows" and no pragma_syntax entry for "CHECKSTYLE"
    When I open report.md
    Then its attention section lists "<path>:<line> FREE pragma_boundary_unknown" for that comment

  Scenario: Estimate versus actual uses the stored estimate
    Given a completed run whose state.json holds estimate.input_tokens
    When the report is rendered
    Then the estimated/actual input-token ratio equals estimate.input_tokens divided by the summed input, cache-creation and cache-read tokens

  Scenario: Files below min_code_lines are not budget-enforced
    Given a file with 20 code lines and 4 coded lines after migration
    Then its budget status is "n/a <min_code_lines"
```

## Implementation Status

- [ ] `TokenCounter` before/after for all dispositions
- [ ] `CostAccountant` per channel with TTL breakdown and long-prompt rates
- [ ] `report.md` and `summary.json` writers (atomic), stdout headline
- [ ] Attention section (incl. `FREE pragma_boundary_unknown` warnings)
- [ ] Incomplete-run report from `manifest.json` + `state.json` (unjudged units listed)
- [ ] Reconciliation invariants enforced
- [ ] Unit tests with recorded real usage and proposals fixtures
- [ ] E2E manual testing completed by Claude Code

**Completion:** 0/8 tasks complete (0%)

## Testing Requirements

- Hand-computed cost fixtures; invariant tests on synthetic and real proposals; follows the epic's **Testing Rules**
  (recorded real usage and responses allowed as report fixtures).

## Manual E2E Test Plan (Claude Code)

1. After a real dry run on a scratch repo, read `report.md` end to end. Check three per-file rows against
   `proposals.jsonl`, and the cost against the usage in `state.json` by a manual calculation.
2. Run `git -C <repo> status --porcelain` and confirm the repo is untouched.

## Definition of Done

- Scenarios automated and passing; coverage > 85%; zero warnings; manual evidence recorded.
