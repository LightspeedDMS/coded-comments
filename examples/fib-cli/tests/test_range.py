import time
import types

import pytest

from fib.core import fib_iterative, fib_range


def test_range_is_inclusive():
    assert list(fib_range(10, 20)) == [55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181, 6765]


def test_range_single_element():
    assert list(fib_range(7, 7)) == [13]


def test_range_from_zero():
    assert list(fib_range(0, 5)) == [0, 1, 1, 2, 3, 5]


@pytest.mark.parametrize("method", [None, "iterative", "doubling"])
@pytest.mark.parametrize("start", [0, 1, 90, 9995, 10000, 20000])
def test_range_matches_single_values(start, method):
    end = start + 12
    assert list(fib_range(start, end, method)) == [fib_iterative(i) for i in range(start, end + 1)]


def test_range_is_lazy():
    gen = fib_range(0, 10**9)
    assert isinstance(gen, types.GeneratorType)
    assert [next(gen) for _ in range(5)] == [0, 1, 1, 2, 3]


def test_range_large_span_is_not_recomputed_per_term():
    started = time.monotonic()
    terms = list(fib_range(0, 20000))
    elapsed = time.monotonic() - started
    assert len(terms) == 20001
    assert terms[-1] == fib_iterative(20000)
    assert elapsed < 5.0


def test_range_rejects_start_greater_than_end():
    with pytest.raises(ValueError, match="start"):
        list(fib_range(5, 4))


def test_range_rejects_negative_start():
    with pytest.raises(ValueError):
        list(fib_range(-1, 3))


def test_range_rejects_non_int():
    with pytest.raises(TypeError):
        list(fib_range(1, 2.5))


def test_range_rejects_unknown_method():
    with pytest.raises(ValueError, match="unknown method"):
        list(fib_range(1, 2, "magic"))


def test_range_validates_eagerly_when_called():
    with pytest.raises(ValueError):
        fib_range(5, 4)
