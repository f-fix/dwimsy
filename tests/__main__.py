#!/usr/bin/env python3
"""tests.__main__ - CLI entrypoint for running dwimsy tests via python3 tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import List, Optional

tests_dir = Path(__file__).resolve().parent
repo_root = tests_dir.parent

if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))

from dwimsy.meta.integrity import version as get_version


class TestProgram(unittest.TestProgram):
    def _do_discovery(self, argv, Loader=None):
        self.start = str(tests_dir)
        self.pattern = "test*.py"
        self.top = str(repo_root)
        if argv is not None:
            if self._discovery_parser is None:
                self._initArgParsers()
            self._discovery_parser.parse_args(argv, self)
        self.createTests(from_discovery=True, Loader=Loader)


def main(argv: Optional[List[str]] = None):
    effective_argv = sys.argv[1:] if argv is None else list(argv)
    if any(arg in ("-V", "--version") for arg in effective_argv):
        print(f"dwimsy {get_version()}")
        return 0
    if any(arg == "--help-all" for arg in effective_argv):
        effective_argv = ["-h" if a == "--help-all" else a for a in effective_argv]
    test_arg = None
    for a in effective_argv:
        if a in ("-T", "--test") or a.startswith("--test="):
            test_arg = a
            break
    if test_arg is not None:
        verbosity = 1
        for a in effective_argv:
            if a in ("-v", "--verbose"):
                verbosity = max(verbosity + 1, 2)
            elif a.startswith("-") and len(a) > 1 and all(c == "v" for c in a[1:]):
                verbosity = max(verbosity + len(a) - 1, 2)
        from dwimsy.tests import run_tests
        pattern = None
        if test_arg.startswith("--test="):
            pattern = [test_arg.split("=", 1)[1]]
        return run_tests(pattern, verbose=verbosity)
    TestProgram(module=None, argv=[sys.argv[0]] + effective_argv)
    return 0


if __name__ == "__main__":
    main()
