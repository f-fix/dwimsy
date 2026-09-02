#!/usr/bin/env python3
"""tests.test_cli_list_versions - Verify --version-list formatting, annotations, and selector taxonomy."""

import io
import os
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

    def test_version_list_short_hash_and_timestamp_by_default(self):
        f0 = {"dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = ""\n', "CHANGELOG.md": b"## [0.1.6.0] - 2026-08-30\n"}
        vspace = VersionSpace([Stream(0, "primary", [Layer(f0, is_delta=False)])])
        out = vspace.format_list_versions(verbose=False)
        self.assertRegex(out, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
        head_hash = vspace.streams[0].get_head_version().content_hash
        self.assertIn(head_hash[:12], out)
        self.assertNotIn(head_hash, out)

    def test_version_list_verbose_expands_to_64_char_hash(self):
        f0 = {"dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = ""\n', "CHANGELOG.md": b"## [0.1.6.0] - 2026-08-30\n"}
        vspace = VersionSpace([Stream(0, "primary", [Layer(f0, is_delta=False)])])
        out = vspace.format_list_versions(verbose=True)
        head_hash = vspace.streams[0].get_head_version().content_hash
        self.assertIn(head_hash, out)

    def test_version_list_cli_flag_variants(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr
        from dwimsy.cli import main as dw_main

        variants = [
            (["--version-list"], False),
            (["--version-list=short"], False),
            (["--version-list=full"], True),
            (["--version-list=long"], True),
            (["--version-list", "--verbose"], True),
            (["--verbose", "--version-list"], True),
            (["--version-list", "-v"], True),
            (["-v", "--version-list"], True),
            (["--version-list=short", "-v"], False),
            (["--version-list=full", "-v"], True),
        ]

        for flags, expect_64_char in variants:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                try:
                    dw_main(flags)
                except SystemExit:
                    pass
            out = buf.getvalue()
            self.assertIn("[primary]", out, f"Failed on flags: {flags}")
            primary_lines = [l for l in out.splitlines() if "[primary]" in l]
            self.assertTrue(len(primary_lines) > 0)
            for pl in primary_lines:
                tokens = pl.split()
                self.assertGreaterEqual(len(tokens), 4)
                h = tokens[3]
                if expect_64_char:
                    self.assertEqual(len(h), 64, f"Expected 64-char hash for {flags}, got: {h}")
                else:
                    self.assertEqual(len(h), 12, f"Expected 12-char hash for {flags}, got: {h}")

    @unittest.skipIf(
        os.environ.get("DWIMSY_BUNDLE_BUILD") == "1",
        "Excluded during bundle build verification",
    )
    def test_version_list_shares_single_entry_when_unbundled_identical_to_baseline(self):
        import tempfile
        from dwimsy.meta import unbundle
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            unbundle.safe_unbundle(output_dir=tmpdir, force=True, quiet=True)
            raw_b64 = unbundle._get_active_blztar()
            vspace = VersionSpace.from_blztar(raw_b64)
            out = vspace.format_list_versions(on_disk_root=tmpdir)
            self.assertFalse(any(line.strip().startswith("[unbundled]") for line in out.splitlines()))
            self.assertIn("=unbundled", out)

    @unittest.skipIf(
        os.environ.get("DWIMSY_BUNDLE_BUILD") == "1",
        "Excluded during bundle build verification",
    )
    def test_version_list_separate_unbundled_row_when_modified(self):
        import tempfile
        from dwimsy.meta import unbundle
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            unbundle.safe_unbundle(output_dir=tmpdir, force=True, quiet=True)
            (tmpdir / "dwimsy" / "_version.py").write_text('__version__ = "0.1.6.58-dev"\n__code_hash__ = ""\n# mod\n')
            raw_b64 = unbundle._get_active_blztar()
            vspace = VersionSpace.from_blztar(raw_b64)
            out = vspace.format_list_versions(on_disk_root=tmpdir)
            self.assertTrue(any(line.strip().startswith("[unbundled]") for line in out.splitlines()))
            self.assertIn("+mod.", out)


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
