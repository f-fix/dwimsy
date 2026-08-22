#!/usr/bin/env python3

import io
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dwimsy.core.audio import StreamingWavReader, StreamingWavWriter


def make_pcm_wav(
    samples,
    channels=1,
    bits=16,
    sample_rate=44100,
    fmt_tag=1,
    data_size_override=None,
    extra_chunk=None,
):
    """Hand-build a WAV file's bytes for reader-side tests, independent
    of StreamingWavWriter, so reader tests don't depend on the writer
    being correct."""
    bytes_per_sample = bits // 8
    block_align = channels * bytes_per_sample
    byte_rate = sample_rate * block_align

    if bits == 16:
        pcm = struct.pack(f"<{len(samples)}h", *samples)
    elif bits == 8:
        pcm = bytes((s + 128) & 0xFF for s in samples)
    elif bits == 24:
        pcm = b"".join(
            int(s).to_bytes(3, byteorder="little", signed=True) for s in samples
        )
    elif bits == 32 and fmt_tag == 3:
        pcm = struct.pack(f"<{len(samples)}f", *samples)
    else:
        raise ValueError("unsupported test format")

    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 0))  # placeholder, unused by reader
    buf.write(b"WAVE")

    if extra_chunk is not None:
        cid, cdata = extra_chunk
        buf.write(cid)
        buf.write(struct.pack("<I", len(cdata)))
        buf.write(cdata)
        if len(cdata) % 2:
            buf.write(b"\x00")

    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(
        struct.pack(
            "<HHIIHH", fmt_tag, channels, sample_rate, byte_rate, block_align, bits
        )
    )
    buf.write(b"data")
    buf.write(
        struct.pack(
            "<I", data_size_override if data_size_override is not None else len(pcm)
        )
    )
    buf.write(pcm)
    buf.seek(0)
    return buf


class TestStreamingWavReader(unittest.TestCase):

    def test_rejects_non_riff(self):
        with self.assertRaises(ValueError):
            StreamingWavReader(io.BytesIO(b"not a wav file at all............"))

    def test_mono_16bit_roundtrip_values(self):
        samples = [0, 16384, -16384, 32767, -32768]
        wav = make_pcm_wav(samples)
        r = StreamingWavReader(wav)
        self.assertEqual(r.channels, 1)
        self.assertEqual(r.bits_per_sample, 16)
        out = r.read_samples(len(samples))
        for expected, got in zip(samples, out):
            self.assertAlmostEqual(expected / 32768.0, got, places=6)

    def test_8bit_pcm(self):
        # 8-bit PCM is unsigned with 128 as the zero point.
        samples = [-128, 0, 127]
        wav = make_pcm_wav(samples, bits=8)
        r = StreamingWavReader(wav)
        out = r.read_samples(3)
        expected = [(-128) / 128.0, 0 / 128.0, 127 / 128.0]
        for e, g in zip(expected, out):
            self.assertAlmostEqual(e, g, places=6)

    def test_24bit_pcm(self):
        samples = [0, 8388607, -8388608]
        wav = make_pcm_wav(samples, bits=24)
        r = StreamingWavReader(wav)
        out = r.read_samples(3)
        expected = [0.0, 8388607 / 8388608.0, -1.0]
        for e, g in zip(expected, out):
            self.assertAlmostEqual(e, g, places=6)

    def test_32bit_float_pcm(self):
        samples = [0.0, 0.5, -0.75]
        wav = make_pcm_wav(samples, bits=32, fmt_tag=3)
        r = StreamingWavReader(wav)
        out = r.read_samples(3)
        for e, g in zip(samples, out):
            self.assertAlmostEqual(e, g, places=6)

    def test_placeholder_data_size_still_reads_to_eof(self):
        samples = [1000, 2000, 3000, 4000]
        wav = make_pcm_wav(samples, data_size_override=0xFFFFFFFF)
        r = StreamingWavReader(wav)
        out = r.read_samples(1024)  # ask for more than exists
        self.assertEqual(len(out), len(samples))

    def test_odd_size_fmt_chunk_padding(self):
        # 18-byte fmt chunk
        samples = [1000, 2000]
        pcm = struct.pack("<2h", *samples)
        buf = io.BytesIO()
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + len(pcm) + 2))
        buf.write(b"WAVE")
        buf.write(b"fmt ")
        buf.write(struct.pack("<I", 18))
        buf.write(struct.pack("<HHIIHHH", 1, 1, 44100, 88200, 2, 16, 0))
        buf.write(b"data")
        buf.write(struct.pack("<I", len(pcm)))
        buf.write(pcm)
        buf.seek(0)
        r = StreamingWavReader(buf)
        out = r.read_samples(2)
        self.assertEqual(len(out), 2)

    def test_skips_unknown_chunks_before_fmt(self):
        samples = [111, 222]
        wav = make_pcm_wav(samples, extra_chunk=(b"LIST", b"INFOICMTsomecomment"))
        r = StreamingWavReader(wav)
        out = r.read_samples(2)
        self.assertEqual(len(out), 2)

    def test_stereo_left_right_mix_diff(self):
        # Interleaved L,R,L,R...
        interleaved = [10000, -5000, 20000, -1000]
        wav = make_pcm_wav(interleaved, channels=2)
        r = StreamingWavReader(io.BytesIO(wav.getvalue()), channel_mode="left")
        left = r.read_samples(2)
        self.assertAlmostEqual(left[0], 10000 / 32768.0, places=6)
        self.assertAlmostEqual(left[1], 20000 / 32768.0, places=6)

        r = StreamingWavReader(io.BytesIO(wav.getvalue()), channel_mode="right")
        right = r.read_samples(2)
        self.assertAlmostEqual(right[0], -5000 / 32768.0, places=6)
        self.assertAlmostEqual(right[1], -1000 / 32768.0, places=6)

        r = StreamingWavReader(io.BytesIO(wav.getvalue()), channel_mode="mix")
        mix = r.read_samples(2)
        self.assertAlmostEqual(mix[0], (10000 - 5000) / 2 / 32768.0, places=6)

        r = StreamingWavReader(io.BytesIO(wav.getvalue()), channel_mode="diff")
        diff = r.read_samples(2)
        self.assertAlmostEqual(diff[0], (10000 - (-5000)) / 2 / 32768.0, places=6)

    def test_stereo_auto_picks_higher_energy_channel(self):
        # Right channel is much louder than left across many frames;
        # "auto" should settle on the right channel.
        interleaved = []
        for _ in range(50):
            interleaved.extend([100, 20000])
        wav = make_pcm_wav(interleaved, channels=2)
        r = StreamingWavReader(wav, channel_mode="auto")
        out = r.read_samples(50)
        self.assertAlmostEqual(out[-1], 20000 / 32768.0, places=6)


class TestStreamingWavWriter(unittest.TestCase):

    def test_seekable_finalize_patches_real_sizes(self):
        buf = io.BytesIO()
        w = StreamingWavWriter(buf, sample_rate=44100, channels=1)
        samples = [0.0, 0.5, -0.5, 1.0, -1.0]
        w.write_pcm_samples(samples)
        ok = w.finalize()
        self.assertTrue(ok)

        buf.seek(0)
        data = buf.read()
        riff_size = struct.unpack("<I", data[4:8])[0]
        data_size = struct.unpack("<I", data[40:44])[0]
        expected_data_bytes = len(samples) * 2  # 16-bit mono
        self.assertEqual(data_size, expected_data_bytes)
        self.assertEqual(riff_size, expected_data_bytes + 36)

    def test_unseekable_stream_leaves_placeholder(self):
        class UnseekableStream(io.RawIOBase):
            def __init__(self):
                self.buf = bytearray()

            def writable(self):
                return True

            def write(self, b):
                self.buf.extend(b)
                return len(b)

            def seekable(self):
                return False

        stream = UnseekableStream()
        w = StreamingWavWriter(stream, channels=1)
        w.write_pcm_samples([0.1, 0.2, 0.3])
        ok = w.finalize()
        self.assertFalse(ok)
        # Placeholder sizes must still be present, unmodified.
        self.assertEqual(struct.unpack("<I", bytes(stream.buf[4:8]))[0], 0xFFFFFFFF)
        self.assertEqual(struct.unpack("<I", bytes(stream.buf[40:44]))[0], 0xFFFFFFFF)

    def test_stereo_modes(self):
        buf = io.BytesIO()
        w = StreamingWavWriter(buf, channels=2, stereo_mode="inv_right")
        w.write_pcm_samples([0.5])
        w.finalize()
        buf.seek(44)  # past the 44-byte header
        l, r = struct.unpack("<hh", buf.read(4))
        # round(0.5 * 32767) = round(16383.5) = 16384 (Python's
        # round-half-to-even picks the even neighbor).
        self.assertEqual(l, 16384)
        self.assertEqual(r, -16384)

    def test_clamping_out_of_range_samples_inv_right(self):
        buf = io.BytesIO()
        w = StreamingWavWriter(buf, channels=2, stereo_mode="inv_right")
        w.write_pcm_samples([2.0, -2.0])
        w.finalize()
        buf.seek(44)
        l1, r1, l2, r2 = struct.unpack("<hhhh", buf.read(8))
        self.assertEqual(l1, 32767)
        self.assertEqual(r1, -32767)
        self.assertEqual(l2, -32768)
        self.assertEqual(r2, 32767)

    def test_clamping_out_of_range_samples(self):
        buf = io.BytesIO()
        w = StreamingWavWriter(buf, channels=1)
        w.write_pcm_samples([2.0, -2.0])  # out of [-1, 1] range
        w.finalize()
        buf.seek(44)
        v1, v2 = struct.unpack("<hh", buf.read(4))
        self.assertEqual(v1, 32767)
        self.assertEqual(v2, -32768)


class TestWriterReaderRoundtrip(unittest.TestCase):

    def test_full_roundtrip_mono(self):
        samples = [(-1.0 + i * (2.0 / 200)) for i in range(200)]
        buf = io.BytesIO()
        w = StreamingWavWriter(buf, sample_rate=44100, channels=1)
        w.write_pcm_samples(samples)
        w.finalize()
        buf.seek(0)

        r = StreamingWavReader(buf)
        self.assertEqual(r.sample_rate, 44100)
        self.assertEqual(r.channels, 1)
        out = r.read_samples(len(samples) + 10)
        self.assertEqual(len(out), len(samples))
        for expected, got in zip(samples, out):
            # Tolerance accounts for both normal 16-bit quantization
            # rounding (~0.5 LSB) and the write/read scale convention
            # (samples are quantized against 32767 but dequantized
            # against 32768, to keep the representable range
            # symmetric around zero without letting +1.0 overflow into
            # 32768) — a small, expected, intentional asymmetry, not a
            # bug.
            self.assertAlmostEqual(expected, got, delta=1e-4)

    def test_full_roundtrip_via_unseekable_pipe_like_stream(self):
        # Simulates the writer -> reader over an actual OS pipe, where
        # the writer can't seek back to patch in real sizes, and the
        # reader must still work correctly against the placeholder
        # 0xFFFFFFFF sizes it's left with.
        import os

        read_fd, write_fd = os.pipe()
        try:
            with os.fdopen(write_fd, "wb") as wf:
                w = StreamingWavWriter(wf, channels=1)
                w.write_pcm_samples([0.1, 0.2, 0.3, 0.4])
                ok = w.finalize()
                self.assertFalse(ok)
            with os.fdopen(read_fd, "rb") as rf:
                r = StreamingWavReader(rf)
                out = r.read_samples(1024)
                self.assertEqual(len(out), 4)
        finally:
            pass  # fds already closed by the `with` blocks above


if __name__ == "__main__":
    unittest.main()
