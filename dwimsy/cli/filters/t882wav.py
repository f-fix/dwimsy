"""dwimsy.cli.filters.t882wav — streaming T88 to WAV audio synthesizer filter.

Backed directly by dwimsy.core.audio (StreamingWavWriter).
"""

import argparse
import io
import math
import os
import struct
import sys
from typing import BinaryIO, Generator, List, Optional, Tuple

from dwimsy.core.audio import StreamingWavWriter


class T88Tag:
    END: int = 0x0000
    VERSION: int = 0x0001
    COMMENT: int = 0x0010
    GAP: int = 0x0100
    DATA: int = 0x0101
    SPACE: int = 0x0102
    MARK: int = 0x0103


class DataSubHeader:
    STRUCT_FORMAT: str = "<IIHH"
    SIZE: int = 12

    def __init__(
        self,
        start_tick: int = 0,
        length_ticks: int = 0,
        data_len: int = 0,
        fmt_code: int = 0x01CC,
    ):
        self.start_tick = int(start_tick)
        self.length_ticks = int(length_ticks)
        self.data_len = int(data_len)
        self.fmt_code = int(fmt_code)

    def pack(self) -> bytes:
        return struct.pack(
            self.STRUCT_FORMAT,
            self.start_tick,
            self.length_ticks,
            self.data_len,
            self.fmt_code,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "DataSubHeader":
        st, lt, dlen, fmt = struct.unpack(cls.STRUCT_FORMAT, data[:12])
        return cls(st, lt, dlen, fmt)


T88_HEADER_MAGICS: Tuple[bytes, ...] = (
    b"PC-8801 Tape Image(T88)\x00",
    b"PC-8001 Tape Image(T88)\x00",
    b"PC-8801 ",
    b"T88-FILE",
    b"PC-8001 ",
)


class StreamingT88Reader:
    def __init__(self, stream: BinaryIO):
        self.stream = stream
        self.header_bytes = b""
        self._parse_header()

    def _read_exact(self, count: int) -> bytes:
        buf = bytearray()
        while len(buf) < count:
            chunk = self.stream.read(count - len(buf))
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    def _parse_header(self):
        hdr = self._read_exact(24)
        if len(hdr) < 24:
            raise ValueError(
                "Input stream is too short to be a valid T88 container (<24 bytes)."
            )
        valid = any(hdr.startswith(m) or hdr[: len(m)] == m for m in T88_HEADER_MAGICS)
        if not valid and not (hdr.startswith(b"PC-") or hdr.startswith(b"T88")):
            raise ValueError(f"Invalid T88 magic signature: got {hdr!r}.")
        self.header_bytes = hdr

    def iter_blocks(self) -> Generator[Tuple[int, int, bytes], None, None]:
        while True:
            tag_hdr = self._read_exact(4)
            if len(tag_hdr) < 4:
                break
            tag_id, length = struct.unpack("<HH", tag_hdr)
            payload = self._read_exact(length) if length > 0 else b""
            if len(payload) < length:
                break
            yield (tag_id, length, payload)
            if tag_id == T88Tag.END:
                break


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
