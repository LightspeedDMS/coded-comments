"""Before/after token counts for the HOW slice pairs, final grammar (throwaway tooling)."""

import json
import sys
from pathlib import Path

import tiktoken

from grammar_check import valid

ROOT = Path(__file__).resolve().parent
ENCODINGS = ("o200k_base", "cl100k_base")
ORIGINAL_FIELD = {"real_compression.jsonl": "original", "doc_sample.jsonl": "span"}
METHOD = ("Original = full enclosing comment text from the named record; after = lines kept verbatim (pragma, "
          "shebang) plus coded lines in the final grammar. Each coded line is validated by grammar_check.valid. "
          "Information beyond the coded facts (history, narration, verification notes) is deliberately dropped.")


def load_original(source, ident):
    for line in (ROOT / source).read_text().splitlines():
        rec = json.loads(line)
        if rec["id"] == ident:
            return rec[ORIGINAL_FIELD[source]]
    raise KeyError("%s not in %s" % (ident, source))


def main():
    pairs = json.loads((ROOT / "how_pairs.json").read_text())
    ledger_path = ROOT / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    entries = ledger["entries"]
    for stale in [k for k in entries if k.startswith("pair.")]:
        del entries[stale]
    bad = [line for p in pairs for line in p["coded"] if not valid(line)]
    for line in bad:
        print("INVALID coded line:", line)
    if bad:
        sys.exit(1)
    totals = {enc: [0, 0] for enc in ENCODINGS}
    for p in pairs:
        original = p.get("original_text") or load_original(p["source"], p["id"])
        after = "\n".join(p["keep"] + p["coded"])
        for enc_name in ENCODINGS:
            enc = tiktoken.get_encoding(enc_name)
            o, a = len(enc.encode(original)), len(enc.encode(after))
            totals[enc_name][0] += o
            totals[enc_name][1] += a
            label = "tiktoken %s %s" % (tiktoken.__version__, enc_name)
            for kind, value in (("orig", o), ("after", a)):
                entries["pair.%s.%s.%s" % (p["tag"], kind, enc_name)] = {
                    "value": value, "source": "%s:%s" % (p["source"], p["id"]), "method": METHOD, "tokenizer": label}
            print(enc_name, p["tag"], o, "->", a)
    for enc_name, (o, a) in totals.items():
        for kind, value in (("orig", o), ("after", a)):
            entries["pair.total.%s.%s" % (kind, enc_name)] = {
                "value": value, "source": "how_pairs.json", "method": METHOD,
                "tokenizer": "tiktoken %s %s" % (tiktoken.__version__, enc_name)}
        print(enc_name, "TOTAL", o, "->", a)
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
