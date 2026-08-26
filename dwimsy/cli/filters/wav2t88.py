#!/usr/bin/env python3
"""dwimsy.cli.filters.wav2t88 - Streaming WAV to T88 demodulator filter.

Backed directly by dwimsy.core.pulse, dwimsy.core.fsk, dwimsy.core.audio,
and dwimsy.tape.t88.
"""

from __future__ import annotations

import sys
from pathlib import Path

for p in Path(__file__).resolve().parents:
    if (p / "dwimsy").is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
        break

from dwimsy.meta.integrity import version as get_version

import argparse
import io
import math
import os
import struct
from typing import BinaryIO, List, Optional, Tuple

from dwimsy.core.audio import StreamingWavReader
from dwimsy.core.fsk import ByteFramer, FSKClassifier
from dwimsy.core.pulse import PulseTimingRecognizer
from dwimsy.tape.t88 import (
    DataSubHeader,
    T88StreamWriter,
    T88Tag,
)


def log_diag(msg: str):
    sys.stderr.write(f"[wav2t88] {msg}\n")
    sys.stderr.flush()


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
    dt = 1.0 / fs

    candidate_order = (
        tuple(sorted(supported_bauds)) if len(supported_bauds) > 1 else supported_bauds
    )

    recognizer = PulseTimingRecognizer(sample_rate=fs)
    classifier = FSKClassifier(mark_freq=2400.0, space_freq=1200.0)
    framers = {
        b: ByteFramer(baud=b, confidence_threshold=confidence_threshold, sample_rate=fs)
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

    tape_time = 0.0

    while True:
        samples = reader.read_samples(1024)
        if not samples:
            break

        for s in samples:
            ev = recognizer.process_sample(s)
            tape_time += dt * classifier.speed_factor
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
                        dec = f_obj.feed(pulse, cur_tick=cur_tick)
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
                    dec = active_framer.feed(pulse, cur_tick=cur_tick)
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


def main(argv: Optional[List[str]] = None):
    effective_argv = sys.argv[1:] if argv is None else list(argv)
    for p in Path(__file__).resolve().parents:
        if (p / "dwimsy").is_dir():
            if str(p) in sys.path:
                sys.path.remove(str(p))
            sys.path.insert(0, str(p))
            break

    test_arg = None
    for a in effective_argv:
        if a in ("-T", "--test") or a.startswith("--test="):
            test_arg = a
            break
    if test_arg is not None:
        verbosity = 1
        for arg in effective_argv:
            if arg in ("-v", "--verbose"):
                verbosity = max(verbosity + 1, 2)
            elif (
                arg.startswith("-") and len(arg) > 1 and all(c == "v" for c in arg[1:])
            ):
                verbosity = max(verbosity + len(arg) - 1, 2)
        from dwimsy.tests import run_tests

        pattern = [test_arg.split("=", 1)[1]] if test_arg.startswith("--test=") else ["wav2t88"]
        rc = run_tests(pattern, verbose=verbosity)
        sys.exit(rc)

    if any(a == "--help-all" for a in effective_argv):
        effective_argv = ["-h" if a == "--help-all" else a for a in effective_argv]

    parser = argparse.ArgumentParser(
        prog="dwimsy-wav2t88",
        description="Stream PC-8001 / PC-8801 WAV audio to standard .t88 tape image.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
    )
    parser.add_argument(
        "input", nargs="?", default="-", help="Input WAV file or '-' for stdin"
    )
    parser.add_argument(
        "output", nargs="?", default="-", help="Output .t88 file or '-' for stdout"
    )
    parser.add_argument(
        "--baud",
        "-b",
        type=int,
        choices=[600, 1200],
        default=None,
        help="Forced baud rate",
    )
    parser.add_argument(
        "--channel",
        "-c",
        default="auto",
        choices=["auto", "left", "right", "mix", "diff"],
        help="Input channel",
    )
    parser.add_argument(
        "--bauds",
        default="600,1200",
        help="Candidate baud rates",
    )
    parser.add_argument(
        "--flavor",
        default="reconstructed",
        choices=[
            "verbatim",
            "reconstructed",
            "kinematic-infilled",
            "rom-authentic",
            "canonical",
        ],
        help="Timing flavor",
    )
    parser.add_argument(
        "--confidence",
        "-C",
        "--min-confidence",
        type=float,
        default=0.75,
        help="Minimum confidence threshold",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress progress output"
    )
    parser.add_argument(
        "-T",
        "--test",
        nargs="?",
        const=True,
        default=False,
        help="Run filter self-tests in-process and exit",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=1,
        help="Increase test runner verbosity when running self-tests",
    )
    parser.add_argument(
        "--help-all",
        action="store_true",
        help="Show full help documentation and exit",
    )

    args = parser.parse_args(effective_argv)

    if args.test is not False:
        from dwimsy.tests import run_tests
        pattern = [args.test] if isinstance(args.test, str) else ["wav2t88"]
        rc = run_tests(pattern, verbose=args.verbose)
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
        bauds = (
            (args.baud,)
            if args.baud
            else tuple(int(b.strip()) for b in args.bauds.split(",") if b.strip())
        )
        process_stream(
            in_s,
            out_s,
            supported_bauds=bauds,
            channel_mode=args.channel,
            confidence_threshold=args.confidence,
            flavor=args.flavor,
            quiet=args.quiet,
        )
    finally:
        if in_s is not sys.stdin.buffer:
            in_s.close()
        if out_s is not sys.stdout.buffer:
            out_s.close()

if __name__ == "__main__":
    main()
