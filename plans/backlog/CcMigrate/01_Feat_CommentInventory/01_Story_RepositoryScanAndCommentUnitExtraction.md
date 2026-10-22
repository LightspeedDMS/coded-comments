# Story 01: Repository Scan and Comment Unit Extraction

## User Story

**As a** developer who wants to de-bloat a codebase's comments
**I want to** run `cc-migrate scan <path>` and see every comment unit in all supported files, counted per host
**So that** I know the size of the migration, and every later stage works from an exact, trustworthy inventory

**What the user can do after this story:** install the tool from `tool/cc-migrate/`, run `cc-migrate scan` on any git
work tree, and get per-host counts of files, units by kind, comment lines and code lines. They also get the full unit
list as JSON with exact byte and line spans, and the skipped files with reasons.

## Scope

- `tool/cc-migrate/` package skeleton with `pyproject.toml` (Python ≥ 3.11, console script `cc-migrate`), installable
  alone (`pip install -e tool/cc-migrate`). `install.sh` is not touched.
- Settings: `src/cc_migrate/config/defaults.toml` < user config (`--config FILE`) < CLI flags. Keys used in this story:
  `reference_dir`, `include`, `exclude`, `max_file_bytes`, `hosts.<name>.enabled`, `sql_dialects` (glob → host).
- CLI help text loaded from `help/*.md` by `ContentLoader` (anti-inline-prompts). A missing help file fails loudly.
- `HostRegistry`: extension → host → explicit Pygments lexer class, plus the host yaml loaded from `reference_dir`.
- Unit extraction for `line_run`, `block`, `trailing`. Docstrings and doc-comment kinds are recognized in Story 02;
  in this story a doc comment is extracted as `line_run` or `block`.

### Host and lexer table (from Decision D1 and D8 evidence)

| host | extensions | Pygments lexer |
|---|---|---|
| python | `.py .pyi` | `PythonLexer` |
| typescript_javascript | `.ts .mts .cts` / `.tsx` / `.js .mjs .cjs` / `.jsx` | `TypeScriptLexer` / `TsxLexer` / `JavascriptLexer` / `JsxLexer` (`.mts`/`.cts` have no Pygments filename mapping, so they are mapped explicitly) |
| shell | `.sh .bash`, extensionless files whose line 1 is a `sh`/`bash` shebang | `BashLexer` |
| go | `.go` | `GoLexer` |
| rust | `.rs` | `RustLexer` |
| csharp | `.cs` | `CSharpLexer` |
| java | `.java` | `JavaLexer` |
| pascal | `.pas .dpr .lpr .pp` (`.pp` explicitly, because Pygments maps it to Puppet) | `DelphiLexer` |
| c | `.c`, `.h` when the repo has no C++ sources | `CLexer` |
| cpp | `.cpp .cc .cxx .hpp .hh .hxx`, `.h` when the repo has C++ sources | `CppLexer` |
| plsql | `.pks .pkb .pls .plb .prc .fnc .trg`, `.sql` by `sql_dialects` | `SqlLexer` (Pygments has no PL/SQL lexer) |
| postgresql | `.sql` by `sql_dialects` | `PostgresLexer` |
| tsql | `.sql` by `sql_dialects` | `TransactSqlLexer` |
| sqlite | `.sql` by `sql_dialects` | `SqlLexer` (the `sqlite3` alias is a console lexer) |

Comment token types: `Comment.Single`, `Comment.Multiline`, `Comment.Special`, `String.Doc` (Rust `///` `//!`).
**Excluded:** `Comment.Preproc` and `Comment.PreprocFile` (C/C# preprocessor directives are code) and
`Comment.Hashbang`, which becomes a unit of kind `line_run` flagged `hashbang=true` so F2 can keep it.
Python `String.Doc` is ignored in this story; Story 02 takes docstrings from `ast`.

## Algorithm

```
scan(path, settings):
  root = git rev-parse --show-toplevel (cwd=path)
  IF command fails: EXIT 2 "cc-migrate needs a git work tree: <path>"
  hosts = HostRegistry.load(settings.reference_dir)        # fails loudly if any of the 14 host yaml files is missing
  listed = git ls-files -z --cached --others --exclude-standard (cwd=root)
  ASSERT len(listed) <= settings.max_files (default 200000), else EXIT 2 "too many files"

  inventory = Inventory()
  FOR rel_path IN listed (bounded by len(listed)):
    IF NOT matches_any(rel_path, settings.include) OR matches_any(rel_path, settings.exclude): CONTINUE
    host = HostRegistry.host_for(rel_path, root, settings.sql_dialects)
    IF host is NONE: CONTINUE                                   # unsupported extension: not counted
    IF host is SQL_UNCONFIGURED: inventory.skip(rel_path, "sql_dialect_unconfigured"); CONTINUE
    IF NOT settings.hosts[host].enabled: inventory.skip(rel_path, "host_disabled"); CONTINUE
    size = file size
    IF size > settings.max_file_bytes: inventory.skip(rel_path, "too_large", size); CONTINUE
    bytes = read file
    text = decode UTF-8 strict (keep BOM flag); ON error: inventory.skip(rel_path, "not_utf8"); CONTINUE
    tokens = lexer(host).get_tokens_unprocessed(text)          # gives character offsets
    IF any token type in Token.Error: inventory.skip(rel_path, "lexer_error", first error line); CONTINUE
    units = UnitExtractor.extract(text, tokens, host)
    counts = LineCounter.count(text, tokens)                    # code lines = non-blank lines with a non-comment, non-docstring token
    inventory.add(SourceFile(rel_path, host, sha256(bytes), newline_style(text)), units, counts)
  RETURN inventory

UnitExtractor.extract(text, tokens, host):
  comment_tokens = merge adjacent tokens of the same comment (Pygments splits /* */ into pieces)
  FOR each comment c (in order):
    line_prefix = text from start of c's line to c.start
    IF c is single-line style AND line_prefix is whitespace only: candidate full-line comment
    ELIF c is single-line style: emit Unit(kind=trailing, span=c, indent=column of statement start)
    ELSE: emit Unit(kind=block, span=c)                         # block tokens never join a run (S6)
  group consecutive full-line candidates into line_run units WHEN:
      next.line == prev.line + 1 AND same start column AND same comment token style
  each unit:
    unit_id   = sha256(path, start_byte, end_byte, file_sha)[:16]
    raw_text  = exact source bytes of the span
    normalized_text = strip markers (#, //, --, /* */, (* *), { }, leading " * "), trim, collapse inner whitespace
    span      = byte offsets on the UTF-8 encoding; line/col 1-based
  RETURN units

render(inventory, flags):
  IF --json: print JSON {files:[...], units:[...] (when --units), skipped:[...], totals:{...}}
  ELSE: print table per host: files, line_run, block, trailing, comment lines, code lines, comment/code ratio;
        then skipped files grouped by reason
  exit code 0 (skips are reported, not errors)
```

## Acceptance Criteria

```gherkin
Feature: cc-migrate scan

  Scenario: Scan a repo containing all 14 hosts
    Given a temporary git repo with one fixture file per host, including a .sql file and sql_dialects mapping "db/pg/*.sql" to postgresql
    When I run "cc-migrate scan <repo>"
    Then the output has one row per host with non-zero file and unit counts
    And the exit code is 0

  Scenario: Comment markers inside strings are not comments
    Given python 'x = "# not"', go 'x := `// raw`', rust 'r#"// raw"#', pascal "'it''s // x'", tsql '[a--b]', and a bash heredoc line "# not comment"
    When I run "cc-migrate scan <repo> --units --json"
    Then none of those string contents appears as a unit
    And each real comment on the same lines appears as a trailing unit

  Scenario: Line runs follow grammar rule S3
    Given three consecutive "#" lines, a blank line, then two "#" lines at the same indentation
    When I scan the file
    Then I get two line_run units with 3 and 2 lines

  Scenario: Preprocessor directives are code
    Given a C file with "#pragma once" and a C# file with "#region Foo"
    When I scan
    Then neither directive is reported as a unit

  Scenario: Exact spans
    Given any unit reported by scan
    When I slice the file bytes with start_byte and end_byte
    Then the slice equals the unit's raw_text exactly

  Scenario: Scale controls
    Given include ["src/**"], exclude ["**/vendor/**"], max_file_bytes 1000, and hosts.rust.enabled false
    When I scan a repo with files in and outside these filters, one file larger than 1000 bytes, and one .rs file
    Then only included files are counted
    And the large file is listed under skipped with reason "too_large"
    And the .rs file is listed under skipped with reason "host_disabled"
    And files ignored by .gitignore are not listed at all

  Scenario: Files that cannot be lexed safely are skipped with a reason
    Given a Latin-1 encoded .py file and a file whose lexing produces Token.Error
    When I scan
    Then they are listed as skipped with reasons "not_utf8" and "lexer_error" with a line number
    And the exit code is 0

  Scenario: SQL dialect is never guessed
    Given a .sql file and no sql_dialects mapping covering it
    When I scan
    Then the file is skipped with reason "sql_dialect_unconfigured"

  Scenario: Not a git work tree
    Given a plain directory that is not inside a git work tree
    When I run "cc-migrate scan <dir>"
    Then the exit code is 2
    And stderr says "cc-migrate needs a git work tree: <dir>"

  Scenario: Missing reference tree fails loudly
    Given reference_dir points to a directory without hosts/python.yaml
    When I run any cc-migrate command
    Then the exit code is 2 and stderr names the missing file
```

## Implementation Status

- [ ] `tool/cc-migrate/` package skeleton, `pyproject.toml`, console script, `README.md`
- [ ] Settings loader with precedence and `defaults.toml`
- [ ] `ContentLoader` (help files, reference tree) failing loudly on missing files
- [ ] `GitWorkTree` check and `FileEnumerator` with globs, size limit, per-host enable
- [ ] `HostRegistry` (14 hosts, explicit lexer classes, `.h` and `.sql` rules)
- [ ] `UnitExtractor` (line_run, block, trailing; spans; normalization) and `LineCounter`
- [ ] `cc-migrate scan` table and `--json --units` output
- [ ] Fixture files for all 14 hosts under `tests/fixtures/hosts/<host>/`
- [ ] Unit tests (real Pygments lexers on real fixture text, no mocks)
- [ ] Integration tests creating real git repos in temp dirs
- [ ] E2E manual testing completed by Claude Code

**Completion:** 0/11 tasks complete (0%)

## Testing Requirements

- Unit: the extraction table per host (one fixture per host with line_run, block, trailing and string-lookalikes);
  span round-trip (`bytes[start:end] == raw_text`) asserted for every unit of every fixture; CRLF and UTF-8 BOM files.
- Integration: a temp git repo created with `git init`, files committed and untracked, a `.gitignore`; asserts
  enumeration and skip reasons. No mocks of git, the file system or Pygments.
- Coverage > 85% for `inventory/`, `config/`, `content/`.

## Manual E2E Test Plan (Claude Code)

1. `python3.11 -m venv .tmp/venv && .tmp/venv/bin/pip install -e tool/cc-migrate`.
2. Copy `~/Dev/claude-usage-reporting` to a temp dir (`cp -a`, never touch the original), then run
   `cc-migrate scan <copy>`. Check that the python and shell rows exist and the comment/code ratio is plausible.
3. `cc-migrate scan <copy> --units --json | python -m json.tool | head`. Pick three units and confirm their spans
   with `sed -n`.
4. Create a scratch git repo with the 14 fixture files, scan it, and confirm the per-host rows and skip reasons.
5. Run on a non-git dir and check exit code 2 and the message.

## Definition of Done

- All acceptance scenarios pass as automated tests; coverage > 85%; zero lint and type warnings.
- Manual E2E steps executed with evidence (command output) recorded in the story.
- No file > 1000 lines, no function > 120 lines, no inline help or prompt text in code.
