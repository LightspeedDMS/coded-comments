# coded-comments: grammar

```
coded   ::= marker SP tag SP clause ( ";" SP? clause )*
marker  ::= ( "#" | "//" | "--" ) SP? "^"
tag     ::= "hazard" | "coupled" | "security" | "invariant" | "external" | "order" | "why" | "see" | "perf" | "todo"
clause  ::= side ( SP? "=>" SP? side )?
side    ::= operand ( SP? cmp SP? operand )?
operand ::= word ( SP word )*
word    ::= ( quoted | wchar )+
quoted  ::= "`" qchar+ "`"
qchar   ::= any character except "`", LF, CR
wchar   ::= any visible character except ";" "<" ">" "=" "!" "`"
cmp     ::= "<=" | ">=" | "!=" | "<" | ">" | "="
SP      ::= " "
```

Write the marker with the space (`# ^`, `// ^`, `-- ^`), as formatters do; readers accept both. Longest operator wins. Inside backticks every character is literal and a
quoted piece may touch plain characters: `` `Vec<u8>`.len() `` is one word. The host file gives the marker.

## Anchors

A word is an anchor by the first match:
- quoted: its leading identifier must resolve (`Vec<u8>` resolves `Vec`);
- issue: `#` and digits;
- doc: `doc:` and an anchor;
- test: `test:` and a test name; resolves to a test function or case declared in the repository's test files;
- path: contains `/` or ends in `py js ts tsx jsx go rs cs java c h cc cpp hpp pas sh sql md yaml yml json toml xml
  cfg conf ini txt`, optional `:symbol`;
- symbol: has `_`, an inner capital, `.` between name characters, `::`, or ends in `()`. `foo.bar` is a symbol.

Any other word is plain.

## Rules

- S1 anchor: a line has at least one anchor, one operator, or the word `before` or `after`.
- S2 repeat: every physical line carries marker, tag and clauses. No continuation lines.
- S3 scope: a run of coded lines directly above a declaration or statement governs it; a trailing coded comment
  (marker preceded by whitespace) governs its own statement; a blank or uncoded line ends a run.
- S4 freshness: an anchor that stops resolving makes the line STALE.
- S5 operators: `=>` leads to; `=` is; `!=` is not; other `cmp` compare values. At most one `=>` per clause and one
  `cmp` per side. Order uses the words `before` and `after`.
- S6 forms: block comments are never coded. Coded syntax is not used inside prose docs.
- S7 why: the first clause of a `why` line is `<choice>, not <alternative>`; the reason follows after `;`.
