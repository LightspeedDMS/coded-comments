"""Freeze a seeded, repo-balanced sample from current Claude-coauthored files."""

import ast
import csv
import hashlib
import io
import json
import re
import tokenize
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEV = Path.home() / "Dev"
SEED = "coded-comments-2026-10-13-v1"
STRATA = ("python", "python_docstring", "typescript_js", "shell", "go", "rust", "csharp", "java", "sql")
PER_STRATUM = 8
POOL_PER_REPO = 30
PRAGMA = re.compile(r"^(?:noqa|type:\s*ignore|pylint:|fmt:|pragma:|eslint-|ts-ignore|nolint|coding[:=]|-\*-)", re.I)


def add(out, stratum, repo, path, line, kind, text):
    text = " ".join(text.split())[:500]
    if len(text) < 8 or PRAGMA.match(text):
        return
    key = "%s\0%s\0%s\0%d\0%s\0%s" % (stratum, repo, path, line, kind, text)
    out.append({"id": hashlib.sha256(key.encode()).hexdigest()[:20], "stratum": stratum,
                "repo": repo, "path": path, "line": line, "kind": kind, "text": text})


def python_candidates(out, repo, relpath):
    path = DEV / repo / relpath
    data = path.read_bytes()
    try:
        for tok in tokenize.tokenize(io.BytesIO(data).readline):
            if tok.type == tokenize.COMMENT and not (tok.start[0] == 1 and tok.string.startswith("#!")):
                add(out, "python", repo, relpath, tok.start[0], "line", tok.string[1:])
    except (tokenize.TokenError, SyntaxError):
        pass
    try:
        with tokenize.open(path) as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc and node.body:
                    add(out, "python_docstring", repo, relpath, node.body[0].lineno, "docstring", doc)
    except (SyntaxError, UnicodeError, ValueError):
        pass


def mask_quotes(line):
    chars = list(line)
    quote = None
    escaped = False
    for index, ch in enumerate(line):
        if quote:
            chars[index] = " "
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
        elif ch in ("'", '"', "`"):
            quote = ch
            chars[index] = " "
    return "".join(chars)


def other_candidates(out, stratum, repo, relpath):
    text = (DEV / repo / relpath).read_text(encoding="utf-8", errors="replace")
    marker = "#" if stratum == "shell" else "--" if stratum == "sql" else "//"
    in_block = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if stratum == "shell" and lineno == 1 and line.startswith("#!"):
            continue
        if in_block:
            end = line.find("*/")
            add(out, stratum, repo, relpath, lineno, "block", line[:end] if end >= 0 else line)
            in_block = end < 0
            if in_block:
                continue
            line = line[end + 2:]
        masked = mask_quotes(line)
        starts = [(masked.find(marker), "line"), (masked.find("/*"), "block")]
        starts = [(pos, kind) for pos, kind in starts if pos >= 0]
        if not starts:
            continue
        pos, kind = min(starts)
        if kind == "line":
            add(out, stratum, repo, relpath, lineno, kind, line[pos + len(marker):])
        else:
            end = line.find("*/", pos + 2)
            add(out, stratum, repo, relpath, lineno, kind, line[pos + 2:end] if end >= 0 else line[pos + 2:])
            in_block = end < 0


def main():
    files = []
    for name in ("ratio_files.tsv", "ratio_files_other.tsv"):
        with (ROOT / name).open(newline="") as handle:
            files.extend(csv.DictReader(handle, delimiter="\t"))
    candidates = []
    for row in files:
        lang, repo, path = row["language"], row["repo"], row["file"]
        if lang == "python":
            python_candidates(candidates, repo, path)
        else:
            other_candidates(candidates, lang, repo, path)
    pool = defaultdict(list)
    for item in candidates:
        pool[(item["stratum"], item["repo"])].append(item)
    candidates = []
    for items in pool.values():
        items.sort(key=lambda x: hashlib.sha256(("pool-v1" + x["id"]).encode()).hexdigest())
        candidates.extend(items[:POOL_PER_REPO])
    candidates.sort(key=lambda x: x["id"])
    with (ROOT / "comment_candidates.jsonl").open("w") as handle:
        for item in candidates:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    by_stratum = defaultdict(lambda: defaultdict(list))
    for item in candidates:
        by_stratum[item["stratum"]][item["repo"]].append(item)
    sample = []
    for stratum in STRATA:
        buckets = by_stratum[stratum]
        for repo in buckets:
            buckets[repo].sort(key=lambda x: hashlib.sha256((SEED + x["id"]).encode()).hexdigest())
        selected = []
        while len(selected) < PER_STRATUM and any(buckets.values()):
            for repo in sorted(buckets):
                if buckets[repo] and len(selected) < PER_STRATUM:
                    selected.append(buckets[repo].pop(0))
        if len(selected) != PER_STRATUM:
            raise ValueError("too few candidates for " + stratum)
        for index, item in enumerate(selected):
            sample.append(dict(item, batch="A" if index % 2 == 0 else "B"))
    with (ROOT / "comment_sample.jsonl").open("w") as handle:
        for item in sample:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    ledger_path = ROOT / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    for name, value, source in (("sample.candidates", len(candidates), "comment_candidates.jsonl"),
                                ("sample.selected", len(sample), "comment_sample.jsonl")):
        ledger["entries"][name] = {"value": value, "source": source,
                                   "method": "count JSONL records after deterministic source-file and comment extraction",
                                   "tokenizer": "not applicable"}
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=1) + "\n")
    print("Froze %d comments from %d candidates" % (len(sample), len(candidates)))


if __name__ == "__main__":
    main()
