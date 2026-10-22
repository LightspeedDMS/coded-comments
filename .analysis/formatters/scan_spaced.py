#!/usr/bin/env python3
"""Rescan the marker-decision corpus for collisions with the SPACED marker forms (`# ^`, `// ^`, `-- ^`).

Reuses .analysis/measure_markers.scan_files (read-only import) so file selection is the original logic.
Usage: PYTHONDONTWRITEBYTECODE=1 python3 scan_spaced.py   (writes ../marker_spaced.json)
"""

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ANALYSIS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ANALYSIS))
import measure_markers as mm  # noqa: E402
from measure_ratios import GROUPS as PY_TS_GROUPS  # noqa: E402
from measure_ratios_other import GROUPS as OTHER_GROUPS  # noqa: E402

TAGS = ("hazard", "coupled", "security", "invariant", "external", "order", "why", "see", "perf", "todo")
TAG_RE = re.compile(r" (%s)\b" % "|".join(TAGS))
SAMPLE_KEYS = ("spaced_any", "spaced_tagged", "legacy_any", "legacy_tagged", "spaced_inline_any")
MAX_SAMPLES = 10
SAMPLE_CHARS = 100
OUT = ANALYSIS / "marker_spaced.json"


def corpus_report(rows):
    expected = set(repo for repos in PY_TS_GROUPS.values() for repo in repos)
    expected |= set(repo for _, repos in OTHER_GROUPS.values() for repo in repos)
    expected = sorted(expected)
    found = [r for r in expected if (mm.DEV / r).is_dir()]
    with (ANALYSIS / "marker_scan_files.tsv").open(newline="") as handle:
        frozen = [(r["language"], r["repo"], r["path"]) for r in csv.DictReader(handle, delimiter="\t")]
    missing_files = [f for f in frozen if not (mm.DEV / f[1] / f[2]).is_file()]
    return {"dev_dir": "~/Dev (CC_CORPUS_DIR or Path.home()/Dev)", "repos_expected": expected, "repos_found": found,
            "repos_missing": [r for r in expected if r not in found],
            "frozen_list_files": len(frozen), "frozen_list_files_missing_on_disk": len(missing_files),
            "fresh_scan_files": len(rows), "fresh_scan_equals_frozen_list": sorted(rows) == sorted(frozen),
            "files_scanned": len(rows), "files_by_language": dict(Counter(lang for lang, _, _ in rows))}


def scan(rows):
    counts, samples = defaultdict(Counter), {key: [] for key in SAMPLE_KEYS}

    def note(lang, key, where):
        counts[lang][key] += 1
        if len(samples[key]) < MAX_SAMPLES:
            samples[key].append(where)

    for lang, repo, path in rows:
        opener = mm.OPENERS[mm.LANG_OPENER[lang]]
        text = (mm.DEV / repo / path).read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            where = "%s/%s:%d: %s" % (repo, path, number, stripped[:SAMPLE_CHARS])
            for form, prefix in (("spaced", opener + " ^"), ("legacy", opener + "^")):
                if stripped.startswith(prefix):
                    note(lang, form + "_any", where)
                    counts[lang]["%s %s_any" % (opener, form)] += 1
                    if TAG_RE.match(stripped[len(prefix):]):
                        note(lang, form + "_tagged", where)
            if not stripped.startswith(opener) and re.search(r"\S\s+" + re.escape(opener) + r" \^", line):
                note(lang, "spaced_inline_any", where)
    return counts, samples


def main():
    rows = mm.scan_files()
    counts, samples = scan(rows)
    total = Counter()
    for lang_counts in counts.values():
        total.update(lang_counts)
    result = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "method": ("Original measure_markers.scan_files file selection (SHA256-ranked, max 400 files per language, "
                         "Claude-touched files that still exist). A line counts when its lstripped text starts with "
                         "opener+' ^' (spaced) or opener+'^' (legacy, baseline); tagged = the next word is one of the tags. "
                         "spaced_inline_any counts non-line-start occurrences (supplementary)."),
              "tags": list(TAGS), "corpus": corpus_report(rows),
              "counts_by_language": {k: dict(v) for k, v in counts.items()},
              "totals": dict(total), "samples": samples}
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    summary = {k: v for k, v in result["corpus"].items() if k not in ("repos_expected", "repos_found")}
    print(json.dumps({"totals": result["totals"], "corpus": summary}, indent=1))


if __name__ == "__main__":
    main()
