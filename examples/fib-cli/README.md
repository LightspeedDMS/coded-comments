# fib-cli

Exact, arbitrary-precision Fibonacci numbers from the command line. F(0)=0, F(1)=1. Python 3.9+, standard library only.

## Usage

Run from this directory:

```
python -m fib 90                          # F(90)
python -m fib 1000                        # exact, 209 digits
python -m fib --range 10 20               # F(10)..F(20) inclusive, one per line
python -m fib --method doubling 50000     # force an algorithm
python -m fib --method iterative 500
```

## Algorithms

- `iterative`: default for n < 10,000.
- `doubling` (fast doubling): default for n >= 10,000.
- `--method` overrides the choice; both always agree.
- `--range` seeds F(START) and F(START+1) with the chosen method, then produces each following term with a single addition, so large ranges are linear in their length.

## Errors

A negative or non-integer n or range bound, a range whose START exceeds END, a missing or conflicting argument (n together with `--range`), and an unknown `--method` print a message on stderr and exit with code 2. Nothing is written to stdout.

## Library

`fib.core` exposes `fib(n, method=None)`, `fib_iterative`, `fib_doubling`, `fib_range(start, end, method=None)` and `choose_method(n)`.

## Tests

```
python -m pytest
```
