#!/usr/bin/env python3

"""dwimsy.cli.main — central CLI entrypoint for dwimsy.

Exposes 'convert' and 'inspect' verbs for Phase 1.
"""

import argparse
import io
import os
import sys
from pathlib import Path

from dwimsy.cli.filters import t882wav as filter_t882wav
from dwimsy.cli.filters import wav2t88 as filter_wav2t88

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEPS_PC88_DIR = REPO_ROOT / "deps" / "pc88_tape_tools"
if str(DEPS_PC88_DIR) not in sys.path:
    sys.path.insert(0, str(DEPS_PC88_DIR))

try:
    import pc88_tape_tools
except ImportError:
    pc88_tape_tools = None


def run_convert(args):
    in_path = args.input
    out_path = args.output

    if in_path == "-":
        in_stream = sys.stdin.buffer
    else:
        in_stream = open(in_path, "rb")

    if out_path == "-":
        out_stream = sys.stdout.buffer
    else:
        out_stream = open(out_path, "wb")

    try:
        in_ext = "" if in_path == "-" else os.path.splitext(in_path)[1].lower()
        out_ext = "" if out_path == "-" else os.path.splitext(out_path)[1].lower()

        # Route by extension / target format
        if (in_ext == ".wav" or args.from_format == "wav") and (
            out_ext == ".t88" or args.to_format == "t88"
        ):
            supported = (args.baud,) if args.baud else (600, 1200)
            filter_wav2t88.process_stream(
                in_stream,
                out_stream,
                supported_bauds=supported,
                channel_mode=args.channel,
                confidence_threshold=args.confidence,
                quiet=args.quiet,
            )
        elif (in_ext == ".t88" or args.from_format == "t88") and (
            out_ext == ".wav" or args.to_format == "wav"
        ):
            filter_t882wav.convert_t88_to_wav(
                in_stream,
                out_stream,
                mode=args.mode,
                sample_rate=args.sample_rate,
                channels=args.channels,
                stereo_mode=args.stereo_mode,
                amplitude=args.amplitude,
                speed_factor=args.speed,
                baud_override=args.baud,
                quiet=args.quiet,
            )
        elif (in_ext == ".t88" or args.from_format == "t88") and (
            out_ext == ".cmt" or args.to_format == "cmt"
        ):
            if pc88_tape_tools is None:
                raise RuntimeError("pc88_tape_tools backend not available.")
            t88_obj = pc88_tape_tools.T88File.unpack(in_stream)
            out_stream.write(t88_obj.extract_cmt_payload())
        elif (in_ext == ".cmt" or args.from_format == "cmt") and (
            out_ext == ".t88" or args.to_format == "t88"
        ):
            if pc88_tape_tools is None:
                raise RuntimeError("pc88_tape_tools backend not available.")
            cmt_data = in_stream.read()
            baud = args.baud if args.baud else 1200
            t88_obj = pc88_tape_tools.T88File.from_cmt_data(cmt_data, baud=baud)
            out_stream.write(t88_obj.pack())
        else:
            # Fallback routing
            if in_ext == ".wav":
                filter_wav2t88.process_stream(in_stream, out_stream, quiet=args.quiet)
            else:
                filter_t882wav.convert_t88_to_wav(
                    in_stream, out_stream, quiet=args.quiet
                )
    finally:
        if in_stream is not sys.stdin.buffer:
            in_stream.close()
        if out_stream is not sys.stdout.buffer:
            out_stream.close()


def run_inspect(args):
    in_path = args.input
    if in_path == "-":
        in_stream = sys.stdin.buffer
    else:
        in_stream = open(in_path, "rb")

    try:
        head = in_stream.read(24)
        in_stream.seek(0)

        if head.startswith(b"RIFF"):
            from dwimsy.core.audio import StreamingWavReader

            reader = StreamingWavReader(in_stream)
            print(
                "======================================================================"
            )
            print(
                "                 DWIMSY CASSETTE AUDIO INSPECTOR                      "
            )
            print(
                "======================================================================"
            )
            print(f"Format     : RIFF/WAVE PCM ({reader.bits_per_sample}-bit)")
            print(f"Sample Rate: {reader.sample_rate} Hz")
            print(f"Channels   : {reader.channels}")
            print(
                "======================================================================"
            )
        elif pc88_tape_tools and (
            head.startswith(b"PC-8801 Tape Image")
            or head.startswith(b"PC-8001 Tape Image")
        ):
            report = pc88_tape_tools.analyze_tape(in_path, verbose=args.verbose)
            print(report)
        elif pc88_tape_tools:
            report = pc88_tape_tools.analyze_tape(in_path, verbose=args.verbose)
            print(report)
        else:
            print(f"Inspecting {in_path}: {len(head)} header bytes read.")
    finally:
        if in_stream is not sys.stdin.buffer:
            in_stream.close()


def main():
    parser = argparse.ArgumentParser(
        prog="dwimsy",
        description="dwimsy — retrocomputing media preservation, demodulation, and conversion.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    p_conv = subparsers.add_parser(
        "convert", help="Convert between media representations (WAV, T88, CMT)."
    )
    p_conv.add_argument("input", help="Input file or '-' for stdin")
    p_conv.add_argument("output", help="Output file or '-' for stdout")
    p_conv.add_argument(
        "--from-format", default=None, help="Explicit input format (wav, t88, cmt)"
    )
    p_conv.add_argument(
        "--to-format", default=None, help="Explicit output format (wav, t88, cmt)"
    )
    p_conv.add_argument(
        "--mode",
        default="tape",
        choices=["tape", "acoustic", "shaped", "ideal"],
        help="Synthesis mode",
    )
    p_conv.add_argument(
        "--baud",
        type=int,
        choices=[600, 1200],
        default=None,
        help="Baud rate override (600 or 1200)",
    )
    p_conv.add_argument(
        "--sample-rate",
        type=int,
        default=44100,
        help="Audio sample rate (default: 44100)",
    )
    p_conv.add_argument(
        "--channels",
        type=int,
        choices=[1, 2],
        default=1,
        help="Audio channels (default: 1)",
    )
    p_conv.add_argument(
        "--stereo-mode",
        default="dual",
        choices=["dual", "left", "right", "diff"],
        help="Stereo routing",
    )
    p_conv.add_argument(
        "--channel",
        default="auto",
        choices=["auto", "left", "right", "mix", "diff"],
        help="Input channel",
    )
    p_conv.add_argument(
        "--amplitude",
        type=float,
        default=0.80,
        help="Audio amplitude 0.01..1.0 (default: 0.80)",
    )
    p_conv.add_argument(
        "--speed", type=float, default=1.0, help="Speed multiplier (default: 1.0)"
    )
    p_conv.add_argument(
        "--confidence",
        type=float,
        default=0.75,
        help="Minimum byte confidence (default: 0.75)",
    )
    p_conv.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress progress output"
    )

    p_insp = subparsers.add_parser(
        "inspect", help="Inspect media container headers and structural contents."
    )
    p_insp.add_argument("input", help="Input file to inspect")
    p_insp.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose block structure"
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(0)

    args = parser.parse_args()
    if args.command == "convert":
        run_convert(args)
    elif args.command == "inspect":
        run_inspect(args)
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
