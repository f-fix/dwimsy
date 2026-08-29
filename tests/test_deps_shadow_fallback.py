#!/usr/bin/env python3
"""tests.test_deps_shadow_fallback - Verify shadow fallback mechanics for deps/."""

import io
import sys
import tempfile
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.meta.unbundle import BundleFinder
from dwimsy.meta.versions import VersionSpace, Stream, Layer


class TestDepsShadowFallback(unittest.TestCase):
    def test_no_live_deps_directory_shadow_fallback_provides_deps(self):
        f_bundle = {
            "dwimsy/__init__.py": b"",
            "deps/bin2fds/__init__.py": b"",
            "deps/bin2fds/bin2fds.py": b"def bin2fds(): return 42\n",
        }
        vspace = VersionSpace([Stream(0, "primary", [Layer(f_bundle, is_delta=False)])])
        b64 = vspace.to_blztar()

        finder = BundleFinder(b64, on_disk_root=None)
        spec = finder.find_spec("deps.bin2fds.bin2fds")
        self.assertIsNotNone(spec)

    def test_live_dependency_present_and_modified_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "dwimsy").mkdir()
            (tmp_root / "dwimsy" / "__init__.py").write_bytes(b"")
            (tmp_root / "deps" / "bin2fds").mkdir(parents=True)
            (tmp_root / "deps" / "bin2fds" / "__init__.py").write_bytes(b"")
            (tmp_root / "deps" / "bin2fds" / "bin2fds.py").write_text(
                "def bin2fds(): return 'live'\n"
            )

            f_bundle = {
                "dwimsy/__init__.py": b"",
                "deps/bin2fds/__init__.py": b"",
                "deps/bin2fds/bin2fds.py": b"def bin2fds(): return 'shadow'\n",
            }
            vspace = VersionSpace(
                [Stream(0, "primary", [Layer(f_bundle, is_delta=False)])]
            )

            finder = BundleFinder(vspace.to_blztar(), on_disk_root=tmp_root)
            spec = finder.find_spec("deps.bin2fds.bin2fds")
            self.assertIsNone(spec)

    def test_git_checkout_undeclared_dependency_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            (tmp_root / ".git").mkdir()
            (tmp_root / ".gitmodules").write_text(
                '[submodule "deps/other"]\n\tpath = deps/other\n\turl = ...\n'
            )

            f_bundle = {
                "dwimsy/__init__.py": b"",
                ".gitmodules": b'[submodule "deps/other"]\n\tpath = deps/other\n\turl = ...\n',
                "deps/undeclared/__init__.py": b"",
                "deps/undeclared/tool.py": b"def tool(): pass\n",
            }
            vspace = VersionSpace(
                [Stream(0, "primary", [Layer(f_bundle, is_delta=False)])]
            )
            finder = BundleFinder(vspace.to_blztar(), on_disk_root=tmp_root)

            spec = finder.find_spec("deps.undeclared.tool")
            self.assertIsNone(spec)


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
