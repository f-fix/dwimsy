#!/usr/bin/env python3
"""tests.test_cli_quiet_version_list - Test Tier 1 -q/--quiet flag with --version-list."""

import subprocess
import sys
import unittest
from pathlib import Path


class TestCliQuietVersionList(unittest.TestCase):
    def test_quiet_version_list(self):
        repo_root = Path(__file__).resolve().parent.parent
        cmd = [sys.executable, "-m", "dwimsy", "-q", "--version-list"]
        cp = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)
        self.assertEqual(cp.returncode, 0)
        lines = cp.stdout.strip().splitlines()
        self.assertTrue(len(lines) > 5)
        for l in lines:
            self.assertTrue(l.strip().startswith("[primary]"))
            self.assertNotIn("[=primary:", l)
            self.assertNotIn("=selected", l)
            self.assertNotIn("=baseline", l)

    def test_verbose_quiet_version_list(self):
        repo_root = Path(__file__).resolve().parent.parent
        cmd = [sys.executable, "-m", "dwimsy", "--verbose", "--quiet", "--version-list"]
        cp = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)
        self.assertEqual(cp.returncode, 0)
        lines = cp.stdout.strip().splitlines()
        for l in lines:
            parts = l.strip().split()
            self.assertEqual(len(parts), 4)
            self.assertEqual(len(parts[3]), 64)


if __name__ == "__main__":
    unittest.main()
