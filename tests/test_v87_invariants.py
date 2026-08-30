#!/usr/bin/env python3
"""tests.test_v87_invariants - Tests for Spec v8.6 and Addendum v8.7-DRAFT stream reading, writing, and argument invariants."""

from __future__ import annotations

import io
import os
import re
import tarfile
import tempfile
import unittest
import warnings
from pathlib import Path

from dwimsy.meta.versions import (
    Layer,
    Stream,
    VersionSpace,
    compute_raw_tar_hash,
    parse_semver,
    parse_tar_layers_from_bytes,
)
from dwimsy.meta.unbundle import parse_early_pipeline_flags, safe_unbundle
from dwimsy.meta import integrity
from dwimsy.meta.version_bump import parse_and_bump_version
from dwimsy.meta import unbundle, version_bump


def _make_tar_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:") as tar:
        for name, data in files.items():
            ti = tarfile.TarInfo(name=name)
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))
    val = buf.getvalue()
    pad = (512 - (len(val) % 512)) % 512
    return val + (b"\x00" * pad)


class TestV87StreamInvariants(unittest.TestCase):
    """Tests for stream decoding and invariant validation rules (§1.1, §1.2, §1.3, §1.4)."""

    def test_pure_semver_position_layer_determination(self):
        """Verify position index 0 is base snapshot, tip overlays are deltas, and sealed area is base snapshots."""
        tar0 = _make_tar_bytes(
            {
                "dwimsy/__init__.py": b"",
                "dwimsy/_version.py": b'__version__ = "0.1.6.10-dev"\n__code_hash__ = ""\n',
            }
        )
        tar1 = _make_tar_bytes(
            {
                "dwimsy/feature.py": b"# new",
                "dwimsy/_version.py": b'__version__ = "0.1.6.11-dev"\n__code_hash__ = ""\n',
            }
        )
        tar2 = _make_tar_bytes(
            {
                "dwimsy/sealed.py": b"# sealed",
                "dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "abcd1234abcd1234"\n',
            }
        )

        raw = tar0 + tar1 + tar2
        layers = parse_tar_layers_from_bytes(raw, stream_name="primary")
        self.assertEqual(len(layers), 3)
        self.assertFalse(layers[0].is_delta)
        self.assertTrue(layers[1].is_delta)
        self.assertFalse(layers[2].is_delta)

    def test_primary_stream_tip_sealed_violation_raises_runtime_error(self):
        """Verify that a sealed layer in the tip sequence of the primary stream raises a fatal RuntimeError."""
        tar0 = _make_tar_bytes(
            {
                "dwimsy/_version.py": b'__version__ = "0.1.6.10-dev"\n__code_hash__ = ""\n'
            }
        )
        tar1 = _make_tar_bytes(
            {
                "dwimsy/_version.py": b'__version__ = "0.1.6.11-dev"\n__code_hash__ = "canonical_hash_1234"\n'
            }
        )
        raw = tar0 + tar1
        with self.assertRaises(RuntimeError):
            parse_tar_layers_from_bytes(raw, stream_name="primary")

    def test_alternate_stream_tip_violation_drops_layers_and_warns(self):
        """Verify that a tip violation in an alternate stream drops all layers and emits a UserWarning."""
        tar0 = _make_tar_bytes(
            {
                "dwimsy/_version.py": b'__version__ = "0.1.6.10-dev"\n__code_hash__ = ""\n'
            }
        )
        tar1 = _make_tar_bytes(
            {
                "dwimsy/_version.py": b'__version__ = "0.1.6.11-dev"\n__code_hash__ = "canonical_hash_1234"\n'
            }
        )
        raw = tar0 + tar1
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            layers = parse_tar_layers_from_bytes(raw, stream_name="alt1")
            self.assertEqual(layers, [])
            self.assertTrue(any(issubclass(item.category, UserWarning) for item in w))

    def test_primary_stream_non_monotonic_semver_raises_runtime_error(self):
        """Verify duplicate or decreasing semver in tip sequence of primary stream raises RuntimeError."""
        tar0 = _make_tar_bytes(
            {
                "dwimsy/_version.py": b'__version__ = "0.1.6.10-dev"\n__code_hash__ = ""\n'
            }
        )
        tar1 = _make_tar_bytes(
            {
                "dwimsy/_version.py": b'__version__ = "0.1.6.10-dev"\n__code_hash__ = ""\n'
            }
        )
        raw = tar0 + tar1
        with self.assertRaises(RuntimeError):
            parse_tar_layers_from_bytes(raw, stream_name="primary")

    def test_sealed_area_with_removal_markers_truncates_stream(self):
        """Verify that removal markers in sealed area truncate stream processing."""
        tar0 = _make_tar_bytes(
            {
                "dwimsy/_version.py": b'__version__ = "0.1.6.10-dev"\n__code_hash__ = ""\n'
            }
        )
        tar1 = _make_tar_bytes(
            {
                ".wh.old_file": b"",
                "dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "abcd1234"\n',
            }
        )
        raw = tar0 + tar1
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            layers = parse_tar_layers_from_bytes(raw, stream_name="primary")
            self.assertEqual(len(layers), 1)

    def test_append_layer_validation(self):
        """Verify Stream.append_layer() enforces writing invariants (§1.4)."""
        st = Stream(
            0,
            "primary",
            [
                Layer(
                    {
                        "dwimsy/_version.py": b'__version__ = "0.1.6.10-dev"\n__code_hash__ = ""\n'
                    },
                    is_delta=False,
                    version_tag="0.1.6.10-dev",
                )
            ],
        )
        # Sealed in tip sequence
        with self.assertRaises(ValueError):
            st.append_layer(
                Layer(
                    {"dwimsy/_version.py": b""},
                    is_delta=True,
                    version_tag="0.1.6.11-dev",
                    code_hash="abc",
                )
            )
        # Non-delta in tip sequence
        with self.assertRaises(ValueError):
            st.append_layer(
                Layer(
                    {"dwimsy/_version.py": b""},
                    is_delta=False,
                    version_tag="0.1.6.11-dev",
                )
            )
        # Decreasing semver in tip sequence
        with self.assertRaises(ValueError):
            st.append_layer(
                Layer(
                    {"dwimsy/_version.py": b""},
                    is_delta=True,
                    version_tag="0.1.6.9-dev",
                )
            )

    def test_serializer_roundtrip_validation(self):
        """Verify Stream.encode_lzma_bytes and VersionSpace.to_blztar validate layers during serialization."""
        st = Stream(
            0,
            "primary",
            [
                Layer(
                    {
                        "dwimsy/_version.py": b'__version__ = "0.1.6.10-dev"\n__code_hash__ = ""\n'
                    },
                    is_delta=False,
                    version_tag="0.1.6.10-dev",
                )
            ],
        )
        lzma_bytes = st.encode_lzma_bytes()
        self.assertGreater(len(lzma_bytes), 0)

        vs = VersionSpace([st])
        b64 = vs.to_blztar()
        self.assertGreater(len(b64), 0)


class TestV87ScannerAndUnbundle(unittest.TestCase):
    """Tests for Tier 1 DWIM scanner and safe unbundling (§2.1, §3.1)."""

    def test_parse_early_pipeline_flags_returns_all_schema_keys(self):
        """Verify parse_early_pipeline_flags returns the complete required schema dictionary."""
        pipeline, remaining = parse_early_pipeline_flags(["convert", "-v"])
        required_keys = {
            "argv0",
            "argv0_overridden",
            "operations",
            "vspace",
            "selected_ref",
            "effective_version",
            "version_snapshots",
            "short_v_count",
            "explicit_verbose_count",
            "verbosity",
            "test_mode",
            "test_pattern",
            "print_version",
            "early_exit",
            "version_list_snapshot",
            "include",
            "restrict_to",
            "prune",
            "splice",
            "alt",
            "version",
            "list_versions",
            "version_help",
        }
        for k in required_keys:
            self.assertIn(k, pipeline)

    def test_verb_scope_reset_on_a(self):
        """Verify that -a NAME discards Tier 2 positionals while preserving Tier 1 state."""
        args = [
            "convert",
            "--baud=1200",
            "input.wav",
            "-a",
            "t882wav",
            "in.t88",
            "out.wav",
        ]
        pipeline, remaining = parse_early_pipeline_flags(args)
        self.assertTrue(pipeline["argv0_overridden"])
        self.assertEqual(remaining, ["in.t88", "out.wav"])

    def test_option_with_equals_sign_matching(self):
        """Verify --option=value arguments are parsed without requiring trailing equals."""
        args = ["--version=baseline", "--test=audio"]
        pipeline, remaining = parse_early_pipeline_flags(args)
        self.assertTrue(pipeline["test_mode"])
        self.assertEqual(pipeline["test_pattern"], "audio")
        self.assertEqual(pipeline["version"], "baseline")

    def test_type_collision_guard_in_safe_unbundle(self):
        """Verify safe_unbundle detects type collision when target file exists as directory."""
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            (tmpdir / "dwimsy").mkdir(parents=True, exist_ok=True)
            (tmpdir / "dwimsy" / "_version.py").mkdir(parents=True, exist_ok=True)

            with self.assertRaises(RuntimeError) as ctx:
                safe_unbundle(output_dir=tmpdir, force=False)
            self.assertIn("Type collision", str(ctx.exception))

    def test_surviving_state_verification_message(self):
        """Verify precision remediation guidance message when local work would be overwritten."""
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            (tmpdir / "dwimsy").mkdir(parents=True, exist_ok=True)
            (tmpdir / "dwimsy" / "_version.py").write_text("# modified on disk\n")

            with self.assertRaises(RuntimeError) as ctx:
                safe_unbundle(output_dir=tmpdir, force=False)
            msg = str(ctx.exception)
            self.assertIn("would overwrite modified on-disk state", msg)
            self.assertIn("--version-include-primary=", msg)
            self.assertIn("--version-include-alt=", msg)
            self.assertIn("--version-include=", msg)

    def test_safe_unbundle_omits_identical_files_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            (tmpdir / "README.md").write_bytes(unbundle.get_asset("README.md"))
            buf = io.StringIO()
            safe_unbundle(output_dir=tmpdir, force=False, stdout=buf)
            self.assertNotIn("[IDENTICAL]", buf.getvalue())

    def test_safe_unbundle_rejects_intermediate_symlink(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            tmpdir = Path(tmp)
            outside_dir = Path(outside)
            (tmpdir / "dwimsy").symlink_to(outside_dir, target_is_directory=True)
            with self.assertRaises(RuntimeError) as ctx:
                safe_unbundle(output_dir=tmpdir, force=False)
            self.assertIn("symlink", str(ctx.exception))


class TestVersionBumpChangelogFormatting(unittest.TestCase):
    """Tests for successive version bump changelog formatting and newline invariants."""

    def test_successive_version_bumps_never_exceed_two_consecutive_newlines(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "dwimsy").mkdir(parents=True, exist_ok=True)
            (tmp_root / "dwimsy" / "_version.py").write_text(
                '__version__ = "0.1.6.40-dev"\n__code_hash__ = ""\n'
            )
            (tmp_root / "README.md").write_text(
                "# Test\n**Version: 0.1.6.40-dev** (2026-08-29)\n"
            )
            (tmp_root / "CHANGELOG.md").write_text(
                "# Changelog\n\nAll notable changes.\n\n## [0.1.6.40-dev] - 2026-08-29\n\n### Changed\n- Initial baseline.\n"
            )

            # Perform 3 successive version bumps
            version_bump.bump_version(
                version_str="0.1.6.41-dev",
                repo_root=tmp_root,
                message="First bump",
                no_bundle=True,
            )
            version_bump.bump_version(
                version_str="0.1.6.42-dev",
                repo_root=tmp_root,
                message="Second bump",
                no_bundle=True,
            )
            version_bump.bump_version(
                version_str="0.1.6.43-dev",
                repo_root=tmp_root,
                message="Third bump",
                no_bundle=True,
            )

            c_text = (tmp_root / "CHANGELOG.md").read_text(encoding="utf-8")
            self.assertNotIn(
                "\n\n\n", c_text, "Found 3 or more consecutive newlines in CHANGELOG.md"
            )
            self.assertIn("## [0.1.6.43-dev]", c_text)
            self.assertIn("## [0.1.6.42-dev]", c_text)
            self.assertIn("## [0.1.6.41-dev]", c_text)
            self.assertIn("## [0.1.6.40-dev]", c_text)

    def test_rev_bump_parses_live_mod_suffixed_version(self):
        """Verify --rev can advance past a live +mod.<hash> terminal snapshot (§1.6.1)."""
        self.assertEqual(
            parse_and_bump_version("0.1.6.50-dev+mod.daf3d6f53a96", part="rev"),
            "0.1.6.51-dev",
        )

    def test_mod_suffix_replaces_rather_than_stacks(self):
        """Verify integrity.version() replaces an existing +mod.<hash> suffix
        rather than stacking a second one on repeated modification cycles
        (§1.6.1: 'X+mod.a' -> 'X+mod.b', never 'X+mod.a+mod.b')."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "dwimsy").mkdir()
            (tmp_root / "dwimsy" / "_version.py").write_text(
                '__version__ = "0.1.6.50-dev+mod.daf3d6f53a96"\n__code_hash__ = ""\n'
            )
            orig_is_modified = integrity.is_modified
            orig_mod_hash = integrity.modification_hash
            integrity.is_modified = lambda root=None: True
            integrity.modification_hash = lambda root=None: "newhash123456"
            try:
                result = integrity.version(root=tmp_root)
            finally:
                integrity.is_modified = orig_is_modified
                integrity.modification_hash = orig_mod_hash
            self.assertEqual(result, "0.1.6.50-dev+mod.newhash123456")
            self.assertEqual(result.count("+mod."), 1)

    def test_version_list_verbose_shows_full_hash_regardless_of_flag_order(self):
        """Verify --version-list picks up --verbose as a global detail toggle,
        not a position-bound pipeline flag: both `--version-list --verbose`
        and `--verbose --version-list` must show the full 64-char hash."""
        pipeline_a, _ = parse_early_pipeline_flags(["--version-list", "--verbose"])
        pipeline_b, _ = parse_early_pipeline_flags(["--verbose", "--version-list"])
        for pipeline in (pipeline_a, pipeline_b):
            snapshot = pipeline["version_list_snapshot"]
            self.assertIsNotNone(snapshot)
            hashes = re.findall(r"\b[0-9a-f]{64}\b", snapshot)
            self.assertTrue(hashes, f"expected a full 64-char hash in: {snapshot!r}")

    def test_version_list_default_shows_short_hash(self):
        """Verify --version-list without --verbose shows the 12-char short
        hash by default (matches the +mod.<short_hash> convention)."""
        pipeline, _ = parse_early_pipeline_flags(["--version-list"])
        snapshot = pipeline["version_list_snapshot"]
        self.assertIsNotNone(snapshot)
        self.assertFalse(re.findall(r"\b[0-9a-f]{64}\b", snapshot))
        self.assertTrue(re.findall(r"\b[0-9a-f]{12}\b", snapshot))


if __name__ == "__main__":
    unittest.main()
