#!/usr/bin/env python3
"""tests.test_unbundle_no_top_level_dwimsy_imports - Assert unbundle.py has no top-level dwimsy imports."""

import ast
import unittest
from pathlib import Path


class TestUnbundleNoTopLevelDwimsyImports(unittest.TestCase):
    def test_no_top_level_dwimsy_imports(self):
        repo_root = Path(__file__).resolve().parent.parent
        unb_file = repo_root / "dwimsy" / "meta" / "unbundle.py"
        tree = ast.parse(unb_file.read_text(encoding="utf-8"), filename=str(unb_file))

        top_level_dwimsy_imports = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "dwimsy" or alias.name.startswith("dwimsy."):
                        top_level_dwimsy_imports.append(
                            (node.lineno, ast.unparse(node))
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module == "dwimsy" or (
                    node.module and node.module.startswith("dwimsy.")
                ):
                    top_level_dwimsy_imports.append((node.lineno, ast.unparse(node)))

        self.assertEqual(
            top_level_dwimsy_imports,
            [],
            f"unbundle.py contains illegal top-level module-scope dwimsy imports: {top_level_dwimsy_imports}",
        )


if __name__ == "__main__":
    unittest.main()
