#!/usr/bin/env python3
"""dwimsy.cli.filters.t882wav - Streaming T88 to WAV audio synthesizer filter.

Backed directly by dwimsy.core.audio (StreamingWavWriter).
"""

from __future__ import annotations

from dwimsy.meta.integrity import version as get_version

import argparse
import io
import math
import os
import struct
import sys
from typing import BinaryIO, Generator, List, Optional, Tuple

from dwimsy.core.audio import StreamingWavWriter
from dwimsy.tape.t88 import (
    DataSubHeader,
    StreamingT88Reader,
    T88Tag,
    T88_HEADER_MAGICS,
)


class T88ToWavSynthesizer:
    def __init__(
        self,
        sample_rate: int = 44100,
        mode: str = "tape",
        amplitude: float = 0.8,
        speed_factor: float = 1.0,
        invert_polarity: bool = False,
    ):
        self.sr = float(sample_rate)
        self.dt = 1.0 / self.sr
        self.mode = mode.lower()
        self.amplitude = max(0.01, min(1.0, float(amplitude)))
        self.speed = max(0.5, min(2.0, float(speed_factor)))
        self.invert = bool(invert_polarity)
        self.current_time = 0.0

        rc_cutoff_hz = 6000.0
        rc_w = 2.0 * math.pi * rc_cutoff_hz
        self.lp_alpha = (rc_w * self.dt) / (1.0 + rc_w * self.dt)
        self.rc_lp = 0.0
        self.dc_x1 = 0.0
        self.dc_y1 = 0.0

        if self.mode in ("ideal", "square", "direct"):
            self._kind = "ideal"
        elif self.mode in ("acoustic", "motor", "spinup"):
            self._kind = "acoustic"
        elif self.mode in ("tape", "cassette", "readback"):
            self._kind = "tape"
        elif self.mode in ("shaped", "pc", "circuit"):
            self._kind = "shaped"
        else:
            self._kind = "raw"

    def generate_silence(self, duration_sec: float) -> List[float]:
        if duration_sec <= 0.0:
            return []
        samples = []
        t_end = self.current_time + duration_sec
        while self.current_time < t_end:
            samples.append(0.0)
            self.current_time += self.dt
        return samples

    def _gen_wave(
        self, two_pi_f: float, duration_sec: float, apply_ramp: bool
    ) -> List[float]:
        if duration_sec <= 0.0:
            return []
        samples = []
        append = samples.append
        dt = self.dt
        amplitude = self.amplitude
        invert = self.invert
        kind = self._kind
        ramp_dur = 0.0025

        t = self.current_time
        t_start = t
        t_end = t + duration_sec
        _sin = math.sin

        if kind == "acoustic":
            _tanh, _exp = math.tanh, math.exp
            tau, t_relay, spinup_dur = 0.080, 0.020, 0.140
            while t < t_end:
                t_rel = t - t_start
                if apply_ramp and t_rel < spinup_dur:
                    if t_rel < t_relay:
                        out = 0.0
                    else:
                        speed_mult = 1.0 - _exp(-(t_rel - t_relay) / tau)
                        phase = two_pi_f * (t_rel - t_relay) * speed_mult
                        sin_val = _sin(phase)
                        base = _tanh((sin_val + 0.15 * _sin(2.0 * phase)) * 1.8)
                        ramp_factor = min(
                            1.0, (t_rel - t_relay) / (spinup_dur - t_relay)
                        )
                        out = base * amplitude * ramp_factor
                else:
                    phase = two_pi_f * t_rel
                    sin_val = _sin(phase)
                    base = _tanh((sin_val + 0.15 * _sin(2.0 * phase)) * 1.8)
                    out = base * amplitude
                if invert:
                    out = -out
                append(out)
                t += dt

        elif kind == "tape":
            _tanh, _cos, pi = math.tanh, math.cos, math.pi
            while t < t_end:
                t_rel = t - t_start
                phase = two_pi_f * t_rel
                sin_val = _sin(phase)
                base = _tanh((sin_val + 0.15 * _sin(2.0 * phase)) * 1.8)
                out = base * amplitude
                if invert:
                    out = -out
                if apply_ramp and t_rel < ramp_dur:
                    out *= 0.5 * (1.0 - _cos(pi * (t_rel / ramp_dur)))
                append(out)
                t += dt

        elif kind == "shaped":
            _cos, pi = math.cos, math.pi
            rc_lp, lp_alpha, dc_x1, dc_y1 = (
                self.rc_lp,
                self.lp_alpha,
                self.dc_x1,
                self.dc_y1,
            )
            while t < t_end:
                t_rel = t - t_start
                phase = two_pi_f * t_rel
                sin_val = _sin(phase)
                raw = 1.0 if sin_val >= 0.0 else -1.0
                rc_lp += lp_alpha * (raw - rc_lp)
                hp_y = rc_lp - dc_x1 + 0.995 * dc_y1
                dc_x1, dc_y1 = rc_lp, hp_y
                out = hp_y * amplitude
                if invert:
                    out = -out
                if apply_ramp and t_rel < ramp_dur:
                    out *= 0.5 * (1.0 - _cos(pi * (t_rel / ramp_dur)))
                append(out)
                t += dt
            self.rc_lp, self.dc_x1, self.dc_y1 = rc_lp, dc_x1, dc_y1

        elif kind == "ideal":
            while t < t_end:
                t_rel = t - t_start
                phase = two_pi_f * t_rel
                sin_val = _sin(phase)
                base = 1.0 if sin_val >= 0.0 else -1.0
                out = base * amplitude
                if invert:
                    out = -out
                append(out)
                t += dt

        else:
            while t < t_end:
                t_rel = t - t_start
                phase = two_pi_f * t_rel
                out = _sin(phase) * amplitude
                if invert:
                    out = -out
                append(out)
                t += dt

        self.current_time = t
        return samples

    def generate_tone(
        self, freq: float, duration_sec: float, ramp_in: bool = False
    ) -> List[float]:
        if duration_sec <= 0.0:
            return []
        actual_freq = freq * self.speed
        two_pi_f = 2.0 * math.pi * actual_freq
        apply_ramp = ramp_in and self._kind in ("tape", "shaped", "acoustic")
        return self._gen_wave(two_pi_f, duration_sec, apply_ramp)

    def generate_uart_data(self, data_bytes: bytes, baud: int) -> List[float]:
        if not data_bytes:
            return []
        samples = []
        actual_baud = baud * self.speed
        bit_dur = 1.0 / actual_baud
        f_mark = 2400.0 * self.speed
        f_space = 1200.0 * self.speed
        two_pi_mark = 2.0 * math.pi * f_mark
        two_pi_space = 2.0 * math.pi * f_space

        for b in data_bytes:
            bits = [0] + [(b >> i) & 1 for i in range(8)] + [1, 1]
            for bit in bits:
                two_pi_f = two_pi_mark if bit == 1 else two_pi_space
                samples.extend(self._gen_wave(two_pi_f, bit_dur, False))
        return samples


def convert_t88_to_wav(
    in_stream: BinaryIO,
    out_stream: BinaryIO,
    mode: str = "tape",
    sample_rate: int = 44100,
    channels: int = 1,
    stereo_mode: str = "dual",
    amplitude: float = 0.8,
    speed_factor: float = 1.0,
    invert_polarity: bool = False,
    baud_override: Optional[int] = None,
    chunk_frames: int = 4096,
    quiet: bool = False,
):
    reader = StreamingT88Reader(in_stream)
    writer = StreamingWavWriter(
        out_stream, sample_rate=sample_rate, channels=channels, stereo_mode=stereo_mode
    )
    synth = T88ToWavSynthesizer(
        sample_rate=sample_rate,
        mode=mode,
        amplitude=amplitude,
        speed_factor=speed_factor,
        invert_polarity=invert_polarity,
    )

    current_tick = 0
    sample_buffer: List[float] = []
    buf_pos = 0
    COMPACT_THRESHOLD = 1 << 16
    after_gap = True

    def flush_samples(force: bool = False):
        nonlocal sample_buffer, buf_pos
        n = len(sample_buffer)
        while (n - buf_pos) >= chunk_frames or (force and buf_pos < n):
            num_to_write = (n - buf_pos) if force else chunk_frames
            end = buf_pos + num_to_write
            writer.write_pcm_samples(sample_buffer[buf_pos:end])
            buf_pos = end
        if buf_pos == n:
            sample_buffer = []
            buf_pos = 0
        elif buf_pos >= COMPACT_THRESHOLD:
            sample_buffer = sample_buffer[buf_pos:]
            buf_pos = 0

    for tag_id, length, payload in reader.iter_blocks():
        if tag_id in (T88Tag.GAP, T88Tag.SPACE, T88Tag.MARK):
            if len(payload) >= 8:
                st, lt = struct.unpack("<II", payload[:8])
                if st > current_tick:
                    gap_ticks = st - current_tick
                    sample_buffer.extend(synth.generate_silence(gap_ticks / 4800.0))
                    current_tick = st
                    after_gap = True

                dur_sec = lt / 4800.0
                if tag_id == T88Tag.GAP:
                    sample_buffer.extend(synth.generate_silence(dur_sec))
                    after_gap = True
                elif tag_id == T88Tag.SPACE:
                    sample_buffer.extend(
                        synth.generate_tone(1200.0, dur_sec, ramp_in=after_gap)
                    )
                    after_gap = False
                elif tag_id == T88Tag.MARK:
                    sample_buffer.extend(
                        synth.generate_tone(2400.0, dur_sec, ramp_in=after_gap)
                    )
                    after_gap = False

                current_tick = st + lt
                flush_samples()

        elif tag_id == T88Tag.DATA:
            if len(payload) >= 12:
                dsh = DataSubHeader.unpack(payload[:12])
                st, lt, dlen, fmt = (
                    dsh.start_tick,
                    dsh.length_ticks,
                    dsh.data_len,
                    dsh.fmt_code,
                )
                pdata = payload[12 : 12 + dlen]

                if st > current_tick:
                    gap_ticks = st - current_tick
                    sample_buffer.extend(synth.generate_silence(gap_ticks / 4800.0))
                    current_tick = st
                    after_gap = True

                if baud_override in (600, 1200):
                    eff_baud = baud_override
                elif fmt == 0x00CC:
                    eff_baud = 600
                elif fmt == 0x01CC:
                    eff_baud = 1200
                elif dlen > 0 and lt > 0:
                    ticks_per_byte = lt / dlen
                    eff_baud = (
                        600
                        if abs(ticks_per_byte - 88) < abs(ticks_per_byte - 44)
                        else 1200
                    )
                else:
                    eff_baud = 1200

                sample_buffer.extend(synth.generate_uart_data(pdata, eff_baud))
                current_tick = st + lt
                after_gap = False
                flush_samples()

    flush_samples(force=True)
    writer.finalize()


def log_diag(msg: str):
    sys.stderr.write(f"[t882wav] {msg}\n")
    sys.stderr.flush()


def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(
        prog="dwimsy-t882wav",
        description="Stream PC-8001 / PC-8801 .t88 tape container image to standard WAV audio.",
        epilog="Note: --mode accepts tape, acoustic, shaped, ideal, cassette, motor, spinup, pc, square.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
    )
    parser.add_argument(
        "input", nargs="?", default="-", help="Input .t88 file or '-' for stdin"
    )
    parser.add_argument(
        "output", nargs="?", default="-", help="Output .wav file or '-' for stdout"
    )
    parser.add_argument(
        "--mode",
        "-m",
        "--wave",
        default="tape",
        choices=[
            "tape",
            "cassette",
            "acoustic",
            "motor",
            "spinup",
            "shaped",
            "pc",
            "ideal",
            "square",
        ],
        help="Synthesis mode",
    )
    parser.add_argument(
        "--sample-rate",
        "-r",
        type=int,
        default=44100,
        help="Audio sample rate (default: 44100)",
    )
    parser.add_argument(
        "--channels",
        "-c",
        type=int,
        choices=[1, 2],
        default=1,
        help="Channels: 1 (mono) or 2 (stereo)",
    )
    parser.add_argument(
        "--stereo-mode",
        default="dual",
        choices=["dual", "left", "right", "diff"],
        help="Stereo routing",
    )
    parser.add_argument(
        "--amplitude",
        "-a",
        "--volume",
        "-v",
        type=float,
        default=0.80,
        help="Peak amplitude 0.01..1.0",
    )
    parser.add_argument(
        "--baud",
        type=int,
        choices=[600, 1200],
        default=None,
        help="Baud override",
    )
    parser.add_argument(
        "--speed",
        "-s",
        type=float,
        default=1.0,
        help="Speed multiplier",
    )
    parser.add_argument("--invert", action="store_true", help="Invert polarity")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress progress")
    parser.add_argument(
        "-T",
        "--test",
        action="store_true",
        help="Run filter self-tests in-process and exit",
    )

    args = parser.parse_args(argv)
    if getattr(args, "test", False):
        from dwimsy.tests import run_tests

        rc = run_tests(["t882wav"])
        sys.exit(rc)
    if not args.input or args.input == "-":
        in_s = sys.stdin.buffer
    else:
        in_s = open(args.input, "rb")

    if not args.output or args.output == "-":
        out_s = sys.stdout.buffer
    else:
        out_s = open(args.output, "wb")

    try:
        convert_t88_to_wav(
            in_s,
            out_s,
            mode=args.mode,
            sample_rate=args.sample_rate,
            channels=args.channels,
            stereo_mode=args.stereo_mode,
            amplitude=args.amplitude,
            speed_factor=args.speed,
            invert_polarity=args.invert,
            baud_override=args.baud,
            quiet=args.quiet,
        )
    finally:
        if in_s is not sys.stdin.buffer:
            in_s.close()
        if out_s is not sys.stdout.buffer:
            out_s.close()


if __name__ == "__main__":
    main()
