#!/usr/bin/env python3
"""tests.test_meta_lint_docstring_identity - Verify relocatable unbundle docstring carve-out and lint invariants."""

import py_compile
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.meta.lint import expected_docstring_identity, lint_headers


def _get_src(rel_path: str) -> str:
    f = pkg_root / rel_path
    if f.is_file():
        return f.read_text(encoding="utf-8")
    from dwimsy.meta import unbundle

    return unbundle.get_asset_text(rel_path)


class TestMetaLintDocstringIdentity(unittest.TestCase):
    def test_positive_relocated_copy_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy_path = Path(tmp) / "standalone_dwimsy.py"
            unbundle_src = _get_src("dwimsy/meta/unbundle.py")
            copy_path.write_text(unbundle_src, encoding="utf-8")

            identity = expected_docstring_identity(copy_path)
            self.assertEqual(identity, "dwimsy.meta.unbundle")

    def test_negative_altered_docstring_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy_path = Path(tmp) / "standalone_dwimsy.py"
            unbundle_src = _get_src("dwimsy/meta/unbundle.py")
            altered = unbundle_src.replace("dwimsy.meta.unbundle -", "wrong.identity -")
            copy_path.write_text(altered, encoding="utf-8")

            identity = expected_docstring_identity(copy_path)
            self.assertEqual(identity, "standalone_dwimsy")

    def test_ordinary_mismatched_path_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy_path = Path(tmp) / "dwimsy" / "core" / "fsk_copy.py"
            copy_path.parent.mkdir(parents=True, exist_ok=True)
            fsk_src = _get_src("dwimsy/core/fsk.py")
            copy_path.write_text(fsk_src, encoding="utf-8")

            identity = expected_docstring_identity(copy_path)
            self.assertEqual(identity, "dwimsy.core.fsk_copy")

    def test_exact_pyc_compile_and_relocate_repro(self):
        with tempfile.TemporaryDirectory() as tmp:
            unbundle_py = pkg_root / "dwimsy" / "meta" / "unbundle.py"
            if not unbundle_py.is_file():
                unbundle_py = Path(tmp) / "unbundle.py"
                unbundle_py.write_text(
                    _get_src("dwimsy/meta/unbundle.py"), encoding="utf-8"
                )
            pyc_dest = Path(tmp) / "dwimsy.pyc"
            py_compile.compile(str(unbundle_py), cfile=str(pyc_dest))

            identity = expected_docstring_identity(pyc_dest)
            self.assertEqual(identity, "dwimsy.meta.unbundle")


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
