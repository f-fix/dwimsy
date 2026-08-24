#!/usr/bin/env python3
"""tests.test_fixture_correspondence - Verify audio captures against reference containers.

Tests verifying correspondence and equivalence between audio snippets (.wav)
and reference container/stream images (.t88 / .cmt)."""

import io
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dwimsy.tape.t88 import T88File, DataSubHeader
from dwimsy.protocols.pc88 import CMTFile
from dwimsy.cli.filters import wav2t88 as native_wav2t88
from dwimsy.core.pulse import PulseTimingRecognizer
from dwimsy.core.fsk import FSKClassifier, ByteFramer
from dwimsy.core.audio import StreamingWavReader
from dwimsy.tests.fixtures import get_fixture_pool


class TestSnippetToInputCorrespondence(unittest.TestCase):
    """Verifies that real audio captures (snippet.wav, snippet2.wav) decode to payloads
    and baud rates matching their respective source images (input01 and input05)."""

    def _demod_with_core(self, wav_path: Path, baud: int) -> bytes:
        """Demodulate a WAV file using dwimsy.core primitives."""
        with open(wav_path, "rb") as f:
            reader = StreamingWavReader(f, channel_mode="auto")
            recognizer = PulseTimingRecognizer(reader.sample_rate)
            classifier = FSKClassifier(mark_freq=2400.0, space_freq=1200.0)
            framer = ByteFramer(baud=baud, sample_rate=reader.sample_rate)

            decoded = []
            in_block = False
            while True:
                samples = reader.read_samples(1024)
                if not samples:
                    break
                for s in samples:
                    ev = recognizer.process_sample(s)
                    if ev is not None:
                        pulse = classifier.classify(ev)
                        framer.update_speed(classifier.speed_factor)
                        b = framer.feed(pulse)
                        if b is not None and b.status in ("OK", "LOW_CONFIDENCE"):
                            if not in_block:
                                in_block = True
                                framer.in_block = True
                            decoded.append(b.value)

                    # Inter-block gap handling
                    if in_block:
                        if framer.carrier_mark_time >= (framer.bit_duration * 24.0):
                            in_block = False
                            framer.reset(in_block=False, in_session=True)
                            framer.leader_validated = True

            return bytes(decoded)

    def test_snippet1_corresponds_to_input01_door_door_1200_baud(self):
        """snippet.wav is a 1200-baud capture of Door Door (MON ML 0x24), matching input01.t88 / input01.cmt."""
        pool = get_fixture_pool()
        wav_path = pool.get("snippet.wav")
        if not wav_path:
            self.skipTest(pool.skip_reason("snippet.wav"))

        # 1. Demodulate snippet.wav with native filter
        with open(wav_path, "rb") as f:
            out_t88 = io.BytesIO()
            native_wav2t88.process_stream(f, out_t88, quiet=True)
            snip_t88 = T88File.unpack(io.BytesIO(out_t88.getvalue()))
            snip_payload = snip_t88.extract_cmt_payload()

        # 2. Check baud rate format code in demodulated T88 (0x01CC = 1200 baud)
        data_blocks = [
            b for b in snip_t88.blocks if b.tag == 0x0101 and len(b.data) >= 12
        ]
        self.assertGreater(len(data_blocks), 0)
        dsh0 = DataSubHeader.unpack(data_blocks[0].data[:12])
        self.assertEqual(
            dsh0.fmt_code, 0x01CC, "snippet.wav must demodulate at 1200 baud"
        )

        # 3. Demodulate with native dwimsy.core pipeline and verify parity
        core_payload = self._demod_with_core(wav_path, baud=1200)
        self.assertEqual(
            core_payload,
            snip_payload,
            "dwimsy.core and wav2t88 must produce identical bytes",
        )

        # 4. Verify match against input01.cmt / input01.t88
        cmt_path = pool.get("input01.cmt")
        t88_path = pool.get("input01.t88")
        if cmt_path:
            with open(cmt_path, "rb") as f:
                input01_cmt = f.read()
            self.assertTrue(
                input01_cmt.startswith(snip_payload),
                f"input01.cmt must start with snippet.wav payload ({snip_payload!r})",
            )
            fname, ftype = CMTFile.extract_file_info(input01_cmt)
            self.assertEqual(fname, "DOOR")
            self.assertEqual(ftype, "MON Machine Language Header (0x24)")

        if t88_path:
            with open(t88_path, "rb") as f:
                t88_file = T88File.unpack(io.BytesIO(f.read()))
            input01_t88_payload = t88_file.extract_cmt_payload()
            self.assertTrue(input01_t88_payload.startswith(snip_payload))
            in_data_blocks = [
                b for b in t88_file.blocks if b.tag == 0x0101 and len(b.data) >= 12
            ]
            in_dsh0 = DataSubHeader.unpack(in_data_blocks[0].data[:12])
            self.assertEqual(in_dsh0.fmt_code, 0x01CC)

    def test_snippet2_corresponds_to_input05_digdug_600_baud(self):
        """snippet2.wav is a 600-baud capture of Dig Dug (N88-BASIC 0xD3), matching input05.t88 / input05.cmt."""
        pool = get_fixture_pool()
        wav_path = pool.get("snippet2.wav")
        if not wav_path:
            self.skipTest(pool.skip_reason("snippet2.wav"))

        # 1. Demodulate snippet2.wav with native filter
        with open(wav_path, "rb") as f:
            out_t88 = io.BytesIO()
            native_wav2t88.process_stream(f, out_t88, quiet=True)
            snip_t88 = T88File.unpack(io.BytesIO(out_t88.getvalue()))
            snip_payload = snip_t88.extract_cmt_payload()

        # 2. Check baud rate format code in demodulated T88 (0x00CC = 600 baud)
        data_blocks = [
            b for b in snip_t88.blocks if b.tag == 0x0101 and len(b.data) >= 12
        ]
        self.assertGreater(len(data_blocks), 0)
        dsh0 = DataSubHeader.unpack(data_blocks[0].data[:12])
        self.assertEqual(
            dsh0.fmt_code, 0x00CC, "snippet2.wav must demodulate at 600 baud"
        )

        # 3. Demodulate with native dwimsy.core pipeline and verify parity
        core_payload = self._demod_with_core(wav_path, baud=600)
        self.assertEqual(
            core_payload,
            snip_payload,
            "dwimsy.core and wav2t88 must produce identical bytes",
        )

        # 4. Verify match against input05.cmt / input05.t88
        cmt_path = pool.get("input05.cmt")
        t88_path = pool.get("input05.t88")
        if cmt_path:
            with open(cmt_path, "rb") as f:
                input05_cmt = f.read()
            self.assertTrue(
                input05_cmt.startswith(snip_payload),
                f"input05.cmt must start with snippet2.wav payload ({snip_payload!r})",
            )
            fname, ftype = CMTFile.extract_file_info(input05_cmt)
            self.assertEqual(fname, "DIGDUG")
            self.assertEqual(ftype, "BASIC Program (0xD3)")

        if t88_path:
            with open(t88_path, "rb") as f:
                t88_file = T88File.unpack(io.BytesIO(f.read()))
            input05_t88_payload = t88_file.extract_cmt_payload()
            self.assertTrue(input05_t88_payload.startswith(snip_payload))
            in_data_blocks = [
                b for b in t88_file.blocks if b.tag == 0x0101 and len(b.data) >= 12
            ]
            in_dsh0 = DataSubHeader.unpack(in_data_blocks[0].data[:12])
            self.assertEqual(in_dsh0.fmt_code, 0x00CC)


if __name__ == "__main__":
    unittest.main()
