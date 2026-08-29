#!/usr/bin/env python3
"""tests.test_meta_splice_safety - Tests for --splice safety verification and conflict abortion."""

import io
import sys
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.meta.versions import VersionSpace, Stream, Layer


class TestMetaSpliceSafety(unittest.TestCase):
    def test_non_conflicting_splice_commits(self):
        f_base = {
            "dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "h0"\n',
            "core.py": b"v0",
        }
        f_old = {
            "dwimsy/_version.py": b'__version__ = "0.1.4.0"\n__code_hash__ = "hold"\n',
            "core.py": b"vold",
        }
        s0 = Stream(
            0,
            "primary",
            [
                Layer(f_base, is_delta=False, code_hash="h0"),
                Layer(f_old, is_delta=False, code_hash="hold"),
            ],
        )

        f_donor = {
            "dwimsy/_version.py": b'__version__ = "0.1.5.0"\n__code_hash__ = "h15"\n',
            "core.py": b"v15_fixed",
        }
        s1 = Stream(1, "alt1", [Layer(f_donor, is_delta=False, code_hash="h15")])

        vspace = VersionSpace([s0, s1])
        vspace.splice("alt1_0.1.5.0")

        p_vers = vspace.streams[0].get_versions()
        tags = [v.tag for v in p_vers]
        self.assertEqual(tags, ["0.1.6.0", "0.1.5.0", "0.1.4.0"])

    def test_conflicting_splice_aborts_and_reports_conflict(self):
        f0 = {
            "dwimsy/_version.py": b'__version__ = "0.1.5.0"\n__code_hash__ = "h15"\n',
            "core.py": b"v15",
        }
        f1 = {
            "dwimsy/_version.py": b'__version__ = "0.1.6.0-dev"\n__code_hash__ = ""\n',
            "core.py": b"v16",
        }
        s0 = Stream(
            0,
            "primary",
            [Layer(f0, is_delta=False, code_hash="h15"), Layer(f1, is_delta=True)],
        )

        f_donor = {
            "dwimsy/_version.py": b'__version__ = "0.1.5.0"\n__code_hash__ = "hdiverged"\n',
            "core.py": b"different",
        }
        s1 = Stream(1, "alt1", [Layer(f_donor, is_delta=False, code_hash="hdiverged")])

        vspace = VersionSpace([s0, s1])
        with self.assertRaises(RuntimeError) as cm:
            vspace.splice("alt1_0.1.5.0")
        self.assertIn("splice aborted: would alter sealed history", str(cm.exception))

    def test_alt_patch_splice_prune_reinsertion(self):
        f0 = {
            "dwimsy/_version.py": b'__version__ = "0.1.4.0"\n__code_hash__ = "h4"\n',
            "app.py": b"v4",
        }
        f1 = {
            "dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "h6"\n',
            "app.py": b"v6",
        }
        s0 = Stream(
            0,
            "primary",
            [
                Layer(f1, is_delta=False, code_hash="h6"),
                Layer(f0, is_delta=False, code_hash="h4"),
            ],
        )
        vspace = VersionSpace([s0])

        vspace.branch_alt("0.1.4.0")
        vspace.streams[0].layers[0].files["app.py"] = b"v4_patched"
        vspace.streams[0].layers[0].files[
            "dwimsy/_version.py"
        ] = b'__version__ = "0.1.4.1"\n__code_hash__ = ""\n'
        vspace.streams[0].layers[0].version_tag = "0.1.4.1"
        vspace.streams[0].seal_open_dev()

        orig = vspace.streams[1]
        donor = vspace.streams[0]
        vspace.streams = [orig, donor]
        vspace.renumber_streams()

        vspace.splice("alt1_0.1.4.1")
        vspace.prune("alt*")

        self.assertEqual(len(vspace.streams), 1)
        tags = [v.tag for v in vspace.streams[0].get_versions()]
        self.assertEqual(tags, ["0.1.6.0", "0.1.4.1", "0.1.4.0"])


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
