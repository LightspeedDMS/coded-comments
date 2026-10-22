"""Token cost of clause separators on the 10 real compressed drafts (throwaway tooling)."""

import json
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parent
ENCODINGS = ("o200k_base", "cl100k_base")
SEPARATORS = {"semi": ";", "semi_space": "; ", "space_semi_space": " ; ", "comma": ",", "space_pipe_space": " | ",
              "pipe": "|", "space_slash_space": " / "}
METHOD = ("Clauses of the 10 drafts in real_compression.jsonl (text after 'marker tag', split on ';') re-joined with "
          "each separator; token total over the 10 joined clause lists. Draft markers/tags excluded.")


def main():
    drafts = [json.loads(l)["compressed"] for l in (ROOT / "real_compression.jsonl").read_text().splitlines() if l]
    clauses = [[c.strip() for c in d.split(" ", 2)[2].split(";")] for d in drafts]
    ledger_path = ROOT / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    entries = ledger["entries"]
    entries["sep.clauses"] = {"value": sum(len(c) for c in clauses), "source": "real_compression.jsonl",
                              "method": METHOD, "tokenizer": "not applicable"}
    for enc_name in ENCODINGS:
        enc = tiktoken.get_encoding(enc_name)
        for name, sep in SEPARATORS.items():
            total = sum(len(enc.encode(sep.join(c))) for c in clauses)
            entries["sep.total.%s.%s" % (name, enc_name)] = {
                "value": total, "source": "real_compression.jsonl", "method": METHOD,
                "tokenizer": "tiktoken %s %s" % (tiktoken.__version__, enc_name)}
            print(enc_name, name, total)
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
