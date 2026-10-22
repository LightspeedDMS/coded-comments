"""Recount doc-comment fixtures and frozen Python/JS volume (analysis only)."""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from doc_volume_py_js import python_docs, js_docs, measure_rows  # noqa: E402


def main():
    py = '''"""Public module."""
__all__ = ["_kept"]
def _kept():
    """Exported despite underscore."""
def _hidden():
    """Private."""
class Widget:
    """Public class."""
    def act(self):
        """Public method."""
    def _internal(self):
        """Private method."""
'''
    docs = python_docs(py)
    assert [(d[1], d[2]) for d in docs] == [
        (1, "public"), (4, "public"), (6, "private"),
        (8, "public"), (10, "public"), (12, "private")]
    js = '''/** Exported API. */
export function fetch() {}
/** Internal helper. */
function parse() {}
/** Not an API. */
const value = 1;
'''
    assert [(d[1], d[2]) for d in js_docs(js)] == [(1, "public"), (3, "private"), (5, "private")]
    rows = list(csv.DictReader((ROOT / "ratio_files.tsv").open(), delimiter="\t"))
    measured = measure_rows(rows)
    ledger = json.loads((ROOT / "numbers.json").read_text())["entries"]
    for lang, result in measured.items():
        for key, value in result.items():
            ident = "doc.%s.%s" % (lang, key)
            assert ledger[ident]["value"] == value, "%s: %r != %r" % (ident, ledger[ident]["value"], value)
        assert result["public_lines"] + result["private_lines"] == result["doc_lines"]
        assert result["inclusive_ratio"] >= ledger["ratio.%s.comment_to_code" % lang]["value"]
    print("doc volume Python/TS-JS OK: %s" % {k: v["inclusive_ratio"] for k, v in measured.items()})


if __name__ == "__main__":
    main()
