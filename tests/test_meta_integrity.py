#!/usr/bin/env python3
"""tests.test_meta_integrity - Verify dwimsy file and package integrity mechanisms."""

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.meta import integrity, unbundle


class IntegrityTests(unittest.TestCase):
    def test_hash_is_stable(self):
        self.assertEqual(
            integrity.canonical_code_hash(), integrity.canonical_code_hash()
        )
        self.assertEqual(len(integrity.canonical_code_hash()), 64)

    def test_version_hash_sentinel_does_not_self_modify(self):
        root = Path(integrity.package_root())
        version_file = root / "_version.py"
        original = version_file.read_bytes()
        try:
            h1 = integrity.canonical_code_hash()
            version_file.write_bytes(
                original.replace(b'__code_hash__ = ""', b'__code_hash__ = "deadbeef"')
            )
            h2 = integrity.canonical_code_hash()
            self.assertEqual(h1, h2)
        finally:
            version_file.write_bytes(original)

    def test_line_endings_are_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_version.py").write_bytes(
                b'__version__ = "x"\r\n__code_hash__ = "abc"\r\n'
            )
            (root / "a.py").write_bytes(b"x = 1\r\ny = 2\r\n")
            h_crlf = integrity.canonical_code_hash(root)
            (root / "a.py").write_bytes(b"x = 1\ny = 2\n")
            h_lf = integrity.canonical_code_hash(root)
            self.assertEqual(h_crlf, h_lf)

    def test_path_order_is_canonical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "dwimsy"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("x = 1\n", encoding="utf-8")
            (pkg / "_version.py").write_text(
                '__version__ = "x"\n__code_hash__ = ""\n', encoding="utf-8"
            )
            (pkg / "z.py").write_text("z = 1\n", encoding="utf-8")
            (pkg / "a.py").write_text("a = 1\n", encoding="utf-8")
            self.assertEqual(
                tuple(
                    p.relative_to(root).as_posix() for p in integrity.source_files(root)
                ),
                ("dwimsy/__init__.py", "dwimsy/_version.py", "dwimsy/a.py", "dwimsy/z.py"),
            )

    def test_bundle_asset_names_preserve_dotfiles(self):
        self.assertIn(".gitignore", unbundle.list_assets())
        self.assertIn(".gitmodules", unbundle.list_assets())
        self.assertEqual(
            unbundle.get_asset(".gitignore"),
            (integrity.find_repo_root() / ".gitignore").read_bytes(),
        )

    def test_unbundle_module_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_version.py").write_text(
                '__version__ = "x"\n__code_hash__ = ""\n', encoding="utf-8"
            )
            (root / "a.py").write_text("a = 1\n", encoding="utf-8")
            h1 = integrity.canonical_code_hash(root)
            (root / "unbundle.py").write_text('blztar = "xyz"\n', encoding="utf-8")
            h2 = integrity.canonical_code_hash(root)
            self.assertEqual(h1, h2)


    def test_manifest_contains_portable_project_window(self):
        patterns = integrity.canonical_manifest()
        self.assertIn("dwimsy/**/*.py", patterns)
        self.assertIn("tests/**/*.py", patterns)
        self.assertIn("README.md", patterns)
        self.assertIn("LICENSE", patterns)
        self.assertIn(".gitignore", patterns)
        self.assertIn(".gitmodules", patterns)
        self.assertIn("deps/pc88_tape_tools/**/*", patterns)

    def test_gitmodule_dependency_globs_are_lazy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dwimsy").mkdir()
            (root / "dwimsy" / "__init__.py").write_text("x = 1\n", encoding="utf-8")
            (root / "dwimsy" / "_version.py").write_text(
                '__version__ = "x"\n__code_hash__ = ""\n', encoding="utf-8"
            )
            (root / ".gitmodules").write_text(
                '[submodule "deps/example"]\npath = deps/example\nurl = https://example.invalid/example.git\n',
                encoding="utf-8",
            )
            patterns = integrity.canonical_manifest(root)
            self.assertIn("deps/example/**/*", patterns)
            self.assertNotIn("deps/example/file.py", patterns)

    def test_unsealed_tree_is_modified(self):
        self.assertEqual(integrity.sealed_code_hash(), "")
        self.assertTrue(integrity.is_modified())
        self.assertIn("+mod.", integrity.version())

    def test_non_deps_python_shebang_and_docstring_conventions(self):
        repo = integrity.find_repo_root()
        py_files = sorted(
            p
            for p in repo.rglob("*.py")
            if not p.relative_to(repo).as_posix().startswith("deps/")
        )
        triple_single = 3 * chr(39)

        for p in py_files:
            rel = p.relative_to(repo).as_posix()
            text = p.read_text(encoding="utf-8")
            lines = text.splitlines()
            self.assertTrue(len(lines) > 0, f"{rel} is empty")

            self.assertNotIn(
                triple_single,
                text,
                f"{rel} contains forbidden triple single quote syntax ({triple_single})",
            )

            parts = list(p.relative_to(repo).with_suffix("").parts)
            if parts[-1] == "__init__":
                expected_mod = ".".join(parts[:-1])
            else:
                expected_mod = ".".join(parts)

            has_main = (
                '__name__ == "__main__"' in text or "__name__ == '__main__'" in text
            )
            has_cli_shebang = lines[0].startswith("#!/usr/bin/env python3")

            if has_main or p.name in ("bundle.py", "unbundle.py"):
                self.assertTrue(
                    has_cli_shebang,
                    f"{rel} has main/CLI entrypoint but lacks #!/usr/bin/env python3 shebang at line 1",
                )
            else:
                self.assertFalse(
                    lines[0].startswith("#!"),
                    f"{rel} has shebang but no main/CLI entrypoint",
                )

            tree = ast.parse(text)
            docstring = ast.get_docstring(tree)
            self.assertIsNotNone(
                docstring, f"{rel} lacks a module docstring at the top"
            )
            first_doc_line = docstring.strip().splitlines()[0]

            expected_prefix = f"{expected_mod} - "
            self.assertTrue(
                first_doc_line.startswith(expected_prefix),
                f"{rel} docstring first line must start with '{expected_prefix}', got '{first_doc_line}'",
            )

            top_str_exprs = [
                node
                for node in tree.body
                if isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ]
            self.assertEqual(
                len(top_str_exprs),
                1,
                f"{rel} contains multiple top-level string literal expressions ({len(top_str_exprs)})",
            )

    def test_markdown_formatting_conventions(self):
        repo = integrity.find_repo_root()
        md_files = sorted(
            p
            for p in repo.rglob("*.md")
            if not p.relative_to(repo).as_posix().startswith("deps/")
        )
        triple_single = 3 * chr(39)

        for p in md_files:
            rel = p.relative_to(repo).as_posix()
            text = p.read_text(encoding="utf-8")

            self.assertNotIn(
                triple_single,
                text,
                f"{rel} contains forbidden triple single quote syntax ({triple_single})",
            )

            lines = text.splitlines()
            for idx, line in enumerate(lines, start=1):
                stripped = line.strip()
                if stripped.startswith("$$") and stripped.endswith("$$"):
                    continue
                inline_dollar = re.findall(r"(?<!\\)\$([^$\n]+)\$", line)
                self.assertEqual(
                    len(inline_dollar),
                    0,
                    f"{rel}:{idx} contains LaTeX math inline delimiter ($...$): {line}",
                )
                for cmd in (r"\approx", r"\text", r"\frac"):
                    self.assertNotIn(
                        cmd,
                        line,
                        f"{rel}:{idx} contains LaTeX command '{cmd}': {line}",
                    )


def main(argv=None):
    import sys

    effective = sys.argv[1:] if argv is None else list(argv)
    if any(a in ("-V", "--version") for a in effective):
        from dwimsy.meta.integrity import version as get_version

        print(f"dwimsy {get_version()}")
        return 0
    unittest.main(argv=[sys.argv[0]] + effective)
    return 0


if __name__ == "__main__":
    main()
