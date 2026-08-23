#!/usr/bin/env python3

"""CLI entrypoint for running dwimsy tests via `python3 tests`."""

import sys
import unittest
from pathlib import Path

tests_dir = Path(__file__).resolve().parent
repo_root = tests_dir.parent

# Ensure repository root and dependencies are on sys.path
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))

deps_pc88_dir = repo_root / "deps" / "pc88_tape_tools"
if str(deps_pc88_dir) not in sys.path:
    sys.path.insert(0, str(deps_pc88_dir))


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


if __name__ == "__main__":
    TestProgram(module=None)
