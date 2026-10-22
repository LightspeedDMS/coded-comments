"""Independently reproduce the seeded, repo-balanced comment sample."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED = "coded-comments-2026-10-13-v1"
STRATA = ("python", "python_docstring", "typescript_js", "shell", "go", "rust", "csharp", "java", "sql")
PER_STRATUM = 8


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main():
    candidates = load(ROOT / "comment_candidates.jsonl")
    actual = load(ROOT / "comment_sample.jsonl")
    by_stratum = defaultdict(lambda: defaultdict(list))
    ids = set()
    for item in candidates:
        assert item["id"] not in ids, "duplicate candidate ID"
        ids.add(item["id"])
        by_stratum[item["stratum"]][item["repo"]].append(item)
    expected = []
    for stratum in STRATA:
        buckets = by_stratum[stratum]
        assert buckets, "empty stratum " + stratum
        for repo in buckets:
            buckets[repo].sort(key=lambda x: hashlib.sha256((SEED + x["id"]).encode()).hexdigest())
        repos = sorted(buckets)
        selected = []
        while len(selected) < PER_STRATUM and any(buckets.values()):
            for repo in repos:
                if buckets[repo] and len(selected) < PER_STRATUM:
                    selected.append(buckets[repo].pop(0))
        assert len(selected) == PER_STRATUM, "too few candidates in " + stratum
        for index, item in enumerate(selected):
            expected.append((item["id"], "A" if index % 2 == 0 else "B"))
    assert [(x["id"], x["batch"]) for x in actual] == expected, "sample differs from seeded draw"
    assert len(actual) == PER_STRATUM * len(STRATA)
    ledger = json.loads((ROOT / "numbers.json").read_text())["entries"]
    assert ledger["sample.candidates"]["value"] == len(candidates)
    assert ledger["sample.selected"]["value"] == len(actual)
    for item in actual:
        assert item["text"].strip() and item["line"] > 0
    print("sample reproducible: %d comments, %d per stratum, batches A/B equal" % (
        len(actual), PER_STRATUM))


if __name__ == "__main__":
    main()
