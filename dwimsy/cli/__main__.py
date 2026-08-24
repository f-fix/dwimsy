#!/usr/bin/env python3
"""dwimsy.cli.__main__ - Central CLI entry point and subcommand dispatcher for the dwimsy toolkit."""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path
from typing import BinaryIO, List, Optional, Sequence

from dwimsy.cli.filters.t882wav import convert_t88_to_wav
from dwimsy.cli.filters.wav2t88 import process_stream
from dwimsy.protocols.pc88 import (
    analyze_tape,
    convert_cmt_to_t88,
    convert_t88_to_cmt,
    join_cmt_files,
    split_cmt_file,
)
from dwimsy.tape.t88 import join_t88_files, split_t88_file
from dwimsy.meta.integrity import version as get_version


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
                    demod.noise_floor * 1.5, demod.signal_peak * 0.05
                ):
                    continue

                if ev.period_sec < boundary_period:
                    mark_cycles += 1
                    mark_dur_hist.append(ev.period_sec)
                    if len(mark_dur_hist) > 50:
                        mark_dur_hist.pop(0)
                        avg_mark_dur = sum(mark_dur_hist) / len(mark_dur_hist)
                        inst_speed = (1.0 / 2400.0) / avg_mark_dur
                        speed_samples.append(inst_speed)
                else:
                    space_cycles += 1

    dur_sec = total_samples / fs
    print_out(f"Total Duration: {dur_sec:.3f} s ({total_samples} samples)")
    print_out(f"Mark Cycles   : {mark_cycles} (~2400 Hz)")
    print_out(f"Space Cycles  : {space_cycles} (~1200 Hz)")

    if speed_samples:
        avg_speed = sum(speed_samples) / len(speed_samples)
        pct = (avg_speed - 1.0) * 100.0
        print_out(f"Est. Speed    : {avg_speed:.4f}x ({pct:+.2f}%)")
    else:
        print_out("Est. Speed    : Unknown (insufficient carrier)")

    if reader.channels == 2:
        print_out(
            f"Stereo Balance: Left energy={reader._left_energy:.2e}, Right energy={reader._right_energy:.2e}"
        )
        if reader.best_channel:
            print_out(f"Recommendation: Channel mode '{reader.best_channel}'")
    print_out("======================================================================")


def format_all_help(parser: argparse.ArgumentParser) -> str:
    """Produce an aligned, unified help text for all primary commands and subcommands."""
    out = [parser.format_help().rstrip()]
    out.append("")
    out.append("=" * 80)
    out.append("DETAILED SUBCOMMAND HELP")
    out.append("=" * 80)

    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, subparser in sorted(action.choices.items()):
                out.append(f"\n--- Subcommand: {name} ---")
                out.append(subparser.format_help().rstrip())

    return "\n".join(out)


def run_convert(args):
    in_s = sys.stdin.buffer if args.input == "-" else open(args.input, "rb")
    out_s = sys.stdout.buffer if args.output == "-" else open(args.output, "wb")

    try:
        in_name = (
            args.input.lower()
            if args.input != "-"
            else (f"stdin.{args.from_format}" if args.from_format else "")
        )
        out_name = (
            args.output.lower()
            if args.output != "-"
            else (f"stdout.{args.to_format}" if args.to_format else "")
        )

        from_fmt = args.from_format
        if not from_fmt:
            if in_name.endswith(".wav"):
                from_fmt = "wav"
            elif in_name.endswith(".t88"):
                from_fmt = "t88"
            elif in_name.endswith(".cmt"):
                from_fmt = "cmt"

        to_fmt = args.to_format
        if not to_fmt:
            if out_name.endswith(".wav"):
                to_fmt = "wav"
            elif out_name.endswith(".t88"):
                to_fmt = "t88"
            elif out_name.endswith(".cmt"):
                to_fmt = "cmt"

        if not from_fmt or not to_fmt:
            print(
                "Error: Could not infer format conversion path. Please specify --from-format and/or --to-format explicitly.",
                file=sys.stderr,
            )
            sys.exit(1)

        from_fmt = from_fmt.lower()
        to_fmt = to_fmt.lower()

        if from_fmt == "wav" and to_fmt == "t88":
            bauds = (
                (args.baud,)
                if args.baud
                else tuple(
                    int(b.strip()) for b in args.bauds.split(",") if b.strip()
                )
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
        elif from_fmt == "t88" and to_fmt == "wav":
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
        elif from_fmt == "t88" and to_fmt == "cmt":
            convert_t88_to_cmt(in_s, out_s, quiet=args.quiet)
        elif from_fmt == "cmt" and to_fmt == "t88":
            baud = args.baud or 1200
            convert_cmt_to_t88(in_s, out_s, baud=baud, quiet=args.quiet)
        elif from_fmt == "wav" and to_fmt == "cmt":
            t88_buf = io.BytesIO()
            bauds = (
                (args.baud,)
                if args.baud
                else tuple(
                    int(b.strip()) for b in args.bauds.split(",") if b.strip()
                )
            )
            process_stream(
                in_s,
                t88_buf,
                supported_bauds=bauds,
                channel_mode=args.channel,
                confidence_threshold=args.confidence,
                flavor=args.flavor,
                quiet=args.quiet,
            )
            t88_buf.seek(0)
            convert_t88_to_cmt(t88_buf, out_s, quiet=args.quiet)
        elif from_fmt == "cmt" and to_fmt == "wav":
            t88_buf = io.BytesIO()
            baud = args.baud or 1200
            convert_cmt_to_t88(in_s, t88_buf, baud=baud, quiet=args.quiet)
            t88_buf.seek(0)
            convert_t88_to_wav(
                t88_buf,
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
        else:
            print(
                f"Error: Unsupported conversion path '{from_fmt}' -> '{to_fmt}'.",
                file=sys.stderr,
            )
            sys.exit(1)
    finally:
        if in_s is not sys.stdin.buffer:
            in_s.close()
        if out_s is not sys.stdout.buffer:
            out_s.close()


def run_inspect(args):
    in_name = args.input.lower()
    in_s = sys.stdin.buffer if args.input == "-" else open(args.input, "rb")
    try:
        if in_name.endswith(".wav"):
            inspect_audio(in_s, channel_mode=args.channel, out_stream=sys.stdout)
        elif in_name.endswith(".t88") or in_name.endswith(".cmt"):
            buf = in_s.read()
            report = analyze_tape(buf, filename=args.input, verbose=args.verbose)
            print(report)
        else:
            magic = in_s.read(12)
            in_s.seek(0)
            if magic.startswith(b"RIFF"):
                inspect_audio(in_s, channel_mode=args.channel, out_stream=sys.stdout)
            else:
                buf = in_s.read()
                report = analyze_tape(buf, filename=args.input, verbose=args.verbose)
                print(report)
    finally:
        if in_s is not sys.stdin.buffer:
            in_s.close()


def run_split(args):
    in_name = args.input.lower()
    in_s = open(args.input, "rb")
    try:
        out_dir = Path(args.output_dir) if args.output_dir else Path.cwd()
        target_fmt = args.format or ("t88" if in_name.endswith(".t88") else "cmt")

        if in_name.endswith(".t88"):
            out_paths = split_t88_file(
                in_s,
                out_dir,
                target_format=target_fmt,
                baud=args.baud,
                comment=args.comment,
            )
        else:
            out_paths = split_cmt_file(
                in_s,
                out_dir,
                target_format=target_fmt,
                baud=args.baud or 1200,
                comment=args.comment,
            )

        print(
            f"Successfully split '{args.input}' into {len(out_paths)} file(s):"
        )
        for p in out_paths:
            print(f"  - {p}")
    finally:
        in_s.close()


def run_join(args):
    out_name = args.output.lower()
    out_fmt = args.format or ("cmt" if out_name.endswith(".cmt") else "t88")

    out_s = open(args.output, "wb")
    try:
        if out_fmt == "cmt":
            join_cmt_files(args.inputs, out_s)
        else:
            bauds = None
            if args.bauds:
                bauds = [
                    int(b.strip()) for b in args.bauds.split(",") if b.strip()
                ]
            join_t88_files(
                args.inputs,
                out_s,
                default_baud=args.baud,
                per_input_bauds=bauds,
                cmt_baud=args.cmt_baud,
                comment=args.comment,
            )
        print(
            f"Successfully joined {len(args.inputs)} file(s) into '{args.output}' ({out_fmt.upper()})"
        )
    finally:
        out_s.close()


def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(
        prog="dwimsy",
        description="dwimsy — retrocomputing media preservation, demodulation, and conversion.",
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
        "-T", "--test", action="store_true", help="Run unit tests and self-test assertions in-process"
    )
    parser.add_argument(
        "--help-all",
        action="store_true",
        help="Show full detailed help for all subcommands at once and exit",
    )

    effective_argv = sys.argv[1:] if argv is None else list(argv)
    if not effective_argv:
        parser.print_help(sys.stderr)
        sys.exit(0)

    if "-T" in effective_argv or "--test" in effective_argv:
        cmd = None
        for arg in effective_argv:
            if arg in ("convert", "inspect", "split", "join", "meta", "t882wav", "wav2t88"):
                cmd = arg
                break
        from dwimsy.tests import run_tests
        rc = run_tests([cmd] if cmd else None)
        sys.exit(rc)

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    p_conv = subparsers.add_parser(
        "convert", help="Convert between media representations (WAV, T88, CMT)."
    )
    p_conv.add_argument(
        "input", help="Input file or '-' for stdin"
    )
    p_conv.add_argument(
        "output", help="Output file or '-' for stdout"
    )
    p_conv.add_argument(
        "--from-format",
        default=None,
        help="Explicit input format (wav, t88, cmt)",
    )
    p_conv.add_argument(
        "--to-format",
        default=None,
        help="Explicit output format (wav, t88, cmt)",
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
        "--speed", "-s", type=float, default=1.0, help="Speed multiplier (default: 1.0)"
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

    p_insp = subparsers.add_parser(
        "inspect",
        help="Inspect media container headers and structural contents.",
    )
    p_insp.add_argument(
        "input", help="Input file or '-' to inspect"
    )
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
        "split",
        help="Split multi-file tape images into individual program files.",
    )
    p_split.add_argument(
        "input", help="Input .cmt or .t88 file"
    )
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
        "-o", "--output", required=True, help="Output destination path"
    )
    p_join.add_argument(
        "inputs",
        nargs="+",
        help="Input files to merge (supports positional -b/--baud a la SoX)",
    )
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
    meta_subparsers = p_meta.add_subparsers(dest="meta_command", metavar="<meta-command>")

    p_meta_bundle = meta_subparsers.add_parser(
        "bundle", help="Generate a self-extracting single-file Python unpacker bundle of dwimsy."
    )
    p_meta_bundle.add_argument(
        "-o", "--output", default=None, help="Output script path or '-' for stdout (default: auto-derived)"
    )
    p_meta_bundle.add_argument(
        "-t", "--tag", default=None, help="Optional short descriptive tag/label (e.g. 'parser-fix')"
    )
    p_meta_bundle.add_argument(
        "--baseline", action="store_true", help="Directly emit the installed canonical baseline bundle module (dwimsy/meta/unbundle.py) as output without bundling working tree"
    )
    p_meta_bundle.add_argument(
        "--with-deps", action="store_true", help="Include legacy submodule scaffolding from deps/"
    )
    p_meta_bundle.add_argument(
        "--status", action="store_true", help="List uncommitted/modified and untracked files before bundling"
    )
    p_meta_bundle.add_argument(
        "--diff", action="store_true", help="Display working tree git diff on stderr before bundling"
    )

    p_meta_fetch_deps = meta_subparsers.add_parser(
        "fetch-deps", help="Fetch or materialize legacy reference submodules into deps/."
    )
    p_meta_fetch_deps.add_argument(
        "--baseline", action="store_true", help="Extract frozen reference submodules directly from the bundled baseline payload without network access"
    )
    p_meta_fetch_deps.add_argument(
        "-f", "--force", action="store_true", help="Overwrite existing deps/ directory if present"
    )

    # Roadmap stubs
    p_help = subparsers.add_parser("help", help="[TODO / Milestone 1.6] Interactive technical manual viewer.")
    p_readme = subparsers.add_parser("readme", help="[TODO / Milestone 1.6] Output project README documentation.")
    p_license = subparsers.add_parser("license", help="[TODO / Milestone 1.6] Output project LICENSE terms.")
    p_changelog = subparsers.add_parser("changelog", help="[TODO / Milestone 1.6] Interactive revision history viewer.")
    p_charset = subparsers.add_parser("charset", help="[TODO / Milestone 2.3] Streaming character set converter.")
    p_extract = subparsers.add_parser("extract", help="[TODO / Milestone 2.3] Payload and filesystem extractor.")
    p_package = subparsers.add_parser("package", help="[TODO / Milestone 2.4] ROM cartridge compiler (cas2rom / mkrom).")
    p_bridge = subparsers.add_parser("bridge", help="[TODO / Milestone 2.5] Real-time hardware transport gateway.")
    p_archive = subparsers.add_parser("archive", help="[TODO / Milestone 2.5] Archival preservation bundle generator.")
    p_recover = subparsers.add_parser("recover", help="[TODO / Milestone 4.0] Forensic bit/pulse recovery engine.")

    p_meta_bundle_fix = meta_subparsers.add_parser("bundle-fixtures", help="[TODO / Milestone 1.6] Package private test fixtures.")
    p_meta_v_bump = meta_subparsers.add_parser("version-bump", help="[TODO / Milestone 1.6] Advance revision and update changelog.")
    p_meta_integrity = meta_subparsers.add_parser("integrity", help="[TODO / Milestone 1.6] Verify source code integrity hash.")

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
        from dwimsy.meta.bundle import run_meta_bundle, run_meta_fetch_deps
        if args.meta_command == "bundle":
            run_meta_bundle(args)
        elif args.meta_command == "fetch-deps":
            run_meta_fetch_deps(args)
        elif args.meta_command in ("bundle-fixtures", "version-bump", "integrity"):
            print(f"[NOT IMPLEMENTED] 'dwimsy meta {args.meta_command}' is scheduled for Milestone 1.6.", file=sys.stderr)
            sys.exit(1)
        else:
            p_meta.print_help(sys.stderr)
            sys.exit(1)
    elif args.command in ("help", "readme", "license", "changelog", "charset", "extract", "package", "bridge", "archive", "recover"):
        print(f"[NOT IMPLEMENTED] 'dwimsy {args.command}' is scheduled for a future milestone.", file=sys.stderr)
        sys.exit(1)
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
