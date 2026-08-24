#!/usr/bin/env python3
"""tests.test_lint_markdown - Verify markdown documentation formatting and rules."""

import re
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

        self.assertEqual(errors, [], "Markdown lint failures:\n" + "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
