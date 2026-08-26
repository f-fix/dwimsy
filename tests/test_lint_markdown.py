#!/usr/bin/env python3
"""tests.test_lint_markdown - Verify markdown documentation formatting and rules."""

import re
import sys
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent


class TestLintMarkdown(unittest.TestCase):
    def test_markdown_files_conform_to_spec(self):
        md_files = sorted(pkg_root.rglob("*.md"))
        errors = []
        forbidden_triple_single = chr(39) * 3

        for p in md_files:
            rel = p.relative_to(pkg_root).as_posix()
            if rel.startswith("deps"):
                continue
            text = p.read_text(encoding="utf-8")

            # Check 1: Forbidden triple single quotes
            if forbidden_triple_single in text:
                errors.append(f"{rel}: contains forbidden triple-single-quotes")

            # Check 2: Check for raw inline LaTeX delimiters ($...$ or $$...$$ embedded in text)
            for i, line in enumerate(text.splitlines(), start=1):
                stripped = line.strip()
                if (
                    stripped.startswith("$$")
                    and stripped.endswith("$$")
                    and len(stripped) > 2
                ):
                    continue
                if re.search(r"(?<!\\)\$[^\$]+\$", line) and not re.search(
                    r"\$[0-9A-Za-z_-]+", line
                ):
                    if any(
                        cmd in line
                        for cmd in ("\\approx", "\\text", "\\frac", "\\cdot", "\\mu")
                    ):
                        errors.append(
                            f"{rel}:{i}: contains inline LaTeX math delimiters in text: `{line[:60]}`"
                        )

            # Check 3: Check for forbidden em and en dashes
            for i, line in enumerate(text.splitlines(), start=1):
                if "\u2014" in line:
                    errors.append(f"{rel}:{i}: contains forbidden em dash (U+2014); use ASCII hyphen-minus '-' instead")
                if "\u2013" in line:
                    errors.append(f"{rel}:{i}: contains forbidden en dash (U+2013); use ASCII hyphen-minus '-' instead")

        self.assertEqual(errors, [], "Markdown lint failures:\n" + "\n".join(errors))


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
