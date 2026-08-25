#!/usr/bin/env python3
"""tests.test_lint_headers - Verify source file sh-bangs, docstrings, and module headers."""

import os
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent


def derive_module_name(rel_path: Path) -> str:
    parts = list(rel_path.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


class TestLintHeaders(unittest.TestCase):
    def test_all_non_deps_python_files_conform_to_header_spec(self):
        py_files = sorted(
            [
                p
                for p in pkg_root.rglob("*.py")
                if not p.relative_to(pkg_root).as_posix().startswith("deps")
            ]
        )

        errors = []
        forbidden_triple = chr(39) * 3

        for p in py_files:
            rel = p.relative_to(pkg_root)
            text = p.read_text(encoding="utf-8")
            lines = text.splitlines()
            if not lines:
                errors.append(f"{rel}: empty file")
                continue

            if forbidden_triple in text:
                errors.append(f"{rel}: contains forbidden triple single-quotes")

            has_main = (
                '__name__ == "__main__"' in text or "__name__ == '__main__'" in text
            )
            is_cli = (
                has_main
                or p.name.startswith("test_")
                or p.name
                in (
                    "__main__.py",
                    "unbundle.py",
                    "bundle.py",
                    "t882wav.py",
                    "wav2t88.py",
                )
            )

            has_shebang = lines[0].startswith("#!")
            if is_cli and not has_shebang:
                errors.append(f"{rel}: missing `#!/usr/bin/env python3` shebang")
            elif not is_cli and has_shebang:
                errors.append(f"{rel}: unexpected shebang on non-CLI module")

            doc_idx = 1 if has_shebang else 0
            if doc_idx >= len(lines):
                errors.append(f"{rel}: missing docstring on line {doc_idx + 1}")
                continue

            doc_line = lines[doc_idx]
            if not (
                doc_line.startswith(chr(34) * 3) or doc_line.startswith(chr(39) * 3)
            ):
                errors.append(
                    f"{rel}: line {doc_idx + 1} does not start with docstring quote (got `{doc_line[:30]}`)"
                )
                continue

            expected_mod = derive_module_name(rel)
            expected_prefix = f"{expected_mod} - "
            clean_doc = doc_line.lstrip(chr(34) + chr(39))
            if not clean_doc.startswith(expected_prefix):
                errors.append(
                    f"{rel}: docstring must begin with `{expected_prefix}`, got `{clean_doc[:45]}`"
                )

        self.assertEqual(errors, [], "Header linting failures:\n" + "\n".join(errors))


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
