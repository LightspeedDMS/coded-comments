"""Step 18 check: doc-comment extraction rules (go/rust/csharp/java) on fixtures, and ledger recount."""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GO = """// Package x does y.
package x

// Exported does a thing.
// More.
func Exported() {}

// helper does.
func helper() {}

// Detached comment

func Other() {}

//go:generate stringer -type=T
func Gen() {}

// Run runs.
func (s *S) Run() {}
// run runs.
func (s *S) run() {}
// Group of consts.
const (
"""
RUST = """//! Crate docs.
//! More.

/// Public thing.
#[derive(Debug)]
pub struct A;

/// Internal thing.
pub(crate) fn f() {}

/// Private fn.
fn g() {}

// not doc
fn h() {}
"""
CSHARP = """/// <summary>
/// Reads.
/// </summary>
public class Reader
{
    /// <summary>Internal.</summary>
    internal void A() {}
    /// <summary>Prot.</summary>
    [Obsolete]
    protected void B() {}
    /// <summary>Member.</summary>
    Member,
    /// <summary>pp</summary>
    private protected void C() {}
"""
JAVA = """/**
 * Public class.
 */
public class A {
    /** Pkg. */
    int x;
    /** Priv. */
    @Deprecated
    private void p() {}
    /** Prot. */
    protected void q() {}
    // not javadoc
    public void r() {}
"""
CASES = [
    ("go", GO, "x.go", [(1, 1, "public"), (4, 5, "public"), (8, 8, "private"), (18, 18, "public"),
                        (20, 20, "private"), (22, 22, "unknown")]),
    ("rust", RUST, "src/lib.rs", [(1, 2, "public"), (4, 4, "public"), (8, 8, "private"), (11, 11, "private")]),
    ("rust", RUST, "src/x.rs", [(1, 2, "private"), (4, 4, "public"), (8, 8, "private"), (11, 11, "private")]),
    ("csharp", CSHARP, "R.cs", [(1, 3, "public"), (6, 6, "private"), (8, 8, "public"), (11, 11, "unknown"),
                                (13, 13, "private")]),
    ("java", JAVA, "A.java", [(1, 3, "public"), (5, 5, "unknown"), (7, 7, "private"), (10, 10, "public")]),
]
LANGS = ("go", "rust", "csharp", "java")


def main():
    from doc_volume_other import DOC_FUNCS, measure_rows

    for lang, text, path, want in CASES:
        got = [tuple(d) for d in DOC_FUNCS[lang](text, path)]
        assert got == want, "%s %s: got %s want %s" % (lang, path, got, want)
    with (ROOT / "ratio_files_other.tsv").open(newline="") as handle:
        rows = [r for r in csv.DictReader(handle, delimiter="\t") if r["language"] in LANGS]
    ledger = json.loads((ROOT / "numbers.json").read_text())["entries"]
    for scope, result in measure_rows(rows).items():
        for lang, values in result.items():
            for key, value in values.items():
                ident = "doc.%s.%s%s" % (lang, scope, key)
                assert ledger[ident]["value"] == value, "%s: %r != %r" % (ident, ledger[ident]["value"], value)
            assert values["public_lines"] + values["private_lines"] + values["unknown_lines"] == values["doc_lines"]
            assert values["doc_lines"] <= values["inclusive_comment_lines"], "doc lines must be comment lines"
            print("%s%s: %s" % (scope or "all.", lang, {k: values[k] for k in (
                "docs", "doc_lines", "public_lines", "private_lines", "unknown_lines", "inclusive_ratio")}))
    print("doc volume other hosts OK")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, ImportError, KeyError, FileNotFoundError) as exc:
        print("FAIL: %s: %s" % (type(exc).__name__, exc))
        sys.exit(1)
