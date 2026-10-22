"""Harvest real pace-maker intel lines and compare token cost of the glyph style vs ASCII notations."""

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parent
TRANSCRIPTS = Path(os.environ.get("CC_TRANSCRIPTS_DIR", str(Path.home() / ".claude" / "projects")))
GREP_TIMEOUT_S = int(os.environ.get("CC_GREP_TIMEOUT_S", "300"))
PATTERN = r"§ △[0-9.]+ ◎[a-z]+ ■[a-z]+ ◇[0-9.]+ ↻[0-9]+"
LINE = re.compile(r"^§ △([0-9.]+) ◎([a-z]+) ■([a-z]+) ◇([0-9.]+) ↻([0-9]+)$")
SEED = "intel-v1"
SAMPLE = 300
ENCODINGS = ("o200k_base", "cl100k_base")
RENDER = {
    "glyph": "§ △{a} ◎{s} ■{t} ◇{c} ↻{n}",
    "words": "intel conf={a} scope={s} type={t} cert={c} iter={n}",
    "short": "i a={a} s={s} t={t} c={c} n={n}",
    "positional": "i {a} {s} {t} {c} {n}",
    "pipe": "i|{a}|{s}|{t}|{c}|{n}",
}
METHOD = ("Distinct intel lines grep'd (read-only) from transcripts under ~/.claude/projects, "
          "SHA256(%s+line)-ranked, first %d kept in intel_lines.txt; fields re-rendered in each notation "
          "and token-counted per line, summed." % (SEED, SAMPLE))


def harvest():
    out = subprocess.run(["grep", "-rhoE", "--include=*.jsonl", PATTERN, str(TRANSCRIPTS)],
                         capture_output=True, text=True, timeout=GREP_TIMEOUT_S)
    if out.returncode not in (0, 1):
        raise RuntimeError("grep failed: rc=%d %s" % (out.returncode, out.stderr[:200]))
    found = out.stdout.splitlines()
    distinct = set(found)
    ranked = sorted(distinct, key=lambda l: hashlib.sha256((SEED + l).encode()).hexdigest())
    return ranked[:SAMPLE], len(distinct), len(found)


def load_ledger(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise RuntimeError("cannot load ledger %s: %s" % (path, exc))


def main():
    lines, distinct, occurrences = harvest()
    if not lines:
        raise RuntimeError("no intel lines found under %s" % TRANSCRIPTS)
    (ROOT / "intel_lines.txt").write_text("\n".join(lines) + "\n")
    fields = [dict(zip("astcn", LINE.match(l).groups())) for l in lines]
    ledger_path = ROOT / "numbers.json"
    ledger = load_ledger(ledger_path)
    entries = ledger["entries"]

    def put(ident, value, tokenizer="not applicable", method=METHOD):
        entries[ident] = {"value": value, "source": "intel_lines.txt", "method": method, "tokenizer": tokenizer}

    put("intel.lines", len(lines))
    put("intel.distinct_in_transcripts", distinct)
    put("intel.occurrences_in_transcripts", occurrences)
    totals = {}
    for enc_name in ENCODINGS:
        enc = tiktoken.get_encoding(enc_name)
        label = "tiktoken %s %s" % (tiktoken.__version__, enc_name)
        for variant, template in RENDER.items():
            totals[(variant, enc_name)] = sum(len(enc.encode(template.format(**f))) for f in fields)
            put("intel.total.%s.%s" % (variant, enc_name), totals[(variant, enc_name)], label)
    adopt = all(totals[("glyph", e)] <= totals[(v, e)] for e in ENCODINGS for v in RENDER if v != "glyph")
    put("intel.verdict", "adopt" if adopt else "reject",
        method="adopt only if glyph total <= every ASCII variant total under both encodings. " + METHOD)
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n")
    for enc_name in ENCODINGS:
        print(enc_name, {v: totals[(v, enc_name)] for v in RENDER})
    print("lines=%d distinct=%d occurrences=%d verdict=%s" % (len(lines), distinct, occurrences, "adopt" if adopt else "reject"))


if __name__ == "__main__":
    main()
