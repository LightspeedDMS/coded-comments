# Doc-comment volume: Go, Rust, C#, Java

Doc comments counted per host: Go = contiguous // block directly above a column-0 package/func/type/var/const (//go: style directives skipped; public iff identifier capitalised; grouped var/const ( = unknown). Rust = /// runs above an item (attributes skipped; public iff item starts 'pub ' - pub(crate) etc. private) and //! runs (public iff file is lib.rs). C# = /// runs (public iff declaration has public, or protected without private; internal/private = private; no modifier, e.g. enum member = unknown). Java = /** */ blocks (public iff public/protected; private = private; no modifier = unknown). Known gaps: Go struct-field and interface-method docs, Rust trait-impl methods, interface members and package-private are not modelled. These hosts' doc comments are already counted as comment lines by scanner.py, so the inclusive ratio equals the original ratio. Line counts, not tokens.

| Scope | Lang | Files | Doc spans | Doc lines | Public | Private | Unknown | Comment lines | Doc share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all | go | 134 | 986 | 2548 | 1694 | 851 | 3 | 6427 | 0.396452 |
| all | rust | 60 | 711 | 5309 | 1450 | 3859 | 0 | 6037 | 0.87941 |
| all | csharp | 60 | 353 | 1576 | 992 | 441 | 143 | 2750 | 0.573091 |
| all | java | 78 | 275 | 1940 | 1624 | 193 | 123 | 2247 | 0.863373 |
| excl_tests. | go | 64 | 713 | 1973 | 1202 | 771 | 0 | 4249 | 0.464345 |
| excl_tests. | rust | 48 | 557 | 4310 | 1450 | 2860 | 0 | 4954 | 0.870004 |
| excl_tests. | csharp | 60 | 353 | 1576 | 992 | 441 | 143 | 2750 | 0.573091 |
| excl_tests. | java | 78 | 275 | 1940 | 1624 | 193 | 123 | 2247 | 0.863373 |
