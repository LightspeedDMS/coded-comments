# Grammar examples

Not installed. Checked by `.analysis/grammar_check.py` and `.analysis/rules_check.py`. References are illustrative;
syntax and rule S1 are checked, resolution is not.

## Valid

```coded
#^ coupled activated-repos with golden-repos copy-on-write; build_snapshot_manager; #1052
#^ order ensure_encryption_key_salt before manager init; failure => abort startup
//^ invariant `Vec<u8>`.len() <= cap
//^ hazard missing abi_version => None, not current ABI; #1784
--^ coupled token-family tables with RefreshTokenBackend._ensure_schema; db/migrations/025.sql
#^ external playwright --with-deps = Debian only; doc:playwright-cli#install
//^ security RemoveDangerouslySkipPermissions before launch; --allowedTools enforced
//^ perf lookup = hot loop; cache = per request; src/idx/lookup.rs:probe
#^ todo split parse_config; #412
//^ why retry = 3, not backoff; server drops idle conns > 30s
//^ external `println!` = stdout; `!flag` = unset
//^ order `a;b` before c.go
//^ invariant id != 0;len>=1; cap <= 64;n>0
//^ coupled foo.bar baz
x = load()  #^ order load() before validate
```

## Invalid (grammar or S1)

```bad
#^ invariant This function validates the input thoroughly
//^ see hot loop
#^ note x=y
//^invariant x<y
//^ hazard a=>
#^ order a before b;  c before d
// invariant x<=y
#^ see
#^ coupled a=>b=>c
//^ invariant a<=b<=c
//^ invariant `Vec<u8>.len()<=cap
//^ invariant ``<=cap
/*^ invariant x<y */
```

Why, in order: no anchor, operator, or before/after (S1); no anchor, operator, or before/after (S1); unknown tag; no
space after marker; empty operand; two spaces after `;` (at most one space may follow `;`); free-form marker; empty
body; two operators in one clause; two operators; unterminated quote; empty quote; block form.

## Valid, rejected by judgment

The grammar cannot see these as wrong; the reviewer's PROSE and VACUOUS judgment does.

```judged
#^ why function_name is very good, not other_name; extremely secure
//^ hazard x => y; this is just narration
--^ invariant process_data simply returns the input
//^ order alpha beta gamma delta epsilon before x
//^ why retry_count, not other_count; works
#^ invariant config.json looks fine
```
