"""
dwimsy.core.fsk — FSK pulse classification and UART byte framing.

This is the platform-tuned half of what was previously one class
(``BaudAgnosticPulseRecognizer`` in ``wav2t88.py``, plus the separate
``PulseToByteAcceptor`` class in the same file): deciding whether a
given cycle period measured by :mod:`dwimsy.core.pulse` represents a
Mark tone, a Space tone, or a gap, tracking carrier drift to stay
locked on as tape speed varies, and assembling the resulting Mark/Space
stream into UART-framed bytes.

Two classes:

- :class:`FSKClassifier` consumes :class:`~dwimsy.core.pulse.PulseEvent`
  objects and yields :class:`ClassifiedPulse` objects (Mark/Space/
  Blank + duration). This is where mark/space frequency live as real
  parameters rather than literals — the previous hardcoded 2400.0/
  1200.0 Hz assumptions, and the boundary between "this cycle is a
  Mark" and "this cycle is a Space", are now derived from
  ``mark_freq``/``space_freq`` instead.
- :class:`ByteFramer` consumes :class:`ClassifiedPulse` objects and
  yields :class:`DecodedByte` objects whenever a full UART frame (1
  start bit, 8 data bits LSB-first, 2 stop bits — dwimsy's currently
  supported KCS-derived platforms all share this framing; a future
  platform needing different framing would need this generalized
  further, which isn't done here) has been decoded.

The Mark/Space boundary is computed as the geometric mean of the two
tones' periods (``sqrt(mark_period * space_period)``), which is exactly
equivalent to the original code's hardcoded ``mark_period * 1.414``
when mark:space is a 2:1 frequency ratio (as it is for every platform
dwimsy currently targets) — sqrt(2) is what you get from the geometric
mean formula at a 2:1 ratio specifically. The general formula is used
here instead of the ratio-specific constant so it keeps working
correctly if a future platform doesn't share that exact 2:1 relationship.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .pulse import PulseEvent

__all__ = ["ClassifiedPulse", "DecodedByte", "FSKClassifier", "ByteFramer"]


@dataclass(frozen=True)
class ClassifiedPulse:
    """One classified cycle, handed from :class:`FSKClassifier` to
    :class:`ByteFramer`. ``symbol`` is one of ``"M"`` (Mark), ``"S"``
    (Space), or ``"B"`` (Blank/gap)."""

    symbol: str
    duration_sec: float
    sample_index: int


@dataclass(frozen=True)
class DecodedByte:
    """One fully-framed byte, emitted by :class:`ByteFramer`. ``status``
    is one of ``"OK"``, ``"LOW_CONFIDENCE"``, or ``"FRAMING_ERROR"``;
    ``confidence`` is the mean per-bit confidence across the frame."""

    value: int
    start_tick: int
    status: str
    confidence: float


class FSKClassifier:
    """
    Classifies cycle periods from :mod:`dwimsy.core.pulse` as Mark,
    Space, or Blank, and tracks carrier drift (tape motor speed
    variation) to stay adaptively locked onto the true Mark frequency
    as it wanders.

    Parameters
    ----------
    mark_freq, space_freq:
        Nominal Mark/Space tone frequencies in Hz. Defaults (2400/1200)
        match PC-88 and standard MSX. A platform with different tones
        (e.g. Amstrad's ~667/1333 Hz 2-tone PWM) would pass those
        instead — the boundary and drift-tracking math below derives
        everything else from these two values.
    envelope_squelch_ratio, noise_floor_squelch_ratio, min_squelch_envelope:
        Amplitude-domain thresholds for deciding a weak/absent signal
        should be treated as Blank rather than classified by frequency
        at all. Not frequency-dependent; exposed mainly for tuning
        against unusually noisy captures.
    drift_plausible_range:
        A (min_ratio, max_ratio) pair, expressed as a fraction of the
        nominal Mark period, bounding which measured Mark cycle
        durations are trusted enough to feed into drift tracking (this
        rejects e.g. a stray Space-adjacent cycle from skewing the
        estimate). Defaults (0.77, 1.25) match the original code's
        literal 0.00032s/0.00052s bounds at 2400 Hz.
    """

    def __init__(
        self,
        mark_freq: float = 2400.0,
        space_freq: float = 1200.0,
        envelope_squelch_ratio: float = 0.22,
        noise_floor_squelch_ratio: float = 2.0,
        min_squelch_envelope: float = 0.0005,
        drift_plausible_range: Tuple[float, float] = (0.77, 1.25),
        drift_smoothing: float = 0.04,
        mark_history_len: int = 80,
        mark_history_min: int = 20,
    ):
        self.nominal_mark_freq = float(mark_freq)
        self.nominal_space_freq = float(space_freq)
        self.nominal_mark_period = 1.0 / self.nominal_mark_freq
        self.nominal_space_period = 1.0 / self.nominal_space_freq

        self.envelope_squelch_ratio = float(envelope_squelch_ratio)
        self.noise_floor_squelch_ratio = float(noise_floor_squelch_ratio)
        self.min_squelch_envelope = float(min_squelch_envelope)

        self.drift_min_period = self.nominal_mark_period * drift_plausible_range[0]
        self.drift_max_period = self.nominal_mark_period * drift_plausible_range[1]
        self.drift_smoothing = float(drift_smoothing)
        self.mark_history_len = int(mark_history_len)
        self.mark_history_min = int(mark_history_min)

        self.measured_f_mark = self.nominal_mark_freq
        self.speed_factor = 1.0
        self.mark_dur_hist: List[float] = []

    def classify(self, event: PulseEvent) -> ClassifiedPulse:
        """Classifies a single PulseEvent. Callers should feed every
        event from :class:`~dwimsy.core.pulse.PulseTimingRecognizer` in
        order; this method updates internal drift-tracking state as a
        side effect, so it isn't safe to call out of order or on a
        subset of events."""

        if event.kind == "silence":
            self.mark_dur_hist.clear()
            return ClassifiedPulse("B", event.period_sec, event.sample_index)

        period_sec = event.period_sec
        boundary_period = math.sqrt(
            self.nominal_mark_period_for_drift() * self.nominal_space_period
        )

        if event.envelope < max(
            event.peak_carrier * self.envelope_squelch_ratio,
            event.noise_floor * self.noise_floor_squelch_ratio,
            self.min_squelch_envelope,
        ):
            self.mark_dur_hist.clear()
            symbol = "B"
        elif period_sec < boundary_period:
            symbol = "M"
            self.mark_dur_hist.append(period_sec)
            if len(self.mark_dur_hist) > self.mark_history_len:
                self.mark_dur_hist.pop(0)
            if len(self.mark_dur_hist) >= self.mark_history_min:
                med_mark = sorted(self.mark_dur_hist)[len(self.mark_dur_hist) // 2]
                if self.drift_min_period <= med_mark <= self.drift_max_period:
                    self.measured_f_mark = (
                        1.0 - self.drift_smoothing
                    ) * self.measured_f_mark + self.drift_smoothing * (1.0 / med_mark)
                    self.speed_factor = self.measured_f_mark / self.nominal_mark_freq
        elif period_sec <= (self.nominal_space_period / 0.75):
            symbol = "S"
            self.mark_dur_hist.clear()
        else:
            symbol = "B"
            self.mark_dur_hist.clear()

        return ClassifiedPulse(symbol, period_sec, event.sample_index)

    def nominal_mark_period_for_drift(self) -> float:
        """The currently drift-tracked Mark period (``1 /
        measured_f_mark``), used to (re)compute the Mark/Space boundary
        each classification. Kept as its own method rather than an
        always-current attribute so the boundary calculation reads the
        same value it's about to be compared against, regardless of
        when :attr:`measured_f_mark` was last updated."""
        return 1.0 / self.measured_f_mark


class ByteFramer:
    """
    Converts a stream of :class:`ClassifiedPulse` (Mark/Space/Blank)
    into UART-framed bytes: 1 start bit, 8 data bits (LSB-first), 2
    stop bits, matching every KCS-derived platform dwimsy currently
    targets. 600 baud is exactly pulse-doubled 1200 baud (twice the
    cycles per bit at the same tone frequencies) rather than a
    different frame structure, so both are handled by the same class
    with a different ``baud`` value.
    """

    def __init__(
        self,
        baud: int,
        confidence_threshold: float = 0.75,
        sample_rate: float = 44100.0,
        filter_group_delay_samples: float = 5.5,
        t88_tick_rate: float = 4800.0,
    ):
        self.nominal_baud = baud
        self.baud = float(baud)
        self.bit_duration = 1.0 / self.baud
        self.confidence_threshold = float(confidence_threshold)
        self.speed_factor = 1.0
        self.sample_rate = float(sample_rate)
        self.filter_group_delay_samples = float(filter_group_delay_samples)
        self.t88_tick_rate = float(t88_tick_rate)
        self.reset()

    def update_speed(self, speed_factor: float):
        self.speed_factor = max(0.85, min(1.18, speed_factor))
        self.baud = self.nominal_baud * self.speed_factor
        self.bit_duration = 1.0 / self.baud

    def reset(self, in_block: bool = False, in_session: bool = False):
        self.state = "IDLE"  # IDLE, DATA, STOP
        self.bit_index = 0
        self.current_byte = 0
        self.accum_time = 0.0
        self.mark_time = 0.0
        self.space_time = 0.0
        self.start_tick = 0
        self.last_activity_tick = 0
        self.carrier_mark_time = 0.0
        self.consecutive_mark_time = 0.0
        self.in_block = in_block
        self.in_session = in_session
        self.leader_validated = False
        self.bit_confidences: List[float] = []

    def feed(self, pulse: ClassifiedPulse) -> Optional[DecodedByte]:
        sym, dur_sec, cur_tick = pulse.symbol, pulse.duration_sec, pulse.sample_index

        if sym == "B":
            self.state = "IDLE"
            self.carrier_mark_time = 0.0
            self.consecutive_mark_time = 0.0
            self.leader_validated = False
            self.in_block = False
            self.in_session = False
            self.bit_confidences.clear()
            return None

        if sym == "M":
            self.mark_time += dur_sec
            self.carrier_mark_time += dur_sec
            self.consecutive_mark_time += dur_sec
        elif sym == "S":
            self.space_time += dur_sec
            self.carrier_mark_time = 0.0
        else:
            self.state = "IDLE"
            return None

        self.accum_time += dur_sec
        result: Optional[DecodedByte] = None

        if self.state == "IDLE":
            if sym == "M":
                self.space_time = 0.0
                self.accum_time = 0.0
                min_mark = (
                    (self.bit_duration * 0.90)
                    if self.in_block
                    else (
                        max(0.020, self.bit_duration * 12.0)
                        if self.in_session
                        else max(0.040, self.bit_duration * 25.0)
                    )
                )
                if self.consecutive_mark_time >= min_mark:
                    self.leader_validated = True
            elif sym == "S":
                if not self.leader_validated:
                    self.consecutive_mark_time = 0.0
                    self.space_time = 0.0
                    self.accum_time = 0.0
                    return None

                start_cycles = 1200.0 / self.nominal_baud
                start_space_thresh = max(
                    (start_cycles - 0.35)
                    * (1.0 / (1200.0 * (self.baud / self.nominal_baud))),
                    self.bit_duration * 0.65,
                )
                if self.space_time >= start_space_thresh:
                    self.state = "DATA"
                    self.bit_index = 0
                    self.current_byte = 0
                    tot_start = self.space_time + self.mark_time
                    start_conf = (
                        min(
                            1.0,
                            self.space_time / max(self.bit_duration * 0.85, tot_start),
                        )
                        if tot_start > 0
                        else 0.0
                    )
                    self.bit_confidences = [start_conf]
                    self.accum_time -= self.bit_duration
                    if self.accum_time < 0:
                        self.accum_time = 0.0
                    self.mark_time = 0.0
                    self.space_time = 0.0
                    # Start-bit rewind under the time-base-corrected
                    # clock: cur_tick is expressed in T88 ticks
                    # (t88_tick_rate Hz, not the audio sample rate), so
                    # the filter's group delay — inherently a number of
                    # *audio samples* — must be converted into the same
                    # tape-time seconds before being subtracted.
                    nominal_bit_dur_tape = 1.0 / self.nominal_baud
                    filter_delay_tape = (
                        self.filter_group_delay_samples
                        / self.sample_rate
                        * self.speed_factor
                    )
                    self.start_tick = max(
                        0,
                        int(
                            round(
                                (
                                    (cur_tick / self.t88_tick_rate)
                                    - nominal_bit_dur_tape
                                    - filter_delay_tape
                                )
                                * self.t88_tick_rate
                            )
                        ),
                    )
                    self.last_activity_tick = cur_tick
                    self.consecutive_mark_time = 0.0
                    self.leader_validated = False

        elif self.state == "DATA":
            bit_thresh = self.bit_duration - 0.000150
            if self.accum_time >= bit_thresh:
                tot = self.mark_time + self.space_time
                if tot > 0:
                    bit_val = 1 if self.mark_time >= self.space_time else 0
                    bit_conf = max(self.mark_time, self.space_time) / tot
                else:
                    bit_val = 0
                    bit_conf = 0.0
                self.bit_confidences.append(bit_conf)

                self.current_byte |= bit_val << self.bit_index
                self.bit_index += 1
                self.accum_time -= self.bit_duration
                if self.accum_time < 0:
                    self.accum_time = 0.0
                self.mark_time = 0.0
                self.space_time = 0.0
                self.last_activity_tick = cur_tick

                if self.bit_index == 8:
                    self.state = "STOP"

        elif self.state == "STOP":
            if self.accum_time >= (self.bit_duration * 1.50):
                self.last_activity_tick = cur_tick
                tot = self.mark_time + self.space_time
                stop_conf = (self.mark_time / tot) if tot > 0 else 0.0
                self.bit_confidences.append(stop_conf)

                byte_conf = (
                    sum(self.bit_confidences) / len(self.bit_confidences)
                    if self.bit_confidences
                    else 0.0
                )
                low_conf_bits = sum(1 for c in self.bit_confidences if c < 0.55)

                if tot > 0 and (self.mark_time / tot) >= 0.60:
                    if byte_conf >= self.confidence_threshold and low_conf_bits <= 2:
                        result = DecodedByte(
                            self.current_byte, self.start_tick, "OK", byte_conf
                        )
                    else:
                        result = DecodedByte(
                            self.current_byte,
                            self.start_tick,
                            "LOW_CONFIDENCE",
                            byte_conf,
                        )
                else:
                    result = DecodedByte(
                        self.current_byte, self.start_tick, "FRAMING_ERROR", byte_conf
                    )

                self.state = "IDLE"
                self.accum_time = 0.0
                self.mark_time = 0.0
                self.space_time = 0.0
                self.bit_confidences.clear()
                self.leader_validated = self.in_block
                self.consecutive_mark_time = self.bit_duration * 1.5

        return result
