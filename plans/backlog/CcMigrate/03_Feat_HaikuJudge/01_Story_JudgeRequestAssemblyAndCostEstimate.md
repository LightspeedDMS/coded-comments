# Story 01: Judge Request Assembly and Cost Estimate

## User Story

**As a** developer about to spend money on a migration
**I want** `cc-migrate migrate <path> --estimate` to show how many units and distinct texts will be judged, the
input and output tokens, and the dollar cost with the batch discount and caching, without any API call
**So that** I can decide whether to run, and narrow the scope with globs or host flags before I pay

**What the user can do after this story:** run `--estimate` with no API key and no network, and get
units scanned, deterministic KEEP/DROP counts, units to judge, distinct judgments, cached prefix tokens, per-request
unit tokens (total and mean), an output-token range, and a dollar range: a best case (warm cache) and a worst case
(no cache hits, `max_tokens` fully used). Each figure is labeled as a tiktoken `o200k_base` proxy. `--dump-request N`
prints the exact rendered request for the Nth distinct key, so the prompt can be inspected.

## Scope

- `ContentLoader` extended: `prompts/judge.md`, `prompts/unit.md`, and the reference files `what.md`, `how.md`,
  `grammar.md`, `exemptions.md` (list configurable as `judge_reference_files`). A missing file exits 2 and names the
  path.
- `RequestBuilder`: builds the exact `params` dict per the Judge Contract in `Feat_HaikuJudge.md`. It is the same
  builder Story 02 sends, so the estimate and the real run cannot drift.
- `defaults.toml` `[pricing."claude-haiku-5-5"]`: `input_per_mtok = 0.10`, `output_per_mtok = 0.50`,
  `cache_read_mult = 0.1`, `cache_write_5m_mult = 1.25`, `cache_write_1h_mult = 2.0`, `batch_mult = 0.5`,
  `long_prompt_threshold = 100000` (with `input_per_mtok_long = 0.50`, `output_per_mtok_long = 2.50`). Source:
  claude-api reference cached 2026-10-06; re-verify at implementation. A model without a pricing entry makes
  `--estimate` exit 2 ("no pricing for model X"), never a guessed price.
- `[judge]` settings: `model`, `max_tokens`, `effort`, `cache_ttl` (`"1h"` | `"5m"`), `estimate_output_tokens_min`
  (default 80, a JSON answer with no thinking), `batch_max_requests` (100000), `batch_max_bytes` (256 MB minus a
  safety margin of 1 MB).
- A `run_id` is computed here (Decision in Epic: HEAD, file hashes, config, prompt and reference hashes, model), so
  the estimate names the run a later `migrate` will create or resume.

## Algorithm

```
estimate(path, settings):
  inventory  = scan(path, settings)                       # F1 + F2, no network
  queue      = dedupe(inventory.units)
  prefix     = RequestBuilder.system_blocks()             # loads prompt + reference files
  P          = o200k(prefix text)
  ASSERT P >= 512 OR warn "prefix below Haiku 5.5 minimum cacheable length; caching will not apply"
  U          = [o200k(RequestBuilder.user_message(k.representative)) for k in queue]
  N          = len(queue)
  price      = settings.pricing[settings.judge.model]  (missing -> exit 2)
  ASSERT max(P + u for u in U) <= price.long_prompt_threshold   (else use the long-prompt rates for those requests)
  b          = price.batch_mult
  warm       = 1 request at standard price: P*write_mult*in + U[0]*in + out_min*out          # write_mult per cache_ttl
  best_in    = (N-1) * P * price.cache_read_mult + sum(U[1:])                                 # every batch request hits the cache
  worst_in   = (N-1) * P + sum(U[1:])                                                         # no hits
  out_low    = (N-1) * settings.judge.estimate_output_tokens_min
  out_high   = (N-1) * settings.judge.max_tokens
  cost_best  = warm + b * (best_in * in_rate + out_low * out_rate)
  cost_worst = warm + b * (worst_in * in_rate + out_high * out_rate)
  batches    = ceil(N / batch_max_requests) adjusted so each serialized chunk < batch_max_bytes
  PRINT table (all token figures labeled "o200k proxy"; dollars rounded to cents and shown with 4 significant digits when < $0.01)
  EXIT 0                                                  # zero network calls: asserted by a test that runs with networking disabled

dump_request(n):
  print json(RequestBuilder.params(queue[n]))            # exactly what Story 02 will send
```

## Acceptance Criteria

```gherkin
Feature: offline estimate

  Scenario: Estimate without credentials or network
    Given ANTHROPIC_API_KEY is unset
    And networking is disabled for the process (a network namespace via "unshare -n" when available, otherwise an in-process socket guard that makes every network connect raise)
    When I run "cc-migrate migrate <repo> --estimate"
    Then the exit code is 0
    And the output shows units_scanned, keep, drop, units_to_judge, distinct_judgments, prefix_tokens, batches, and a best and worst dollar figure
    And every token figure is labeled "o200k proxy"

  Scenario: Estimate reflects dedupe and scope controls
    Given a repo where 40 copies of the same comment exist
    When I run --estimate
    Then distinct_judgments counts that text once
    When I add exclude ["tests/**"] and re-run --estimate
    Then units_to_judge and the dollar range decrease

  Scenario: The request is inspectable and contains no code bodies
    When I run "cc-migrate migrate <repo> --estimate --dump-request 0"
    Then the printed request has model "claude-haiku-5-5", output_config.format.type "json_schema", output_config.effort "low", thinking type "adaptive"
    And it has no temperature, top_p or top_k field and no assistant message
    And the last system block carries cache_control with the configured ttl
    And the user message contains the signature line but no other line of the source file

  Scenario: Missing prompt or reference files fail loudly
    Given reference_dir lacks grammar.md
    When I run --estimate
    Then the exit code is 2 and stderr names grammar.md

  Scenario: Unknown pricing is not guessed
    Given judge.model is set to a model without a pricing entry
    When I run --estimate
    Then the exit code is 2 and stderr says "no pricing for model"
```

## Implementation Status

- [ ] `prompts/judge.md` and `prompts/unit.md` written to the Judge Contract content requirements
- [ ] `ContentLoader` for prompts and reference files with hashes for `run_id`
- [ ] `RequestBuilder` (system blocks with cache_control, user message, params, schema)
- [ ] Pricing and judge settings in `defaults.toml` with validation
- [ ] `CostEstimator` (best/worst, warm-up, batches, long-prompt guard)
- [ ] `migrate --estimate` and `--dump-request` output
- [ ] Unit tests (real files, real tiktoken)
- [ ] Network-disabled integration test proving zero calls
- [ ] E2E manual testing completed by Claude Code

**Completion:** 0/9 tasks complete (0%)

## Testing Requirements

- Golden test: the rendered request for a fixture unit compared to a checked-in expected JSON (all fields except
  hashed run metadata).
- Property: for every unit in the 14-host fixture repo, the user message contains no source line other than the
  signature line.
- Zero-network proof, always executed: run under `unshare -n` when it is available (and permitted) on the machine;
  otherwise use the unprivileged fallback, a socket guard installed in the test process (`socket.socket.connect`,
  `connect_ex` and `socket.create_connection` replaced by functions that raise) while `estimate` runs in-process. Either
  way the test fails if any network connection is attempted, and the output names which mechanism was used. The test
  is never skipped for lack of `unshare`.
- The figures `estimate` computes are the ones F3 Story 02 stores in `RunState.estimate` for the report's
  estimate-vs-actual comparison.

## Manual E2E Test Plan (Claude Code)

1. With `ANTHROPIC_API_KEY` unset, run `cc-migrate migrate <copy of claude-usage-reporting> --estimate`; record the
   table.
2. `--dump-request 0 | python -m json.tool` and read the request in full: no code body, correct params.
3. Re-run with `--config` excluding `tests/**` and compare the numbers.

## Definition of Done

- Scenarios automated and passing; coverage > 85%; zero warnings; manual evidence recorded.
- No prompt text in `.py` files (anti-inline-prompts verified by review).
