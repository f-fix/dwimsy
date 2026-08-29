#!/usr/bin/env python3
"""tests.test_cli_self_location - Verify self-location detection and --argv0 overrides."""

import sys
import tempfile
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.meta.unbundle import detect_self_location


class TestCLISelfLocation(unittest.TestCase):
    def test_real_checkout_detected(self):
        is_checkout, root = detect_self_location(
            str(pkg_root / "dwimsy" / "meta" / "unbundle.py")
        )
        self.assertTrue(is_checkout)
        self.assertEqual(root.resolve(), pkg_root.resolve())

    def test_renamed_copy_detects_non_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            lone_copy = Path(tmp) / "dwimsy_0.1.6.3-dev.py"
            lone_copy.write_bytes(b"")
            is_checkout, root = detect_self_location(str(lone_copy))
            self.assertFalse(is_checkout)

    def test_lone_file_without_siblings_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_unbundle = Path(tmp) / "dwimsy" / "meta" / "unbundle.py"
            fake_unbundle.parent.mkdir(parents=True, exist_ok=True)
            fake_unbundle.write_bytes(b"")
            is_checkout, root = detect_self_location(str(fake_unbundle))
            self.assertFalse(is_checkout)

    def test_argv0_overrides_self_location(self):
        real_unbundle = pkg_root / "dwimsy" / "meta" / "unbundle.py"
        is_checkout, root = detect_self_location(argv0_override=str(real_unbundle))
        self.assertTrue(is_checkout)


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
