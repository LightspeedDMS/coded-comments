"""Independently recount every candidate with both proxy tokenizers."""

import json
import sys
from pathlib import Path

import tiktoken


ROOT = Path(__file__).resolve().parents[1]
ENCODINGS = ("o200k_base", "cl100k_base")


def main():
    candidates = json.loads((ROOT / "token_candidates.json").read_text())
    entries = json.loads((ROOT / "numbers.json").read_text())["entries"]
    assert len(candidates) >= 30
    ids = {c["id"] for c in candidates}
    assert len(ids) == len(candidates), "duplicate candidate id"
    assert {"marker", "tag", "line"} <= {c["group"] for c in candidates}
    assert any("§" in c["text"] for c in candidates)
    assert any(c["text"].startswith("--@") for c in candidates)
    assert any(c["text"].startswith("/*@") for c in candidates)
    for c in candidates:
        assert c["text"] and c["host"]
        for enc_name in ENCODINGS:
            ident = "tok.cand.%s.%s" % (c["id"], enc_name)
            entry = entries[ident]
            expected = len(tiktoken.get_encoding(enc_name).encode(c["text"]))
            assert entry["value"] == expected, ident
            assert entry["source"] == "token_candidates.json:" + c["id"]
            assert enc_name in entry["tokenizer"] and tiktoken.__version__ in entry["tokenizer"]
    print("candidate tokens OK: %d candidates x %d encodings" % (len(candidates), len(ENCODINGS)))


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, FileNotFoundError, KeyError) as exc:
        print("FAIL: %s: %s" % (type(exc).__name__, exc))
        sys.exit(1)
