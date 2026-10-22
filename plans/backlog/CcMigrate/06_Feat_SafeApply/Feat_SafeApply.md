# Feature 06: Safe Apply

## Description

`cc-migrate migrate <path> --apply` rewrites files in place from the completed dry run's `proposals.jsonl`. It makes
**no API calls**, refuses unless the target is a git repository with a clean working tree (user decision; no branch
mode, no commits: the user reviews `git diff` and commits), and guarantees that only comment
bytes changed. That guarantee is checked per file: the non-comment Pygments token stream is identical before and
after, and for Python the AST is equal modulo docstrings. A file that fails the guarantee is restored from the
original bytes held in memory and reported; `git checkout`/`restore` is never used.

## The Code-Identity Guarantee

```
significant(tokens) = [(type, value) for (type, value) in tokens
                       if type not in Comment.* (except Comment.Preproc, Comment.PreprocFile, Comment.Hashbang)
                       and type not in String.Doc
                       and value.strip() != ""]                    # whitespace-only tokens ignored
python docstrings     = stdlib ast docstring nodes (not Pygments), removed before comparison
inserted_pass         = the `pass` statements the editor inserted for sole-statement docstrings (recorded per edit)

verify(before_text, after_text, host, edits):
  ASSERT significant(lex(before)) == significant(lex(after)) minus the recorded inserted_pass tokens
  ASSERT no Token.Error in lex(after)
  IF host == python:
    ASSERT ast.dump(strip_docstrings(ast.parse(before))) == ast.dump(strip_docstrings_and_inserted_pass(ast.parse(after)))
  ASSERT every inserted coded line in after matches the core.yaml regex
```

Whitespace is excluded from token identity because removed lines change it. Python indentation is covered by the
AST check. Go's semicolon insertion is not affected, because the editor never joins lines.

## Technical Architecture

```
migrate --apply
  -> manifest complete? (else exit 2 "dry run incomplete")
  -> GitGuard: work tree, `git status --porcelain` empty (tracked and untracked), HEAD recorded
  -> FOR file in proposals (bounded by manifest.files):
       sha256(current bytes) == manifest.files[path]? else skip "changed_since_dry_run"
       Editor.apply(file bytes, proposals for file)  -> new bytes + edit log
       IdentityVerifier.verify(...)                 -> pass | fail(reason)
       pass: atomic write (temp in same dir + fsync + os.replace), preserve file mode
       fail: keep the original (never written) or restore the original bytes if a write happened; report "reverted: <reason>"
  -> apply report (F5 format + applied/reverted/skipped)
```

## Dependencies

- F4 (proposals with placement), F5 (report format), F1 (lexers), F2 (validator regex).

## Stories (implementation order)

1. **01_Story_ApplyLineBlockAndTrailingProposals**: preconditions, the editor for `line_run`, `block`, `trailing`
   and `doc_comment` (DROP and REWRITE), prose split off a pragma (`pragma_prose`: remove the prose bytes, keep the
   pragma bytes, insert REWRITE lines above the governed statement), verification, revert, apply report. Proposals of
   kinds not yet supported (`docstring`, any CAP) skip their whole file with reason `unsupported_kind` (no broken
   state).
2. **02_Story_ApplyDocstringsAndDocComments**: Python docstrings (move to above the declaration,
   sole-statement `pass`), CAP rendering in every host doc form.

## Integration Points

- F7 drives `--apply` on the copied real repo and checks identity and grammar independently.
