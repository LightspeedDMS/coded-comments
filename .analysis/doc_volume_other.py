"""Doc-comment volume and public/private split for Go, Rust, C#, Java (analysis tooling only)."""

import csv
import json
import os
import re
from collections import defaultdict
from pathlib import Path

from testpaths import is_test_path

ROOT = Path(__file__).resolve().parent
DEV = Path(os.environ.get("CC_CORPUS_DIR", str(Path.home() / "Dev")))
LANGS = ("go", "rust", "csharp", "java")
GO_DIRECTIVE = re.compile(r"^//[a-z0-9]+:")
GO_DECL = re.compile(r"^(?:package\s+(?P<pkg>\w+)|func\s+(?:\([^)]*\)\s*)?(?P<fn>\w+)|type\s+(?P<ty>\w+)"
                     r"|(?:var|const)\s+(?P<vc>\w+)|(?:var|const)\s*\()")
JAVA_DOC = re.compile(r"/\*\*.*?\*/", re.DOTALL)
WORDS = re.compile(r"[A-Za-z_]+")
HEAD_END = re.compile(r"[(={;]")
METHOD = ("Doc comments counted per host: Go = contiguous // block directly above a column-0 package/func/type/"
          "var/const (//go: style directives skipped; public iff identifier capitalised; grouped var/const ( = "
          "unknown). Rust = /// runs above an item (attributes skipped; public iff item starts 'pub ' - pub(crate) "
          "etc. private) and //! runs (public iff file is lib.rs). C# = /// runs (public iff declaration has "
          "public, or protected without private; internal/private = private; no modifier, e.g. enum member = "
          "unknown). Java = /** */ blocks (public iff public/protected; private = private; no modifier = "
          "unknown). Known gaps: Go struct-field and interface-method docs, Rust trait-impl methods, interface "
          "members and package-private are not modelled. These hosts' doc comments are already counted as comment "
          "lines by scanner.py, so the inclusive ratio equals the original ratio. Line counts, not tokens.")


def _runs(lines, is_doc):
    """Yield (first, last) 1-based line ranges of consecutive doc lines."""
    start = None
    for i, line in enumerate(lines + [""], start=1):
        if i <= len(lines) and is_doc(line):
            start = start or i
        elif start:
            yield start, i - 1
            start = None


def _next_decl(lines, last, skip):
    """Return the first line after `last` that is not blank/skipped, only if no blank gap precedes it."""
    for line in lines[last:]:
        if not line.strip():
            return None
        if skip(line.strip()):
            continue
        return line
    return None


def go_docs(text, path=""):
    lines = text.splitlines()
    out = []
    for first, last in _runs(lines, lambda l: l.startswith("//")):
        body = [n for n in range(first, last + 1) if not GO_DIRECTIVE.match(lines[n - 1])]
        decl = lines[last] if last < len(lines) else ""
        m = GO_DECL.match(decl)
        if not body or not m:
            continue
        name = m.group("pkg") or m.group("fn") or m.group("ty") or m.group("vc")
        vis = "unknown" if name is None else ("public" if name[0].isupper() or m.group("pkg") else "private")
        out.append((body[0], body[-1], vis))
    return out


def rust_docs(text, path=""):
    lines = text.splitlines()
    out = []
    for first, last in _runs(lines, lambda l: l.lstrip().startswith("//!")):
        out.append((first, last, "public" if path.endswith("lib.rs") else "private"))
    outer = lambda l: l.lstrip().startswith("///") and not l.lstrip().startswith("////")
    for first, last in _runs(lines, outer):
        decl = _next_decl(lines, last, lambda s: s.startswith("#[") or s.startswith("///")) or ""
        out.append((first, last, "public" if decl.lstrip().startswith("pub ") else "private"))
    return sorted(out)


def _modifier_visibility(decl, public_words, private_words):
    head = HEAD_END.split(decl, 1)[0]
    words = {w.lower() for w in WORDS.findall(head)}
    if "private" in words:
        return "private"
    if words & public_words:
        return "public"
    if words & private_words:
        return "private"
    return "unknown"


def csharp_docs(text, path=""):
    lines = text.splitlines()
    out = []
    for first, last in _runs(lines, lambda l: l.lstrip().startswith("///")):
        decl = _next_decl(lines, last, lambda s: s.startswith("[")) or ""
        out.append((first, last, _modifier_visibility(decl, {"public", "protected"}, {"internal"})))
    return out


def java_docs(text, path=""):
    out = []
    for match in JAVA_DOC.finditer(text):
        first = text.count("\n", 0, match.start()) + 1
        last = text.count("\n", 0, match.end() - 1) + 1
        rest = text[match.end():].split("\n")[1:] if "\n" in text[match.end():] else []
        decl = next((l for l in rest if l.strip() and not l.strip().startswith("@")), "")
        out.append((first, last, _modifier_visibility(decl, {"public", "protected"}, set())))
    return out


DOC_FUNCS = {"go": go_docs, "rust": rust_docs, "csharp": csharp_docs, "java": java_docs}


def _measure_scope(rows):
    totals = defaultdict(lambda: defaultdict(int))
    for row in rows:
        lang = row["language"]
        text = (DEV / row["repo"] / row["file"]).read_text(encoding="utf-8", errors="replace")
        docs = DOC_FUNCS[lang](text, row["file"])
        buckets = {"public": set(), "private": set(), "unknown": set()}
        for first, last, vis in docs:
            buckets[vis].update(range(first, last + 1))
        values = {"files": 1, "docs": len(docs),
                  "doc_lines": len(buckets["public"] | buckets["private"] | buckets["unknown"]),
                  "public_lines": len(buckets["public"]), "private_lines": len(buckets["private"] - buckets["public"]),
                  "unknown_lines": len(buckets["unknown"] - buckets["public"] - buckets["private"]),
                  "inclusive_comment_lines": int(row["comment_lines"]), "inclusive_code_lines": int(row["code_lines"])}
        for key, value in values.items():
            totals[lang][key] += value
    result = {}
    for lang, v in totals.items():
        out = dict(v)
        out["inclusive_ratio"] = round(out["inclusive_comment_lines"] / out["inclusive_code_lines"], 6)
        out["doc_share_of_comment_lines"] = round(out["doc_lines"] / out["inclusive_comment_lines"], 6)
        result[lang] = out
    return result


def measure_rows(rows):
    """Return {scope_prefix: {lang: values}}; scope '' = all sampled files, 'excl_tests.' = non-test files."""
    kept = [r for r in rows if not is_test_path(r["file"])]
    return {"": _measure_scope(rows), "excl_tests.": _measure_scope(kept)}


def main():
    with (ROOT / "ratio_files_other.tsv").open(newline="") as handle:
        rows = [r for r in csv.DictReader(handle, delimiter="\t") if r["language"] in LANGS]
    result = measure_rows(rows)
    ledger_path = ROOT / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    lines = ["# Doc-comment volume: Go, Rust, C#, Java", "", METHOD, "",
             "| Scope | Lang | Files | Doc spans | Doc lines | Public | Private | Unknown | Comment lines | Doc share |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for scope, per_lang in result.items():
        for lang, v in per_lang.items():
            for key, value in v.items():
                ledger["entries"]["doc.%s.%s%s" % (lang, scope, key)] = {
                    "value": value, "source": "ratio_files_other.tsv and current HEAD files",
                    "method": METHOD, "tokenizer": "not applicable"}
            lines.append("| %s | %s | %d | %d | %d | %d | %d | %d | %d | %s |" % (
                scope or "all", lang, v["files"], v["docs"], v["doc_lines"], v["public_lines"], v["private_lines"],
                v["unknown_lines"], v["inclusive_comment_lines"], v["doc_share_of_comment_lines"]))
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n")
    (ROOT / "doc_volume_other.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[6:]))


if __name__ == "__main__":
    main()
