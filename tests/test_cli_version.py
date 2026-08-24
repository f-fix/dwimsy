#!/usr/bin/env python3
"""tests.test_cli_version - Verify dwimsy CLI version reporting and endpoint consistency."""

import io
import os
import subprocess
import sys
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
from dwimsy.meta import bundle as bundle_mod
from dwimsy.meta import unbundle as unbundle_mod
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
            with self.assertRaises(SystemExit) as cm:
                dwimsy_cli_main(["--version"])
        self.assertEqual(cm.exception.code, 0)
        expected = f"dwimsy {get_version()}\n"
        self.assertEqual(buf.getvalue(), expected)

    def test_cli_short_version_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            with self.assertRaises(SystemExit) as cm:
                dwimsy_cli_main(["-V"])
        self.assertEqual(cm.exception.code, 0)
        expected = f"dwimsy {get_version()}\n"
        self.assertEqual(buf.getvalue(), expected)

    def test_all_cli_modules_implement_main_and_version(self):
        expected_v = f"{get_version()}"
        cli_modules = [
            ("dwimsy.cli", dwimsy_cli_main),
            ("dwimsy.cli.filters.t882wav", t882wav_mod.main),
            ("dwimsy.cli.filters.wav2t88", wav2t88_mod.main),
            ("dwimsy.meta.bundle", bundle_mod.main),
            ("dwimsy.meta.unbundle", unbundle_mod.main),
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

    def test_subprocess_cli_module_invocations(self):
        repo_root = Path(pkg_root)
        interp = sys.executable
        expected_v = get_version()

        test_targets = [
            "dwimsy",
            "dwimsy.cli",
            "dwimsy.cli.filters.t882wav",
            "dwimsy.cli.filters.wav2t88",
            "dwimsy.meta.bundle",
            "dwimsy.meta.unbundle",
            "dwimsy.tests",
            "tests",
        ]

        for target in test_targets:
            res = subprocess.run(
                [interp, "-m", target, "--version"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                res.returncode,
                0,
                f"python -m {target} --version failed with code {res.returncode}: {res.stderr}",
            )
            out = (res.stdout or res.stderr).strip()
            self.assertIn(
                expected_v,
                out,
                f"python -m {target} --version output '{out}' missing expected '{expected_v}'",
            )


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
