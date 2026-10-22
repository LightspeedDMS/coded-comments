"""Step 12 check: ledger category/disposition counts and test-excluded ratios match independent recounts."""

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PATH_FIXTURES = [
    ("pkg/storage_test.go", True), ("rust/src/graph/code_graph_tests.rs", True),
    ("rust/src/bind/resolve_tests_family.rs", True), ("src/FooTest.java", True),
    ("src/Svc/JobTests.cs", True), ("src/test_x.py", True), ("tests/unit/a.py", True),
    ("web/src/a.test.ts", True), ("src/Latest.java", False), ("src/main.js", False),
    ("src/attest.go", False), ("pkg/storage.go", False),
]


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main():
    from testpaths import is_test_path

    for path, want in PATH_FIXTURES:
        assert is_test_path(path) == want, "is_test_path(%r) != %s" % (path, want)
    ledger = json.loads((ROOT / "numbers.json").read_text())["entries"]
    sample = {s["id"]: s for s in load(ROOT / "comment_sample.jsonl")}
    labels = load(ROOT / "classification_A.jsonl") + load(ROOT / "classification_B.jsonl")
    assert len(labels) == len(sample) == 72
    cats, disps = Counter(), Counter()
    by_stratum = defaultdict(Counter)
    tests = 0
    for lab in labels:
        cats[lab["primary_category"]] += 1
        disps[lab["disposition"]] += 1
        by_stratum[sample[lab["id"]]["stratum"]][lab["disposition"]] += 1
        tests += is_test_path(sample[lab["id"]]["path"]) or "test file" in lab["justification"].lower()
    for cat, n in cats.items():
        assert ledger["cat.all.%s" % cat]["value"] == n, cat
    for disp, n in disps.items():
        assert ledger["disp.all.%s" % disp]["value"] == n, disp
    assert ledger["cat.all.total"]["value"] == 72
    false_pos = cats["unclear"]
    assert ledger["cat.all.extraction_false_positive"]["value"] == false_pos
    assert ledger["cat.substantive.total"]["value"] == 72 - false_pos
    for stratum, counter in by_stratum.items():
        for disp, n in counter.items():
            assert ledger["disp.%s.%s" % (stratum, disp)]["value"] == n, (stratum, disp)
    assert ledger["sample.test_file_records"]["value"] == tests
    totals = defaultdict(lambda: Counter())
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
            ident = "ratio.%s.excl_tests.%s" % (lang, field)
            assert ledger[ident]["value"] == t[field], "%s: %s vs %s" % (ident, ledger[ident]["value"], t[field])
        if t["code_lines"]:
            ident = "ratio.%s.excl_tests.comment_to_code" % lang
            assert ledger[ident]["value"] == round(t["comment_lines"] / t["code_lines"], 6), ident
        print("%s excl tests: %s" % (lang, dict(t)))
    print("categories %s dispositions %s test-file records %d" % (dict(cats), dict(disps), tests))


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, ImportError, KeyError, FileNotFoundError) as exc:
        print("FAIL: %s: %s" % (type(exc).__name__, exc))
        sys.exit(1)
