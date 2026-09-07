#!/usr/bin/env python3
"""tests.test_unbundle_rollback_instructions - Test unbundle rollback instructions and timestamps."""

import unittest, subprocess, sys, tempfile, shutil, os
from pathlib import Path


@unittest.skipIf(
    os.environ.get("DWIMSY_BUNDLE_BUILD") == "1"
    or os.environ.get("DWIMSY_STANDALONE_TEST") == "1",
    "Excluded during bundle build verification",
)
class TestRollbackInstructionsAndTimestamps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dwimsy_test_rb_"))
        cls.bundle_path = cls.temp_dir / "dwimsy_test_bundle.py"
        src_dir = Path(__file__).resolve().parents[1]
        subprocess.run(
            [
                sys.executable,
                "-m",
                "dwimsy.meta.bundle",
                "-o",
                str(cls.bundle_path),
                "--with-deps",
            ],
            cwd=str(src_dir),
            check=True,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_version_list_timestamps(self):
        res = subprocess.run(
            [sys.executable, str(self.bundle_path), "--version-list"],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = res.stdout.splitlines()
        timestamps = set()
        for line in lines:
            parts = line.split()
            if len(parts) >= 3 and parts[2].endswith("Z"):
                timestamps.add(parts[2])
        self.assertGreater(
            len(timestamps), 3, "Expected multiple distinct timestamps across layers"
        )
        self.assertTrue(any("2026-09-06" in ts for ts in timestamps))
        self.assertTrue(
            any(
                "2026-08-29" in ts or "2026-08-30" in ts or "2026-08-31" in ts
                for ts in timestamps
            )
        )

    def test_upgrade_prints_rollback_instructions(self):
        target_dir = self.temp_dir / "checkout_upgrade"
        target_dir.mkdir(parents=True, exist_ok=True)
        # Setup clean 0.1.6.70
        subprocess.run(
            [
                sys.executable,
                str(self.bundle_path),
                "--version=0.1.6.70-dev",
                "meta",
                "unbundle",
                str(target_dir),
                "--deps",
                "--force",
                "--quiet",
            ],
            check=True,
        )
        # Upgrade to latest
        res = subprocess.run(
            [
                sys.executable,
                str(self.bundle_path),
                "meta",
                "unbundle",
                str(target_dir),
                "--deps",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn(
            "To roll back to previous version '0.1.6.70-dev', run: python3", res.stdout
        )
        self.assertIn("--version=0.1.6.70-dev", res.stdout)

    def test_destructive_rollback_requires_force_or_alt(self):
        target_dir = self.temp_dir / "checkout_rollback"
        target_dir.mkdir(parents=True, exist_ok=True)
        # Setup clean head
        subprocess.run(
            [
                sys.executable,
                str(self.bundle_path),
                "meta",
                "unbundle",
                str(target_dir),
                "--deps",
                "--force",
                "--quiet",
            ],
            check=True,
        )
        # Unsafe rollback without --force or --version-alt should fail
        res = subprocess.run(
            [
                sys.executable,
                str(self.bundle_path),
                "--version=0.1.6.70-dev",
                "meta",
                "unbundle",
                str(target_dir),
                "--deps",
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("discard information", res.stderr)

        # Forced rollback should succeed and state no undo available
        res_forced = subprocess.run(
            [
                sys.executable,
                str(self.bundle_path),
                "--version=0.1.6.70-dev",
                "--force",
                "meta",
                "unbundle",
                str(target_dir),
                "--deps",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("No undo command is available", res_forced.stdout)

        # Rollback with --version-alt should succeed and print roll-forward command
        target_dir_alt = self.temp_dir / "checkout_alt"
        target_dir_alt.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                sys.executable,
                str(self.bundle_path),
                "meta",
                "unbundle",
                str(target_dir_alt),
                "--deps",
                "--force",
                "--quiet",
            ],
            check=True,
        )
        res_alt = subprocess.run(
            [
                sys.executable,
                str(self.bundle_path),
                "--version-alt",
                "--version=0.1.6.70-dev",
                "meta",
                "unbundle",
                str(target_dir_alt),
                "--deps",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("To roll forward to it, run:", res_alt.stdout)


if __name__ == "__main__":
    unittest.main()
