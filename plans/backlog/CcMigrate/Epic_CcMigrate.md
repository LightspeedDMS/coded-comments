# Epic: cc-migrate — migrate every comment in a codebase to coded-comments

## Epic Completion Status: **🔄 IN PROGRESS**

**Story Completion:** 0/12 stories complete

✅ **COMPLETED STORIES:**
- (none)

🔄 **IN PROGRESS:**
- (none)

⏳ **PENDING:**
- F1 Story 1: Repository Scan and Comment Unit Extraction ⏳ (`01_Feat_CommentInventory/01_Story_RepositoryScanAndCommentUnitExtraction.md`)
- F1 Story 2: Declaration Attachment and Doc Forms ⏳ (`01_Feat_CommentInventory/02_Story_DeclarationAttachmentAndDocForms.md`)
- F2 Story 1: Exemptions and Mechanical Drops ⏳ (`02_Feat_DeterministicPreclassification/01_Story_ExemptionsAndMechanicalDrops.md`)
- F2 Story 2: Repo Index and Coded Line Validator ⏳ (`02_Feat_DeterministicPreclassification/02_Story_RepoIndexAndCodedLineValidator.md`)
- F2 Story 3: Export Status and Judgment Dedupe ⏳ (`02_Feat_DeterministicPreclassification/03_Story_ExportStatusAndJudgmentDedupe.md`)
- F3 Story 1: Judge Request Assembly and Cost Estimate ⏳ (`03_Feat_HaikuJudge/01_Story_JudgeRequestAssemblyAndCostEstimate.md`)
- F3 Story 2: Resumable Batch Judging ⏳ (`03_Feat_HaikuJudge/02_Story_ResumableBatchJudging.md`)
- F4 Story 1: Validated Proposals with Budget Trim ⏳ (`04_Feat_ProposalValidation/01_Story_ValidatedProposalsWithBudgetTrim.md`)
- F5 Story 1: Migration Report and Cost Accounting ⏳ (`05_Feat_DryRunReport/01_Story_MigrationReportAndCostAccounting.md`)
- F6 Story 1: Apply Line, Block and Trailing Proposals ⏳ (`06_Feat_SafeApply/01_Story_ApplyLineBlockAndTrailingProposals.md`)
- F6 Story 2: Apply Docstrings and Doc Comments ⏳ (`06_Feat_SafeApply/02_Story_ApplyDocstringsAndDocComments.md`)
- F7 Story 1: Real Repo Acceptance Run ⏳ (`07_Feat_EndToEndAcceptance/01_Story_RealRepoAcceptanceRun.md`)

**Overall Progress:** 0% complete

---

## Non-Negotiable Principles

These five rules override anything else in this epic, its features or its stories. A story that conflicts with them
is wrong; fix the story.

1. **DEFAULT = DROP.** A comment survives only if it passes a WHAT-gate admission test (`reference/what.md`; tags
   `hazard coupled security invariant external order why see perf todo`). Poetry, narration, restating code, history/changelog, business
   paraphrase and explanations of hard code are removed, plain and simple. **Doubt = DROP.** The LLM judgment has
   **no** UNKNOWN or "needs review" outcome.
2. **Haiku judges and rewrites purely from the comment text.** It never sees code bodies. Its input per comment is the
   comment text plus minimal parser-extracted metadata: host language, file path, comment kind (`line_run`, `block`,
   `docstring`, `doc_comment`, `trailing`), the attached declaration's name, kind and signature line (no body), and an
   `exported` boolean decided **deterministically** by the tool from `reference/hosts/<host>.yaml`. Undecidable export
   status = not exported. Never assume exempt.
3. **One call per comment returns both the verdict and the result.** Structured JSON:
   `{decision: DROP|REWRITE|CAP, lines: [0–3 coded lines], cap_text, reason}`. There is no second "rewrite" call and
   no repair call. A returned line that fails validation is dropped; if every line fails, the comment is dropped.
4. **Cross-file references are resolved by the tool, never invented by Haiku.** Haiku only copies anchors literally
   named in the comment text (or the attached declaration's name, see Decision D6). The tool resolves path and symbol
   anchors against a repo index built once per run. An unresolvable anchor makes that line invalid, and the line is
   dropped.
5. **Deterministic first, LLM second.** Code decides everything that needs no judgment: exemptions, banners,
   commented-out code, existing coded lines that fail the grammar, budget or anchor checks, export status,
   deduplication, validation, budgets and placement. None of it goes to Haiku. Existing coded lines that pass those
   checks are judged by Haiku like any other unit (user decision; F2 Story 02).

**User philosophy:** code is self-explanatory. Claude-generated code is bloated with comments (Python measured at
0.546 comment lines per code line once docstrings count, `docs/evidence.md`). cc-migrate exists to remove that
bloat and keep only the few facts that prevent a mistake or save a search.

---

## Epic Intent

`cc-migrate` is a command-line tool. Pointed at a git work tree, it finds every comment in every supported file and
gives each one exactly one disposition:

| disposition | meaning | decided by |
|---|---|---|
| `KEEP` | valid exemption (whole-comment pragma, legal/metadata header, generated marker) | deterministic code |
| `DROP` | removed; the default for everything that is not admitted | deterministic code or Haiku |
| `REWRITE` | replaced by 1–3 validated coded lines (`#^`, `//^`, `--^`) | Haiku, then validated by code |
| `CAP` | prose doc on a truly exported declaration, reduced to the exemption cap (plus optional coded lines) | Haiku, then validated by code |

Files that cannot be migrated safely are **skipped as a whole**, with a reason in the report (generated file,
non-UTF-8, lexer error tokens, unparseable Python, size limit, unconfigured SQL dialect).

The workflow is: `scan` (inventory) → `migrate --estimate` (cost, zero API calls) → `migrate` (dry run: judge,
validate, write proposals and report) → `migrate --apply` (rewrite files in place from the proposals, zero API calls,
with a code-identity guarantee).

**Apply precondition (user decision):** `--apply` requires the target to be a git repository with a clean working
tree (`git status --porcelain` empty, untracked files included). There is no branch mode: the tool never creates or
switches branches and never commits; the user reviews the result with `git diff` and commits it.

An interrupted dry run is resumed by re-running `migrate` with the same inputs; there is no separate resume or
re-render command. `migrate` itself writes `report.md` and `summary.json` (F5).

---

## Overall Architecture

```
                  cc-migrate CLI  (scan | migrate [--estimate | --apply])
                                              |
        +-------------------------------------+---------------------------------------+
        |                                     |                                       |
        v                                     v                                       v
+------------------+   CommentUnits   +----------------------+   JudgeQueue   +----------------------+
| 1 Inventory      |----------------->| 2 Preclassification  |--------------->| 3 Haiku Judge        |
|  FileEnumerator  |                  |  ExemptionRules      |  (distinct     |  ContentLoader       |
|  HostRegistry    |                  |  MechanicalDrops     |   texts only)  |  RequestBuilder      |
|  Lexer (Pygments)|                  |  CommentedCodeProbe  |                |  CostEstimator       |
|  UnitExtractor   |                  |  CodedLineValidator  |                |  BatchClient         |
|  DeclAttacher    |                  |  ExportDeciders(14)  |                |  RunState (resume)   |
+------------------+                  |  JudgmentDedupe      |                +----------+-----------+
        |                             +----------+-----------+                           | Judgments
        |  file bytes, tokens                    | Dispositions (KEEP/DROP)              v
        |                                        |                      +-----------------------------+
        |                                        +--------------------->| 4 Proposal Validation       |
        |                                                               |  LineComposer (marker)      |
        |                       +-----------------+   RepoIndex          |  CodedLineValidator (reuse) |
        +---------------------->| RepoIndex       |--------------------->|  AnchorResolver             |
                                | paths, idents,  |                      |  CapValidator               |
                                | py qualnames    |                      |  BudgetTrimmer              |
                                +-----------------+                      +--------------+--------------+
                                                                                        | proposals.jsonl
                                       +------------------------------------------------+
                                       v                                                v
                          +---------------------------+                    +---------------------------+
                          | 5 Report                  |                    | 6 Apply                   |
                          |  TokenCounter (o200k)     |                    |  GitGuard (clean tree)    |
                          |  CostAccountant (usage)   |                    |  Editor + Placement       |
                          |  SummaryWriter (md, json) |                    |  IdentityVerifier         |
                          +---------------------------+                    |  (Pygments + Python AST)  |
                                                                           |  Reverter                 |
                                                                           +---------------------------+

  Read-only inputs:  ~/.claude/coded-comments/  (what.md how.md grammar.md exemptions.md rules/core.yaml hosts/*.yaml)
  Tool content:      tool/cc-migrate/src/cc_migrate/prompts/*.md, help/*.md, defaults.toml
  Run state:         ${XDG_CACHE_HOME:-~/.cache}/cc-migrate/<repo-key>/<run-id>/  (never inside the target repo)
```

### Components

| component | responsibility | feature |
|---|---|---|
| `FileEnumerator` | lists candidate files with `git ls-files --cached --others --exclude-standard` (respects `.gitignore`), applies include/exclude globs, max file size, per-host enable flags | F1 |
| `HostRegistry` | maps file extension to host and to an explicit Pygments lexer class (never `get_lexer_for_filename`: `.pp` resolves to Puppet), loads `hosts/<host>.yaml` | F1 |
| `UnitExtractor` | turns comment tokens into `CommentUnit`s: `line_run`, `block`, `trailing`, `docstring`, `doc_comment`, with byte and line spans | F1 |
| `DeclAttacher` | finds the governed declaration or statement of each unit (S3 scope) and extracts name, kind, signature line | F1 |
| `ExemptionRules` | shebang, encoding/modeline, legal/SPDX paragraphs, pragmas (host yaml plus tool `extra_pragmas`; prose after a pragma split off via `pragma_syntax`, Decision D7), generated markers | F2 |
| `MechanicalDrops` | banners, dividers, empty comments, commented-out code → DROP without the LLM | F2 |
| `RepoIndex` | repo-relative paths, identifier set per file and repo-wide, Python qualified names; built once per run | F2 |
| `CodedLineValidator` | grammar (regexes from `rules/core.yaml`), S1, budgets (`line_chars`, `line_tokens`, `run_lines`), anchor resolution and provenance; reused by F2 for existing lines (failing lines DROP, passing lines go to Haiku) and by F4 for new lines | F2 |
| `ExportDeciders` | one deterministic decider per host; undecidable = not exported | F2 |
| `JudgmentDedupe` | groups units by a `JudgmentKey` so each distinct text is judged once | F2 |
| `ContentLoader` | loads `prompts/*.md`, `help/*.md` and the installed reference files; fails loudly when any file is missing | F3 |
| `RequestBuilder` | renders the cached system prefix and the per-unit user message; attaches the JSON schema | F3 |
| `CostEstimator` | offline token and dollar estimate (tiktoken o200k proxy, pricing from config) | F3 |
| `BatchClient` | warm-up request, Message Batches submit, bounded polling, result streaming, bounded resubmission | F3 |
| `RunState` | atomic, resumable state file keyed by run id; an interrupted run never pays twice | F3 |
| `LineComposer` | prefixes the host marker to `tag body` returned by Haiku (Haiku never writes markers) | F4 |
| `AnchorResolver` | resolves path/symbol anchors and expands a unique basename to its repo-relative path | F4 |
| `CapValidator` | checks capped doc text against the exemption cap | F4 |
| `BudgetTrimmer` | enforces `run_lines` and `coded_per_code` with a deterministic drop order | F4 |
| `ProposalStore` | writes and reads `proposals.jsonl` plus `manifest.json` (`complete:false` and no `proposals.jsonl` for an incomplete run, Decision D11) | F4 |
| `TokenCounter`, `CostAccountant`, `SummaryWriter` | before/after comment tokens, actual API cost from `usage`, `report.md` and `summary.json` | F5 |
| `GitGuard` | target is a git work tree with a clean status; file hashes match the dry run | F6 |
| `Editor` / `Placement` | byte-exact edits: removal, coded run above the governed declaration, trailing stays trailing, indentation kept, CRLF kept | F6 |
| `IdentityVerifier` | non-comment Pygments token stream identical before and after; Python AST equal modulo docstrings | F6 |
| `Reverter` | restore original bytes held in memory on failure | F6 |

### Ubiquitous Language

| term | meaning |
|---|---|
| Host | one of the 14 language bindings in `reference/hosts/` |
| CommentUnit | the smallest thing judged: a line run, block, trailing comment, docstring or doc comment |
| Governed target | the declaration or statement a unit (or coded run) applies to (grammar rule S3) |
| Disposition | `KEEP`, `DROP`, `REWRITE`, `CAP`, plus the deterministic `JUDGE` (pending Haiku) during a run |
| JudgmentKey | dedupe key: `sha256(host, kind, exported, normalized text)` |
| Judgment | Haiku's one structured answer for one JudgmentKey |
| Proposal | the validated, placement-ready outcome for one unit |
| Run | one dry run identified by `run-id = sha256(HEAD, file hashes, config, prompt and reference hashes, model)` |

---

## Technology Stack

| technology | purpose | why |
|---|---|---|
| Python ≥ 3.11 | implementation language | `tomllib` in stdlib; `/usr/bin/python3.11` exists on this machine; the target's Python files are parsed by the tool's own `ast` |
| Pygments 2.19.x | lexing for all 14 hosts: comment extraction, name tokens, identity verification | see Decision D1 |
| Python `ast` (stdlib) | Python docstrings, qualified names, `__all__`, AST-equality check | exact, no dependency |
| `anthropic` Python SDK | Message Batches, prompt caching, structured outputs (`output_config.format` JSON schema) | official SDK; never raw HTTP |
| `tiktoken` (`o200k_base`) | comment-token proxy for budgets, the report and the estimate | same proxy as `docs/evidence.md`, offline |
| PyYAML | reads `rules/core.yaml` and `hosts/*.yaml` | the reference tree is YAML |
| `jsonschema` | validates each parsed judgment against `JUDGMENT_SCHEMA` before use | structured outputs constrain generation, but a parsed response is still checked (anti-silent-failure) |
| git CLI | file enumeration that respects `.gitignore`, clean-tree check | single enumeration path |
| pytest + pytest-cov | unit, integration and E2E tests; coverage > 85% | team standard |

Model facts used by this epic (claude-api reference, cached 2026-10-06; verify at implementation time and keep them
in `defaults.toml`, never hard-coded): `claude-haiku-5-5` costs $0.10 input / $0.50 output per MTok for prompts of
100K tokens or less. Batches cost 50% of standard prices, hold up to 100,000 requests or 256 MB per batch, finish
within 24 hours at most, and keep results for 29 days. Cache reads cost 0.1× input, 5-minute writes 1.25× and 1-hour
writes 2×. The minimum cacheable prefix for Haiku 5.5 is 512 tokens. On Haiku 5.5, adaptive thinking is on by default
and counts toward `max_tokens`; `temperature` and `top_p` other than their defaults return a 400, and so does an
assistant prefill. Structured outputs go through `output_config.format`.

---

## Key Architectural Decisions

### D1. Lexer: Pygments, not tree-sitter (decided with evidence)

Criteria: (a) one tokenizer covers all 14 hosts, (b) it separates comments from strings correctly, (c) it gives
enough name tokens for declaration metadata, (d) the same tokenizer can verify that only comment bytes changed,
(e) dependency weight and Python 3.11 compatibility.

Evidence gathered 2026-10-14 on this machine (`pygments 2.19.2`, `tree-sitter-language-pack 0.9.1` wheel inspected):

| criterion | Pygments 2.19.2 | tree-sitter-language-pack 0.9.1 |
|---|---|---|
| hosts covered | all 14: Python, TS/TSX, JS/JSX, Bash, Go, Rust, C#, Java, Delphi (Pascal), C, C++, PostgreSQL, PL/pgSQL, Transact-SQL, generic SQL. **No PL/SQL lexer** (alias `plsql` absent): PL/SQL uses the generic `sql` lexer. The `sqlite3` alias is a *console* lexer: SQLite uses generic `sql` | bundled grammars include python, typescript, tsx, javascript, bash, go, rust, java, pascal, c, cpp, one generic `sql`. **No C#, no T-SQL, no PL/SQL, no PL/pgSQL** |
| comments vs strings | probe: `"// not"`, `` `// raw` `` (Go), `r#"// raw"#` (Rust), `'it''s // x'` (Delphi), `$${x#pre}`, heredoc `# not comment`, T-SQL `[a--b]`, `'a--b'`: none lexed as comments; real comments were | grammar-level, accurate |
| doc forms | Python docstring = `String.Doc`; Rust `///` and `//!` = `String.Doc`; Java/TS `/** */` = `Comment.Multiline`; C# and C++ `///` = `Comment.Single` (prefix rule needed) | node kinds per grammar |
| pitfalls found | C/C# `#pragma`, `#region` are `Comment.Preproc` (they are code and must be excluded); Delphi `{$mode}` is `Comment.Multiline` (pragma rule `{$` handles it); `get_lexer_for_filename("a.pp")` = Puppet | none for the covered grammars |
| declaration metadata | `Name.Function`, `Name.Class`, `Name.Namespace` tokens on the signature line | full syntax tree |
| weight | pure Python, already installed | 19.5 MB wheel with native `.so` per grammar |

**Decision:** Pygments is the single lexer for extraction, metadata and identity verification. The stdlib `ast`
complements it for Python only (docstrings, qualified names, `__all__`, AST equality). tree-sitter is rejected
because it lacks C#, T-SQL and PL/SQL. Using it would mean running two lexing stacks, and verification would no
longer use one tokenizer across all hosts. **Accepted cost:** export decisions for Rust, C#, Java, C++ and Pascal
need brace/section tracking over tokens instead of a syntax tree. Where that tracking cannot decide, the answer is
"not exported" (principle 2). Files whose lexing produces `Token.Error` are skipped, not guessed.

### D2. Haiku never writes markers
Haiku returns `{tag, body}` pairs. `LineComposer` prefixes the host marker from `hosts/<host>.yaml`. This removes a
whole class of SYNTAX failures, and the cached system prefix needs no host files, so one prefix serves all 14 hosts.

### D3. Cached prefix content
System prefix = `prompts/judge.md` (the tool's own instructions) + `what.md` + `how.md` + `grammar.md` +
`exemptions.md`, loaded from the installed tree (`reference_dir`, default `~/.claude/coded-comments`, configurable).
One `cache_control` breakpoint sits at the end of the prefix with a 1-hour TTL (`cache_ttl`, configurable). Batches
run requests concurrently, and an entry is readable only after its first response starts, so one **warm-up request**
(the first distinct unit, sent synchronously at standard price) writes the cache before the batch is submitted. Its
result is recorded like any other. Cache hits inside a batch are best effort; the report shows the real
`cache_read_input_tokens`.

### D4. Structured output, not forced tool use
Requests use `output_config.format` with a JSON schema (`decision` enum, `lines[]` of `{tag enum, body}`, `cap_text`,
`reason`). There is no `temperature` (it returns a 400 on Haiku 5.5) and no prefill. Thinking is adaptive with
`effort` = `low` (configurable). `max_tokens` = 2048 (configurable), because thinking counts toward it. Any
`stop_reason` other than `end_turn`, unparseable JSON, a schema violation or a refusal counts as **malformed**: the
unit is DROPPED and the count shows in the report.

### D5. Dedupe key
`JudgmentKey = sha256(host, kind, exported, normalized comment text)`. The declaration is deliberately left out of
the key, so repeated texts are judged once (agreed in conversation). The request carries the first occurrence's
declaration. Anchor provenance (D6) is re-checked **per occurrence**, so a line naming occurrence A's declaration is
dropped at occurrence B.

### D6. Anchor provenance
A path or symbol anchor in a returned line must appear literally in the comment text or be the attached
declaration's name. The declaration name is allowed because `reference/examples.md` shows `#^ order _flush before close`
naming the governed function. **The default `anchor_provenance = "comment+decl"` (comment text plus the governed
declaration's name) is the user's approved decision.** The setting keeps the option `anchor_provenance = "comment"`
to tighten this to comment-text-only.
`#n` issue anchors and `doc:` anchors must appear literally in the comment text. The tool makes no network calls to
verify `doc:` targets. A bare basename (`refresh_token_backend.py`) that matches exactly one repo path is expanded to
its repo-relative path; zero or several matches make the line invalid.

### D7. Pragmas: keep the whole pragma, split off trailing prose (user decision)
A comment is `KEEP` whole **only when the entire comment is a recognized pragma** (`exemptions.md` rule 2: host yaml
`pragma` or a tool `extra_pragmas` entry, with its arguments). When a pragma is followed by prose and the pragma's
argument syntax is known for the host (`pragma_syntax` in `defaults.toml`, e.g. `noqa: CODES`, `type: ignore[...]`,
`pylint: disable=...`, `eslint-disable... -- reason`, plus the other host yaml pragmas with a regular argument
syntax), the comment is **split**: the pragma bytes stay in place as `KEEP "pragma"`, and the prose becomes its own
unit that is classified and judged by Haiku like any other comment (DROP or REWRITE; a REWRITE is placed as a coded
line above the governed statement, F4). When the boundary between pragma and prose cannot be determined (no
`pragma_syntax` entry for that pragma, or the entry does not match), the comment is kept **unchanged** and listed as a
`FREE` warning (`pragma_boundary_unknown`) in the report's attention section (F5), never silently.

### D8. SQL dialect is configured, never guessed
`.pks .pkb .pls .plb .prc .fnc .trg` map to `plsql`. A `.sql` file needs a dialect from `sql_dialects` (glob →
host) in the config. Without one, the file is skipped with reason `sql_dialect_unconfigured` (anti-fallback).
`.h` maps to `cpp` when the repo contains any `.cpp/.cc/.cxx` file, else to `c`.

### D9. Run state lives outside the target repo
`--apply` requires a clean tree, so state, proposals and reports are written to
`${XDG_CACHE_HOME:-~/.cache}/cc-migrate/<repo-key>/<run-id>/` (`--work-dir` overrides). Nothing is ever written
inside the target repo except by `--apply`.

### D10. Token measurement
Comment tokens (before/after), `line_tokens` budgets and the estimate use tiktoken `o200k_base` as a proxy for
Claude's tokenizer, consistent with `docs/evidence.md`. `count_tokens` is not used, because the estimate must make
zero API calls. API cost in the report comes only from the `usage` fields the API returned. The report also shows
the estimated/actual input-token ratio, so the proxy error is visible.

### D11. Incomplete runs fail clearly
Batch results that are `errored` (server side) or `expired` are resubmitted at most `max_resubmits` times (default 2).
Units still without a judgment make the run **incomplete**: F4 writes `manifest.json` with `complete:false` (listing
the unjudged keys) and no `proposals.jsonl`; `migrate` still renders `report.md` and `summary.json` from the manifest
and the run state, showing which units are incomplete, and exits 3; `--apply` refuses a run whose manifest has
`complete:false` (exit 2); re-running `migrate` resumes and resubmits only those keys. An `invalid_request` error is a tool bug and aborts the run. Units are
never silently dropped for infrastructure reasons, and no UNKNOWN judgment is invented.

### D12. Tool placement (anti-file-chaos)
```
tool/cc-migrate/
  pyproject.toml            # package cc-migrate, console script cc-migrate, installable on its own
  README.md                 # install and usage
  src/cc_migrate/
    cli.py
    config/      defaults.toml, settings loading and precedence
    content/     loader code only (loads prompts/, help/ and the reference tree; holds no .md files)
    prompts/     judge.md, unit.md                 # every prompt .md lives here
    help/        scan.md, migrate.md               # every help/message .md lives here
    inventory/   files, hosts, lexing, units, declarations
    classify/    exemptions, mechanical, commented_code, export/<host>, dedupe
    coded/       grammar, anchors, repo_index, budgets
    judge/       requests, estimate, batch, state, results
    proposals/   compose, validate, cap, trim, store
    report/      tokens, cost, summary
    apply/       git_guard, editor, placement, verify
  tests/  unit/  integration/  e2e/  fixtures/hosts/<host>/  fixtures/recorded_judgments/
```
`install.sh` stays reference-only. No source file exceeds 1000 lines and no function exceeds 120 lines.

---

## Features (implementation order)

1. **01_Feat_CommentInventory**: `cc-migrate scan <path>` finds every comment unit in all 14 hosts with exact
   positions, kind and attached-declaration metadata, under scale controls (globs, size, `.gitignore`, per-host enable).
2. **02_Feat_DeterministicPreclassification**: exemptions, mechanical drops, commented-out code, the repo index and
   coded-line validator (existing coded lines), deterministic export status and judgment dedupe. `scan` reports what
   will be kept, dropped and judged.
3. **03_Feat_HaikuJudge**: request assembly from external prompt files, `migrate --estimate` with zero API calls, and
   resumable Message Batches judging with prompt caching and structured output.
4. **04_Feat_ProposalValidation**: every returned line composed, validated and resolved; CAP text capped; per-file
   budgets trimmed deterministically; `proposals.jsonl` written.
5. **05_Feat_DryRunReport**: per-file and total counts, comment tokens before/after, real API cost, budget status,
   skipped files.
6. **06_Feat_SafeApply**: `migrate --apply` rewrites files from the proposals in a clean git tree, verifies the code
   identity and reverts any failing file.
7. **07_Feat_EndToEndAcceptance**: real Haiku run on a temporary copy of a real repo, plus a judgment calibration set.

Scale controls (agreed in conversation) are placed where the code needs them: globs, size, `.gitignore` and
per-host enable live in F1 (the scanner applies them), and `--estimate` lives in F3 (it needs the exact rendered
requests).

---

## Testing Rules

Every story follows these rules; stories reference them instead of restating them.

- **TDD:** each behavior starts as a failing test. Package coverage stays > 85%; zero lint and type warnings.
- **Anti-mock:** real files, real Pygments lexers, real stdlib `ast`, real tiktoken, and real git repositories created
  with `git init` in pytest temp directories. Git, the file system, the lexers and the repo index are never mocked.
- **No API mocks in E2E or integration tests:** they call the real Anthropic API, run only with `CC_MIGRATE_REAL_API=1`
  and a key, and are reported as skipped otherwise (visible, never silently omitted).
- **Recorded real Haiku responses** (captured by those real-API tests, stored in `tests/fixtures/recorded_judgments/`)
  are allowed as fixtures **only** for unit tests of the validator (the F3 result parser's response checks and the F4
  proposal validation), the report (F5) and apply (F6). Hand-built judgment records are allowed only as validator
  input data for edge cases real runs rarely produce (malformed line, unresolvable anchor, over budget), never as a
  stand-in for the API in integration or E2E tests.
- **Calibration set:** the labeled comments from `.analysis/` are copied into `tests/fixtures/calibration/` and used
  only in tests (F7); the tool never reads `.analysis/` at runtime.

---

## Known Limits (by design)

- **Explanations of hard code are deleted.** The code is the source of truth; an explanation is not an admission test.
- **Haiku compresses what a comment claims; it cannot verify the claim is still true.** Only anchors are verified
  (existence and provenance), not the semantics of a `hazard` or `invariant`.
- **Context-dependent comments are dropped** ("because of the above", "same as before"): Haiku sees no code.
- **Evidence gaps:** C, C++ and Pascal had no corpus samples in the design phase, and the four SQL dialects were
  pooled. Their host bindings rest on syntax knowledge, and their pragma and generated lists may be incomplete; the
  tool's `extra_pragmas` mitigates this.
- **Identity verification uses the same lexer that found the comments.** For Python, the AST check is independent. For
  the other hosts, a lexer that mistakes string content for a comment would also pass verification. Files with
  `Token.Error` are skipped to reduce that risk, and the risk stays documented.
- **Symbol resolution outside Python is identifier-level.** `A.b` resolves when both identifiers occur in the repo
  (or in the named file for `path:A.b`). It does not check that `b` is a member of `A`. Python uses exact qualified
  names from `ast`.
- **Prose after a pragma is split only where the pragma's argument syntax is known** (`pragma_syntax`). Otherwise the
  comment is kept unchanged and listed as a `FREE pragma_boundary_unknown` warning in the report (Decision D7).
- **Path-shaped words that are not paths** (`_AC/_BAT/_SAV`) make a line invalid and get it dropped. The judge prompt
  tells Haiku to quote or avoid them.
- **Python files whose syntax is newer than the tool's interpreter** fail `ast.parse` and are skipped.
- **Comments inside PostgreSQL dollar-quoted bodies** are migrated only when the routine's `LANGUAGE` is `sql` or
  `plpgsql`; otherwise they are excluded and counted.

## Risks and Mitigations

| risk | mitigation |
|---|---|
| A tool pragma missing from the host yaml gets dropped and breaks a linter | `extra_pragmas` seeded with common ones (`pyright:`, `isort:`, `nosec`, `istanbul ignore`, `c8 ignore`, `biome-ignore`, `@ts-check`, `eslint-env`, `NOSONAR`, `codeql[`, `lgtm[`, `nolint`); the report lists dropped comments for review before `--apply` |
| Batch cache misses inflate cost | warm-up request, 1-hour TTL, a no-cache upper bound in the estimate, actual cache reads in the report |
| An interrupted or expired batch | atomic `RunState`; results are retained for 29 days; bounded resubmission; resume never resubmits a judged key |
| Apply corrupts code | clean-tree precondition, file-hash match, token identity plus Python AST check, in-memory revert, git history |
| LLM nondeterminism makes tests flaky | unit tests use recorded real judgments; real-API tests assert structural properties and calibrated thresholds |

## Out of Scope

- A reviewer or validator for future diffs (the reference tree's reviewer spec covers that).
- Strict ISO Pascal and C89 (`docs/open-questions.md` decision 5).
- Editing `COMMENT ON` (PostgreSQL) or `sp_addextendedproperty` (T-SQL): those are code, not comments.
- Any LLM backend other than the Anthropic API. With no `ANTHROPIC_API_KEY`, the run fails loudly.
