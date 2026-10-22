# Feature 07: End-to-End Acceptance

## Description

Prove the whole tool on real code with real Haiku calls and no API mocks: estimate → dry run → apply → independent
verification, on a **temporary copy** of a real repository (`~/Dev/claude-usage-reporting`: 101 tracked files, 91
Python and 2 shell, measured 2026-10-14). The original repository is never touched. A small calibration set checks
that the judge applies principle 1 (default DROP) on obvious cases and admits obvious hazards.

## Safety rules for this feature

- The source repo is copied with `cp -a` (or `git clone --no-hardlinks`) into a pytest `tmp_path` or the scratchpad.
  Each test asserts the working directory is under the temp root before any write.
- A test that resolves to the original path aborts before doing anything.
- Real-API tests run only with `CC_MIGRATE_REAL_API=1` and a key, and are reported as skipped otherwise (visible).

## Independent verification (not reusing the tool's own verifier)

- `git diff --numstat` / `git diff -U0` of the copy: every removed or added line is a comment, docstring or blank
  line, checked by a **separate** check that lexes each changed hunk's file before and after with the plain Pygments
  API and compares the non-comment token streams. The check lives in the test code, not imported from `cc_migrate`.
- `python -m py_compile` on every changed Python file; the copy's own test suite (`pytest`) passes as it did before
  the migration (baseline captured first).
- Every line in the copy that carries a marker is validated with the regexes read directly from `rules/core.yaml`.
- Report reconciliation: `summary.json` counts equal the counts recomputed from `proposals.jsonl` and from the
  on-disk files after apply (coded lines present, comment tokens on disk with o200k).

## Dependencies

- F1–F6 complete.

## Stories

1. **01_Story_RealRepoAcceptanceRun**: the automated E2E test, the calibration set, the tool README usage section,
   and the documented manual run.

## Integration Points

- Produces the evidence the epic's Definition of Done needs: numbers before and after, real cost, zero identity
  violations.
