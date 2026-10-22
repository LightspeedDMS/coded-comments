# Grammar examples

Not installed. Checked by `.analysis/grammar_check.py` and `.analysis/rules_check.py`. References are illustrative;
syntax, rule S1 (an anchor, an operator, or before/after), S5 (one `=>` per clause, one comparison per side) and S7
(`why` form) are checked, resolution is not. The canonical marker is spaced (`# ^`, `// ^`, `-- ^`); the legacy
unspaced marker is still read.

## Valid

```coded
# ^ coupled activated-repos with golden-repos copy-on-write; build_snapshot_manager; #1052
# ^ order ensure_encryption_key_salt before manager init; failure => abort startup
// ^ invariant `Vec<u8>`.len() <= cap
// ^ hazard missing abi_version => None, not current ABI; #1784
-- ^ coupled token-family tables with RefreshTokenBackend._ensure_schema; db/migrations/025.sql
# ^ external playwright --with-deps = Debian only; doc:playwright-cli#install
// ^ security RemoveDangerouslySkipPermissions before launch; --allowedTools enforced
// ^ perf lookup = hot loop; cache = per request; src/idx/lookup.rs:probe
# ^ todo split parse_config; #412
// ^ why retry = 3, not backoff; server drops idle conns > 30s
// ^ external `println!` = stdout; `!flag` = unset
// ^ order `a;b` before c.go
// ^ invariant id != 0;len>=1; cap <= 64;n>0
// ^ coupled foo.bar baz
x = load()  # ^ order load() before validate
// ^ hazard evicting idle buckets before refill => key gets free tokens; test:TestSweepKeepsPartialBuckets
// ^ order drain in-flight before stopJanitor; cmd/server/main_test.go:TestShutdownDrainsInFlightRequest
# ^ why skip the retry loop, not wrap it; test:test_send_fails_fast
//^ hazard missing abi_version => None, not current ABI; #1784
# ^ hazard removing set_int_max_str_digits(0) => printing ints > 4300 digits raises ValueError
// ^ hazard attempt > 0 => delay <= maxBackoff
// ^ hazard `float->Duration` conversion => negative RetryAfter
```

The `//^` line is the legacy unspaced marker: still valid, so formatters that rewrite `#^` or `//^` into `# ^` or
`// ^` never invalidate a line.

`=>` binds loosest: a clause is `side => side`, and each side holds at most one comparison. The last three lines are
each one `=>` with a comparison on one or both sides. An unquoted `->` lexes as `-` and `>`, so it reads as a `>`
comparison; quote it, as in the last line.

## Invalid (grammar, S5 or S7)

```bad
# ^ invariant This function validates the input thoroughly
// ^ see hot loop
# ^ note x=y
// ^invariant x<y
// ^ hazard a=>
# ^ order a before b;  c before d
// invariant x<=y
# ^ see
# ^ coupled a=>b=>c
// ^ invariant a<=b<=c
// ^ invariant `Vec<u8>.len()<=cap
// ^ invariant ``<=cap
/*^ invariant x<y */
// ^ hazard a => b < c < d
# ^ invariant a < b = c
// ^ hazard a < b => c => d
# ^ why skip the retry loop; src/net/client.py:send
// ^ why cache per request; backoff = 0
```

Why, in order: no anchor, operator, or before/after (S1); no anchor, operator, or before/after (S1); unknown tag; no
space after marker; empty operand; two spaces after `;` (at most one space may follow `;`); free-form marker; empty
body; two `=>` in one clause (S5); two comparisons on one side (S5); unterminated quote; empty quote; block form; two
comparisons on the right side of `=>` (`<` twice); two comparisons on one side (`<` then `=`); two `=>` in one clause
(after a comparison); `why` without `, not <alternative>` in its first clause (S7), twice.

## Valid, rejected by judgment

The grammar cannot see these as wrong; the reviewer's PROSE and VACUOUS judgment does.

```judged
# ^ why function_name is very good, not other_name; extremely secure
// ^ hazard x => y; this is just narration
-- ^ invariant process_data simply returns the input
// ^ order alpha beta gamma delta epsilon before x
// ^ why retry_count, not other_count; works
# ^ invariant config.json looks fine
```

## Real lines from the example builds (2026-10-22)

Sixteen lines written by agents in the example builds, verbatim (legacy markers kept as written), under the class the
checkers must give them. A line that fails the grammar or S7 is INVALID; a valid line over `line_chars` 160 or
`line_tokens` 40 is BUDGET; the rest are VALID.

Invalid (grammar or S5 or S7). The first two hold two comparisons on one side (`>4300` and the `>` inside `int->str`;
`>=` twice). The last three are `why` lines without `, not <alternative>`; the checkers also report prose signals for
them (`so`; `:` and `but`; `:`) as judged PROSE, which is separate from the grammar result.

```bad
#^ hazard removing this => ValueError printing results >4300 digits on CPython 3.9.14+ (int->str cap); hasattr: older builds lack the API
//^ why tokens >= 1-eps, not >= 1; summed fractional refills drift below 1; internal/limiter/limiter_test.go:TestFractionalRefillIsPreservedAcrossRequests
//^ why PRAGMAs never read the file, so reading the schema is what rejects a non-database file
//^ why double cast: RETURNING always yields a row, but node:sqlite types get() as Record|undefined
//^ why re-check under the write lock: a concurrent migrator may have applied it since the pending scan
```

Valid grammar, over budget (BUDGET). The first line was invalid under the earlier one-operator rule: its unquoted `->`
reads as one `>` comparison left of `=>`, which S5 allows; quoted as `float->Duration` it would say what it means.

```budget
//^ hazard float->Duration conversion without clamp => undefined/negative RetryAfter for tiny rates; internal/limiter/limiter_test.go:TestRetryAfterSaturatesInsteadOfOverflowing
//^ hazard start.Round(0) or UnixNano() math here => wall-clock steps mint/destroy tokens; time.Since uses the monotonic reading, doc:pkg-time#hdr-Monotonic_Clocks
//^ hazard evict on idle alone => key resets to full capacity before refill time, minting tokens; internal/limiter/limiter_test.go:TestSweepKeepsBucketsThatWouldNotBeFullYet
//^ hazard (d+unit-1)/unit rounding => int64 overflow when RetryAfter is saturated at MaxInt64; internal/httpapi/handler_test.go:TestSaturatedRetryAfterDoesNotOverflow
```

Valid.

```coded
//^ why set-but-empty RL_* = invalid, not default; fail fast on misconfiguration; internal/config/config_test.go:TestInvalidValuesAreRejected
//^ order stop accepting + drain in-flight (drain) before stopJanitor; cmd/ratelimiter/main_test.go:TestShutdownDrainsInFlightRequest
//^ coupled help/usage.md sits at the project root, two levels above dist/src/ => keep rootDir "." in tsconfig
//^ hazard foreign_keys is per-connection and a no-op inside a transaction => set at open, never later
//^ coupled mirrors the 'equity' literal in migrations/0001_init.sql (entries_no_overdraft) => change both
//^ coupled migrations/ sits at the project root, two levels above dist/src/ (and src/) => keep rootDir "." in tsconfig
--^ coupled 'equity' literal mirrors EQUITY_ACCOUNT in src/ledger.ts => change both
```

Corrected forms (valid, within budget). Each has at most one `=>` and one comparison per side, replaces the narration
with a clause or a `test:` anchor, and gives `why` its `<choice>, not <alternative>` first clause. The first two drop
the second comparison on a side; the third is shortened and spelled without `->`.

```coded
# ^ hazard removing set_int_max_str_digits(0) => ValueError past 4300 digits; CPython 3.9.14+
// ^ why threshold `1-eps`, not 1; summed fractional refills drift below 1; test:TestFractionalRefillIsPreservedAcrossRequests
// ^ hazard unclamped float to Duration => negative RetryAfter at tiny rates; test:TestRetryAfterSaturatesInsteadOfOverflowing
// ^ external PRAGMAs never read the file => schema read rejects a non-database file
// ^ why double cast, not a null check; INSERT RETURNING => always one row
// ^ why re-check under write lock, not trust the pending scan; concurrent migrator => double apply
// ^ hazard evict on idle alone => key refills before refill time; test:TestSweepKeepsBucketsThatWouldNotBeFullYet
-- ^ coupled 'equity' literal with src/ledger.ts:EQUITY_ACCOUNT
```
