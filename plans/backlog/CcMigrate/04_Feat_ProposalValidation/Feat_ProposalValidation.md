# Feature 04: Proposal Validation

## Description

Turn each unit's deterministic disposition or Haiku judgment into a **validated, placement-ready Proposal**. Every
coded line Haiku returns is composed with the host marker, then checked against the grammar, the budgets, anchor
resolution and anchor provenance. Invalid lines are dropped; a REWRITE whose lines all fail becomes DROP. CAP text is
checked against the exemption cap. Then each file is held to its `coded_per_code` budget and `run_lines` limit by a
deterministic trimming rule. The output is `proposals.jsonl` plus `manifest.json`: the single input of the report
(F5) and of apply (F6).

## Proposal record (one JSON line per unit)

```
{
  unit_id, path, host, kind, start_byte, end_byte, start_line, end_line, file_sha256,
  original_text,                       # exact bytes of the span (UTF-8)
  disposition: KEEP | DROP | REWRITE | CAP,
  source: deterministic | judge | validator | budget,
  reason,                              # exemption/drop reason, Haiku reason, or validator/budget cause
  judgment_key?, judge_decision?, malformed_cause?,
  lines: [composed coded lines],       # for REWRITE / CAP
  dropped_lines: [{line, class, detail}],
  cap_text?,                           # for CAP
  pragma_prose?,                       # true for prose split off a pragma (F2 Story 01); its span excludes the pragma bytes
  warning?,                            # e.g. "FREE pragma_boundary_unknown" on a pragma kept unchanged (Decision D7)
  placement: {mode: in_place | above_target | trailing, target_line, target_start_line, indent}
}
manifest.json: {run_id, repo_root, head_commit, created_at, model, settings_hash, files:{path: sha256}, complete: bool,
                incomplete_keys?: [{judgment_key, cause, unit_ids}]}
```

**Incomplete run (Decision D11):** when F3 returns a run with unjudged keys, F4 writes `manifest.json` with
`complete:false` and `incomplete_keys`, and writes **no** `proposals.jsonl`. F5 still renders the report from the
manifest and the run state, and F6 refuses the run. A complete run writes both files with `complete:true`.

## Technical Architecture

```
units + judgments.jsonl
   |
   +── run incomplete (unjudged keys) -> ProposalStore.write_manifest(complete:false, incomplete_keys); stop
   v
ProposalBuilder ── deterministic dispositions pass through (KEEP/DROP with reason)
   |              ── malformed judgment -> DROP (source=judge, reason=malformed:<cause>)
   v
LineComposer (marker + " " + tag + " " + body)
   v
CodedLineValidator (F2) + AnchorResolver (basename expansion, provenance) ──> invalid -> dropped_lines
   v
DecisionConsistency (DROP/REWRITE/CAP cardinality, CAP only when exported)
   v
CapValidator ──> invalid cap -> CAP becomes REWRITE (if lines remain) or DROP
   v
BudgetTrimmer per file (run_lines, coded_per_code)
   v
ProposalStore -> proposals.jsonl, manifest.json
```

## Dependencies

- F2 (`CodedLineValidator`, `RepoIndex`, deterministic dispositions); F3 (`judgments.jsonl`, `RunState`).

## Stories

1. **01_Story_ValidatedProposalsWithBudgetTrim**: all of the above; `migrate` (dry run) writes `proposals.jsonl` and
   prints a validation summary.

One story: composition, validation, cap checking and trimming are one indivisible user outcome (a trustworthy
proposals file). Splitting them would leave untestable intermediate states.

## Integration Points

- F5 reads `proposals.jsonl`, `manifest.json` and `RunState` usage.
- F6 applies `proposals.jsonl`; it never calls the API and never re-validates semantics, but it re-checks file hashes.
