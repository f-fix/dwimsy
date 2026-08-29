#!/usr/bin/env python3
"""tests.test_cli_multicall_dispatch - Verify multicall verb dispatch and applet routing."""

import sys
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.meta.unbundle import resolve_multicall_verb, resolve_argv0_command


class TestCLIMulticallDispatch(unittest.TestCase):
    def test_applet_verbs_bare_dispatch(self):
        self.assertEqual(resolve_multicall_verb("t882wav"), "t882wav")
        self.assertEqual(resolve_multicall_verb("wav2t88"), "wav2t88")
        self.assertEqual(resolve_multicall_verb("/usr/local/bin/t882wav"), "t882wav")

    def test_applet_verbs_prefixed_and_extensions(self):
        self.assertEqual(resolve_multicall_verb("dwimsy-t882wav"), "t882wav")
        self.assertEqual(resolve_multicall_verb("dwimsy-t882wav_1.2.0.py"), "t882wav")
        self.assertEqual(resolve_multicall_verb("dwimsy-t882wav.pyz"), "t882wav")
        self.assertEqual(resolve_multicall_verb("dwimsy_wav2t88_1.2.0.exe"), "wav2t88")

    def test_meta_verbs_do_not_bare_dispatch(self):
        self.assertIsNone(resolve_multicall_verb("unbundle"))
        self.assertIsNone(resolve_multicall_verb("bundle"))
        self.assertIsNone(resolve_multicall_verb("lint"))
        self.assertIsNone(resolve_multicall_verb("dwimsy"))


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


class TestUniversalEntryPointDispatch(unittest.TestCase):
    def test_all_separator_forms(self):
        expected = ["meta", "unbundle"]
        for name in (
            "dwimsy-meta-unbundle",
            "dwimsy_meta_unbundle",
            "dwimsy/meta/unbundle",
            r"dwimsy\\meta\\unbundle",
            "dwimsy meta unbundle",
            "meta-unbundle",
        ):
            self.assertEqual(resolve_argv0_command(name), expected, name)

    def test_bare_unbundle_does_not_dispatch(self):
        for name in ("unbundle", "dwimsy-unbundle", "dwimsy_unbundle"):
            self.assertEqual(resolve_argv0_command(name), [], name)
