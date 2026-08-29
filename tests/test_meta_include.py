#!/usr/bin/env python3
"""tests.test_meta_include - Verify static stream import without foreign code execution."""

import io
import sys
import tempfile
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.meta.versions import VersionSpace, Stream, Layer


class TestMetaInclude(unittest.TestCase):
    def test_static_include_from_script_no_exec(self):
        with tempfile.TemporaryDirectory() as tmp:
            foreign_script = Path(tmp) / "foreign_bundle.py"
            f_files = {
                "dwimsy/_version.py": b'__version__ = "0.2.0.0"\n__code_hash__ = "h20"\n',
                "trap.txt": b"ok",
            }
            s_foreign = Stream(
                0, "primary", [Layer(f_files, is_delta=False, code_hash="h20")]
            )
            v_foreign = VersionSpace([s_foreign])
            b64 = v_foreign.to_blztar()

            script_text = f'#!/usr/bin/env python3\nraise RuntimeError("EXECUTION TRAP TRIGGERED")\nblztar = """\n{b64}\n"""\n'
            foreign_script.write_text(script_text, encoding="utf-8")

            vspace = VersionSpace()
            vspace.include_source(foreign_script)
            self.assertEqual(len(vspace.streams), 2)
            self.assertEqual(vspace.streams[1].name, "alt1")
            self.assertEqual(vspace.streams[1].layers[0].version_tag, "0.2.0.0")

    def test_static_include_from_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            dir_path = Path(tmp) / "repo"
            unbundle_path = dir_path / "dwimsy" / "meta" / "unbundle.py"
            unbundle_path.parent.mkdir(parents=True, exist_ok=True)

            f_files = {
                "dwimsy/_version.py": b'__version__ = "0.3.0.0"\n__code_hash__ = "h30"\n'
            }
            v_foreign = VersionSpace(
                [
                    Stream(
                        0, "primary", [Layer(f_files, is_delta=False, code_hash="h30")]
                    )
                ]
            )
            script_text = f'blztar = """\n{v_foreign.to_blztar()}\n"""\n'
            unbundle_path.write_text(script_text, encoding="utf-8")

            vspace = VersionSpace()
            vspace.include_source(dir_path)
            self.assertEqual(len(vspace.streams), 2)
            self.assertEqual(vspace.streams[1].layers[0].version_tag, "0.3.0.0")

    def test_include_accumulation_and_peer_tokens(self):
        f1 = {
            "dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "same"\n'
        }
        v1 = VersionSpace(
            [Stream(0, "primary", [Layer(f1, is_delta=False, code_hash="same")])]
        )

        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "b1.py"
            p1.write_text(f'blztar = """\n{v1.to_blztar()}\n"""', encoding="utf-8")

            vspace = VersionSpace(
                [Stream(0, "primary", [Layer(f1, is_delta=False, code_hash="same")])]
            )
            vspace.include_source(p1)
            vspace.include_source(p1)

            self.assertEqual(len(vspace.streams), 3)
            out = vspace.format_list_versions()
            self.assertIn("=alt1_0.1.6.0", out)
            self.assertIn("=alt2_0.1.6.0", out)


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
