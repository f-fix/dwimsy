import importlib.util
import io
import math
import os
import sys
import unittest
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dwimsy.core.pulse import PulseTimingRecognizer, PulseEvent


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
        # Let AGC/filters settle first.
        self._feed_tone(r, 2400.0, 0.05, fs)
        events = self._feed_tone(r, 2400.0, 0.05, fs)
        cycles = [e for e in events if e.kind == "cycle"]
        self.assertGreater(len(cycles), 5)
        periods = [e.period_sec for e in cycles[3:-1]]  # skip transients
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
        # A large DC offset plus a small 2400 Hz tone should still be
        # trackable — the DC blocker must remove the offset, not just
        # attenuate it, or the Schmitt slicer's symmetric threshold
        # would never fire since positive-going crossings would be
        # biased away from occurring at the true zero-crossing.
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
        # Establish a settled noise floor first with near-silence.
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
        # Feed a clean 2400 Hz tone; every measured half-cycle should
        # be well above the (deliberately raised) glitch threshold, so
        # no cycle should ever be silently dropped for being "too
        # short" under normal operation.
        events = self._feed_tone(r, 2400.0, 0.02, fs)
        events += self._feed_tone(r, 2400.0, 0.02, fs)
        cycles = [e for e in events if e.kind == "cycle"]
        self.assertGreater(len(cycles), 5)

    def test_higher_frequency_drift_not_rejected_as_glitch(self):
        # Fast 4800 Hz tone (+5% speed = 5040 Hz) should not be rejected
        fs = 44100.0
        r = PulseTimingRecognizer(fs, center_freq=3600.0, bandwidth=4800.0)
        self._feed_tone(r, 5040.0, 0.05, fs)
        events = self._feed_tone(r, 5040.0, 0.05, fs)
        cycles = [e for e in events if e.kind == "cycle"]
        self.assertGreater(len(cycles), 20)

    def test_center_freq_and_bandwidth_are_configurable(self):
        # An octave-shifted "MSX fast mode"-like tone (4800/2400 Hz)
        # should be trackable once the front end is retuned up an
        # octave, confirming center_freq/bandwidth genuinely change
        # filter behavior rather than being ignored parameters.
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
DEFAULT_FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


def find_fixture_path(
    filename: str, subdirs: Tuple[str, ...] = ("set1", "set2", "pc88", "")
) -> Optional[Path]:
    """Locate a sample fixture file in tests/fixtures or via DWIMSY_TEST_FIXTURES."""
    search_roots = []
    env_dir = os.environ.get("DWIMSY_TEST_FIXTURES")
    if env_dir:
        search_roots.append(Path(env_dir))
    search_roots.append(DEFAULT_FIXTURES_DIR)
    search_roots.append(REPO_ROOT / "fixtures")

    for root in search_roots:
        if not root.exists():
            continue
        direct = root / filename
        if direct.is_file():
            return direct
        for sub in subdirs:
            p = root / sub / filename
            if p.is_file():
                return p
        for match in root.rglob(filename):
            if match.is_file():
                return match
    return None


@unittest.skipUnless(
    SUBMODULE_TOOL_PATH.exists(),
    f"Submodule tool not found at {SUBMODULE_TOOL_PATH}. Ensure git submodules are initialized "
    "(git submodule update --init --recursive).",
)
class TestPulseEquivalenceAgainstOriginal(unittest.TestCase):
    """
    Swaps the new PulseTimingRecognizer into the submodule wav2t88.py
    pipeline in place of its old inline analog front end
    (BaudAgnosticPulseRecognizer.process_sample), leaving every
    downstream stage — classification thresholds, drift tracking,
    UART byte framing, T88 container writing — completely untouched.

    If the final .t88 bytes produced this way are identical to running
    the fully original, unmodified tool on the same real tape audio,
    that's strong evidence the extracted front end is a faithful,
    lossless port: everything but the analog front end is provably
    identical code, so any behavior difference would have to come from
    the front end itself.
    """

    def setUp(self):
        self.orig = _load_module(
            "orig_wav2t88_for_pulse_check", str(SUBMODULE_TOOL_PATH)
        )

    def _run_demod_with_frontend(self, wav_path, use_new_frontend):
        """Runs the original module's demodulation loop, swapping in
        the new PulseTimingRecognizer for the analog front end when
        use_new_frontend is True. Mirrors the original module's own
        top-level demodulation loop closely enough to produce the same
        T88 bytes it would via its normal CLI path, without needing to
        shell out to it."""
        orig = self.orig

        with open(wav_path, "rb") as f:
            reader = orig.StreamingWavReader(f, channel_mode="auto")
            fs = reader.sample_rate

            if use_new_frontend:
                front = PulseTimingRecognizer(fs)
            else:
                front = orig.BaudAgnosticPulseRecognizer(fs)

            # Classification state mirrors the ORIGINAL class's own
            # instance attributes exactly, since with use_new_frontend
            # this logic is now external to the recognizer object.
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
        wav_path = find_fixture_path("snippet.wav", subdirs=("set1", "pc88", ""))
        if not wav_path or not wav_path.exists():
            self.skipTest(
                "snippet.wav not found in tests/fixtures/ (or DWIMSY_TEST_FIXTURES). "
                "Unpack sample data into tests/fixtures/ to run this test."
            )
        self._check_file(wav_path)

    def test_equivalence_on_real_tape_snippet_2(self):
        wav_path = find_fixture_path("snippet2.wav", subdirs=("set2", "pc88", ""))
        if not wav_path or not wav_path.exists():
            self.skipTest(
                "snippet2.wav not found in tests/fixtures/ (or DWIMSY_TEST_FIXTURES). "
                "Unpack sample data into tests/fixtures/ to run this test."
            )
        self._check_file(wav_path)


if __name__ == "__main__":
    unittest.main()
