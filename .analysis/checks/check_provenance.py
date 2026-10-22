"""Recompute Claude-authored commit counts for two independent source repos."""

import csv
import subprocess
from pathlib import Path


DEV = Path.home() / "Dev"
TSV = Path(__file__).resolve().parents[1] / "provenance.tsv"
REPOS = ("code-indexer", "claude-pace-maker")
GREP = r"Co-Authored-By:[[:space:]]*Claude"


def git_commits(repo: str) -> set[str]:
    output = subprocess.check_output(
        [
            "git", "-C", str(DEV / repo), "log", "--all",
            "--regexp-ignore-case", "--extended-regexp", f"--grep={GREP}",
            "--format=%H",
        ],
        text=True,
    )
    return set(output.splitlines())


def main() -> None:
    with TSV.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert rows, "provenance.tsv has no rows"
    assert set(rows[0]) == {"repo", "commit", "file"}
    for repo in REPOS:
        expected = git_commits(repo)
        actual = {r["commit"] for r in rows if r["repo"] == repo}
        assert actual == expected, (
            f"{repo}: TSV has {len(actual)} commits, git log has {len(expected)}; "
            f"missing={len(expected - actual)}, extra={len(actual - expected)}"
        )
        print(f"{repo}: {len(actual)} Claude-authored commits match git log")


if __name__ == "__main__":
    main()
