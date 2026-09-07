"""tests.test_meta_diff - Verify standalone diff isolation rules."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dwimsy.meta import diff


class TestStandaloneDiffIsolation(unittest.TestCase):
    def test_bare_diff_does_not_infer_surrounding_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            (cwd / "dwimsy").mkdir()
            (cwd / "dwimsy" / "__init__.py").write_text("\n", encoding="utf-8")
            with patch.object(diff.integrity, "is_standalone_bundle", return_value=True):
                with patch.object(diff.Path, "cwd", return_value=cwd):
                    with self.assertRaisesRegex(ValueError, "could not be resolved"):
                        diff.render_diff()
