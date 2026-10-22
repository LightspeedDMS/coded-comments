# Story 01: Validated Proposals with Budget Trim

## User Story

**As a** developer reviewing a dry run before touching code
**I want** every Haiku result turned into a validated proposal (lines composed, grammar- and budget-checked, anchors
resolved against the repo, CAP text capped, each file held to its coded-line budget), with every dropped line
explained
**So that** what gets applied later is guaranteed to be valid coded-comments syntax with resolvable anchors, and I can
audit every decision in one file

**What the user can do after this story:** after `cc-migrate migrate <path>` completes, open
`<work-dir>/<run-id>/proposals.jsonl` and `manifest.json`: one proposal per unit with disposition, source, reason,
composed lines, dropped lines with violation classes, CAP text and placement. The command prints a validation
summary: lines returned, lines kept, lines dropped by class (`SYNTAX`, `PROSE`, `STALE`, `PROVENANCE`, `BUDGET`,
`SCOPE`, `DOCCAP`, `TRAILING_SINGLE`), REWRITEs demoted to DROP, CAPs demoted. For an incomplete run it writes only
`manifest.json` with `complete:false` and the unjudged keys, and no `proposals.jsonl`.

## Scope

- **Composition:** `line = indent + host.marker + tag + " " + body` (the host marker from yaml already ends with a
  space, e.g. `'#^ '`). Haiku's `body` is trimmed. Bodies containing a newline are invalid (`SYNTAX`).
- **Validation:** `CodedLineValidator` from F2 with `origin = "new"`. In addition:
  - **Provenance (`PROVENANCE`, Decision D6):** every path/symbol/quoted anchor must occur literally in the
    occurrence's comment text or equal the occurrence's declaration name (with `anchor_provenance = "comment"`, the
    comment text only). `#n` and `doc:` anchors must occur literally in the comment text (`doc:` checks the text after
    the prefix).
  - **Basename expansion:** a path anchor that is not a repo path but equals the basename of exactly one repo path is
    rewritten to the repo-relative path; zero or several matches → `STALE`. The line is then re-checked for budgets.
  - **Duplicates:** an identical composed line repeated within one proposal is kept once.
- **Decision consistency** (validator, not Haiku): DROP → lines and cap_text ignored. REWRITE → needs at least one
  valid line, else DROP (`reason = all_lines_invalid`). CAP when `exported == false` → treated as REWRITE with its
  lines (cap_text discarded, `dropped_lines` gets `DOCCAP not_exported`). CAP with invalid cap_text → REWRITE when
  valid lines remain, else DROP.
- **Per-occurrence evaluation:** a judgment is applied to every occurrence of its `JudgmentKey`, and provenance and
  scope are evaluated per occurrence (Decision D5).
- **Placement:**

| unit kind | REWRITE / CAP-lines placement | rule |
|---|---|---|
| line_run, block, doc_comment above a target | `in_place`, unit indent | the original already sits above its target (S3) |
| line_run or block with `declaration.kind == none` | `in_place` only when it is in the file's leading comment area (file-wide facts, how.md); otherwise lines dropped with `SCOPE` | no governed target |
| trailing | `trailing` with the single highest-priority valid line; other lines dropped `TRAILING_SINGLE` | inserting a run above a continuation line can break code |
| `pragma_prose` (prose split off a pragma, Decision D7) | `above_target` at the first line of the governed statement (the statement on the pragma's line for a trailing pragma, the next statement for a full-line pragma), statement indent; when full-line pragma comments sit directly above that statement, the lines go above them so each pragma stays adjacent to the statement it governs | user decision: a REWRITE is placed as a coded line above the governed statement; the pragma bytes stay in place |
| docstring (def/class) | `above_target` at `target_start_line` (first decorator), owner indent | how.md: run directly above the declaration |
| docstring (module) | `in_place` at the docstring position | file-wide facts at the top after license/shebang |
| CAP text | `in_place` doc replacement in the same doc form | F6 Story 2 renders it |

- **Budgets (deterministic trim):** within a run of coded lines that govern one target, at most
  `run_lines` lines are kept. Per file with `code_lines >= min_code_lines`, at most
  `floor(coded_per_code * code_lines)` coded lines are kept. Lines are removed in this **drop order**: (1) tag
  priority, lowest first, `see < todo < perf < why < external < order < coupled < invariant < hazard < security` (rationale: `see` asserts no
  constraint and `todo` is tracked elsewhere, while `security`/`hazard` prevent the costliest mistakes); (2) more o200k tokens
  first; (3) later file position first. Removed lines get `BUDGET run_lines` or `BUDGET coded_per_code`. A REWRITE
  left with no lines becomes DROP. The priority list is in `defaults.toml` (`budget_drop_order`).

## Algorithm

```
build_proposals(units, judgments, state, index, core, settings):
  IF state.unjudged_keys():                                 # incomplete run (Decision D11)
    ProposalStore.write_manifest(complete=false, incomplete_keys=[(k, cause, occurrence unit_ids) for k in state.unjudged_keys()])
    RETURN INCOMPLETE                                       # no proposals.jsonl; F5 still renders the report; migrate exits 3
  proposals = []
  FOR u IN units (sorted by path, start_byte):
    IF u.disposition in (KEEP, DROP): proposals.append(Proposal.deterministic(u)); CONTINUE   # carries u.warning
    j = judgments[JudgmentKey(u)]
    ASSERT j is not NONE                                    # complete run: every JUDGE key has a judgment
    IF j.malformed: proposals.append(Proposal.drop(u, source=judge, reason="malformed:" + j.cause)); CONTINUE
    p = Proposal(u, judge_decision=j.decision, reason=j.reason)
    IF j.decision == DROP: p.disposition = DROP; proposals.append(p); CONTINUE
    kept = []
    FOR (tag, body) IN j.lines[:3]:                         # any 4th line is dropped as BUDGET run_lines
      line = compose(u.host, tag, body)
      line = expand_basenames(line, index)                  # unique basename -> repo path
      v = validate_line(line, u.host, ctx(u, origin="new"), index, core)
      IF v is valid: v = check_provenance(line, u, settings.anchor_provenance)
      IF v is valid AND line not in kept: kept.append(line) ELSE p.dropped_lines.append(v or DUP)
    cap_ok = j.decision == CAP AND u.exported AND validate_cap(j.cap_text, u, core) is valid
    p.disposition, p.lines, p.cap_text = consistency(j.decision, kept, cap_ok, j.cap_text)
    p.placement = place(u, p)                               # table above; may drop lines (SCOPE, TRAILING_SINGLE)
    IF p.disposition == REWRITE AND NOT p.lines: p.disposition = DROP; p.reason = "all_lines_invalid"
    proposals.append(p)
  FOR file IN group_by_path(proposals): trim_budgets(file, core, settings)
  ProposalStore.write(proposals, manifest(complete=true))   # reached only for a complete run

validate_cap(text, u, core):
  lines = text.split("\n"); ASSERT len(lines) bounded by 1 + params(u.declaration.signature_line) + 2
  IF lines[0].strip() == "" OR len(any line) > core.budgets.line_chars: RETURN DOCCAP
  IF any line contains a host marker, "```", ">>>", a "#<digits>" issue id, or starts with "Example": RETURN DOCCAP
  FOR L IN lines[1:]: IF NOT matches  ^[A-Za-z_][\w.*\-]*\s*:\s+\S  : RETURN DOCCAP          # name: note
  IF content_words(lines[0]) ⊆ split_identifier(u.declaration.name) ∪ STOPWORDS: RETURN DOCCAP  # only repeats the name
  RETURN valid

params(signature_line):
  text between the first "(" and its matching ")" (bounded scan), split on top-level commas,
  minus self/cls/this; RETURN count

trim_budgets(file_proposals, core, s):
  FOR each governed target T: coded = lines of REWRITE/CAP proposals governing T   # existing coded lines were judged too
    WHILE len(coded) > core.budgets.run_lines (bounded by len(coded)): remove first in drop order; mark BUDGET run_lines
  IF file.code_lines >= core.budgets.min_code_lines:
    allowed = floor(core.budgets.coded_per_code * file.code_lines)
    all_lines = every coded line that will exist in the file after apply
    WHILE len(all_lines) > allowed (bounded by len(all_lines)): remove first in drop order; mark BUDGET coded_per_code
  demote proposals left without lines (REWRITE -> DROP, reason "budget")
  record file.budget_status = {code_lines, coded_lines_after, ratio, limit, trimmed_count, enforced: bool}
```

Existing coded lines that passed the F2 checks were judged by Haiku (user decision), so they arrive here as REWRITE
lines like any other and take part in the same drop order. When the budget removes the last line of a proposal, it
becomes DROP with `source=budget`, which follows how.md ("Over a limit: delete the weakest line").

## Acceptance Criteria

```gherkin
Feature: validated proposals

  Scenario: Valid lines are composed with the host marker
    Given a python unit whose judgment is REWRITE with lines [{tag: "order", body: "ensure_key_salt before manager init; failure => abort startup"}]
    And "ensure_key_salt" is named in the comment text and declared in the repo
    When proposals are built
    Then the proposal has disposition REWRITE and lines ["#^ order ensure_key_salt before manager init; failure => abort startup"] with the unit's indent

  Scenario: Invented anchors are dropped
    Given "src/db/schema.py" exists and declares "Schema"
    And a judgment line "coupled schema with src/db/schema.py:Schema" where the comment text never mentions schema.py or Schema
    When proposals are built
    Then the line is in dropped_lines with class PROVENANCE
    And if no other line is valid the disposition is DROP with reason "all_lines_invalid"

  Scenario: Unique basenames are expanded
    Given the comment mentions "refresh_token_backend.py" and the repo has exactly one file with that basename at "src/storage/refresh_token_backend.py"
    When proposals are built
    Then the composed line contains "src/storage/refresh_token_backend.py"

  Scenario: Ambiguous basenames are stale
    Given two repo files named "utils.py" and a line anchored on "utils.py"
    Then the line is dropped with class STALE

  Scenario: CAP only on exported declarations
    Given a CAP judgment for a docstring with exported false
    When proposals are built
    Then the disposition is REWRITE if valid lines exist, else DROP
    And dropped_lines notes "DOCCAP not_exported"

  Scenario: CAP text that only repeats the name is rejected
    Given an exported function "get_user" and a CAP judgment with cap_text "Get the user."
    When proposals are built
    Then the CAP is rejected with DOCCAP

  Scenario: Trailing comments keep one line
    Given a trailing unit whose judgment returns valid "external" and "why" lines
    Then the proposal keeps the "external" line as trailing and drops "why" with TRAILING_SINGLE

  Scenario: Budget trimming is deterministic
    Given a file with 60 code lines (limit floor(0.10*60)=6) and 9 valid coded lines across tags security, hazard, invariant, see, see, todo, why, perf, coupled
    When proposals are built
    Then the two see lines and the todo line are dropped with "BUDGET coded_per_code"
    And running the build twice yields byte-identical proposals.jsonl

  Scenario: Malformed judgments drop their units
    Given a judgment recorded as malformed "max_tokens"
    Then every occurrence's proposal is DROP with reason "malformed:max_tokens"

  Scenario: Every kept line is grammar-valid
    Given any completed dry run
    Then every line in every proposal's "lines" fully matches the core.yaml coded regex for its host

  Scenario: Incomplete runs write no proposals
    Given a run in which 3 keys remain unjudged after max_resubmits rounds
    When proposals are built
    Then manifest.json has complete false and lists the 3 keys with their unit_ids
    And no proposals.jsonl exists for that run

  Scenario: Prose split off a pragma is placed above the governed statement
    Given "// eslint-disable-next-line no-console -- CI log scraper reads stdout" directly above "console.log(x);"
    And the prose unit's judgment is REWRITE with a valid line
    When proposals are built
    Then the proposal has placement above_target with the composed line going above the pragma line
    And the pragma unit is KEEP "pragma" with no lines

  Scenario: Existing coded lines are trimmed like new ones
    Given an existing valid coded line that Haiku returned as REWRITE identical to the original
    When proposals are built
    Then its line takes part in the run_lines and coded_per_code drop order
```

## Implementation Status

- [ ] `LineComposer` and basename expansion
- [ ] Provenance check (`comment+decl` and `comment` modes)
- [ ] Decision consistency and per-occurrence application
- [ ] `CapValidator` with param counting
- [ ] Placement computation per unit kind (incl. SCOPE, TRAILING_SINGLE and `pragma_prose`)
- [ ] `BudgetTrimmer` (run_lines, coded_per_code, drop order from config)
- [ ] `ProposalStore` (`proposals.jsonl`, `manifest.json`, `complete:false` manifest for incomplete runs) and validation summary output
- [ ] Unit tests driven by recorded real judgments
- [ ] Integration test: real dry run on a scratch repo (real API, opt-in) producing proposals
- [ ] E2E manual testing completed by Claude Code

**Completion:** 0/10 tasks complete (0%)

## Testing Requirements

- Recorded real judgments (from F3 integration runs) plus hand-built judgment records for edge cases, used only as
  inputs to this stage (recorded real judgments are allowed by the epic's **Testing Rules** section).
- Determinism test: two builds from the same inputs produce byte-identical outputs.
- Property test over the 14-host fixture repo: every composed line passes `validate_line`, and no new line exceeds
  `line_chars` or `line_tokens`.

## Manual E2E Test Plan (Claude Code)

1. Run a real dry run on a scratch repo seeded with the ten real "before" comments from `docs/evidence.md` (adapted
   to the scratch repo's symbols) plus ten junk comments; inspect `proposals.jsonl` by hand.
2. Confirm every junk comment is DROP and record which valuable ones became REWRITE and with which tags.
3. Grep the proposals for `PROVENANCE` and `STALE` drops and check each against the comment text.

## Definition of Done

- Scenarios automated and passing; coverage > 85%; zero warnings; manual evidence recorded.
