import argparse
import sys

from .core import METHODS, fib, fib_range


def _non_negative_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("%r is not an integer" % text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer, got %d" % value)
    return value


def build_parser():
    parser = argparse.ArgumentParser(prog="fib", description="Print Fibonacci numbers (exact, arbitrary precision).")
    parser.add_argument("n", nargs="?", type=_non_negative_int, help="print F(n)")
    parser.add_argument("--range", nargs=2, type=_non_negative_int, metavar=("START", "END"),
                        help="print F(START)..F(END) inclusive, one per line")
    parser.add_argument("--method", choices=sorted(METHODS),
                        help="algorithm (default: iterative below 10000, doubling from 10000)")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.n is not None and args.range is not None:
        parser.error("give either n or --range START END, not both")
    if args.n is None and args.range is None:
        parser.error("n is required (or use --range START END)")
    if args.range is not None:
        start, end = args.range
        if start > end:
            parser.error("start (%d) must not exceed end (%d)" % (start, end))
        for term in fib_range(start, end, args.method):
            sys.stdout.write("%d\n" % term)
    else:
        sys.stdout.write("%d\n" % fib(args.n, args.method))
    return 0
