#!/usr/bin/env python3
"""tests.test_lint_filenames - Verify NFKC casefolded collision detection and filename portability."""

import sys
import tempfile
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.meta.lint import lint_filenames


class TestLintFilenames(unittest.TestCase):
    def test_nfkc_casefold_filename_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dwimsy").mkdir()
            (root / "dwimsy" / "test.py").write_text("")
            (root / "dwimsy" / "TEST.py").write_text("")

            errors = lint_filenames(root)
            self.assertTrue(any("Filename collision" in e for e in errors))

    def test_fullwidth_A_collides_with_ascii_a(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dwimsy").mkdir()
            (root / "dwimsy" / "a.py").write_text("")
            (root / "dwimsy" / "\uff21.py").write_text("")

            errors = lint_filenames(root)
            self.assertTrue(any("Filename collision" in e for e in errors))

    def test_current_repo_filenames_conform(self):
        errors = lint_filenames(pkg_root)
        self.assertEqual(errors, [])


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
