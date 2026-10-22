"""Step 14 check: pace-maker intel glyph line vs ASCII notations, recounted from harvested real lines."""

import json
import re
import sys
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
ENCODINGS = ("o200k_base", "cl100k_base")
LINE = re.compile(r"^§ △([0-9.]+) ◎([a-z]+) ■([a-z]+) ◇([0-9.]+) ↻([0-9]+)$")
MIN_LINES = 200
RENDER = {
    "glyph": "§ △{a} ◎{s} ■{t} ◇{c} ↻{n}",
    "words": "intel conf={a} scope={s} type={t} cert={c} iter={n}",
    "short": "i a={a} s={s} t={t} c={c} n={n}",
    "positional": "i {a} {s} {t} {c} {n}",
    "pipe": "i|{a}|{s}|{t}|{c}|{n}",
}


def main():
    lines = (ROOT / "intel_lines.txt").read_text().splitlines()
    assert len(lines) >= MIN_LINES, "only %d intel lines" % len(lines)
    assert len(set(lines)) == len(lines), "duplicate lines"
    fields = []
    for line in lines:
        m = LINE.match(line)
        assert m, "not an intel line: %r" % line
        fields.append(dict(zip("astcn", m.groups())))
    ledger = json.loads((ROOT / "numbers.json").read_text())["entries"]
    assert ledger["intel.lines"]["value"] == len(lines)
    totals = {}
    for enc_name in ENCODINGS:
        enc = tiktoken.get_encoding(enc_name)
        for variant, template in RENDER.items():
            total = sum(len(enc.encode(template.format(**f))) for f in fields)
            ident = "intel.total.%s.%s" % (variant, enc_name)
            assert ledger[ident]["value"] == total, "%s: ledger %s recount %s" % (ident, ledger[ident]["value"], total)
            totals[(variant, enc_name)] = total
        assert totals[("glyph", enc_name)] == sum(len(enc.encode(l)) for l in lines), "glyph render != raw line"
    adopt = all(totals[("glyph", e)] <= totals[(v, e)] for e in ENCODINGS for v in RENDER if v != "glyph")
    verdict = ledger["intel.verdict"]["value"]
    assert verdict == ("adopt" if adopt else "reject"), "verdict %s contradicts totals" % verdict
    for enc_name in ENCODINGS:
        print(enc_name, {v: totals[(v, enc_name)] for v in RENDER})
    print("intel glyph check OK: %d real lines, verdict=%s" % (len(lines), verdict))


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, FileNotFoundError, KeyError) as exc:
        print("FAIL: %s: %s" % (type(exc).__name__, exc))
        sys.exit(1)
