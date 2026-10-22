"""Count real enclosing comments before and after exploratory coded compression."""

import json
import re
from pathlib import Path

import tiktoken


ROOT = Path(__file__).resolve().parent
DEV = Path.home() / "Dev"
ENCODINGS = ("o200k_base", "cl100k_base")
DRAFTS = {
    "01543994050bc513b7ec": "#@ cpl activated-repos=golden-repos CoW placement; reflink activation; build_snapshot_manager #1052",
    "d65b3916a3672dfb85b9": "#@ ord ensure_encryption_key_salt<manager init; failure=>abort startup",
    "06f029a9f140dc49da78": "#@ cpl manual-trigger route reads app.state.self_monitoring_repo_root,github_repo #87",
    "acb4c5338c42055fc45c": "#@ ext TLP>=1.10 _AC/_BAT/_SAV=mode; /etc/tlp.conf wins; _SAV->_BAT; set _BAT=BAL, AC=BAL; leave _AC for GNOME Performance",
    "16c980e52afdfa7f7764": "//@ inv topN<=1024 before make; CodeQL allocation warning false positive; slice<=1MiB",
    "90419c465f2d1d4002b4": "///@ haz qualified external Java type!=java.lang from bare simple name; receiver::FileTypedNames",
    "64a5c5d83e0d4552f2fc": "//@ haz missing abi_version=>None, never current ABI; #1784",
    "e45785f19ed2d934ed49": "//@ haz Testing env: skip Claude execution; otherwise test process hangs",
    "003ca781c182cdd178af": "//@ why parse error=>null; caller logs warning",
    "c2d05ec7931a65758e3f": "--@ cpl token-family tables owner=RefreshTokenBackend._ensure_schema",
}


def extract(item):
    lines = (DEV / item["repo"] / item["path"]).read_text(errors="replace").splitlines()
    index = item["line"] - 1
    line = lines[index]
    if item["kind"] == "docstring":
        found = re.search(r"(['\"]{3})", line)
        if not found:
            raise ValueError("docstring delimiter absent: " + item["id"])
        marker = found.group(1)
        end = index
        if line.count(marker) < 2:
            end += 1
            while end < len(lines) and marker not in lines[end]:
                end += 1
        return "\n".join(lines[index:end + 1])
    if item["kind"] == "block":
        start = index
        while start >= 0 and "/*" not in lines[start]:
            start -= 1
        end = index
        while end < len(lines) and "*/" not in lines[end]:
            end += 1
        if start < 0 or end >= len(lines):
            raise ValueError("block delimiter absent: " + item["id"])
        return "\n".join(lines[start:end + 1])
    marker = "#" if item["stratum"] in ("python", "shell") else "--" if item["stratum"] == "sql" else "//"
    pattern = re.compile(r"^\s*" + re.escape(marker))
    if not pattern.match(line):
        pos = line.find(marker)
        if pos < 0:
            raise ValueError("line marker absent: " + item["id"])
        return line[pos:]
    start = index
    while start > 0 and pattern.match(lines[start - 1]):
        start -= 1
    end = index
    while end + 1 < len(lines) and pattern.match(lines[end + 1]):
        end += 1
    return "\n".join(lines[start:end + 1])


def deletable_excerpt(item):
    """Return only an exact full-line comment (or whole docstring), never code."""
    if item["kind"] == "docstring":
        return extract(item)
    if item["stratum"] == "shell" and item["kind"] == "block":
        return None  # Shell has no slash-star comments; this is an extractor false positive.
    line = (DEV / item["repo"] / item["path"]).read_text(errors="replace").splitlines()[item["line"] - 1]
    stripped = line.lstrip()
    if item["kind"] == "block":
        return line if stripped.startswith(("/*", "*")) else None
    marker = "#" if item["stratum"] in ("python", "shell") else "--" if item["stratum"] == "sql" else "//"
    return line if stripped.startswith(marker) else None


def main():
    sample = {x["id"]: x for x in map(json.loads, (ROOT / "comment_sample.jsonl").read_text().splitlines())}
    labels = {x["id"]: x for name in ("classification_A.jsonl", "classification_B.jsonl")
              for x in map(json.loads, (ROOT / name).read_text().splitlines())}
    rows = []
    for ident, compressed in DRAFTS.items():
        item = sample[ident]
        rows.append({"id": ident, "repo": item["repo"], "path": item["path"], "line": item["line"],
                     "category": labels[ident]["primary_category"], "original": extract(item),
                     "compressed": compressed})
    (ROOT / "real_compression.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows))

    # Deletion is a separate counterfactual on verified full-line excerpts only.
    redundant = []
    seen = set()
    for ident, label in labels.items():
        if label["disposition"] != "redundant":
            continue
        item = sample[ident]
        original = deletable_excerpt(item)
        if original is None:
            continue
        key = (item["repo"], item["path"], item["line"])
        if key in seen:
            continue
        seen.add(key)
        redundant.append({"id": ident, "repo": item["repo"], "path": item["path"],
                          "line": item["line"], "original": original})
    (ROOT / "redundant_deletion.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in redundant))

    ledger_path = ROOT / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    entries = ledger["entries"]
    report = ["# Real comment compression experiment", "",
              "Draft coded lines are exploratory, not the final grammar. Originals are full enclosing comments "
              "from the read-only corpus files. Each selected record was labeled valuable in the frozen sample. "
              "Counts use tiktoken proxies for Claude and include comment syntax. They do not prove semantic equivalence "
              "of the drafts; review each before migration.", "",
              "| ID | Category | o200k original | o200k draft | cl100k original | cl100k draft |",
              "|---|---|---:|---:|---:|---:|"]
    for enc_name in ENCODINGS:
        encoder = tiktoken.get_encoding(enc_name)
        total_orig = total_draft = 0
        for row in rows:
            for field in ("original", "compressed"):
                ident = "tok.real.%s.%s.%s" % (row["id"], field, enc_name)
                count = len(encoder.encode(row[field]))
                entries[ident] = {"value": count, "source": "real_compression.jsonl:" + row["id"],
                                  "method": "tiktoken count of exact original source excerpt or exploratory draft",
                                  "tokenizer": "tiktoken %s %s" % (tiktoken.__version__, enc_name)}
                if field == "original":
                    total_orig += count
                else:
                    total_draft += count
        for field, value in (("original", total_orig), ("compressed", total_draft)):
            entries["tok.real.total.%s.%s" % (field, enc_name)] = {
                "value": value, "source": "real_compression.jsonl",
                "method": "sum of ten per-comment tiktoken counts",
                "tokenizer": "tiktoken %s %s" % (tiktoken.__version__, enc_name)}
        entries["tok.real.total.saved.%s" % enc_name] = {
            "value": total_orig - total_draft, "source": "real_compression.jsonl",
            "method": "sum(original tokens) minus sum(draft tokens) over ten selected comments",
            "tokenizer": "tiktoken %s %s" % (tiktoken.__version__, enc_name)}
        deleted = sum(len(encoder.encode(row["original"])) for row in redundant)
        entries["tok.delete.redundant.%s" % enc_name] = {
            "value": deleted, "source": "redundant_deletion.jsonl",
            "method": "sum of distinct verified full-line redundant excerpts (or whole docstrings); sampled subset only",
            "tokenizer": "tiktoken %s %s" % (tiktoken.__version__, enc_name)}
    entries["tok.delete.redundant.excerpts"] = {
        "value": len(redundant), "source": "redundant_deletion.jsonl",
        "method": "count of verified full-line redundant excerpts, excluding inline and syntax false positives",
        "tokenizer": "not applicable"}
    for row in rows:
        ident = row["id"]
        report.append("| %s | %s | %d [m:tok.real.%s.original.o200k_base] | %d [m:tok.real.%s.compressed.o200k_base] | %d [m:tok.real.%s.original.cl100k_base] | %d [m:tok.real.%s.compressed.cl100k_base] |" % (
            ident, row["category"], entries["tok.real.%s.original.o200k_base" % ident]["value"], ident,
            entries["tok.real.%s.compressed.o200k_base" % ident]["value"], ident,
            entries["tok.real.%s.original.cl100k_base" % ident]["value"], ident,
            entries["tok.real.%s.compressed.cl100k_base" % ident]["value"], ident))
    report += ["", "For these ten selected valuable comments, the drafts remove %d o200k tokens "
               "[m:tok.real.total.saved.o200k_base] and %d cl100k tokens "
               "[m:tok.real.total.saved.cl100k_base]. One short original expands; the total is dominated by "
               "long source blocks, so it is not a corpus-wide savings rate." % (
                   entries["tok.real.total.saved.o200k_base"]["value"],
                   entries["tok.real.total.saved.cl100k_base"]["value"]), "",
               "Separate deletion estimate: %d verified full-line excerpts labeled redundant "
               "in the frozen sample would remove %d o200k tokens [m:tok.delete.redundant.o200k_base] "
               "or %d cl100k tokens [m:tok.delete.redundant.cl100k_base]. "
               "This excludes inline comments and extractor false positives. It is a sampled-excerpt estimate, "
               "not a repository-wide saving estimate." % (
                   len(redundant), entries["tok.delete.redundant.o200k_base"]["value"],
                   entries["tok.delete.redundant.cl100k_base"]["value"])]
    (ROOT / "real_compression.md").write_text("\n".join(report) + "\n")
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n")
    print("Measured %d valuable originals/drafts and %d redundant deletions" % (len(rows), len(redundant)))


if __name__ == "__main__":
    main()
