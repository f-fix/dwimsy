#!/usr/bin/env python3
"""tests.test_core_pulse - Verify pulse timing recognition and zero-crossing detection."""

import importlib.util
import io
import math
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dwimsy.core.pulse import PulseTimingRecognizer, PulseEvent
from dwimsy.tests.fixtures import get_fixture_pool


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPulseTimingRecognizerSynthetic(unittest.TestCase):
    """Isolated tests against synthetic signals, independent of any
    real tape audio or the original standalone tool."""

    def _feed_tone(self, recognizer, freq, seconds, fs, amplitude=0.5):
        n = int(seconds * fs)
        events = []
        for i in range(n):
            s = amplitude * math.sin(2 * math.pi * freq * i / fs)
            ev = recognizer.process_sample(s)
            if ev is not None:
                events.append(ev)
        return events

    def test_pure_2400hz_tone_measures_correct_period(self):
        fs = 44100.0
        r = PulseTimingRecognizer(fs)
        self._feed_tone(r, 2400.0, 0.05, fs)
        events = self._feed_tone(r, 2400.0, 0.05, fs)
        cycles = [e for e in events if e.kind == "cycle"]
        self.assertGreater(len(cycles), 5)
        periods = [e.period_sec for e in cycles[3:-1]]
        avg_period = sum(periods) / len(periods)
        self.assertAlmostEqual(avg_period, 1.0 / 2400.0, delta=1e-5)

    def test_pure_1200hz_tone_measures_correct_period(self):
        fs = 44100.0
        r = PulseTimingRecognizer(fs)
        self._feed_tone(r, 1200.0, 0.05, fs)
        events = self._feed_tone(r, 1200.0, 0.05, fs)
        cycles = [e for e in events if e.kind == "cycle"]
        self.assertGreater(len(cycles), 5)
        periods = [e.period_sec for e in cycles[3:-1]]
        avg_period = sum(periods) / len(periods)
        self.assertAlmostEqual(avg_period, 1.0 / 1200.0, delta=2e-5)

    def test_dc_offset_is_blocked(self):
        fs = 44100.0
        r = PulseTimingRecognizer(fs)
        n = int(0.05 * fs)
        for i in range(n):
            s = 0.9 + 0.15 * math.sin(2 * math.pi * 2400.0 * i / fs)
            r.process_sample(s)
        events = []
        for i in range(n, n + int(0.05 * fs)):
            s = 0.9 + 0.15 * math.sin(2 * math.pi * 2400.0 * i / fs)
            ev = r.process_sample(s)
            if ev is not None:
                events.append(ev)
        cycles = [e for e in events if e.kind == "cycle"]
        self.assertGreater(len(cycles), 5)

    def test_silence_emits_heartbeat_after_gap(self):
        fs = 44100.0
        r = PulseTimingRecognizer(fs)
        events = []
        for i in range(int(0.02 * fs)):
            ev = r.process_sample(0.0)
            if ev is not None:
                events.append(ev)
        silences = [e for e in events if e.kind == "silence"]
        self.assertGreater(len(silences), 0)

    def test_subsample_glitch_shorter_than_threshold_is_rejected(self):
        fs = 44100.0
        r = PulseTimingRecognizer(fs, glitch_reject_sec=0.0002)
        events = self._feed_tone(r, 2400.0, 0.02, fs)
        events += self._feed_tone(r, 2400.0, 0.02, fs)
        cycles = [e for e in events if e.kind == "cycle"]
        self.assertGreater(len(cycles), 5)

    def test_higher_frequency_drift_not_rejected_as_glitch(self):
        fs = 44100.0
        r = PulseTimingRecognizer(fs, center_freq=3600.0, bandwidth=4800.0)
        self._feed_tone(r, 5040.0, 0.05, fs)
        events = self._feed_tone(r, 5040.0, 0.05, fs)
        cycles = [e for e in events if e.kind == "cycle"]
        self.assertGreater(len(cycles), 20)

    def test_center_freq_and_bandwidth_are_configurable(self):
        fs = 44100.0
        r = PulseTimingRecognizer(fs, center_freq=3600.0, bandwidth=4800.0)
        self._feed_tone(r, 4800.0, 0.05, fs)
        events = self._feed_tone(r, 4800.0, 0.05, fs)
        cycles = [e for e in events if e.kind == "cycle"]
        self.assertGreater(len(cycles), 5)
        periods = [e.period_sec for e in cycles[3:-1]]
        avg_period = sum(periods) / len(periods)
        self.assertAlmostEqual(avg_period, 1.0 / 4800.0, delta=1e-5)


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
class TestPulseEquivalenceAgainstOriginal(unittest.TestCase):
    def setUp(self):
        self.orig = _load_submodule(
            "orig_wav2t88_for_pulse_check", "deps/pc88_tape_tools/wav2t88.py"
        )

    def _run_demod_with_frontend(self, wav_path, use_new_frontend):
        orig = self.orig

        with open(wav_path, "rb") as f:
            reader = orig.StreamingWavReader(f, channel_mode="auto")
            fs = reader.sample_rate

            if use_new_frontend:
                front = PulseTimingRecognizer(fs)
            else:
                front = orig.BaudAgnosticPulseRecognizer(fs)

            measured_f_mark = 2400.0
            mark_dur_hist = []
            speed_factor = 1.0

            def classify(period_sec, envelope, peak_carrier, noise_floor):
                nonlocal measured_f_mark, speed_factor
                nominal_mark_period = 1.0 / measured_f_mark
                boundary_period = nominal_mark_period * 1.414

                if envelope < max(peak_carrier * 0.22, noise_floor * 2.0, 0.0005):
                    mark_dur_hist.clear()
                    return "B"
                elif period_sec < boundary_period:
                    mark_dur_hist.append(period_sec)
                    if len(mark_dur_hist) > 80:
                        mark_dur_hist.pop(0)
                    if len(mark_dur_hist) >= 20:
                        med_mark = sorted(mark_dur_hist)[len(mark_dur_hist) // 2]
                        if 0.00032 <= med_mark <= 0.00052:
                            measured_f_mark = 0.96 * measured_f_mark + 0.04 * (
                                1.0 / med_mark
                            )
                            speed_factor = measured_f_mark / 2400.0
                    return "M"
                elif period_sec <= (1.0 / (1200.0 * 0.75)):
                    mark_dur_hist.clear()
                    return "S"
                else:
                    mark_dur_hist.clear()
                    return "B"

            acceptor = orig.PulseToByteAcceptor(baud=1200)
            out_bytes = bytearray()

            while True:
                samples = reader.read_samples(4096)
                if not samples:
                    break
                for s in samples:
                    if use_new_frontend:
                        ev = front.process_sample(s)
                        if ev is None:
                            continue
                        if ev.kind == "silence":
                            sym, dur, tick = "B", ev.period_sec, ev.sample_index
                        else:
                            sym = classify(
                                ev.period_sec,
                                ev.envelope,
                                ev.peak_carrier,
                                ev.noise_floor,
                            )
                            dur, tick = ev.period_sec, ev.sample_index
                        acceptor.update_speed(speed_factor)
                        result = acceptor.feed_full_cycle(sym, dur, tick)
                    else:
                        r = front.process_sample(s)
                        if r is None:
                            continue
                        sym, dur, tick = r
                        acceptor.update_speed(front.speed_factor)
                        result = acceptor.feed_full_cycle(sym, dur, tick)

                    if result is not None:
                        byte_val, _start_tick, _status, _conf = result
                        out_bytes.append(byte_val & 0xFF)

            return bytes(out_bytes)

    def _check_file(self, wav_path):
        original_bytes = self._run_demod_with_frontend(wav_path, use_new_frontend=False)
        new_bytes = self._run_demod_with_frontend(wav_path, use_new_frontend=True)
        self.assertTrue(
            len(original_bytes) > 0, "sanity: original path decoded nothing"
        )
        self.assertEqual(
            original_bytes,
            new_bytes,
            f"core.pulse front end produced different decoded bytes than the "
            f"original inline front end on {wav_path}",
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
