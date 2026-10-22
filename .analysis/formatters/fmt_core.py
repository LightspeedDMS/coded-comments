"""Measurement core: locate coded lines, classify their change, run one formatter pass."""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ID_RE = re.compile(r"id=(\w+)\.([SL])\b")
MARKER_RE = re.compile(r"(#|//|--)( ?)\^")
ERR_TAIL_CHARS = 400
EMPTY_CONFIG = {"black": "pyproject.toml", "rustfmt": "rustfmt.toml"}
SQLFLUFF_MAX_OK_RC = 1  #^ external sqlfluff format exits 1 when unfixable lint remains; PRS in output means parse failure


def coded_lines(text, fixture, strict=True):
    found = {}
    for line in text.splitlines():
        match = ID_RE.search(line)
        if not match:
            continue
        key = (match.group(1), match.group(2))
        if key in found:
            sys.exit("duplicate id %s in %s" % (key, fixture))
        if strict and not MARKER_RE.search(line):
            sys.exit("id line without marker in %s: %s" % (fixture, line))
        found[key] = line
    return found


def classify(before, after):
    marker_before = MARKER_RE.search(before)
    if marker_before is None:
        sys.exit("classify: before-line has no marker: %s" % before)
    if after is None:
        return "line_missing"
    if before == after:
        return "unchanged"
    marker_after = MARKER_RE.search(after)
    if marker_after is None or marker_before.group(0) != marker_after.group(0):
        return "marker_changed"
    if before[marker_before.end():] != after[marker_after.end():]:
        return "text_changed"
    return "whitespace_only"


def run_once(sp, text, name, workroot):
    env = dict(os.environ, **sp["env"])
    with tempfile.TemporaryDirectory(prefix="w_", dir=workroot) as tmp:
        work = Path(tmp)
        if sp["formatter"] in EMPTY_CONFIG:
            (work / EMPTY_CONFIG[sp["formatter"]]).write_text("")
        target = work / name
        target.write_text(text)
        proc = subprocess.run(sp["argv"](target), capture_output=True, text=True, cwd=work, env=env, check=False)
        log = (proc.stdout if sp["mode"] == "inplace" else "") + proc.stderr
        if sp["formatter"].startswith("sqlfluff"):
            failed = "PRS" in log or "Traceback" in log or proc.returncode > SQLFLUFF_MAX_OK_RC
        else:
            failed = proc.returncode != 0
        if failed:
            return None, "rc=%d %s" % (proc.returncode, log.strip()[-ERR_TAIL_CHARS:])
        return (proc.stdout if sp["mode"] == "stdout" else target.read_text()), None
