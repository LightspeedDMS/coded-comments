"""Tally the classified doc-comment sample into the ledger (throwaway tooling)."""

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED_ROWS = 36
SRC = "doc_sample.jsonl+doc_classification.jsonl"
METHOD = ("Seeded sample (seed docsample-v1): 3 doc spans per language x lexical visibility cell, non-test files "
          "of the frozen ratio TSVs, round-robin across repos; labeled with category_rubric.md. true_export follows "
          "Amendment 3 judged by hand from repo/path (app vs library, internal/ dirs, export keyword); 'uncertain' = "
          "library status or crate/package reachability not established. Counts of 36 records, not rates.")


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main():
    sample = load(ROOT / "doc_sample.jsonl")
    labels = load(ROOT / "doc_classification.jsonl")
    assert [s["id"] for s in sample] == [l["id"] for l in labels], "classification ids differ from doc_sample"
    assert len(labels) == EXPECTED_ROWS
    rubric = dict(re.findall(r"^\| `(\w+)` \| (\w+) \|", (ROOT / "category_rubric.md").read_text(), re.M))
    for lab in labels:
        assert rubric[lab["primary_category"]] == lab["disposition"], lab["id"]
        assert lab["disposition"] != "exempt" or lab["true_export"] == "yes", "exempt without proven export: " + lab["id"]
    by_id = {s["id"]: s for s in sample}
    counts = Counter()
    for lab in labels:
        lex = by_id[lab["id"]]["lexvis"]
        counts["total"] += 1
        counts["cat." + lab["primary_category"]] += 1
        counts["disp." + lab["disposition"]] += 1
        counts["export." + lab["true_export"]] += 1
        counts["lex.%s.export.%s" % (lex, lab["true_export"])] += 1
        counts["lex.%s.disp.%s" % (lex, lab["disposition"])] += 1
        counts["export.%s.disp.%s" % (lab["true_export"], lab["disposition"])] += 1
    ledger_path = ROOT / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    for stale in [k for k in ledger["entries"] if k.startswith("docsample.")]:
        del ledger["entries"][stale]
    for key, value in sorted(counts.items()):
        ledger["entries"]["docsample." + key] = {"value": value, "source": SRC, "method": METHOD,
                                                 "tokenizer": "not applicable"}
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n")
    for key, value in sorted(counts.items()):
        print(key, value)


if __name__ == "__main__":
    main()
