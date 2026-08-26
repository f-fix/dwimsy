#!/usr/bin/env python3
"""dwimsy.cli.__main__ - Central CLI entrypoint for dwimsy.

Exposes the primary media verbs plus maintainer and roadmap placeholder commands.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path
from typing import BinaryIO, List, Optional, Tuple

for p in Path(__file__).resolve().parents:
    if (p / "dwimsy").is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
        break

from dwimsy.cli.filters import t882wav as filter_t882wav
from dwimsy.cli.filters import wav2t88 as filter_wav2t88
from dwimsy.tape.t88 import T88File, split_t88_file, join_t88_files
from dwimsy.protocols.pc88 import (
    CMTFile,
    convert_t88_to_cmt,
    convert_cmt_to_t88,
    split_cmt_file,
    join_cmt_files,
    analyze_tape,
)
from dwimsy.meta.integrity import version as get_version

class _LazyVersionAction(argparse.Action):
    """Only evaluates version function if -V or --version is present in CLI arguments."""

    def __init__(
        self,
        option_strings,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help="show program's version number and exit",
        version_fn=None,
    ):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help,
        )
        self.version_fn = version_fn

    def __call__(self, parser, namespace, values, option_string=None):
        fn = self.version_fn or get_version
        parser._print_message(f"{parser.prog} {fn()}\n", sys.stdout)
        parser.exit()
from dwimsy.meta.bundle import run_meta_bundle, run_meta_fetch_deps
from dwimsy.meta import integrity


def inspect_audio(
    in_stream: io.BytesIO | BinaryIO, channel_mode: str = "auto", out_stream=sys.stdout
):
    """Deep acoustic inspection of cassette audio recordings (matching wav2t88 --inspect)."""
    from dwimsy.core.audio import StreamingWavReader
    from dwimsy.core.pulse import PulseTimingRecognizer

    reader = StreamingWavReader(in_stream, channel_mode=channel_mode)
    fs = reader.sample_rate
    demod = PulseTimingRecognizer(fs)

    def print_out(msg: str):
        print(msg, file=out_stream)

    print_out("======================================================================")
    print_out("               PC-8001 / PC-8801 TAPE AUDIO INSPECTOR                 ")
    print_out("======================================================================")
    print_out(
        f"Source Format : {reader.sample_rate} Hz, {reader.bits_per_sample}-bit, {reader.channels} channel(s)"
    )
    print_out(f"Channel Mode  : {channel_mode.upper()}")
    print_out("Scanning tape audio signal...")

    total_samples = 0
    mark_cycles = 0
    space_cycles = 0
    speed_samples: list[float] = []
    mark_dur_hist: list[float] = []
    measured_f_mark = 2400.0

    while True:
        samples = reader.read_samples(2048)
        if not samples:
            break
        total_samples += len(samples)
        for s in samples:
            ev = demod.process_sample(s)
            if ev and ev.kind == "cycle":
                nominal_mark_period = 1.0 / measured_f_mark
                boundary_period = nominal_mark_period * 1.414

                if ev.envelope < max(
                    ev.peak_carrier * 0.22, ev.noise_floor * 2.0, 0.0005
                ):
                    mark_dur_hist.clear()
                elif ev.period_sec < boundary_period:
                    mark_cycles += 1
                    mark_dur_hist.append(ev.period_sec)
                    if len(mark_dur_hist) > 80:
                        mark_dur_hist.pop(0)
                    if len(mark_dur_hist) >= 20:
                        med_mark = sorted(mark_dur_hist)[len(mark_dur_hist) // 2]
                        if 0.00032 <= med_mark <= 0.00052:
                            measured_f_mark = 0.96 * measured_f_mark + 0.04 * (
                                1.0 / med_mark
                            )
                            speed_samples.append(measured_f_mark)
                elif ev.period_sec <= (1.0 / (1200.0 * 0.75)):
                    space_cycles += 1
                    mark_dur_hist.clear()
                else:
                    mark_dur_hist.clear()

    dur_sec = total_samples / fs
    m = int(dur_sec // 60)
    s = dur_sec % 60

    print_out("----------------------------------------------------------------------")
    print_out(f"Total Duration       : {m:02d}:{s:06.3f} ({total_samples} samples)")
    if reader.channels > 1:
        print_out(f"Left Channel Energy  : {reader.l_energy:.1f}")
        print_out(f"Right Channel Energy : {reader.r_energy:.1f}")
        if reader.l_energy > reader.r_energy * 2.0:
            print_out(
                "Recommendation       : Data is predominantly on LEFT channel. Use '--channel left'."
            )
        elif reader.r_energy > reader.l_energy * 2.0:
            print_out(
                "Recommendation       : Data is predominantly on RIGHT channel. Use '--channel right'."
            )

    print_out(f"2400 Hz Mark Cycles  : {mark_cycles}")
    print_out(f"1200 Hz Space Cycles : {space_cycles}")

    if speed_samples:
        avg_f_mark = sum(speed_samples) / len(speed_samples)
        speed_offset_pct = (avg_f_mark / 2400.0 - 1.0) * 100.0
        print_out(
            f"Avg Carrier Freq     : {avg_f_mark:.1f} Hz (Deck Motor Speed: {speed_offset_pct:+.2f}%)"
        )
    else:
        print_out("Carrier Signal       : WARNING: No 2400 Hz Mark tone detected.")

    print_out("======================================================================")


def safe_page(text: str, out_stream=None) -> None:
    """Output text using terminal pager if stdout is a TTY, falling back cleanly to direct write."""
    if out_stream is None:
        out_stream = sys.stdout

    is_tty = False
    try:
        is_tty = hasattr(out_stream, "isatty") and out_stream.isatty()
    except (AttributeError, io.UnsupportedOperation, OSError):
        is_tty = False

    if is_tty:
        try:
            import pydoc

            pydoc.pager(text)
            return
        except Exception:
            pass

    out_stream.write(text)
    if not text.endswith("\n"):
        out_stream.write("\n")
    out_stream.flush()


def format_all_help(parser: argparse.ArgumentParser) -> str:
    """Recursively collect help documentation across all subcommands and nested namespaces."""
    out = io.StringIO()
    parser.print_help(out)
    out.write("\n\n" + "=" * 80 + "\n")
    out.write("DETAILED SUBCOMMAND HELP\n")
    out.write("=" * 80 + "\n")

    def _collect_subparsers(p, prefix=""):
        for action in p._actions:
            if isinstance(action, argparse._SubParsersAction):
                for choice, subparser in action.choices.items():
                    name = f"{prefix} {choice}".strip() if prefix else choice
                    out.write(f"\n--- Command: {name} ---\n")
                    sub_out = io.StringIO()
                    subparser.print_help(sub_out)
                    out.write(sub_out.getvalue().strip() + "\n")
                    _collect_subparsers(subparser, prefix=name)

    _collect_subparsers(parser)
    return out.getvalue()


def get_doc_asset_text(filename: str) -> str:
    """Return documentation text from repo disk file or embedded in-memory bundle asset."""
    repo_root = integrity.find_repo_root()
    disk_file = repo_root / filename
    if disk_file.is_file():
        try:
            return disk_file.read_text(encoding="utf-8")
        except OSError:
            pass
    try:
        from dwimsy.meta import unbundle

        return unbundle.get_asset_text(filename)
    except Exception:
        raise FileNotFoundError(
            f"Documentation asset '{filename}' could not be located on disk or in bundle payload."
        )


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

        if (in_ext == ".wav" or args.from_format == "wav") and (
            out_ext == ".t88" or args.to_format == "t88"
        ):
            if args.baud:
                supported = (args.baud,)
            elif getattr(args, "bauds", None):
                supported = tuple(
                    int(b.strip()) for b in args.bauds.split(",") if b.strip()
                )
            else:
                supported = (600, 1200)

            filter_wav2t88.process_stream(
                in_stream,
                out_stream,
                supported_bauds=supported,
                channel_mode=args.channel,
                confidence_threshold=args.confidence,
                flavor=getattr(args, "flavor", "reconstructed"),
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
                invert_polarity=getattr(args, "invert", False),
                baud_override=args.baud,
                quiet=args.quiet,
            )
        elif (in_ext == ".t88" or args.from_format == "t88") and (
            out_ext == ".cmt" or args.to_format == "cmt"
        ):
            t88_obj = T88File.unpack(in_stream)
            out_stream.write(t88_obj.extract_cmt_payload())
        elif (in_ext == ".cmt" or args.from_format == "cmt") and (
            out_ext == ".t88" or args.to_format == "t88"
        ):
            cmt_data = in_stream.read()
            baud = args.baud if args.baud else 1200
            t88_obj = T88File.from_cmt_data(cmt_data, baud=baud)
            out_stream.write(t88_obj.pack())
        elif (in_ext == ".wav" or args.from_format == "wav") and (
            out_ext == ".cmt" or args.to_format == "cmt"
        ):
            t88_buf = io.BytesIO()
            supported = (args.baud,) if args.baud else (600, 1200)
            filter_wav2t88.process_stream(
                in_stream,
                t88_buf,
                supported_bauds=supported,
                channel_mode=args.channel,
                confidence_threshold=args.confidence,
                flavor=getattr(args, "flavor", "reconstructed"),
                quiet=args.quiet,
            )
            t88_obj = T88File.unpack(io.BytesIO(t88_buf.getvalue()))
            out_stream.write(t88_obj.extract_cmt_payload())
        elif (in_ext == ".cmt" or args.from_format == "cmt") and (
            out_ext == ".wav" or args.to_format == "wav"
        ):
            cmt_data = in_stream.read()
            baud = args.baud if args.baud else 1200
            t88_obj = T88File.from_cmt_data(cmt_data, baud=baud)
            t88_buf = io.BytesIO(t88_obj.pack())
            filter_t882wav.convert_t88_to_wav(
                t88_buf,
                out_stream,
                mode=args.mode,
                sample_rate=args.sample_rate,
                channels=args.channels,
                stereo_mode=args.stereo_mode,
                amplitude=args.amplitude,
                speed_factor=args.speed,
                invert_polarity=getattr(args, "invert", False),
                baud_override=args.baud,
                quiet=args.quiet,
            )
        else:
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
    channel_mode = getattr(args, "channel", "auto")

    if in_path == "-":
        in_stream = sys.stdin.buffer
    else:
        in_stream = open(in_path, "rb")

    try:
        head = in_stream.read(24)
        in_stream.seek(0)

        if head.startswith(b"RIFF"):
            inspect_audio(in_stream, channel_mode=channel_mode, out_stream=sys.stdout)
        else:
            if in_path == "-":
                report = analyze_tape(in_stream, verbose=args.verbose)
            else:
                report = analyze_tape(in_path, verbose=args.verbose)
            print(report)
    finally:
        if in_stream is not sys.stdin.buffer:
            in_stream.close()


def run_split(args):
    fmt = (args.format or "cmt").lower()
    if fmt in ("t88", ".t88"):
        summary = split_t88_file(
            args.input,
            output_dir=args.output_dir,
            comment=args.comment,
            baud=args.baud,
        )
    else:
        summary = split_cmt_file(args.input, output_dir=args.output_dir)

    print(f"\n[SUCCESS] Split '{args.input}' into {len(summary)} file(s):\n")
    print(
        f"{'#':<3} | {'Filename':<12} | {'File Format / Type':<32} | {'Size (Bytes)':<12} | Saved Path"
    )
    print("-" * 90)
    for idx, (fname, ftype, size, path) in enumerate(summary, start=1):
        print(f"{idx:<3} | {fname:<12} | {ftype:<32} | {size:<12} | {path}")
    print("-" * 90)


def _parse_scoped_join_inputs(raw_argv: List[str]) -> List[Tuple[str, Optional[int]]]:
    """Parses positional SoX-style scoped options before input paths (e.g. -b 1200 f1 -b 600 f2)."""
    parsed: List[Tuple[str, Optional[int]]] = []
    current_baud: Optional[int] = None
    i = 0
    while i < len(raw_argv):
        arg = raw_argv[i]
        if arg in ("-b", "--baud") and i + 1 < len(raw_argv):
            try:
                current_baud = int(raw_argv[i + 1])
                i += 2
                continue
            except ValueError:
                pass
        parsed.append((arg, current_baud))
        current_baud = None
        i += 1
    return parsed


def run_join(args, raw_inputs: Optional[List[str]] = None):
    out_ext = os.path.splitext(args.output)[1].lower()
    fmt = (
        args.format.lower() if args.format else ("t88" if out_ext == ".t88" else "cmt")
    )

    if raw_inputs:
        scoped_items = _parse_scoped_join_inputs(raw_inputs)
    else:
        scoped_items = [(p, None) for p in args.inputs]

    if fmt in ("t88", ".t88"):
        out_file = join_t88_files(
            scoped_items,
            args.output,
            comment=args.comment,
            baud=args.baud,
            cmt_baud=args.cmt_baud,
            bauds=getattr(args, "bauds", None),
        )
    else:
        input_paths_only = [item[0] for item in scoped_items]
        out_file = join_cmt_files(input_paths_only, args.output)

    print(f"[SUCCESS] Merged {len(scoped_items)} file(s) -> {out_file}")


def main(argv: Optional[List[str]] = None):
    effective_argv = sys.argv[1:] if argv is None else list(argv)
    if effective_argv and effective_argv[0] == "dwimsy":
        effective_argv = effective_argv[1:]

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
        cmd = None
        verbosity = 1
        for arg in effective_argv:
            if arg in (
                "convert",
                "inspect",
                "split",
                "join",
                "meta",
                "t882wav",
                "wav2t88",
                "audio",
                "pulse",
                "fsk",
                "tape",
                "protocols",
                "integrity",
                "bundle",
                "lint",
                "readme",
                "license",
                "changelog",
                "tests",
            ):
                cmd = arg
            elif arg in ("-v", "--verbose"):
                verbosity = max(verbosity + 1, 2)
            elif (
                arg.startswith("-") and len(arg) > 1 and all(c == "v" for c in arg[1:])
            ):
                verbosity = max(verbosity + len(arg) - 1, 2)
        from dwimsy.tests import run_tests

        if test_arg.startswith("--test="):
            pattern = [test_arg.split("=", 1)[1]]
        else:
            pattern = [cmd] if cmd else None
        rc = run_tests(pattern, verbose=verbosity)
        return rc

    parser = argparse.ArgumentParser(
        prog="dwimsy",
        description="dwimsy - retrocomputing media preservation, demodulation, and conversion.",
        epilog="Project Homepage: https://github.com/f-fix/dwimsy\nTip: Run 'dwimsy <command> --help' or 'dwimsy --help-all' to view detailed options for all commands.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-V",
        "--version",
        action=_LazyVersionAction,
        version_fn=get_version,
    )
    parser.add_argument(
        "-T",
        "--test",
        nargs="?",
        const=True,
        default=False,
        help="Run unit tests and self-test assertions in-process",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=1,
        help="Increase test or command verbosity",
    )
    parser.add_argument(
        "--help-all",
        action="store_true",
        help="Show full detailed help for all subcommands at once and exit",
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
    p_conv.add_argument(
        "--baud",
        "-b",
        type=int,
        choices=[600, 1200],
        default=None,
        help="Baud rate override (600 or 1200)",
    )
    p_conv.add_argument(
        "--bauds",
        default="600,1200",
        help="Comma-separated candidate baud rates for autodetect mode (default: 600,1200)",
    )
    p_conv.add_argument(
        "--flavor",
        default="reconstructed",
        choices=[
            "verbatim",
            "reconstructed",
            "kinematic-infilled",
            "rom-authentic",
            "canonical",
        ],
        help="Demodulation timing flavor (default: reconstructed)",
    )
    p_conv.add_argument(
        "--sample-rate",
        "-r",
        type=int,
        default=44100,
        help="Audio sample rate (default: 44100)",
    )
    p_conv.add_argument(
        "--channels",
        "-c",
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
        "-a",
        "--volume",
        type=float,
        default=0.80,
        help="Audio amplitude 0.01..1.0 (default: 0.80)",
    )
    p_conv.add_argument(
        "--speed",
        "-s",
        type=float,
        default=1.0,
        help="Speed multiplier (default: 1.0)",
    )
    p_conv.add_argument(
        "--invert", action="store_true", help="Invert audio polarity"
    )
    p_conv.add_argument(
        "--confidence",
        "-C",
        "--min-confidence",
        type=float,
        default=0.75,
        help="Minimum byte confidence (default: 0.75)",
    )
    p_conv.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress progress output"
    )
    p_conv.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    p_inspect = subparsers.add_parser(
        "inspect",
        help="Inspect media container headers and structural contents.",
    )
    p_inspect.add_argument("input", help="Input file or '-' to inspect")
    p_inspect.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose block structure"
    )
    p_inspect.add_argument(
        "-c",
        "--channel",
        default="auto",
        choices=["auto", "left", "right", "mix", "diff"],
        help="Audio channel to inspect (default: auto)",
    )
    p_inspect.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    p_split = subparsers.add_parser(
        "split",
        help="Split multi-file tape images into individual program files.",
    )
    p_split.add_argument("input", help="Input .cmt or .t88 tape container image")
    p_split.add_argument(
        "-o",
        "--output-dir",
        default=".",
        help="Destination directory (default: current directory)",
    )
    p_split.add_argument(
        "-f",
        "--format",
        default=None,
        help="Output split format override (cmt or t88)",
    )
    p_split.add_argument(
        "-c",
        "--comment",
        default="PC-8801 Tape Split",
        help="T88 container comment (default: 'PC-8801 Tape Split')",
    )
    p_split.add_argument(
        "-b",
        "--baud",
        type=int,
        choices=[600, 1200],
        default=None,
        help="Forced baud rate for T88 splitting",
    )
    p_split.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    p_join = subparsers.add_parser(
        "join",
        help="Join multiple files into a single .cmt or .t88 tape image.",
    )
    p_join.add_argument(
        "output",
        help="Output merged tape image (.cmt or .t88)",
    )
    p_join.add_argument(
        "inputs",
        nargs="+",
        help="Input files to merge sequentially",
    )
    p_join.add_argument(
        "-f",
        "--format",
        default=None,
        help="Output container format (cmt or t88)",
    )
    p_join.add_argument(
        "-c",
        "--comment",
        default="PC-8801 Tape Merge",
        help="T88 container comment (default: 'PC-8801 Tape Merge')",
    )
    p_join.add_argument(
        "-b",
        "--baud",
        type=int,
        choices=[600, 1200],
        default=None,
        help="Forced global baud rate for T88 container synthesis",
    )
    p_join.add_argument(
        "--cmt-baud",
        type=int,
        choices=[600, 1200],
        default=None,
        help="Explicit baud rate override for raw CMT inputs",
    )
    p_join.add_argument(
        "--bauds",
        default="600,1200",
        help="Comma-separated candidate baud rates for autodetect mode (default: 600,1200)",
    )
    p_join.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    # t882wav
    p_t882wav = subparsers.add_parser(
        "t882wav",
        help="Synthesize PCM WAV audio from a T88 cassette image.",
    )
    p_t882wav.add_argument("input", nargs="?", default="-", help="Input .t88 file or '-' for stdin")
    p_t882wav.add_argument("output", nargs="?", default="-", help="Output .wav file or '-' for stdout")
    p_t882wav.add_argument("--mode", "-m", "--wave", default="tape", choices=["tape", "cassette", "acoustic", "motor", "spinup", "shaped", "pc", "ideal", "square"], help="Synthesis mode")
    p_t882wav.add_argument("--sample-rate", "-r", type=int, default=44100, help="Audio sample rate (default: 44100)")
    p_t882wav.add_argument("--channels", "-c", type=int, choices=[1, 2], default=1, help="Channels: 1 (mono) or 2 (stereo)")
    p_t882wav.add_argument("--stereo-mode", default="dual", choices=["dual", "left", "right", "diff"], help="Stereo routing")
    p_t882wav.add_argument("--amplitude", "-a", "--volume", type=float, default=0.80, help="Waveform amplitude (0.01 to 1.0, default: 0.80)")
    p_t882wav.add_argument("--speed", "-s", type=float, default=1.0, help="Speed multiplier factor (default: 1.0)")
    p_t882wav.add_argument("--invert", action="store_true", help="Invert audio polarity (default: False)")
    p_t882wav.add_argument("--baud", "-b", type=int, choices=[600, 1200], default=None, help="Baud rate override (default: auto)")
    p_t882wav.add_argument("-q", "--quiet", action="store_true", help="Quiet mode: suppress progress output")
    p_t882wav.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    # wav2t88
    p_wav2t88 = subparsers.add_parser(
        "wav2t88",
        help="Demodulate PCM WAV audio into a T88 cassette image.",
    )
    p_wav2t88.add_argument("input", nargs="?", default="-", help="Input WAV file or '-' for stdin")
    p_wav2t88.add_argument("output", nargs="?", default="-", help="Output .t88 file or '-' for stdout")
    p_wav2t88.add_argument("--baud", "-b", type=int, choices=[600, 1200], default=None, help="Forced baud rate")
    p_wav2t88.add_argument("--channel", "-c", default="auto", choices=["auto", "left", "right", "mix", "diff"], help="Input channel")
    p_wav2t88.add_argument("--bauds", default="600,1200", help="Candidate baud rates")
    p_wav2t88.add_argument("--flavor", default="reconstructed", choices=["verbatim", "reconstructed", "kinematic-infilled", "rom-authentic", "canonical"], help="Timing flavor")
    p_wav2t88.add_argument("--confidence", "-C", "--min-confidence", type=float, default=0.75, help="Minimum confidence threshold")
    p_wav2t88.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output")
    p_wav2t88.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    # tests
    p_tests = subparsers.add_parser(
        "tests",
        help="Run the dwimsy unit test suite in-process.",
    )
    p_tests.add_argument("patterns", nargs="*", default=None, help="Optional test patterns or keywords")
    p_tests.add_argument("-v", "--verbose", action="count", default=1, help="Increase test runner verbosity")
    p_tests.add_argument("-l", "--list", action="store_true", help="List discoverable unit test IDs without running them")
    p_tests.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    # readme
    p_readme = subparsers.add_parser("readme", help="Output project README documentation.")
    p_readme.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    # license
    p_license = subparsers.add_parser("license", help="Output project LICENSE terms.")
    p_license.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    # changelog
    p_changelog = subparsers.add_parser("changelog", help="Output project revision history from CHANGELOG.md.")
    p_changelog.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    # help
    p_help = subparsers.add_parser("help", help="Interactive technical manual viewer.")
    p_help.add_argument("topic", nargs="?", default=None, help="Subcommand or topic name to inspect")
    p_help.add_argument("--help-all", action="store_true", help="Show full detailed help for all subcommands")

    # meta
    from dwimsy.meta.__main__ import build_parser as build_meta_parser
    p_meta = subparsers.add_parser(
        "meta",
        help="Maintainer tools and repository lifecycle management.",
    )
    meta_subparsers = p_meta.add_subparsers(dest="meta_command", metavar="<meta-command>")
    p_meta_bundle = meta_subparsers.add_parser("bundle", help="Generate a self-extracting single-file Python unpacker bundle of dwimsy.")
    p_meta_bundle.add_argument("-o", "--output", default=None, help="Output script path or '-' for stdout")
    p_meta_bundle.add_argument("-t", "--tag", default=None, help="Optional short descriptive tag/label")
    p_meta_bundle.add_argument("--baseline", action="store_true", help="Directly emit installed baseline bundle")
    p_meta_bundle.add_argument("--with-deps", action="store_true", help="Include legacy submodule scaffolding from deps/")
    p_meta_bundle.add_argument("--status", action="store_true", help="List uncommitted/modified and untracked files")
    p_meta_bundle.add_argument("--diff", action="store_true", help="Display working tree diff before bundling")
    p_meta_bundle.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity")
    p_meta_bundle.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    p_meta_unbundle = meta_subparsers.add_parser("unbundle", help="Extract dwimsy standalone bundle to a target directory.")
    p_meta_unbundle.add_argument("target_directory", nargs="?", default=None, help="Target directory for extraction")
    p_meta_unbundle.add_argument("--deps", "-d", action="store_true", help="Also extract reference dependencies into deps/")
    p_meta_unbundle.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    p_meta_diff = meta_subparsers.add_parser("diff", help="Show differences between the working tree and embedded baseline.")
    p_meta_diff.add_argument("-r", "--root", default=None, help="Target repository root")
    p_meta_diff.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    p_meta_integrity = meta_subparsers.add_parser("integrity", help="Verify the canonical portable-project integrity hash.")
    p_meta_integrity.add_argument("--baseline", action="store_true", help="Inspect embedded baseline")
    p_meta_integrity.add_argument("-q", "--quiet", action="store_true", help="Suppress output on clean status")
    p_meta_integrity.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    p_meta_fetch = meta_subparsers.add_parser("fetch-deps", help="Fetch or materialize legacy reference submodules into deps/.")
    p_meta_fetch.add_argument("--baseline", action="store_true", help="Force extraction from bundled baseline")
    p_meta_fetch.add_argument("-f", "--force", action="store_true", help="Overwrite existing deps/ files")
    p_meta_fetch.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    p_meta_bump = meta_subparsers.add_parser("version-bump", help="Advance revision, record changelog, and synchronize bundle baseline.")
    p_meta_bump.add_argument("target_version", nargs="?", default=None, help="Explicit new version string")
    p_meta_bump.add_argument("--patch", action="store_true", help="Increment patch component")
    p_meta_bump.add_argument("--minor", action="store_true", help="Increment minor component")
    p_meta_bump.add_argument("--major", action="store_true", help="Increment major component")
    p_meta_bump.add_argument("--rev", action="store_true", help="Increment build/revision digit")
    p_meta_bump.add_argument("--release", action="store_true", help="Remove -dev suffix")
    p_meta_bump.add_argument("--dev", action="store_true", help="Ensure -dev suffix")
    p_meta_bump.add_argument("-m", "--message", default=None, help="Changelog description message")
    p_meta_bump.add_argument("--no-bundle", action="store_true", help="Skip bundle baseline synchronization")
    p_meta_bump.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    p_meta_lint = meta_subparsers.add_parser("lint", help="Verify repository headers, docstrings, markdown syntax, and dash policy.")
    p_meta_lint.add_argument("-q", "--quiet", action="store_true", help="Suppress output on success")
    p_meta_lint.add_argument("--help-all", action="store_true", help="Show full help documentation and exit")

    meta_subparsers.add_parser("bundle-fixtures", help="[TODO / Milestone 1.6] Package private test fixtures.")

    # Roadmap placeholders
    for pl, h in [
        ("charset", "[TODO / Milestone 2.3] Streaming character set converter."),
        ("extract", "[TODO / Milestone 2.3] Payload and filesystem extractor."),
        ("package", "[TODO / Milestone 2.4] ROM cartridge compiler (cas2rom / mkrom)."),
        ("bridge", "[TODO / Milestone 2.5] Real-time hardware transport gateway."),
        ("archive", "[TODO / Milestone 2.5] Archival preservation bundle generator."),
        ("recover", "[TODO / Milestone 4.0] Forensic bit/pulse recovery engine."),
    ]:
        subparsers.add_parser(pl, help=h)

    if not effective_argv:
        parser.print_help(sys.stderr)
        return 0

    if any(a == "--help-all" for a in effective_argv):
        non_flags = [a for a in effective_argv if not a.startswith("-")]
        if not non_flags:
            safe_page(format_all_help(parser))
            return 0
        elif non_flags[0] == "meta":
            from dwimsy.meta.__main__ import format_meta_help_all, build_parser as build_meta_p
            safe_page(format_meta_help_all(build_meta_p()))
            return 0
        else:
            effective_argv = ["-h" if a == "--help-all" else a for a in effective_argv]

    args = parser.parse_args(effective_argv)

    if getattr(args, "help_all", False):
        safe_page(format_all_help(parser))
        return 0

    if args.command == "convert":
        run_convert(args)
    elif args.command == "inspect":
        run_inspect(args)
    elif args.command == "split":
        run_split(args)
    elif args.command == "join":
        run_join(args)
    elif args.command == "t882wav":
        in_s = sys.stdin.buffer if args.input == "-" else open(args.input, "rb")
        out_s = sys.stdout.buffer if args.output == "-" else open(args.output, "wb")
        try:
            filter_t882wav.convert_t88_to_wav(
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
    elif args.command == "wav2t88":
        in_s = sys.stdin.buffer if args.input == "-" else open(args.input, "rb")
        out_s = sys.stdout.buffer if args.output == "-" else open(args.output, "wb")
        try:
            bauds = (
                (args.baud,)
                if args.baud
                else tuple(int(b.strip()) for b in args.bauds.split(",") if b.strip())
            )
            filter_wav2t88.process_stream(
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
    elif args.command == "tests":
        from dwimsy.tests import list_tests, run_tests
        if args.list:
            for tid in list_tests(args.patterns):
                print(tid)
            return 0
        rc = run_tests(args.patterns, verbose=args.verbose)
        return rc
    elif args.command == "readme":
        safe_page(get_doc_asset_text("README.md"))
        return 0
    elif args.command == "license":
        safe_page(get_doc_asset_text("LICENSE"))
        return 0
    elif args.command == "changelog":
        safe_page(get_doc_asset_text("CHANGELOG.md"))
        return 0
    elif args.command == "help":
        if args.topic:
            topic = args.topic.strip()
            found = False
            for action in parser._actions:
                if isinstance(action, argparse._SubParsersAction) and topic in action.choices:
                    sub_out = io.StringIO()
                    action.choices[topic].print_help(sub_out)
                    safe_page(sub_out.getvalue())
                    found = True
                    break
            if not found:
                print(f"Unknown command topic '{topic}'. Run 'dwimsy --help-all' for all topics.", file=sys.stderr)
                return 1
        else:
            safe_page(format_all_help(parser))
        return 0
    elif args.command == "meta":
        from dwimsy.meta import __main__ as meta_main
        meta_args = [a for a in effective_argv[1:]]
        return meta_main.main(meta_args)
    elif args.command in (
        "charset",
        "extract",
        "package",
        "bridge",
        "archive",
        "recover",
    ):
        milestones = {
            "charset": "Milestone 2.3",
            "extract": "Milestone 2.3",
            "package": "Milestone 2.4",
            "bridge": "Milestone 2.5",
            "archive": "Milestone 2.5",
            "recover": "Milestone 4.0",
        }
        ms = milestones.get(args.command, "a future milestone")
        print(
            f"[NOT IMPLEMENTED] 'dwimsy {args.command}' is scheduled for {ms}.",
            file=sys.stderr,
        )
        return 1
    else:
        parser.print_help(sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
