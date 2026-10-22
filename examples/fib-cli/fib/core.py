"""Fibonacci algorithms: F(0)=0, F(1)=1, arbitrary precision."""


def _validate(n):
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("n must be an integer, got %s" % type(n).__name__)
    if n < 0:
        raise ValueError("n must be non-negative, got %d" % n)


def fib_iterative(n):
    _validate(n)
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _pair_doubling(n):
    """Return (F(n), F(n+1)) by fast doubling, consuming the bits of n from the top."""
    a, b = 0, 1
    for bit in bin(n)[2:]:
        c = a * (2 * b - a)
        d = a * a + b * b
        if bit == "1":
            a, b = d, c + d
        else:
            a, b = c, d
    return a, b


def fib_doubling(n):
    _validate(n)
    return _pair_doubling(n)[0]


DOUBLING_THRESHOLD = 10000
METHODS = {"iterative": fib_iterative, "doubling": fib_doubling}


def choose_method(n):
    return "doubling" if n >= DOUBLING_THRESHOLD else "iterative"


def _resolve_method(n, method):
    if method is None:
        return choose_method(n)
    if method not in METHODS:
        raise ValueError("unknown method %r (expected one of: %s)" % (method, ", ".join(METHODS)))
    return method


def fib(n, method=None):
    _validate(n)
    return METHODS[_resolve_method(n, method)](n)


def fib_range(start, end, method=None):
    """Validate eagerly, then yield F(start)..F(end) inclusive, one addition per term."""
    _validate(start)
    _validate(end)
    if start > end:
        raise ValueError("start (%d) must not exceed end (%d)" % (start, end))
    method = _resolve_method(start, method)
    return _walk(METHODS[method](start), METHODS[method](start + 1), end - start + 1)


def _walk(a, b, count):
    for _ in range(count):
        yield a
        a, b = b, a + b
