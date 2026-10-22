"""Measure the load paths of reference/ against the Amendment 6 token targets (throwaway tooling)."""

import json
import re
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "reference"
ENCODINGS = (("o200k", "o200k_base"), ("cl100k", "cl100k_base"))
HOST_ALLOWANCE = 150
TARGETS = {"writer": 2000, "reviewer": 3500, "entry": 220, "host": 150}
WRITER = ("what.md", "how.md")
REVIEWER = ("reviewer.md", "what.md", "rules/core.yaml", "grammar.md", "exemptions.md")
ALLOWANCE_METHOD = "tokens of the files on the path plus a 150-token host-file allowance"
LARGEST_METHOD = "tokens of the files on the path plus the largest measured host file"


def read(rel):
    return (REF / rel).read_text(encoding="utf-8")


def measure(short, name, files):
    """Return {ledger key: (value, method)} for one encoding, and print the same numbers."""
    encoder = tiktoken.get_encoding(name)
    sizes = {rel: len(encoder.encode(read(rel))) for rel in files}
    hosts = {rel: n for rel, n in sizes.items() if rel.startswith("hosts/")}
    largest = max(hosts, key=hosts.get)
    writer_base, reviewer_base = sum(sizes[r] for r in WRITER), sum(sizes[r] for r in REVIEWER)
    results = {
        "path.writer.%s" % short: (writer_base + HOST_ALLOWANCE, ALLOWANCE_METHOD),
        "path.reviewer.%s" % short: (reviewer_base + HOST_ALLOWANCE, ALLOWANCE_METHOD),
        "path.writer_largest_host.%s" % short: (writer_base + hosts[largest], LARGEST_METHOD),
        "path.reviewer_largest_host.%s" % short: (reviewer_base + hosts[largest], LARGEST_METHOD),
        "path.entry.%s" % short: (sizes["ENTRY.md"], "tokens of reference/ENTRY.md alone"),
        "path.total.%s" % short: (sum(sizes.values()), "tokens of every file in reference/"),
    }
    print(name, sizes)
    print("%s: writer %d (target %d), reviewer %d (target %d), entry %d (target %d), largest host %s %d, tree %d" % (
        name, results["path.writer.%s" % short][0], TARGETS["writer"], results["path.reviewer.%s" % short][0],
        TARGETS["reviewer"], sizes["ENTRY.md"], TARGETS["entry"], largest, hosts[largest], sum(sizes.values())))
    return results


def main():
    files = sorted(p.relative_to(REF).as_posix() for p in REF.rglob("*") if p.is_file())
    ledger_path = ROOT / ".analysis" / "numbers.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entries = ledger["entries"]
    for stale in [k for k in entries if k.startswith("path.")]:
        del entries[stale]
    for short, name in ENCODINGS:
        for ident, (value, method) in measure(short, name, files).items():
            entries[ident] = {"value": value, "source": "reference/", "method": "%s %s" % (name, method),
                              "tokenizer": "tiktoken %s %s" % (tiktoken.__version__, name)}
    citations = sum(len(re.findall(r"\[m:", read(rel))) for rel in files)
    entries["path.citations_in_reference"] = {"value": citations, "source": "reference/",
                                              "method": "count of '[m:' occurrences in reference/"}
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("[m: keys in reference/: %d" % citations)


if __name__ == "__main__":
    main()
