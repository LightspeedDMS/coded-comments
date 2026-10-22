# Story 02: Repo Index and Coded Line Validator

## User Story

**As a** developer whose codebase already contains some coded comments
**I want** every existing `#^` / `//^` / `--^` line validated against the grammar, the budgets and the repository
(anchors resolve), dropping invalid ones with the violation class and sending valid ones to Haiku judgment like any
other comment (user decision: a valid line may come back REWRITE, identical or improved, or DROP)
**So that** stale or malformed coded lines do not survive the migration, valid ones still pass the WHAT gate, and the
same validator can later check every line Haiku writes

**What the user can do after this story:** `cc-migrate scan <path>` reports existing coded lines as `JUDGE coded_valid`
or `DROP <CLASS>` (`SYNTAX`, `PROSE`, `STALE`, `BUDGET`) with a detail (for example
`STALE RefreshTokenBackend._ensure_schema not found`), and the per-host table gains `coded_valid` and
`coded_invalid` columns.

## Scope

- `RepoIndex` built once per run from the F1 enumeration (all tracked and untracked-not-ignored paths, every host
  file's tokens, Python `ast`).
- `CodedLineValidator` driven entirely by `rules/core.yaml` (`markers`, `hosts`, `parts`, `word_class_order`,
  `word_class`, `budgets`), loaded via `ContentLoader`. **No regex or limit is re-typed in code;** a test asserts
  that the composed regex for each host equals the one built from the YAML.
- Classification step 6 for units whose every line starts with the host marker followed by a space. A unit that mixes
  coded and prose lines is split: coded lines are validated here, prose lines go on to steps 7–10.
- Violation classes produced here (subset of `reviewer.md`): `SYNTAX`, `PROSE` (no anchor, no operator and no `before`/`after` word, rule S1),
  `STALE` (anchor does not resolve), `BUDGET` (`line_chars`, `line_tokens`, `run_lines`). A line that fails one of
  them is `DROP <CLASS>` deterministically. Judgment classes (`VACUOUS`, `REDUNDANT`, `UNSUPPORTED`, `DUP`) are not
  decided by code: a coded line that is deterministically valid is `JUDGE` with reason `coded_valid` (user decision).
  Consecutive valid lines of one unit form one `JUDGE` child unit; failing lines are split off as `DROP` child units.
  `coded_valid` units enter the F2 Story 03 dedupe, the F3 estimate and judging, and F4 validation exactly like any
  other `JUDGE` unit (the validator runs again on whatever Haiku returns).

## Algorithm

```
RepoIndex.build(root, enumerated_files, tokens_by_file):
  paths      = set(repo-relative paths of all enumerated files) ∪ set(git ls-files output)   # includes non-host files (md, yaml, json)
  by_base    = map basename -> sorted list of paths
  idents     = map path -> set(Name.* token values)          # every host file lexed in F1
  all_idents = union of idents values
  py_qual    = map path -> set(qualified names "Class.method", "func", "Class") from ast (bounded walk)
  RETURN index

validate_line(line_text, host, unit_context, index, core):
  regex = compile(core.parts.coded with {marker} = core.markers[core.hosts[host]], {tags} = "|".join(core.tags))
  IF NOT regex.fullmatch(line_text.strip()):           RETURN Violation(SYNTAX, "grammar")
  body  = text after "<marker> <tag> "
  IF len(line_text.strip()) > core.budgets.line_chars:  RETURN Violation(BUDGET, "line_chars")
  IF o200k_tokens(line_text.strip()) > core.budgets.line_tokens: RETURN Violation(BUDGET, "line_tokens")
  clauses = re.split("; ?", body)                      # one optional space after ";"
  words   = tokenize each clause into words and operators (longest operator first: => <= >= != < > =)
  anchors = [w for w in words if word_class(w, core) != plain]    # first match in word_class_order
  has_op  = any clause contains an operator
  has_ord = any word in core.order_words                # before, after
  IF NOT anchors AND NOT has_op AND NOT has_ord:        RETURN Violation(PROSE, "S1 no anchor, operator or order word")
  FOR a IN anchors:
    result = resolve(a, index, unit_context)
    IF result is unresolved:                            RETURN Violation(STALE, a)
  RETURN Valid

resolve(word, index, ctx):
  class = word_class(word)
  quoted -> resolve leading identifier of the quoted content as a symbol
  issue  -> valid (well-formed #n; tracker state is not checked, reviewer.md)
  doc    -> valid when the doc: target text is a repo path that exists, or when ctx.origin == "existing"
            (existing human or AI-written doc anchors are not network-verified); F4 adds the provenance rule for new lines
  path   -> p, sym = split on first ":" ; p must be in index.paths
            IF sym: last identifier of sym must be in index.idents[p] (python: full sym in index.py_qual[p])
  symbol -> parts = split on "." or "::" ; strip trailing "()"
            py_heads = set of first components of every qualified name in index.py_qual (classes, module-level defs)
            IF len(parts) > 1 AND parts[0] in py_heads:
                dotted name must equal a qualified name in index.py_qual of some file (exact member check)
            ELSE:
                every part must be in index.all_idents (identifier-level; Epic known limit)

check_runs(file_units):                                   # run_lines budget for existing runs
  FOR each run of consecutive coded lines (S3):
    IF len(run) > core.budgets.run_lines: mark lines beyond the limit (in file order) Violation(BUDGET, "run_lines")
```

## Acceptance Criteria

```gherkin
Feature: existing coded lines

  Scenario: A valid coded line is sent to judgment
    Given a python repo where "src/pkg/store.py" declares class "Store" with method "_flush"
    And a file containing "#^ order Store._flush before close; close drops _buf" above a statement
    When I run "cc-migrate scan <repo> --units"
    Then the unit is JUDGE "coded_valid"
    And it is counted in units_to_judge

  Scenario: The real stale-reference case is caught
    Given a python repo where "_ensure_schema" is declared on "RefreshTokenSqliteBackend" but not on "RefreshTokenBackend"
    And a SQL file (dialect configured) containing "--^ coupled token tables with RefreshTokenBackend._ensure_schema"
    When I scan
    Then the unit is DROP "STALE" with detail "RefreshTokenBackend._ensure_schema"

  Scenario: Grammar failures
    Given "//^ hazard <change> => <failure>; #123"
    When I scan
    Then the unit is DROP "SYNTAX"

  Scenario: Lines with no anchor, operator or order word
    Given "#^ why because it is better"
    When I scan
    Then the unit is DROP "PROSE"

  Scenario: Budget violations
    Given a coded line of 170 characters that is otherwise valid
    And a run of four valid coded lines above one declaration
    When I scan
    Then the long line is DROP "BUDGET line_chars"
    And the fourth line of the run is DROP "BUDGET run_lines"

  Scenario: Paths must exist
    Given "#^ see docs/missing.md; setup notes" and "#^ see docs/setup.md; setup notes" where only docs/setup.md exists
    When I scan
    Then the first is DROP "STALE" and the second is JUDGE "coded_valid"

  Scenario: The validator uses core.yaml as its only source
    Given rules/core.yaml with budgets.line_chars changed to 100 in a copied reference_dir
    When I scan with that reference_dir
    Then a 120-character valid line is DROP "BUDGET line_chars"
```

## Implementation Status

- [ ] `RepoIndex` (paths, basenames, identifiers, Python qualified names)
- [ ] Regex composition from `rules/core.yaml` per host, with an equality test against the YAML
- [ ] Word classification in `word_class_order`, operator tokenizing, S1 check
- [ ] Anchor resolution (quoted, issue, doc, path, path:symbol, symbol)
- [ ] Budgets: `line_chars`, `line_tokens` (tiktoken o200k), `run_lines`
- [ ] Classification step 6 (valid -> `JUDGE coded_valid`, invalid -> `DROP <CLASS>`), with mixed-unit splitting
- [ ] `scan` coded columns and `DROP <CLASS>` details
- [ ] Unit tests including every fenced coded example from `reference/` (all must validate when their anchors exist in a fixture repo)
- [ ] E2E manual testing completed by Claude Code

**Completion:** 0/9 tasks complete (0%)

## Testing Requirements

- Every fenced `coded` example in `reference/how.md`, `reference/examples.md` and `reference/migrate.md` must pass
  `SYNTAX`, `PROSE` and `BUDGET` (the same property `.analysis/grammar_check.py` established). Anchors are checked
  against a fixture repo that declares the named symbols.
- Real temp git repos; no mocked index.

## Manual E2E Test Plan (Claude Code)

1. In a scratch repo, write five coded lines (valid, stale, syntax error, prose, too long), then scan and compare the
   classes (the valid line is `JUDGE coded_valid`, the others `DROP <CLASS>`).
2. Rename a symbol referenced by a valid coded line, re-scan, and confirm it changes from `JUDGE coded_valid` to
   `DROP STALE`.

## Definition of Done

- Scenarios automated and passing; coverage > 85%; zero warnings; manual evidence recorded.
