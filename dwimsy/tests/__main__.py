#!/usr/bin/env python3
"""dwimsy.tests.__main__ - In-process CLI test runner for dwimsy.tests."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from dwimsy.tests import run_tests
from dwimsy.meta.integrity import version as get_version


def main(argv: Optional[List[str]] = None) -> int:
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
    args = parser.parse_args(argv)
    rc = run_tests(args.patterns, verbose=args.verbose)
    return rc


if __name__ == "__main__":
    sys.exit(main())
