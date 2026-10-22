"""Step 16 check: sigil choice follows from recounted token overhead, corpus collisions and known collisions."""

import csv
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
DEV = Path(os.environ.get("CC_CORPUS_DIR", str(Path.home() / "Dev")))
ENCODINGS = ("o200k_base", "cl100k_base")
MIN_CANDIDATES = 10
MIN_BODIES = 3
MIN_SCAN_FILES = 500
OPENERS = {"hash": "#", "slash": "//", "dash": "--"}
LANG_OPENER = {"python": "hash", "shell": "hash", "typescript_js": "slash", "go": "slash", "rust": "slash",
               "csharp": "slash", "java": "slash", "c": "slash", "cpp": "slash", "pascal": "slash", "sql": "dash"}
HOSTS = {"python": "hash", "typescript_javascript": "slash", "shell": "hash", "go": "slash", "rust": "slash",
         "csharp": "slash", "java": "slash", "pascal": "slash", "c": "slash", "cpp": "slash",
         "plsql": "dash", "postgresql": "dash", "tsql": "dash", "sqlite": "dash"}
POSITIVE = ["{o}{s} inv x<=y", "    {o}{s} cpl src/a.x:f", "x = 1 {o}{s} haz keep timeout #12"]
NEGATIVE = {
    "hash": ["# noqa: E501", "#!/usr/bin/env bash", "#: sphinx doc", "# plain prose", "#pragma once",
             "# type: ignore", "#{s}{s} double", "x = 1  #{s}no-space", "#{s}", "${#{s}}"],
    "slash": ["// eslint-disable-next-line", "//@ts-ignore", "/// <summary>", "//! inner doc", "// plain prose",
              "//go:generate stringer", "//nolint:gosec", "http://{s}x.example", "//{s}{s}{s} marks", "//{s}", "/{s}"],
    "dash": ["-- plain", "--+ hint", "--{s}{s} double", "---- banner", "--{s}", "SELECT 1; --{s}no-space"],
}


def count(enc, text):
    return len(enc.encode(text))


def verify_overhead(decision, ledger):
    overhead = {}
    for enc_name in ENCODINGS:
        enc = tiktoken.get_encoding(enc_name)
        for opener, text in OPENERS.items():
            base = sum(count(enc, "%s %s" % (text, b)) for b in decision["bodies"])
            for name, sig in decision["candidates"].items():
                got = sum(count(enc, "%s%s %s" % (text, sig, b)) for b in decision["bodies"]) - base
                ident = "marker.overhead.%s.%s.%s" % (opener, name, enc_name)
                assert ledger[ident]["value"] == got, "%s: ledger %s recount %s" % (ident, ledger[ident]["value"], got)
                overhead[(opener, name, enc_name)] = got
    return overhead


def verify_collisions(decision, ledger):
    with (ROOT / "marker_scan_files.tsv").open(newline="") as handle:
        files = list(csv.DictReader(handle, delimiter="\t"))
    assert len(files) >= MIN_SCAN_FILES, "scan list too small: %d" % len(files)
    collisions, per_lang = Counter(), Counter()
    for row in files:
        per_lang[row["language"]] += 1
        opener = OPENERS[LANG_OPENER[row["language"]]]
        text = (DEV / row["repo"] / row["path"]).read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            stripped = line.lstrip()
            for name, sig in decision["candidates"].items():
                if stripped.startswith(opener + sig):
                    collisions[(row["language"], name)] += 1
    for lang in LANG_OPENER:
        assert per_lang[lang] > 0, "no scan files for " + lang
        assert ledger["marker.files.%s" % lang]["value"] == per_lang[lang], lang
        for name in decision["candidates"]:
            ident = "marker.collision.%s.%s" % (lang, name)
            assert ledger[ident]["value"] == collisions[(lang, name)], "%s: %s vs %s" % (
                ident, ledger[ident]["value"], collisions[(lang, name)])
    return collisions


def select_sigil(decision, known, overhead, collisions):
    cands = list(decision["candidates"])
    eligible = [n for n in cands if not any(collisions[(l, n)] for l in LANG_OPENER) and not known.get(n)]
    assert eligible, "no sigil survives collision filters"
    best = min(eligible, key=lambda n: (sum(overhead[(o, n, e)] for o in OPENERS for e in ENCODINGS), cands.index(n)))
    assert decision["sigil_name"] == best and decision["sigil"] == decision["candidates"][best], (
        "decision %s != rule %s" % (decision["sigil_name"], best))
    return eligible


def verify_regexes(decision):
    assert set(decision["hosts"]) == set(HOSTS)
    for host, opener_name in HOSTS.items():
        info = decision["hosts"][host]
        assert info["opener"] == OPENERS[opener_name] and info["marker"] == info["opener"] + decision["sigil"], host
        rx = re.compile(info["regex"])
        for tmpl in POSITIVE:
            line = tmpl.replace("{o}", info["opener"]).replace("{s}", decision["sigil"])
            assert rx.search(line), "%s regex must accept %r" % (host, line)
        for tmpl in NEGATIVE[opener_name]:
            line = tmpl.replace("{s}", decision["sigil"])
            assert not rx.search(line), "%s regex must reject %r" % (host, line)


def main():
    decision = json.loads((ROOT / "marker_decision.json").read_text())
    known = json.loads((ROOT / "known_collisions.json").read_text())
    ledger = json.loads((ROOT / "numbers.json").read_text())["entries"]
    assert len(decision["candidates"]) >= MIN_CANDIDATES and len(decision["bodies"]) >= MIN_BODIES
    overhead = verify_overhead(decision, ledger)
    collisions = verify_collisions(decision, ledger)
    eligible = select_sigil(decision, known, overhead, collisions)
    verify_regexes(decision)
    print("marker decision OK: sigil %r (%s), eligible=%s, hosts=%d" % (
        decision["sigil"], decision["sigil_name"], eligible, len(decision["hosts"])))


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, FileNotFoundError, KeyError, re.error) as exc:
        print("FAIL: %s: %s" % (type(exc).__name__, exc))
        sys.exit(1)
