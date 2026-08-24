"""dwimsy.core.audio - Streaming RIFF/WAVE I/O.

Milestone 1 scope: WAV only. FLAC support is deferred to Milestone 2,
where it ships alongside MSX support (see the project README's roadmap).
"""

from __future__ import annotations

import array
import io
import os
import struct
import sys
from typing import BinaryIO, List

__all__ = ["StreamingWavReader", "StreamingWavWriter"]


class StreamingWavReader:
    """
    Incremental streaming RIFF/WAVE reader.

    Parses the ``fmt `` chunk to determine sample format, then serves
    audio in caller-chosen frame-sized chunks via :meth:`read_samples`,
    returned as a flat list of floats in ``[-1.0, 1.0]``.

    Supports 8/16/24-bit PCM and 32-bit IEEE float samples, mono or
    stereo. For stereo input, ``channel_mode`` selects which channel
    (or combination) to hand back as the mono stream consumers expect:

    - ``"auto"`` (default): picks the channel with higher cumulative
      energy once enough samples have streamed by to make it a
      confident choice; whichever channel actually carries the tape
      signal on 2-channel captures where one channel is far quieter
      than the other (e.g. a spare/blank channel, or a much weaker
      azimuth-misaligned channel) wins.
    - ``"left"`` / ``"l"`` / ``"0"``: always the left channel.
    - ``"right"`` / ``"r"`` / ``"1"``: always the right channel.
    - ``"mix"`` / ``"mono"``: average of both channels.
    - ``"diff"`` / ``"l-r"``: difference of both channels (useful for
      differential/noise-cancelling captures).

    A ``data`` chunk size of ``0xFFFFFFFF`` (the placeholder value a
    streaming writer emits when it can't seek back to patch in a real
    size) is accepted transparently: this reader never enforces the
    declared size as a read boundary, it simply reads frames until the
    underlying stream is exhausted.
    """

    def __init__(self, stream: BinaryIO, channel_mode: str = "auto"):
        self.stream = stream
        self.channel_mode = channel_mode.lower()
        self.channels = 1
        self.sample_rate = 44100
        self.bits_per_sample = 16
        self.format_tag = 1  # 1 = PCM, 3 = IEEE float
        self.bytes_per_sample = 2
        self.frame_size = 2
        self.data_size = -1
        self._parse_header()

        # Running per-channel energy accumulators for "auto" channel
        # selection; updated incrementally as frames are read, so the
        # choice can be (and is) revisited as more signal streams by.
        self.l_energy = 0.0
        self.r_energy = 0.0

    def _read_exact(self, count: int) -> bytes:
        buf = bytearray()
        while len(buf) < count:
            chunk = self.stream.read(count - len(buf))
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    def _parse_header(self):
        riff_hdr = self._read_exact(12)
        if len(riff_hdr) < 12 or riff_hdr[0:4] != b"RIFF" or riff_hdr[8:12] != b"WAVE":
            raise ValueError("Input is not a valid RIFF/WAVE stream")

        fmt_found = False
        while True:
            chunk_hdr = self._read_exact(8)
            if len(chunk_hdr) < 8:
                raise ValueError("Premature EOF while parsing WAV chunks")
            chunk_id, chunk_size = struct.unpack("<4sI", chunk_hdr)

            if chunk_id == b"fmt ":
                fmt_data = self._read_exact(chunk_size)
                if chunk_size % 2:
                    self._read_exact(1)
                if len(fmt_data) < 16:
                    raise ValueError("Invalid fmt chunk size")
                (
                    self.format_tag,
                    self.channels,
                    self.sample_rate,
                    byte_rate,
                    self.frame_size,
                    self.bits_per_sample,
                ) = struct.unpack("<HHIIHH", fmt_data[:16])
                self.bytes_per_sample = (self.bits_per_sample + 7) // 8
                fmt_found = True
            elif chunk_id == b"data":
                if not fmt_found:
                    raise ValueError("'data' chunk encountered before 'fmt ' chunk")
                self.data_size = chunk_size
                break
            else:
                # Skip any other (e.g. LIST/INFO) chunk. Per the RIFF
                # spec, chunks are padded to an even byte boundary; the
                # chunk_size field reflects only the un-padded payload,
                # so an odd-sized chunk has one extra pad byte after it
                # that must also be consumed, or the next chunk header
                # read would be misaligned by one byte. (The original
                # standalone tool this was ported from didn't account
                # for this — harmless in practice since real-world
                # LIST/INFO chunks are almost always already
                # even-sized, but worth fixing now that it's caught.)
                if chunk_size > 0 and chunk_size != 0xFFFFFFFF:
                    self._read_exact(chunk_size + (chunk_size % 2))

    def read_samples(self, num_frames: int = 1024) -> List[float]:
        raw_bytes = self._read_exact(num_frames * self.frame_size)
        if not raw_bytes:
            return []

        frames_read = len(raw_bytes) // self.frame_size

        if self.bits_per_sample == 16 and self.format_tag == 1:
            total_values = frames_read * self.channels
            unpacked = struct.unpack(f"<{total_values}h", raw_bytes[: total_values * 2])
            raw_float = [v / 32768.0 for v in unpacked]
        elif self.bits_per_sample == 8 and self.format_tag == 1:
            total_values = frames_read * self.channels
            raw_float = [(v - 128) / 128.0 for v in raw_bytes[:total_values]]
        elif self.bits_per_sample == 24 and self.format_tag == 1:
            raw_float = []
            idx = 0
            for _ in range(frames_read * self.channels):
                val = int.from_bytes(
                    raw_bytes[idx : idx + 3], byteorder="little", signed=True
                )
                idx += 3
                raw_float.append(val / 8388608.0)
        elif self.bits_per_sample == 32 and self.format_tag == 3:
            total_values = frames_read * self.channels
            raw_float = list(
                struct.unpack(f"<{total_values}f", raw_bytes[: total_values * 4])
            )
        else:
            raise ValueError(
                f"Unsupported WAV format: format_tag={self.format_tag}, "
                f"bits={self.bits_per_sample}"
            )

        if self.channels == 1:
            return raw_float

        c_mode = self.channel_mode
        if c_mode in ("auto", "left", "l", "0"):
            if c_mode == "auto":
                for i in range(frames_read):
                    self.l_energy += abs(raw_float[i * self.channels + 0])
                    self.r_energy += abs(raw_float[i * self.channels + 1])
                chosen = 1 if self.r_energy > (self.l_energy * 1.5) else 0
                return [
                    raw_float[i * self.channels + chosen] for i in range(frames_read)
                ]
            return [raw_float[i * self.channels + 0] for i in range(frames_read)]
        elif c_mode in ("right", "r", "1"):
            return [raw_float[i * self.channels + 1] for i in range(frames_read)]
        elif c_mode in ("mix", "mono"):
            return [
                (raw_float[i * self.channels + 0] + raw_float[i * self.channels + 1])
                * 0.5
                for i in range(frames_read)
            ]
        elif c_mode in ("diff", "l-r"):
            return [
                (raw_float[i * self.channels + 0] - raw_float[i * self.channels + 1])
                * 0.5
                for i in range(frames_read)
            ]
        return [raw_float[i * self.channels + 0] for i in range(frames_read)]


class StreamingWavWriter:
    """
    Incremental streaming RIFF/WAVE writer.

    - Writes standard 16-bit PCM WAV chunks to output stream.
    - Initially outputs streaming placeholder ``0xFFFFFFFF`` for chunk
      sizes, since the real sizes aren't known until all samples have
      been written.
    - On :meth:`finalize`, seeks back to write exact chunk sizes if the
      output stream is seekable (a real file), or leaves the streaming
      placeholder header intact if it isn't (a pipe/stdout) — readers
      that don't enforce declared chunk sizes (like
      :class:`StreamingWavReader` above) handle either case correctly.
    """

    def __init__(
        self,
        out_stream: BinaryIO,
        sample_rate: int = 44100,
        channels: int = 1,
        stereo_mode: str = "dual",
    ):
        self.out = out_stream
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.stereo_mode = stereo_mode.lower()
        self.bits_per_sample = 16
        self.bytes_per_sample = 2
        self.block_align = self.channels * self.bytes_per_sample
        self.byte_rate = self.sample_rate * self.block_align

        self.total_frames_written = 0
        self.total_pcm_bytes_written = 0
        self.header_written = False

        self._write_initial_header()

    def _write_initial_header(self):
        # 12 bytes RIFF header + 24 bytes fmt chunk + 8 bytes data header = 44 bytes
        # Streaming placeholder sizes = 0xFFFFFFFF
        placeholder_size = 0xFFFFFFFF
        hdr = bytearray()
        hdr.extend(b"RIFF")
        hdr.extend(struct.pack("<I", placeholder_size))
        hdr.extend(b"WAVE")
        hdr.extend(b"fmt ")
        hdr.extend(struct.pack("<I", 16))  # Subchunk1Size for PCM
        hdr.extend(
            struct.pack(
                "<HHIIHH",
                1,  # AudioFormat: 1 = PCM
                self.channels,  # NumChannels
                self.sample_rate,  # SampleRate
                self.byte_rate,  # ByteRate
                self.block_align,  # BlockAlign
                self.bits_per_sample,  # BitsPerSample
            )
        )
        hdr.extend(b"data")
        hdr.extend(struct.pack("<I", placeholder_size))

        self.out.write(bytes(hdr))
        self.out.flush()
        self.header_written = True

    def write_pcm_samples(self, mono_floats: List[float]):
        """
        Converts floating-point samples in ``[-1.0, 1.0]`` to 16-bit
        PCM and streams them out. For stereo output, ``stereo_mode``
        controls how the (mono) input is placed across two channels:
        ``dual``/``both``/``mono``/``center`` duplicates it to both
        channels; ``left``/``l``/``0`` and ``right``/``r``/``1`` place
        it in just one channel (silence in the other);
        ``inv_right``/``diff``/``invert_r`` puts the signal in the left
        channel and its inversion in the right (a differential output
        some hardware/decoders reject noise better from).
        """
        if not mono_floats:
            return

        num_frames = len(mono_floats)
        # Quantize to 16-bit signed integer [-32768, 32767].
        _round = round
        quantized = []
        qappend = quantized.append
        for s in mono_floats:
            v = int(_round(s * 32767.0))
            if v > 32767:
                v = 32767
            elif v < -32768:
                v = -32768
            qappend(v)

        # array.array uses native machine byte order, but WAV PCM data must be
        # little-endian; byteswap on big-endian hosts to preserve correctness.
        def _to_le_bytes(int_list):
            arr = array.array("h", int_list)
            if sys.byteorder == "big":
                arr.byteswap()
            return arr.tobytes()

        if self.channels == 1:
            raw_bytes = _to_le_bytes(quantized)
        elif self.channels == 2:
            stereo_pcm = []
            smode = self.stereo_mode
            if smode in ("dual", "both", "mono", "center"):
                for v in quantized:
                    stereo_pcm.extend([v, v])
            elif smode in ("left", "l", "0"):
                for v in quantized:
                    stereo_pcm.extend([v, 0])
            elif smode in ("right", "r", "1"):
                for v in quantized:
                    stereo_pcm.extend([0, v])
            elif smode in ("inv_right", "diff", "invert_r"):
                for v in quantized:
                    inv_v = -v if v != -32768 else 32767
                    stereo_pcm.extend([v, inv_v])
            else:
                for v in quantized:
                    stereo_pcm.extend([v, v])
            raw_bytes = _to_le_bytes(stereo_pcm)
        else:
            raw_bytes = _to_le_bytes(quantized)

        self.out.write(raw_bytes)
        self.total_frames_written += num_frames
        self.total_pcm_bytes_written += len(raw_bytes)

    def finalize(self) -> bool:
        """
        Attempts to update the WAV header with exact sizes if seekable.
        Returns True if the seek-and-patch succeeded, False if the
        output stream was unseekable (e.g. a pipe) and the placeholder
        header was left in place instead.
        """
        self.out.flush()
        is_seekable = False
        try:
            if hasattr(self.out, "seekable"):
                is_seekable = self.out.seekable()
            else:
                self.out.seek(0, os.SEEK_CUR)
                is_seekable = True
        except (io.UnsupportedOperation, OSError, AttributeError):
            is_seekable = False

        if not is_seekable:
            return False

        try:
            cur_pos = self.out.tell()
            # Update RIFF size at byte offset 4: (total_pcm_bytes + 36)
            riff_size = self.total_pcm_bytes_written + 36
            # Avoid 32-bit overflow if size exceeds 4 GB
            riff_size_field = min(0xFFFFFFFF, riff_size)
            data_size_field = min(0xFFFFFFFF, self.total_pcm_bytes_written)

            self.out.seek(4, os.SEEK_SET)
            self.out.write(struct.pack("<I", riff_size_field))

            # Update data size at byte offset 40
            self.out.seek(40, os.SEEK_SET)
            self.out.write(struct.pack("<I", data_size_field))

            # Seek back to original end position
            self.out.seek(cur_pos, os.SEEK_SET)
            self.out.flush()
            return True
        except (io.UnsupportedOperation, OSError, AttributeError):
            return False
