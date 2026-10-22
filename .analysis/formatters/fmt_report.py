"""Markdown rendering of the matrix results."""

from fmt_specs import POSITIONS

CELL = {"unchanged": "=", "marker_changed": "M", "text_changed": "T", "whitespace_only": "W", "line_missing": "X"}
LEGEND = ("Legend: `=` unchanged, `M` marker rewritten, `T` text after marker changed, `W` only whitespace around "
          "the marker changed, `X` line vanished, `E` formatter error, `-` position absent in language "
          "(S = spaced form, L = legacy unspaced form).")
VARIANT_TITLE = {"clean": "clean (fixtures already formatted)",
                 "deindented": "deindented (all leading whitespace stripped; formatter must re-indent)"}


def cell(recs):
    parts = []
    for form in "SL":
        match = [x for x in recs if x["form"] == form]
        if not match:
            parts.append("%s:-" % form)
        elif match[0]["status"] == "error":
            parts.append("%s:E" % form)
        else:
            parts.append("%s:%s" % (form, CELL[match[0]["kind"]]))
    return " ".join(parts)


def headline_lines(res):
    spaced_all = [r for r in res["records"] if r["form"] == "S"]
    spaced = [r for r in spaced_all if r["status"] == "error" or r.get("kind") in ("marker_changed", "text_changed", "line_missing")]
    second = [r for r in spaced_all if r.get("second_pass") not in (None, "unchanged", "n/a")]
    ws_only = [r for r in spaced_all if r.get("kind") == "whitespace_only"]
    lines = ["## Headline", ""]
    if not spaced and not second:
        lines.append("No formatter changed the SPACED marker (`# ^`, `// ^`, `-- ^`) or its text at any position, in either "
                     "fixture variant, on the first or the second pass. The spaced form is a fixed point of every tested "
                     "formatter that ran without error.")
    else:
        lines.append("**%d spaced-form lines had the marker or text changed (or the formatter errored) on pass 1; %d changed "
                     "on pass 2:**" % (len(spaced), len(second)))
        lines.append("")
        lines += ["- %s / %s / %s / %s: `%s` -> `%s` (%s)" % (r["language"], r["formatter"], r["variant"], r["position"],
                                                          r["before"], r.get("after"), r.get("kind") or r.get("detail"))
                  for r in spaced]
    lines += ["", "Whitespace-only adjustments of spaced lines (marker and text intact; re-indentation to the formatter's "
              "own style, or the gap before a trailing comment): %d of %d spaced lines across all runs." %
              (len(ws_only), len(spaced_all))]
    return lines + ["", LEGEND, ""]


def matrix_lines(res, variant):
    recs = res["records"]
    lines = ["## Matrix: variant `%s`" % VARIANT_TITLE[variant], "",
             "| Language | Formatter | " + " | ".join(POSITIONS) + " | idempotent |",
             "|---|---|" + "---|" * (len(POSITIONS) + 1)]
    keys = []
    for r in recs:
        key = (r["language"], r["formatter"])
        if r["variant"] == variant and key not in keys:
            keys.append(key)
    for lang, fmt in keys:
        row = [lang, fmt]
        for pos in POSITIONS:
            row.append(cell([r for r in recs if (r["language"], r["formatter"], r["variant"], r["position"]) ==
                             (lang, fmt, variant, pos)]))
        idem = [i for i in res["idempotency"] if (i["language"], i["formatter"], i["variant"]) == (lang, fmt, variant)]
        row.append("ERR" if any(i["idempotent"] is None for i in idem) else
                   "yes" if all(i["idempotent"] for i in idem) else "NO")
        lines.append("| " + " | ".join(row) + " |")
    return lines + [""]


def legacy_lines(res):
    lines = ["## Legacy-form (unspaced) rewrites, variant `clean`", "",
             "| Language | Formatter | Position | Kind | Before | After |", "|---|---|---|---|---|---|"]
    for r in res["records"]:
        if r["form"] == "L" and r.get("kind") in ("marker_changed", "text_changed", "line_missing") and r["variant"] == "clean":
            lines.append("| %s | %s | %s | %s | `%s` | `%s` |" % (
                r["language"], r["formatter"], r["position"], r["kind"], r["before"], r.get("after")))
    return lines + ["", "The `deindented` variant rewrites of the L form are in results.json.", ""]


def tail_lines(res):
    errs = [r for r in res["records"] if r["status"] == "error"]
    lines = ["## Not applicable / not tested", "", "- Pascal: %s" % res["pascal"],
             "- Shell: no class/struct field construct, so no `field` position.",
             "- Go `pkgdoc` (directly above the `package` clause) exists only for Go; `top` is separated from it by a blank line.",
             "- Python `deindented` variant skipped (indentation is syntax).", "", "## Errors", ""]
    lines += ["- %s / %s / %s: %s" % (r["language"], r["formatter"], r["fixture"], r["detail"]) for r in errs] or ["none"]
    lines += ["", "## Tool versions", ""] + ["- %s: %s" % kv for kv in res["tools"].items()]
    lines += ["", "## Exact commands (per fixture file, fresh temp dir, default config)", "",
              "- black: `black FILE` (empty pyproject.toml beside FILE stops config discovery)",
              "- ruff: `ruff format --isolated FILE`",
              "- gofmt: `gofmt FILE` (stdout captured)",
              "- rustfmt: `rustfmt --edition 2021 --config-path TMPDIR FILE`",
              "- prettier: `prettier --no-config --no-editorconfig --write FILE`",
              "- clang-format: `clang-format -i --style=<LLVM|Google|Chromium|Mozilla|WebKit|Microsoft|GNU> FILE`",
              "- dotnet: `dotnet format whitespace --folder TMPDIR` (DOTNET_CLI_HOME redirected, telemetry off)",
              "- shfmt: `shfmt FILE` (stdout captured; default style = tabs)",
              "- sqlfluff: `sqlfluff format --dialect <postgres|tsql|sqlite|oracle> --nocolor FILE`",
              "- Second pass: same command on the first-pass output; idempotent = both outputs byte-identical.", "",
              "Re-run: `FMT_TOOLS=<dir> TMPDIR=<scratch> python3 .analysis/formatters/run_matrix.py`", ""]
    return lines


def render_md(res):
    lines = ["# Formatter compatibility matrix for the spaced coded-comment marker", "",
             "Generated by `.analysis/formatters/run_matrix.py` at %s. Fixtures: `.analysis/formatters/fixtures/`." %
             res["generated"], ""]
    lines += headline_lines(res)
    for variant in ("clean", "deindented"):
        lines += matrix_lines(res, variant)
    return "\n".join(lines + legacy_lines(res) + tail_lines(res))
