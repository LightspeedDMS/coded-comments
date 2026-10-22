"""Measure comment/code lines for the remaining host languages (same sampling convention as measure_ratios.py)."""

import csv
import hashlib
import json
import os
from pathlib import Path

from measure_ratios import source_path
from scanner import count_lines

ROOT = Path(__file__).resolve().parent
DEV = Path(os.environ.get("CC_CORPUS_DIR", str(Path.home() / "Dev")))
MAX_PER_REPO = 60
MIN_FILES = 10
SKIP_DIRS = {"vendor", "third_party", "thirdparty", "bin", "obj", "target", "generated", "node_modules"}
GROUPS = {
    "shell": ({".sh", ".bash"}, ("setup-dev-rocky", "claude-server", "code-indexer")),
    "go": ({".go"}, ("ragflow", "roxy", "tdd-guard")),
    "rust": ({".rs"}, ("code-indexer",)),
    "csharp": ({".cs"}, ("claude-server",)),
    "java": ({".java"}, ("swing-mcp-automation", "tdd-guard")),
    "c": ({".c", ".h"}, ("code-indexer", "GitNexus")),
    "cpp": ({".cpp", ".cc", ".hpp"}, ("code-indexer", "GitNexus")),
    "pascal": ({".pas", ".pp", ".dpr"}, ("code-indexer",)),
    "sql": ({".sql"}, ("code-indexer", "claude-server", "llm-creds-provider")),
}
METHOD = (
    "SHA256-ranked up to 60 current, non-test, non-vendor files per canonical repo from provenance.tsv; "
    "scanner.count_lines: comment/code line if it contains that token, mixed lines count in both, "
    "blank in neither; shell shebang excluded; strings handled per single-line quote rules (Go backtick "
    "multi-line). Not modeled: Rust nested block comments and lifetimes-as-quotes, C# verbatim/raw strings, "
    "shell heredocs (counted as code), Pascal compiler directives (counted as comments). "
    "Ratio=comment_lines/code_lines, rounded to 6 decimals."
)


def main():
    with (ROOT / "provenance.tsv").open(newline="") as handle:
        provenance = list(csv.DictReader(handle, delimiter="\t"))
    rows = []
    for lang, (exts, repos) in GROUPS.items():
        for repo in repos:
            paths = {r["file"] for r in provenance if r["repo"] == repo and r["file"]}
            paths = [p for p in paths if Path(p).suffix.lower() in exts and source_path(p)
                     and not SKIP_DIRS & {x.lower() for x in Path(p).parts}
                     and (DEV / repo / p).is_file()]
            paths.sort(key=lambda p: hashlib.sha256((repo + ":" + p).encode()).hexdigest())
            for p in paths[:MAX_PER_REPO]:
                text = (DEV / repo / p).read_text(encoding="utf-8", errors="replace")
                comment, code = count_lines(text, lang)
                rows.append((lang, repo, p, comment, code))
    with (ROOT / "ratio_files_other.tsv").open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(("language", "repo", "file", "comment_lines", "code_lines"))
        writer.writerows(rows)
    ledger_path = ROOT / "numbers.json"
    ledger = json.loads(ledger_path.read_text())
    gaps = []
    lines = ["# Remaining host-language comment-to-code sample", "",
             "Same convention as ratios.md (step 7). Scanner: scanner.py. " + METHOD, "",
             "| Language | Repos | Files | Comment lines | Code lines | Ratio |", "|---|---|---:|---:|---:|---:|"]
    for lang in GROUPS:
        sample = [r for r in rows if r[0] == lang]
        stats = {"files": len(sample), "comment_lines": sum(r[3] for r in sample),
                 "code_lines": sum(r[4] for r in sample)}
        if stats["code_lines"]:
            stats["comment_to_code"] = round(stats["comment_lines"] / stats["code_lines"], 6)
        for key, value in stats.items():
            ledger["entries"]["ratio.%s.%s" % (lang, key)] = {
                "value": value, "source": "ratio_files_other.tsv", "method": METHOD, "tokenizer": "not applicable"}
        if stats["files"] < MIN_FILES:
            gaps.append(lang)
        lines.append("| %s | %s | %d | %d | %d | %s |" % (
            lang, ", ".join(sorted({r[1] for r in sample})) or "-", stats["files"], stats["comment_lines"],
            stats["code_lines"], stats.get("comment_to_code", "n/a")))
    ledger["corpus_gaps"] = gaps + ["sql_dialects"]
    ledger["corpus_gaps_note"] = (
        "Languages listed have < %d sampled files (thin evidence). sql_dialects: .sql files were not classified "
        "into Oracle PL/SQL, PostgreSQL, T-SQL or SQLite; one combined sql ratio is reported." % MIN_FILES)
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=1) + "\n")
    lines += ["", "Thin samples (< %d files): %s. SQL dialects are not separated in the corpus."
              % (MIN_FILES, ", ".join(gaps) or "none")]
    (ROOT / "ratios_other.md").write_text("\n".join(lines) + "\n")
    print("Measured %d files; gaps: %s" % (len(rows), gaps))


if __name__ == "__main__":
    main()
