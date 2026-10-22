"""Check a classification batch (argv[1] = A or B) against the frozen sample and the rubric table."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCHES = ("A", "B")
RUBRIC_ROWS = 18
MIN_JUSTIFICATION = 15
MAX_JUSTIFICATION = 300


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main(batch):
    if batch not in BATCHES:
        raise ValueError("batch must be one of %s" % (BATCHES,))
    rubric = dict(re.findall(r"^\| `(\w+)` \| (\w+) \|", (ROOT / "category_rubric.md").read_text(), re.M))
    assert len(rubric) == RUBRIC_ROWS, "rubric table parse: %d rows" % len(rubric)
    sample = [r for r in load(ROOT / "comment_sample.jsonl") if r["batch"] == batch]
    rows = load(ROOT / ("classification_%s.jsonl" % batch))
    assert [r["id"] for r in rows] == [s["id"] for s in sample], "ids differ from sample batch " + batch
    for row in rows:
        cat = row["primary_category"]
        assert cat in rubric, "unknown category %s" % cat
        assert row["disposition"] == rubric[cat], "%s: %s is %s in rubric" % (row["id"], cat, rubric[cat])
        just = row["justification"]
        assert MIN_JUSTIFICATION <= len(just) <= MAX_JUSTIFICATION, "%s: justification length %d" % (
            row["id"], len(just))
        if cat == "public_api_doc":
            assert "public" in just.lower(), "%s: exempt label must state visibility" % row["id"]
    print("batch %s: %d records classified, categories and dispositions match rubric" % (batch, len(rows)))


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except (AssertionError, FileNotFoundError, KeyError, IndexError, ValueError) as exc:
        print("FAIL: %s: %s" % (type(exc).__name__, exc))
        sys.exit(1)
