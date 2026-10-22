"""Choose the single marker sigil: token overhead + corpus collisions + known collisions (analysis tooling)."""

import csv
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

import tiktoken

from measure_ratios import EXTS as PY_TS_EXTS
from measure_ratios import GROUPS as PY_TS_GROUPS
from measure_ratios_other import GROUPS as OTHER_GROUPS
from measure_ratios_other import SKIP_DIRS

ROOT = Path(__file__).resolve().parent
DEV = Path(os.environ.get("CC_CORPUS_DIR", str(Path.home() / "Dev")))
MAX_FILES_PER_LANG = 400
ENCODINGS = ("o200k_base", "cl100k_base")
OPENERS = {"hash": "#", "slash": "//", "dash": "--"}
LANG_OPENER = {"python": "hash", "shell": "hash", "typescript_js": "slash", "go": "slash", "rust": "slash",
               "csharp": "slash", "java": "slash", "c": "slash", "cpp": "slash", "pascal": "slash", "sql": "dash"}
CANDIDATES = {"at": "@", "caret": "^", "tilde": "~", "pct": "%", "dollar": "$", "bang": "!", "pipe": "|",
              "eq": "=", "plus": "+", "amp": "&", "star": "*", "gt": ">", "colon": ":", "semi": ";", "section": "§"}
BODIES = ["inv x<=y", "cpl src/a.py:f", "haz keep timeout #12"]
HOSTS = {"python": "hash", "typescript_javascript": "slash", "shell": "hash", "go": "slash", "rust": "slash",
         "csharp": "slash", "java": "slash", "pascal": "slash", "c": "slash", "cpp": "slash",
         "plsql": "dash", "postgresql": "dash", "tsql": "dash", "sqlite": "dash"}
RULE = ("sigil = argmin over candidates with zero line-start collisions in the scanned corpus and no entry in "
        "known_collisions.json, of total marker overhead (tokens of opener+sigil+' '+body minus opener+' '+body, "
        "summed over bodies, openers and both encodings); ties broken by candidate order")


def scan_files():
    groups = {lang: (PY_TS_EXTS[lang], list(repos)) for lang, repos in PY_TS_GROUPS.items()}
    groups.update({lang: (exts, list(repos)) for lang, (exts, repos) in OTHER_GROUPS.items()})
    with (ROOT / "provenance.tsv").open(newline="") as handle:
        provenance = list(csv.DictReader(handle, delimiter="\t"))
    rows = []
    for lang, (exts, repos) in groups.items():
        found = []
        for repo in repos:
            paths = {r["file"] for r in provenance if r["repo"] == repo and r["file"]}
            for p in paths:
                parts = {x.lower() for x in Path(p).parts}
                if Path(p).suffix.lower() in exts and not SKIP_DIRS & parts and (DEV / repo / p).is_file():
                    found.append((repo, p))
        found.sort(key=lambda t: hashlib.sha256((t[0] + ":" + t[1]).encode()).hexdigest())
        rows.extend((lang, repo, p) for repo, p in found[:MAX_FILES_PER_LANG])
    return rows


def count_collisions(rows):
    collisions, per_lang = Counter(), Counter()
    for lang, repo, p in rows:
        per_lang[lang] += 1
        opener = OPENERS[LANG_OPENER[lang]]
        for line in (DEV / repo / p).read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.lstrip()
            for name, sig in CANDIDATES.items():
                if stripped.startswith(opener + sig):
                    collisions[(lang, name)] += 1
    return collisions, per_lang


def measure_overhead():
    overhead = {}
    for enc_name in ENCODINGS:
        enc = tiktoken.get_encoding(enc_name)
        for opener, text in OPENERS.items():
            base = sum(len(enc.encode("%s %s" % (text, b))) for b in BODIES)
            for name, sig in CANDIDATES.items():
                overhead[(opener, name, enc_name)] = sum(
                    len(enc.encode("%s%s %s" % (text, sig, b))) for b in BODIES) - base
    return overhead


def host_regex(opener, sigil):
    return r"(?:^|\s)%s%s \S" % (re.escape(opener), re.escape(sigil))


def main():
    rows = scan_files()
    with (ROOT / "marker_scan_files.tsv").open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(("language", "repo", "path"))
        writer.writerows(rows)
    collisions, per_lang = count_collisions(rows)
    overhead = measure_overhead()
    known = json.loads((ROOT / "known_collisions.json").read_text())
    names = list(CANDIDATES)
    eligible = [n for n in names if not any(collisions[(l, n)] for l in LANG_OPENER) and not known.get(n)]
    best = min(eligible, key=lambda n: (sum(overhead[(o, n, e)] for o in OPENERS for e in ENCODINGS), names.index(n)))
    ledger_path = ROOT / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    method = RULE + ". Corpus: up to %d SHA256-ranked Claude-touched files per language (marker_scan_files.tsv)." % MAX_FILES_PER_LANG

    def put(ident, value, tokenizer="not applicable"):
        ledger["entries"][ident] = {"value": value, "source": "marker_scan_files.tsv+marker_decision.json",
                                    "method": method, "tokenizer": tokenizer}

    for (opener, name, enc_name), value in overhead.items():
        put("marker.overhead.%s.%s.%s" % (opener, name, enc_name), value,
            "tiktoken %s %s" % (tiktoken.__version__, enc_name))
    for lang in LANG_OPENER:
        put("marker.files.%s" % lang, per_lang[lang])
        for name in names:
            put("marker.collision.%s.%s" % (lang, name), collisions[(lang, name)])
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n")
    decision = {
        "sigil": CANDIDATES[best], "sigil_name": best, "rule": RULE, "candidates": CANDIDATES, "bodies": BODIES,
        "eligible": eligible,
        "scope": "coded comments are LINE comments only: opener + sigil + space + body; block-comment forms are never coded",
        "hosts": {h: {"opener": OPENERS[o], "marker": OPENERS[o] + CANDIDATES[best],
                      "regex": host_regex(OPENERS[o], CANDIDATES[best])} for h, o in HOSTS.items()},
    }
    (ROOT / "marker_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=1) + "\n")
    print("sigil=%r (%s) eligible=%s files=%d" % (CANDIDATES[best], best, eligible, len(rows)))
    for name in names:
        total = sum(collisions[(l, name)] for l in LANG_OPENER)
        cost = {e: sum(overhead[(o, name, e)] for o in OPENERS) for e in ENCODINGS}
        print("%-8s %r collisions=%-5d overhead(sum over 3 openers)=%s known=%d" % (
            name, CANDIDATES[name], total, cost, len(known.get(name, []))))


if __name__ == "__main__":
    main()
