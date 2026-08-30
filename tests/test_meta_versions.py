#!/usr/bin/env python3
"""tests.test_meta_versions - Tests for multi-stream version reconciliation and layering."""

import base64
import io
import lzma
import os
import sys
import unittest
import warnings
from contextlib import redirect_stderr
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.meta import versions
from dwimsy.meta.versions import (
    VersionSpace,
    Stream,
    Layer,
    VersionRef,
    decode_multiblock_base64,
    encode_multiblock_base64,
    demux_lzma_streams,
    parse_semver,
    validate_version_tag,
    _RETAIN_POINT_RELEASES,
    _RETAIN_MINOR_RELEASES,
    _RETAIN_MAJOR_RELEASES,
)


class TestMetaVersions(unittest.TestCase):
    def test_hatchling_empty_blztar(self):
        vspace = VersionSpace.from_blztar("")
        self.assertEqual(len(vspace.streams), 1)
        self.assertEqual(vspace.streams[0].name, "primary")

    def test_empty_base_lzma_stream(self):
        empty_c = lzma.compress(b"")
        b64 = encode_multiblock_base64(empty_c)
        vspace = VersionSpace.from_blztar(b64)
        self.assertEqual(len(vspace.streams), 1)
        self.assertEqual(vspace.streams[0].name, "primary")

    def test_first_layer_sealed_and_unsealed(self):
        unsealed_files = {
            "dwimsy/_version.py": b'__version__ = "0.1.6.0-dev"\n__code_hash__ = ""\n'
        }
        lyr1 = Layer(unsealed_files, is_delta=False)
        self.assertFalse(lyr1.sealed)
        self.assertEqual(lyr1.version_tag, "0.1.6.0-dev")

        sealed_files = {
            "dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "abcdef123456"\n'
        }
        lyr2 = Layer(sealed_files, is_delta=False)
        self.assertTrue(lyr2.sealed)
        self.assertEqual(lyr2.version_tag, "0.1.6.0")

    def test_unsealed_amendment_sequences_and_sealed_historical_tail(self):
        f0 = {
            "dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "h0"\n',
            "a.txt": b"1",
        }
        f1 = {
            "dwimsy/_version.py": b'__version__ = "0.1.6.1-dev"\n__code_hash__ = ""\n',
            "a.txt": b"2",
        }
        f2 = {
            "dwimsy/_version.py": b'__version__ = "0.1.6.2-dev"\n__code_hash__ = ""\n',
            "b.txt": b"3",
        }
        f_hist = {
            "dwimsy/_version.py": b'__version__ = "0.1.5.0"\n__code_hash__ = "h_hist"\n',
            "c.txt": b"4",
        }

        s = Stream(
            0,
            "primary",
            [
                Layer(f0, is_delta=False),
                Layer(f1, is_delta=True),
                Layer(f2, is_delta=True),
                Layer(f_hist, is_delta=False, code_hash="h_hist"),
            ],
        )

        versions = s.get_versions()
        self.assertEqual(len(versions), 4)
        self.assertEqual(versions[0].tag, "0.1.6.0")
        self.assertEqual(versions[1].tag, "0.1.6.1-dev")
        self.assertEqual(versions[2].tag, "0.1.6.2-dev")
        self.assertEqual(versions[3].tag, "0.1.5.0")
        self.assertTrue(versions[3].sealed)

    def test_unreadable_sealed_layer_truncates_only_affected_stream(self):
        f0 = {"dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "h0"\n'}
        l0 = Layer(f0, is_delta=False, code_hash="h0")
        good_tar = l0.get_tar_bytes()
        corrupt_tar = b"not a valid tar header block" * 20
        stream_bytes = good_tar + corrupt_tar

        c = lzma.compress(stream_bytes)
        b64 = encode_multiblock_base64(c)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            vspace = VersionSpace.from_blztar(b64)
        self.assertEqual(len(vspace.streams[0].layers), 1)

    def test_unreadable_sealed_layers_can_truncate_multiple_streams(self):
        f0 = {"dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "h0"\n'}
        l0 = Layer(f0, is_delta=False, code_hash="h0")
        good_tar = l0.get_tar_bytes()
        corrupt_tar = b"garbage data here" * 30

        c1 = lzma.compress(good_tar + corrupt_tar)
        c2 = lzma.compress(good_tar + corrupt_tar)

        b64 = encode_multiblock_base64(c1 + c2)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            vspace = VersionSpace.from_blztar(b64)
        self.assertEqual(len(vspace.streams), 2)
        self.assertEqual(len(vspace.streams[0].layers), 1)
        self.assertEqual(len(vspace.streams[1].layers), 1)

    def test_later_alt_stream_survives_earlier_stream_truncation(self):
        f0 = {"dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "h0"\n'}
        l0 = Layer(f0, is_delta=False, code_hash="h0")
        good_tar = l0.get_tar_bytes()
        corrupt_tar = b"garbage data here" * 30

        c1 = lzma.compress(good_tar + corrupt_tar)
        f_alt = {
            "dwimsy/_version.py": b'__version__ = "0.2.0.0"\n__code_hash__ = "halt"\n'
        }
        l_alt = Layer(f_alt, is_delta=False, code_hash="halt")
        c2 = lzma.compress(l_alt.get_tar_bytes())

        b64 = encode_multiblock_base64(c1 + c2)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            vspace = VersionSpace.from_blztar(b64)
        self.assertEqual(len(vspace.streams), 2)
        self.assertEqual(vspace.streams[1].layers[0].version_tag, "0.2.0.0")

    def test_retention_applies_only_to_primary(self):
        layers_p = [
            Layer(
                {
                    "dwimsy/_version.py": b'__version__ = "0.1.6.5"\n__code_hash__ = "h"\n'
                },
                is_delta=False,
                code_hash="h",
            ),
            Layer(
                {
                    "dwimsy/_version.py": b'__version__ = "0.1.6.4"\n__code_hash__ = "h4"\n'
                },
                is_delta=False,
                code_hash="h4",
            ),
            Layer(
                {
                    "dwimsy/_version.py": b'__version__ = "0.1.6.3"\n__code_hash__ = "h3"\n'
                },
                is_delta=False,
                code_hash="h3",
            ),
            Layer(
                {
                    "dwimsy/_version.py": b'__version__ = "0.1.6.2"\n__code_hash__ = "h2"\n'
                },
                is_delta=False,
                code_hash="h2",
            ),
            Layer(
                {
                    "dwimsy/_version.py": b'__version__ = "0.1.6.1"\n__code_hash__ = "h1"\n'
                },
                is_delta=False,
                code_hash="h1",
            ),
            Layer(
                {
                    "dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "h0"\n'
                },
                is_delta=False,
                code_hash="h0",
            ),
        ]
        s_prim = Stream(0, "primary", layers_p)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            s_prim.apply_retention()
        self.assertEqual(len(s_prim.layers), 4)

        s_alt = Stream(
            1,
            "alt1",
            [
                Layer(
                    {
                        "dwimsy/_version.py": b'__version__ = "0.1.6.5"\n__code_hash__ = "h"\n'
                    },
                    is_delta=False,
                    code_hash="h",
                ),
                Layer(
                    {
                        "dwimsy/_version.py": b'__version__ = "0.1.6.4"\n__code_hash__ = "h4"\n'
                    },
                    is_delta=False,
                    code_hash="h4",
                ),
                Layer(
                    {
                        "dwimsy/_version.py": b'__version__ = "0.1.6.3"\n__code_hash__ = "h3"\n'
                    },
                    is_delta=False,
                    code_hash="h3",
                ),
                Layer(
                    {
                        "dwimsy/_version.py": b'__version__ = "0.1.6.2"\n__code_hash__ = "h2"\n'
                    },
                    is_delta=False,
                    code_hash="h2",
                ),
                Layer(
                    {
                        "dwimsy/_version.py": b'__version__ = "0.1.6.1"\n__code_hash__ = "h1"\n'
                    },
                    is_delta=False,
                    code_hash="h1",
                ),
            ],
        )
        s_alt.apply_retention()
        self.assertEqual(len(s_alt.layers), 5)

    def test_lzma_stream_boundary_without_base64_padding(self):
        c1 = None
        for n in range(10, 200):
            data = b"X" * n
            cand = lzma.compress(data)
            if len(cand) % 3 == 0:
                c1 = cand
                break
        self.assertIsNotNone(c1)
        self.assertEqual(len(c1) % 3, 0)

        c2 = lzma.compress(b"Stream 2 data")
        raw_concat = c1 + c2
        b64 = base64.b64encode(raw_concat).decode("ascii")

        uncomp, chunks = demux_lzma_streams(decode_multiblock_base64(b64))
        self.assertEqual(len(uncomp), 2)
        self.assertEqual(len(chunks), 2)

    def test_sealed_is_reserved_case_insensitively(self):
        with self.assertRaises(ValueError):
            validate_version_tag("sealed")
        with self.assertRaises(ValueError):
            validate_version_tag("SEALED")
        with self.assertRaises(ValueError):
            validate_version_tag("Sealed")

    def test_terminal_sealed_suffix_is_reserved_case_insensitively(self):
        with self.assertRaises(ValueError):
            validate_version_tag("0.2.1_sealed")
        with self.assertRaises(ValueError):
            validate_version_tag("0.2.1_SEALED")
        with self.assertRaises(ValueError):
            validate_version_tag("0.2.1_-_GPT9_sealed")

    def test_valid_version_tags(self):
        validate_version_tag("0.2.1_-_GPT9")
        validate_version_tag("0.2.1-rc1")
        validate_version_tag("1.0.0+build1")

    def test_sealed_layer_in_primary_tip_raises_hard_error(self):
        """Spec §1.1.1: sealed tar after layer 0 in primary tip sequence raises fatal error."""
        f0 = {
            "dwimsy/__init__.py": b"x=1\n",
            "dwimsy/_version.py": b'__version__ = "0.1.6.0-dev"\n__code_hash__ = ""\n',
        }
        f1_sealed = {
            "dwimsy/__init__.py": b"x=2\n",
            "dwimsy/_version.py": b'__version__ = "0.1.6.1-dev"\n__code_hash__ = "h1"\n',
        }
        lyr0 = Layer(f0, is_delta=False, version_tag="0.1.6.0-dev")
        lyr1_sealed = Layer(
            f1_sealed, is_delta=True, version_tag="0.1.6.1-dev", code_hash="h1"
        )
        tar_bytes = lyr0.get_tar_bytes() + lyr1_sealed.get_tar_bytes()
        with self.assertRaises(RuntimeError) as cm:
            versions.parse_tar_layers_from_bytes(tar_bytes, stream_name="primary")
        self.assertIn(
            "sealed tar encountered at layer 1 in open development tip sequence",
            str(cm.exception),
        )

    def test_duplicate_version_in_primary_open_dev_raises_fatal_error(self):
        """Spec §1.1.1: duplicate version tag in primary stream open dev tip raises early hard error."""
        f0 = {
            "dwimsy/__init__.py": b"x=1\n",
            "dwimsy/_version.py": b'__version__ = "0.1.6.0-dev"\n__code_hash__ = ""\n',
        }
        f1 = {
            "dwimsy/__init__.py": b"x=2\n",
            "dwimsy/_version.py": b'__version__ = "0.1.6.0-dev"\n__code_hash__ = ""\n',
        }
        lyr0 = Layer(f0, is_delta=False, version_tag="0.1.6.0-dev")
        lyr1 = Layer(f1, is_delta=True, version_tag="0.1.6.0-dev")
        tar_bytes = lyr0.get_tar_bytes() + lyr1.get_tar_bytes()
        with self.assertRaises(RuntimeError) as cm:
            versions.parse_tar_layers_from_bytes(tar_bytes, stream_name="primary")
        self.assertIn(
            "is not strictly greater than preceding tip semver", str(cm.exception)
        )

    def test_adding_duplicate_version_to_stream_raises_hard_error(self):
        """Spec §1.1.1: attempting to add duplicate version tag to any stream raises ValueError."""
        f0 = {"dwimsy/_version.py": b'__version__ = "0.1.6.0"\n__code_hash__ = "h0"\n'}
        st = Stream(0, "primary", [Layer(f0, is_delta=False, version_tag="0.1.6.0")])
        with self.assertRaises(ValueError) as cm:
            st.append_layer(Layer(f0, is_delta=True, version_tag="0.1.6.0"))
        self.assertIn("Cannot add duplicate version tag '0.1.6.0'", str(cm.exception))

    def test_duplicate_version_in_alt_stream_invalidates_stream(self):
        """Spec §1.1.1: duplicate version tag in alt stream invalidates remainder with warning."""
        f0 = {
            "dwimsy/__init__.py": b"x=1\n",
            "dwimsy/_version.py": b'__version__ = "0.1.6.0-dev"\n__code_hash__ = ""\n',
        }
        f1 = {
            "dwimsy/__init__.py": b"x=2\n",
            "dwimsy/_version.py": b'__version__ = "0.1.6.0-dev"\n__code_hash__ = ""\n',
        }
        lyr0 = Layer(f0, is_delta=False, version_tag="0.1.6.0-dev")
        lyr1 = Layer(f1, is_delta=True, version_tag="0.1.6.0-dev")
        tar_bytes = lyr0.get_tar_bytes() + lyr1.get_tar_bytes()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", UserWarning)
            parsed = versions.parse_tar_layers_from_bytes(tar_bytes, stream_name="alt1")
        self.assertEqual(len(parsed), 0)
        self.assertTrue(
            any(
                "alternate stream 'alt1' invalidated" in str(item.message) for item in w
            )
        )


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


class TestSelectionSets(unittest.TestCase):
    def _space(self):
        primary = Stream(
            0,
            "primary",
            [
                Layer(
                    {
                        "dwimsy/_version.py": b'__version__ = "0.1.6.10-dev"\n__code_hash__ = ""\n',
                        "p": b"p",
                    },
                    is_delta=False,
                )
            ],
        )
        alt1 = Stream(
            1,
            "alt1",
            [
                Layer(
                    {
                        "dwimsy/_version.py": b'__version__ = "0.1.6.11-dev"\n__code_hash__ = ""\n',
                        "a1": b"1",
                    },
                    is_delta=False,
                )
            ],
        )
        alt2 = Stream(
            2,
            "alt2",
            [
                Layer(
                    {
                        "dwimsy/_version.py": b'__version__ = "0.1.6.12-dev"\n__code_hash__ = ""\n',
                        "a2": b"2",
                    },
                    is_delta=False,
                )
            ],
        )
        return VersionSpace([primary, alt1, alt2])

    def test_bare_alt_resolves_all_alternate_heads(self):
        space = self._space()
        selection = space.resolve_selection("alt")
        self.assertTrue(selection.is_multi)
        self.assertEqual([item.stream.name for item in selection], ["alt1", "alt2"])
        self.assertEqual(
            [item.version.tag for item in selection], ["0.1.6.11-dev", "0.1.6.12-dev"]
        )

    def test_multi_selection_alt_creates_shadow_streams_without_touching_primary(self):
        space = self._space()
        primary_tag = space.streams[0].get_head_version().tag
        selection = space.resolve_selection("alt")
        space.branch_selection(selection)
        self.assertEqual(space.streams[0].get_head_version().tag, primary_tag)
        self.assertEqual(len(space.streams), 5)
        self.assertEqual(
            [s.name for s in space.streams], ["primary", "alt1", "alt2", "alt3", "alt4"]
        )
        self.assertEqual(space.streams[3].get_head_version().tag, "0.1.6.11-dev")
        self.assertEqual(space.streams[4].get_head_version().tag, "0.1.6.12-dev")
        self.assertEqual(
            space.streams[3].materialize_layer_state(0),
            space.streams[1].materialize_layer_state(0),
        )

    def test_baseline_excludes_terminal_mod_overlay(self):
        space = self._space()
        primary = space.streams[0]
        primary.append_layer(
            Layer(
                {
                    "dwimsy/_version.py": b'__version__ = "0.1.6.10+mod.abc"\n__code_hash__ = ""\n',
                    "p": b"modified",
                },
                is_delta=True,
                version_tag="0.1.6.10+mod.abc",
            )
        )
        primary_sel = space.resolve_selection("primary")
        baseline_sel = space.resolve_selection("baseline")
        self.assertEqual(primary_sel.first.version.tag, "0.1.6.10+mod.abc")
        self.assertEqual(baseline_sel.first.version.tag, "0.1.6.10-dev")

    def test_mod_replacement_only_allows_same_base_or_forward_progress(self):
        space = self._space()
        primary = space.streams[0]
        primary.append_layer(
            Layer(
                {
                    "dwimsy/_version.py": b'__version__ = "0.1.6.10+mod.abc"\n__code_hash__ = ""\n'
                },
                is_delta=True,
                version_tag="0.1.6.10+mod.abc",
            )
        )
        with self.assertRaises(ValueError):
            primary.append_layer(
                Layer({}, is_delta=True, version_tag="0.1.6.9"), allow_replacement=True
            )
        primary.append_layer(
            Layer({}, is_delta=True, version_tag="0.1.6.10+mod.def"),
            allow_replacement=True,
        )
        self.assertEqual(primary.layers[-1].version_tag, "0.1.6.10+mod.def")
        primary.append_layer(
            Layer({}, is_delta=True, version_tag="0.1.6.11-dev"), allow_replacement=True
        )
        self.assertEqual(primary.layers[-1].version_tag, "0.1.6.11-dev")
