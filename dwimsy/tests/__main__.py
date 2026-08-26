#!/usr/bin/env python3
"""dwimsy.tests.__main__ - In-process CLI test runner for dwimsy.tests."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from dwimsy.tests import list_tests, run_tests
from dwimsy.meta.integrity import version as get_version


def main(argv: Optional[List[str]] = None) -> int:
    effective = sys.argv[1:] if argv is None else list(argv)

    test_arg = None
    for a in effective:
        if a in ("-T", "--test") or a.startswith("--test="):
            test_arg = a
            break
    if test_arg is not None:
        verbosity = 1
        for a in effective:
            if a in ("-v", "--verbose"):
                verbosity = max(verbosity + 1, 2)
            elif a.startswith("-") and len(a) > 1 and all(c == "v" for c in a[1:]):
                verbosity = max(verbosity + len(a) - 1, 2)
        pattern = None
        if test_arg.startswith("--test="):
            pattern = [test_arg.split("=", 1)[1]]
        else:
            pattern = ["tests"]
        return run_tests(pattern, verbose=verbosity)

    if any(a == "--help-all" for a in effective):
        effective = ["-h" if a == "--help-all" else a for a in effective]

    parser = argparse.ArgumentParser(
        prog="python -m dwimsy.tests",
        description="Discover and run dwimsy unit tests in-process (from disk or in-memory bundle payload).",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
    )
    parser.add_argument(
        "-T",
        "--test",
        nargs="?",
        const=True,
        default=False,
        help="Run unit tests in-process (optional pattern filter)",
    )
    parser.add_argument(
        "patterns",
        nargs="*",
        default=None,
        help="Optional test file patterns or subsystem keywords (e.g. 'core', 'tape', 'convert')",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=1,
        help="Increase test runner verbosity",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List discovered unit test IDs without running them",
    )
    parser.add_argument(
        "--help-all",
        action="store_true",
        help="Show full help documentation and exit",
    )
    args = parser.parse_args(effective)

    if args.list:
        tests_found = list_tests(args.patterns)
        for tid in tests_found:
            print(tid)
        return 0

    if args.test is not False:
        patterns = [args.test] if isinstance(args.test, str) else args.patterns
    else:
        patterns = args.patterns

    rc = run_tests(patterns, verbose=args.verbose)
    return rc


if __name__ == "__main__":
    sys.exit(main())
