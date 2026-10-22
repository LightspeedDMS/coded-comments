# coded-comments

A comment protocol and a compact comment language for code written and read by AI coding agents.

AI-generated code tends to carry about as much comment as code: restated names, narrated steps, copied docs, ticket
history. Every one of those lines costs context tokens each time an agent reads the file, and most of them tell the
agent nothing it could not derive from the code itself. coded-comments sets a strict admission test for comments and a
terse, machine-checkable line format for the few that pass.

```
// ^ hazard removing nonce check => replay attacks; #123
# ^ order ensure_key_salt before KeyManager init; failure => abort startup
-- ^ coupled token-family tables with src/code_indexer/server/storage/sqlite_backends/refresh_token_backend.py:RefreshTokenSqliteBackend._ensure_schema
```

## Principles

- **Self-explanatory code first.** A comment is written only if it prevents a mistake or saves a search that the
  code, names, types and tests cannot answer. Everything else is deleted, not reworded.
- **One fact per line, coded, never prose.** A surviving comment is a single tagged line with an anchor or an
  operator, so a reviewer can check it mechanically and an agent can read it in a few tokens.
- **Verifiable references.** Paths, symbols, issue numbers and doc anchors must resolve. A reference that stops
  resolving is a detectable defect, not silent rot.
- **Small instruction footprint.** The installed rules are split by task so an agent loads only what it needs: about
  1,990 tokens to write comments, about 3,500 to review them (o200k, with a 150-token host-file allowance).

## Example

Before:

```python
# Initialize the cache
cache = {}

# Loop over the users and add each one to the cache.
# Added in PR #212 after the refactor.
for user in users:
    cache[user.id] = user

# IMPORTANT: the salt must exist before the key manager starts,
# otherwise startup should fail instead of continuing.
ensure_key_salt()
manager = KeyManager()
```

After:

```python
cache = {}
for user in users:
    cache[user.id] = user

# ^ order ensure_key_salt before KeyManager init; failure => abort startup
ensure_key_salt()
manager = KeyManager()
```

The first two comments restate the code or record history and are removed. The third carries an ordering constraint
the code does not show, so it survives as one coded line.

## The language

A coded line is `<marker> <tag> <clause>[; <clause>]`: one fact per physical line, no continuation lines. Clauses
are terse facts that keep their verbs ("must parse as", "is read last") and drop filler.

**Markers** (line comments only):

| marker | languages |
|---|---|
| `# ^` | Python, Shell |
| `// ^` | TypeScript/JavaScript, Go, Rust, C#, Java, C, C++, Pascal (Delphi, Free Pascal) |
| `-- ^` | SQL: Oracle PL/SQL, PostgreSQL, SQL Server T-SQL, SQLite |

The marker is written with a space for formatter compatibility: black, ruff and gofmt rewrite `#^` and `//^` into
that form. Readers accept both the spaced and the legacy unspaced marker.

**Tags.** Each tag has an admission test; a fact that matches none is not written.

| tag | write it only if |
|---|---|
| `hazard` | a plausible edit brings back a known failure and no compiler or test flags that edit |
| `coupled` | changing this forces a change elsewhere that nothing would flag |
| `security` | it marks who is trusted, what is validated or what must not be exposed, and the code does not show it |
| `invariant` | a condition must stay true and no check, assert or type enforces it here |
| `external` | behavior depends on an external API, tool, version or spec quirk the code cannot show |
| `order` | correctness depends on order, concurrency, retry, cleanup or lifecycle that local flow hides |
| `why` | a reader would plausibly "fix" the code into something that fails; the line names that rejected option (`not X`) |
| `see` | the detail lives more than a hop away and a search is slow |
| `perf` | the path is hot, shown by a number, a bound or a measurement reference |
| `todo` | a remaining task is checkable: an issue number, or `done when <path:symbol> <state>` |

**Operators:** `=>` leads to (causes, then, returns, requires), `=` is, `!=` is not, `<` `<=` `>` `>=` compare values.
`=>` binds loosest: a clause is `side => side` with at most one comparison per side (`removing X => ints > 4300 digits raise`).
Order is written with the words `before` and `after`.
**Anchors:** `path:symbol`, `#123`, `doc:anchor`, `test:Name` (a test that fails on the wrong edit), symbol names, and
backtick literals for names that contain operator characters (`` `Vec<u8>` ``).

```
// ^ invariant topN <= maxSimpleTopN; slice <= 1MiB
# ^ external /etc/tlp.conf is read last => wins over /etc/tlp.d/*.conf
// ^ why return null, not throw; parse error => caller logs warning
// ^ hazard evicting idle buckets before refill => key gets free tokens; test:TestSweepKeepsPartialBuckets
# ^ todo move retry policy to config; done when internal/retry/policy.go:Default reads config
```

A Codex model given only the entry snippet below explained 59 such snippets across all 14 languages, plus 15 held-out
ones, with no misreadings in two consecutive runs ([`.analysis/readability/`](.analysis/readability/README.md)).

**Exempt from the format:** prose docs on the truly exported API surface (capped in length), tool pragmas, license and
copyright headers, shebang and encoding lines, and generated-code markers. Each language's export test, pragmas and
generated markers are defined in its host file under `reference/hosts/`.

The full rules are in [`reference/what.md`](reference/what.md) (what to write), [`reference/how.md`](reference/how.md)
(line shapes and limits) and [`reference/grammar.md`](reference/grammar.md) (EBNF).

## Installation

Requires Bash. The installer copies `reference/` to `~/.claude/coded-comments/`, replacing any previous copy.

```bash
git clone https://github.com/LightspeedDMS/coded-comments.git
cd coded-comments
./install.sh               # install or update
./install.sh --uninstall   # remove ~/.claude/coded-comments
```

The installer touches nothing else under `~/.claude`: not `CLAUDE.md`, `settings.json` or hooks. To activate the
protocol, add the entry snippet it prints (also in [`reference/ENTRY.md`](reference/ENTRY.md)) to your
`~/.claude/CLAUDE.md` or a project's `CLAUDE.md`:

```markdown
## Code comments (coded-comments)
Before writing your first comment in a session, read `~/.claude/coded-comments/index.md`.
In code and tests, comment only to prevent a mistake or save a search that code, names, types and tests cannot. Each comment is one coded line that replaces prose, never sits beside it: `// ^ hazard removing nonce => replay attacks; test:TestReplayRejected` (`# ^` Python/Shell, `-- ^` SQL). Tags: hazard coupled security invariant external order why see perf todo; `why <choice>, not <rejected>; <reason>`. Per clause one `=>` (leads to) and one `=` `!=` `<` `>` per side; order by before/after; `;` separates facts; anchors `path:symbol` `#123` `doc:x` `test:Name`. No prose docs (docstrings, JSDoc, godoc) except on a library's public API. Exempt: pragmas, licenses, generated markers.
```

The snippet costs 214 tokens (o200k; 213 cl100k). The agent reads `index.md` on demand and loads only the files for the task at
hand:

| task | files loaded |
|---|---|
| write comments | `what.md`, `how.md`, one host file |
| review a diff | `reviewer.md`, `what.md`, `rules/core.yaml`, `grammar.md`, `exemptions.md`, one host file |
| migrate existing comments | `migrate.md` plus the writing files |
| decide whether something is exempt | `exemptions.md`, one host file |
| placement examples (optional) | `examples.md` |

## Reviewing

[`reference/reviewer.md`](reference/reviewer.md) specifies a micro code review of the comments in a diff, and
[`reference/rules/core.yaml`](reference/rules/core.yaml) holds the same rules as data for hooks or other tooling.
Each finding is one line with a class, a severity and an action, followed by a verdict:

| severity | action | classes |
|---|---|---|
| high | block | `FREE` (uncoded prose), `SYNTAX`, `PROSE`, `STALE` (unresolvable anchor) |
| medium | warn | `UNKNOWN`, `VACUOUS`, `REDUNDANT`, `UNSUPPORTED`, `SCOPE` |
| low | warn | `DUP`, `DOCCAP`, `BUDGET` |

Default budgets, tunable per project: 160 characters and 40 tokens per line, runs of at most 3 lines, and at most 0.10
coded lines per code line in files of 50 or more code lines.

No validator is shipped; the specification and rule data are meant to be enforced by an agent or a hook.

## Repository layout

| path | contents |
|---|---|
| `reference/` | the installable rule set (24 files) |
| `reference/hosts/` | one binding per language: marker, comment forms, export test, pragmas, generated markers (14 hosts) |
| `docs/design.md` | design overview and rationale |
| `docs/evidence.md` | measurements behind each decision |
| `docs/grammar-examples.md` | valid and invalid line examples |
| `docs/open-questions.md` | settled decisions and known limits |
| `.analysis/` | labeled comment samples, measurement scripts and results (`numbers.json`, cited by `docs/evidence.md`) |
| `install.sh` | installer |

## Evidence and limitations

The design was derived from source files touched by more than 10,000 AI-coauthored commits. In a labeled sample of 72
comments, 34 were redundant and 24 carried value; compressing 10 valuable comments into coded lines reduced them from
868 to 236 tokens. Details and caveats are in [`docs/evidence.md`](docs/evidence.md); the labeled samples, scripts and
results are in `.analysis/`. Re-running the scripts requires the original repositories.

Known limits:

- Token counts use tiktoken `o200k_base` as a proxy for Claude's tokenizer.
- C, C++ and Pascal bindings rest on language knowledge, not corpus measurement; the four SQL dialects were measured
  together.
- Category labels come from a single labeler; counts should be read as ranges.
- The protocol deliberately deletes comments that only explain hard code. The code is treated as the source of truth.

## Roadmap

`cc-migrate`, a command-line tool that migrates every comment in an existing codebase, is specified in epic
[#1](https://github.com/LightspeedDMS/coded-comments/issues/1) and its stories. It sends each comment, with minimal metadata and no code, to a
small model that decides to drop it, rewrite it as coded lines, or trim an exported doc. Every proposal is then
validated against the grammar, budgets and anchor resolution, and a dry-run report is produced before any file
changes.

## License

[MIT](LICENSE) © 2026 Lightspeed DMS
