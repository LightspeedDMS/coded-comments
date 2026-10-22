"""Token cost of the backtick literal escape (Amendment 5; throwaway tooling)."""

import json
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parent
ENCODINGS = ("o200k_base", "cl100k_base")
# (quoted part, unquoted suffix): only the part containing operator characters is quoted, as grammar.md prescribes
ITEMS = [("Vec<u8>", ""), ("List<T>", ""), ("std::map<K,V>", ""), ("println!", ""), ("!flag", ""), ("a->b", ""),
         ("Option<&str>", ""), ("Vec<u8>", ".len()")]
LINE = "//^ inv %s<=cap"
METHOD = ("Each item counted bare and with only its operator-bearing part wrapped in backticks (suffix left outside), "
          "alone and inside the line '//^ inv X<=cap'; bare forms are NOT valid grammar (operator characters) and "
          "serve only as the cost baseline.")


def main():
    ledger_path = ROOT / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    entries = ledger["entries"]
    for enc_name in ENCODINGS:
        enc = tiktoken.get_encoding(enc_name)
        label = "tiktoken %s %s" % (tiktoken.__version__, enc_name)
        totals = {"raw": 0, "quoted": 0, "line_raw": 0, "line_quoted": 0}
        for lit, suffix in ITEMS:
            raw, quoted = lit + suffix, "`%s`%s" % (lit, suffix)
            totals["raw"] += len(enc.encode(raw))
            totals["quoted"] += len(enc.encode(quoted))
            totals["line_raw"] += len(enc.encode(LINE % raw))
            totals["line_quoted"] += len(enc.encode(LINE % quoted))
        for key, value in totals.items():
            entries["bt.total.%s.%s" % (key, enc_name)] = {"value": value, "source": "measure_backtick.py ITEMS",
                                                          "method": METHOD, "tokenizer": label}
        print(enc_name, totals, "n=%d" % len(ITEMS))
    entries["bt.literals"] = {"value": len(ITEMS), "source": "measure_backtick.py ITEMS", "method": METHOD,
                              "tokenizer": "not applicable"}
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
