# Corpus comment rubric and frozen sample

Use `comment_sample.jsonl` for classification. Its source is the current, non-test files in `ratio_files.tsv` and `ratio_files_other.tsv`, themselves traced to Claude-coauthored commits. The source file may have later edits, so this is **Claude-touched file** evidence, not proof that Claude wrote each sampled line. `freeze_comment_sample.py` extracts candidate comment lines and Python docstrings, keeps the SHA256(`pool-v1` + id) top 30 per language/repo stratum in `comment_candidates.jsonl`, then selects eight records per language/prose stratum with seed `coded-comments-2026-10-13-v1`. Candidates are ranked by SHA256(seed + id); repositories are visited in sorted round-robin order. The sample is frozen for steps 10–12. Batch A and B each contain four records per stratum. The check in `checks/check_comment_sample.py` independently reconstructs this draw from the frozen candidate pool.

## Label one primary category

For each record, inspect the cited source path and nearby code before labeling. Record `id`, `primary_category`, `disposition`, and a one-line justification. Use the category that captures the strongest information the comment adds. If a comment mixes a restatement and a real hazard, label the hazard and mention the excess prose. Do not infer a past bug or an external constraint without evidence in the comment or nearby code. For semantic lookups in an indexed repo, use `cidx query ... --quiet`.

| Primary category | Disposition | Test for the label |
|---|---|---|
| `restates_code` | redundant | Repeats a name, expression, type or obvious effect. |
| `narrates_steps` | redundant | Describes the next visible operation or control-flow step. |
| `duplicates_docs` | redundant | Repeats an identifiable nearby document/API contract; cite the duplicate in the justification. |
| `history_changelog` | redundant | Records a change date, author or old behavior better held in version history. |
| `business_paraphrase` | redundant | Restates a business rule already apparent from code/tests, without a constraint or rationale. |
| `invariant` | valuable | States a condition that must remain true and is not enforced or obvious locally. |
| `hazard_guard` | valuable | Names a failure mode or prior bug and the change that would reintroduce it. |
| `rationale_alternative` | valuable | Explains a non-obvious choice or why an apparent alternative fails. |
| `external_constraint` | valuable | Points to an external API, protocol, version or specification quirk. |
| `cross_file_coupling` | valuable | Names another path/symbol that must change or stay synchronized. |
| `ordering_lifecycle` | valuable | States ordering, concurrency, retry, cleanup or lifecycle constraints. |
| `security_boundary` | valuable | States trust, auth, validation or data exposure boundaries. |
| `performance` | valuable | Names a hot path, measured cost or non-obvious complexity guard. |
| `reference` | valuable | Gives a useful issue, specification, path, symbol or anchor pointer without duplicating it. |
| `actionable_todo` | valuable | Specifies a remaining task with a checkable target or issue reference. |
| `public_api_doc` | exempt | Concise prose on an exported/public API for human or IDE consumption. Check visibility; a private docstring is not automatically exempt. |
| `tool_or_header` | exempt | Tool pragma, license/copyright, shebang, encoding line or generated-code marker missed by extraction filters. |
| `unclear` | uncertain | Context is insufficient to justify any category; state what evidence is missing. |

The valuable label means the information deserves preservation, **not** that its current wording is efficient. A useful comment can still need compression into the later coded language. `public_api_doc` is an exemption from the coded-only rule, not proof of unique value. Count dispositions and primary categories separately in step 12.

The line-oriented extractor can cut a multi-line block or docstring and can mistake comment-like syntax inside regex/template constructs. Read source context before deciding. C, C++ and Pascal have no qualifying files in the ratio corpus; SQL dialects are pooled, so this sample cannot justify dialect-specific frequency claims.
