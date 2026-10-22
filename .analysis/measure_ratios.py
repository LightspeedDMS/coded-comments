"""Measure comment/code lines in a reproducible Claude-coauthored file sample."""

import csv
import hashlib
import io
import json
import tokenize
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEV = Path.home() / "Dev"
GROUPS = {
    "python": {"code-indexer": "src/", "claude-pace-maker": "src/"},
    "typescript_js": {"tdd-guard": "", "claude-server": "claude-web-ui/src/"},
}
EXTS = {"python": {".py"}, "typescript_js": {".ts", ".tsx", ".js", ".jsx"}}
MAX_PER_REPO = 60


def source_path(path: str) -> bool:
    parts = Path(path).parts
    name = Path(path).name.lower()
    return not any(p.lower() in {"test", "tests", "fixtures", "node_modules", "dist"} for p in parts) and not (
        name.startswith("test_") or name.endswith(("_test.py", ".test.ts", ".test.tsx", ".spec.ts", ".spec.js"))
    )


def py_counts(path: Path):
    data = path.read_bytes()
    comment, code = set(), set()
    ignored = {tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT, tokenize.DEDENT, tokenize.NL, tokenize.NEWLINE}
    for tok in tokenize.tokenize(io.BytesIO(data).readline):
        if tok.type == tokenize.COMMENT:
            comment.add(tok.start[0])
        elif tok.type not in ignored:
            code.update(range(tok.start[0], tok.end[0] + 1))
    return len(comment), len(code)


def js_counts(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    comments = codes = 0
    quote = None
    block = False
    escaped = False
    for line in text.splitlines():
        has_comment = has_code = False
        i = 0
        while i < len(line):
            ch = line[i]
            nxt = line[i + 1] if i + 1 < len(line) else ""
            if block:
                has_comment = True
                if ch == "*" and nxt == "/":
                    block = False
                    i += 2
                else:
                    i += 1
            elif quote:
                has_code = True
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == quote:
                    quote = None
                i += 1
            elif ch == "/" and nxt == "/":
                has_comment = True
                break
            elif ch == "/" and nxt == "*":
                has_comment = True
                block = True
                i += 2
            elif ch in ("'", '"', "`"):
                has_code = True
                quote = ch
                i += 1
            else:
                if not ch.isspace():
                    has_code = True
                i += 1
        comments += has_comment
        codes += has_code
    return comments, codes


def main():
    with (ROOT / "provenance.tsv").open(newline="") as handle:
        provenance = list(csv.DictReader(handle, delimiter="\t"))
    selected = []
    for lang, repos in GROUPS.items():
        for repo, prefix in repos.items():
            paths = {r["file"] for r in provenance if r["repo"] == repo and r["file"]}
            paths = [p for p in paths if p.startswith(prefix) and Path(p).suffix in EXTS[lang]
                     and source_path(p) and (DEV / repo / p).is_file()]
            paths.sort(key=lambda p: hashlib.sha256((repo + ":" + p).encode()).hexdigest())
            selected.extend((lang, repo, p) for p in paths[:MAX_PER_REPO])
    rows = []
    skipped = []
    for lang, repo, relpath in selected:
        try:
            comment, code = (py_counts if lang == "python" else js_counts)(DEV / repo / relpath)
            rows.append((lang, repo, relpath, comment, code))
        except (SyntaxError, UnicodeError, tokenize.TokenError) as exc:
            skipped.append((lang, repo, relpath, type(exc).__name__))
    with (ROOT / "ratio_files.tsv").open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(("language", "repo", "file", "comment_lines", "code_lines"))
        writer.writerows(rows)
    with (ROOT / "ratio_skipped.tsv").open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(("language", "repo", "file", "reason"))
        writer.writerows(skipped)
    ledger_path = ROOT / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    for lang in GROUPS:
        sample = [r for r in rows if r[0] == lang]
        stats = {"files": len(sample), "comment_lines": sum(r[3] for r in sample),
                 "code_lines": sum(r[4] for r in sample)}
        stats["comment_to_code"] = round(stats["comment_lines"] / stats["code_lines"], 6)
        for key, value in stats.items():
            ledger["entries"]["ratio.%s.%s" % (lang, key)] = {
                "value": value,
                "source": "ratio_files.tsv",
                "method": "SHA256-ranked up to 60 current, non-test files per canonical repo from provenance.tsv; "
                          "line belongs to comment/code if it contains that token; mixed lines count in both. "
                          "Python: tokenize, docstrings counted as code. TS/JS: quote-aware lexical scan "
                          "(regex literals and template interpolation may be misclassified). "
                          "Ratio=comment_lines/code_lines, rounded to 6 decimals.",
                "tokenizer": "not applicable",
            }
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=1) + "\n")
    lines = ["# Python and TS/JS comment-to-code sample", "",
             "Inputs: provenance.tsv; canonical code-indexer and claude-pace-maker for Python, "
             "tdd-guard and claude-server for TS/JS. Paths must exist at HEAD. "
             "Test/fixture/build paths are excluded. Up to 60 files per repo are selected by SHA256(repo:path).",
             "A line with both code and comment counts once in each column. Blank lines count in neither. "
             "Python docstrings count as code; TS/JS scanning handles quoted strings and block comments "
             "but may misclassify regex literals or template interpolation. Skips are in ratio_skipped.tsv.", "",
             "| Language | Files | Comment lines | Code lines | Ratio |", "|---|---:|---:|---:|---:|"]
    for lang in GROUPS:
        values = {k: ledger["entries"]["ratio.%s.%s" % (lang, k)]["value"]
                  for k in ("files", "comment_lines", "code_lines", "comment_to_code")}
        lines.append("| %s | %s | %s | %s | %s |" % (lang, values["files"], values["comment_lines"],
                     values["code_lines"], values["comment_to_code"]))
    (ROOT / "ratios.md").write_text("\n".join(lines) + "\n")
    print("Measured %d files; skipped %d" % (len(rows), len(skipped)))


if __name__ == "__main__":
    main()
