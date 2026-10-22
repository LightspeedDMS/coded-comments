# Story 03: Export Status and Judgment Dedupe

## User Story

**As a** developer migrating a library or an application
**I want** each doc comment and docstring marked `exported` true or false by deterministic per-host rules, with
undecidable cases treated as not exported, and units headed for judgment grouped so each distinct text is judged
once
**So that** only the truly exported surface can keep capped prose (principle 2, `exemptions.md`), and I pay for one
judgment per distinct comment, not per repeated copy

**What the user can do after this story:** `cc-migrate scan <path>` shows `exported` per doc unit with the rule that
decided it (`export_rule`, e.g. `python:__all__`, `go:capitalized+exported_receiver`, `undecidable`). It also shows
`units_to_judge`, `distinct_judgments` and the dedupe ratio per host and in total.

## Scope

- `exported` is computed only for `docstring` and `doc_comment` units. All other units are `exported=false`.
- One decider per host. Each implements only what it can decide from the repository; everything else returns
  `(false, "undecidable")`. Undecidable is never exempt.

### Export rules (from `hosts/<host>.yaml` `exported`, decidable subset)

| host | exported = true when | everything else |
|---|---|---|
| python | the owner's name is in a static `__all__` list/tuple of its module; or the module's package `__init__.py` explicitly imports it (`from .mod import Name`); or it is a `[project.scripts]`/entry-point target in `pyproject.toml`; or it is a public (no leading `_`) method/class docstring of a class that is exported by one of these rules; module docstring when the module is a package `__init__.py` whose package is imported by those rules | false |
| typescript_javascript | **library** (nearest `package.json` has `main`, `exports` or `types`, and `"private"` is not true): the declaration has `export`, or a local name listed in `export { ... }`, or is a public (not `private`/`#`) member of an exported class. **App**: the name is re-exported by the entry file (`main`/`exports` target) | false; no package.json = undecidable |
| shell, sqlite (doc none), postgresql, tsql (doc forms are code) | never applicable | false |
| go | identifier capitalized; package name is not `main`; path has no `internal/` segment; for methods, the receiver type is capitalized | false |
| rust | crate has `src/lib.rs`; the item is `pub` (not `pub(crate)`/`pub(super)`/`pub(in ...)`); and either it is declared in `lib.rs`, or every module on the path from `lib.rs` is declared `pub mod`, or `lib.rs` has a `pub use` naming it | false |
| csharp | the member and every enclosing type are `public` (tracked by brace depth over tokens); the nearest `.csproj` has no `<OutputType>Exe</OutputType>` / `WinExe` | false |
| java | the member and its top-level type are `public`; if a `module-info.java` exists, the package is in an `exports` clause; if none exists, the nearest build file declares a library (Gradle `java-library` plugin, or Maven `<packaging>jar</packaging>` or no packaging, with no `mainClass` configured) | false |
| pascal | the declaration lies between the unit's `interface` and `implementation` keywords | false |
| c | the file is a header under a top-level `include/` directory and the declaration is not `static` | false |
| cpp | the file is a header under a top-level `include/` directory, the declaration is not `static`, and inside a class/struct it is in a `public:` section (`struct` default public, `class` default private) | false |
| plsql | the repo contains `GRANT ... ON <object> TO <grantee>` for the containing package or object, where the grantee is not the owning schema | false |

### Dedupe

```
JudgmentKey = sha256( host | kind | exported | normalized_text )         # Decision D5
```

`normalized_text` comes from F1 (markers stripped, whitespace collapsed); case is preserved. The representative of
each key is its first occurrence in (path, start_byte) order. Every occurrence keeps its own `unit_id` and
`declaration` for the per-occurrence provenance check in F4.

## Algorithm

```
decide_exports(units, files, index, host_settings):
  project = ProjectFacts.load(root)           # package.json files, pyproject.toml, lib.rs, *.csproj, module-info.java,
                                              # build files, GRANT statements, include/ headers; parsed once, bounded
  FOR u IN units WHERE u.kind IN (docstring, doc_comment):
    (u.exported, u.export_rule) = DECIDERS[u.host](u, files[u.path], project, index)
    ASSERT u.export_rule is not empty                          # every decision is explained
  FOR other units: (u.exported, u.export_rule) = (false, "not_doc")

dedupe(units):
  queue = ordered map JudgmentKey -> {representative, occurrences[]}
  FOR u IN units WHERE u.disposition == JUDGE (sorted by path, start_byte):
    k = JudgmentKey(u)
    IF k not in queue: queue[k] = {representative: u, occurrences: []}
    queue[k].occurrences.append(u.unit_id)
  RETURN queue                                                 # len(queue) = distinct judgments

python_decider(u, file, project, index):
  owner = u.declaration
  module_all = static __all__ of file (ast: Assign to __all__ of List/Tuple of str constants), else NONE
  IF owner.kind == module: RETURN (file is __init__.py AND package_is_exported(file), "python:package_init")
  IF module_all is not NONE AND owner.top_level_name in module_all: RETURN (true, "python:__all__")
  IF owner.top_level_name in project.init_reexports[package_of(file)]: RETURN (true, "python:init_reexport")
  IF (module_path, owner.name) in project.entry_points: RETURN (true, "python:entry_point")
  IF owner.kind == method AND NOT owner.name startswith "_" AND class_is_exported(owner.class): RETURN (true, "python:member_of_exported")
  RETURN (false, "undecidable")
```

The other deciders follow the table, with the same shape: each returns `(bool, rule_name)` and is unit-tested on a
fixture for every row and every "false" branch.

## Acceptance Criteria

```gherkin
Feature: export status and dedupe

  Scenario: Python __all__ decides export
    Given "pkg/api.py" with __all__ = ["connect"] and docstrings on "connect" and "_helper"
    When I run "cc-migrate scan <repo> --units --json"
    Then the "connect" docstring has exported true and export_rule "python:__all__"
    And the "_helper" docstring has exported false

  Scenario: Go unexported receiver
    Given "func (s *store) Load()" with a doc comment in package "cache" (not under internal/)
    When I scan
    Then the doc comment has exported false

  Scenario: Go internal and main packages
    Given capitalized functions with doc comments in "internal/x/x.go" and in a "package main" file
    When I scan
    Then both have exported false

  Scenario: TypeScript app versus library
    Given a package.json with "private": true and no main/exports/types, and "export function f()" with a JSDoc in a non-entry module
    When I scan
    Then the JSDoc has exported false
    When package.json instead has "main": "dist/index.js" and no private flag
    Then the JSDoc has exported true with export_rule "ts:library_export"

  Scenario: Pascal interface section
    Given a unit with a "///" doc above a procedure in the interface section and another in the implementation section
    When I scan
    Then the first has exported true and the second false

  Scenario: Undecidable is never exempt
    Given a Rust crate with only src/main.rs and a "pub fn" with "///" docs
    When I scan
    Then the doc has exported false

  Scenario: Repeated texts are judged once
    Given 40 python files each containing the same "# Initialize the logger" line_run (not exported)
    When I scan
    Then units_to_judge counts 40 and distinct_judgments counts 1 for that text
    And all 40 unit_ids are listed as occurrences of one JudgmentKey in the JSON
```

## Implementation Status

- [ ] `ProjectFacts` loader (package.json, pyproject.toml, lib.rs module tree, csproj, module-info, build files, GRANTs, include/ headers)
- [ ] Python, TS/JS, Go deciders
- [ ] Rust, C#, Java deciders (brace and section tracking over tokens)
- [ ] Pascal, C, C++, PL/SQL deciders; non-applicable hosts
- [ ] `JudgmentKey` and dedupe queue with occurrences
- [ ] `scan` fields: `exported`, `export_rule`, `units_to_judge`, `distinct_judgments`
- [ ] Unit tests per decider row and per false branch (real fixture projects)
- [ ] E2E manual testing completed by Claude Code

**Completion:** 0/8 tasks complete (0%)

## Testing Requirements

- One fixture mini-project per host under `tests/fixtures/export/<host>/`, created as real files (and real temp git
  repos in integration tests).
- Assert that no decider ever returns true with an empty or `undecidable` rule.

## Manual E2E Test Plan (Claude Code)

1. On the claude-usage-reporting copy, run `scan --units --json`. List the docstrings with exported true and check two
   against `__all__` / `__init__.py` by hand; check the dedupe counts.
2. In the 14-host fixture repo, confirm one true and one false export per applicable host.

## Definition of Done

- Scenarios automated and passing; coverage > 85%; zero warnings; manual evidence recorded.
