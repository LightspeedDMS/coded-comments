import pytest

from fib.core import choose_method, fib, fib_iterative


@pytest.mark.parametrize("n,expected", [
    (0, "iterative"),
    (90, "iterative"),
    (9999, "iterative"),
    (10000, "doubling"),
    (10001, "doubling"),
    (50000, "doubling"),
])
def test_choose_method_threshold(n, expected):
    assert choose_method(n) == expected


@pytest.mark.parametrize("n", [0, 1, 90, 9999, 10000, 12345])
@pytest.mark.parametrize("method", [None, "iterative", "doubling"])
def test_fib_matches_reference_for_every_method(n, method):
    assert fib(n, method) == fib_iterative(n)


def test_fib_rejects_unknown_method():
    with pytest.raises(ValueError, match="unknown method"):
        fib(10, "magic")


def test_fib_validates_n_regardless_of_method():
    with pytest.raises(ValueError):
        fib(-1, "doubling")
    with pytest.raises(TypeError):
        fib(1.5)
