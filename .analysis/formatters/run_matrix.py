#!/usr/bin/env python3
"""Formatter compatibility matrix for coded-comment markers (spaced `# ^` vs legacy `#^`).

Usage: FMT_TOOLS=<dir with venv/, npm/, gobin/> TMPDIR=<scratch> python3 run_matrix.py
Writes results.json and results.md next to this script. Fixtures live in fixtures/.
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fmt_core import MARKER_RE, classify, coded_lines, run_once
from fmt_report import render_md
from fmt_specs import build_specs, tool_versions

ROOT = Path(__file__).resolve().parent
FIX = ROOT / "fixtures"
PASCAL_NOTE = "N/A: no common formatter available on this machine (fpc/ptop/jcf not installed); not tested"


def second_pass_kind(first, second, key, err2):
    if key not in first or MARKER_RE.search(first[key]) is None:
        return "n/a"
    if err2:
        return "error"
    return classify(first[key], second.get(key))


def evaluate_variant(sp, fixture, variant, text, workroot):
    before = coded_lines(text, fixture)
    pass1, err1 = run_once(sp, text, fixture, workroot)
    pass2, err2 = (None, None) if err1 else run_once(sp, pass1, fixture, workroot)
    first = {} if err1 else coded_lines(pass1, fixture, strict=False)
    second = {} if (err1 or err2) else coded_lines(pass2, fixture, strict=False)
    records = []
    for key, line in sorted(before.items()):
        rec = {"language": sp["language"], "formatter": sp["formatter"], "variant": variant,
               "fixture": fixture, "position": key[0], "form": key[1], "before": line.strip()}
        if err1:
            rec.update(status="error", detail=err1)
        else:
            kind, after = classify(line, first.get(key)), first.get(key)
            rec.update(status="unchanged" if kind == "unchanged" else "rewritten", kind=kind,
                       after=after.strip() if after else None, second_pass=second_pass_kind(first, second, key, err2))
        records.append(rec)
    idem = {"language": sp["language"], "formatter": sp["formatter"], "variant": variant, "fixture": fixture,
            "idempotent": None if (err1 or err2) else pass1 == pass2, "error": err1 or err2}
    return records, idem


def main():
    records, idempotency, not_applicable = [], [], []
    with tempfile.TemporaryDirectory(prefix="fmtmatrix_") as tmp:
        workroot = Path(tmp)
        versions = tool_versions()
        for sp in build_specs(workroot):
            for fixture in sp["fixtures"]:
                original = (FIX / fixture).read_text()
                variants = [("clean", original)]
                if sp["deindent"]:
                    variants.append(("deindented", "\n".join(l.lstrip() for l in original.split("\n"))))
                else:
                    not_applicable.append({"language": sp["language"], "formatter": sp["formatter"],
                                           "variant": "deindented", "reason": "indentation is syntax"})
                for variant, text in variants:
                    recs, idem = evaluate_variant(sp, fixture, variant, text, workroot)
                    records.extend(recs)
                    idempotency.append(idem)
    result = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tools": versions,
              "records": records, "idempotency": idempotency, "not_applicable": not_applicable,
              "pascal": PASCAL_NOTE}
    (ROOT / "results.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    (ROOT / "results.md").write_text(render_md(result))
    spaced = [r for r in records if r["form"] == "S" and r.get("kind") not in ("unchanged", "whitespace_only")]
    print("records=%d spaced_marker_text_missing_or_error=%d" % (len(records), len(spaced)))
    for r in spaced:
        print(" ", r["language"], r["formatter"], r["variant"], r["position"], r.get("kind"), r["before"], "->",
              r.get("after") or r.get("detail"))


if __name__ == "__main__":
    main()
