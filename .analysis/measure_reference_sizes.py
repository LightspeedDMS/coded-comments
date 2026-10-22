"""Record token and line sizes of every reference/ file in the ledger (throwaway tooling)."""

import json
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
ENCODINGS = ("o200k_base", "cl100k_base")
SUFFIXES = (".md", ".yaml", ".yml")
METHOD = "len(tiktoken.get_encoding(name).encode(file text)) of the file as it exists in reference/ (proxy for Claude's tokenizer)."


def main():
    ledger_path = ROOT / ".analysis" / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    entries = ledger["entries"]
    for stale in [k for k in entries if k.startswith("size.reference/")]:
        del entries[stale]
    files = sorted(p for p in (ROOT / "reference").rglob("*") if p.is_file() and p.suffix in SUFFIXES)
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        entries["size.%s.lines" % rel] = {"value": len(text.splitlines()), "source": rel, "method": "line count",
                                          "tokenizer": "not applicable"}
        for enc_name in ENCODINGS:
            enc = tiktoken.get_encoding(enc_name)
            entries["size.%s.%s" % (rel, enc_name)] = {
                "value": len(enc.encode(text)), "source": rel, "method": METHOD,
                "tokenizer": "tiktoken %s %s" % (tiktoken.__version__, enc_name)}
            print(rel, enc_name, entries["size.%s.%s" % (rel, enc_name)]["value"])
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
