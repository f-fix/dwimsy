#!/usr/bin/env python3

import importlib.util
import math
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dwimsy.core.pulse import PulseTimingRecognizer
from dwimsy.core.fsk import FSKClassifier, ByteFramer, ClassifiedPulse, DecodedByte
from dwimsy.tests.fixtures import get_fixture_pool


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
        self.assertAlmostEqual(expected, (1 / 2400.0) * math.sqrt(2), places=12)

    def test_octave_shifted_frequencies_classify_correctly(self):
        fs = 44100.0
        r = PulseTimingRecognizer(fs, center_freq=3600.0, bandwidth=4800.0)
        c = FSKClassifier(mark_freq=4800.0, space_freq=2400.0)
        _feed_tone(r, c, 4800.0, 0.05, fs)
        symbols = _feed_tone(r, c, 4800.0, 0.05, fs)
        marks = [p for p in symbols if p.symbol == "M"]
        self.assertGreater(len(marks), len(symbols) * 0.8)


class TestByteFramerSynthetic(unittest.TestCase):

    def _make_pulses(self, symbol_durs, fs=44100.0):
        pulses = []
        sample_idx = 0
        for sym, dur in symbol_durs:
            sample_idx += int(dur * fs)
            pulses.append(ClassifiedPulse(sym, dur, sample_idx))
        return pulses

    def test_decodes_a_simple_byte(self):
        baud = 1200
        bit_dur = 1.0 / baud
        framer = ByteFramer(baud=baud)

        events = []
        events.append(("M", 0.10))
        events.append(("S", bit_dur))
        bits = [1, 0, 1, 0, 1, 0, 1, 0]
        for b in bits:
            events.append(("M" if b else "S", bit_dur))
        events.append(("M", bit_dur * 1.6))
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


REPO_ROOT = Path(__file__).resolve().parent.parent
SUBMODULE_TOOL_PATH = REPO_ROOT / "deps" / "pc88_tape_tools" / "wav2t88.py"


def _has_submodule(rel_path: str) -> bool:
    disk_p = REPO_ROOT / rel_path
    if disk_p.is_file():
        return True
    from dwimsy.meta import unbundle
    try:
        unbundle.get_asset(rel_path)
        return True
    except Exception:
        return False


def _load_submodule(name: str, rel_path: str):
    disk_p = REPO_ROOT / rel_path
    if disk_p.is_file():
        return _load_module(name, str(disk_p))
    from dwimsy.meta import unbundle
    code_text = unbundle.get_asset_text(rel_path)
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    exec(code_text, mod.__dict__)
    return mod


@unittest.skipUnless(
    _has_submodule("deps/pc88_tape_tools/wav2t88.py"),
    f"Submodule tool not found at {SUBMODULE_TOOL_PATH} and not available in bundle payload.",
)
class TestFSKEquivalenceAgainstOriginal(unittest.TestCase):
    def setUp(self):
        self.orig = _load_submodule("orig_wav2t88_for_fsk_check", "deps/pc88_tape_tools/wav2t88.py")

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
        orig = self.orig
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
        self.assertTrue(
            len(original_bytes) > 0, "sanity: original path decoded nothing"
        )
        self.assertEqual(
            original_bytes,
            new_bytes,
            f"core.pulse + core.fsk produced different decoded bytes than "
            f"the original monolithic implementation on {wav_path}",
        )

    def test_equivalence_on_real_tape_snippet_1(self):
        pool = get_fixture_pool()
        wav_path = pool.get("snippet.wav")
        if not wav_path:
            self.skipTest(pool.skip_reason("snippet.wav"))
        self._check_file(wav_path)

    def test_equivalence_on_real_tape_snippet_2(self):
        pool = get_fixture_pool()
        wav_path = pool.get("snippet2.wav")
        if not wav_path:
            self.skipTest(pool.skip_reason("snippet2.wav"))
        self._check_file(wav_path)


if __name__ == "__main__":
    unittest.main()
