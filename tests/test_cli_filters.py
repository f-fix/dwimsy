#!/usr/bin/env python3
"""tests.test_cli_filters - Verify streaming conversion filters and CLI pipelines."""

import io
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dwimsy.tape.t88 import T88File
from dwimsy.cli.filters import t882wav as native_t882wav
from dwimsy.cli.filters import wav2t88 as native_wav2t88
from dwimsy.cli import main as dwimsy_cli
from dwimsy.tests.fixtures import get_fixture_pool


class TestPhase1FiltersAndCLI(unittest.TestCase):
    def test_native_t882wav_synthetic_roundtrip(self):
        payload = b"\xd3" * 10 + b"PHASE1_FILTER_TEST"
        t88_obj = T88File.from_cmt_data(payload, baud=1200)
        t88_bytes = t88_obj.pack()

        wav_out = io.BytesIO()
        native_t882wav.convert_t88_to_wav(
            io.BytesIO(t88_bytes), wav_out, mode="tape", quiet=True
        )
        wav_data = wav_out.getvalue()
        self.assertGreater(len(wav_data), 44)

        t88_out = io.BytesIO()
        native_wav2t88.process_stream(io.BytesIO(wav_data), t88_out, quiet=True)
        t88_demod_data = t88_out.getvalue()

        demod_obj = T88File.unpack(io.BytesIO(t88_demod_data))
        self.assertEqual(demod_obj.extract_cmt_payload(), payload)

    def test_real_sample_input16_roundtrip_verification(self):
        """Milestone 1 Verification: Bit-exact roundtrip on a real PC-88 sample (input16.t88)."""
        pool = get_fixture_pool()
        t88_path = pool.get("input16.t88")
        cmt_path = pool.get("input16.cmt")
        if not (t88_path and cmt_path):
            self.skipTest(pool.skip_reason("input16.t88") if not t88_path else pool.skip_reason("input16.cmt"))

        with open(t88_path, "rb") as f:
            t88_orig_bytes = f.read()
        with open(cmt_path, "rb") as f:
            expected_cmt = f.read()

        wav_out = io.BytesIO()
        native_t882wav.convert_t88_to_wav(
            io.BytesIO(t88_orig_bytes), wav_out, mode="tape", quiet=True
        )
        wav_bytes = wav_out.getvalue()

        t88_out = io.BytesIO()
        native_wav2t88.process_stream(io.BytesIO(wav_bytes), t88_out, quiet=True)
        t88_demod_bytes = t88_out.getvalue()

        demod_file = T88File.unpack(io.BytesIO(t88_demod_bytes))
        demod_cmt = demod_file.extract_cmt_payload()
        self.assertEqual(
            demod_cmt,
            expected_cmt,
            "Demodulated CMT payload must match reference input16.cmt byte-for-byte",
        )

    def test_cli_convert_routing_t88_to_cmt(self):
        pool = get_fixture_pool()
        t88_path = pool.get("input16.t88")
        cmt_path = pool.get("input16.cmt")
        if not (t88_path and cmt_path):
            self.skipTest(pool.skip_reason("input16.t88") if not t88_path else pool.skip_reason("input16.cmt"))

        class ConvertArgs:
            command = "convert"
            input = str(t88_path)
            output = "-"
            from_format = "t88"
            to_format = "cmt"
            mode = "tape"
            baud = None
            sample_rate = 44100
            channels = 1
            stereo_mode = "dual"
            channel = "auto"
            amplitude = 0.8
            speed = 1.0
            confidence = 0.75
            quiet = True

        out_s = io.BytesIO()
        old_stdout = sys.stdout

        class StdoutBufferWrapper:
            buffer = out_s

        sys.stdout = StdoutBufferWrapper()
        try:
            dwimsy_cli.run_convert(ConvertArgs)
        finally:
            sys.stdout = old_stdout

        with open(cmt_path, "rb") as f:
            expected_cmt = f.read()
        self.assertEqual(out_s.getvalue(), expected_cmt)


if __name__ == "__main__":
    unittest.main()
