"""Recount original and draft compressed comments from real source excerpts."""

import json
import sys
from pathlib import Path

import tiktoken


ROOT = Path(__file__).resolve().parents[1]
DEV = Path.home() / "Dev"
ENCODINGS = ("o200k_base", "cl100k_base")


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main():
    rows = load(ROOT / "real_compression.jsonl")
    sample = {r["id"]: r for r in load(ROOT / "comment_sample.jsonl")}
    labels = {r["id"]: r for name in ("classification_A.jsonl", "classification_B.jsonl")
              for r in load(ROOT / name)}
    entries = json.loads((ROOT / "numbers.json").read_text())["entries"]
    assert len(rows) == 10 and len({r["id"] for r in rows}) == 10
    totals = {enc: [0, 0] for enc in ENCODINGS}
    for row in rows:
        item = sample[row["id"]]
        assert labels[row["id"]]["disposition"] == "valuable"
        assert (row["repo"], row["path"]) == (item["repo"], item["path"])
        source = (DEV / row["repo"] / row["path"]).read_text(errors="replace")
        assert row["original"] in source, "original not in source: " + row["id"]
        assert row["compressed"].strip() and len(row["compressed"]) < len(row["original"])
        for enc in ENCODINGS:
            tokenizer = tiktoken.get_encoding(enc)
            for field, slot in (("original", 0), ("compressed", 1)):
                count = len(tokenizer.encode(row[field]))
                ident = "tok.real.%s.%s.%s" % (row["id"], field, enc)
                assert entries[ident]["value"] == count, ident
                totals[enc][slot] += count
    for enc, (original, compressed) in totals.items():
        assert entries["tok.real.total.original.%s" % enc]["value"] == original
        assert entries["tok.real.total.compressed.%s" % enc]["value"] == compressed
        assert entries["tok.real.total.saved.%s" % enc]["value"] == original - compressed
        print("%s: original=%d compressed=%d saved=%d" % (enc, original, compressed, original - compressed))
    deleted = load(ROOT / "redundant_deletion.jsonl")
    assert entries["tok.delete.redundant.excerpts"]["value"] == len(deleted)
    assert len({(r["repo"], r["path"], r["line"]) for r in deleted}) == len(deleted)
    for row in deleted:
        assert labels[row["id"]]["disposition"] == "redundant"
        source = (DEV / row["repo"] / row["path"]).read_text(errors="replace")
        assert row["original"] in source
        if sample[row["id"]]["kind"] != "docstring":
            assert row["original"] == source.splitlines()[row["line"] - 1]
    for enc in ENCODINGS:
        total = sum(len(tiktoken.get_encoding(enc).encode(r["original"])) for r in deleted)
        assert entries["tok.delete.redundant.%s" % enc]["value"] == total
    print("redundant full-line excerpts=%d, ledger token sums match" % len(deleted))


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, FileNotFoundError) as exc:
        print("FAIL: %s: %s" % (type(exc).__name__, exc))
        sys.exit(1)
