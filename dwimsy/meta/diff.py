#!/usr/bin/env python3
"""dwimsy.meta.diff - Version-labeled unified diff engine comparing trees across streams."""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

for p in Path(__file__).resolve().parents:
    if (p / "dwimsy").is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
        break

from dwimsy.meta import integrity, unbundle
from dwimsy.meta.versions import VersionSpace, VersionRef


def render_diff(
    root: Optional[Path] = None,
    v1_sel: Optional[str] = None,
    v2_sel: Optional[str] = None,
) -> str:
    """Return a version-labeled unified diff between versions or working tree."""
    cwd = Path.cwd().resolve()
    if root is not None:
        repo = Path(root).resolve()
    elif (cwd / "dwimsy" / "__init__.py").is_file():
        repo = cwd
    else:
        repo = integrity.find_repo_root(None)

    raw_b64 = unbundle._get_active_blztar()
    vspace = VersionSpace.from_blztar(raw_b64) if raw_b64 else VersionSpace()

    target1 = v1_sel or "baseline"
    target2 = v2_sel or "unbundled"

    def _resolve_target(target: str) -> Tuple[Dict[str, bytes], str]:
        if target == "unbundled":
            is_checkout = bool(
                repo
                and (repo / "dwimsy").is_dir()
                and (repo / "dwimsy" / "__init__.py").is_file()
            )
            if not is_checkout or (
                integrity.is_standalone_bundle() and "<dwimsy-bundle>" in str(repo)
            ):
                raise ValueError(
                    "Version selector 'unbundled' could not be resolved: current working directory is not inside a dwimsy checkout.\n"
                    "To compare an unbundled directory with the bundle version, use universal flags:\n"
                    "  --version-include-primary=. --version=alt\n"
                    "or specify explicit versions to compare (e.g. 'dwimsy meta diff [VER1] [VER2]')."
                )
            assets = integrity.canonical_assets(repo, baseline=False)
            tag = f"dwimsy_{integrity.version(root=repo)}"
            return assets, tag
        elif target == "baseline":
            b_ref = vspace.resolve_version_ref("baseline")
            if b_ref is not None:
                s_b, ord_b, ref_b = b_ref
                assets = s_b.materialize_layer_state(ord_b)
                tag = f"dwimsy_{ref_b.tag}"
            else:
                assets = integrity.canonical_assets(repo, baseline=True)
                tag = f"dwimsy_{integrity._version_values(repo, baseline=True).get('__version__', '0.1.6.0')}"
            return assets, tag
        else:
            res = vspace.resolve_version_ref(target)
            if res is None:
                raise ValueError(f"Version selector '{target}' could not be resolved.")
            s, ord_idx, ref = res
            assets = s.materialize_layer_state(ord_idx)
            stream_prefix = f"alt{s.index}_" if s.index > 0 else ""
            tag = f"dwimsy_{stream_prefix}{ref.tag}"
            return assets, tag

    old_assets, v1_tag = _resolve_target(target1)
    new_assets, v2_tag = _resolve_target(target2)

    lines: List[str] = []
    all_files = sorted(set(old_assets) | set(new_assets))

    for name in all_files:
        a = old_assets.get(name)
        b = new_assets.get(name)
        old_bytes = None if a is None else integrity._canonical_bytes(a, name)
        new_bytes = None if b is None else integrity._canonical_bytes(b, name)

        def _sub_version_summary_bytes(data):
            if data is None or not name.endswith("unbundle.py"):
                return data
            text = data.decode("utf-8", errors="replace")
            m = re.search(r'blztar = """([\s\S]*?)"""', text)
            if not m or not m.group(1).strip():
                return data
            summary = vspace.format_list_versions(on_disk_root=repo if repo else None)
            ph = (
                'blztar = """\n'
                '<- actual omitted base64 lzma tar sequence(s) would start here\n\n'
                '$VERSION_SUMMARY\n' + summary + '\n\n'
                'actual omitted base64 lzma tar sequence(s) would end here ->\n'
                '"""'
            )
            return (text[:m.start()] + ph + text[m.end():]).encode("utf-8")

        # Normalize the generated blztar payload before equality testing; otherwise
        # canonical bundle elision can bypass the intended $VERSION_SUMMARY view.
        old_bytes = _sub_version_summary_bytes(old_bytes)
        new_bytes = _sub_version_summary_bytes(new_bytes)

        if old_bytes == new_bytes:
            continue

        if old_bytes is None:
            old_lines = []
            old_label = "/dev/null"
        else:
            old_lines = old_bytes.decode("utf-8", errors="replace").splitlines(True)
            old_label = f"{v1_tag}/{name}"

        if new_bytes is None:
            new_lines = []
            new_label = "/dev/null"
        else:
            new_lines = new_bytes.decode("utf-8", errors="replace").splitlines(True)
            new_label = f"{v2_tag}/{name}"


        diff = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=old_label,
                tofile=new_label,
            )
        )
        if diff:
            lines.append(f"diff --git a/{name} b/{name}\n")
            lines.extend(diff)

    return "".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for running dwimsy.meta.diff directly."""
    effective = sys.argv[1:] if argv is None else list(argv)
    from dwimsy.cli.dispatch import early_dispatch

    handled, effective = early_dispatch(
        effective, ["meta", "diff"], use_process_argv0=(argv is None)
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

        pattern = (
            [test_arg.split("=", 1)[1]]
            if test_arg.startswith("--test=")
            else ["meta diff"]
        )
        return run_tests(pattern, verbose=verbosity)

    if any(a == "--help-all" for a in effective):
        effective = ["-h" if a == "--help-all" else a for a in effective]

    from dwimsy.meta.integrity import version as get_version

    parser = argparse.ArgumentParser(
        prog="dwimsy-diff",
        description="Version-labeled unified diff engine.",
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
        nargs="?",
        const=True,
        default=False,
        help="Run scoped diff self-tests in-process (optional pattern filter)",
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
        help="Show full help documentation and exit",
    )
    parser.add_argument("-r", "--root", default=None, help="Target repository root")
    parser.add_argument(
        "versions",
        nargs="*",
        default=[],
        help="Optional version tags or selectors to compare (e.g. [VER1] [VER2])",
    )
    args = parser.parse_args(effective)

    if args.test is not False:
        from dwimsy.tests import run_tests

        pattern = [args.test] if isinstance(args.test, str) else ["meta diff"]
        return run_tests(pattern, verbose=max(args.verbose, 1))

    v1 = args.versions[0] if len(args.versions) > 0 else None
    v2 = args.versions[1] if len(args.versions) > 1 else None

    try:
        diff_text = render_diff(root=getattr(args, "root", None), v1_sel=v1, v2_sel=v2)
        sys.stdout.write(diff_text)
        return 0
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
