"""tests.test_fixture_isolation - Verify hermetic standalone fixture discovery."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from dwimsy.tests.fixtures import FixturePool, FixtureSpec


class TestFixtureIsolation(unittest.TestCase):
    def test_constrained_test_root_excludes_cwd_fixture_directory(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as cwd_tmp:
            constrained = Path(tmp)
            cwd = Path(cwd_tmp)
            fixture_dir = cwd / "tests" / "fixtures"
            fixture_dir.mkdir(parents=True)
            fixture = fixture_dir / "private.bin"
            fixture.write_bytes(b"private fixture from surrounding checkout\n")

            import hashlib

            sha1 = hashlib.sha1(fixture.read_bytes()).hexdigest()
            spec = FixtureSpec(
                id="private",
                filename=fixture.name,
                size=fixture.stat().st_size,
                crc32="00000000",
                md5="0" * 32,
                sha1=sha1,
            )
            old_root = os.environ.get("DWIMSY_TEST_REPO_ROOT")
            old_cwd = Path.cwd()
            try:
                os.environ["DWIMSY_TEST_REPO_ROOT"] = str(constrained)
                os.chdir(cwd)
                pool = FixturePool(registry={"private": spec})
                self.assertIsNone(pool.get("private"))
                self.assertNotIn(fixture_dir, pool._scanned_dirs)
            finally:
                os.chdir(old_cwd)
                if old_root is None:
                    os.environ.pop("DWIMSY_TEST_REPO_ROOT", None)
                else:
                    os.environ["DWIMSY_TEST_REPO_ROOT"] = old_root
