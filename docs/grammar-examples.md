# Grammar examples

Not installed. Checked by `.analysis/grammar_check.py` and `.analysis/rules_check.py`. References are illustrative;
syntax and rule S1 are checked, resolution is not.

## Valid

```coded
#^ cpl activated-repos=golden-repos copy-on-write;build_snapshot_manager;#1052
#^ ord ensure_encryption_key_salt<manager init;failure=>abort startup
//^ inv `Vec<u8>`.len()<=cap
//^ haz missing abi_version=>None not current ABI;#1784
--^ cpl token-family tables=RefreshTokenBackend._ensure_schema;db/migrations/025.sql
#^ ext playwright --with-deps=Debian only;doc:playwright-cli#install
//^ sec RemoveDangerouslySkipPermissions<launch;--allowedTools enforced
//^ perf lookup=hot loop;cache=per request;src/idx/lookup.rs:probe
#^ todo split parse_config;#412
//^ why retry=3 not backoff;server drops idle conns>30s
//^ ext `println!`=stdout;`!flag`=unset
//^ ord `a;b`<c.go
//^ inv id!=0;len>=1;cap<=64;n>0
//^ cpl foo.bar baz
x = load()  #^ ord load()<validate
```

## Invalid (grammar or S1)

```bad
#^ inv This function validates the input before doing anything
//^ ref hot loop
#^ note x=y
//^inv x<y
//^ haz a=>
#^ ord a<b; c<d
// inv x<=y
#^ ref
#^ cpl a=>b=>c
//^ inv a<=b<=c
//^ inv `Vec<u8>.len()<=cap
//^ inv ``<=cap
/*^ inv x<y */
```

Why, in order: no anchor or operator (S1); no anchor or operator (S1); unknown tag; no space after marker; empty
operand; space after `;`; free-form marker; empty body; two operators in one clause; two operators; unterminated
quote; empty quote; block form.

## Valid, rejected by judgment

The grammar cannot see these as wrong; the reviewer's PROSE and VACUOUS judgment does.

```judged
#^ why function_name is very good and extremely secure
//^ haz x=y;this is just narration
--^ inv process_data simply returns the input
//^ ord alpha beta gamma delta epsilon<x
//^ why retry_count works
#^ inv config.json looks fine
```
