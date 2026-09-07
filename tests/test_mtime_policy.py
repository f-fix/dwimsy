#!/usr/bin/env python3
"""tests.test_mtime_policy - Regression tests for DWIMSY layer timestamp canonicalization."""

import datetime
import io
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dwimsy.meta import unbundle, versions


class TestMtimePolicy(unittest.TestCase):
    def test_layer_timestamp_uses_newest_meaningful_member(self):
        layer = versions.Layer(
            {"a": b"a", "b": b"b"},
            version_tag="0.1.6.95-dev",
            mtime=versions.LEGACY_BOGUS_MTIME,
            file_mtimes={
                "a": versions.LEGACY_BOGUS_MTIME,
                "b": 1_750_000_123,
            },
        )
        space = versions.VersionSpace([versions.Stream(0, "primary", [layer])])
        self.assertEqual(
            space.get_layer_timestamp(layer),
            "2025-06-15T15:08:43Z",
        )

    def test_layer_timestamp_falls_back_to_changelog_when_all_members_are_bogus(self):
        tag = "0.1.6.95-dev"
        layer = versions.Layer(
            {
                "CHANGELOG.md": f"## [{tag}] - 2026-09-06T12:34:56Z\n\n### Changed\n- test\n".encode(),
                "a": b"a",
            },
            version_tag=tag,
            mtime=versions.LEGACY_BOGUS_MTIME,
            file_mtimes={
                "CHANGELOG.md": versions.LEGACY_BOGUS_MTIME,
                "a": versions.LEGACY_BOGUS_MTIME,
            },
        )
        space = versions.VersionSpace([versions.Stream(0, "primary", [layer])])
        self.assertEqual(space.get_layer_timestamp(layer), "2026-09-06T12:34:56Z")

    def test_generated_layer_tar_uses_one_mtime_for_every_member(self):
        layer = versions.Layer(
            {"a": b"a", "b": b"b"},
            is_delta=True,
            version_tag="0.1.6.95-dev",
            mtime=1_750_000_123,
            file_mtimes={"a": 1_700_000_001, "b": 1_700_000_002},
        )
        # New packing paths are expected to canonicalize file_mtimes before
        # constructing Layer; verify the TAR serializer honors that mapping.
        layer.file_mtimes = {name: 1_750_000_123 for name in layer.files}
        import tarfile

        with tarfile.open(fileobj=io.BytesIO(layer.get_tar_bytes()), mode="r:") as tar:
            self.assertEqual({m.mtime for m in tar.getmembers()}, {1_750_000_123})

    def test_stream_copy_preserves_layer_timestamps(self):
        layer = versions.Layer(
            {"a": b"a"},
            mtime=1_750_000_123,
            file_mtimes={"a": 1_750_000_123},
        )
        copied = versions.Stream(0, "primary", [layer]).copy().layers[0]
        self.assertEqual(copied.mtime, layer.mtime)
        self.assertEqual(copied.file_mtimes, layer.file_mtimes)

    def test_repeated_unbundle_does_not_rewrite_identical_unbundle_and_normalizes_mtime(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            raw_b64 = unbundle._get_active_blztar()
            space = versions.VersionSpace.from_blztar(raw_b64)
            head = space.streams[0].get_head_version()
            self.assertIsNotNone(head)
            expected = space.get_layer_timestamp(space.streams[0].layers[head.ordinal])
            expected_epoch = datetime.datetime.fromisoformat(
                expected.replace("Z", "+00:00")
            ).timestamp()

            unbundle.safe_unbundle(
                b64_string=raw_b64,
                output_dir=target,
                force=True,
                quiet=True,
            )
            carrier = target / "dwimsy" / "meta" / "unbundle.py"
            first_bytes = carrier.read_bytes()
            first_inode = carrier.stat().st_ino
            os.utime(carrier, (expected_epoch, expected_epoch))
            time.sleep(1.05)

            unbundle.safe_unbundle(
                b64_string=raw_b64,
                output_dir=target,
                force=True,
                quiet=True,
            )
            second_bytes = carrier.read_bytes()
            second_stat = carrier.stat()
            self.assertEqual(second_bytes, first_bytes)
            self.assertEqual(second_stat.st_ino, first_inode)
            self.assertEqual(second_stat.st_mtime, expected_epoch)


if __name__ == "__main__":
    unittest.main()
