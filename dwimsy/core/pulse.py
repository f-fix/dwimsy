"""
dwimsy.core.pulse — analog front-end pulse timing extraction.

This module is the platform-agnostic half of what was previously one
class (``BaudAgnosticPulseRecognizer`` in ``wav2t88.py``): the DC
blocker, bandpass filter, AGC/envelope tracking, Schmitt-trigger
slicer, and sub-sample zero-crossing interpolation that turns a raw
audio sample stream into precisely-timed cycle-period measurements.

Deliberately NOT included here: deciding what a given cycle period
*means* (Mark? Space? Blank?), and any frequency-drift tracking that
depends on that decision. Those are FSK-classification concerns —
inherently platform-tuned (a PC-88 Mark cycle and an MSX-fast-mode Mark
cycle are different durations) — and belong in ``dwimsy.core.fsk``,
which consumes this module's output. This module only answers "how
long was that cycle, precisely, and how strong/clean was the signal
when it happened" — the same question regardless of what frequencies
the caller's platform happens to use for Mark and Space.

The original code's bandpass filter (center 1800 Hz, 600-3600 Hz
bandwidth) and Space-side thresholds were hardcoded around PC-88 and
MSX's shared 2400/1200 Hz tones. Both are now constructor parameters
(``center_freq``, ``bandwidth``) rather than literals, since e.g. an
MSX-fast-mode capture needs the front end retuned an octave up (see
the project README's discussion of MSX's 2400-baud mode being a
tape-speed-doubled version of its 1200-baud waveform, not a timing
change) — that's exactly the kind of per-platform retuning this split
is meant to make a constructor argument instead of a code change.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PulseEvent:
    """
    One measurement emitted by :class:`PulseTimingRecognizer`.

    ``kind`` is either:

    - ``"cycle"``: a complete positive+negative half-cycle pair was
      measured. ``period_sec`` is its duration; ``polarity`` is the
      sign (+1/-1) of the half-cycle that *ended* the pair (matching
      the original code's convention, where the polarity recorded is
      that of the transition immediately preceding the completed
      pair) — callers doing FSK classification don't need to care
      about this, since dwimsy's supported platforms are all
      polarity-independent, but it's preserved for anyone who does.
    - ``"silence"``: no zero-crossing has been seen for long enough
      (>1.5 ms) that the signal is presumptively in a gap, *and* the
      envelope has dropped low enough that this isn't just a slow
      cycle. ``period_sec`` is fixed at 0.0015 for this event, purely
      as a heartbeat tick — real classification of "how long has this
      gap lasted" belongs to whatever's counting consecutive silence
      events, not to this module.

    Every event also carries a same-tick snapshot of the AGC's
    envelope, peak-carrier, and noise-floor trackers, since FSK-layer
    squelch/confidence decisions (e.g. "is this transition too weak to
    trust?") need those values at the moment of the event, not the
    current instant when the caller gets around to reading them.
    """

    kind: str  # "cycle" | "silence"
    time_sec: float
    sample_index: int
    period_sec: float
    polarity: int
    envelope: float
    peak_carrier: float
    noise_floor: float


class PulseTimingRecognizer:
    """
    Analog front-end: DC blocker -> bandpass filter -> AGC -> Schmitt
    trigger -> sub-sample zero-crossing interpolation -> half-cycle
    pairing. Feed it samples one at a time via :meth:`process_sample`;
    it yields a :class:`PulseEvent` whenever it has a new measurement,
    or ``None`` most of the time (most individual samples don't
    complete a cycle or a silence tick).

    Parameters
    ----------
    sample_rate:
        Audio sample rate in Hz.
    center_freq, bandwidth:
        Bandpass filter tuning, in Hz. Defaults (1800 Hz center,
        2400 Hz bandwidth) match PC-88/MSX's standard 2400/1200 Hz
        Mark/Space tones. A caller targeting a different frequency
        pair (e.g. MSX's octave-shifted fast mode, or Amstrad's 2-tone
        PWM scheme) should pass values appropriate to that platform's
        actual tone frequencies.
    dc_blocker_pole:
        Pole location for the one-pole DC-blocking filter. Default
        0.995 matches the original ~180 Hz cutoff at 44.1/48 kHz.
    glitch_reject_sec:
        Half-cycles shorter than this are treated as noise glitches
        and discarded rather than measured. Default 100 microseconds.
    """

    def __init__(
        self,
        sample_rate: float,
        center_freq: float = 1800.0,
        bandwidth: float = 2400.0,
        dc_blocker_pole: float = 0.995,
        glitch_reject_sec: float = 0.00010,
    ):
        self.fs = float(sample_rate)
        self.dt = 1.0 / self.fs
        self.dc_blocker_pole = float(dc_blocker_pole)
        self.glitch_reject_sec = float(glitch_reject_sec)

        # 2nd-order Biquad Bandpass filter coefficients.
        w0 = 2.0 * math.pi * center_freq / self.fs
        q = center_freq / bandwidth
        alpha = math.sin(w0) / (2.0 * q)
        a0 = 1.0 + alpha
        self.b0 = alpha / a0
        self.b1 = 0.0
        self.b2 = -alpha / a0
        self.a1 = (-2.0 * math.cos(w0)) / a0
        self.a2 = (1.0 - alpha) / a0

        self.x1 = 0.0
        self.x2 = 0.0
        self.y1 = 0.0
        self.y2 = 0.0
        self.dc_x1 = 0.0
        self.dc_y1 = 0.0

        self.envelope = 0.0
        self.noise_floor = 0.0001
        self.peak_carrier = 0.001
        self.schmitt_state = 0
        self.last_transition_time = 0.0
        self.current_time = 0.0
        self.prev_y = 0.0

        self.pos_half_dur = 0.0
        self.neg_half_dur = 0.0

    def process_sample(self, s: float) -> Optional[PulseEvent]:
        self.current_time += self.dt

        # 1. DC Blocker
        dc_y = s - self.dc_x1 + self.dc_blocker_pole * self.dc_y1
        self.dc_x1 = s
        self.dc_y1 = dc_y

        # 2. Bandpass Filter
        bp_y = (
            self.b0 * dc_y
            + self.b1 * self.x1
            + self.b2 * self.x2
            - self.a1 * self.y1
            - self.a2 * self.y2
        )
        self.x2 = self.x1
        self.x1 = dc_y
        self.y2 = self.y1
        self.y1 = bp_y

        # 3. Dynamic AGC (Fast attack, rapid decay)
        abs_y = abs(bp_y)
        if abs_y > self.envelope:
            self.envelope = 0.75 * self.envelope + 0.25 * abs_y
        else:
            self.envelope = 0.998 * self.envelope + 0.002 * abs_y

        if self.envelope > self.peak_carrier:
            self.peak_carrier = 0.9 * self.peak_carrier + 0.1 * self.envelope
        else:
            self.peak_carrier = 0.9999 * self.peak_carrier + 0.0001 * self.envelope

        if abs_y < self.noise_floor:
            self.noise_floor = 0.99 * self.noise_floor + 0.01 * abs_y
        else:
            self.noise_floor = 0.99999 * self.noise_floor + 0.00001 * abs_y

        # 4. Adaptive Schmitt Trigger Slicer (12% of envelope)
        v_thresh = max(self.envelope * 0.12, self.noise_floor * 2.0, 0.0003)
        new_state = self.schmitt_state
        if bp_y > v_thresh:
            new_state = 1
        elif bp_y < -v_thresh:
            new_state = -1

        # 5. Zero-crossing transition with sub-sample linear interpolation
        if new_state != self.schmitt_state and new_state != 0:
            if (bp_y - self.prev_y) != 0:
                frac = (0.0 - self.prev_y) / (bp_y - self.prev_y)
                frac = max(0.0, min(1.0, frac))
            else:
                frac = 0.5
            exact_crossing_time = (self.current_time - self.dt) + frac * self.dt

            half_dur_sec = exact_crossing_time - self.last_transition_time
            self.last_transition_time = exact_crossing_time
            prev_polarity = self.schmitt_state
            self.schmitt_state = new_state

            if half_dur_sec >= self.glitch_reject_sec:
                if prev_polarity == 1:
                    self.pos_half_dur = half_dur_sec
                elif prev_polarity == -1:
                    self.neg_half_dur = half_dur_sec

                if self.pos_half_dur > 0 and self.neg_half_dur > 0:
                    full_cycle_sec = self.pos_half_dur + self.neg_half_dur
                    self.pos_half_dur = 0.0
                    self.neg_half_dur = 0.0

                    cur_sample = int(round(exact_crossing_time * self.fs))
                    return PulseEvent(
                        kind="cycle",
                        time_sec=exact_crossing_time,
                        sample_index=cur_sample,
                        period_sec=full_cycle_sec,
                        polarity=prev_polarity,
                        envelope=self.envelope,
                        peak_carrier=self.peak_carrier,
                        noise_floor=self.noise_floor,
                    )
                self.prev_y = bp_y
                return None

        # Silence heartbeat: no transition for a while and the signal
        # has genuinely dropped, not just a slow cycle in progress.
        if (self.current_time - self.last_transition_time) > 0.0015:
            if self.envelope < max(self.noise_floor * 3.0, 0.0008):
                cur_sample = int(round(self.current_time * self.fs))
                return PulseEvent(
                    kind="silence",
                    time_sec=self.current_time,
                    sample_index=cur_sample,
                    period_sec=0.0015,
                    polarity=0,
                    envelope=self.envelope,
                    peak_carrier=self.peak_carrier,
                    noise_floor=self.noise_floor,
                )

        self.prev_y = bp_y
        return None
