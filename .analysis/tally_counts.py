"""Write classification tallies and test-excluded ratios into numbers.json (analysis tooling only)."""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from testpaths import is_test_path

ROOT = Path(__file__).resolve().parent
LABEL_METHOD = ("Count of primary_category/disposition over classification_A.jsonl + classification_B.jsonl "
                "(72 records, frozen sample); records are single lines labeled by their enclosing comment.")
RATIO_METHOD = ("Same files as the original ratio entry minus paths matching testpaths.is_test_path; "
                "the frozen per-repo cap of 60 files is NOT refilled, so file counts shrink.")


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def put(entries, ident, value, source, method):
    entries[ident] = {"value": value, "source": source, "method": method, "tokenizer": "not applicable"}


def main():
    ledger_path = ROOT / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    entries = ledger["entries"]
    sample = {s["id"]: s for s in load(ROOT / "comment_sample.jsonl")}
    labels = load(ROOT / "classification_A.jsonl") + load(ROOT / "classification_B.jsonl")
    src = "classification_A.jsonl+classification_B.jsonl"
    cats, disps, tests = Counter(), Counter(), 0
    by_stratum = defaultdict(Counter)
    for lab in labels:
        cats[lab["primary_category"]] += 1
        disps[lab["disposition"]] += 1
        by_stratum[sample[lab["id"]]["stratum"]][lab["disposition"]] += 1
        tests += is_test_path(sample[lab["id"]]["path"]) or "test file" in lab["justification"].lower()
    for cat, n in cats.items():
        put(entries, "cat.all.%s" % cat, n, src, LABEL_METHOD)
    for disp, n in disps.items():
        put(entries, "disp.all.%s" % disp, n, src, LABEL_METHOD)
    for stratum, counter in by_stratum.items():
        for disp, n in counter.items():
            put(entries, "disp.%s.%s" % (stratum, disp), n, src, LABEL_METHOD)
    put(entries, "cat.all.total", len(labels), src, LABEL_METHOD)
    put(entries, "cat.all.extraction_false_positive", cats["unclear"], src,
        LABEL_METHOD + " 'unclear' records were all labeled extraction false positives (not comments).")
    put(entries, "cat.substantive.total", len(labels) - cats["unclear"], src, LABEL_METHOD)
    put(entries, "sample.test_file_records", tests, "comment_sample.jsonl+classification_A.jsonl+classification_B.jsonl",
        "Sample records whose path matches testpaths.is_test_path or whose justification identifies an inline test.")
    totals = defaultdict(Counter)
    for name in ("ratio_files.tsv", "ratio_files_other.tsv"):
        with (ROOT / name).open(newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                lang = row["language"]
                if is_test_path(row["file"]):
                    totals[lang]["test_files"] += 1
                    continue
                totals[lang]["files"] += 1
                totals[lang]["comment_lines"] += int(row["comment_lines"])
                totals[lang]["code_lines"] += int(row["code_lines"])
    for lang, t in totals.items():
        for field in ("files", "comment_lines", "code_lines", "test_files"):
            put(entries, "ratio.%s.excl_tests.%s" % (lang, field), t[field], "ratio_files*.tsv", RATIO_METHOD)
        if t["code_lines"]:
            put(entries, "ratio.%s.excl_tests.comment_to_code" % lang,
                round(t["comment_lines"] / t["code_lines"], 6), "ratio_files*.tsv", RATIO_METHOD)
        original = entries.get("ratio.%s.comment_to_code" % lang)
        if original is not None:
            original["includes_test_files"] = t["test_files"]
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=1) + "\n")
    print("categories", dict(cats), "dispositions", dict(disps), "test-file records", tests)


if __name__ == "__main__":
    main()
