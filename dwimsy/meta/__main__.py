#!/usr/bin/env python3
"""dwimsy.meta.__main__ - Central CLI dispatcher for maintainer and repository lifecycle tools."""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path
from typing import List, Optional

here = Path(__file__).resolve()
if len(here.parts) >= 3 and here.parts[-3] == "dwimsy" and here.parts[-2] == "meta":
    p = here.parents[2]
    if (p / "dwimsy" / "_version.py").is_file() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dwimsy.meta import bundle, diff, integrity, lint, unbundle, version_bump


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dwimsy meta",
        description="dwimsy meta - Maintainer tools and repository lifecycle management.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {integrity.version()}",
    )
    parser.add_argument(
        "-T",
        "--test",
        nargs="?",
        const=True,
        default=False,
        help="Run scoped meta self-tests in-process (optional pattern filter)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase output verbosity",
    )
    parser.add_argument(
        "--help-all",
        action="store_true",
        help="Show full detailed help for all meta subcommands and exit",
    )

    subparsers = parser.add_subparsers(dest="meta_command", metavar="<meta-command>")

    # bundle
    p_bundle = subparsers.add_parser(
        "bundle",
        help="Generate a self-extracting single-file Python unpacker bundle of dwimsy.",
    )
    p_bundle.add_argument(
        "-o", "--output", default=None, help="Output script path or '-' for stdout"
    )
    p_bundle.add_argument(
        "-t", "--tag", default=None, help="Optional short descriptive tag/label"
    )
    p_bundle.add_argument(
        "--with-deps",
        action="store_true",
        help="Include legacy submodule scaffolding from deps/",
    )
    p_bundle.add_argument(
        "--status",
        action="store_true",
        help="List uncommitted/modified and untracked files",
    )
    p_bundle.add_argument(
        "--diff", action="store_true", help="Display working tree diff before bundling"
    )
    p_bundle.add_argument(
        "-f", "--force", action="store_true", help="Force bundle emission"
    )
    p_bundle.add_argument(
        "--baseline", action="store_true", help="Bundle clean baseline"
    )
    p_bundle.add_argument(
        "--dry-run",
        action="store_true",
        help="Build bundle in memory/temp and display manifest without committing",
    )
    p_bundle.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase verbosity"
    )
    p_bundle.add_argument(
        "--help-all", action="store_true", help="Show full help documentation and exit"
    )

    # unbundle
    p_unbundle = subparsers.add_parser(
        "unbundle",
        help="Extract dwimsy standalone bundle to a target directory.",
    )
    p_unbundle.add_argument(
        "target_directory",
        nargs="?",
        default=None,
        help="Target directory for extraction",
    )
    p_unbundle.add_argument(
        "--deps",
        "-d",
        action="store_true",
        help="Also extract reference dependencies into deps/",
    )
    p_unbundle.add_argument(
        "-f", "--force", action="store_true", help="Force unbundle extraction"
    )
    p_unbundle.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress progress output"
    )
    p_unbundle.add_argument(
        "--help-all", action="store_true", help="Show full help documentation and exit"
    )

    # diff
    p_diff = subparsers.add_parser(
        "diff",
        help="Show differences between the working tree and embedded baseline.",
    )
    p_diff.add_argument("-r", "--root", default=None, help="Target repository root")
    p_diff.add_argument(
        "versions",
        nargs="*",
        default=[],
        help="Optional version tags or selectors to compare (e.g. [VER1] [VER2])",
    )
    p_diff.add_argument(
        "--help-all", action="store_true", help="Show full help documentation and exit"
    )

    # integrity
    p_integrity = subparsers.add_parser(
        "integrity",
        help="Verify the canonical portable-project integrity hash.",
    )
    p_integrity.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress output on clean status"
    )
    p_integrity.add_argument(
        "--help-all", action="store_true", help="Show full help documentation and exit"
    )

    # fetch-deps
    p_fetch = subparsers.add_parser(
        "fetch-deps",
        help="Fetch or materialize legacy reference submodules into deps/.",
    )
    p_fetch.add_argument(
        "-f", "--force", action="store_true", help="Overwrite existing deps/ files"
    )
    p_fetch.add_argument(
        "--help-all", action="store_true", help="Show full help documentation and exit"
    )

    # version-bump
    p_bump = subparsers.add_parser(
        "version-bump",
        help="Advance revision, record changelog, and synchronize bundle baseline.",
    )
    p_bump.add_argument(
        "target_version", nargs="?", default=None, help="Explicit new version string"
    )
    p_bump.add_argument(
        "--patch", action="store_true", help="Increment patch component"
    )
    p_bump.add_argument(
        "--minor", action="store_true", help="Increment minor component"
    )
    p_bump.add_argument(
        "--major", action="store_true", help="Increment major component"
    )
    p_bump.add_argument(
        "--rev", action="store_true", help="Increment build/revision digit"
    )
    p_bump.add_argument("--release", action="store_true", help="Remove -dev suffix")
    p_bump.add_argument("--dev", action="store_true", help="Ensure -dev suffix")
    p_bump.add_argument(
        "-m", "--message", default=None, help="Changelog description message"
    )
    p_bump.add_argument(
        "--no-bundle", action="store_true", help="Skip bundle baseline synchronization"
    )
    p_bump.add_argument(
        "--help-all", action="store_true", help="Show full help documentation and exit"
    )

    # lint
    p_lint = subparsers.add_parser(
        "lint",
        help="Verify repository headers, docstrings, markdown syntax, and dash policy.",
    )
    p_lint.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress output on success"
    )
    p_lint.add_argument(
        "--help-all", action="store_true", help="Show full help documentation and exit"
    )

    # bundle-fixtures (placeholder)
    subparsers.add_parser(
        "bundle-fixtures",
        help="[TODO / Milestone 1.6] Package private test fixtures.",
    )

    return parser


def format_meta_help_all(parser: argparse.ArgumentParser) -> str:
    out = io.StringIO()
    parser.print_help(out)
    out.write("\n\n" + "=" * 80 + "\n")
    out.write("DETAILED META SUBCOMMAND HELP\n")
    out.write("=" * 80 + "\n")

    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for choice, subparser in action.choices.items():
                out.write(f"\n--- Meta Subcommand: {choice} ---\n")
                sub_out = io.StringIO()
                subparser.print_help(sub_out)
                out.write(sub_out.getvalue().strip() + "\n")
    return out.getvalue()


def main(argv: Optional[List[str]] = None) -> int:
    effective = sys.argv[1:] if argv is None else list(argv)
    from dwimsy.cli.dispatch import early_dispatch

    handled, effective = early_dispatch(
        effective, ["meta"], use_process_argv0=(argv is None)
    )
    if handled:
        return 0
    from dwimsy.cli.dispatch import early_dispatch

    handled, effective = early_dispatch(
        effective, ["meta"], use_process_argv0=(argv is None)
    )
    if handled:
        return 0

    test_arg = None
    for a in effective:
        if a in ("-T", "--test") or a.startswith("--test="):
            test_arg = a
            break
    if test_arg is not None:
        verbosity = 1
        for a in effective:
            if a in ("-v", "--verbose"):
                verbosity = max(verbosity + 1, 2)
            elif a.startswith("-") and len(a) > 1 and all(c == "v" for c in a[1:]):
                verbosity = max(verbosity + len(a) - 1, 2)
        from dwimsy.tests import run_tests

        pattern = None
        if test_arg.startswith("--test="):
            pattern = [test_arg.split("=", 1)[1]]
        elif "bundle" in effective:
            pattern = ["meta bundle"]
        elif "unbundle" in effective:
            pattern = ["meta unbundle"]
        elif "diff" in effective:
            pattern = ["meta diff"]
        elif "integrity" in effective:
            pattern = ["meta integrity"]
        elif "version-bump" in effective:
            pattern = ["meta version-bump"]
        elif "lint" in effective:
            pattern = ["meta lint"]
        elif "fetch-deps" in effective:
            pattern = ["meta fetch-deps"]
        else:
            pattern = ["meta"]
        return run_tests(pattern, verbose=verbosity)

    if any(a == "--help-all" for a in effective):
        non_flags = [a for a in effective if not a.startswith("-")]
        if len(non_flags) > 0 and non_flags[0] in (
            "bundle",
            "unbundle",
            "diff",
            "integrity",
            "fetch-deps",
            "version-bump",
            "lint",
            "bundle-fixtures",
        ):
            effective = ["-h" if a == "--help-all" else a for a in effective]
        else:
            parser = build_parser()
            from dwimsy.cli.__main__ import safe_page

            safe_page(format_meta_help_all(parser))
            return 0

    parser = build_parser()
    if not effective:
        parser.print_help(sys.stderr)
        return 0

    args = parser.parse_args(effective)

    if args.meta_command == "bundle":
        return bundle.run_meta_bundle(args)
    elif args.meta_command == "unbundle":
        if not getattr(args, "target_directory", None):
            print(
                "usage: dwimsy meta unbundle [-h] [--deps] target_directory",
                file=sys.stderr,
            )
            return 1
        try:
            target_v = getattr(args, "version", None)
            unbundle.safe_unbundle(
                b64_string=unbundle._get_active_blztar(),
                output_dir=args.target_directory,
                with_deps=args.deps,
                force=getattr(args, "force", False),
                dry_run=getattr(args, "dry_run", False),
                quiet=getattr(args, "quiet", False),
                target_version=target_v,
                verbose=getattr(args, "verbose", 0) > 0,
            )
            return 0
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            return 1
    elif args.meta_command == "diff":
        root_path = Path(args.root).resolve() if getattr(args, "root", None) else None
        v1 = (
            args.versions[0]
            if getattr(args, "versions", None) and len(args.versions) > 0
            else None
        )
        v2 = (
            args.versions[1]
            if getattr(args, "versions", None) and len(args.versions) > 1
            else None
        )
        try:
            out = diff.render_diff(root=root_path, v1_sel=v1, v2_sel=v2)
            if out:
                sys.stdout.write(out)
            return 0
        except (ValueError, RuntimeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    elif args.meta_command == "integrity":
        current = integrity.canonical_code_hash()
        sealed = integrity.sealed_code_hash()
        modified = integrity.is_modified()
        ver_str = integrity.version()
        if not getattr(args, "quiet", False):
            print(f"Canonical hash : {current}")
            print(f"Sealed hash    : {sealed or '(unsealed)'}")
            print(f"Status         : {'MODIFIED' if modified else 'CLEAN'}")
            print(f"Version        : {ver_str}")
        return 1 if modified else 0
    elif args.meta_command == "fetch-deps":
        return bundle.run_meta_fetch_deps(args)
    elif args.meta_command == "version-bump":
        part = "patch"
        if getattr(args, "major", False):
            part = "major"
        elif getattr(args, "minor", False):
            part = "minor"
        elif getattr(args, "rev", False):
            part = "rev"
        new_v = version_bump.bump_version(
            version_str=getattr(args, "target_version", None),
            part=part,
            release=getattr(args, "release", False),
            dev=getattr(args, "dev", False),
            message=getattr(args, "message", None),
            no_bundle=getattr(args, "no_bundle", False),
            verbose=getattr(args, "verbose", 0) > 0,
        )
        print(f"Version bumped to {new_v}")
        return 0
    elif args.meta_command == "lint":
        errs = lint.run_all_lints()
        if errs:
            for e in errs:
                print(f"[FAIL] {e}", file=sys.stderr)
            return 1
        if not getattr(args, "quiet", False):
            print("[SUCCESS] All repository lint checks passed cleanly.")
        return 0
    elif args.meta_command == "bundle-fixtures":
        print(
            "[NOT IMPLEMENTED] 'dwimsy meta bundle-fixtures' is scheduled for Milestone 1.6.",
            file=sys.stderr,
        )
        return 1
    else:
        parser.print_help(sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
