# Feature 02: Deterministic Pre-classification

## Description

Decide, without any LLM, everything that needs no judgment (principle 5). Each `CommentUnit` gets a disposition:
`KEEP` (exempt), `DROP` (mechanical junk or invalid coded line), or `JUDGE` (goes to Haiku, including existing coded
lines that pass the deterministic checks; user decision). The repo index and the coded-line validator are built here,
because existing `^` lines must be validated before any judging and F4 reuses the same validator for new lines. Export status is decided per host, and units headed for judgment
are deduplicated so each distinct text is judged once.

After this feature, `cc-migrate scan` reports, per host and in total: kept by exemption kind, dropped by mechanical
reason, existing coded lines valid/invalid, units to judge, and distinct judgments after dedupe. This is the number
that drives cost.

## Classification order (first match wins)

```
0  file level   generated marker in the first `generated_marker_lines` (default 5) lines -> skip file "generated"
1  KEEP         hashbang on line 1
2  KEEP         encoding line or modeline in lines 1-2
3  KEEP         legal paragraph in the file's leading comment (copyright, (c), license, SPDX-License-Identifier,
                 "all rights reserved", "permission is hereby granted", "warranty"); non-legal paragraphs of the
                 same unit are split off and classified on their own
4  KEEP / SPLIT comment starts with a host pragma or a tool extra_pragma (Decision D7): the whole comment is the
                 pragma -> KEEP; pragma + prose with known argument syntax (pragma_syntax) -> split: pragma bytes KEEP,
                 prose becomes its own unit classified from step 4 on (normally JUDGE); boundary undeterminable ->
                 KEEP unchanged with a FREE "pragma_boundary_unknown" warning for the report
5  KEEP         a generated marker inside hand-written code (that line only)
6  JUDGE / DROP existing coded line(s): pass grammar, budget and anchor checks -> JUDGE "coded_valid" (Haiku returns
                 DROP or REWRITE like any unit); fail -> DROP with the violation class
7  DROP         empty comment
8  DROP         banner or divider
9  DROP         commented-out code
10 JUDGE        everything else (with `exported` decided for docstring and doc_comment kinds)
```

## Technical Architecture

```
CommentUnit[] --> ExemptionRules --> CodedLineValidator(existing) --> MechanicalDrops --> CommentedCodeProbe
                                              ^                                                  |
                                              |                                                  v
                                       RepoIndex (built once)                         ExportDeciders[host]
                                                                                                 |
                                                                                                 v
                                                                                 JudgmentDedupe -> JudgeQueue
```

- `RepoIndex`: repo-relative path set (from F1's enumeration plus every tracked path), basename → paths map,
  identifiers per file and repo-wide (Pygments `Name.*` tokens of every enumerated file), Python qualified names from
  `ast`. Built once per run, held in memory, never persisted.
- `CodedLineValidator`: driven by `rules/core.yaml` (regex parts, word classes, budgets) loaded through
  `ContentLoader`. It is the single source of truth: no regex or limit is duplicated in code.

## Dependencies

- F1 (units, tokens, declarations, file enumeration).

## Stories (implementation order)

1. **01_Story_ExemptionsAndMechanicalDrops**: steps 0–5 and 7–9; `scan` shows dispositions and reasons.
2. **02_Story_RepoIndexAndCodedLineValidator**: step 6; the reusable validator; `scan` shows existing coded-line
   verdicts with violation classes.
3. **03_Story_ExportStatusAndJudgmentDedupe**: the 14 export deciders and dedupe; `scan` shows `exported` and the
   distinct-judgment count.

## Integration Points

- F3 consumes the `JudgeQueue` (distinct `JudgmentKey`s with a representative unit).
- F4 reuses `CodedLineValidator` and `RepoIndex`.
- F5 reports deterministic dispositions alongside judged ones.
