#!/usr/bin/env python3
"""tests.test_readme_sync - Verify README documentation and CLI help outputs are in sync."""

import difflib
import io
import os
import sys
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))


class TestReadmeSync(unittest.TestCase):
    def test_readme_contains_cli_help_sections(self):
        readme_file = pkg_root / "README.md"
        if readme_file.is_file():
            readme_text = readme_file.read_text(encoding="utf-8")
        else:
            from dwimsy.meta import unbundle

            readme_text = unbundle.get_asset_text("README.md")

        required_snippets = [
            "usage: dwimsy [-h] [-V] [-T] [-v] [--help-all] <command>",
            "usage: dwimsy convert",
            "usage: dwimsy inspect",
            "usage: dwimsy split",
            "usage: dwimsy join",
            "usage: dwimsy meta",
            "usage: dwimsy meta bundle",
            "usage: dwimsy meta fetch-deps",
            "usage: dwimsy-t882wav",
            "usage: dwimsy-wav2t88",
            "usage: python -m dwimsy.tests",
        ]

        for snippet in required_snippets:
            if snippet not in readme_text:
                diff = "\n".join(
                    difflib.unified_diff(
                        [snippet],
                        readme_text.splitlines(),
                        fromfile="expected_snippet",
                        tofile="README.md",
                        lineterm="",
                    )
                )
                self.fail(f"Snippet '{snippet}' not found in README.md:\n{diff}")


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
