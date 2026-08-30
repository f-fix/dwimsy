#!/usr/bin/env python3
"""tests.test_meta_bundle - Verify dwimsy meta bundling and unbundling machinery."""

import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.cli import main as dwimsy_cli_main
from dwimsy.meta import bundle, integrity, unbundle


@unittest.skipIf(
    os.environ.get("DWIMSY_BUNDLE_BUILD") == "1",
    "Excluded during bundle build verification",
)
class TestMetaBundle(unittest.TestCase):
    def test_unbundle_asset_readers(self):
        assets = unbundle.list_assets()
        self.assertIn("README.md", assets)
        self.assertIn("CHANGELOG.md", assets)
        self.assertIn("LICENSE", assets)
        self.assertIn("deps/bin2fds/bin2fds.py", assets)

        readme_text = unbundle.get_asset_text("README.md")
        self.assertTrue(readme_text.startswith("# dwimsy"))

        license_bytes = unbundle.get_asset("LICENSE")
        self.assertTrue(len(license_bytes) > 0)

        dep_code = unbundle.get_asset_text("deps/bin2fds/bin2fds.py")
        self.assertIn("def bin2fds", dep_code)

        with self.assertRaises(FileNotFoundError):
            unbundle.get_asset("non_existent_file_xyz.txt")

    def test_unbundle_extract_default_excludes_deps(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            unbundle.extract_b64_lzma_tar(unbundle.blztar, tmp_path, with_deps=False)

            self.assertTrue((tmp_path / "README.md").is_file())
            self.assertTrue((tmp_path / "dwimsy" / "__init__.py").is_file())
            self.assertTrue((tmp_path / "dwimsy" / "meta" / "unbundle.py").is_file())
            self.assertFalse((tmp_path / "deps").exists())

    def test_unbundle_extract_with_deps_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            unbundle.extract_b64_lzma_tar(unbundle.blztar, tmp_path, with_deps=True)

            self.assertTrue((tmp_path / "README.md").is_file())
            self.assertTrue((tmp_path / "dwimsy" / "__init__.py").is_file())
            self.assertTrue((tmp_path / "deps" / "bin2fds" / "bin2fds.py").is_file())

    def test_unbundle_extract_deps_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            unbundle.extract_b64_lzma_tar(unbundle.blztar, tmp_path, with_deps=False)
            self.assertFalse((tmp_path / "deps").exists())

            extracted = unbundle.extract_deps(tmp_path)
            self.assertTrue(len(extracted) > 0)
            self.assertTrue((tmp_path / "deps" / "bin2fds" / "bin2fds.py").is_file())

    def test_bundle_build_script_fallback_without_deps_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            unbundle.extract_b64_lzma_tar(unbundle.blztar, tmp_path, with_deps=False)
            self.assertFalse((tmp_path / "deps").exists())

            # Building bundle from clean tree without deps/ on disk must still embed deps/
            script = bundle.build_bundle_script(tmp_path, with_deps=True, preset=1)
            self.assertTrue(script.startswith("#!/usr/bin/env python3"))
            self.assertIn('blztar = """', script)
            self.assertIn("def extract_b64_lzma_tar", script)

            # Unpack the generated bundle with deps and verify deps exist
            dest_unpack = tmp_path / "unpacked_from_clean"
            out_bundle = tmp_path / "clean_bundle.py"
            out_bundle.write_text(script, encoding="utf-8")
            res = subprocess.run(
                [
                    sys.executable,
                    str(out_bundle),
                    "meta",
                    "unbundle",
                    str(dest_unpack),
                    "--deps",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0)
            self.assertTrue((dest_unpack / "deps" / "bin2fds" / "bin2fds.py").is_file())

    def test_cli_meta_fetch_deps_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            unbundle.extract_b64_lzma_tar(unbundle.blztar, tmp_path, with_deps=False)
            self.assertFalse((tmp_path / "deps").exists())

            buf = io.StringIO()
            err = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(err):
                cur = os.getcwd()
                try:
                    os.chdir(tmp_path)
                    try:
                        dwimsy_cli_main(["meta", "fetch-deps", "--version=baseline"])
                    except SystemExit as e:
                        self.assertEqual(e.code, 0)
                finally:
                    os.chdir(cur)

            self.assertTrue((tmp_path / "deps").is_dir())
            self.assertTrue((tmp_path / "deps" / "bin2fds" / "bin2fds.py").is_file())

    def test_cli_meta_bundle_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_bundle = tmp_path / "test_bundle.py"
            buf = io.StringIO()
            err = io.StringIO()

            with redirect_stdout(buf), redirect_stderr(err):
                dwimsy_cli_main(["meta", "bundle", "-o", str(out_bundle)])

            self.assertTrue(out_bundle.is_file())
            self.assertTrue(os.access(str(out_bundle), os.X_OK))

            clean_env = dict(os.environ)
            clean_env.pop("DWIMSY_TEST_REPO_ROOT", None)

            # Test default unpacking (no deps)
            dest_unpack = tmp_path / "unpacked_dest"
            res = subprocess.run(
                [sys.executable, str(out_bundle), "meta", "unbundle", str(dest_unpack)],
                capture_output=True,
                text=True,
                env=clean_env,
            )
            self.assertEqual(res.returncode, 0)
            self.assertTrue((dest_unpack / "README.md").is_file())
            self.assertTrue((dest_unpack / "dwimsy" / "meta" / "unbundle.py").is_file())
            self.assertFalse((dest_unpack / "deps").exists())

            # Test unpacking with --deps
            dest_unpack_deps = tmp_path / "unpacked_dest_deps"
            res_d = subprocess.run(
                [
                    sys.executable,
                    str(out_bundle),
                    "meta",
                    "unbundle",
                    str(dest_unpack_deps),
                    "--deps",
                ],
                capture_output=True,
                text=True,
                env=clean_env,
            )
            self.assertEqual(res_d.returncode, 0)
            self.assertTrue(
                (dest_unpack_deps / "deps" / "bin2fds" / "bin2fds.py").is_file()
            )

            # Test CLI version in unpacked destination
            res_v = subprocess.run(
                [sys.executable, "-m", "dwimsy", "--version"],
                cwd=str(dest_unpack),
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_v.returncode, 0)
            self.assertIn("dwimsy ", res_v.stdout)

    def test_cli_meta_bundle_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_bundle = tmp_path / "baseline_bundle.py"
            buf = io.StringIO()
            err = io.StringIO()

            with redirect_stdout(buf), redirect_stderr(err):
                try:
                    dwimsy_cli_main(
                        ["meta", "bundle", "--version=baseline", "-o", str(out_bundle)]
                    )
                except SystemExit as e:
                    self.assertEqual(e.code, 0)

            self.assertTrue(out_bundle.is_file())
            self.assertTrue(
                out_bundle.read_text(encoding="utf-8").startswith(
                    "#!/usr/bin/env python3"
                )
            )

    def test_unbundle_reconstitutes_self_from_embedded_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "tree"
            script = bundle.build_bundle_script(
                integrity.find_repo_root(), with_deps=False, preset=0
            )
            match = re.search(r'blztar = """\n([A-Za-z0-9+/\n=]+)\n"""', script)
            self.assertIsNotNone(match)
            payload = match.group(1)
            unbundle.extract_b64_lzma_tar(payload, target, with_deps=False)
            restored = target / "dwimsy" / "meta" / "unbundle.py"
            with unbundle._open_bundle_tar(payload) as tar:
                member = next(
                    m
                    for m in tar.getmembers()
                    if (m.name[2:] if m.name.startswith("./") else m.name)
                    == "dwimsy/meta/unbundle.py"
                )
                template = tar.extractfile(member).read()
                mtime = member.mtime
            self.assertEqual(
                unbundle.elide_blztar_bytes(restored.read_bytes()), template
            )
            self.assertEqual(int(restored.stat().st_mtime), int(mtime))

    def test_cli_meta_bundle_verbose(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_bundle = tmp_path / "test_bundle_verbose.py"
            buf = io.StringIO()
            err = io.StringIO()

            with redirect_stdout(buf), redirect_stderr(err):
                dwimsy_cli_main(["meta", "bundle", "-o", str(out_bundle), "--verbose"])

            self.assertTrue(out_bundle.is_file())
            err_output = err.getvalue()
            self.assertIn("[SUCCESS] Generated bundle", err_output)

    def test_cli_meta_diff_writes_stdout(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            dwimsy_cli_main(["meta", "diff"])
        self.assertIsInstance(buf.getvalue(), str)

    def test_cli_meta_unbundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = tmp_path / "extracted_via_cli"
            buf = io.StringIO()
            with redirect_stdout(buf):
                dwimsy_cli_main(["meta", "unbundle", str(out_dir)])
            self.assertTrue(out_dir.is_dir())
            self.assertTrue((out_dir / "README.md").is_file())
            self.assertTrue((out_dir / "dwimsy" / "__init__.py").is_file())
            self.assertTrue((out_dir / "dwimsy" / "meta" / "unbundle.py").is_file())
            self.assertIn("Successfully extracted to", buf.getvalue())

    def test_unbundle_is_unbundle_invocation_pattern(self):
        self.assertTrue(unbundle.is_unbundle_invocation("unbundle"))
        self.assertTrue(unbundle.is_unbundle_invocation("unbundle.py"))
        self.assertTrue(unbundle.is_unbundle_invocation("/path/to/unbundle.py"))
        self.assertTrue(unbundle.is_unbundle_invocation("dwimsy-unbundle"))
        self.assertTrue(unbundle.is_unbundle_invocation("dwimsy-meta-unbundle"))
        self.assertTrue(unbundle.is_unbundle_invocation("dwimsy.meta.unbundle"))
        self.assertFalse(unbundle.is_unbundle_invocation("dwimsy"))
        self.assertFalse(unbundle.is_unbundle_invocation("dwimsy.py"))
        self.assertFalse(unbundle.is_unbundle_invocation("/usr/local/bin/dwimsy"))
        self.assertFalse(unbundle.is_unbundle_invocation("dwimsy_0.1.6.0-dev.py"))

    def test_integrity_hash_ignores_unbundle(self):
        h1 = integrity.canonical_code_hash()
        source_files = integrity.source_files()
        self.assertNotIn(
            "dwimsy/meta/unbundle.py", [p.as_posix() for p in source_files]
        )
        self.assertEqual(h1, integrity.canonical_code_hash())


def main(argv=None):
    import sys

    effective = sys.argv[1:] if argv is None else list(argv)
    if any(a in ("-V", "--version") for a in effective):
        from dwimsy.meta.integrity import version as get_version

        print(f"dwimsy {get_version()}")
        return 0
    unittest.main(argv=[sys.argv[0]] + effective)
    return 0


if __name__ == "__main__":
    main()
