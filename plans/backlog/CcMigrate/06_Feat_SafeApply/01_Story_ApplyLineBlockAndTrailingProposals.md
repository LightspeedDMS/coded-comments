# Story 01: Apply Line, Block and Trailing Proposals

## User Story

**As a** developer who reviewed a dry run
**I want** `cc-migrate migrate <path> --apply` to rewrite my files from the proposals, only in a clean git tree, only
changing comment bytes, and reverting any file that fails verification
**So that** I get the migration without any risk to the code, and every change is reviewable as a git diff

**What the user can do after this story:** run `--apply` after a complete dry run. Line-comment runs, block comments,
trailing comments and doc comments are dropped or replaced by coded lines in all 14 hosts; prose split off a pragma is
removed from the pragma line (the pragma bytes stay) and, for a REWRITE, its coded lines go above the governed
statement. Each file is verified for
code identity; failures are restored and reported. An apply report lists applied, reverted and skipped files with
reasons. `git diff` shows only comment changes.

## Scope

- **Preconditions** (each failure exits 2 with a specific message, nothing written):
  `manifest.complete == true`; `git rev-parse --is-inside-work-tree`; `git status --porcelain` is empty, untracked
  files included; the run directory belongs to this repo (`manifest.repo_root`). There is no branch mode: the tool
  never creates or switches branches and never commits (user decision).
- **Per-file guard:** the current `sha256` equals `manifest.files[path]`, else skip `changed_since_dry_run`.
- **Editor (byte-exact, works on the UTF-8 bytes, preserves BOM and newline style):**

| proposal | edit |
|---|---|
| KEEP | none |
| DROP full-line unit (line_run, block or doc_comment alone on its lines) | delete the unit's whole lines including their line terminators |
| DROP trailing | delete the comment bytes and the horizontal whitespace before them on that line |
| DROP block sharing a line with code | delete the comment bytes; if code is on both sides and neither neighbor byte is whitespace, insert one space; if the line becomes whitespace-only, delete the line |
| REWRITE `in_place` | replace the unit's whole lines with the composed lines, each prefixed with the unit's indent and terminated with the file's newline style |
| REWRITE `trailing` | replace the comment bytes with the single composed line (keeping the original whitespace gap before it) |
| DROP `pragma_prose` | delete the unit's span (separator and prose); the pragma bytes before it and any closing delimiter (`*/`, `}`) after it stay byte-identical |
| REWRITE `pragma_prose` (`above_target`) | delete the span as for DROP, and insert the composed lines above `target_start_line` (above any full-line pragma lines directly over the governed statement), each prefixed with the target's indent and terminated with the file's newline style |
| KEEP with warning `FREE pragma_boundary_unknown` | none (the comment stays unchanged) |
| docstring units or CAP | not in this story: the whole file is skipped `unsupported_kind` |

  Edits are applied from the end of the file to the start, so spans stay valid. Overlapping spans are an invariant
  violation: the file is skipped `overlapping_edits` and the report flags it as a bug.
- **Verification:** `IdentityVerifier` as specified in `Feat_SafeApply.md`, plus `significant` token equality,
  Python AST equality (docstrings untouched in this story), grammar validity of every inserted line, and no
  `Token.Error`. Editing a pragma line to remove its trailing prose changes only comment bytes, so the identity check
  applies unchanged.
- **Write and revert:** new bytes are verified **before** writing. A file that fails verification is never written.
  Writes are atomic (temp file in the same directory + `fsync` + `os.replace`) and preserve the file mode. If a write
  fails mid-way, the original bytes held in memory are restored with the same atomic procedure, and the report shows
  `reverted: <reason>`. No `git checkout`, `git restore`, `git stash` or `git reset` is ever used.
- **Apply report:** `apply_report.md` / `apply_summary.json` in the run directory: applied, reverted (reason),
  skipped (reason), and comment tokens before/after on disk measured from the written files.
- An applied run is marked `applied_at` in the manifest; a second `--apply` of the same run exits 2
  `run already applied`.

## Algorithm

```
apply(run_dir, repo):
  m = load manifest; IF NOT m.complete: EXIT 2 "dry run incomplete; re-run migrate"
  IF m.applied_at: EXIT 2 "run already applied"
  GitGuard.require_clean(repo)                                # EXIT 2 with the offending porcelain lines
  results = []
  FOR path, proposals IN group_by_path(load proposals.jsonl) (bounded by len(m.files)):
    IF any p.kind == docstring OR p.disposition == CAP (not yet supported): results.skip(path, "unsupported_kind"); CONTINUE
    original = read bytes(path)
    IF sha256(original) != m.files[path]: results.skip(path, "changed_since_dry_run"); CONTINUE
    edits = sorted(Editor.plan(original, proposals), by start_byte DESC)
    IF overlaps(edits): results.skip(path, "overlapping_edits"); CONTINUE
    new = original
    FOR e IN edits: new = e.apply(new)                       # bounded by len(edits)
    v = IdentityVerifier.verify(original, new, host, edits)
    IF NOT v.ok: results.revert(path, v.reason); CONTINUE   # never written
    TRY atomic_write(path, new, mode=stat(path).mode)
    ON error: atomic_write(path, original); results.revert(path, "write_failed: " + error); CONTINUE
    results.applied(path, tokens_before(original), tokens_after(new))
  m.applied_at = now; save manifest atomically
  write apply report
  EXIT 0 if no reverts, else EXIT 5 ("applied with reverts; see report")
```

## Acceptance Criteria

```gherkin
Feature: apply line, block and trailing proposals

  Scenario: Refuse a dirty tree
    Given a completed dry run and an untracked file in the repo
    When I run "cc-migrate migrate <repo> --apply"
    Then the exit code is 2 and stderr lists the untracked file
    And no file is modified

  Scenario: Refuse an incomplete dry run
    Given a run whose manifest has complete false
    When I run --apply
    Then the exit code is 2 with "dry run incomplete"

  Scenario: Drops and rewrites across hosts
    Given a clean scratch repo with go, typescript, sql (postgresql) and pascal files containing DROP and REWRITE proposals
    When I run --apply
    Then each DROP unit's lines are gone and each REWRITE unit is replaced by its coded lines at the same indentation
    And "git diff" shows changes only on comment lines
    And the apply report lists every file as applied

  Scenario: Trailing comments stay trailing
    Given "MAX_BATCH = 500  # vendor caps batches at 500" with a REWRITE line "#^ ext vendor batch API<=500 items"
    When I apply
    Then the line becomes "MAX_BATCH = 500  #^ ext vendor batch API<=500 items"

  Scenario: Prose after a pragma is removed and the pragma bytes stay
    Given "x = compute()  # noqa: E501 vendor URL cannot wrap" whose prose unit has a DROP proposal
    When I apply
    Then the line becomes "x = compute()  # noqa: E501"
    And verification passes

  Scenario: Rewritten pragma prose goes above the governed statement
    Given "// eslint-disable-next-line no-console -- CI log scraper reads stdout" directly above "console.log(x);"
    And the prose unit has a REWRITE proposal with the line "//^ ext CI log scraper=>reads stdout"
    When I apply
    Then the pragma line reads "// eslint-disable-next-line no-console"
    And "//^ ext CI log scraper=>reads stdout" is on the line directly above the pragma line, at the statement's indentation
    And the pragma line stays directly above "console.log(x);"
    And verification passes

  Scenario: Inline block comments do not glue tokens
    Given the C code "int a/* note */=1;" with the block dropped
    When I apply
    Then the line reads "int a =1;" and the token stream is unchanged

  Scenario: Verification failure leaves the file untouched
    Given a proposal set crafted so that an edit would remove a non-comment token
    When I apply
    Then the file's bytes are identical to before
    And the apply report shows "reverted" with reason "token_stream_changed"
    And the exit code is 5

  Scenario: Files changed after the dry run are skipped
    Given a file edited and committed after the dry run
    When I apply
    Then that file is skipped "changed_since_dry_run" and others are applied

  Scenario: CRLF and BOM are preserved
    Given a CRLF file with a UTF-8 BOM
    When I apply
    Then the result still uses CRLF and keeps the BOM

  Scenario: A run applies once
    Given an applied run
    When I run --apply again
    Then the exit code is 2 with "run already applied"
```

## Implementation Status

- [ ] `GitGuard` (work tree, clean porcelain, repo match)
- [ ] Per-file hash guard
- [ ] `Editor` plans and byte edits for every row of the table (BOM, newline style, indentation), including `pragma_prose`
- [ ] `IdentityVerifier` (significant tokens, Python AST, inserted-line grammar, no error tokens)
- [ ] Atomic write with mode preservation; in-memory restore on write failure
- [ ] Apply report and manifest `applied_at`
- [ ] Unit tests per edit kind per host (real lexers, real files)
- [ ] Integration tests in real temp git repos (dirty-tree refusal, revert, hash skip)
- [ ] E2E manual testing completed by Claude Code

**Completion:** 0/9 tasks complete (0%)

## Testing Requirements

- For every host fixture: apply a synthetic proposals file that drops every non-exempt unit, then assert verification
  passes and that re-scanning finds only KEEP units.
- Mutation test: inject an edit that deletes one code token; verification must fail for every host.
- No mocks of git or the file system; temp repos via `git init` in pytest `tmp_path`.

## Manual E2E Test Plan (Claude Code)

1. In a scratch multi-host repo, run `migrate` (real dry run), then `--apply`; inspect `git diff` file by file.
2. Make the tree dirty and confirm the refusal; clean it, apply, and confirm success.
3. Build the scratch project where a compiler is available (`python -m py_compile`, `go build`, `tsc --noEmit` when
   installed) to confirm the edits compile.

## Definition of Done

- Scenarios automated and passing; coverage > 85%; zero warnings; manual evidence (diffs, reports) recorded.
