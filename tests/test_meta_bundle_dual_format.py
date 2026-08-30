#!/usr/bin/env python3
"""tests.test_meta_bundle_dual_format - Verify dual format .py + .pyz bundle emission and -o flag."""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.meta import bundle, integrity


@unittest.skipIf(
    os.environ.get("DWIMSY_BUNDLE_BUILD") == "1",
    "Excluded during bundle build verification",
)
class TestMetaBundleDualFormat(unittest.TestCase):
    def test_default_emits_py_and_pyz(self):
        with tempfile.TemporaryDirectory() as tmp:
            cur = os.getcwd()
            try:
                os.chdir(tmp)
                (Path(tmp) / "dwimsy").mkdir()
                (Path(tmp) / "dwimsy" / "__init__.py").write_bytes(b"")
                (Path(tmp) / "dwimsy" / "_version.py").write_bytes(
                    (pkg_root / "dwimsy" / "_version.py").read_bytes()
                )
                (Path(tmp) / "dwimsy" / "meta").mkdir()
                (Path(tmp) / "dwimsy" / "meta" / "__init__.py").write_bytes(b"")
                (Path(tmp) / "dwimsy" / "meta" / "unbundle.py").write_bytes(
                    (pkg_root / "dwimsy" / "meta" / "unbundle.py").read_bytes()
                )
                (Path(tmp) / "tests").mkdir()

                rc = bundle.main([])
                self.assertEqual(rc, 0)

                files = [p.name for p in Path(tmp).iterdir() if p.is_file()]
                py_files = [f for f in files if f.endswith(".py")]
                pyz_files = [f for f in files if f.endswith(".pyz")]
                self.assertTrue(len(py_files) >= 1)
                self.assertTrue(len(pyz_files) >= 1)
            finally:
                os.chdir(cur)

    def test_explicit_output_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_py = Path(tmp) / "custom.py"
            rc = bundle.main(["-o", str(out_py)])
            self.assertEqual(rc, 0)
            self.assertTrue(out_py.is_file())

            out_pyz = Path(tmp) / "custom.pyz"
            rc_z = bundle.main(["-o", str(out_pyz)])
            self.assertEqual(rc_z, 0)
            self.assertTrue(out_pyz.is_file())

    def test_invalid_extension_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_bad = Path(tmp) / "custom.tar"
            err = io.StringIO()
            old_err = sys.stderr
            sys.stderr = err
            try:
                rc = bundle.main(["-o", str(out_bad)])
            finally:
                sys.stderr = old_err
            self.assertEqual(rc, 1)
            self.assertIn("error: unsupported output extension '.tar'", err.getvalue())


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
