#!/usr/bin/env python3
"""dwimsy.cli.__main__ - Central CLI entrypoint for dwimsy.

Exposes 'convert', 'inspect', 'split', and 'join' verbs.
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
from dwimsy.meta.bundle import run_meta_bundle, run_meta_fetch_deps


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


def format_all_help(parser: argparse.ArgumentParser) -> str:
    out = io.StringIO()
    parser.print_help(out)
    out.write("\n\n" + "=" * 80 + "\n")
    out.write("DETAILED SUBCOMMAND HELP\n")
    out.write("=" * 80 + "\n")

    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for choice, subparser in action.choices.items():
                out.write(f"\n--- Subcommand: {choice} ---\n")
                sub_out = io.StringIO()
                subparser.print_help(sub_out)
                out.write(sub_out.getvalue().strip() + "\n")
    return out.getvalue()


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

    for p in Path(__file__).resolve().parents:
        if (p / "dwimsy").is_dir():
            if str(p) in sys.path:
                sys.path.remove(str(p))
            sys.path.insert(0, str(p))
            break

    parser = argparse.ArgumentParser(
        prog="dwimsy",
        description="dwimsy - retrocomputing media preservation, demodulation, and conversion.",
        epilog="Tip: Run 'dwimsy <command> --help' or 'dwimsy --help-all' to view detailed options for all commands.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
    )
    parser.add_argument(
        "-T",
        "--test",
        action="store_true",
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
        "-v",
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
    p_conv.add_argument("--invert", action="store_true", help="Invert audio polarity")
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

    p_insp = subparsers.add_parser(
        "inspect", help="Inspect media container headers and structural contents."
    )
    p_insp.add_argument("input", help="Input file or '-' to inspect")
    p_insp.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose block structure"
    )
    p_insp.add_argument(
        "-c",
        "--channel",
        default="auto",
        choices=["auto", "left", "right", "mix", "diff"],
        help="Audio channel routing mode for WAV inspection (default: auto)",
    )

    p_split = subparsers.add_parser(
        "split", help="Split multi-file tape images into individual program files."
    )
    p_split.add_argument("input", help="Input .cmt or .t88 file")
    p_split.add_argument(
        "-o", "--output-dir", default=None, help="Output directory for split files"
    )
    p_split.add_argument(
        "--format",
        choices=["cmt", "t88"],
        default=None,
        help="Target split format: 'cmt' (default) or 't88'",
    )
    p_split.add_argument(
        "-b", "--baud", type=int, default=None, help="Baud rate override for T88 output"
    )
    p_split.add_argument(
        "--comment", default="", help="Optional comment embedded in T88 headers"
    )

    p_join = subparsers.add_parser(
        "join", help="Join multiple files into a single .cmt or .t88 tape image."
    )
    p_join.add_argument(
        "inputs",
        nargs="+",
        help="Input files to merge (supports positional -b/--baud a la SoX)",
    )
    p_join.add_argument("-o", "--output", required=True, help="Output destination path")
    p_join.add_argument(
        "--format",
        choices=["cmt", "t88"],
        default=None,
        help="Target output format ('cmt' or 't88', inferred from output extension by default)",
    )
    p_join.add_argument(
        "-b",
        "--baud",
        type=int,
        default=None,
        help="Global baud rate override for all T88 outputs",
    )
    p_join.add_argument(
        "--bauds",
        default=None,
        help="Sequential comma-separated baud rates per input (e.g. '1200,600')",
    )
    p_join.add_argument(
        "--cmt-baud",
        type=int,
        default=1200,
        help="Default baud rate for raw .cmt inputs when producing .t88",
    )
    p_join.add_argument(
        "--comment", default="", help="Optional comment embedded in T88 header"
    )

    p_meta = subparsers.add_parser(
        "meta", help="Maintainer tools and repository lifecycle management."
    )
    meta_subparsers = p_meta.add_subparsers(
        dest="meta_command", metavar="<meta-command>"
    )

    p_meta_bundle = meta_subparsers.add_parser(
        "bundle",
        help="Generate a self-extracting single-file Python unpacker bundle of dwimsy.",
    )
    p_meta_bundle.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output script path or '-' for stdout (default: auto-derived)",
    )
    p_meta_bundle.add_argument(
        "-t",
        "--tag",
        default=None,
        help="Optional short descriptive tag/label (e.g. 'parser-fix')",
    )
    p_meta_bundle.add_argument(
        "--baseline",
        action="store_true",
        help="Directly emit the installed canonical baseline bundle module (dwimsy/meta/unbundle.py) as output without bundling working tree",
    )
    p_meta_bundle.add_argument(
        "--with-deps",
        action="store_true",
        help="Include legacy submodule scaffolding from deps/",
    )
    p_meta_bundle.add_argument(
        "--status",
        action="store_true",
        help="List uncommitted/modified and untracked files before bundling",
    )
    p_meta_bundle.add_argument(
        "--diff",
        action="store_true",
        help="Display working tree git diff on stderr before bundling",
    )
    p_meta_bundle.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity of bundle build and test verification",
    )
    p_meta_fetch_deps = meta_subparsers.add_parser(
        "fetch-deps",
        help="Fetch or materialize legacy reference submodules into deps/.",
    )
    p_meta_fetch_deps.add_argument(
        "--baseline",
        action="store_true",
        help="Extract frozen reference submodules directly from the bundled baseline payload without network access",
    )
    p_meta_fetch_deps.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite existing deps/ directory if present",
    )

    # Registered roadmap placeholder commands
    subparsers.add_parser(
        "help", help="[TODO / Milestone 1.6] Interactive technical manual viewer."
    )
    subparsers.add_parser(
        "readme", help="[TODO / Milestone 1.6] Output project README documentation."
    )
    subparsers.add_parser(
        "license", help="[TODO / Milestone 1.6] Output project LICENSE terms."
    )
    subparsers.add_parser(
        "changelog", help="[TODO / Milestone 1.6] Interactive revision history viewer."
    )
    subparsers.add_parser(
        "charset", help="[TODO / Milestone 2.3] Streaming character set converter."
    )
    subparsers.add_parser(
        "extract", help="[TODO / Milestone 2.3] Payload and filesystem extractor."
    )
    subparsers.add_parser(
        "package",
        help="[TODO / Milestone 2.4] ROM cartridge compiler (cas2rom / mkrom).",
    )
    subparsers.add_parser(
        "bridge", help="[TODO / Milestone 2.5] Real-time hardware transport gateway."
    )
    subparsers.add_parser(
        "archive", help="[TODO / Milestone 2.5] Archival preservation bundle generator."
    )
    subparsers.add_parser(
        "recover", help="[TODO / Milestone 4.0] Forensic bit/pulse recovery engine."
    )

    meta_subparsers.add_parser(
        "bundle-fixtures", help="[TODO / Milestone 1.6] Package private test fixtures."
    )
    meta_subparsers.add_parser(
        "version-bump",
        help="[TODO / Milestone 1.6] Advance revision and update changelog.",
    )
    meta_subparsers.add_parser(
        "integrity", help="[TODO / Milestone 1.6] Verify source code integrity hash."
    )

    if not effective_argv:
        parser.print_help(sys.stderr)
        sys.exit(0)

    if "-T" in effective_argv or "--test" in effective_argv:
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
            ):
                cmd = arg
            elif arg in ("-v", "--verbose"):
                verbosity = max(verbosity + 1, 2)
            elif (
                arg.startswith("-") and len(arg) > 1 and all(c == "v" for c in arg[1:])
            ):
                verbosity = max(verbosity + len(arg) - 1, 2)
        from dwimsy.tests import run_tests

        rc = run_tests([cmd] if cmd else None, verbose=verbosity)
        sys.exit(rc)

    args = parser.parse_args(argv)

    if args.help_all:
        print(format_all_help(parser))
        sys.exit(0)

    if args.command == "convert":
        run_convert(args)
    elif args.command == "inspect":
        run_inspect(args)
    elif args.command == "split":
        run_split(args)
    elif args.command == "join":
        run_join(args)
    elif args.command == "meta":
        if args.meta_command == "bundle":
            run_meta_bundle(args)
        elif args.meta_command == "fetch-deps":
            run_meta_fetch_deps(args)
        elif args.meta_command in ("bundle-fixtures", "version-bump", "integrity"):
            print(
                f"[NOT IMPLEMENTED] 'dwimsy meta {args.meta_command}' is scheduled for Milestone 1.6.",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            p_meta.print_help(sys.stderr)
            sys.exit(1)
    elif args.command in (
        "help",
        "readme",
        "license",
        "changelog",
        "charset",
        "extract",
        "package",
        "bridge",
        "archive",
        "recover",
    ):
        milestones = {
            "help": "Milestone 1.6",
            "readme": "Milestone 1.6",
            "license": "Milestone 1.6",
            "changelog": "Milestone 1.6",
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
        sys.exit(1)
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
