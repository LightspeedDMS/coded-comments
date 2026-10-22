"""Measure docstring-inclusive ratios on the frozen Python and TS/JS sample."""

import ast
import csv
import io
import json
import os
import re
import tokenize
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEV = Path(os.environ.get("CC_CORPUS_DIR", str(Path.home() / "Dev")))
JS_DOC = re.compile(r"/\*\*.*?\*/", re.DOTALL)
JS_EXPORT = re.compile(r"^(?:export\b|(?:declare\s+)?(?:public\s+))")
IGNORED = {tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT,
           tokenize.DEDENT, tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT}


def python_docs(text):
    """Return (first line, last line, visibility) for true AST docstrings."""
    tree = ast.parse(text)
    exported = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            try:
                values = ast.literal_eval(node.value)
                exported.update(x for x in values if isinstance(x, str))
            except (ValueError, TypeError):
                pass
    docs = []

    def visit(node, public, depth):
        body = node.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, (ast.Str, ast.Constant)):
            expr = body[0].value
            if isinstance(getattr(expr, "value", None), str):
                docs.append((expr.lineno, expr.end_lineno, "public" if public else "private"))
        for child in body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = child.name
                visible_name = not name.startswith("_") or (name.startswith("__") and name.endswith("__"))
                visible = public and (visible_name or (depth == 0 and name in exported))
                visit(child, visible, depth + 1)
    visit(tree, True, 0)
    return docs


def js_docs(text):
    """Return JSDoc spans; `export` on the next nonblank line marks public."""
    docs = []
    for match in JS_DOC.finditer(text):
        start = text.count("\n", 0, match.start()) + 1
        end = text.count("\n", 0, match.end() - 1) + 1
        tail = text[match.end():].lstrip()
        visibility = "public" if JS_EXPORT.match(tail) else "private"
        docs.append((start, end, visibility))
    return docs


def python_doc_only_lines(text, docs):
    """Find lines whose only code token is an AST docstring STRING token."""
    ranges = {(a, b) for a, b, _ in docs}
    all_doc_lines = {line for a, b, _ in docs for line in range(a, b + 1)}
    other_code = set()
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in IGNORED:
            continue
        if tok.type == tokenize.STRING and (tok.start[0], tok.end[0]) in ranges:
            continue
        other_code.update(range(tok.start[0], tok.end[0] + 1))
    return all_doc_lines - other_code


def measure_rows(rows):
    totals = defaultdict(lambda: defaultdict(int))
    details = []
    for row in rows:
        lang = row["language"]
        path = DEV / row["repo"] / row["file"]
        text = path.read_text(encoding="utf-8", errors="replace")
        docs = python_docs(text) if lang == "python" else js_docs(text)
        by_visibility = {visibility: set() for visibility in ("public", "private")}
        for first, last, visibility in docs:
            by_visibility[visibility].update(range(first, last + 1))
        # Assign any overlapping spans to public once; a line is never counted twice.
        by_visibility["private"] -= by_visibility["public"]
        doc_lines = by_visibility["public"] | by_visibility["private"]
        base_comment = int(row["comment_lines"])
        base_code = int(row["code_lines"])
        if lang == "python":
            comment_lines = base_comment + len(doc_lines)
            code_lines = base_code - len(python_doc_only_lines(text, docs))
        else:
            # Existing JS lexical scanner already counts JSDoc as comments.
            comment_lines, code_lines = base_comment, base_code
        values = {"files": 1, "docs": len(docs), "doc_lines": len(doc_lines),
                  "public_lines": len(by_visibility["public"]),
                  "private_lines": len(by_visibility["private"]),
                  "inclusive_comment_lines": comment_lines, "inclusive_code_lines": code_lines}
        for key, value in values.items():
            totals[lang][key] += value
        details.append((lang, row["repo"], row["file"], len(docs),
                        len(by_visibility["public"]), len(by_visibility["private"])))
    result = {}
    for lang, values in totals.items():
        out = dict(values)
        out["inclusive_ratio"] = round(out["inclusive_comment_lines"] / out["inclusive_code_lines"], 6)
        result[lang] = out
    return result


def main():
    with (ROOT / "ratio_files.tsv").open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    measured = measure_rows(rows)
    ledger_path = ROOT / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    method = ("Frozen ratio_files.tsv sample. Python: AST first-statement docstrings on module/class/function; "
              "module public; top-level names public unless leading underscore, except __all__; nested names "
              "public only under public ancestor; dunder names public. Count docstring span once as non-code "
              "and subtract docstring-only token lines from code. TS/JS: /** */ lexical spans; public iff "
              "next nonblank text starts export, declare public or public; otherwise private. JSDoc already "
              "included in baseline comment lines. Lexical JS scanner can misclassify strings or detached JSDoc. "
              "Ratio=inclusive comment lines / inclusive code lines, rounded to 6 decimals.")
    for lang, values in measured.items():
        for key, value in values.items():
            ledger["entries"]["doc.%s.%s" % (lang, key)] = {
                "value": value, "source": "ratio_files.tsv and current HEAD files",
                "method": method, "tokenizer": "not applicable"}
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n")
    lines = ["# Docstring-inclusive volume: Python and TS/JS", "", method, "",
             "| Language | Files | Doc spans | Public lines | Private lines | Inclusive comment/code | Ratio |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for lang, v in measured.items():
        lines.append("| %s | %s | %s | %s | %s | %s/%s | %s |" % (
            lang, v["files"], v["docs"], v["public_lines"], v["private_lines"],
            v["inclusive_comment_lines"], v["inclusive_code_lines"], v["inclusive_ratio"]))
    lines += ["", "These are line counts, not token counts. The current file may have changed since the Claude-coauthored commit."]
    (ROOT / "doc_volume_py_js.md").write_text("\n".join(lines) + "\n")
    print("measured doc volume: %s" % {k: v["inclusive_ratio"] for k, v in measured.items()})


if __name__ == "__main__":
    main()
