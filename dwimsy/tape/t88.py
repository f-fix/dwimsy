"""dwimsy.tape.t88 — T88 tape image container primitives, reader, and writer.

Provides canonical constants, data structures, and streaming reader/writer
implementations for NEC PC-8001/PC-8801 .t88 format files.
"""

import struct
from typing import BinaryIO, Generator, List, Optional, Tuple

__all__ = [
    "T88Tag",
    "DataSubHeader",
    "T88_HEADER_MAGICS",
    "StreamingT88Reader",
    "T88StreamWriter",
]


class T88Tag:
    """Standard T88 block tag identifiers."""

    END: int = 0x0000  # Terminal block marker
    VERSION: int = 0x0001  # Format version header
    COMMENT: int = 0x0010  # Text comment/annotation
    GAP: int = 0x0100  # Blank / unmodulated gap
    DATA: int = 0x0101  # FSK data payload (with DataSubHeader)
    DATA_1200: int = 0x0101  # Alias for standard 1200-baud data
    DATA_300: int = 0x0101  # Alias for standard data
    SPACE: int = 0x0102  # Space tone burst (1200 Hz nominal)
    MARK: int = 0x0103  # Mark carrier tone burst (2400 Hz nominal)


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
            # 24-byte magic signature + 6 bytes version & parameter fields (<HHH)
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
