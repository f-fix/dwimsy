#!/usr/bin/env python3
"""tests.test_test_runner - Verify dwimsy in-process test discovery and execution CLI & engine."""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy import tests as dw_tests
from dwimsy.cli import main as dwimsy_cli_main
from dwimsy.cli.filters.t882wav import main as t882wav_main
from dwimsy.cli.filters.wav2t88 import main as wav2t88_main
from dwimsy.meta import __main__ as meta_main
from dwimsy.meta import bundle as bundle_mod
from dwimsy.meta import unbundle as unbundle_mod
from dwimsy.meta import diff as diff_mod
from dwimsy.meta import integrity as integrity_mod
from dwimsy.meta import version_bump as version_bump_mod
from dwimsy.meta import lint as lint_mod
from dwimsy.tests.__main__ import main as dw_tests_main
from tests.__main__ import main as tests_main


@unittest.skipIf(
    os.environ.get("DWIMSY_BUNDLE_BUILD") == "1",
    "Excluded during bundle build verification",
)
class TestTestRunner(unittest.TestCase):
    def test_expand_test_patterns(self):
        self.assertEqual(dw_tests.expand_test_patterns(None), ["test_*.py"])
        self.assertIn("test_cli_filters.py", dw_tests.expand_test_patterns(["convert"]))
        self.assertIn("test_meta_bundle.py", dw_tests.expand_test_patterns(["meta"]))
        self.assertIn("test_core_audio.py", dw_tests.expand_test_patterns(["audio"]))

    def test_run_tests_scoped_in_process(self):
        buf = io.StringIO()
        rc = dw_tests.run_tests(["meta integrity"], verbose=1, stream=buf)
        self.assertEqual(rc, 0)
        self.assertIn("OK", buf.getvalue())

    def test_main_scoped_verb_test_flag_in_process(self):
        buf = io.StringIO()
        with redirect_stderr(buf):
            with self.assertRaises(SystemExit) as cm:
                dwimsy_cli_main(["convert", "--test"])
            self.assertEqual(cm.exception.code, 0)
        self.assertIn("OK", buf.getvalue())

    def test_main_scoped_verb_test_flag_verbose_in_process(self):
        buf = io.StringIO()
        with redirect_stderr(buf):
            with self.assertRaises(SystemExit) as cm:
                dwimsy_cli_main(["meta", "integrity", "--test", "--verbose"])
            self.assertEqual(cm.exception.code, 0)
        out = buf.getvalue()
        self.assertIn("OK", out)
        self.assertIn("test_hash_is_stable", out)

    def test_filter_t882wav_test_flag_in_process(self):
        buf = io.StringIO()
        orig_argv = sys.argv
        try:
            sys.argv = ["t882wav", "--test"]
            with redirect_stderr(buf):
                with self.assertRaises(SystemExit) as cm:
                    t882wav_main()
                self.assertEqual(cm.exception.code, 0)
            self.assertIn("OK", buf.getvalue())
        finally:
            sys.argv = orig_argv

    def test_filter_t882wav_test_flag_verbose_in_process(self):
        buf = io.StringIO()
        orig_argv = sys.argv
        try:
            sys.argv = ["t882wav", "--test", "--verbose"]
            with redirect_stderr(buf):
                with self.assertRaises(SystemExit) as cm:
                    t882wav_main()
                self.assertEqual(cm.exception.code, 0)
            out = buf.getvalue()
            self.assertIn("OK", out)
            self.assertIn("test_native_t882wav_synthetic_roundtrip", out)
        finally:
            sys.argv = orig_argv

    def test_filter_wav2t88_test_flag_in_process(self):
        buf = io.StringIO()
        orig_argv = sys.argv
        try:
            sys.argv = ["wav2t88", "--test"]
            with redirect_stderr(buf):
                with self.assertRaises(SystemExit) as cm:
                    wav2t88_main()
                self.assertEqual(cm.exception.code, 0)
            self.assertIn("OK", buf.getvalue())
        finally:
            sys.argv = orig_argv

    def test_filter_wav2t88_test_flag_verbose_in_process(self):
        buf = io.StringIO()
        orig_argv = sys.argv
        try:
            sys.argv = ["wav2t88", "--test", "-v"]
            with redirect_stderr(buf):
                with self.assertRaises(SystemExit) as cm:
                    wav2t88_main()
                self.assertEqual(cm.exception.code, 0)
            out = buf.getvalue()
            self.assertIn("OK", out)
            self.assertIn("test_pure_1200hz_tone_measures_correct_period", out)
        finally:
            sys.argv = orig_argv

    def test_dwimsy_tests_main_verbose_flag(self):
        buf = io.StringIO()
        with redirect_stderr(buf):
            rc = dw_tests_main(["meta integrity", "--verbose"])
            self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("OK", out)
        self.assertIn("test_hash_is_stable", out)

    def test_dwimsy_tests_main_list_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = dw_tests_main(["--list"])
            self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("test_all_non_deps_python_files_conform_to_header_spec", out)

    def test_run_tests_fallback_without_disk_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            buf = io.StringIO()
            rc = dw_tests.run_tests(
                ["meta integrity"], verbose=1, stream=buf, repo_root=tmp_path
            )
            self.assertEqual(rc, 0)
            self.assertIn("OK", buf.getvalue())

    def test_all_cli_entrypoints_universal_flags(self):
        entrypoints = [
            ("dwimsy.cli", dwimsy_cli_main),
            ("dwimsy.cli.filters.t882wav", t882wav_main),
            ("dwimsy.cli.filters.wav2t88", wav2t88_main),
            ("dwimsy.meta", meta_main.main),
            ("dwimsy.meta.bundle", bundle_mod.main),
            ("dwimsy.meta.unbundle", unbundle_mod.main),
            ("dwimsy.meta.diff", diff_mod.main),
            ("dwimsy.meta.integrity", integrity_mod.main),
            ("dwimsy.meta.version_bump", version_bump_mod.main),
            ("dwimsy.meta.lint", lint_mod.main),
            ("dwimsy.tests", dw_tests_main),
            ("tests", tests_main),
        ]
        for name, fn in entrypoints:
            # 1. Test --help
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                try:
                    rc_h = fn(["--help"])
                except SystemExit as e:
                    rc_h = e.code
            self.assertEqual(rc_h, 0, f"{name} --help failed with code {rc_h}")

            # 2. Test --version
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                try:
                    rc_v = fn(["--version"])
                except SystemExit as e:
                    rc_v = e.code
            self.assertEqual(rc_v, 0, f"{name} --version failed with code {rc_v}")

            # 3. Test --test=__no_such_test__
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                try:
                    rc_t = fn(["--test=__no_such_test__"])
                except SystemExit as e:
                    rc_t = e.code
            self.assertEqual(
                rc_t, 0, f"{name} --test=__no_such_test__ failed with code {rc_t}"
            )


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
