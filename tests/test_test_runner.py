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


class TestTestRunner(unittest.TestCase):
    def test_expand_test_patterns(self):
        self.assertEqual(dw_tests.expand_test_patterns(None), ["test_*.py"])
        self.assertIn("test_cli_filters.py", dw_tests.expand_test_patterns(["convert"]))
        self.assertIn("test_meta_bundle.py", dw_tests.expand_test_patterns(["meta"]))
        self.assertIn("test_core_audio.py", dw_tests.expand_test_patterns(["audio"]))

    def test_run_tests_scoped_in_process(self):
        buf = io.StringIO()
        rc = dw_tests.run_tests(["integrity"], verbose=1, stream=buf)
        self.assertEqual(rc, 0)
        self.assertIn("OK", buf.getvalue())

    def test_main_scoped_verb_test_flag_in_process(self):
        buf = io.StringIO()
        with redirect_stderr(buf):
            with self.assertRaises(SystemExit) as cm:
                dwimsy_cli_main(["meta", "--test"])
            self.assertEqual(cm.exception.code, 0)
        self.assertIn("OK", buf.getvalue())

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

    def test_run_tests_fallback_without_disk_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            buf = io.StringIO()
            rc = dw_tests.run_tests(
                ["integrity"], verbose=1, stream=buf, repo_root=tmp_path
            )
            self.assertEqual(rc, 0)
            self.assertIn("OK", buf.getvalue())


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
