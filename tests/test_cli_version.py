#!/usr/bin/env python3
"""tests.test_cli_version - Verify CLI version reporting and version strings."""

import io
import sys
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

import dwimsy
from dwimsy.cli.__main__ import main
from dwimsy.meta.integrity import version as get_version


class TestCLIVersion(unittest.TestCase):
    def test_package_dunder_version(self):
        self.assertTrue(hasattr(dwimsy, "__version__"))
        self.assertIsInstance(dwimsy.__version__, str)
        self.assertTrue(len(dwimsy.__version__) > 0)

    def test_cli_version_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            with self.assertRaises(SystemExit) as cm:
                main(["--version"])
        self.assertEqual(cm.exception.code, 0)
        expected = f"dwimsy {get_version()}\n"
        self.assertEqual(buf.getvalue(), expected)

    def test_cli_short_version_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            with self.assertRaises(SystemExit) as cm:
                main(["-V"])
        self.assertEqual(cm.exception.code, 0)
        expected = f"dwimsy {get_version()}\n"
        self.assertEqual(buf.getvalue(), expected)


if __name__ == "__main__":
    unittest.main()
