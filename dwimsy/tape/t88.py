"""dwimsy.tape.t88 - NEC PC-88 T88 cassette image container parser and writer."""

from __future__ import annotations

import io
import os
import struct
import sys
from pathlib import Path
from typing import BinaryIO, Dict, Generator, List, Optional, Tuple, Union

# Bootstrap sys.path if executed directly as a script
for p in Path(__file__).resolve().parents:
    if (p / "dwimsy").is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
        break

__all__ = [
    "T88Tag",
    "DataSubHeader",
    "T88_HEADER_MAGICS",
    "T88Block",
    "T88File",
    "StreamingT88Reader",
    "T88StreamWriter",
    "split_t88_file",
    "join_t88_files",
]


class T88Tag:
    """Block tag identifiers for the T88 container format."""

    END: int = 0x0000
    VERSION: int = 0x0001
    GAP: int = 0x0100  # Blank / gap tag (start_tick: uint32, length_ticks: uint32)
    COMMENT: int = 0x0010
    DATA: int = 0x0101
    DATA_300: int = 0x0101  # DATA tag with 12-byte timing/length sub-header
    DATA_1200: int = 0x0101  # DATA tag with 12-byte timing/length sub-header
    SPACE: int = 0x0102  # Space carrier tag
    MARK: int = 0x0103  # Mark carrier lead-in tag


class DataSubHeader:
    """12-byte T88 DATA block sub-header (<IIHH)."""

    STRUCT_FORMAT: str = "<IIHH"
    SIZE: int = 12

    def __init__(
        self,
        start_tick: int = 0,
        length_ticks: int = 0,
        data_len: int = 0,
        fmt_code: int = 0x01CC,
    ):
        self.start_tick = int(start_tick)
        self.length_ticks = int(length_ticks)
        self.data_len = int(data_len)
        self.fmt_code = int(fmt_code)

    def pack(self) -> bytes:
        return struct.pack(
            self.STRUCT_FORMAT,
            self.start_tick,
            self.length_ticks,
            self.data_len,
            self.fmt_code,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "DataSubHeader":
        st, lt, dlen, fmt = struct.unpack(cls.STRUCT_FORMAT, data[:12])
        return cls(st, lt, dlen, fmt)


T88_HEADER_MAGICS: Tuple[bytes, ...] = (
    b"PC-8801 Tape Image(T88)\x00",
    b"PC-8001 Tape Image(T88)\x00",
    b"PC-8801 ",
    b"T88-FILE",
    b"PC-8001 ",
)


class T88Block:
    """Represents a single tagged data block within a T88 container."""

    def __init__(self, tag: int, data: bytes = b"") -> None:
        self.tag: int = tag
        self.data: bytes = data

    @property
    def length(self) -> int:
        return len(self.data)

    def pack(self) -> bytes:
        if self.tag == T88Tag.END:
            return struct.pack("<HH", self.tag, 0)
        return struct.pack("<HH", self.tag, self.length) + self.data

    @classmethod
    def unpack(cls, stream: io.BytesIO) -> Optional["T88Block"]:
        tag_bytes = stream.read(2)
        if not tag_bytes or len(tag_bytes) < 2:
            return None

        (tag,) = struct.unpack("<H", tag_bytes)
        len_bytes = stream.read(2)
        if not len_bytes or len(len_bytes) < 2:
            return cls(tag=tag, data=b"")

        (length,) = struct.unpack("<H", len_bytes)
        data = stream.read(length) if length > 0 else b""
        return cls(tag=tag, data=data)


class T88File:
    """Represents a full T88 cassette image file container."""

    DEFAULT_MAGIC: bytes = b"PC-8801 Tape Image(T88)\x00"
    VALID_MAGICS: Tuple[bytes, ...] = (
        b"PC-8801 Tape Image(T88)\x00",
        b"PC-8001 Tape Image(T88)\x00",
        b"PC-8801 ",
        b"T88-FILE",
        b"PC-8001 ",
    )

    def __init__(
        self,
        magic: bytes = DEFAULT_MAGIC,
        version: int = 0x0100,
        blocks: Optional[List[T88Block]] = None,
    ) -> None:
        self.magic: bytes = magic
        self.version: int = version
        self.blocks: List[T88Block] = blocks if blocks is not None else []

    @classmethod
    def is_valid_magic(cls, magic: bytes) -> bool:
        if magic.startswith(b"PC-8801 Tape Image") or magic.startswith(
            b"PC-8001 Tape Image"
        ):
            return True
        if (
            magic.startswith(b"T88")
            or magic.startswith(b"PC-88")
            or magic.startswith(b"PC-80")
        ):
            return True
        return False

    def pack(self) -> bytes:
        header = self.magic.ljust(24, b"\x00")[:24]
        body = b"".join(block.pack() for block in self.blocks)
        return header + body

    @classmethod
    def unpack(cls, stream: io.BytesIO) -> "T88File":
        header = stream.read(24)
        if len(header) < 24:
            raise ValueError("Invalid T88 file: header is shorter than 24 bytes.")

        if not cls.is_valid_magic(header):
            if cls.is_valid_magic(header[:16]):
                stream.seek(16)
            else:
                raise ValueError(
                    f"Invalid T88 magic signature: got {header!r}. Expected a valid "
                    f"header such as b'PC-8801 Tape Image(T88)\\x00'."
                )

        blocks: List[T88Block] = []
        while True:
            block = T88Block.unpack(stream)
            if block is None:
                break
            blocks.append(block)
            if block.tag == T88Tag.END:
                break

        return cls(magic=header, blocks=blocks)

    def extract_cmt_payload(self) -> bytes:
        payload_chunks: List[bytes] = []

        for block in self.blocks:
            if block.tag == 0x0101 and block.data:
                if len(block.data) >= 12:
                    dsh = DataSubHeader.unpack(block.data[:12])
                    payload_chunks.append(block.data[12 : 12 + dsh.data_len])
                else:
                    payload_chunks.append(block.data)

        if not payload_chunks:
            for block in self.blocks:
                if (
                    block.tag
                    not in (
                        T88Tag.END,
                        T88Tag.VERSION,
                        T88Tag.COMMENT,
                        T88Tag.GAP,
                        T88Tag.SPACE,
                        T88Tag.MARK,
                    )
                    and block.data
                ):
                    payload_chunks.append(block.data)

        return b"".join(payload_chunks)

    def extract_metadata(self) -> Dict[str, str]:
        comments: List[str] = []
        for block in self.blocks:
            if block.tag == T88Tag.COMMENT:
                comments.append(block.data.decode("utf-8", errors="ignore").strip())
        return {"comment": "\n".join(comments)}

    @classmethod
    def from_cmt_data(
        cls,
        cmt_data: bytes,
        comment: str = "",
        chunk_size: int = 32000,
        baud: int = 1200,
    ) -> "T88File":
        from dwimsy.protocols.pc88 import CMTFile, ProtocolRegistry

        blocks: List[T88Block] = []
        blocks.append(T88Block(T88Tag.VERSION, struct.pack("<H", 0x0100)))

        if comment:
            comment_bytes = comment.encode("utf-8", errors="ignore")
            blocks.append(T88Block(T88Tag.COMMENT, comment_bytes))

        fmt_code = ProtocolRegistry.get_fmt_code(baud)
        ticks_per_byte = ProtocolRegistry.get_ticks_per_byte(baud)
        current_tick = 0

        if not cmt_data:
            blocks.append(T88Block(T88Tag.GAP, struct.pack("<II", current_tick, 480)))
            current_tick += 480
            blocks.append(T88Block(T88Tag.GAP, struct.pack("<II", current_tick, 480)))
            current_tick += 480
            blocks.append(
                T88Block(T88Tag.SPACE, struct.pack("<II", current_tick, 12000))
            )
            current_tick += 12000
            blocks.append(T88Block(T88Tag.MARK, struct.pack("<II", current_tick, 2400)))
            current_tick += 2400
            data_header = DataSubHeader(current_tick, 0, 0, fmt_code).pack()
            blocks.append(T88Block(0x0101, data_header))
        else:
            cmt_obj = CMTFile(cmt_data)
            split_items = cmt_obj.split()
            if not split_items:
                split_items = [("part", "Raw Data / Unknown", cmt_data)]

            for file_idx, (name, ftype, chunk) in enumerate(split_items):
                type_code = (
                    chunk[0]
                    if (chunk and chunk[0] in ProtocolRegistry.PROFILES)
                    else (0xFF if "NONTAMA" in ftype else 0x00)
                )
                profile = ProtocolRegistry.get_profile(type_code)
                space_len = profile.lead_space_ticks
                mark_len = profile.lead_mark_ticks

                if file_idx == 0:
                    blocks.append(
                        T88Block(T88Tag.GAP, struct.pack("<II", current_tick, 480))
                    )
                    current_tick += 480
                    blocks.append(
                        T88Block(T88Tag.GAP, struct.pack("<II", current_tick, 480))
                    )
                    current_tick += 480
                    blocks.append(
                        T88Block(
                            T88Tag.SPACE, struct.pack("<II", current_tick, space_len)
                        )
                    )
                    current_tick += space_len
                    blocks.append(
                        T88Block(
                            T88Tag.MARK, struct.pack("<II", current_tick, mark_len)
                        )
                    )
                    current_tick += mark_len
                else:
                    blocks.append(
                        T88Block(
                            T88Tag.SPACE, struct.pack("<II", current_tick, space_len)
                        )
                    )
                    current_tick += space_len
                    blocks.append(
                        T88Block(
                            T88Tag.MARK, struct.pack("<II", current_tick, mark_len)
                        )
                    )
                    current_tick += mark_len

                hdr_len = 0
                if len(chunk) >= 9 and chunk[0] in (0x24, 0xD3, 0x9C):
                    p_byte = chunk[0]
                    idx = 0
                    while idx < len(chunk) and chunk[idx] == p_byte:
                        idx += 1
                    if idx >= 3 and idx + 6 <= len(chunk):
                        hdr_len = idx + 6

                if hdr_len > 0 and len(chunk) > hdr_len:
                    hdr_data = chunk[:hdr_len]
                    body_data = chunk[hdr_len:]

                    h_ticks = len(hdr_data) * ticks_per_byte
                    h_hdr = DataSubHeader(
                        current_tick, h_ticks, len(hdr_data), fmt_code
                    ).pack()
                    blocks.append(T88Block(0x0101, h_hdr + hdr_data))
                    current_tick += h_ticks

                    blocks.append(
                        T88Block(
                            T88Tag.MARK,
                            struct.pack("<II", current_tick, profile.inter_mark_ticks),
                        )
                    )
                    current_tick += profile.inter_mark_ticks

                    for offset in range(0, len(body_data), chunk_size):
                        subchunk = body_data[offset : offset + chunk_size]
                        data_len = len(subchunk)
                        data_ticks = data_len * ticks_per_byte
                        data_header = DataSubHeader(
                            current_tick, data_ticks, data_len, fmt_code
                        ).pack()
                        blocks.append(T88Block(0x0101, data_header + subchunk))
                        current_tick += data_ticks
                else:
                    for offset in range(0, len(chunk), chunk_size):
                        subchunk = chunk[offset : offset + chunk_size]
                        data_len = len(subchunk)
                        data_ticks = data_len * ticks_per_byte
                        data_header = DataSubHeader(
                            current_tick, data_ticks, data_len, fmt_code
                        ).pack()
                        blocks.append(T88Block(0x0101, data_header + subchunk))
                        current_tick += data_ticks

                blocks.append(
                    T88Block(
                        T88Tag.MARK,
                        struct.pack("<II", current_tick, profile.post_mark_ticks),
                    )
                )
                current_tick += profile.post_mark_ticks
                blocks.append(
                    T88Block(
                        T88Tag.SPACE,
                        struct.pack("<II", current_tick, profile.post_space_ticks),
                    )
                )
                current_tick += profile.post_space_ticks
                blocks.append(
                    T88Block(
                        T88Tag.GAP,
                        struct.pack("<II", current_tick, profile.post_gap_ticks),
                    )
                )
                current_tick += profile.post_gap_ticks

        blocks.append(T88Block(T88Tag.END, b""))
        return cls(magic=cls.DEFAULT_MAGIC, version=0x0100, blocks=blocks)


class StreamingT88Reader:
    """Streaming reader for T88 container blocks."""

    def __init__(self, stream: BinaryIO):
        self.stream = stream
        self.header_bytes = b""
        self._parse_header()

    def _read_exact(self, count: int) -> bytes:
        buf = bytearray()
        while len(buf) < count:
            chunk = self.stream.read(count - len(buf))
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    def _parse_header(self):
        hdr = self._read_exact(24)
        if len(hdr) < 24:
            raise ValueError(
                "Input stream is too short to be a valid T88 container (<24 bytes)."
            )
        valid = any(hdr.startswith(m) or hdr[: len(m)] == m for m in T88_HEADER_MAGICS)
        if not valid and not (hdr.startswith(b"PC-") or hdr.startswith(b"T88")):
            raise ValueError(f"Invalid T88 magic signature: got {hdr!r}.")
        self.header_bytes = hdr

    def iter_blocks(self) -> Generator[Tuple[int, int, bytes], None, None]:
        while True:
            tag_hdr = self._read_exact(4)
            if len(tag_hdr) < 4:
                break
            tag_id, length = struct.unpack("<HH", tag_hdr)
            payload = self._read_exact(length) if length > 0 else b""
            if len(payload) < length:
                break
            yield (tag_id, length, payload)
            if tag_id == T88Tag.END:
                break


class T88StreamWriter:
    """Streaming writer for emitting T88 container files."""

    def __init__(self, out_stream: BinaryIO):
        self.out = out_stream
        self.header_written = False

    def write_header(self):
        if not self.header_written:
            hdr = b"PC-8801 Tape Image(T88)\x00" + struct.pack(
                "<HHH", 0x0001, 0x0002, 0x0100
            )
            self.out.write(hdr)
            self.header_written = True
            self.out.flush()

    def _write_tag(self, tag_id: int, payload: bytes):
        self.write_header()
        self.out.write(struct.pack("<HH", tag_id, len(payload)) + payload)
        self.out.flush()

    def write_blank(self, start_tick: int, length_tick: int):
        if length_tick > 0:
            self._write_tag(
                T88Tag.GAP, struct.pack("<II", int(start_tick), int(length_tick))
            )

    def write_space(self, start_tick: int, length_tick: int):
        if length_tick > 0:
            self._write_tag(
                T88Tag.SPACE, struct.pack("<II", int(start_tick), int(length_tick))
            )

    def write_mark(self, start_tick: int, length_tick: int):
        if length_tick > 0:
            self._write_tag(
                T88Tag.MARK, struct.pack("<II", int(start_tick), int(length_tick))
            )

    def write_data(self, start_tick: int, baud: int, data_bytes: bytes):
        if not data_bytes:
            return
        fmt = 0x01CC if baud >= 1200 else 0x00CC
        ticks_per_byte = int(round(11.0 * 4800.0 / baud))
        offset = 0
        cur_tick = start_tick
        while offset < len(data_bytes):
            chunk = data_bytes[offset : offset + 32768]
            length_tick = len(chunk) * ticks_per_byte
            hdr = DataSubHeader(cur_tick, length_tick, len(chunk), fmt).pack()
            self._write_tag(T88Tag.DATA, hdr + chunk)
            offset += len(chunk)
            cur_tick += length_tick

    def write_end(self):
        self._write_tag(T88Tag.END, b"")


def split_t88_file(
    input_path: str,
    output_dir: Optional[str] = None,
    comment: str = "",
    baud: Optional[int] = None,
    default_baud: int = 1200,
    cmt_baud: Optional[int] = None,
) -> List[Tuple[str, str, int, str]]:
    from dwimsy.protocols.pc88 import CMTFile, ProtocolRegistry, _extract_payload_or_raw

    with open(input_path, "rb") as f:
        raw_data = f.read()

    if output_dir is None:
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_dir = f"{base_name}_split"

    os.makedirs(output_dir, exist_ok=True)
    summary_info: List[Tuple[str, str, int, str]] = []

    if cmt_baud is not None:
        default_baud = cmt_baud

    if len(raw_data) >= 24 and T88File.is_valid_magic(raw_data[:24]):
        try:
            t88 = T88File.unpack(io.BytesIO(raw_data))
            blocks = [
                b for b in t88.blocks if b.tag not in (T88Tag.VERSION, T88Tag.END)
            ]

            # Detect file boundaries by identifying header DATA blocks
            header_entries: List[Tuple[int, str, str]] = []
            for idx, b in enumerate(blocks):
                if b.tag == 0x0101:
                    payload = b""
                    if len(b.data) >= 12:
                        dsh = DataSubHeader.unpack(b.data[:12])
                        payload = b.data[12 : 12 + dsh.data_len]
                    else:
                        payload = b.data

                    fn, ft = CMTFile.extract_file_info(payload)
                    if fn:
                        header_entries.append((idx, fn, ft))
                    elif b"NONTAMA" in payload[:300]:
                        idx_n = payload.find(b"NONTAMA")
                        if idx_n == 0 or (idx_n > 0 and payload[idx_n - 1] == 0xFF):
                            header_entries.append(
                                (
                                    idx,
                                    "NONTAMA",
                                    CMTFile.TYPE_NAMES.get(
                                        0xFF, "NONTAMA Machine Language Loader"
                                    ),
                                )
                            )
                    elif not header_entries:
                        header_entries.append((idx, "part", "Binary Data"))

            if header_entries:
                # Partition carrier blocks between File N trailer and File N+1 lead-in
                split_cuts = [0]
                for k in range(len(header_entries) - 1):
                    prev_hdr_idx = header_entries[k][0]
                    next_hdr_idx = header_entries[k + 1][0]

                    carrier_start = prev_hdr_idx + 1
                    while (
                        carrier_start < next_hdr_idx
                        and blocks[carrier_start].tag == 0x0101
                    ):
                        carrier_start += 1

                    carrier_blocks = blocks[carrier_start:next_hdr_idx]
                    gap_offset = -1
                    for ci, cb in enumerate(carrier_blocks):
                        if cb.tag == T88Tag.GAP:
                            gap_offset = ci

                    if gap_offset != -1:
                        cut_idx = carrier_start + gap_offset + 1
                    else:
                        if (
                            len(carrier_blocks) >= 2
                            and carrier_blocks[-2].tag == T88Tag.SPACE
                            and carrier_blocks[-1].tag == T88Tag.MARK
                        ):
                            cut_idx = next_hdr_idx - 2
                        elif (
                            len(carrier_blocks) >= 1
                            and carrier_blocks[-1].tag == T88Tag.MARK
                        ):
                            cut_idx = next_hdr_idx - 1
                        else:
                            cut_idx = carrier_start + len(carrier_blocks) // 2

                    split_cuts.append(cut_idx)

                split_cuts.append(len(blocks))

                used_names: Dict[str, int] = {}
                for k in range(len(header_entries)):
                    fname_raw = header_entries[k][1]
                    ftype = header_entries[k][2]
                    sec_blocks = blocks[split_cuts[k] : split_cuts[k + 1]]

                    uname = CMTFile._dedup_name(fname_raw or "part", used_names)

                    new_blocks: List[T88Block] = []
                    new_blocks.append(
                        T88Block(T88Tag.VERSION, struct.pack("<H", 0x0100))
                    )
                    if comment:
                        new_blocks.append(
                            T88Block(
                                T88Tag.COMMENT,
                                comment.encode("utf-8", errors="ignore"),
                            )
                        )

                    timing_blocks = [
                        b
                        for b in sec_blocks
                        if b.tag in (T88Tag.GAP, T88Tag.SPACE, T88Tag.MARK, 0x0101)
                    ]
                    min_tick = 0
                    for tb in timing_blocks:
                        if len(tb.data) >= 8:
                            st = struct.unpack("<II", tb.data[:8])[0]
                            min_tick = st
                            break

                    curr_tick = 0
                    for b in sec_blocks:
                        if b.tag in (T88Tag.GAP, T88Tag.SPACE, T88Tag.MARK):
                            if len(b.data) >= 8:
                                st, lt = struct.unpack("<II", b.data[:8])
                                if baud is None:
                                    new_st = max(0, st - min_tick)
                                else:
                                    new_st = curr_tick
                                    curr_tick += lt
                                new_b_data = struct.pack("<II", new_st, lt) + b.data[8:]
                                new_blocks.append(T88Block(b.tag, new_b_data))
                            else:
                                new_blocks.append(T88Block(b.tag, b.data))
                        elif b.tag == 0x0101:
                            if len(b.data) >= 12:
                                dsh = DataSubHeader.unpack(b.data[:12])
                                st, lt, dlen, res = (
                                    dsh.start_tick,
                                    dsh.length_ticks,
                                    dsh.data_len,
                                    dsh.fmt_code,
                                )
                                payload = b.data[12 : 12 + dlen]
                                if baud is None:
                                    new_st = max(0, st - min_tick)
                                    new_lt = lt
                                else:
                                    ticks_per_byte = (
                                        ProtocolRegistry.get_ticks_per_byte(baud)
                                    )
                                    new_lt = dlen * ticks_per_byte
                                    new_st = curr_tick
                                    curr_tick += new_lt
                                    res = ProtocolRegistry.get_fmt_code(baud)
                                new_b_data = (
                                    DataSubHeader(new_st, new_lt, dlen, res).pack()
                                    + payload
                                )
                                new_blocks.append(T88Block(b.tag, new_b_data))
                            else:
                                new_blocks.append(T88Block(b.tag, b.data))
                        elif b.tag == T88Tag.COMMENT:
                            if not comment:
                                new_blocks.append(T88Block(b.tag, b.data))
                        else:
                            new_blocks.append(T88Block(b.tag, b.data))

                    new_blocks.append(T88Block(T88Tag.END, b""))
                    split_t88 = T88File(
                        magic=t88.magic, version=t88.version, blocks=new_blocks
                    )
                    t88_bytes = split_t88.pack()

                    clean_name = uname[:-4] if uname.lower().endswith(".t88") else uname
                    out_name = f"{k+1:02d}_{clean_name}.t88"
                    out_path = os.path.join(output_dir, out_name)
                    with open(out_path, "wb") as out_f:
                        out_f.write(t88_bytes)
                    summary_info.append((uname, ftype, len(t88_bytes), out_path))

                return summary_info
        except Exception:
            pass

    raw_cmt = _extract_payload_or_raw(raw_data)
    cmt = CMTFile(raw_cmt)
    chunks = cmt.split()
    effective_baud = baud if baud is not None else default_baud

    for idx, (name, ftype, chunk_data) in enumerate(chunks, start=1):
        t88_obj = T88File.from_cmt_data(
            chunk_data, comment=comment, baud=effective_baud
        )
        t88_bytes = t88_obj.pack()
        clean_name = name[:-4] if name.lower().endswith(".t88") else name
        out_name = f"{idx:02d}_{clean_name}.t88"
        out_path = os.path.join(output_dir, out_name)
        with open(out_path, "wb") as out_f:
            out_f.write(t88_bytes)
        summary_info.append((name, ftype, len(t88_bytes), out_path))

    return summary_info


def join_t88_files(
    input_paths: List[Union[str, Tuple[str, Optional[int]]]],
    output_path: str,
    comment: str = "",
    baud: Optional[int] = None,
    default_baud: int = 1200,
    cmt_baud: Optional[int] = None,
    bauds: Optional[Union[List[Optional[int]], str]] = None,
    chunk_size: int = 32000,
) -> str:
    """Joins multiple .t88 and .cmt files into a single .t88 container.

    Supports per-input baud rates (positional tuple or --bauds list),
    global overrides (baud), and default cmt_baud fallback.
    """
    from dwimsy.protocols.pc88 import ProtocolRegistry

    combined_blocks: List[T88Block] = []
    combined_blocks.append(T88Block(T88Tag.VERSION, struct.pack("<H", 0x0100)))

    if comment:
        combined_blocks.append(
            T88Block(T88Tag.COMMENT, comment.encode("utf-8", errors="ignore"))
        )

    if cmt_baud is not None:
        default_baud = cmt_baud

    parsed_bauds: List[Optional[int]] = []
    if isinstance(bauds, str):
        parsed_bauds = [int(b.strip()) if b.strip() else None for b in bauds.split(",")]
    elif isinstance(bauds, list):
        parsed_bauds = list(bauds)

    current_tick = 0

    for path_idx, item in enumerate(input_paths):
        if isinstance(item, tuple):
            path, item_baud = item
        else:
            path = item
            item_baud = parsed_bauds[path_idx] if path_idx < len(parsed_bauds) else None

        with open(path, "rb") as f:
            data = f.read()

        is_t88 = len(data) >= 24 and T88File.is_valid_magic(data[:24])

        if is_t88:
            try:
                t88 = T88File.unpack(io.BytesIO(data))
                file_blocks = [
                    b for b in t88.blocks if b.tag not in (T88Tag.VERSION, T88Tag.END)
                ]

                min_tick = 0
                for b in file_blocks:
                    if b.tag in (T88Tag.GAP, T88Tag.SPACE, T88Tag.MARK, 0x0101):
                        if len(b.data) >= 8:
                            st = struct.unpack("<II", b.data[:8])[0]
                            min_tick = st
                            break

                file_start_tick = current_tick
                file_max_end = current_tick

                effective_t88_baud = baud if baud is not None else item_baud

                for b in file_blocks:
                    if b.tag in (T88Tag.GAP, T88Tag.SPACE, T88Tag.MARK):
                        if len(b.data) >= 8:
                            st, lt = struct.unpack("<II", b.data[:8])
                            if effective_t88_baud is None:
                                new_st = file_start_tick + max(0, st - min_tick)
                                file_max_end = max(file_max_end, new_st + lt)
                            else:
                                new_st = current_tick
                                current_tick += lt
                                file_max_end = current_tick
                            new_b_data = struct.pack("<II", new_st, lt) + b.data[8:]
                            combined_blocks.append(T88Block(b.tag, new_b_data))
                        else:
                            combined_blocks.append(T88Block(b.tag, b.data))

                    elif b.tag == 0x0101:
                        if len(b.data) >= 12:
                            dsh = DataSubHeader.unpack(b.data[:12])
                            st, lt, dlen, res = (
                                dsh.start_tick,
                                dsh.length_ticks,
                                dsh.data_len,
                                dsh.fmt_code,
                            )
                            payload = b.data[12 : 12 + dlen]
                            if effective_t88_baud is None:
                                new_st = file_start_tick + max(0, st - min_tick)
                                new_lt = lt
                                file_max_end = max(file_max_end, new_st + new_lt)
                                new_fmt = res
                            else:
                                ticks_per_byte = ProtocolRegistry.get_ticks_per_byte(
                                    effective_t88_baud
                                )
                                new_lt = dlen * ticks_per_byte
                                new_st = current_tick
                                current_tick += new_lt
                                file_max_end = current_tick
                                new_fmt = ProtocolRegistry.get_fmt_code(
                                    effective_t88_baud
                                )
                            new_b_data = (
                                DataSubHeader(new_st, new_lt, dlen, new_fmt).pack()
                                + payload
                            )
                            combined_blocks.append(T88Block(b.tag, new_b_data))
                        else:
                            combined_blocks.append(T88Block(b.tag, b.data))

                    elif b.tag == T88Tag.COMMENT:
                        if not comment:
                            combined_blocks.append(T88Block(b.tag, b.data))
                    else:
                        combined_blocks.append(T88Block(b.tag, b.data))

                current_tick = file_max_end
                continue
            except Exception:
                pass

        if path_idx > 0:
            combined_blocks.append(
                T88Block(T88Tag.GAP, struct.pack("<II", current_tick, 9600))
            )
            current_tick += 9600

        effective_cmt_baud = (
            baud
            if baud is not None
            else (item_baud if item_baud is not None else default_baud)
        )
        ticks_per_byte = ProtocolRegistry.get_ticks_per_byte(effective_cmt_baud)
        fmt_code = ProtocolRegistry.get_fmt_code(effective_cmt_baud)
        mark_len = 9600
        combined_blocks.append(
            T88Block(T88Tag.MARK, struct.pack("<II", current_tick, mark_len))
        )
        current_tick += mark_len

        if not data:
            data_header = DataSubHeader(current_tick, 0, 0, fmt_code).pack()
            combined_blocks.append(T88Block(0x0101, data_header))
        else:
            for offset in range(0, len(data), chunk_size):
                chunk = data[offset : offset + chunk_size]
                data_len = len(chunk)
                data_ticks = data_len * ticks_per_byte
                data_header = DataSubHeader(
                    current_tick, data_ticks, data_len, fmt_code
                ).pack()
                combined_blocks.append(T88Block(0x0101, data_header + chunk))
                current_tick += data_ticks

    combined_blocks.append(T88Block(T88Tag.END, b""))

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    joined_t88 = T88File(blocks=combined_blocks)
    with open(output_path, "wb") as f:
        f.write(joined_t88.pack())

    return output_path
