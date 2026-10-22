"""Final-gate self-check (throwaway): every coded-looking example in the shipped docs, fenced or inline, is valid."""

import re
import sys
from pathlib import Path

import yaml

import grammar_check as gc

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "reference"
LINE = re.compile(r"(?:^|\s)((?:%s) (?:%s) \S.*)$" % (gc.MARKERS, gc.TAGS))
INLINE = re.compile(r"`((?:%s) (?:%s) [^`]+)`" % (gc.MARKERS, gc.TAGS))
SCANNED = [REF / "ENTRY.md", REF / "index.md", REF / "what.md", REF / "how.md", REF / "migrate.md",
           REF / "reviewer.md", REF / "exemptions.md", REF / "grammar.md", ROOT / "README.md",
           ROOT / "docs" / "design.md", ROOT / "docs" / "open-questions.md", ROOT / "docs" / "evidence.md"]


def examples(path):
    found, skip = [], False
    for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if text.startswith("```"):
            skip = text.strip() in ("```bad",) if not skip else False
            continue
        if skip:
            continue
        for match in INLINE.finditer(text):
            found.append((number, match.group(1)))
        match = LINE.search(text)
        if match and not INLINE.search(text):
            found.append((number, match.group(1)))
    return found


def check_examples(errors):
    total = 0
    for path in SCANNED:
        for number, line in examples(path):
            total += 1
            if not gc.valid(line):
                errors.append("%s:%d invalid example: %s" % (path.relative_to(ROOT), number, line))
    return total


STALE = re.compile(r"\bone operator per clause\b|\btwo operators\b|\bsecond operator\b", re.I)


def check_stale_wording(errors):
    """The one-operator-per-clause rule is gone (S5: one '=>' per clause, one cmp per side); no doc may claim it."""
    for path in SCANNED + [ROOT / "docs" / "grammar-examples.md"]:
        for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if STALE.search(text):
                errors.append("%s:%d stale one-operator wording: %s" % (path.relative_to(ROOT), number, text.strip()))


def check_snippet(errors):
    """The entry snippet embedded in README.md is ENTRY.md lines 1-3 verbatim."""
    entry = "\n".join((REF / "ENTRY.md").read_text(encoding="utf-8").splitlines()[:3])
    blocks = re.findall(r"```markdown\n(.*?)\n```", (ROOT / "README.md").read_text(encoding="utf-8"), re.DOTALL)
    if entry not in blocks:
        errors.append("README.md entry snippet differs from reference/ENTRY.md lines 1-3")


def check_coverage(errors):
    rules = yaml.safe_load((REF / "rules" / "core.yaml").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    index = (REF / "index.md").read_text(encoding="utf-8")
    for host in rules["hosts"]:
        if host not in index:
            errors.append("index.md lacks host " + host)
    for path in sorted(p for p in REF.rglob("*") if p.is_file()):
        rel = path.relative_to(REF).as_posix()
        if rel.startswith("hosts/"):
            continue
        if path.name not in readme and rel not in readme:
            errors.append("README layout lacks " + rel)
        if path.name not in ("ENTRY.md", "index.md") and rel not in index:
            errors.append("index.md lacks " + rel)


def main():
    errors = []
    total = check_examples(errors)
    check_stale_wording(errors)
    check_snippet(errors)
    check_coverage(errors)
    for error in errors:
        print("FAIL", error)
    print("selfcheck: %d examples in %d files, %d failures" % (total, len(SCANNED), len(errors)))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
