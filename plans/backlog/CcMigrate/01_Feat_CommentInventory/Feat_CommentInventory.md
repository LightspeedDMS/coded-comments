# Feature 01: Comment Inventory

## Description

Find every comment in every supported file of a git work tree, for all 14 hosts, with exact byte and line positions,
the unit kind, and the governed declaration's metadata. This is the foundation every later feature consumes. The user
gets `cc-migrate scan <path>`: a per-host inventory (files, units by kind, comment lines, code lines,
comment-per-code ratio) and, with `--units --json`, the full unit list.

## Objectives

- One lexer path (Pygments, Decision D1) for all 14 hosts; Python docstrings via the stdlib `ast`.
- Units match what the reference tree means by a comment: contiguous line-comment runs (grammar rule S3: a blank or
  uncoded line ends a run), block comments, trailing comments, docstrings and doc comments.
- Exact spans, so that F6 can edit bytes and nothing else.
- Scale controls applied at enumeration time: `.gitignore` (through git), include/exclude globs, max file size,
  per-host enable flags.
- Whole-file skips with explicit reasons, never silent: non-UTF-8, `Token.Error` in the lexing, Python `ast.parse`
  failure, size over the limit, unconfigured SQL dialect.

## Technical Architecture

```
cc-migrate scan <path> [--units] [--json] [--config FILE]
   |
   v
Settings (defaults.toml < user config < CLI)            ContentLoader (help/*.md for --help text)
   |
   v
GitWorkTree.require(path) --not a work tree--> exit 2 "cc-migrate needs a git work tree: <path>"
   |
   v
FileEnumerator: git ls-files -co --exclude-standard -> include/exclude globs -> size limit -> HostRegistry.host_for(path)
   |                                                                               (disabled host -> skipped: host_disabled)
   v
Lexer.tokens(file, host) --error token--> skipped: lexer_error
   |
   v
UnitExtractor (line_run | block | trailing | docstring | doc_comment)  -> CommentUnit[]
   |
   v
DeclAttacher (governed target: name, kind, signature line)               -> CommentUnit.declaration
   |
   v
ScanReport (table per host | JSON units)
```

Domain objects (pseudocode types):

```
Host            = {name, marker, line_token, block_tokens, doc_rule, lexer_class, pragmas, generated}
SourceFile      = {path (repo-relative), host, bytes, sha256, newline_style}
CommentUnit     = {unit_id, path, host, kind, start_byte, end_byte, start_line, end_line,
                   start_col, indent, raw_text, normalized_text, declaration?}
Declaration     = {name?, kind (function|method|class|type|module|variable|statement|unknown),
                   signature_line, line_no}
SkippedFile     = {path, reason, detail}
```

## Dependencies

- None on other features. Read-only dependency on the installed reference tree (`hosts/*.yaml`) through
  `ContentLoader` with `reference_dir` from the settings.

## Stories (implementation order)

1. **01_Story_RepositoryScanAndCommentUnitExtraction**: package skeleton, settings, git enumeration with scale
   controls, host registry, Pygments lexing, unit extraction for all 14 hosts, `cc-migrate scan` with per-host counts.
2. **02_Story_DeclarationAttachmentAndDocForms**: docstrings (Python `ast`), doc-comment recognition per host,
   governed-target attachment with name, kind and signature line, `scan --units` showing it.

## Integration Points

- F2 consumes `CommentUnit[]` and `SourceFile` bytes and tokens.
- F4 and F6 rely on the spans and the `indent`.
- F5 reuses the code-line and comment-line counts computed here.
