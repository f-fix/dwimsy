#!/usr/bin/env python3
"""tests.__main__ - Test runner entry point for the tests package."""

import sys
import unittest

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(start_dir=".", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
