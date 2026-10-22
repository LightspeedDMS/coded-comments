"""Recount Python and TS/JS ratios from the frozen per-file measurement table."""

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ledger = json.loads((ROOT / "numbers.json").read_text())["entries"]
    with (ROOT / "ratio_files.tsv").open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    totals = defaultdict(lambda: {"comment_lines": 0, "code_lines": 0, "files": 0})
    repos = defaultdict(set)
    for row in rows:
        lang = row["language"]
        repos[lang].add(row["repo"])
        totals[lang]["files"] += 1
        for field in ("comment_lines", "code_lines"):
            value = int(row[field])
            assert value >= 0
            totals[lang][field] += value
    assert set(totals) == {"python", "typescript_js"}
    assert len(repos["python"]) >= 2 and len(repos["typescript_js"]) >= 2
    for lang, stats in totals.items():
        assert stats["files"] > 0 and stats["code_lines"] > 0
        for field, value in stats.items():
            ident = "ratio.%s.%s" % (lang, field)
            assert ledger[ident]["value"] == value, ident
            assert ledger[ident]["source"] == "ratio_files.tsv"
            assert ledger[ident]["method"]
        ident = "ratio.%s.comment_to_code" % lang
        expected = round(stats["comment_lines"] / stats["code_lines"], 6)
        assert ledger[ident]["value"] == expected, ident
        print("%s: %d files, %d comment lines / %d code lines = %.6f" % (
            lang, stats["files"], stats["comment_lines"], stats["code_lines"], expected
        ))


if __name__ == "__main__":
    main()
