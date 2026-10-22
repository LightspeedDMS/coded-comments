# Story 02: Declaration Attachment and Doc Forms

## User Story

**As a** developer preparing a migration
**I want** each comment unit to carry its doc-form kind and the name, kind and signature line of the declaration or
statement it governs
**So that** the judge receives the minimal metadata it is allowed to see (principle 2), export status can be decided
per declaration, and coded runs can later be placed directly above the governed target

**What the user can do after this story:** `cc-migrate scan <path> --units` lists every unit with its kind
(`line_run`, `block`, `trailing`, `docstring`, `doc_comment`), its governed target (`name`, `kind`,
`signature_line`, `line_no`), and for Python docstrings the owner (module, class or def). The per-host table gains
a `docstring` / `doc_comment` column.

## Scope

### Doc forms per host (from `hosts/<host>.yaml` `doc`)

| host | doc form recognized as `doc_comment` / `docstring` |
|---|---|
| python | `docstring` = first statement of module, class, def or async def that is a string constant (stdlib `ast`; owner lineno, end_lineno and col offsets). Other bare string statements are **not** comments and are not units |
| typescript_javascript, java | `/** ... */` block directly above a declaration |
| c, cpp | `/** ... */` or a `///` line run directly above a declaration |
| csharp | `///` line run directly above a declaration (`Comment.Single` whose text starts with `///`) |
| rust | `///` run (outer doc) above an item; `//!` run (inner doc) at the start of a module or file |
| go | `//` line run directly above a declaration, with no blank line between |
| pascal | `///` run or `{ }` block directly above a declaration |
| plsql | `--` run or `/* */` directly above a package spec item |
| postgresql, tsql | none: their doc forms (`COMMENT ON`, `sp_addextendedproperty`) are code and never units |
| shell, sqlite | none |

"Directly above" follows rule S3: no blank line and no non-comment line between the unit's last line and the target.

### Governed target (S3)

- `line_run`, `block`, `doc_comment`: the first code line after the unit's last line, when no blank line separates
  them; otherwise `kind=none` (a floating comment).
- `trailing`: the statement on its own line (the code before the comment on that line).
- `docstring`: its owner (`def`/`class` header line, or `module`).
- Decorators and attributes (`@x`, `[Attr]`, `#[derive]`, Java annotations) are skipped when finding the
  signature line, and their first line is recorded as `target_start_line` (needed by F6 placement).

## Algorithm

```
attach(unit, tokens_by_line, text, host):
  IF unit.kind == docstring:
    unit.declaration = Declaration(name=owner.name or "<module>", kind=owner.kind,
                                   signature_line=owner header line (first line only),
                                   line_no=owner.lineno, target_start_line=first decorator line or owner.lineno)
    RETURN
  IF unit.kind == trailing:
    line = unit.start_line
    unit.declaration = classify_line(line, tokens_by_line[line], host); RETURN
  next = unit.end_line + 1
  IF next is blank OR next > last line: unit.declaration = Declaration(kind=none); RETURN
  target_start = next
  scan = next
  FOR i IN range(MAX_DECORATOR_LINES = 20):                 # bounded skip over decorators/attributes/annotations
    IF line scan is a decorator/attribute/annotation line (host rule on tokens): scan += 1 ELSE BREAK
  IF i reached the bound: unit.declaration = Declaration(kind=unknown, line_no=target_start); RETURN
  unit.declaration = classify_line(scan, tokens_by_line[scan], host)
  unit.declaration.target_start_line = target_start

classify_line(line_no, line_tokens, host):
  name = first token in (Name.Function, Name.Class, Name.Namespace, Name.Function.Magic) on the line
  kind = mapping of the declaration keyword on the line:
         def/fn/func/function/procedure/sub -> function   (method when nested in a class body: brace/indent depth > 0
                                                           inside a class/struct/impl/interface scope)
         class/struct/interface/trait/enum/type/record/unit/package -> class or type
         const/let/var/val/static/final + Name -> variable
         otherwise -> statement
  IF name is NONE AND kind in (function, class, type, variable):
      name = first plain Name token after the keyword
  signature = the line text, stripped, truncated to signature_max_chars (default 200)
  RETURN Declaration(name, kind, signature, line_no)

doc_form(unit, host):
  IF host rule matches the unit's leading token text (e.g. "///", "/**", "//!") AND declaration.kind != none:
      unit.kind = doc_comment
  # Go: any line_run with declaration.kind in (function, class, type, variable) becomes doc_comment

python_docstrings(text):
  tree = ast.parse(text)  ON SyntaxError: skip file with reason "python_parse_error" (line, msg)
  FOR node IN [module] + every ClassDef/FunctionDef/AsyncFunctionDef (ast.walk is bounded by the node count):
    first = node.body[0] when it is Expr(Constant(str))
    IF first: emit Unit(kind=docstring, span from first.lineno/col_offset to end_lineno/end_col_offset,
                        sole_statement = (len(node.body) == 1), owner=node)
```

## Acceptance Criteria

```gherkin
Feature: governed target and doc forms

  Scenario: Python docstrings come from the AST
    Given a module docstring, a class docstring, a method docstring, and a bare triple-quoted string later in a function body
    When I run "cc-migrate scan <repo> --units --json"
    Then exactly three units have kind "docstring" with owners "<module>", the class name and the method name
    And the bare string statement is not a unit
    And the method docstring unit reports sole_statement true when it is the only body statement

  Scenario: Decorators are skipped for the signature but kept for placement
    Given "# note" above "@cache" above "def load(path):"
    When I scan
    Then the unit's declaration has name "load", kind "function", signature "def load(path):"
    And target_start_line is the line of "@cache"

  Scenario Outline: Doc comment recognition per host
    Given a <host> fixture with <form> directly above "<decl>"
    When I scan
    Then that unit has kind "doc_comment" and declaration name "<name>"

    Examples:
      | host                  | form                | decl                           | name    |
      | rust                  | /// Loads.          | pub fn load() {}               | load    |
      | csharp                | /// <summary>       | public void Load() {}          | Load    |
      | java                  | /** Loads. */       | public void load() {}          | load    |
      | typescript_javascript | /** Loads. */       | export function load() {}      | load    |
      | go                    | // Load loads.      | func Load() {}                 | Load    |
      | pascal                | /// Adds an item    | procedure TList.Add(...);      | Add     |
      | cpp                   | /// Loads.          | void load();                   | load    |

  Scenario: A blank line detaches a comment
    Given "// helper notes", a blank line, then "func helper() {}"
    When I scan
    Then the unit's declaration kind is "none" and its kind is "line_run"

  Scenario: Trailing comments govern their own statement
    Given "MAX_BATCH = 500  # vendor limit"
    When I scan
    Then the trailing unit's declaration has kind "variable", name "MAX_BATCH" and the line as signature

  Scenario: Python files the tool cannot parse are skipped
    Given a .py file with a syntax error
    When I scan
    Then it is skipped with reason "python_parse_error" and the line number
```

## Implementation Status

- [ ] Python docstring extraction via `ast` (owners, spans, `sole_statement`)
- [ ] Doc-form recognition per host (table above)
- [ ] `DeclAttacher` with bounded decorator/attribute skip and `target_start_line`
- [ ] `classify_line` name/kind extraction from Pygments tokens for 14 hosts
- [ ] `scan --units` output with kind and declaration fields; new table columns
- [ ] Unit tests per host with real fixtures
- [ ] Integration test on a temp git repo
- [ ] E2E manual testing completed by Claude Code

**Completion:** 0/8 tasks complete (0%)

## Testing Requirements

- Unit tests per host for every doc form, decorator/attribute skipping, floating comments, trailing targets, nested
  methods (kind `method`), and Python docstring spans that round-trip to exact bytes.
- No mocks: real `ast`, real Pygments, real fixture files.

## Manual E2E Test Plan (Claude Code)

1. Run `cc-migrate scan <copy of claude-usage-reporting> --units --json`. Pick five docstring units and confirm owner
   and span with `sed -n`.
2. Run on the 14-host fixture repo and check one `doc_comment` per host where the host has a doc form.
3. Add a decorated function with a comment above to a scratch repo; confirm `target_start_line` and the signature.

## Definition of Done

- All scenarios automated and passing; coverage > 85%; zero warnings.
- Manual E2E evidence recorded; file and function size limits respected.
