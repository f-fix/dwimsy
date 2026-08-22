"""dwimsy.cli.filters.wav2t88 — streaming WAV to T88 demodulator filter.

Backed directly by dwimsy.core.pulse, dwimsy.core.fsk, and dwimsy.core.audio.
"""

import argparse
import io
import math
import os
import struct
import sys
from typing import BinaryIO, List, Optional, Tuple

from dwimsy.core.audio import StreamingWavReader
from dwimsy.core.fsk import ByteFramer, FSKClassifier
from dwimsy.core.pulse import PulseTimingRecognizer


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


class T88StreamWriter:
    def __init__(self, out_stream: BinaryIO):
        self.out = out_stream
        self.header_written = False

    def write_header(self):
        if not self.header_written:
            hdr = (
                b"PC-8801 Tape Image(T88)\x00"
                + struct.pack("<HHHH", 0x0001, 0x0002, 0x0100, 0x0000)[:6]
            )
            self.out.write(hdr)
            self.header_written = True
            self.out.flush()

    def _write_tag(self, tag_id: int, payload: bytes):
        self.write_header()
        self.out.write(struct.pack("<HH", tag_id, len(payload)) + payload)
        self.out.flush()

    def write_blank(self, start_tick: int, length_tick: int):
        if length_tick > 0:
            self._write_tag(
                T88Tag.GAP, struct.pack("<II", int(start_tick), int(length_tick))
            )

    def write_space(self, start_tick: int, length_tick: int):
        if length_tick > 0:
            self._write_tag(
                T88Tag.SPACE, struct.pack("<II", int(start_tick), int(length_tick))
            )

    def write_mark(self, start_tick: int, length_tick: int):
        if length_tick > 0:
            self._write_tag(
                T88Tag.MARK, struct.pack("<II", int(start_tick), int(length_tick))
            )

    def write_data(self, start_tick: int, baud: int, data_bytes: bytes):
        if not data_bytes:
            return
        fmt = 0x01CC if baud >= 1200 else 0x00CC
        ticks_per_byte = int(round(11.0 * 4800.0 / baud))
        offset = 0
        cur_tick = start_tick
        while offset < len(data_bytes):
            chunk = data_bytes[offset : offset + 32768]
            length_tick = len(chunk) * ticks_per_byte
            hdr = DataSubHeader(cur_tick, length_tick, len(chunk), fmt).pack()
            self._write_tag(T88Tag.DATA, hdr + chunk)
            offset += len(chunk)
            cur_tick += length_tick

    def write_end(self):
        self._write_tag(T88Tag.END, b"")


def process_stream(
    in_stream: BinaryIO,
    out_stream: BinaryIO,
    supported_bauds: Tuple[int, ...] = (600, 1200),
    channel_mode: str = "auto",
    confidence_threshold: float = 0.75,
    flavor: str = "reconstructed",
    quiet: bool = False,
):
    reader = StreamingWavReader(in_stream, channel_mode=channel_mode)
    fs = reader.sample_rate

    candidate_order = (
        tuple(sorted(supported_bauds)) if len(supported_bauds) > 1 else supported_bauds
    )

    recognizer = PulseTimingRecognizer(fs)
    classifier = FSKClassifier(mark_freq=2400.0, space_freq=1200.0)
    framers = {
        b: ByteFramer(b, confidence_threshold=confidence_threshold, sample_rate=fs)
        for b in candidate_order
    }
    active_framer: Optional[ByteFramer] = None
    writer = T88StreamWriter(out_stream)

    state = "BLANK"
    state_start_tick = 0
    mark_counter = 0
    space_counter = 0
    mark_first_tick = 0
    space_first_tick = 0
    last_mark_tick = 0
    last_space_tick = 0
    data_buffer: List[int] = []
    block_confidences: List[float] = []
    data_start_tick = 0
    session_locked_baud: Optional[int] = None
    candidate_buffers = {b: [] for b in candidate_order}

    while True:
        samples = reader.read_samples(1024)
        if not samples:
            break

        for s in samples:
            ev = recognizer.process_sample(s)
            tape_time = recognizer.current_time * classifier.speed_factor
            cur_tick = int(round(tape_time * 4800.0))

            if ev is not None:
                pulse = classifier.classify(ev)
                for f_obj in framers.values():
                    f_obj.update_speed(classifier.speed_factor)

                if active_framer is None:
                    active_candidates = (
                        (session_locked_baud,)
                        if session_locked_baud is not None
                        else candidate_order
                    )
                    confirmed_framer = None

                    for baud in active_candidates:
                        f_obj = framers[baud]
                        dec = f_obj.feed(pulse)
                        if dec is not None:
                            if dec.status == "OK":
                                candidate_buffers[baud] = [
                                    (dec.value, dec.start_tick, dec.confidence)
                                ]
                                confirmed_framer = f_obj
                                break
                            elif dec.status in ("LOW_CONFIDENCE", "FRAMING_ERROR"):
                                candidate_buffers[baud].clear()

                    if confirmed_framer is not None:
                        active_framer = confirmed_framer
                        active_framer.in_block = True
                        active_framer.leader_validated = True
                        chosen_baud = int(active_framer.nominal_baud)
                        session_locked_baud = chosen_baud
                        byte_val, byte_tick_start, byte_conf = candidate_buffers[
                            chosen_baud
                        ][0]

                        prev_len = byte_tick_start - state_start_tick
                        if prev_len > 0:
                            if state == "BLANK":
                                writer.write_blank(state_start_tick, prev_len)
                            elif state == "MARK":
                                writer.write_mark(state_start_tick, prev_len)
                            elif state == "SPACE":
                                writer.write_space(state_start_tick, prev_len)

                        state = "DATA"
                        data_start_tick = byte_tick_start
                        data_buffer = [byte_val]
                        block_confidences = [byte_conf]
                        for b in candidate_order:
                            candidate_buffers[b].clear()
                else:
                    dec = active_framer.feed(pulse)
                    if dec is not None and dec.status == "OK":
                        data_buffer.append(dec.value)
                        block_confidences.append(dec.confidence)

            if active_framer is not None:
                is_carrier_returned = active_framer.carrier_mark_time >= (
                    active_framer.bit_duration * 24.0
                )
                is_silence_gap = (cur_tick - active_framer.last_activity_tick) > int(
                    4800 * 0.15
                )

                if is_carrier_returned or is_silence_gap:
                    is_noise = (
                        data_buffer
                        and len(data_buffer) < 4
                        and is_silence_gap
                        and not is_carrier_returned
                    )
                    ticks_per_byte = int(
                        round(11.0 * 4800.0 / active_framer.nominal_baud)
                    )
                    data_end_tick = data_start_tick + len(data_buffer) * ticks_per_byte

                    if data_buffer and not is_noise:
                        writer.write_data(
                            data_start_tick,
                            int(active_framer.nominal_baud),
                            bytes(data_buffer),
                        )

                    data_buffer = []
                    block_confidences = []
                    state_start_tick = data_end_tick
                    state = "MARK" if is_carrier_returned else "BLANK"
                    if is_carrier_returned:
                        last_mark_tick = cur_tick
                    if is_silence_gap:
                        session_locked_baud = None

                    reuse_leader = (
                        is_carrier_returned
                        and not is_silence_gap
                        and session_locked_baud is not None
                    )
                    active_framer = None
                    for b, f_obj in framers.items():
                        f_obj.reset(
                            in_block=False, in_session=(session_locked_baud is not None)
                        )
                        if reuse_leader and b == session_locked_baud:
                            f_obj.leader_validated = True
                        candidate_buffers[b].clear()

            elif state == "BLANK":
                if ev is not None and pulse.symbol == "M":
                    cycle_ticks = int(
                        round(pulse.duration_sec * classifier.speed_factor * 4800.0)
                    )
                    if mark_counter == 0:
                        mark_first_tick = max(state_start_tick, cur_tick - cycle_ticks)
                    mark_counter += 1
                    space_counter = 0
                    if mark_counter > 40:
                        tag_len = mark_first_tick - state_start_tick
                        if tag_len > 0:
                            writer.write_blank(state_start_tick, tag_len)
                        state = "MARK"
                        state_start_tick = mark_first_tick
                        last_mark_tick = cur_tick
                        mark_counter = 0
                elif ev is not None and pulse.symbol == "S":
                    cycle_ticks = int(
                        round(pulse.duration_sec * classifier.speed_factor * 4800.0)
                    )
                    if space_counter == 0:
                        space_first_tick = max(state_start_tick, cur_tick - cycle_ticks)
                    space_counter += 1
                    mark_counter = 0
                    if space_counter > 20:
                        tag_len = space_first_tick - state_start_tick
                        if tag_len > 0:
                            writer.write_blank(state_start_tick, tag_len)
                        state = "SPACE"
                        state_start_tick = space_first_tick
                        last_space_tick = cur_tick
                        space_counter = 0
                elif ev is not None and pulse.symbol == "B":
                    mark_counter = 0
                    space_counter = 0

            elif state == "MARK":
                if ev is not None and pulse.symbol == "M":
                    last_mark_tick = cur_tick
                    space_counter = 0
                elif ev is not None and pulse.symbol == "S":
                    cycle_ticks = int(
                        round(pulse.duration_sec * classifier.speed_factor * 4800.0)
                    )
                    if space_counter == 0:
                        space_first_tick = cur_tick - cycle_ticks
                    space_counter += 1
                    if space_counter > 20:
                        tag_len = space_first_tick - state_start_tick
                        if tag_len > 0:
                            writer.write_mark(state_start_tick, tag_len)
                            state_start_tick = space_first_tick
                        state = "SPACE"
                        last_space_tick = cur_tick
                        space_counter = 0
                if (cur_tick - last_mark_tick) > int(4800 * 0.050) and state == "MARK":
                    tag_len = last_mark_tick - state_start_tick
                    if tag_len > 0:
                        writer.write_mark(state_start_tick, tag_len)
                        state_start_tick = last_mark_tick
                    state = "BLANK"
                    session_locked_baud = None
                    for f_obj in framers.values():
                        f_obj.in_session = False
                    mark_counter = 0
                    space_counter = 0

            elif state == "SPACE":
                if ev is not None and pulse.symbol == "S":
                    last_space_tick = cur_tick
                    mark_counter = 0
                elif ev is not None and pulse.symbol == "M":
                    cycle_ticks = int(
                        round(pulse.duration_sec * classifier.speed_factor * 4800.0)
                    )
                    if mark_counter == 0:
                        mark_first_tick = cur_tick - cycle_ticks
                    mark_counter += 1
                    if mark_counter > 40:
                        tag_len = mark_first_tick - state_start_tick
                        if tag_len > 0:
                            writer.write_space(state_start_tick, tag_len)
                            state_start_tick = mark_first_tick
                        state = "MARK"
                        last_mark_tick = cur_tick
                        mark_counter = 0
                if (cur_tick - last_space_tick) > int(
                    4800 * 0.050
                ) and state == "SPACE":
                    tag_len = last_space_tick - state_start_tick
                    if tag_len > 0:
                        writer.write_space(state_start_tick, tag_len)
                        state_start_tick = last_space_tick
                    state = "BLANK"
                    mark_counter = 0
                    space_counter = 0

    cur_tick = int(round(recognizer.current_time * classifier.speed_factor * 4800.0))
    if state == "DATA" and data_buffer and active_framer is not None:
        writer.write_data(
            data_start_tick, int(active_framer.nominal_baud), bytes(data_buffer)
        )
    elif state == "BLANK":
        writer.write_blank(state_start_tick, cur_tick - state_start_tick)
    elif state == "MARK":
        writer.write_mark(state_start_tick, cur_tick - state_start_tick)
    elif state == "SPACE":
        writer.write_space(state_start_tick, cur_tick - state_start_tick)

    writer.write_end()
