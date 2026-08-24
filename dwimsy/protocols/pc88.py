"""dwimsy.protocols.pc88 - NEC PC-8001/PC-8801 ROM protocols and CMT stream handling."""

from __future__ import annotations

import argparse
import io
import os
import re
import struct
import sys
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Tuple, TYPE_CHECKING

# Bootstrap sys.path if executed directly as a script
for p in Path(__file__).resolve().parents:
    if (p / "dwimsy").is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
        break

if TYPE_CHECKING:
    from dwimsy.tape.t88 import T88File

__all__ = [
    "ProtocolProfile",
    "ProtocolRegistry",
    "CMTFile",
    "convert_t88_to_cmt",
    "convert_cmt_to_t88",
    "split_cmt_file",
    "join_cmt_files",
    "analyze_tape",
]


class ProtocolProfile:
    """Encapsulates timing and structural parameters for a PC-8001/PC-8801 tape protocol."""

    def __init__(
        self,
        name: str,
        type_code: int,
        lead_space_ticks: int,
        lead_mark_ticks: int,
        inter_mark_ticks: int = 960,
        post_mark_ticks: int = 6240,
        post_space_ticks: int = 12000,
        post_gap_ticks: int = 16320,
        default_baud: int = 1200,
    ):
        self.name = name
        self.type_code = type_code
        self.lead_space_ticks = lead_space_ticks
        self.lead_mark_ticks = lead_mark_ticks
        self.inter_mark_ticks = inter_mark_ticks
        self.post_mark_ticks = post_mark_ticks
        self.post_space_ticks = post_space_ticks
        self.post_gap_ticks = post_gap_ticks
        self.default_baud = default_baud


class ProtocolRegistry:
    """Centralized registry for PC-8001/PC-8801 tape protocol definitions and timing constants."""

    BASIC = ProtocolProfile(
        name="BASIC Program (0xD3)",
        type_code=0xD3,
        lead_space_ticks=12000,
        lead_mark_ticks=2400,
        inter_mark_ticks=960,
        post_mark_ticks=6240,
        post_space_ticks=12000,
        post_gap_ticks=16320,
        default_baud=1200,
    )
    MON_HEADER = ProtocolProfile(
        name="MON Machine Language Header (0x24)",
        type_code=0x24,
        lead_space_ticks=4800,
        lead_mark_ticks=12000,
        inter_mark_ticks=960,
        post_mark_ticks=6240,
        post_space_ticks=12000,
        post_gap_ticks=16320,
        default_baud=1200,
    )
    MON_RECORDS = ProtocolProfile(
        name="MON Machine Language Records (0x3A)",
        type_code=0x3A,
        lead_space_ticks=4800,
        lead_mark_ticks=12000,
        inter_mark_ticks=960,
        post_mark_ticks=6240,
        post_space_ticks=12000,
        post_gap_ticks=16320,
        default_baud=1200,
    )
    ASCII = ProtocolProfile(
        name="ASCII / Sequential File (0x9C)",
        type_code=0x9C,
        lead_space_ticks=12000,
        lead_mark_ticks=2400,
        inter_mark_ticks=960,
        post_mark_ticks=6240,
        post_space_ticks=12000,
        post_gap_ticks=16320,
        default_baud=1200,
    )
    NONTAMA = ProtocolProfile(
        name="NONTAMA Machine Language Loader",
        type_code=0xFF,
        lead_space_ticks=4800,
        lead_mark_ticks=12000,
        inter_mark_ticks=960,
        post_mark_ticks=6240,
        post_space_ticks=12000,
        post_gap_ticks=16320,
        default_baud=1200,
    )
    RAW = ProtocolProfile(
        name="Raw Data / Unknown",
        type_code=0x00,
        lead_space_ticks=12000,
        lead_mark_ticks=2400,
        inter_mark_ticks=960,
        post_mark_ticks=6240,
        post_space_ticks=12000,
        post_gap_ticks=16320,
        default_baud=1200,
    )

    PROFILES = {
        0xD3: BASIC,
        0x24: MON_HEADER,
        0x3A: MON_RECORDS,
        0x9C: ASCII,
        0xFF: NONTAMA,
        0x00: RAW,
    }

    @classmethod
    def get_profile(cls, type_code: int) -> ProtocolProfile:
        return cls.PROFILES.get(type_code, cls.RAW)

    @staticmethod
    def get_fmt_code(baud: int) -> int:
        return 0x01CC if baud >= 1200 else 0x00CC

    @staticmethod
    def get_ticks_per_byte(baud: int) -> int:
        return int(round(44 * 1200 / baud)) if baud > 0 else 44


class CMTFile:
    """Represents a raw sequential CMT tape dump stream."""

    HEADER_PREAMBLE_BYTES: Tuple[int, ...] = (0x24, 0xD3, 0x9C)
    PREAMBLE_BYTES: Tuple[int, ...] = (0x24, 0xD3, 0x9C)

    TYPE_NAMES: Dict[int, str] = {
        0xD3: "BASIC Program (0xD3)",
        0x9C: "ASCII / Sequential File (0x9C)",
        0x24: "MON Machine Language Header (0x24)",
        0x3A: "MON Machine Language Records (0x3A)",
        0xFF: "NONTAMA Machine Language Loader",
    }

    CANONICAL_SYNC_LEN: int = 8

    def __init__(self, data: bytes = b"") -> None:
        self.data: bytes = data

    @staticmethod
    def _dedup_name(name: str, used: Dict[str, int]) -> str:
        if name in used:
            used[name] += 1
            return f"{name}_{used[name]}"
        used[name] = 1
        return name

    @classmethod
    def is_valid_cassette_filename(
        cls, name_bytes: bytes, allow_null: bool = False
    ) -> bool:
        if len(name_bytes) != 6:
            return False
        ok_byte = (
            lambda b: (32 <= b <= 126)
            or (0xA1 <= b <= 0xDF)
            or (allow_null and b == 0x00)
        )
        valid_chars = sum(1 for b in name_bytes if ok_byte(b))
        if valid_chars == 6:
            non_spaces = [b for b in name_bytes if b not in (0x20, 0x00)]
            if len(non_spaces) > 0:
                return True
        return False

    @classmethod
    def extract_file_info(cls, chunk: bytes) -> Tuple[str, str]:
        if len(chunk) < 7:
            return "", "Raw Data / Unknown"

        idx_non = chunk.find(b"NONTAMA")
        if idx_non != -1:
            is_nontama = False
            if idx_non == 0 and len(chunk) >= 13:
                is_nontama = True
            elif idx_non > 0 and chunk[idx_non - 1] == 0xFF:
                if all(b == 0 for b in chunk[: idx_non - 1]):
                    is_nontama = True
            if is_nontama:
                return "NONTAMA", cls.TYPE_NAMES.get(
                    0xFF, "NONTAMA Machine Language Loader"
                )

        for p_byte in (0x24, 0xD3, 0x9C):
            for min_len in (10, 8, 6, 4, 3):
                lead = bytes([p_byte]) * min_len
                if chunk.startswith(lead):
                    idx = min_len
                    while idx < len(chunk) and chunk[idx] == p_byte:
                        idx += 1
                    if idx + 6 <= len(chunk):
                        name_bytes = chunk[idx : idx + 6]
                        allow_null = idx >= cls.CANONICAL_SYNC_LEN
                        if cls.is_valid_cassette_filename(
                            name_bytes, allow_null=allow_null
                        ):
                            name_str = "".join(
                                chr(b) if (32 <= b <= 126 or 0xA1 <= b <= 0xDF) else " "
                                for b in name_bytes
                            ).strip()
                            name_str = re.sub(r'[\\/*?:"<>|]', "_", name_str)
                            if name_str:
                                file_type = cls.TYPE_NAMES.get(
                                    p_byte, f"Unknown (0x{p_byte:02X})"
                                )
                                return name_str, file_type

        if chunk.startswith(b":") and len(chunk) >= 4:
            return "", cls.TYPE_NAMES.get(0x3A, "MON Machine Language Records (0x3A)")

        return "", "Raw Data / Unknown"

    @classmethod
    def extract_filename(cls, chunk: bytes) -> str:
        fname, _ = cls.extract_file_info(chunk)
        return fname

    def split(self) -> List[Tuple[str, str, bytes]]:
        """Splits multi-file CMT or T88 stream using the authentic ROM state machine."""
        if not self.data:
            return []

        buf = _extract_payload_or_raw(self.data)
        n = len(buf)
        pos = 0
        used_names: Dict[str, int] = {}
        entries: List[Tuple[str, str, bytes]] = []

        while pos < n:
            file_start = pos

            # 1. Custom Bootstrap Loader (0xFF NONTAMA)
            is_nontama = False
            nt_p = pos
            while nt_p < min(pos + 300, n - 7):
                if buf[nt_p : nt_p + 8] == b"\xffNONTAMA" or (
                    nt_p == 0 and buf[0:7] == b"NONTAMA"
                ):
                    is_nontama = True
                    break
                elif buf[nt_p] not in (0x00, 0xFF):
                    break
                nt_p += 1

            if is_nontama:
                p = nt_p + (8 if buf[nt_p : nt_p + 8] == b"\xffNONTAMA" else 7)
                if p + 6 <= n:
                    _, dlen, _ = struct.unpack("<HHH", buf[p : p + 6])
                    p += 6
                    file_end = min(p + dlen + 1, n)
                    while file_end < n and buf[file_end] in (0x00, 0xFF):
                        if file_end + 1 < n and (
                            buf[file_end + 1] in (0x24, 0xD3, 0x9C, 0x3A)
                            or buf[file_end + 1 : file_end + 9] == b"\xffNONTAMA"
                        ):
                            break
                        file_end += 1
                else:
                    file_end = n
                chunk = buf[file_start:file_end]
                entries.append(
                    (
                        self._dedup_name("NONTAMA", used_names),
                        "NONTAMA Machine Language Loader",
                        chunk,
                    )
                )
                pos = file_end
                continue

            # 2. Headerless MON Record Stream (MON O / MON I)
            is_mon_o = False
            mp = pos
            while mp < min(pos + 48, n - 4):
                if buf[mp] == 0x3A:
                    ah, al, chk = buf[mp + 1], buf[mp + 2], buf[mp + 3]
                    if (ah + al + chk) & 0xFF == 0 and ah != 0:
                        is_mon_o = True
                        break
                    else:
                        break
                elif buf[mp] not in (0x00, 0xFF):
                    break
                mp += 1

            if is_mon_o:
                p = mp + 4
                term_end = n
                while p < n:
                    while p < n and buf[p] != 0x3A:
                        p += 1
                    if p >= n:
                        break
                    while p + 1 < n and buf[p] == 0x3A and buf[p + 1] == 0x3A:
                        p += 1
                    if p + 2 <= n:
                        dlen = buf[p + 1]
                        if dlen == 0:
                            term_end = p + 3 if p + 3 <= n else p + 2
                            while term_end < n and buf[term_end] in (0x00, 0xFF):
                                if term_end + 1 < n and (
                                    buf[term_end + 1] in (0x24, 0xD3, 0x9C, 0x3A)
                                    or buf[term_end + 1 : term_end + 9]
                                    == b"\xffNONTAMA"
                                ):
                                    break
                                term_end += 1
                            break
                        elif p + 2 + dlen + 1 <= n:
                            p = p + 2 + dlen + 1
                            continue
                    p += 1
                file_end = term_end
                chunk = buf[file_start:file_end]
                entries.append(
                    (
                        self._dedup_name("part", used_names),
                        "MON Machine Language Records (0x3A)",
                        chunk,
                    )
                )
                pos = file_end
                continue

            # 3. Named Protocol Header: 0x24, 0xD3, 0x9C
            hdr_pos = -1
            hdr_name = ""
            hdr_type = ""
            hdr_body = -1

            i = pos
            while i < n - 7:
                if buf[i : i + 8] == b"\xffNONTAMA":
                    hdr_pos = i
                    hdr_name = "NONTAMA"
                    hdr_type = "NONTAMA Machine Language Loader"
                    hdr_body = i + 14
                    break

                b = buf[i]
                if b in (0x24, 0xD3, 0x9C):
                    for plen in (10, 8, 6, 4, 3):
                        if buf[i : i + plen] == bytes([b]) * plen:
                            idx = i + plen
                            while idx < n and buf[idx] == b:
                                idx += 1
                            if idx + 6 <= n:
                                name_bytes = buf[idx : idx + 6]
                                allow_null = (idx - i) >= self.CANONICAL_SYNC_LEN
                                ok_byte = (
                                    lambda c: (32 <= c <= 126)
                                    or (0xA1 <= c <= 0xDF)
                                    or (allow_null and c == 0)
                                )
                                if sum(
                                    1 for c in name_bytes if ok_byte(c)
                                ) == 6 and any(
                                    c not in (0x20, 0x00) for c in name_bytes
                                ):
                                    name_str = "".join(
                                        (
                                            chr(c)
                                            if (32 <= c <= 126 or 0xA1 <= c <= 0xDF)
                                            else " "
                                        )
                                        for c in name_bytes
                                    ).strip()
                                    name_str = re.sub(r'[\\/*?:"<>|]', "_", name_str)
                                    if name_str:
                                        hdr_pos = i
                                        hdr_name = name_str
                                        type_map = {
                                            0xD3: "BASIC Program (0xD3)",
                                            0x24: "MON Machine Language Header (0x24)",
                                            0x9C: "ASCII / Sequential File (0x9C)",
                                        }
                                        hdr_type = type_map.get(
                                            b, f"Unknown (0x{b:02X})"
                                        )
                                        hdr_body = idx + 6
                                        break
                    if hdr_pos != -1:
                        break
                i += 1

            if hdr_pos == -1:
                if pos < n:
                    if entries:
                        p_name, p_type, p_data = entries[-1]
                        entries[-1] = (p_name, p_type, p_data + buf[pos:n])
                    else:
                        entries.append(
                            (
                                self._dedup_name("part", used_names),
                                "Raw Data / Unknown",
                                buf[pos:n],
                            )
                        )
                break

            if hdr_pos > pos:
                if entries:
                    p_name, p_type, p_data = entries[-1]
                    entries[-1] = (p_name, p_type, p_data + buf[pos:hdr_pos])
                file_start = hdr_pos

            if hdr_type == "MON Machine Language Header (0x24)":
                p = hdr_body
                while p < n and buf[p] != 0x3A:
                    p += 1
                if p + 4 <= n and buf[p] == 0x3A:
                    p += 4
                term_end = n
                while p < n:
                    while p < n and buf[p] != 0x3A:
                        p += 1
                    if p >= n:
                        break
                    while p + 1 < n and buf[p] == 0x3A and buf[p + 1] == 0x3A:
                        p += 1
                    if p + 2 <= n:
                        dlen = buf[p + 1]
                        if dlen == 0:
                            term_end = p + 3 if p + 3 <= n else p + 2
                            while term_end < n and buf[term_end] in (0x00, 0xFF):
                                if term_end + 1 < n and (
                                    buf[term_end + 1] in (0x24, 0xD3, 0x9C, 0x3A)
                                    or buf[term_end + 1 : term_end + 9]
                                    == b"\xffNONTAMA"
                                ):
                                    break
                                term_end += 1
                            break
                        elif p + 2 + dlen + 1 <= n:
                            p = p + 2 + dlen + 1
                            continue
                    p += 1
                file_end = term_end
                chunk = buf[file_start:file_end]
                entries.append(
                    (self._dedup_name(hdr_name, used_names), hdr_type, chunk)
                )
                pos = file_end
                continue

            elif hdr_type == "NONTAMA Machine Language Loader":
                pos_ff = buf.find(b"\xffNONTAMA", file_start)
                if pos_ff != -1 and pos_ff + 14 <= n:
                    _, dlen, _ = struct.unpack("<HHH", buf[pos_ff + 8 : pos_ff + 14])
                    n_end = min(pos_ff + 14 + dlen + 1, n)
                    while n_end < n and buf[n_end] in (0x00, 0xFF):
                        if n_end + 1 < n and (
                            buf[n_end + 1] in (0x24, 0xD3, 0x9C, 0x3A)
                            or buf[n_end + 1 : n_end + 9] == b"\xffNONTAMA"
                        ):
                            break
                        n_end += 1
                    file_end = n_end
                else:
                    file_end = n
                chunk = buf[file_start:file_end]
                entries.append(
                    (self._dedup_name(hdr_name, used_names), hdr_type, chunk)
                )
                pos = file_end
                continue

            elif hdr_type == "ASCII / Sequential File (0x9C)":
                sp = hdr_body
                eof_p = buf.find(b"\x1a", sp)
                if eof_p != -1:
                    file_end = eof_p + 1
                    while file_end < n and buf[file_end] in (0x00, 0xFF):
                        if file_end + 1 < n and (
                            buf[file_end + 1] in (0x24, 0xD3, 0x9C, 0x3A)
                            or buf[file_end + 1 : file_end + 9] == b"\xffNONTAMA"
                        ):
                            break
                        file_end += 1
                else:
                    file_end = n
                chunk = buf[file_start:file_end]
                entries.append(
                    (self._dedup_name(hdr_name, used_names), hdr_type, chunk)
                )
                pos = file_end
                continue

            else:
                # BASIC (0xD3)
                sp = hdr_body
                next_start = n
                while sp < n - 7:
                    if buf[sp] == 0x3A and sp + 4 <= n:
                        ah, al, chk = buf[sp + 1], buf[sp + 2], buf[sp + 3]
                        if (ah + al + chk) & 0xFF == 0 and ah != 0:
                            if sp > hdr_body and buf[sp - 1] in (0x00, 0xFF):
                                next_start = sp
                                break
                    if buf[sp : sp + 8] == b"\xffNONTAMA":
                        next_start = (
                            sp - 256
                            if (sp >= 256 and buf[sp - 256 : sp] == b"\x00" * 256)
                            else sp
                        )
                        break
                    b = buf[sp]
                    if b in (0x24, 0xD3, 0x9C):
                        for plen in (10, 8, 6, 4, 3):
                            if buf[sp : sp + plen] == bytes([b]) * plen:
                                idx = sp + plen
                                while idx < n and buf[idx] == b:
                                    idx += 1
                                if idx + 6 <= n:
                                    name_bytes = buf[idx : idx + 6]
                                    allow_null = (idx - sp) >= 8
                                    ok_byte = (
                                        lambda c: (32 <= c <= 126)
                                        or (0xA1 <= c <= 0xDF)
                                        or (allow_null and c == 0)
                                    )
                                    if sum(
                                        1 for c in name_bytes if ok_byte(c)
                                    ) == 6 and any(
                                        c not in (0x20, 0x00) for c in name_bytes
                                    ):
                                        next_start = sp
                                        break
                        if next_start != n:
                            break
                    sp += 1

                file_end = next_start
                chunk = buf[file_start:file_end]
                entries.append(
                    (self._dedup_name(hdr_name, used_names), hdr_type, chunk)
                )
                pos = file_end

        return entries

    @classmethod
    def join(cls, chunks: List[bytes]) -> "CMTFile":
        return cls(b"".join(chunks))


def _extract_payload_or_raw(data: bytes) -> bytes:
    from dwimsy.tape.t88 import T88File

    if len(data) >= 24 and T88File.is_valid_magic(data[:24]):
        try:
            t88 = T88File.unpack(io.BytesIO(data))
            return t88.extract_cmt_payload()
        except Exception:
            return data
    return data


def convert_t88_to_cmt(input_path: str, output_path: Optional[str] = None) -> str:
    from dwimsy.tape.t88 import T88File

    if output_path is None:
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}.cmt"

    with open(input_path, "rb") as f:
        stream = io.BytesIO(f.read())
        t88 = T88File.unpack(stream)

    cmt_payload = t88.extract_cmt_payload()

    with open(output_path, "wb") as f:
        f.write(cmt_payload)

    return output_path


def convert_cmt_to_t88(
    input_path: str,
    output_path: Optional[str] = None,
    comment: str = "",
    baud: int = 1200,
) -> str:
    from dwimsy.tape.t88 import T88File

    if output_path is None:
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}.t88"

    with open(input_path, "rb") as f:
        cmt_data = f.read()

    t88 = T88File.from_cmt_data(cmt_data, comment=comment, baud=baud)

    with open(output_path, "wb") as f:
        f.write(t88.pack())

    return output_path


def split_cmt_file(
    input_path: str, output_dir: Optional[str] = None
) -> List[Tuple[str, str, int, str]]:
    with open(input_path, "rb") as f:
        tape_data = f.read()

    cmt = CMTFile(tape_data)
    chunks = cmt.split()

    if output_dir is None:
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_dir = f"{base_name}_split"

    os.makedirs(output_dir, exist_ok=True)
    summary_info: List[Tuple[str, str, int, str]] = []

    for idx, (name, ftype, chunk_data) in enumerate(chunks, start=1):
        clean_name = name[:-4] if name.lower().endswith(".cmt") else name
        out_name = f"{idx:02d}_{clean_name}.cmt"
        out_path = os.path.join(output_dir, out_name)
        with open(out_path, "wb") as f:
            f.write(chunk_data)
        summary_info.append((name, ftype, len(chunk_data), out_path))

    return summary_info


def join_cmt_files(input_paths: List[str], output_path: str) -> str:
    chunks: List[bytes] = []
    for path in input_paths:
        with open(path, "rb") as f:
            data = f.read()
        chunks.append(_extract_payload_or_raw(data))

    joined = CMTFile.join(chunks)

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "wb") as f:
        f.write(joined.data)

    return output_path


def analyze_tape(input_path: str | BinaryIO, verbose: bool = False) -> str:
    from dwimsy.tape.t88 import DataSubHeader, T88File, T88Tag

    if isinstance(input_path, (str, os.PathLike)):
        filename_display = os.path.basename(str(input_path))
        with open(input_path, "rb") as f:
            raw_data = f.read()
    elif hasattr(input_path, "read"):
        filename_display = getattr(input_path, "name", "<stream>")
        if isinstance(filename_display, str):
            filename_display = os.path.basename(filename_display)
        raw_data = input_path.read()
    else:
        raw_data = bytes(input_path)
        filename_display = "<data>"

    lines: List[str] = []
    lines.append("=" * 80)
    lines.append(f"TAPE ANALYSIS REPORT: {filename_display}")
    lines.append("=" * 80)
    lines.append(f"File Size: {len(raw_data):,} bytes")

    is_t88 = len(raw_data) >= 24 and T88File.is_valid_magic(raw_data[:24])

    if is_t88:
        t88 = T88File.unpack(io.BytesIO(raw_data))
        lines.append("Format:    .t88 Container (Manuke Station / X88000)")
        magic_trimmed = t88.magic.rstrip(b"\x00")
        lines.append(f"Magic:     {magic_trimmed!r}")
        lines.append(f"Version:   0x{t88.version:04X}")
        lines.append(f"Blocks:    {len(t88.blocks):,}")
        meta = t88.extract_metadata()
        if meta.get("comment"):
            lines.append(f"Comment:   {meta['comment']}")

        total_ticks = 0
        total_data_bytes = 0
        carrier_marks = 0
        carrier_spaces = 0
        gaps = 0

        for b in t88.blocks:
            if b.tag in (T88Tag.GAP, T88Tag.SPACE, T88Tag.MARK) and len(b.data) >= 8:
                st, lt = struct.unpack("<II", b.data[:8])
                total_ticks = max(total_ticks, st + lt)
                if b.tag == T88Tag.MARK:
                    carrier_marks += 1
                elif b.tag == T88Tag.SPACE:
                    carrier_spaces += 1
                elif b.tag == T88Tag.GAP:
                    gaps += 1
            elif b.tag == 0x0101 and len(b.data) >= 12:
                dsh = DataSubHeader.unpack(b.data[:12])
                total_ticks = max(total_ticks, dsh.start_tick + dsh.length_ticks)
                total_data_bytes += dsh.data_len

        dur_sec = total_ticks / 4800.0
        m = int(dur_sec // 60)
        s = dur_sec % 60
        lines.append(f"Duration:  {m:02d}:{s:06.3f} ({total_ticks:,} ticks @ 4800 Hz)")
        lines.append(f"Payload:   {total_data_bytes:,} data bytes")
        lines.append(
            f"Tones:     {carrier_marks} Mark (2400 Hz), {carrier_spaces} Space (1200 Hz), {gaps} Blank Gaps"
        )

        data_blocks = [b for b in t88.blocks if b.tag == 0x0101 and len(b.data) >= 12]
        if data_blocks:
            dsh = DataSubHeader.unpack(data_blocks[0].data[:12])
            st, lt, dlen, _ = (
                dsh.start_tick,
                dsh.length_ticks,
                dsh.data_len,
                dsh.fmt_code,
            )
            if dlen > 0:
                tpb = lt / dlen
                est_baud = int(round(44 * 1200 / tpb)) if tpb > 0 else 1200
                lines.append(f"Est. Baud: {est_baud} baud (~{tpb:.1f} ticks/byte)")

        if verbose:
            lines.append("\n--- T88 Block Breakdown ---")
            tag_names = {
                T88Tag.END: "END",
                T88Tag.VERSION: "VERSION",
                T88Tag.COMMENT: "COMMENT",
                T88Tag.GAP: "GAP",
                T88Tag.DATA_1200: "DATA",
                T88Tag.SPACE: "SPACE",
                T88Tag.MARK: "MARK",
            }
            for idx, b in enumerate(t88.blocks):
                tname = tag_names.get(b.tag, f"0x{b.tag:04X}")
                if b.tag == 0x0101 and len(b.data) >= 12:
                    dsh = DataSubHeader.unpack(b.data[:12])
                    st, lt, dlen, res = (
                        dsh.start_tick,
                        dsh.length_ticks,
                        dsh.data_len,
                        dsh.fmt_code,
                    )
                    eff_baud = 600 if res == 0x00CC else 1200
                    dur_s = lt / 4800.0
                    pld = b.data[12 : 12 + dlen]
                    fn, ft = CMTFile.extract_file_info(pld)
                    fn_str = (
                        f" [name='{fn}' type='{ft}']" if fn else f" {repr(pld[:16])}"
                    )
                    lines.append(
                        f"  #{idx:03d} | {tname:<7} | tick {st:8d}..{st+lt:<8d} ({lt:6d} ticks, {dur_s:6.3f}s) | dlen={dlen:5d} [{eff_baud} baud]{fn_str}"
                    )
                elif (
                    b.tag in (T88Tag.MARK, T88Tag.SPACE, T88Tag.GAP)
                    and len(b.data) >= 8
                ):
                    st, lt = struct.unpack("<II", b.data[:8])
                    dur_s = lt / 4800.0
                    lines.append(
                        f"  #{idx:03d} | {tname:<7} | tick {st:8d}..{st+lt:<8d} ({lt:6d} ticks, {dur_s:6.3f}s)"
                    )
                else:
                    lines.append(
                        f"  #{idx:03d} | {tname:<7} | len={len(b.data):5d} bytes"
                    )
    else:
        lines.append("Format:    Raw .cmt Sequential Tape Stream")

    cmt_payload = _extract_payload_or_raw(raw_data)
    cmt_file = CMTFile(cmt_payload)
    split_items = cmt_file.split()

    lines.append("\n--- Cassette Content / Programs on Tape ---")
    lines.append(f"Total Programs / Streams Detected: {len(split_items)}")
    lines.append(
        f"{'#':<3} | {'Filename':<12} | {'File Format / Type':<35} | {'Size (Bytes)':<12} | Details"
    )
    lines.append("-" * 90)

    for idx, (name, ftype, chunk) in enumerate(split_items, start=1):
        details = []
        if "BASIC" in ftype:
            p_idx = 0
            while p_idx < len(chunk) and chunk[p_idx] in (0xD3,):
                p_idx += 1
            p_idx += 6
            while p_idx < len(chunk) and chunk[p_idx] in (0xD3,):
                p_idx += 1
            b_start = p_idx
            line_nums = []
            code_sz = len(chunk)
            while p_idx + 4 <= len(chunk):
                next_ptr, lnum = struct.unpack("<HH", chunk[p_idx : p_idx + 4])
                if next_ptr == 0:
                    code_sz = (p_idx + 2) - b_start
                    break
                line_end = chunk.find(b"\x00", p_idx + 4)
                if line_end == -1:
                    break
                line_nums.append(lnum)
                p_idx = line_end + 1
            if line_nums:
                details.append(
                    f"{len(line_nums)} lines (L{line_nums[0]}..L{line_nums[-1]}), Code: {code_sz:,}B"
                )
            else:
                details.append(f"Code: {len(chunk):,}B")
        elif "MON" in ftype:
            p = 0
            if chunk.startswith(b"\x24"):
                while p < len(chunk) and chunk[p] in (0x24,):
                    p += 1
                if p > 0:
                    p += 6
            while p < len(chunk) and chunk[p] in (0x24, 0x00, 0xFF):
                p += 1

            cur_addr = None
            start_addr = None
            min_addr = None
            max_addr = None
            recs = 0
            tot = 0

            while p < len(chunk):
                while p + 1 < len(chunk) and chunk[p] == 0x3A and chunk[p + 1] == 0x3A:
                    p += 1
                if chunk[p] == 0x3A:
                    if p + 4 <= len(chunk):
                        ah, al, chk = chunk[p + 1], chunk[p + 2], chunk[p + 3]
                        if (ah + al + chk) & 0xFF == 0 and ah != 0:
                            cur_addr = (ah << 8) | al
                            if start_addr is None:
                                start_addr = cur_addr
                            if min_addr is None or cur_addr < min_addr:
                                min_addr = cur_addr
                            p += 4
                            continue
                    if p + 2 <= len(chunk):
                        dlen = chunk[p + 1]
                        if dlen == 0:
                            p += 3
                            break
                        if 0 < dlen and p + 2 + dlen + 1 <= len(chunk):
                            if cur_addr is not None:
                                if start_addr is None:
                                    start_addr = cur_addr
                                if min_addr is None or cur_addr < min_addr:
                                    min_addr = cur_addr
                                cur_end = (cur_addr + dlen - 1) & 0xFFFF
                                if max_addr is None or cur_end > max_addr:
                                    max_addr = cur_end
                                cur_addr = (cur_addr + dlen) & 0xFFFF
                            tot += dlen
                            recs += 1
                            p = p + 2 + dlen + 1
                            continue
                p += 1

            if min_addr is not None and max_addr is not None and max_addr >= min_addr:
                details.append(
                    f"{recs} records ({tot:,}B loaded), Range: ${min_addr:04X}..${max_addr:04X}"
                )
            elif tot > 0:
                details.append(f"{recs} records ({tot:,}B loaded)")
            else:
                details.append(f"MON Records ({len(chunk):,}B)")
        elif "NONTAMA" in ftype:
            pos_ff = chunk.find(b"\xffNONTAMA")
            if pos_ff != -1 and pos_ff + 14 <= len(chunk):
                l_addr, l_len, e_addr = struct.unpack(
                    "<HHH", chunk[pos_ff + 8 : pos_ff + 14]
                )
                details.append(
                    f"Load: ${l_addr:04X}..${(l_addr+l_len-1)&0xFFFF:04X} ({l_len:,}B), Exec: ${e_addr:04X}"
                )
            else:
                details.append(f"NONTAMA Stream ({len(chunk):,}B)")
        else:
            details.append(f"{len(chunk):,} bytes")

        detail_str = ", ".join(details)
        lines.append(
            f"{idx:<3} | {name:<12} | {ftype:<35} | {len(chunk):<12,} | {detail_str}"
        )

    lines.append("-" * 90)
    return "\n".join(lines)
