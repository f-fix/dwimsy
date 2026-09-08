#!/usr/bin/env python3
"""tests.test_cli_version - Verify dwimsy CLI version reporting and endpoint consistency."""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

import dwimsy
from dwimsy.cli import main as dwimsy_cli_main
from dwimsy.cli.filters import t882wav as t882wav_mod
from dwimsy.cli.filters import wav2t88 as wav2t88_mod
from dwimsy.meta import __main__ as meta_main_mod
from dwimsy.meta import bundle as bundle_mod
from dwimsy.meta import unbundle as unbundle_mod
from dwimsy.meta import diff as diff_mod
from dwimsy.meta import integrity as integrity_mod
from dwimsy.meta import version_bump as version_bump_mod
from dwimsy.meta import lint as lint_mod
from dwimsy.tests import __main__ as dw_tests_main_mod
from tests import __main__ as tests_main_mod
from dwimsy.meta.integrity import version as get_version


class TestCLIVersion(unittest.TestCase):
    def test_package_dunder_version(self):
        self.assertTrue(hasattr(dwimsy, "__version__"))
        self.assertIsInstance(dwimsy.__version__, str)
        self.assertTrue(len(dwimsy.__version__) > 0)

    def test_cli_version_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            try:
                rc = dwimsy_cli_main(["--version"])
            except SystemExit as e:
                rc = e.code
        self.assertEqual(rc, 0)
        self.assertIn("dwimsy ", buf.getvalue())

    def test_cli_short_version_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            try:
                rc = dwimsy_cli_main(["-V"])
            except SystemExit as e:
                rc = e.code
        self.assertEqual(rc, 0)
        self.assertIn("dwimsy ", buf.getvalue())

    def test_all_cli_modules_implement_main_and_version(self):
        expected_v = f"{get_version()}"
        cli_modules = [
            ("dwimsy.cli", dwimsy_cli_main),
            ("dwimsy.cli.filters.t882wav", t882wav_mod.main),
            ("dwimsy.cli.filters.wav2t88", wav2t88_mod.main),
            ("dwimsy.meta", meta_main_mod.main),
            ("dwimsy.meta.bundle", bundle_mod.main),
            ("dwimsy.meta.unbundle", unbundle_mod.main),
            ("dwimsy.meta.diff", diff_mod.main),
            ("dwimsy.meta.integrity", integrity_mod.main),
            ("dwimsy.meta.version_bump", version_bump_mod.main),
            ("dwimsy.meta.lint", lint_mod.main),
            ("dwimsy.tests", dw_tests_main_mod.main),
            ("tests", tests_main_mod.main),
        ]

        for mod_name, main_fn in cli_modules:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                try:
                    rc = main_fn(["--version"])
                except SystemExit as e:
                    rc = e.code
            out = buf.getvalue().strip()
            self.assertEqual(
                rc, 0, f"{mod_name} --version returned non-zero exit code {rc}"
            )
            self.assertIn(
                expected_v,
                out,
                f"{mod_name} --version output '{out}' missing expected '{expected_v}'",
            )

    def test_cli_version_default_short_hash_and_timestamp(self):
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            try:
                dwimsy_cli_main(["--version"])
            except SystemExit as e:
                pass
        out = buf.getvalue().strip()
        self.assertRegex(
            out, r"^dwimsy \S+ \(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z [0-9a-f]{12}\)$"
        )

    def test_cli_version_verbose_full_hash(self):
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            try:
                dwimsy_cli_main(["--version", "--verbose"])
            except SystemExit as e:
                pass
        out = buf.getvalue().strip()
        self.assertRegex(
            out, r"^dwimsy \S+ \(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z [0-9a-f]{64}\)$"
        )

    @unittest.skipIf(
        os.environ.get("DWIMSY_BUNDLE_BUILD") == "1",
        "Excluded during bundle build verification",
    )
    def test_cli_version_clean_unbundled_has_no_mod_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            unbundle_mod.safe_unbundle(output_dir=tmpdir, force=True, quiet=True)
            self.assertFalse(integrity_mod.is_modified(root=tmpdir))
            ver_str = integrity_mod.version(root=tmpdir)
            self.assertNotIn("+mod.", ver_str)

    @unittest.skipIf(
        os.environ.get("DWIMSY_BUNDLE_BUILD") == "1",
        "Excluded during bundle build verification",
    )
    def test_cli_version_modified_has_mod_suffix_and_matching_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            unbundle_mod.safe_unbundle(output_dir=tmpdir, force=True, quiet=True)
            (tmpdir / "dwimsy" / "_version.py").write_text(
                '__version__ = "0.1.6.58-dev"\n__code_hash__ = ""\n# mod\n'
            )
            self.assertTrue(integrity_mod.is_modified(root=tmpdir))
            ver_str = integrity_mod.version(root=tmpdir)
            self.assertIn("+mod.", ver_str)
            mod_suffix = ver_str.split("+mod.")[1]
            banner = integrity_mod.version_banner(root=tmpdir, verbose=False)
            self.assertIn(mod_suffix, banner)


def main(argv=None):
    effective = sys.argv[1:] if argv is None else list(argv)
    if any(a in ("-V", "--version") for a in effective):
        from dwimsy.meta.integrity import version as get_version

        print(f"dwimsy {get_version()}")
        return 0
    unittest.main(argv=[sys.argv[0]] + effective)
    return 0



    def test_bump_version_programmatic_api_requires_explicit_tier_or_target(self):
        from dwimsy.meta.version_bump import bump_version
        with self.assertRaises(ValueError) as ctx:
            bump_version(message="Valid message")
        self.assertIn("explicit bump tier", str(ctx.exception))

    def test_bump_version_programmatic_api_requires_non_empty_message(self):
        from dwimsy.meta.version_bump import bump_version
        with self.assertRaises(ValueError) as ctx:
            bump_version(part="patch", message="")
        self.assertIn("non-empty changelog message", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            bump_version(part="patch", message="   ")
        self.assertIn("non-empty changelog message", str(ctx.exception))

    def test_parse_and_bump_version_requires_explicit_part(self):
        from dwimsy.meta.version_bump import parse_and_bump_version
        with self.assertRaises(ValueError) as ctx:
            parse_and_bump_version("0.1.6.0-dev")
        self.assertIn("explicit bump tier", str(ctx.exception))

    def test_bump_version_transactional_safety_on_test_failure(self):
        import tempfile
        import shutil
        from dwimsy.meta import unbundle, version_bump
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / "checkout"
            unbundle.extract_b64_lzma_tar(unbundle.blztar, tmp_path, with_deps=True)

            orig_version = (tmp_path / "dwimsy" / "_version.py").read_bytes()
            orig_changelog = (tmp_path / "CHANGELOG.md").read_bytes()
            orig_readme = (tmp_path / "README.md").read_bytes()
            orig_unbundle = (tmp_path / "dwimsy" / "meta" / "unbundle.py").read_bytes()

            broken_test = tmp_path / "tests" / "test_broken_synthetic.py"
            broken_test.write_text("import unittest\nclass BrokenTest(unittest.TestCase):\n    def test_fail(self):\n        self.fail('intentional failure')\n")

            with self.assertRaises(RuntimeError) as ctx:
                version_bump.bump_version(part="patch", message="Test failing bump", repo_root=tmp_path)
            self.assertIn("test suite failed", str(ctx.exception))

            self.assertEqual((tmp_path / "dwimsy" / "_version.py").read_bytes(), orig_version)
            self.assertEqual((tmp_path / "CHANGELOG.md").read_bytes(), orig_changelog)
            self.assertEqual((tmp_path / "README.md").read_bytes(), orig_readme)
            self.assertEqual((tmp_path / "dwimsy" / "meta" / "unbundle.py").read_bytes(), orig_unbundle)


if __name__ == "__main__":
    main()


class PlaceholderHelpTests(unittest.TestCase):
    def test_recover_help_advertises_unimplemented_status_and_milestone(self):
        proc = subprocess.run(
            [sys.executable, "-m", "dwimsy", "recover", "--help"],
            cwd=pkg_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        out = proc.stdout + proc.stderr
        self.assertIn("NOT IMPLEMENTED", out)
        self.assertIn("Milestone 4.0", out)
        self.assertIn("Forensic bit/pulse recovery engine", out)

    def test_bundle_fixtures_help_advertises_unimplemented_status_and_milestone(self):
        proc = subprocess.run(
            [sys.executable, "-m", "dwimsy", "meta", "bundle-fixtures", "--help"],
            cwd=pkg_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        out = proc.stdout + proc.stderr
        self.assertIn("NOT IMPLEMENTED", out)
        self.assertIn("Milestone 1.6", out)
        self.assertIn("Package private test fixtures", out)

    def test_top_level_help_lists_unimplemented_placeholders(self):
        proc = subprocess.run(
            [sys.executable, "-m", "dwimsy", "--help"],
            cwd=pkg_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        out = proc.stdout + proc.stderr
        self.assertIn("recover", out)
        self.assertIn("Milestone 4.0", out)
        self.assertIn("charset", out)
        self.assertIn("Milestone 2.3", out)
