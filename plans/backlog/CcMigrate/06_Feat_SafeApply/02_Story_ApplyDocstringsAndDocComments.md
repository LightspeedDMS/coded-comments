# Story 02: Apply Docstrings and Doc Comments

## User Story

**As a** developer migrating a Python-heavy or library codebase
**I want** `--apply` to remove or rewrite Python docstrings (moving coded lines above the declaration) and render
capped docs for exported declarations in each host's doc form
**So that** the biggest source of comment bloat (docstrings: Python 0.148 → 0.546 comment lines per code line once
they count) is migrated with the same code-identity guarantee

**What the user can do after this story:** `--apply` handles every proposal kind; no file is skipped as
`unsupported_kind`. The result is left uncommitted in the working tree for review with `git diff`.

## Scope

### Python docstrings

| proposal | edit |
|---|---|
| DROP, docstring is not the only body statement | delete the docstring's lines |
| DROP, docstring is the sole body statement | replace the docstring's lines with one `pass` line at the body indentation; record the insertion for the verifier |
| DROP, module docstring | delete its lines (an empty module is valid) |
| REWRITE (def/class) | delete the docstring as above, and insert the composed lines directly above `target_start_line` (first decorator) at the owner's indentation |
| REWRITE (module) | replace the module docstring lines with the composed lines at column 0 (file-wide facts at the top, how.md) |
| CAP | replace the docstring with the capped docstring (same quote style and string prefix, same indentation), and insert any CAP coded lines above `target_start_line` |

Capped Python docstring layout (from `reference/examples.md`): `"""Summary."""` when there is only a summary;
otherwise the summary line, one blank line, then one `name: note` line per note, then the closing quotes on their own
line, all at the body indentation.

### CAP rendering per doc form (no coded syntax inside; the content is exactly the validated `cap_text`)

| host / original form | rendering |
|---|---|
| python docstring | as above |
| typescript_javascript, java `/** */` | `/**` / ` * Summary.` / ` * @param name note` / ` * @returns note` / ` * @throws Type note` / ` */` |
| c, cpp `/** */` or `///` | same form as the original; Doxygen `@param`, `@return`, `@throws` |
| csharp `///`, pascal `///` with XML | `/// <summary>Summary.</summary>`, `/// <param name="name">note</param>`, `/// <returns>note</returns>`, `/// <exception cref="Type">note</exception>` |
| pascal `///` without XML, `{ }` | the same delimiter style as the original, plain lines |
| rust `///` / `//!` | plain lines with the same prefix |
| go `//` | plain lines with `// ` prefix |
| plsql `--` / `/* */` | same delimiter style, plain lines |

Note-name mapping: `return`/`returns` → return element; `raise`/`raises`/`throws`/`exception` (optionally followed by
a type) → throws element; anything else → param element. The indentation is that of the original doc.

## Algorithm

```
plan_docstring_edit(p, file):
  ds = p.span; owner = p.declaration
  IF p.disposition == DROP:
    IF p.sole_statement: RETURN Replace(ds.lines, indent(ds) + "pass" + nl, record=InsertedPass(line))
    RETURN Delete(ds.lines)
  IF p.disposition == REWRITE:
    IF owner.kind == module: RETURN Replace(ds.lines, [L + nl for L in p.lines])
    edits = [Delete or Replace-with-pass as in DROP]
    edits += Insert(before_line=owner.target_start_line, lines=[indent(owner) + L + nl for L in p.lines])
    RETURN edits
  IF p.disposition == CAP:
    edits = [Replace(ds.lines, render_python_cap(p.cap_text, quote_style(ds), prefix(ds), body_indent))]
    IF p.lines: edits += Insert(before_line=owner.target_start_line, lines=[indent(owner) + L + nl for L in p.lines])
    RETURN edits

render_doc_cap(p, host, original_form):
  summary, notes = split cap_text into first line and "name: note" lines (already validated by CapValidator)
  RETURN host-form lines per the CAP rendering table, each prefixed with the original doc's indent
```

The verifier from Story 01 removes `InsertedPass` tokens before comparing token streams, and compares Python ASTs
with docstrings stripped and each recorded inserted `pass` removed. Insertions and deletions in one file are ordered
by byte offset descending. A docstring edit and an insert above its owner never overlap, because the owner header
lies between them.

## Acceptance Criteria

```gherkin
Feature: docstrings and doc comments

  Scenario: A redundant private docstring is removed
    Given "def _load(path):" whose body is a docstring "Load the path." followed by "return open(path).read()" and a DROP proposal
    When I apply
    Then the docstring lines are gone and the function body starts with "return"
    And verification passes

  Scenario: A sole-statement docstring becomes pass
    Given an abstract method whose only body statement is a docstring, with a DROP proposal
    When I apply
    Then the docstring is replaced by "pass" at the body indentation
    And the AST check passes with the inserted pass recorded

  Scenario: Rewritten docstrings move above the decorated declaration
    Given "@cache" above "def flush(self):" with a docstring and a REWRITE line "#^ order flush before close; close drops _buf"
    When I apply
    Then "#^ order flush before close; close drops _buf" is on the line directly above "@cache" at the same indentation
    And the docstring is gone

  Scenario: Capped Python docstring on an exported function
    Given an exported "connect(url, timeout)" with a long docstring and a CAP proposal "Open a pooled connection.\ntimeout: seconds per attempt, not total."
    When I apply
    Then the docstring reads exactly as in reference/examples.md, keeping the original quote style and indentation

  Scenario Outline: CAP rendering per host form
    Given an exported <host> declaration with a <form> doc and a CAP proposal with a summary and one param note
    When I apply
    Then the doc is rendered in <form> with the summary and the param note and nothing else
    And verification passes

    Examples:
      | host                  | form       |
      | typescript_javascript | /** */     |
      | java                  | /** */     |
      | csharp                | /// XML    |
      | rust                  | ///        |
      | go                    | //         |
      | cpp                   | ///        |
      | pascal                | /// XML    |
```

## Implementation Status

- [ ] Python docstring edit plans (delete, sole-statement `pass`, move above the target, module case)
- [ ] Python CAP docstring rendering (quote style, prefix, indentation)
- [ ] CAP rendering for every host doc form, with note-name mapping
- [ ] Verifier support for recorded `InsertedPass`
- [ ] Unit tests per edit and per form (real lexers, real `ast`)
- [ ] Integration tests in real temp git repos (docstring and CAP edits, identity failure)
- [ ] E2E manual testing completed by Claude Code

**Completion:** 0/7 tasks complete (0%)

## Testing Requirements

- Every Python fixture with docstrings: synthetic DROP-all and REWRITE-all proposals must verify and `py_compile`.
- Round-trip test: after apply, re-scan finds no docstring units except CAP ones, and those CAP docs equal the
  proposals' `cap_text` once the delimiters are stripped.

## Manual E2E Test Plan (Claude Code)

1. Copy claude-usage-reporting to a temp dir, run a real dry run and `--apply`; inspect `git diff` for a sample of
   files; run its test suite (`pytest`) in the copy to confirm behavior is unchanged.
2. Run the multi-host scratch repo with CAP proposals and read each rendered doc.

## Definition of Done

- Scenarios automated and passing; coverage > 85%; zero warnings; manual evidence recorded.
