"""Step 8 check: syntax scanner behaves on fixtures; remaining-language ledger matches the TSV."""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LANGS = {"shell", "go", "rust", "csharp", "java", "c", "cpp", "pascal", "sql"}
MIN_FILES = 10

FIXTURES = [
    ("shell", "#!/bin/sh\n# note\necho $# # trailing\nx=\"a # b\"\n", (2, 2)),
    ("rust", "let a: &'static str = \"x\"; // c\n/* b1\nb2 */\n", (3, 1)),
    ("sql", "SELECT '--not'; -- real\n/* blk */\nSELECT 1\n", (2, 2)),
    ("pascal", "{ a\nb }\nx := 1; (* c *)\n// d\n", (4, 1)),
    ("c", "int a; /* x */ int b;\n// y\n\n", (2, 1)),
    ("go", "s := `a // b\nc`\n// z\n", (1, 2)),
]


def main() -> None:
    from scanner import count_lines

    for lang, text, want in FIXTURES:
        got = count_lines(text, lang)
        assert got == want, "scanner %s: got %s want %s" % (lang, got, want)
    ledger = json.loads((ROOT / "numbers.json").read_text())
    entries = ledger["entries"]
    with (ROOT / "ratio_files_other.tsv").open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    totals = defaultdict(lambda: {"files": 0, "comment_lines": 0, "code_lines": 0})
    for row in rows:
        for field in ("comment_lines", "code_lines"):
            totals[row["language"]][field] += int(row[field])
        totals[row["language"]]["files"] += 1
    assert set(totals) <= LANGS
    for lang in LANGS:
        stats = totals[lang]
        for field, value in stats.items():
            ident = "ratio.%s.%s" % (lang, field)
            assert entries[ident]["value"] == value, ident
            assert entries[ident]["method"] and entries[ident]["source"] == "ratio_files_other.tsv"
        if stats["code_lines"]:
            ident = "ratio.%s.comment_to_code" % lang
            assert entries[ident]["value"] == round(stats["comment_lines"] / stats["code_lines"], 6), ident
        if stats["files"] < MIN_FILES:
            assert lang in ledger["corpus_gaps"], lang + " is thin but not listed in corpus_gaps"
        print("%s: %s" % (lang, dict(stats)))
    assert "sql_dialects" in ledger["corpus_gaps"], "SQL dialect gap not recorded"
    print("remaining-language ratios OK")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, ImportError, FileNotFoundError, KeyError) as exc:
        print("FAIL: %s: %s" % (type(exc).__name__, exc))
        sys.exit(1)
