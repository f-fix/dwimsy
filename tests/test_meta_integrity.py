#!/usr/bin/env python3
"""tests.test_meta_integrity - verify dwimsy file and package integrity mechanisms"""

import os
import tempfile
import unittest
from pathlib import Path

from dwimsy.meta import integrity


class IntegrityTests(unittest.TestCase):
    def test_hash_is_stable(self):
        self.assertEqual(integrity.canonical_code_hash(), integrity.canonical_code_hash())
        self.assertEqual(len(integrity.canonical_code_hash()), 64)

    def test_version_hash_sentinel_does_not_self_modify(self):
        root = Path(integrity.package_root())
        version_file = root / "_version.py"
        original = version_file.read_bytes()
        try:
            h1 = integrity.canonical_code_hash()
            version_file.write_bytes(
                original.replace(b'__code_hash__ = ""', b'__code_hash__ = "deadbeef"')
            )
            h2 = integrity.canonical_code_hash()
            self.assertEqual(h1, h2)
        finally:
            version_file.write_bytes(original)

    def test_line_endings_are_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_version.py").write_bytes(b'__version__ = "x"\r\n__code_hash__ = "abc"\r\n')
            (root / "a.py").write_bytes(b"x = 1\r\ny = 2\r\n")
            h_crlf = integrity.canonical_code_hash(root)
            (root / "a.py").write_bytes(b"x = 1\ny = 2\n")
            h_lf = integrity.canonical_code_hash(root)
            self.assertEqual(h_crlf, h_lf)

    def test_path_order_is_canonical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_version.py").write_text('__version__ = "x"\n__code_hash__ = ""\n', encoding="utf-8")
            (root / "z.py").write_text("z = 1\n", encoding="utf-8")
            (root / "a.py").write_text("a = 1\n", encoding="utf-8")
            self.assertEqual(
                tuple(p.relative_to(root).as_posix() for p in integrity.source_files(root)),
                ("_version.py", "a.py", "z.py"),
            )

    def test_unbundle_module_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_version.py").write_text('__version__ = "x"\n__code_hash__ = ""\n', encoding="utf-8")
            (root / "a.py").write_text("a = 1\n", encoding="utf-8")
            h1 = integrity.canonical_code_hash(root)
            (root / "unbundle.py").write_text('blztar = "xyz"\n', encoding="utf-8")
            h2 = integrity.canonical_code_hash(root)
            self.assertEqual(h1, h2)

    def test_unsealed_tree_is_modified(self):
        self.assertEqual(integrity.sealed_code_hash(), "")
        self.assertTrue(integrity.is_modified())
        self.assertIn("+mod.", integrity.version())


if __name__ == "__main__":
    unittest.main()
