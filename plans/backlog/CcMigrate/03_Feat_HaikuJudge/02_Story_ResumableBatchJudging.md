# Story 02: Resumable Batch Judging

## User Story

**As a** developer running a migration on a real codebase
**I want** `cc-migrate migrate <path>` to judge every distinct comment with one Haiku call each, through the Message
Batches API with prompt caching, and to resume after an interruption without paying again
**So that** the migration costs as little as possible, never loses paid work, and fails clearly when it cannot finish

**What the user can do after this story:** run `cc-migrate migrate <path>` (dry run). It submits batches, waits with
bounded polling, collects results, and writes
`<work-dir>/<run-id>/judgments.jsonl` (one record per `JudgmentKey`: parsed judgment or `malformed` with cause, plus
`usage`). It prints a judging summary: judged, malformed by cause, resubmitted, incomplete. Re-running the same
command resumes the same run.

## Scope

- **Credential gate:** `ANTHROPIC_API_KEY` must be set and non-empty, or the command exits 2 with
  `ANTHROPIC_API_KEY is not set; cc-migrate uses the Anthropic API only (use --estimate for an offline estimate)`.
  No other backend and no fallback.
- **Warm-up (Decision D3):** the first pending key is sent with `client.messages.create` at standard price, with the
  identical prefix, so the cache entry exists before the batch. Its judgment and `usage` are recorded with
  `channel=warmup`.
- **Batches:** `client.messages.batches.create(requests=[{custom_id, params}])`, chunked to at most
  `batch_max_requests` and `batch_max_bytes` per batch. `custom_id` = first 32 hex characters of the `JudgmentKey`.
  Results are keyed by `custom_id`, never by position (they arrive in any order).
- **Polling (anti-unbounded-loop):** `poll_interval_s` (default 60) and `max_wait_s` (default 90000, which is 25
  hours, more than the 24-hour batch maximum). `max_polls = ceil(max_wait_s / poll_interval_s)`. Reaching the bound
  exits 3 ("still processing; re-run to resume") with the state saved.
- **Result handling per `result.type`:**
  - `succeeded`: parse; `malformed` when `stop_reason != "end_turn"` (covers `max_tokens` and `refusal`), when there is
    no text block, when the JSON is invalid, or when the schema does not validate. Malformed keys are final: their
    units become DROP in F4 and are counted by cause (principle 3: no repair call).
  - `errored` with an `invalid_request_error`: abort the run with exit 4 and the error body (a tool bug; never
    retried).
  - `errored` with another error type, or `expired`: eligible for resubmission in the next round, at most
    `max_resubmits` rounds (default 2). After that, the key is `unjudged` and the run is **incomplete** (Decision D11).
  - `canceled`: same as expired (only when the user canceled a batch out of band).
- **RunState** (`state.json`, written atomically with temp file + `fsync` + `os.replace` after every transition):
  `run_id`, `created_at`, keys with status `pending|submitted|judged|malformed|unjudged`, batch ids with status and
  their member keys, resubmit round per key, warm-up record, and the **stored estimate**
  `estimate = {input_tokens, output_tokens_low, output_tokens_high, cost_best_usd, cost_worst_usd, computed_at}`,
  computed once by the Story 01 `CostEstimator` for this run's queue when the state is created (before the warm-up).
  `input_tokens = N × P + sum(U)` (every input token the requests carry, cache-agnostic), so F5 can compare it with
  the actual `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`. Judgments are appended to
  `judgments.jsonl` as they arrive (deduplicated by key on load).
- **Resume:** loading the state skips `judged` and `malformed` keys. Batches that have not ended are polled again,
  never resubmitted. Batches that ended but whose results were not fully read are re-read (results are retained for
  29 days). Only keys in no live batch are submitted. Re-running `migrate` with the same inputs is the only resume
  mechanism.
- **Incomplete run (Decision D11):** when keys remain unjudged after `max_resubmits` rounds, `judge` returns the state
  marked incomplete instead of exiting; `migrate` then has F4 write `manifest.json` with `complete:false` (no
  `proposals.jsonl`) and F5 render `report.md`/`summary.json`, and exits 3. A run stopped at the polling bound is still
  waiting, not incomplete: it saves the state and exits 3 with no manifest.
- Exit codes: 0 complete; 2 configuration error; 3 waiting or incomplete; 4 API contract error.

## Algorithm

```
judge(run, queue, settings):
  require_api_key()                                         # exit 2 if missing
  state = RunState.load_or_create(work_dir / run.run_id, keys=queue.keys())
  IF state.estimate is NONE:
    state.estimate = CostEstimator.estimate(queue, settings).stored_fields()            # Story 01; atomic write
  client = anthropic.Anthropic()                            # SDK default retries (2) for 429/5xx on single calls
  IF state.warmup is NONE AND state.pending_keys():
    k = first pending key
    resp = client.messages.create(**RequestBuilder.params(queue[k]))
    state.record(k, parse(resp), usage=resp.usage, channel="warmup")       # atomic write

  FOR round IN range(settings.max_resubmits + 1):           # bounded rounds
    collect_live_batches(state, client, settings)           # polls batches not yet ended
    todo = state.keys_needing_submission()                   # pending + resubmittable
    IF todo is empty: BREAK
    FOR chunk IN chunk_by_count_and_bytes(todo, settings):
      batch = client.messages.batches.create(requests=[{custom_id: k[:32], params: RequestBuilder.params(queue[k])} for k in chunk])
      state.add_batch(batch.id, chunk)                       # atomic write BEFORE polling
    collect_live_batches(state, client, settings)
  IF state.keys_needing_submission():
    mark them unjudged; state.save(); PRINT incomplete summary
    RETURN state (incomplete)                               # migrate: F4 manifest complete:false, F5 report, EXIT 3
  write judging summary; RETURN state

collect_live_batches(state, client, s):
  FOR batch_id IN state.live_batches():
    FOR poll IN range(ceil(s.max_wait_s / s.poll_interval_s)):
      b = client.messages.batches.retrieve(batch_id)
      IF b.processing_status == "ended": BREAK
      sleep(s.poll_interval_s)
    ELSE: state.save(); PRINT "batch <id> still processing"; EXIT 3
    FOR r IN client.messages.batches.results(batch_id):       # finite stream
      k = state.key_for(r.custom_id)
      MATCH r.result.type:
        "succeeded" -> state.record(k, parse(r.result.message), usage=r.result.message.usage, channel="batch")
        "errored"   -> IF r.result.error.type == "invalid_request_error": state.save(); EXIT 4 with details
                       ELSE state.mark_resubmittable(k, cause=r.result.error.type)
        "expired" | "canceled" -> state.mark_resubmittable(k, cause=r.result.type)
    state.mark_batch_read(batch_id)

parse(message):
  IF message.stop_reason != "end_turn": RETURN Malformed(cause=message.stop_reason)
  text = first content block with type == "text"            # thinking blocks may precede it
  IF text is NONE: RETURN Malformed("no_text")
  data = json.loads(text) ON error: RETURN Malformed("invalid_json")
  IF NOT jsonschema_valid(data, JUDGMENT_SCHEMA): RETURN Malformed("schema")
  RETURN Judgment(data)
```

## Acceptance Criteria

```gherkin
Feature: resumable batch judging

  Scenario: Missing API key fails loudly
    Given ANTHROPIC_API_KEY is unset
    When I run "cc-migrate migrate <repo>"
    Then the exit code is 2
    And stderr says "ANTHROPIC_API_KEY is not set"
    And no network connection is attempted

  Scenario: A small real run completes
    Given a scratch git repo with 12 distinct judgeable comments in python and typescript
    And a valid ANTHROPIC_API_KEY
    When I run "cc-migrate migrate <repo>"
    Then judgments.jsonl has one record per distinct key
    And exactly one record has channel "warmup" and the rest channel "batch"
    And the summary shows judged + malformed = 12 and incomplete = 0
    And the exit code is 0

  Scenario: Interrupted runs resume without paying twice
    Given a run whose batch was submitted and whose process was then stopped (polling bound reached or process killed) before the results were read
    When I run "cc-migrate migrate <repo>" again with the same inputs
    Then no new batch is created for keys already submitted
    And the existing batch is polled and read
    And total request count in the state equals the number of distinct keys plus resubmissions

  Scenario: Malformed responses are dropped and counted
    Given a recorded real response whose stop_reason is "max_tokens"
    And a recorded real response whose text is not valid JSON for the schema
    When the result parser processes them
    Then both keys are recorded as malformed with causes "max_tokens" and "schema"
    And the judging summary counts malformed by cause

  Scenario: Invalid requests abort
    Given a batch result of type errored with error type "invalid_request_error"
    When results are collected
    Then the run stops with exit code 4 and prints the error body
    And the state file is saved

  Scenario: Polling is bounded
    Given poll_interval_s 1 and max_wait_s 3 and a batch that is still processing
    When I run migrate
    Then the command exits 3 after at most 3 polls with "still processing; re-run to resume"

  Scenario: Incomplete runs are explicit
    Given keys that remain errored after max_resubmits rounds
    When the run finishes
    Then those keys are listed as unjudged
    And manifest.json has complete false and no proposals.jsonl exists
    And report.md and summary.json are written for the run
    And the exit code is 3

  Scenario: The estimate is stored with the run
    Given a new run
    When I run "cc-migrate migrate <repo>"
    Then state.json contains estimate.input_tokens, output_tokens_low, output_tokens_high, cost_best_usd and cost_worst_usd
    And they equal the figures "--estimate" prints for the same inputs
```

## Implementation Status

- [ ] Credential gate with message from `help/` content
- [ ] Warm-up request and recording
- [ ] Batch chunking by count and bytes; `custom_id` mapping
- [ ] Bounded polling and result streaming; result-type handling
- [ ] Result parser with malformed causes and schema validation
- [ ] `RunState` atomic persistence (including the stored estimate) and resume semantics
- [ ] Incomplete-run hand-off to F4 (`complete:false` manifest) and F5 (report), exit 3
- [ ] Judging summary and exit codes
- [ ] Unit tests for the parser and state (recorded real responses as fixtures, real file system)
- [ ] Integration test against the real API on a tiny repo (marked `real_api`, opt-in by env var)
- [ ] E2E manual testing completed by Claude Code

**Completion:** 0/11 tasks complete (0%)

## Testing Requirements

- Follows the epic's **Testing Rules** section. Recorded real responses (captured from the integration test, stored
  in `tests/fixtures/recorded_judgments/`) drive only the result-parser unit tests, which are validator tests (the
  response checks of Decision D4). `RunState` tests use the real file system; resume is proven by the real-API
  integration test.
- The batch client is never mocked in integration tests; they make real calls and cost cents. They run only when
  `CC_MIGRATE_REAL_API=1` and a key are present, and otherwise report skipped (visible, not silent).
- State atomicity: a test kills the process between two state writes (real subprocess + SIGKILL) and verifies the
  state file parses and resume works.

## Manual E2E Test Plan (Claude Code)

1. On a scratch repo with about 15 comments, run `migrate` and inspect `judgments.jsonl` and `state.json`.
2. Run again: confirm "nothing to submit" and identical judgments.
3. Start a run, kill it after the batch is submitted (batch id in `state.json`), re-run the same command, and confirm
   it resumes the same batch id.
4. Unset the key and confirm exit 2 and the message.

## Definition of Done

- Scenarios automated and passing; coverage > 85%; zero warnings; real-API evidence (batch ids, usage) recorded.
