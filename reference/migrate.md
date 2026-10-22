# coded-comments: migrate existing comments

1. Exempt (`exemptions.md`): leave it.
2. Run the `what.md` gate on every fact in it. No admission: delete.
3. Admitted: write one coded line per fact (`how.md`), anchors resolved.
4. Delete the original. Never keep prose beside its coded line.
5. Check file and diff limits (`how.md`); the migration exception applies when the file's comment lines decrease.

```
# TODO #874: repos_skipped could be derived by walking the domains-to-repos
# mapping; deferred — 0 is a non-None, non-negative int (FR6 contract met).
```
```coded
#^ todo derive repos_skipped;domains-to-repos mapping;#874
```

```
# IMPORTANT: Tantivy uses DFA-based regex engine (via tantivy-fst crate)
# which is immune to ReDoS attacks. All regex queries complete in linear
# time O(n) regardless of pattern complexity.
```
```coded
#^ perf regex_query=linear time DFA;no backtracking
```
