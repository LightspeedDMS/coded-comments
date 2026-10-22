# coded-comments: WHAT to document

For each fact you might write, go top to bottom. The first yes decides.

0. Pragma, license, copyright, shebang, encoding line, generated marker: leave as is.
1. Derivable from the code, names, types or tests in this file or one hop away (a used symbol's definition, its direct
   callers or callees, this unit's test)? Write nothing. Exception, go to 5: only a test that fails after the wrong
   edit holds the rule.
2. History, authorship, date, ticket story, review round, "used to", "fixed in"? Write nothing. Exception, go to 5:
   removal would break a named caller or data.
3. Restates a name, narrates steps, paraphrases a business rule the code shows, labels a section, is a banner,
   commented-out code, or a `todo` with no target? Write nothing.
4. A doc, issue, spec or other code already holds it? Do not copy. If the next edit must respect a rule from it,
   write that rule as one `ext`, `inv` or `haz` line with the `doc:` or path anchor. Else write one `ref` only when
   the target is more than a hop away; otherwise nothing.
5. Match one admission test: write one coded line with that tag. No match: write nothing.

If you cannot say in five words which mistake the line prevents or which search it saves, delete it.

| tag | write it only if |
|---|---|
| `haz` | a plausible edit brings back a known failure and no compiler or test flags that edit; name both |
| `cpl` | changing this forces a change elsewhere that nothing would flag; name the place |
| `sec` | it marks who is trusted, what is validated or what must not be exposed, and the code does not show it |
| `inv` | a condition must stay true and no check, assert or type enforces it here |
| `ext` | behavior depends on an external API, tool, version or spec quirk the code cannot show |
| `ord` | correctness depends on order, concurrency, retry, cleanup or lifecycle that local flow hides |
| `why` | a reader would plausibly "fix" the code into something that fails; give the reason or the rejected option |
| `ref` | the detail lives more than a hop away and a search is slow; never copy the detail |
| `perf` | the path is hot, shown by a number, a bound or a measurement ref; or a simplification changes complexity |
| `todo` | a remaining task is checkable: it names an issue, or a path:symbol and what done looks like |

## Exported surface

A truly exported declaration (host file) may keep one prose doc, in addition to coded lines: a summary line plus one
line per param, return or raise the types do not carry. Never required; omit it when it only repeats the name. No
coded syntax inside it. A fact that passed step 5 goes in a coded line, not in the prose.
