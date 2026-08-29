#!/usr/bin/env python3
"""tests.test_cli_list_versions - Verify --version-list formatting, annotations, and selector taxonomy."""

import io
import sys
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.meta.versions import VersionSpace, Stream, Layer


class TestCLIListVersions(unittest.TestCase):
    def test_primary_annotation_and_alt_prefix(self):
        f0 = {
            "dwimsy/_version.py": b'__version__ = "0.1.6.3-dev"\n__code_hash__ = ""\n'
        }
        f_alt = {
            "dwimsy/_version.py": b'__version__ = "0.1.5.0"\n__code_hash__ = "h15"\n'
        }
        vspace = VersionSpace(
            [
                Stream(
                    0,
                    "primary",
                    [Layer(f0, is_delta=False)],
                    source="dwimsy_0.1.6.3-dev.py",
                ),
                Stream(
                    1,
                    "alt1",
                    [Layer(f_alt, is_delta=False, code_hash="h15")],
                    source="/tmp/alt1.py",
                ),
            ]
        )

        out = vspace.format_list_versions()
        self.assertIn("[primary]", out)
        self.assertIn("alt1_0.1.5.0", out)
        self.assertIn("[=primary: dwimsy_0.1.6.3-dev.py]", out)
        self.assertIn("[=alt1: /tmp/alt1.py]", out)

    def test_alt_sealed_single_version_uses_first_eligible_alt(self):
        f0 = {"dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "h0"\n'}
        f_alt1 = {
            "dwimsy/_version.py": b'__version__ = "0.1.5.0"\n__code_hash__ = "h1"\n'
        }
        f_alt2 = {
            "dwimsy/_version.py": b'__version__ = "0.1.4.0"\n__code_hash__ = "h2"\n'
        }

        vspace = VersionSpace(
            [
                Stream(0, "primary", [Layer(f0, is_delta=False, code_hash="h0")]),
                Stream(1, "alt1", [Layer(f_alt1, is_delta=False, code_hash="h1")]),
                Stream(2, "alt2", [Layer(f_alt2, is_delta=False, code_hash="h2")]),
            ]
        )

        res = vspace.resolve_version_ref("alt_sealed")
        self.assertIsNotNone(res)
        st, ord_idx, ref = res
        self.assertEqual(st.name, "alt1")
        self.assertEqual(ref.tag, "0.1.5.0")

    def test_alt_sealed_filter_includes_all_alternates(self):
        f0 = {"dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "h0"\n'}
        f_alt1 = {
            "dwimsy/_version.py": b'__version__ = "0.1.5.0"\n__code_hash__ = "h1"\n'
        }
        f_alt2 = {
            "dwimsy/_version.py": b'__version__ = "0.1.4.0"\n__code_hash__ = "h2"\n'
        }

        vspace = VersionSpace(
            [
                Stream(0, "primary", [Layer(f0, is_delta=False, code_hash="h0")]),
                Stream(1, "alt1", [Layer(f_alt1, is_delta=False, code_hash="h1")]),
                Stream(2, "alt2", [Layer(f_alt2, is_delta=False, code_hash="h2")]),
            ]
        )

        matches = vspace.match_versions("alt_sealed")
        self.assertEqual(len(matches), 2)
        tags = [ref.tag for st, ord_idx, ref in matches]
        self.assertEqual(tags, ["0.1.5.0", "0.1.4.0"])

    def test_primary_sealed_filter_only_primary(self):
        f0 = {"dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "h0"\n'}
        f_alt1 = {
            "dwimsy/_version.py": b'__version__ = "0.1.5.0"\n__code_hash__ = "h1"\n'
        }

        vspace = VersionSpace(
            [
                Stream(0, "primary", [Layer(f0, is_delta=False, code_hash="h0")]),
                Stream(1, "alt1", [Layer(f_alt1, is_delta=False, code_hash="h1")]),
            ]
        )

        matches = vspace.match_versions("primary_sealed")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][2].tag, "0.1.6.0")

    def test_restrict_to_wildcard_sealed(self):
        f0 = {"dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "h0"\n'}
        f_alt1 = {
            "dwimsy/_version.py": b'__version__ = "0.1.5.0"\n__code_hash__ = "h1"\n'
        }

        vspace = VersionSpace(
            [
                Stream(0, "primary", [Layer(f0, is_delta=False, code_hash="h0")]),
                Stream(1, "alt1", [Layer(f_alt1, is_delta=False, code_hash="h1")]),
            ]
        )

        matches = vspace.match_versions("*_sealed")
        self.assertEqual(len(matches), 2)

    def test_peer_tokens_symmetry(self):
        f_same = {
            "dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "h_match"\n',
            "a.txt": b"1",
        }
        vspace = VersionSpace(
            [
                Stream(
                    0, "primary", [Layer(f_same, is_delta=False, code_hash="h_match")]
                ),
                Stream(1, "alt1", [Layer(f_same, is_delta=False, code_hash="h_match")]),
            ]
        )
        out = vspace.format_list_versions()
        self.assertIn("=alt1_0.1.6.0", out)
        self.assertIn("=primary_0.1.6.0", out)


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
