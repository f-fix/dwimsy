#!/usr/bin/env python3
"""tests.test_tape_t88 - Tests for T88 container parsing, serialization, split, and join."""

import io
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dwimsy.tape.t88 import (
    T88Tag,
    T88Block,
    T88File,
    DataSubHeader,
    split_t88_file,
    join_t88_files,
)
from dwimsy.protocols.pc88 import CMTFile


class TestTapeT88(unittest.TestCase):
    @staticmethod
    def _make_ml_file(name: bytes, addr: int, data: bytes) -> bytes:
        lead = b"\x24" * 10 + name.ljust(6, b" ")[:6]
        ah = (addr >> 8) & 0xFF
        al = addr & 0xFF
        achk = (0 - (ah + al)) & 0xFF
        addr_rec = struct.pack("BBBB", 0x3A, ah, al, achk)
        dlen = len(data)
        dchk = (0 - (dlen + sum(data))) & 0xFF
        data_rec = struct.pack("BB", 0x3A, dlen) + data + struct.pack("B", dchk)
        term_rec = b"\x3a\x00\x00"
        return lead + addr_rec + data_rec + term_rec

    def setUp(self) -> None:
        self.ml_file = self._make_ml_file(
            b"BIN001", 0x8000, b"\x21\x00\x80\x3e\x01\xcd\x00\x00"
        )
        self.basic_file = (
            (b"\xd3" * 10 + b"PROG01")
            + (b"\xd3" * 10)
            + struct.pack("<HH", 0x8010, 10)
            + b'\x90 "HELLO WORLD"'
            + b"\x00"
            + struct.pack("<H", 0x0000)
        )
        self.combined_cmt = self.ml_file + self.basic_file

    def test_t88_block_pack_unpack(self) -> None:
        header = DataSubHeader(0, 440, 10, 0).pack()
        b_data = T88Block(T88Tag.DATA_1200, header + b"1234567890")
        p_data = b_data.pack()
        u_data = T88Block.unpack(io.BytesIO(p_data))
        self.assertIsNotNone(u_data)
        if u_data is not None:
            self.assertEqual(u_data.tag, T88Tag.DATA_1200)
            self.assertEqual(u_data.length, len(header) + 10)
            self.assertEqual(u_data.data, header + b"1234567890")

    def test_t88_file_pack_unpack(self) -> None:
        t88 = T88File.from_cmt_data(self.ml_file, comment="Authentic Test Image")
        packed = t88.pack()
        unpacked = T88File.unpack(io.BytesIO(packed))
        self.assertTrue(T88File.is_valid_magic(unpacked.magic))
        self.assertEqual(unpacked.version, 0x0100)
        self.assertEqual(unpacked.extract_cmt_payload(), self.ml_file)
        self.assertEqual(unpacked.extract_metadata()["comment"], "Authentic Test Image")

    def test_invalid_t88_header(self) -> None:
        invalid_stream = io.BytesIO(b"INVALID_HEADER_BYTES_TOO_SHORT")
        with self.assertRaises(ValueError):
            T88File.unpack(invalid_stream)

    def test_split_and_join_t88(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            t88_in = os.path.join(tmpdir, "input.t88")
            split_dir = os.path.join(tmpdir, "split_t88")
            rejoined_out = os.path.join(tmpdir, "rejoined.t88")

            t88_orig = T88File.from_cmt_data(self.combined_cmt, baud=1200)
            with open(t88_in, "wb") as f:
                f.write(t88_orig.pack())

            split_info = split_t88_file(t88_in, split_dir, baud=None)
            self.assertEqual(len(split_info), 2)
            self.assertEqual(os.path.basename(split_info[0][3]), "01_BIN001.t88")
            self.assertEqual(os.path.basename(split_info[1][3]), "02_PROG01.t88")

            split_files = [item[3] for item in split_info]
            res_join = join_t88_files(split_files, rejoined_out, baud=None)
            with open(res_join, "rb") as f:
                rejoined = T88File.unpack(io.BytesIO(f.read()))

            self.assertEqual(
                rejoined.extract_cmt_payload(), t88_orig.extract_cmt_payload()
            )

    def test_join_t88_per_input_baud(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = os.path.join(tmpdir, "f1.cmt")
            f2 = os.path.join(tmpdir, "f2.cmt")
            out_t88 = os.path.join(tmpdir, "multi_baud.t88")
            with open(f1, "wb") as f:
                f.write(self.ml_file)
            with open(f2, "wb") as f:
                f.write(self.basic_file)

            # Test per-input baud specification via (path, baud) tuples
            join_t88_files([(f1, 600), (f2, 1200)], out_t88)
            with open(out_t88, "rb") as f:
                joined = T88File.unpack(io.BytesIO(f.read()))
            dblocks = [b for b in joined.blocks if b.tag == 0x0101]
            self.assertGreaterEqual(len(dblocks), 2)
            dsh1 = DataSubHeader.unpack(dblocks[0].data[:12])
            dsh2 = DataSubHeader.unpack(dblocks[-1].data[:12])
            self.assertEqual(dsh1.fmt_code, 0x00CC)  # 600 baud
            self.assertEqual(dsh2.fmt_code, 0x01CC)  # 1200 baud


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
