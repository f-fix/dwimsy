#!/usr/bin/env python3
"""tests.test_cli_case_insensitivity - Verify case-insensitive CLI matching and universal flag normalization."""

import sys
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.meta.unbundle import parse_early_pipeline_flags
from dwimsy.meta.versions import VersionSpace, Stream, Layer


class TestCLICaseInsensitivity(unittest.TestCase):
    def test_V_is_v_not_verbose(self):
        pipeline, remaining = parse_early_pipeline_flags(["-V"])
        self.assertTrue(pipeline.get("print_version"))
        self.assertEqual(pipeline.get("verbosity"), 0)

        pipeline, remaining = parse_early_pipeline_flags(["-v"])
        self.assertTrue(pipeline.get("print_version"))
        self.assertEqual(pipeline.get("verbosity"), 0)

    def test_mixed_case_short_options(self):
        pipeline, remaining = parse_early_pipeline_flags(["-vv"])
        self.assertFalse(pipeline.get("print_version"))
        self.assertEqual(pipeline.get("verbosity"), 1)

        pipeline, remaining = parse_early_pipeline_flags(["-VV"])
        self.assertFalse(pipeline.get("print_version"))
        self.assertEqual(pipeline.get("verbosity"), 1)

        pipeline, remaining = parse_early_pipeline_flags(["-vV"])
        self.assertFalse(pipeline.get("print_version"))
        self.assertEqual(pipeline.get("verbosity"), 1)

        pipeline, remaining = parse_early_pipeline_flags(["-vvv"])
        self.assertEqual(pipeline.get("verbosity"), 2)

    def test_exact_case_preservation_of_paths_and_values(self):
        pipeline, remaining = parse_early_pipeline_flags(
            ["CONVERT", "--FORMAT=WAV", "/Path/To/File.WAV"]
        )
        self.assertEqual(remaining, ["CONVERT", "--FORMAT=WAV", "/Path/To/File.WAV"])

    def test_help_translation(self):
        pipeline, remaining = parse_early_pipeline_flags(["-?"])
        self.assertEqual(remaining, ["-h"])
        pipeline2, remaining2 = parse_early_pipeline_flags(["/?"])
        self.assertEqual(remaining2, ["-h"])

    def test_version_lookup_case_insensitive_preserves_canonical_tag(self):
        f0 = {
            "dwimsy/_version.py": b'__version__ = "0.1.6.3-dev"\n__code_hash__ = ""\n'
        }
        vspace = VersionSpace([Stream(0, "primary", [Layer(f0, is_delta=False)])])

        res = vspace.resolve_version_ref("0.1.6.3-DEV")
        self.assertIsNotNone(res)
        st, ord_idx, ref = res
        self.assertEqual(ref.tag, "0.1.6.3-dev")


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
