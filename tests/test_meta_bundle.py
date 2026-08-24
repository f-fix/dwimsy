#!/usr/bin/env python3
"""tests.test_meta_bundle - verify dwimsy meta bundling and unbundling machinery."""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.cli.main import main
from dwimsy.meta import bundle, integrity, unbundle


class TestMetaBundle(unittest.TestCase):
    def test_unbundle_asset_readers(self):
        assets = unbundle.list_assets()
        self.assertIn("README.md", assets)
        self.assertIn("LICENSE", assets)

        readme_text = unbundle.get_asset_text("README.md")
        self.assertTrue(readme_text.startswith("# dwimsy"))

        license_bytes = unbundle.get_asset("LICENSE")
        self.assertTrue(len(license_bytes) > 0)

        with self.assertRaises(FileNotFoundError):
            unbundle.get_asset("non_existent_file_xyz.txt")

    def test_unbundle_extract_all_and_self_reconstitution(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            unbundle.extract_b64_lzma_tar(unbundle.blztar, tmp_path)

            self.assertTrue((tmp_path / "README.md").is_file())
            self.assertTrue((tmp_path / "dwimsy" / "__init__.py").is_file())
            self.assertTrue((tmp_path / "dwimsy" / "meta" / "unbundle.py").is_file())

    def test_bundle_build_script(self):
        root = bundle.find_repo_root()
        script = bundle.build_bundle_script(root, with_deps=False, preset=1)
        self.assertTrue(script.startswith("#!/usr/bin/env python3"))
        self.assertIn('blztar = """', script)
        self.assertIn("def extract_b64_lzma_tar", script)

    def test_cli_meta_bundle_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_bundle = tmp_path / "test_bundle.py"
            buf = io.StringIO()
            err = io.StringIO()

            with redirect_stdout(buf), redirect_stderr(err):
                main(["meta", "bundle", "-o", str(out_bundle)])

            self.assertTrue(out_bundle.is_file())
            self.assertTrue(os.access(str(out_bundle), os.X_OK))

            # Test unpacking the generated bundle in another directory
            dest_unpack = tmp_path / "unpacked_dest"
            res = subprocess.run([sys.executable, str(out_bundle), str(dest_unpack)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertTrue((dest_unpack / "README.md").is_file())
            self.assertTrue((dest_unpack / "dwimsy" / "meta" / "unbundle.py").is_file())

            # Test CLI version in unpacked destination
            res_v = subprocess.run([sys.executable, "-m", "dwimsy", "--version"], cwd=str(dest_unpack), capture_output=True, text=True)
            self.assertEqual(res_v.returncode, 0)
            self.assertIn("dwimsy ", res_v.stdout)

    def test_cli_meta_bundle_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_bundle = tmp_path / "baseline_bundle.py"
            buf = io.StringIO()
            err = io.StringIO()

            with redirect_stdout(buf), redirect_stderr(err):
                main(["meta", "bundle", "--baseline", "-o", str(out_bundle)])

            self.assertTrue(out_bundle.is_file())
            self.assertEqual(out_bundle.read_text(encoding="utf-8"), Path(unbundle.__file__).read_text(encoding="utf-8"))

    def test_integrity_hash_ignores_unbundle(self):
        h1 = integrity.canonical_code_hash()
        source_files = integrity.source_files()
        self.assertNotIn("dwimsy/meta/unbundle.py", [p.as_posix() for p in source_files])
        self.assertEqual(h1, integrity.canonical_code_hash())


if __name__ == "__main__":
    unittest.main()
