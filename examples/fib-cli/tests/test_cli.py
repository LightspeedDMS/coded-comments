import subprocess
import sys
from pathlib import Path

import pytest

from fib.core import fib_iterative

ROOT = Path(__file__).resolve().parent.parent


def run(*args):
    return subprocess.run(
        [sys.executable, "-m", "fib", *args],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
    )


def test_single_value():
    r = run("90")
    assert (r.returncode, r.stdout, r.stderr) == (0, "2880067194370816120\n", "")


@pytest.mark.parametrize("n", [0, 1, 2])
def test_small_values(n):
    r = run(str(n))
    assert (r.returncode, r.stdout) == (0, "%d\n" % fib_iterative(n))


def test_exact_big_value():
    r = run("1000")
    assert r.returncode == 0
    assert r.stdout == "%d\n" % fib_iterative(1000)


def test_range_inclusive_one_per_line():
    r = run("--range", "10", "20")
    assert r.returncode == 0
    assert r.stdout.split("\n") == [
        "55", "89", "144", "233", "377", "610", "987", "1597", "2584", "4181", "6765", "",
    ]


def test_range_single_term():
    assert run("--range", "7", "7").stdout == "13\n"


def test_range_large_runs_quickly_and_is_correct():
    r = run("--range", "0", "20000")
    lines = r.stdout.splitlines()
    assert r.returncode == 0
    assert len(lines) == 20001
    assert lines[-1] == str(fib_iterative(20000))


@pytest.mark.parametrize("method", ["iterative", "doubling"])
def test_method_selection_agrees(method):
    r = run("--method", method, "12345")
    assert (r.returncode, r.stdout) == (0, "%d\n" % fib_iterative(12345))


def test_doubling_50000_output_length():
    r = run("--method", "doubling", "50000")
    assert r.returncode == 0
    assert len(r.stdout) == 10450 + 1


def test_large_n_uses_default_without_flag():
    r = run("20000")
    assert r.stdout == "%d\n" % fib_iterative(20000)


def test_method_applies_to_range():
    r = run("--method", "doubling", "--range", "10", "13")
    assert r.stdout.split() == ["55", "89", "144", "233"]


def assert_rejected(r, fragment):
    assert r.returncode == 2
    assert r.stdout == ""
    assert fragment in r.stderr
    assert "Traceback" not in r.stderr


def test_negative_n():
    assert_rejected(run("-5"), "non-negative")


@pytest.mark.parametrize("bad", ["abc", "1.5", "1e3"])
def test_non_integer_n(bad):
    assert_rejected(run(bad), "integer")


def test_range_start_exceeds_end():
    assert_rejected(run("--range", "20", "10"), "start")


def test_range_negative_bound():
    assert_rejected(run("--range", "-1", "5"), "non-negative")


def test_range_non_integer_bound():
    assert_rejected(run("--range", "1", "x"), "integer")


def test_no_arguments():
    assert_rejected(run(), "n")


def test_n_and_range_together():
    assert_rejected(run("5", "--range", "1", "2"), "not both")


def test_range_needs_two_values():
    assert_rejected(run("--range", "3"), "--range")


def test_invalid_method():
    assert_rejected(run("--method", "magic", "5"), "magic")
