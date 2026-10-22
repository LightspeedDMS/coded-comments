"""Read-only inventory of files touched by Claude-coauthored commits."""

import csv
import subprocess
from pathlib import Path


DEV = Path.home() / "Dev"
OUT = Path(__file__).resolve().parent
GREP = r"Co-Authored-By:[[:space:]]*Claude"


def commit_files(repo: Path) -> dict[str, set[str]]:
    output = subprocess.check_output(
        [
            "git", "-C", str(repo), "log", "--all", "--regexp-ignore-case",
            "--extended-regexp", f"--grep={GREP}", "--format=COMMIT:%H",
            "--name-only",
        ],
        text=True,
        errors="replace",
    )
    found: dict[str, set[str]] = {}
    commit = None
    for line in output.splitlines():
        if line.startswith("COMMIT:"):
            commit = line.removeprefix("COMMIT:")
            found.setdefault(commit, set())
        elif line and commit is not None:
            found[commit].add(line)
    return found


def main() -> None:
    repos = sorted(p for p in DEV.iterdir() if p.is_dir() and (p / ".git").exists())
    summary = []
    with (OUT / "provenance.tsv").open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(("repo", "commit", "file"))
        for repo in repos:
            commits = commit_files(repo)
            files = {path for paths in commits.values() for path in paths}
            summary.append((repo.name, len(commits), len(files)))
            for commit, paths in sorted(commits.items()):
                for path in sorted(paths) if paths else ("",):
                    writer.writerow((repo.name, commit, path))

    total_commits = sum(count for _, count, _ in summary)
    md = [
        "# Claude coauthor provenance",
        "",
        "Discovery: immediate child directories of ~/Dev containing .git; nested test/third-party repos excluded.",
        "Locator: git log --all --regexp-ignore-case --extended-regexp "
        "--grep='Co-Authored-By:[[:space:]]*Claude' --format=COMMIT:%H --name-only.",
        "The TSV contains one row per commit/file pair, including an empty file cell for commits without paths.",
        "Paths are historical; later corpus steps must check whether they still exist before reading.",
        "All source repos were read-only. Counts are distinct commit hashes and distinct historical paths per repo.",
        "",
        "| Repo | Claude-coauthored commits | Distinct files |",
        "|---|---:|---:|",
    ]
    md.extend(f"| {name} | {count} | {files} |" for name, count, files in summary)
    md.extend(("", f"Total: {total_commits} commits across {len(repos)} top-level repositories."))
    (OUT / "provenance.md").write_text("\n".join(md) + "\n")
    print(f"Located {total_commits} commits in {len(repos)} repositories")


if __name__ == "__main__":
    main()
