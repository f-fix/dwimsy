#!/usr/bin/env python3

import io
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dwimsy.protocols.pc88 import (
    CMTFile,
    ProtocolRegistry,
    convert_t88_to_cmt,
    convert_cmt_to_t88,
    split_cmt_file,
    join_cmt_files,
    analyze_tape,
)
from dwimsy.tape.t88 import T88File, T88Tag, T88Block, DataSubHeader


class TestProtocolsPC88(unittest.TestCase):
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

    @staticmethod
    def _make_mon_o_stream(addr: int, data: bytes) -> bytes:
        ah = (addr >> 8) & 0xFF
        al = addr & 0xFF
        achk = (0 - (ah + al)) & 0xFF
        addr_rec = struct.pack("BBBB", 0x3A, ah, al, achk)
        dlen = len(data)
        dchk = (0 - (dlen + sum(data))) & 0xFF
        data_rec = struct.pack("BB", 0x3A, dlen) + data + struct.pack("B", dchk)
        term_rec = b"\x3a\x00\x00"
        return addr_rec + data_rec + term_rec

    def setUp(self) -> None:
        self.ml_file = self._make_ml_file(
            b"BIN001", 0x8000, b"\x21\x00\x80\x3e\x01\xcd\x00\x00"
        )
        self.ml_file_2 = self._make_ml_file(b"BIN002", 0x9000, b"\x3e\x01\xcd\x00\x50")
        self.ml_file_3 = self._make_ml_file(b"BIN003", 0xA000, b"\x3e\x02\xcd\x00\x50")
        self.three_ml_cmt = self.ml_file + self.ml_file_2 + self.ml_file_3

        self.basic_file = (
            (b"\xd3" * 10 + b"PROG01")
            + (b"\xd3" * 10)
            + struct.pack("<HH", 0x8010, 10)
            + b'\x90 "HELLO WORLD"'
            + b"\x00"
            + struct.pack("<H", 0x0000)
        )

        self.ascii_file = (
            b"\x9c" * 10 + b"TEXT01"
        ) + b'10 PRINT "TEST"\r\n20 END\r\n\x1a'

        self.combined_cmt = self.ml_file + self.basic_file + self.ascii_file

        self.mon_o_1 = self._make_mon_o_stream(0x8000, b"\x01\x02\x03\x04")
        self.mon_o_2 = self._make_mon_o_stream(0x9000, b"\x11\x12\x13\x14\x15\x16")
        self.basic_and_two_mon_o_tape = self.basic_file + self.mon_o_1 + self.mon_o_2

    def test_split_and_join_cmt(self) -> None:
        cmt_file = CMTFile(self.combined_cmt)
        split_items = cmt_file.split()
        self.assertEqual(len(split_items), 3)
        self.assertEqual(split_items[0][0], "BIN001")
        self.assertEqual(split_items[0][1], "MON Machine Language Header (0x24)")
        self.assertEqual(split_items[0][2], self.ml_file)
        self.assertEqual(split_items[1][0], "PROG01")
        self.assertEqual(split_items[1][1], "BASIC Program (0xD3)")
        self.assertEqual(split_items[1][2], self.basic_file)
        self.assertEqual(split_items[2][0], "TEXT01")
        self.assertEqual(split_items[2][1], "ASCII / Sequential File (0x9C)")
        self.assertEqual(split_items[2][2], self.ascii_file)
        joined = CMTFile.join([item[2] for item in split_items])
        self.assertEqual(joined.data, self.combined_cmt)

    def test_three_consecutive_mon_r_files(self) -> None:
        cmt_file = CMTFile(self.three_ml_cmt)
        split_items = cmt_file.split()
        self.assertEqual(len(split_items), 3)
        self.assertEqual(split_items[0][0], "BIN001")
        self.assertEqual(split_items[0][2], self.ml_file)
        self.assertEqual(split_items[1][0], "BIN002")
        self.assertEqual(split_items[1][2], self.ml_file_2)
        self.assertEqual(split_items[2][0], "BIN003")
        self.assertEqual(split_items[2][2], self.ml_file_3)

    def test_basic_and_headerless_mon_o_files_split(self) -> None:
        cmt_file = CMTFile(self.basic_and_two_mon_o_tape)
        split_items = cmt_file.split()
        self.assertEqual(len(split_items), 3)
        self.assertEqual(split_items[0][0], "PROG01")
        self.assertEqual(split_items[0][1], "BASIC Program (0xD3)")
        self.assertEqual(split_items[0][2], self.basic_file)
        self.assertEqual(split_items[1][0], "part")
        self.assertEqual(split_items[1][1], "MON Machine Language Records (0x3A)")
        self.assertEqual(split_items[1][2], self.mon_o_1)
        self.assertEqual(split_items[2][0], "part_2")
        self.assertEqual(split_items[2][1], "MON Machine Language Records (0x3A)")
        self.assertEqual(split_items[2][2], self.mon_o_2)

    def test_nontama_loader(self) -> None:
        basic_loader = (
            (b"\xd3" * 10 + b"LOADER")
            + struct.pack("<HH", 0x8010, 10)
            + b'10 PRINT "LOAD"'
            + b"\x00"
            + struct.pack("<H", 0x0000)
        )
        nontama_data = (
            b"\xffNONTAMA"
            + struct.pack("<HHH", 0x0100, 100, 0x0100)
            + b"A" * 100
            + b"\x55"
        )
        tape = basic_loader + nontama_data
        cmt = CMTFile(tape)
        splits = cmt.split()
        self.assertEqual(len(splits), 2)
        self.assertEqual(splits[0][0], "LOADER")
        self.assertEqual(splits[0][1], "BASIC Program (0xD3)")
        self.assertEqual(splits[1][0], "NONTAMA")
        self.assertEqual(splits[1][1], "NONTAMA Machine Language Loader")
        self.assertEqual(splits[1][2], nontama_data)

    def test_analyze_tape_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p_cmt = os.path.join(tmpdir, "test.cmt")
            with open(p_cmt, "wb") as f:
                f.write(self.combined_cmt)
            rep = analyze_tape(p_cmt, verbose=False)
            self.assertIn("TAPE ANALYSIS REPORT", rep)
            self.assertIn("BIN001", rep)
            self.assertIn("PROG01", rep)
            self.assertIn("TEXT01", rep)


if __name__ == "__main__":
    unittest.main()
