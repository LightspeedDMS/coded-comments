"""Measured inputs for budgets.md (throwaway tooling).

The ceiling is coded lines per code line, the same definition as the baseline ratios (comment lines / code lines),
so the two are directly comparable and no conversion is applied.
"""

import json
import statistics
from pathlib import Path

import tiktoken

from measure_how_pairs import load_original

ROOT = Path(__file__).resolve().parent
CODED_TO_CODE_CEILING = 0.10
BASELINES = {
    "python": "doc.python.inclusive_ratio", "typescript_js": "ratio.typescript_js.comment_to_code",
    "shell": "ratio.shell.comment_to_code", "go": "ratio.go.excl_tests.comment_to_code",
    "rust": "ratio.rust.excl_tests.comment_to_code", "csharp": "ratio.csharp.comment_to_code",
    "java": "ratio.java.comment_to_code", "sql": "ratio.sql.comment_to_code",
}
SRC = "how_pairs.json coded lines"
METHOD = "Computed over the coded lines of the 10 real pairs in how_pairs.json (tiktoken o200k proxy for tokens)."


def put(entries, ident, value, source, method, tokenizer="not applicable"):
    entries[ident] = {"value": value, "source": source, "method": method, "tokenizer": tokenizer}


def add_projection(entries, pairs, lines):
    orig_lines = sum(len((p.get("original_text") or load_original(p["source"], p["id"])).splitlines()) for p in pairs)
    total = entries["cat.all.total"]["value"]
    if orig_lines == 0 or total == 0 or not BASELINES:
        raise ValueError("projection inputs are empty: orig_lines=%d total=%d" % (orig_lines, total))
    keep = round(len(lines) / orig_lines, 3)
    valuable_share = entries["disp.all.valuable"]["value"] / total
    put(entries, "budget.pairs.orig_lines", orig_lines, SRC, "Line count of the original comment of each of the 10 pairs.")
    put(entries, "budget.pairs.coded_lines", len(lines), SRC, "Total number of coded lines over the 10 pairs.")
    put(entries, "budget.pairs.line_keep_ratio", keep, SRC, "coded lines / original lines over the 10 pairs.")
    projected = {}
    for lang, ident in BASELINES.items():
        projected[lang] = round(entries[ident]["value"] * valuable_share * keep, 3)
        put(entries, "budget.projected.%s" % lang, projected[lang], ident,
            "PROJECTION, not a measurement: baseline x (24/72 valuable share) x line_keep_ratio; small hand-picked pairs.")
    put(entries, "budget.projected.max", max(projected.values()), "budget.projected.*", "Maximum of the per-host projections.")


def main():
    ledger_path = ROOT / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    entries = ledger["entries"]
    for stale in [k for k in entries if k.startswith("budget.")]:
        del entries[stale]
    pairs = json.loads((ROOT / "how_pairs.json").read_text())
    lines = [line for p in pairs for line in p["coded"]]
    enc = tiktoken.get_encoding("o200k_base")
    chars = [len(line) for line in lines]
    toks = [len(enc.encode(line)) for line in lines]
    label = "tiktoken %s o200k_base" % tiktoken.__version__
    put(entries, "budget.coded.lines", len(lines), SRC, METHOD)
    put(entries, "budget.coded.chars_mean", round(statistics.mean(chars), 1), SRC, METHOD)
    put(entries, "budget.coded.chars_max", max(chars), SRC, METHOD)
    put(entries, "budget.coded.tokens_mean", round(statistics.mean(toks), 1), SRC, METHOD, label)
    put(entries, "budget.coded.tokens_max", max(toks), SRC, METHOD, label)
    put(entries, "budget.coded.run_max", max(len(p["coded"]) for p in pairs), SRC, METHOD)
    for lang, ident in BASELINES.items():
        base = entries[ident]["value"]
        cut = round(100 * (base - CODED_TO_CODE_CEILING) / base, 1)
        put(entries, "budget.cut_to_ceiling.%s" % lang, cut, ident,
            "Percent a coded-to-code ceiling of %.2f lowers the measured baseline %s. A ceiling, not a prediction." % (
                CODED_TO_CODE_CEILING, ident))
    add_projection(entries, pairs, lines)
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n")
    print({k: v["value"] for k, v in entries.items() if k.startswith("budget.")})


if __name__ == "__main__":
    main()
