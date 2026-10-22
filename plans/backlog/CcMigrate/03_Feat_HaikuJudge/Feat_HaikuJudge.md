# Feature 03: Haiku Judge

## Description

Judge each distinct comment text (one `JudgmentKey`) with exactly **one** Claude Haiku call that returns both the
verdict and the result (principle 3), using the Message Batches API at 50% price, a cached shared instruction prefix,
and schema-constrained JSON output. Before any call, `migrate --estimate` gives a cost estimate that needs no API key
and makes no network calls. Runs are resumable: an interrupted run never pays twice for the same key.

## The Judge Contract

### Request (per JudgmentKey)

| part | content | cached |
|---|---|---|
| `system[0]` | `prompts/judge.md` (tool-owned instructions, see below) | yes |
| `system[1]` | `what.md`, `how.md`, `grammar.md`, `exemptions.md` from `reference_dir` (default `~/.claude/coded-comments`), each wrapped in a fixed heading; `cache_control: {type: "ephemeral", ttl: <cache_ttl>}` on this last system block | yes (breakpoint) |
| `messages[0]` (user) | `prompts/unit.md` rendered with: `host`, `path`, `kind`, `exported`, `declaration.kind`, `declaration.name`, `declaration.signature_line`, and the comment text (markers stripped, line breaks kept) | no |
| params | `model` (default `claude-haiku-5-5`), `max_tokens` (default 2048), `thinking: {type: "adaptive"}`, `output_config: {effort: <judge_effort, default "low">, format: {type: "json_schema", schema: JUDGMENT_SCHEMA}}`; **no** `temperature`/`top_p`/`top_k` (they return a 400 on Haiku 5.5), **no** assistant prefill | — |

The prefix is byte-identical across all requests and all hosts (Decision D2: no host files in the prefix, because
Haiku never writes markers). The tool never sends code bodies: the only code text in a request is the one-line
`signature_line` (principle 2).

### Response schema (`JUDGMENT_SCHEMA`)

```
object, additionalProperties false, required [decision, lines, cap_text, reason]
  decision : enum [DROP, REWRITE, CAP]
  lines    : array of object {tag: enum [haz, cpl, sec, inv, ext, ord, why, ref, perf, todo], body: string},
             additionalProperties false, required [tag, body]      # body = clauses after the tag, no marker
  cap_text : string                                                # "" unless decision == CAP
  reason   : string                                                # short; shown in the report
```

Cardinality rules the schema may not express are enforced in F4 (`lines` 1–3 for REWRITE, 0–3 for CAP, empty for
DROP; CAP only when `exported` is true).

### `prompts/judge.md` must state (content requirements, written at implementation)

1. Default is DROP. Doubt is DROP. There is no "unknown" answer.
2. Run the WHAT gate in `what.md` from the top. REWRITE only when an admission test matches and you can name in five
   words which mistake the line prevents or which search it saves.
3. Always DROP: narration, restating names or code, history/changelog/ticket stories, business paraphrase, poetry,
   explanations of how hard code works, context-dependent text ("as above", "see below"), and `todo` without an issue
   or `path:symbol=done` target.
4. Output `tag` + `body` only; never write a marker; at most 3 lines; one fact per line; shapes from `how.md`.
5. Anchors: copy only paths, symbols, issue numbers and doc references that appear literally in the comment text, or
   the declaration name given. Never invent a path. Quote names containing `< > = !` with backticks. Do not use words
   containing `/` unless they are real paths named in the comment.
6. CAP only when `exported` is true: `cap_text` = one summary line plus one `name: note` line per param, return or
   raise that the types do not carry. No examples, history, ticket ids, restated name or coded syntax. If the doc only
   repeats the name, DROP. Facts that pass the gate go in `lines`, not in `cap_text`.
7. Return JSON matching the schema and nothing else.

`prompts/unit.md` is a template with named placeholders; rendering escapes nothing beyond JSON-string safety of the
comment text. Both files are package data, loaded by `ContentLoader`; a missing file aborts with a clear error.

## Technical Architecture

```
JudgeQueue --> RequestBuilder --> CostEstimator --(--estimate)--> print estimate, exit 0
                    |
                    v
      require ANTHROPIC_API_KEY (else exit 2, clear message, no fallback)
                    |
                    v
      RunState.load_or_create(run_id) --> keys without a judgment
                    |
                    v
      warm-up: messages.create(first pending key) --> write cache, record judgment
                    |
                    v
      chunk pending keys (<= 100,000 requests and < 256 MB per batch) --> batches.create(custom_id = key[:32])
                    |
                    v
      bounded poll (poll_interval_s, max_wait_s) --> batches.results stream --> ResultParser --> RunState (atomic)
                    |
                    v
      errored(server)/expired --> resubmit (<= max_resubmits) --> else run INCOMPLETE:
                                  F4 writes manifest.json complete:false (no proposals.jsonl), F5 writes the report, exit 3
```

## Dependencies

- F2 (`JudgeQueue`, units, export status). `anthropic` SDK, `tiktoken`.

## Stories (implementation order)

1. **01_Story_JudgeRequestAssemblyAndCostEstimate**: content loading, request rendering, schema, pricing config,
   `cc-migrate migrate <path> --estimate` (zero API calls).
2. **02_Story_ResumableBatchJudging**: API key gate, warm-up, batch submit/poll/results, malformed handling, bounded
   resubmission, resumable `RunState` (with the stored estimate); dry run writes `judgments.jsonl`. Re-running
   `migrate` is the resume mechanism.

## Integration Points

- F4 consumes `judgments.jsonl` (one record per `JudgmentKey`) together with the unit occurrences.
- F5 consumes the per-request `usage` stored in `RunState` for actual cost.
