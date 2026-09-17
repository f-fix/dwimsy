#!/usr/bin/env python3
"""tests.test_prog_name_dispatcher_consistency - every argparse prog=
must be a name the dispatcher actually routes back to that same command,
across -a override, symlink basename, and bare positional forms; no
truncated/impostor/mis-spelled variant may resolve to the same target."""

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

from dwimsy.meta.unbundle import resolve_argv0_command

EXPECTED_TARGETS = {
    "dwimsy/meta/lint.py": ["meta", "lint"],
    "dwimsy/meta/integrity.py": ["meta", "integrity"],
    "dwimsy/meta/diff.py": ["meta", "diff"],
    "dwimsy/meta/version_bump.py": ["meta", "version-bump"],
    "dwimsy/meta/bundle.py": ["meta", "bundle"],
    "dwimsy/tests/__main__.py": ["tests"],
    "dwimsy/cli/filters/wav2t88.py": ["wav2t88"],
    "dwimsy/cli/filters/t882wav.py": ["t882wav"],
}

MUST_NOT_RESOLVE = {
    "dwimsy-bundle": ["meta", "bundle"],
    "dwimsy-lint": ["meta", "lint"],
    "dwimsy-meta-bundle-fixtures-extra": ["meta", "bundle-fixtures"],
}

FUSED_AND_SPACE_SPELLINGS_MUST_FAIL = [
    "dwimsy-meta-versionbump",
    "dwimsy-meta-version bump",
    "dwimsy-meta-bundlefixtures",
    "dwimsy-meta-bundle fixtures",
    "dwimsy-meta-fetchdeps",
    "dwimsy-meta-fetch deps",
]

UNDERSCORE_SPELLINGS_MUST_RESOLVE = [
    ("dwimsy-meta-version_bump", ["meta", "version-bump"]),
    ("dwimsy-meta-bundle_fixtures", ["meta", "bundle-fixtures"]),
    ("dwimsy-meta-fetch_deps", ["meta", "fetch-deps"]),
]

MIXED_SPELLING_FORMS_MUST_RESOLVE = [
    (["dwimsy-meta-version-bump"], ["meta", "version-bump"]),
    (["dwimsy-meta-version_bump"], ["meta", "version-bump"]),
    (["dwimsy-meta", "version-bump"], ["meta", "version-bump"]),
    (["dwimsy", "meta", "version-bump"], ["meta", "version-bump"]),
    (["dwimsy", "meta-version-bump"], ["meta", "version-bump"]),
]


def _prog_literal(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "prog":
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
    return None


class TestProgNameDispatcherConsistency(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_every_entry_point_prog_resolves_to_its_own_target(self):
        for rel_path, target in EXPECTED_TARGETS.items():
            with self.subTest(module=rel_path):
                prog = _prog_literal(self.repo_root / rel_path)
                self.assertIsNotNone(prog, f"{rel_path}: no literal prog= found")
                self.assertEqual(resolve_argv0_command(prog), target)

    def test_argv0_and_symlink_forms_agree(self):
        for rel_path, target in EXPECTED_TARGETS.items():
            prog = _prog_literal(self.repo_root / rel_path)
            with self.subTest(module=rel_path):
                self.assertEqual(resolve_argv0_command(prog), target)
                self.assertEqual(resolve_argv0_command(f"/usr/local/bin/{prog}"), target)

    def test_known_impostor_names_do_not_resolve(self):
        for name, real_target in MUST_NOT_RESOLVE.items():
            with self.subTest(name=name):
                self.assertNotEqual(resolve_argv0_command(name), real_target)

    def test_fused_and_space_spellings_fail(self):
        for name in FUSED_AND_SPACE_SPELLINGS_MUST_FAIL:
            with self.subTest(name=name):
                self.assertEqual(resolve_argv0_command(name), [])

    def test_underscore_spellings_resolve_to_canonical_commands(self):
        for name, expected in UNDERSCORE_SPELLINGS_MUST_RESOLVE:
            with self.subTest(name=name):
                self.assertEqual(resolve_argv0_command(name), expected)

    @unittest.skipIf(
        os.environ.get("DWIMSY_BUNDLE_BUILD") == "1"
        or os.environ.get("DWIMSY_STANDALONE_TEST") == "1"
        or os.environ.get("DWIMSY_WITHOUT_SUBPROCESS") == "1"
        or sys.platform in ("emscripten", "wasi"),
        "Subprocess execution disabled during bundle build or on Emscripten/WASI",
    )
    def test_bare_positional_forms_all_dispatch_identically(self):
        bundle = self.repo_root
        for argv, _target in MIXED_SPELLING_FORMS_MUST_RESOLVE:
            with self.subTest(argv=argv):
                res = subprocess.run(
                    [sys.executable, "-m", "dwimsy", *argv, "--help"],
                    cwd=str(bundle),
                    capture_output=True,
                    text=True,
                )
                self.assertIn("usage: dwimsy meta version-bump", res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
