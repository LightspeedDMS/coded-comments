import random

import pytest

from fib.core import fib_doubling, fib_iterative

F90 = 2880067194370816120
F1000_PREFIX = "43466557686937456435688527675040625802564660517371780402481729089536555417949051"
SMALL = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
ALGORITHMS = [fib_iterative, fib_doubling]
SAMPLE = [0, 1, 2, 3, 4, 5, 10, 63, 64, 65, 90, 91, 500, 1000, 9999, 10000, 10001, 16383, 16384, 20000]
SAMPLE += random.Random(1234).sample(range(20001), 30)


@pytest.mark.parametrize("algo", ALGORITHMS)
@pytest.mark.parametrize("n,expected", list(enumerate(SMALL)))
def test_small_values(algo, n, expected):
    assert algo(n) == expected


@pytest.mark.parametrize("algo", ALGORITHMS)
def test_f90(algo):
    assert algo(90) == F90


@pytest.mark.parametrize("algo", ALGORITHMS)
def test_f1000_is_exact(algo):
    digits = str(algo(1000))
    assert digits.startswith(F1000_PREFIX)
    assert len(digits) == 209


@pytest.mark.parametrize("algo", ALGORITHMS)
@pytest.mark.parametrize("bad", [-1, -100])
def test_rejects_negative(algo, bad):
    with pytest.raises(ValueError):
        algo(bad)


@pytest.mark.parametrize("algo", ALGORITHMS)
@pytest.mark.parametrize("bad", [1.5, "7", None, True])
def test_rejects_non_int(algo, bad):
    with pytest.raises(TypeError):
        algo(bad)


@pytest.mark.parametrize("n", SAMPLE)
def test_algorithms_agree(n):
    assert fib_doubling(n) == fib_iterative(n)


def test_recurrence_holds_for_doubling_at_large_n():
    n = 20000
    assert fib_doubling(n + 2) == fib_doubling(n + 1) + fib_doubling(n)
