#!/usr/bin/env python3
"""tests.test_lint_headers - Verify source file sh-bangs, docstrings, and module headers."""

import os
import sys
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.meta.lint import (
    derive_module_name,
    expected_docstring_identity,
    lint_headers,
)


class TestLintHeaders(unittest.TestCase):
    def test_all_non_deps_python_files_conform_to_header_spec(self):
        errors = lint_headers(pkg_root)
        self.assertEqual(errors, [], "Header linting failures:\n" + "\n".join(errors))


def main(argv=None):
    effective = sys.argv[1:] if argv is None else list(argv)
    if any(a in ("-V", "--version") for a in effective):
        from dwimsy.meta.integrity import version as get_version

        print(f"dwimsy {get_version()}")
        return 0
    unittest.main(argv=[sys.argv[0]] + effective)
    return 0


if __name__ == "__main__":
    main()
