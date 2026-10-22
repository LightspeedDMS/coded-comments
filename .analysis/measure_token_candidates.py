"""Measure proposed coded-comment markers and tags with tiktoken proxies."""

import json
from pathlib import Path

import tiktoken


ROOT = Path(__file__).resolve().parent
ENCODINGS = ("o200k_base", "cl100k_base")


def main():
    candidates = json.loads((ROOT / "token_candidates.json").read_text())
    ledger_path = ROOT / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    encoders = {name: tiktoken.get_encoding(name) for name in ENCODINGS}
    lines = ["# Candidate marker and tag token costs", "",
             "Counts use tiktoken proxies, not Claude token counts. The candidate strings are exploratory; "
             "the marker and grammar are chosen after the corpus before/after measurement. "
             "Standalone tag costs may differ when a tokenizer merges them with adjacent syntax.", "",
             "| Group | Host | Candidate | o200k | cl100k |", "|---|---|---|---:|---:|"]
    for c in candidates:
        counts = {}
        for enc_name, encoder in encoders.items():
            ident = "tok.cand.%s.%s" % (c["id"], enc_name)
            count = len(encoder.encode(c["text"]))
            counts[enc_name] = count
            ledger["entries"][ident] = {
                "value": count,
                "source": "token_candidates.json:" + c["id"],
                "method": "len(tiktoken.get_encoding(name).encode(candidate.text))",
                "tokenizer": "tiktoken %s %s" % (tiktoken.__version__, enc_name),
            }
        lines.append("| %s | %s | `%s` | %d [m:tok.cand.%s.o200k_base] | %d [m:tok.cand.%s.cl100k_base] |" % (
            c["group"], c["host"], c["text"], counts["o200k_base"], c["id"],
            counts["cl100k_base"], c["id"]))
    ledger_path.write_text(json.dumps(ledger, separators=(",", ":"), ensure_ascii=False) + "\n")
    (ROOT / "token_candidates.md").write_text("\n".join(lines) + "\n")
    print("Measured %d candidates with %d tiktoken encodings" % (len(candidates), len(ENCODINGS)))


if __name__ == "__main__":
    main()
