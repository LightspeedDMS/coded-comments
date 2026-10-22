# Story 01: Exemptions and Mechanical Drops

## User Story

**As a** developer migrating comments
**I want** exempt comments (pragmas, legal headers, shebangs, encoding lines, generated markers) kept untouched, and
mechanical junk (banners, dividers, empty comments, commented-out code) dropped without paying for an LLM call
**So that** tooling and legal text never break, and the API budget is spent only on comments that need judgment

**What the user can do after this story:** `cc-migrate scan <path>` shows each unit's disposition (`KEEP`, `DROP`,
`JUDGE`) with a reason (`hashbang`, `encoding`, `legal`, `pragma`, `generated_line`, `empty`, `banner`,
`commented_code`), counts per host and reason, and the files skipped as `generated`. A pragma followed by prose shows
as two units (the pragma bytes `KEEP pragma`, the prose `JUDGE` with `pragma_prose=true`), and a pragma whose prose
boundary cannot be determined shows as `KEEP pragma` with the warning `FREE pragma_boundary_unknown`.

## Scope

- Steps 0–5 and 7–9 of the classification order in `Feat_DeterministicPreclassification.md`. Step 6 (existing coded
  lines) is Story 02. Until Story 02 lands, units that carry the host marker are classified `JUDGE`.
- `extra_pragmas` in `defaults.toml`, per host, added to `hosts/<host>.yaml` `pragma`. Initial seed:
  python `pyright:`, `isort:`, `nosec`, `pragma: no branch`; typescript_javascript `istanbul ignore`, `c8 ignore`,
  `biome-ignore`, `@ts-check`, `eslint-env`, `global `, `jshint`, `@flow`; go `nolint`, `lint:ignore`, `codeql[`,
  `lgtm[`; all slash hosts `NOSONAR`. The user can extend or replace the list; the report shows the effective list.
- Units split at step 3 (legal paragraphs) produce child units with their own spans.
- **Pragma prose split (Decision D7, user decision).** `pragma_syntax` in `defaults.toml`, per host: pragma prefix →
  regex for the exact pragma bytes including its arguments. The user can extend it. Initial seed (from the user's
  examples and the host yaml pragmas with a regular argument syntax):

| host | pragma | pragma bytes (regex sketch) | prose boundary |
|---|---|---|---|
| python | `noqa` | `noqa(: ?[A-Z]+[0-9]+(, ?[A-Z]+[0-9]+)*)?` | after the last code |
| python | `type: ignore` | `type: ?ignore(\[[\w\-, ]+\])?` | after `]` or `ignore` |
| python | `pylint: disable` | `pylint: ?disable=[\w\-]+(, ?[\w\-]+)*` | after the last name |
| python | `pragma: no cover`, `fmt: off`, `pyright:` | the fixed text; `pyright: ?ignore(\[[\w, ]+\])?` | after the match |
| typescript_javascript | `eslint-disable` (all variants) | `eslint-disable(-next-line\|-line)?( [\w\-/@]+(, ?[\w\-/@]+)*)?` | ` -- ` (ESLint's description separator) |
| typescript_javascript | `@ts-ignore`, `@ts-expect-error`, `@ts-nocheck`, `prettier-ignore` | the fixed text | after the match |
| go | `//nolint` | `nolint(:[\w,]+)?` | after the linter list |
| go | `//go:` | `go:\w+.*` (the argument is the rest of the line) | none: the whole comment is the pragma |
| rust | `rustfmt::skip`, `clippy::` | `rustfmt::skip`, `clippy::[\w:]+` | after the match |
| shell | `shellcheck disable`, `shellcheck source` | `shellcheck (disable\|source)=\S+` | after the argument |
| c, cpp | `NOLINT`, `NOLINTNEXTLINE` | `NOLINT(NEXTLINE)?(\([\w\-,.*]+\))?` | after the match |

  A split yields two child units: the pragma bytes (`KEEP pragma`, left in place) and the prose (`pragma_prose=true`),
  whose span starts right after the pragma bytes (separator included) and ends before any closing delimiter (`*/`,
  `}`), so a later DROP or REWRITE removes only those bytes. When the prose starts on a following line of a line run,
  the child is an ordinary line unit made of those whole lines.

## Algorithm

```
classify_file(file, units, host, settings):
  head = first settings.generated_marker_lines lines of file text
  IF any marker in host.generated appears in a comment token within head: RETURN SKIP_FILE("generated", marker)

  FOR unit IN units (in file order):
    unit.disposition = classify_unit(unit, file, host, settings)

classify_unit(u, file, host, s):
  IF u.hashbang AND u.start_line == 1:                                  RETURN KEEP("hashbang")
  IF u.start_line <= 2 AND matches(ENCODING_OR_MODELINE, u.normalized_text): RETURN KEEP("encoding")
  IF u is the file's leading comment unit (only hashbang/encoding/blank lines before it):
      paragraphs = split u at blank comment lines
      IF any paragraph matches LEGAL_PATTERNS:
          split u: legal paragraphs -> KEEP("legal") child units; others -> new child units classified recursively
          RETURN SPLIT
  pragma = first of (host.pragma + s.extra_pragmas[host]) that u.normalized_text starts with
  IF pragma:
      text = marker-stripped comment text with offsets mapped back to u.raw_text bytes
      syn  = s.pragma_syntax[host].get(pragma)                # regex for the exact pragma bytes
      IF syn AND syn.fullmatch(text):                         RETURN KEEP("pragma")      # whole comment is a pragma
      IF syn AND (m = syn.match(text)) AND rest_after(m, separators) is non-empty:
          split u: [start, m.end) -> KEEP("pragma") child (bytes stay in place);
                   rest -> child unit with pragma_prose=true, classified from step 4 on      # a second pragma is still recognized
          RETURN SPLIT                                        # terminates: each split strictly shrinks the text
      IF text.strip() == pragma:                              RETURN KEEP("pragma")
      RETURN KEEP("pragma", warning="FREE pragma_boundary_unknown")       # unchanged, listed in the report (F5)
  IF contains_any(u.normalized_text, host.generated):                   RETURN KEEP("generated_line")
  IF u.normalized_text == "":                                           RETURN DROP("empty")
  IF is_banner(u):                                                      RETURN DROP("banner")
  IF is_commented_code(u, host):                                        RETURN DROP("commented_code")
  RETURN JUDGE

ENCODING_OR_MODELINE = regex  coding[:=]\s*[-\w.]+  |  -\*-.*-\*-  |  \b(vim?|ex):\s*set?\s
LEGAL_PATTERNS       = case-insensitive: copyright | \(c\) | © | licen[cs]e | SPDX-License-Identifier
                       | all rights reserved | permission is hereby granted | warranty

is_banner(u):
  FOR each line L of u (marker-stripped):
    sym = count of characters in "=-*#~/_+<>|." in L;  alnum = count of letters and digits in L
    IF len(L.strip()) >= 3 AND alnum == 0: line is a divider
    ELIF sym >= 6 AND words(L) <= 4 AND sym >= alnum: line is a titled banner      # "===== Helpers ====="
    ELSE: RETURN false
  RETURN true                                     # every line is a divider or a titled banner

is_commented_code(u, host):
  body = marker-stripped text of u with the original line breaks; dedent
  IF host == python:
      tree = ast.parse(body)  ON SyntaxError: RETURN false
      RETURN tree.body is non-empty AND every statement is one of
             (Assign, AugAssign, AnnAssign, Return, Import, ImportFrom, FunctionDef, ClassDef, If, For, While,
              With, Try, Raise, Expr(Call), Expr(Await))           # a bare Name like "Cleanup" is NOT code
  ELSE:
      toks = host lexer tokens of body (bounded by len(body))
      IF any Token.Error in toks: RETURN false
      sig = tokens that are not Text/whitespace
      punct = sig tokens of Punctuation or Operator types
      kw    = sig tokens of Keyword types
      ends_like_code = last non-blank line ends with one of ";", "{", "}", ")" (host statement terminators)
      RETURN len(sig) >= 3 AND ends_like_code AND (punct + kw) / len(sig) >= s.commented_code_min_ratio (default 0.35)
```

Rationale for the heuristic thresholds: a false positive drops a comment, which is the default outcome anyway
(principle 1), so the probe may be aggressive. A false negative sends the unit to Haiku, which is expected to drop
it. The thresholds live in `defaults.toml`.

## Acceptance Criteria

```gherkin
Feature: deterministic exemptions and drops

  Scenario: Generated files are skipped whole
    Given a Go file whose first line is "// Code generated by protoc-gen-go. DO NOT EDIT."
    When I run "cc-migrate scan <repo>"
    Then the file is listed as skipped with reason "generated" and the marker text
    And none of its units is counted

  Scenario: Headers are kept
    Given a Python file starting with "#!/usr/bin/env python3", "# -*- coding: utf-8 -*-", then "# Copyright 2026 ACME", "# SPDX-License-Identifier: MIT", "#", "# Parses the config."
    When I scan with --units
    Then the shebang is KEEP "hashbang", the coding line is KEEP "encoding"
    And the two legal lines form one KEEP "legal" unit
    And "Parses the config." is a separate unit with disposition JUDGE

  Scenario Outline: Comments that are entirely a pragma are kept whole
    Given a <host> file with the comment "<comment>"
    When I scan
    Then the unit is KEEP "pragma"

    Examples:
      | host                  | comment                                   |
      | python                | # noqa: E501                              |
      | python                | # type: ignore[attr-defined]              |
      | python                | # pyright: ignore[reportGeneralTypeIssues] |
      | typescript_javascript | // eslint-disable-next-line no-console    |
      | go                    | //go:build linux                          |
      | rust                  | // rustfmt::skip                          |
      | pascal                | {$mode objfpc}                            |
      | shell                 | # shellcheck disable=SC2086               |

  Scenario Outline: Prose after a pragma with known argument syntax is split off
    Given a <host> file with the comment "<comment>"
    When I scan with --units
    Then "<pragma>" is a KEEP "pragma" unit whose bytes are unchanged in place
    And "<prose>" is a separate unit with pragma_prose true and disposition JUDGE

    Examples:
      | host                  | comment                                                                 | pragma                              | prose                         |
      | python                | x = f()  # noqa: E501 vendor URL cannot wrap                            | noqa: E501                          | vendor URL cannot wrap        |
      | python                | # type: ignore[attr-defined] set by the plugin loader                   | type: ignore[attr-defined]          | set by the plugin loader      |
      | python                | # pylint: disable=broad-except worker must never die                    | pylint: disable=broad-except        | worker must never die         |
      | typescript_javascript | // eslint-disable-next-line no-console -- CI log scraper reads stdout   | eslint-disable-next-line no-console | CI log scraper reads stdout   |

  Scenario: A pragma whose prose boundary cannot be determined is kept and flagged
    Given pragma_syntax has no entry for the java pragma "CHECKSTYLE"
    And a java file with the comment "// CHECKSTYLE:OFF legacy mapping table follows"
    When I scan with --units --json
    Then the unit is KEEP "pragma" with its bytes unchanged
    And it carries the warning "FREE pragma_boundary_unknown"

  Scenario: A pragma whose argument is the rest of the line is kept whole
    Given a go file with the comment "//go:generate stringer -type=Op"
    When I scan
    Then the unit is KEEP "pragma" with no warning

  Scenario: Banners and dividers are dropped
    Given the comments "# ==========", "// ===== Helpers =====", and "-- ----------------"
    When I scan
    Then each is DROP "banner"

  Scenario: Commented-out code is dropped, prose is not
    Given python comments "# result = compute(x, y)" and "# Cleanup"
    And a typescript comment "// const total = items.reduce((a, b) => a + b, 0);"
    When I scan
    Then the two code comments are DROP "commented_code"
    And "# Cleanup" is JUDGE

  Scenario: Empty comments are dropped
    Given a line containing only "#"
    When I scan
    Then it is DROP "empty"

  Scenario: Effective pragma list is visible
    When I run "cc-migrate scan <repo> --json"
    Then the JSON contains the effective pragma list per host (host yaml plus extra_pragmas)
```

## Implementation Status

- [ ] Generated-file skip and generated-line keep
- [ ] Hashbang, encoding/modeline and legal-paragraph rules with unit splitting
- [ ] Pragma rule (host yaml + `extra_pragmas`) with the seeded defaults
- [ ] Pragma prose split (`pragma_syntax` seed, `pragma_prose` child units) and `FREE pragma_boundary_unknown` warning
- [ ] Banner/divider and empty-comment rules
- [ ] Commented-out code probe (Python `ast`; token ratio for other hosts)
- [ ] `scan` disposition column, counts per reason, JSON fields
- [ ] Unit tests per rule and per host
- [ ] Integration test on a temp git repo with all 14 hosts
- [ ] E2E manual testing completed by Claude Code

**Completion:** 0/10 tasks complete (0%)

## Testing Requirements

- One table-driven test per rule with positive and negative cases per host; a legal-split span round-trip test.
- Pragma split: for every `pragma_syntax` seed entry, a whole-pragma case (KEEP, no split), a pragma + prose case
  (split; pragma bytes + prose span reconstruct the original bytes exactly) and a pragma + unknown-syntax case
  (KEEP with the `FREE pragma_boundary_unknown` warning).
- Commented-code probe evaluated on a labeled fixture set (at least 20 code and 20 prose comments drawn from real
  repos); record the false-positive and false-negative counts in the test output.

## Manual E2E Test Plan (Claude Code)

1. `cc-migrate scan <copy of claude-usage-reporting>` shows non-zero `JUDGE` counts and the mechanical drops by
   reason.
2. `--units --json`, then sample ten `DROP` units and ten `KEEP` units and confirm each against the source.
3. Add a protobuf-style generated file to a scratch repo and confirm the whole-file skip.
4. In the scratch repo add `x = f()  # noqa: E501 vendor URL cannot wrap` and a java
   `// CHECKSTYLE:OFF legacy mapping table follows`; run `scan --units --json` and confirm the split (pragma bytes
   `KEEP pragma`, prose `JUDGE` with `pragma_prose=true`) and the `FREE pragma_boundary_unknown` warning.

## Definition of Done

- Scenarios automated and passing; coverage > 85%; zero warnings; manual evidence recorded.
