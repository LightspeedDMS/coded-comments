# Story 01: Real Repo Acceptance Run

## User Story

**As the** owner of cc-migrate
**I want** an end-to-end acceptance run that migrates a temporary copy of a real repository with real Haiku calls, then
independently verifies code identity, coded-line validity, behavior and report numbers, plus a calibration check of
the judge on real labeled comments
**So that** I have evidence, not claims, that the tool deletes the bloat, keeps only valid coded facts, never changes
code, and costs what the report says

**What the user can do after this story:** run `pytest -m real_api tests/e2e` (with `CC_MIGRATE_REAL_API=1` and a key)
to get the full acceptance verdict with numbers. The tool's `README.md` documents install, the four-step workflow
(`scan`, `--estimate`, dry run, `--apply`) and how to read the report.

## Scope

- **E2E test `tests/e2e/test_real_repo_acceptance.py`:**
  1. Clone: `git clone --no-hardlinks ~/Dev/claude-usage-reporting <tmp>/repo`. The clone gives a clean tree at HEAD
     even if the original has uncommitted work. Assert `<tmp>/repo` resolves under the temp root and differs from the
     source path. The original is never opened for writing.
  2. Baseline: run the copy's own test suite in a fresh venv inside `<tmp>` and record the pass/fail counts.
  3. `cc-migrate scan` → record per-host counts.
  4. `cc-migrate migrate --estimate` with `ANTHROPIC_API_KEY` removed from the environment → must succeed; record the
     best and worst dollar figures.
  5. `cc-migrate migrate` (real Batches API) → must finish complete (exit 0) within the bounded wait.
  6. `cc-migrate migrate --apply` (changes stay uncommitted in the clone's working tree).
  7. Independent verification (`Feat_EndToEndAcceptance.md`): non-comment token identity per changed file (test-owned
     Pygments comparison), `py_compile` of every changed `.py`, the copy's test suite equals the baseline, every
     marker line valid per `rules/core.yaml` regexes, every path anchor exists in the copy, report reconciliation.
  8. Assert the principle-level outcomes: comment tokens after < comment tokens before; every proposal has
     disposition in {KEEP, DROP, REWRITE, CAP} (no UNKNOWN); the actual cost lies within [0, worst estimate].
  9. Idempotence: `cc-migrate scan` on the migrated copy shows that every coded line written by the apply passes the
     deterministic step-6 checks:
     none is `DROP SYNTAX/PROSE/STALE/BUDGET`; all are `JUDGE coded_valid` (valid coded lines are judged by Haiku,
     user decision). The `--estimate` `distinct_judgments` for the migrated copy (coded lines plus CAP docs) is
     recorded, not asserted to be zero.
- **Calibration test `tests/e2e/test_judge_calibration.py`** (real API, one small batch):
  - DROP set: the 32 real comments in `.analysis/redundant_deletion.jsonl`, copied into
    `tests/fixtures/calibration/redundant.jsonl` (the tool never reads `.analysis/` at runtime; epic Testing Rules).
  - Admit set: the 10 real originals in `.analysis/real_compression.jsonl` (`original` field), copied into
    `tests/fixtures/calibration/valuable.jsonl`.
  - Each record is judged through the real `RequestBuilder` and `BatchClient` with host `python` (or the record's
    host), kind `line_run`, exported false.
  - Thresholds (configurable in the test, initial values): DROP set ≥ 31/32 judged DROP; admit set ≥ 8/10 judged
    REWRITE with at least one line that passes grammar and S1 (anchors are not resolved here, because those repos are
    not present). Every miss is printed with its text and judgment, so prompt tuning is evidence-driven.
- **README:** `tool/cc-migrate/README.md` with install (`pip install -e tool/cc-migrate`), prerequisites (git work
  tree, `ANTHROPIC_API_KEY` for dry runs, reference tree installed by `./install.sh`), commands, run-directory layout,
  exit codes, configuration keys, known limits (copied from the epic).

## Algorithm

```
acceptance(src = ~/Dev/claude-usage-reporting):
  tmp = mkdtemp(); repo = tmp / "repo"
  git clone --no-hardlinks src repo
  ASSERT realpath(repo) startswith realpath(tmp) AND realpath(repo) != realpath(src)
  baseline = run_tests(repo)                           # bounded timeout, e.g. 900 s
  scan     = run("cc-migrate scan", repo, json)
  est      = run("cc-migrate migrate --estimate", repo, env without ANTHROPIC_API_KEY)
  dry      = run("cc-migrate migrate", repo)            # bounded by settings max_wait_s; exit 0 required
  head0    = git rev-parse HEAD
  app      = run("cc-migrate migrate --apply", repo)
  FOR f IN git diff --name-only head0 (working tree vs head0; bounded):
     ASSERT significant_tokens(show(head0:f)) == significant_tokens(read(f))     # test-owned lexer comparison
     IF f endswith ".py": ASSERT py_compile(f)
  ASSERT run_tests(repo) == baseline
  FOR line IN every line of every tracked host file containing a marker at line start or after whitespace:
     ASSERT core_regex(host).fullmatch(line.strip())
  ASSERT reconcile(summary.json, proposals.jsonl, files on disk)
  ASSERT dry.tokens_after < dry.tokens_before
  ASSERT 0 <= dry.cost_actual <= est.cost_worst
  RECORD numbers in the test output (units, dispositions, tokens before/after, cost, cache hit share)
```

## Acceptance Criteria

```gherkin
Feature: real repo acceptance

  Scenario: Full workflow on a temporary copy
    Given CC_MIGRATE_REAL_API=1 and a valid ANTHROPIC_API_KEY
    And a clone of ~/Dev/claude-usage-reporting in a temporary directory
    When the acceptance test runs scan, estimate, dry run and apply
    Then every step exits 0
    And the original repository's git status and HEAD are unchanged
    And every changed file has an identical non-comment token stream before and after
    And every changed Python file compiles and the copy's test suite matches the baseline
    And every coded line in the copy fully matches the core.yaml grammar for its host
    And summary.json reconciles with proposals.jsonl and the files on disk
    And comment tokens after are fewer than before
    And the actual cost is at most the worst-case estimate

  Scenario: Estimate is offline
    Given ANTHROPIC_API_KEY is removed from the environment
    When the estimate step runs
    Then it exits 0 and makes no network connection

  Scenario: Judge calibration on real labeled comments
    Given the 32 redundant and 10 valuable real comments from the design-phase corpus
    When they are judged by real Haiku through the tool's request builder
    Then at least 31 of 32 redundant comments are DROP
    And at least 8 of 10 valuable comments are REWRITE with a grammar-valid line
    And every miss is printed with its text and judgment

  Scenario: Real-API tests are visible when disabled
    Given CC_MIGRATE_REAL_API is not set
    When I run pytest
    Then the real-API tests are reported as skipped with the reason, never silently omitted
```

## Implementation Status

- [ ] Calibration fixtures copied from `.analysis/` into `tests/fixtures/calibration/`
- [ ] `test_judge_calibration.py` with thresholds and miss reporting
- [ ] `test_real_repo_acceptance.py` with clone safety assertions
- [ ] Test-owned independent identity checker (Pygments, not importing `cc_migrate`)
- [ ] Baseline and post-apply test-suite comparison
- [ ] Report reconciliation checker
- [ ] `tool/cc-migrate/README.md` complete
- [ ] Real run executed; numbers recorded in this story
- [ ] E2E manual testing completed by Claude Code

**Completion:** 0/9 tasks complete (0%)

## Testing Requirements

- Zero mocks anywhere in this story: real git, real files, real Pygments, real Anthropic API.
- Bounded waits on every subprocess (timeouts set per step) per the anti-unbounded-loop rule.
- Coverage of the whole package stays > 85% (unit and integration suites from earlier stories plus this one).

## Manual E2E Test Plan (Claude Code)

1. Run the same workflow by hand on a fresh clone in the scratchpad: `scan`, `--estimate`, dry run (real Haiku),
   reading `report.md`, `--apply`.
2. Read `git diff` of the clone for at least 10 files and judge whether each kept coded line passes the WHAT gate;
   list any line you would have dropped (evidence for prompt tuning, not a pass/fail gate).
3. Run the copy's test suite and compare with the baseline.
4. Record the before/after numbers, the cost, and the cache-hit share in this story's Implementation Status.

## Definition of Done

- All scenarios pass with real API calls; evidence (numbers, batch ids, cost) recorded; zero warnings; README complete.
- Epic completion status updated to reflect all 12 stories.
