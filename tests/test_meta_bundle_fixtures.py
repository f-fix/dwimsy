#!/usr/bin/env python3
"""tests.test_meta_bundle_fixtures - Fixture bundle construction and pool integration tests."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from dwimsy.meta.bundle import build_fixture_bundles
from dwimsy.tests.fixtures import FixturePool


class TestMetaBundleFixtures(unittest.TestCase):
    def make_sources(self, root: Path):
        (root / "one.wav").write_bytes(b"one")
        (root / "two.t88").write_bytes(b"two")
        (root / "three.txt").write_bytes(b"three")

    def test_build_both_formats_and_pool_lazy_materialization(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"
            out = Path(td) / "out"
            root.mkdir()
            self.make_sources(root)
            paths = build_fixture_bundles([root], out)
            self.assertEqual({p.suffix for p in paths}, {".py", ".pyz"})
            py = next(p for p in paths if p.suffix == ".py")
            pool = FixturePool([py])
            sha = hashlib.sha1(b"one").hexdigest()
            self.assertNotIn(sha, pool._materialized)
            got = pool.get("one.wav")
            self.assertIsNotNone(got)
            self.assertEqual(got.read_bytes(), b"one")
            self.assertIn(sha, pool._materialized)

    def test_selector_order_and_sha_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"
            out = Path(td) / "out"
            root.mkdir()
            self.make_sources(root)
            sha = hashlib.sha1(b"one").hexdigest()
            paths = build_fixture_bundles(
                [root],
                out,
                operations=[
                    ("restrict", "ext:wav"),
                    ("include", "two.t88"),
                    ("prune", "sha1:" + sha[:12]),
                ],
                formats="py",
            )
            pool = FixturePool(paths)
            self.assertIsNone(pool.get("one.wav"))
            self.assertIsNotNone(pool.get("two.t88"))
            self.assertIsNone(pool.get("three.txt"))

    def test_fixture_bundle_standalone_unbundle(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"
            out = Path(td) / "out"
            dest = Path(td) / "dest"
            root.mkdir()
            self.make_sources(root)
            py = build_fixture_bundles([root], out, formats="py")[0]
            if (
                sys.platform in ("emscripten", "wasi")
                or os.environ.get("DWIMSY_WITHOUT_SUBPROCESS") == "1"
            ):
                code = py.read_text(encoding="utf-8")
                old_argv = list(sys.argv)
                try:
                    sys.argv = [str(py), "meta", "unbundle", str(dest)]
                    try:
                        exec(
                            compile(code, str(py), "exec"),
                            {"__name__": "__main__", "__file__": str(py)},
                        )
                        rc = 0
                    except SystemExit as e:
                        rc = (
                            e.code
                            if isinstance(e.code, int)
                            else (0 if e.code is None else 1)
                        )
                finally:
                    sys.argv = old_argv
                self.assertEqual(rc, 0)
            else:
                try:
                    proc = subprocess.run(
                        [sys.executable, str(py), "meta", "unbundle", str(dest)],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                except (OSError, NotImplementedError):
                    code = py.read_text(encoding="utf-8")
                    old_argv = list(sys.argv)
                    try:
                        sys.argv = [str(py), "meta", "unbundle", str(dest)]
                        try:
                            exec(
                                compile(code, str(py), "exec"),
                                {"__name__": "__main__", "__file__": str(py)},
                            )
                            rc = 0
                        except SystemExit as e:
                            rc = (
                                e.code
                                if isinstance(e.code, int)
                                else (0 if e.code is None else 1)
                            )
                    finally:
                        sys.argv = old_argv
                    self.assertEqual(rc, 0)
            self.assertEqual((dest / "one.wav").read_bytes(), b"one")


if __name__ == "__main__":
    unittest.main()
