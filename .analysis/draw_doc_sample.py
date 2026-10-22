"""Draw a seeded doc-comment sample (language x lexical visibility) for classification (throwaway tooling)."""

import csv
import hashlib
import json
import os
from pathlib import Path

from doc_volume_other import DOC_FUNCS
from doc_volume_py_js import js_docs, python_docs
from testpaths import is_test_path

ROOT = Path(__file__).resolve().parent
DEV = Path(os.environ.get("CC_CORPUS_DIR", str(Path.home() / "Dev")))
SEED = "docsample-v1"
PER_CELL = 3
MAX_SPAN_CHARS = 700
CONTEXT_AFTER = 2
LANGS = ("python", "typescript_js", "go", "rust", "csharp", "java")
# every extractor is called as f(text, path); DOC_FUNCS entries already accept (text, path)
EXTRACT = {"python": lambda t, p: python_docs(t), "typescript_js": lambda t, p: js_docs(t)}
EXTRACT.update({lang: DOC_FUNCS[lang] for lang in ("go", "rust", "csharp", "java")})


def candidates():
    rows = []
    for name in ("ratio_files.tsv", "ratio_files_other.tsv"):
        with (ROOT / name).open(newline="") as handle:
            rows += [r for r in csv.DictReader(handle, delimiter="\t") if r["language"] in LANGS]
    out = []
    for row in rows:
        if is_test_path(row["file"]):
            continue
        text = (DEV / row["repo"] / row["file"]).read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for first, last, vis in EXTRACT[row["language"]](text, row["file"]):
            ident = hashlib.sha256(("%s:%s:%d" % (row["repo"], row["file"], first)).encode()).hexdigest()[:12]
            span = "\n".join(lines[first - 1:last])[:MAX_SPAN_CHARS]
            before = "\n".join(lines[max(0, first - 3):first - 1]) if row["language"] == "python" else ""
            after = "\n".join(lines[last:last + CONTEXT_AFTER])
            out.append({"id": ident, "lang": row["language"], "repo": row["repo"], "path": row["file"],
                        "first": first, "last": last, "lexvis": vis, "span": span, "before": before, "after": after})
    return out


def main():
    pool = candidates()
    sample = []
    for lang in LANGS:
        for vis in ("public", "private"):
            cell = [c for c in pool if c["lang"] == lang and c["lexvis"] == vis]
            cell.sort(key=lambda c: hashlib.sha256((SEED + c["id"]).encode()).hexdigest())
            by_repo, picked = {}, []
            for c in cell:  # round-robin across repos so one repo cannot fill a cell
                by_repo.setdefault(c["repo"], []).append(c)
            while len(picked) < PER_CELL and any(by_repo.values()):
                for repo in sorted(by_repo):
                    if by_repo[repo] and len(picked) < PER_CELL:
                        picked.append(by_repo[repo].pop(0))
            sample += picked
    (ROOT / "doc_sample.jsonl").write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in sample))
    print("pool=%d sample=%d" % (len(pool), len(sample)))


if __name__ == "__main__":
    main()
