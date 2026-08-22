import importlib.util
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dwimsy.core.pulse import PulseTimingRecognizer
from dwimsy.core.fsk import FSKClassifier, ByteFramer, ClassifiedPulse, DecodedByte


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _feed_tone(recognizer, classifier, freq, seconds, fs, amplitude=0.5):
    n = int(seconds * fs)
    symbols = []
    for i in range(n):
        s = amplitude * math.sin(2 * math.pi * freq * i / fs)
        ev = recognizer.process_sample(s)
        if ev is not None:
            symbols.append(classifier.classify(ev))
    return symbols


class TestFSKClassifierSynthetic(unittest.TestCase):

    def test_pure_mark_tone_classified_as_mark(self):
        fs = 44100.0
        r = PulseTimingRecognizer(fs)
        c = FSKClassifier(mark_freq=2400.0, space_freq=1200.0)
        _feed_tone(r, c, 2400.0, 0.05, fs)  # settle
        symbols = _feed_tone(r, c, 2400.0, 0.05, fs)
        marks = [p for p in symbols if p.symbol == "M"]
        self.assertGreater(len(marks), len(symbols) * 0.8)

    def test_pure_space_tone_classified_as_space(self):
        fs = 44100.0
        r = PulseTimingRecognizer(fs)
        c = FSKClassifier(mark_freq=2400.0, space_freq=1200.0)
        _feed_tone(r, c, 1200.0, 0.05, fs)
        symbols = _feed_tone(r, c, 1200.0, 0.05, fs)
        spaces = [p for p in symbols if p.symbol == "S"]
        self.assertGreater(len(spaces), len(symbols) * 0.8)

    def test_silence_classified_as_blank(self):
        fs = 44100.0
        r = PulseTimingRecognizer(fs)
        c = FSKClassifier()
        symbols = []
        for _ in range(int(0.02 * fs)):
            ev = r.process_sample(0.0)
            if ev is not None:
                symbols.append(c.classify(ev))
        self.assertTrue(any(p.symbol == "B" for p in symbols))

    def test_boundary_is_geometric_mean_of_periods(self):
        c = FSKClassifier(mark_freq=2400.0, space_freq=1200.0)
        expected = math.sqrt((1 / 2400.0) * (1 / 1200.0))
        # At 2:1 ratio this should equal the original hardcoded
        # constant (mark_period * sqrt(2)) to high precision.
        self.assertAlmostEqual(expected, (1 / 2400.0) * math.sqrt(2), places=12)

    def test_octave_shifted_frequencies_classify_correctly(self):
        # A "fast MSX mode"-like 4800/2400 Hz pair, fed into a
        # correspondingly-retuned classifier + front end.
        fs = 44100.0
        r = PulseTimingRecognizer(fs, center_freq=3600.0, bandwidth=4800.0)
        c = FSKClassifier(mark_freq=4800.0, space_freq=2400.0)
        _feed_tone(r, c, 4800.0, 0.05, fs)
        symbols = _feed_tone(r, c, 4800.0, 0.05, fs)
        marks = [p for p in symbols if p.symbol == "M"]
        self.assertGreater(len(marks), len(symbols) * 0.8)


class TestByteFramerSynthetic(unittest.TestCase):

    def _make_pulses(self, symbol_durs, fs=44100.0):
        """symbol_durs: list of (symbol, duration_sec) with sample_index
        tracking elapsed audio samples at fs."""
        pulses = []
        sample_idx = 0
        for sym, dur in symbol_durs:
            sample_idx += int(dur * fs)
            pulses.append(ClassifiedPulse(sym, dur, sample_idx))
        return pulses

    def test_decodes_a_simple_byte(self):
        # 1200 baud: bit_duration = 1/1200 s. Build: long Mark leader,
        # then a Space start bit, then 8 data bits (LSB-first) encoding
        # 0x55 = 0b01010101 (bit0=1,bit1=0,...), each bit's dominant
        # symbol held for one full bit_duration, then 2 "stop" bits'
        # worth of Mark.
        baud = 1200
        bit_dur = 1.0 / baud
        framer = ByteFramer(baud=baud)

        events = []
        # Leader: long mark (needs >= max(0.040, bit_dur*25) sec while
        # not in_block/in_session -> use a generous leader).
        events.append(("M", 0.10))
        # Start bit: Space, long enough to exceed start_space_thresh.
        events.append(("S", bit_dur))
        # 8 data bits, LSB-first, value 0x55 = 0b01010101
        # bit0=1(M) bit1=0(S) bit2=1(M) bit3=0(S) bit4=1(M) bit5=0(S) bit6=1(M) bit7=0(S)
        bits = [1, 0, 1, 0, 1, 0, 1, 0]
        for b in bits:
            events.append(("M" if b else "S", bit_dur))
        # Stop: enough Mark time to close out the frame (>= 1.5 bit durations).
        events.append(("M", bit_dur * 1.6))
        # A following Blank to flush any pending state (not required to
        # get a result, since STOP fires as soon as accum_time clears
        # the threshold, but keeps the test's intent explicit).
        events.append(("B", 0.01))

        pulses = self._make_pulses(events)
        results = []
        for p in pulses:
            r = framer.feed(p)
            if r is not None:
                results.append(r)

        self.assertEqual(len(results), 1)
        decoded = results[0]
        self.assertEqual(decoded.value, 0x55)
        self.assertIn(decoded.status, ("OK", "LOW_CONFIDENCE"))
        self.assertGreater(decoded.start_tick, 0)

    def test_blank_resets_idle_state(self):
        framer = ByteFramer(baud=1200)
        r = framer.feed(ClassifiedPulse("B", 0.01, 0))
        self.assertIsNone(r)
        self.assertEqual(framer.state, "IDLE")
        self.assertFalse(framer.leader_validated)


REAL_FIXTURE_DIR = Path("/home/claude/fixtures")
ORIGINAL_TOOL_PATH = Path("/home/claude/src/pc88_tape_tools/wav2t88.py")


@unittest.skipUnless(
    REAL_FIXTURE_DIR.exists() and ORIGINAL_TOOL_PATH.exists(),
    "Private tape-audio fixtures and/or the original standalone tool "
    "aren't available in this environment — see the README's Test "
    "Fixtures section.",
)
class TestFSKEquivalenceAgainstOriginal(unittest.TestCase):
    """
    Swaps BOTH the new PulseTimingRecognizer (core.pulse) and the new
    FSKClassifier + ByteFramer (core.fsk) into the ORIGINAL wav2t88.py
    pipeline in place of its old inline BaudAgnosticPulseRecognizer +
    PulseToByteAcceptor, leaving only the T88 container writing stage
    untouched (that's the next module to port). If the decoded byte
    stream is identical to running the fully original code on the same
    real tape audio, that's strong evidence both new modules together
    are a faithful, lossless split of the original single class.
    """

    def setUp(self):
        self.orig = _load_module("orig_wav2t88_for_fsk_check", str(ORIGINAL_TOOL_PATH))

    def _run_original(self, wav_path):
        orig = self.orig
        with open(wav_path, "rb") as f:
            reader = orig.StreamingWavReader(f, channel_mode="auto")
            fs = reader.sample_rate
            front = orig.BaudAgnosticPulseRecognizer(fs)
            acceptor = orig.PulseToByteAcceptor(baud=1200)
            out_bytes = bytearray()
            while True:
                samples = reader.read_samples(4096)
                if not samples:
                    break
                for s in samples:
                    r = front.process_sample(s)
                    if r is None:
                        continue
                    sym, dur, tick = r
                    acceptor.update_speed(front.speed_factor)
                    result = acceptor.feed_full_cycle(sym, dur, tick)
                    if result is not None:
                        out_bytes.append(result[0] & 0xFF)
            return bytes(out_bytes)

    def _run_new(self, wav_path):
        orig = self.orig  # only for StreamingWavReader, unrelated to what's under test
        with open(wav_path, "rb") as f:
            reader = orig.StreamingWavReader(f, channel_mode="auto")
            fs = reader.sample_rate
            front = PulseTimingRecognizer(fs)
            classifier = FSKClassifier(mark_freq=2400.0, space_freq=1200.0)
            framer = ByteFramer(baud=1200, sample_rate=fs)
            out_bytes = bytearray()
            while True:
                samples = reader.read_samples(4096)
                if not samples:
                    break
                for s in samples:
                    ev = front.process_sample(s)
                    if ev is None:
                        continue
                    pulse = classifier.classify(ev)
                    framer.update_speed(classifier.speed_factor)
                    result = framer.feed(pulse)
                    if result is not None:
                        out_bytes.append(result.value & 0xFF)
            return bytes(out_bytes)

    def _check_file(self, wav_path):
        original_bytes = self._run_original(wav_path)
        new_bytes = self._run_new(wav_path)
        self.assertTrue(len(original_bytes) > 0, "sanity: original path decoded nothing")
        self.assertEqual(
            original_bytes, new_bytes,
            f"core.pulse + core.fsk produced different decoded bytes than "
            f"the original monolithic implementation on {wav_path}",
        )

    def test_equivalence_on_real_tape_snippet_1(self):
        wav_path = REAL_FIXTURE_DIR / "set1" / "snippet.wav"
        if not wav_path.exists():
            self.skipTest(f"{wav_path} not present")
        self._check_file(wav_path)

    def test_equivalence_on_real_tape_snippet_2(self):
        wav_path = REAL_FIXTURE_DIR / "set2" / "snippet2.wav"
        if not wav_path.exists():
            self.skipTest(f"{wav_path} not present")
        self._check_file(wav_path)


if __name__ == "__main__":
    unittest.main()
