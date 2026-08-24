#!/usr/bin/env python3
"""tests.test_readme_sync - Verify README documentation and CLI help outputs are in sync."""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.cli.__main__ import main, format_all_help
from dwimsy.cli.filters.t882wav import main as t882wav_main
from dwimsy.cli.filters.wav2t88 import main as wav2t88_main
from dwimsy.tests.__main__ import main as tests_main


class TestReadmeSync(unittest.TestCase):
    def test_readme_contains_cli_help_sections(self):
        readme_text = (pkg_root / "README.md").read_text(encoding="utf-8")

        self.assertIn("usage: dwimsy [-h] [-V] [-T] [--help-all] <command>", readme_text)
        self.assertIn("usage: dwimsy convert", readme_text)
        self.assertIn("usage: dwimsy inspect", readme_text)
        self.assertIn("usage: dwimsy split", readme_text)
        self.assertIn("usage: dwimsy join", readme_text)
        self.assertIn("usage: dwimsy meta", readme_text)
        self.assertIn("usage: dwimsy meta bundle", readme_text)
        self.assertIn("usage: dwimsy meta fetch-deps", readme_text)
        self.assertIn("usage: dwimsy-t882wav", readme_text)
        self.assertIn("usage: dwimsy-wav2t88", readme_text)
        self.assertIn("usage: python -m dwimsy.tests", readme_text)


if __name__ == "__main__":
    unittest.main()
