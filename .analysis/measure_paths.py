"""Measure the load paths of reference/ against the Amendment 6 token targets (throwaway tooling)."""

import json
import re
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "reference"
ENC = tiktoken.get_encoding("o200k_base")
HOST_ALLOWANCE = 150
TARGETS = {"writer": 2000, "reviewer": 3500, "entry": 150, "host": 150}
WRITER = ("what.md", "how.md")
REVIEWER = ("reviewer.md", "what.md", "rules/core.yaml", "grammar.md", "exemptions.md")
METHOD = "o200k tokens (tiktoken proxy) of the files on the path plus a 150-token host-file allowance."


def read(rel):
    return (REF / rel).read_text(encoding="utf-8")


def main():
    files = sorted(p.relative_to(REF).as_posix() for p in REF.rglob("*") if p.is_file())
    sizes = {rel: len(ENC.encode(read(rel))) for rel in files}
    citations = sum(len(re.findall(r"\[m:", read(rel))) for rel in files)
    writer = sum(sizes[r] for r in WRITER) + HOST_ALLOWANCE
    reviewer = sum(sizes[r] for r in REVIEWER) + HOST_ALLOWANCE
    ledger_path = ROOT / ".analysis" / "numbers.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entries = ledger["entries"]
    for stale in [k for k in entries if k.startswith("path.")]:
        del entries[stale]
    for ident, value in (("path.writer.o200k", writer), ("path.reviewer.o200k", reviewer),
                         ("path.total.o200k", sum(sizes.values())), ("path.citations_in_reference", citations)):
        entries[ident] = {"value": value, "source": "reference/", "method": METHOD,
                          "tokenizer": "tiktoken %s o200k_base" % tiktoken.__version__}
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(sizes)
    print("writer path %d (target %d), reviewer path %d (target %d), tree %d, [m: keys in reference/: %d" % (
        writer, TARGETS["writer"], reviewer, TARGETS["reviewer"], sum(sizes.values()), citations))


if __name__ == "__main__":
    main()
