#!/usr/bin/env python3
"""dwimsy.meta.diff - Version-labeled unified diff engine comparing trees across streams."""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

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
    repo = integrity.find_repo_root(root)
    raw_b64 = unbundle._get_active_blztar()
    vspace = VersionSpace.from_blztar(raw_b64) if raw_b64 else VersionSpace()

    v1_tag = "baseline"
    v2_tag = "unbundled"

    if v1_sel is None and v2_sel is None:
        baseline_assets = integrity.canonical_assets(repo, baseline=True)
        unbundled_assets = integrity.canonical_assets(repo, baseline=False)
        v1_tag = f"dwimsy_{integrity._version_values(repo, baseline=True).get('__version__', '0.1.6.0')}"
        v2_tag = f"dwimsy_{integrity.version(root=repo)}"
        old_assets = baseline_assets
        new_assets = unbundled_assets
    else:
        target1 = v1_sel or "baseline"
        target2 = v2_sel or "unbundled"

        if target1 == "unbundled":
            old_assets = integrity.canonical_assets(repo, baseline=False)
            v1_tag = f"dwimsy_{integrity.version(root=repo)}"
        else:
            res1 = vspace.resolve_version_ref(target1)
            if res1 is None:
                raise ValueError(f"Version selector '{target1}' could not be resolved.")
            s1, ord1, ref1 = res1
            old_assets = s1.materialize_layer_state(ord1)
            stream_prefix = f"alt{s1.index}_" if s1.index > 0 else ""
            v1_tag = f"dwimsy_{stream_prefix}{ref1.tag}"

        if target2 == "unbundled":
            new_assets = integrity.canonical_assets(repo, baseline=False)
            v2_tag = f"dwimsy_{integrity.version(root=repo)}"
        else:
            res2 = vspace.resolve_version_ref(target2)
            if res2 is None:
                raise ValueError(f"Version selector '{target2}' could not be resolved.")
            s2, ord2, ref2 = res2
            new_assets = s2.materialize_layer_state(ord2)
            stream_prefix = f"alt{s2.index}_" if s2.index > 0 else ""
            v2_tag = f"dwimsy_{stream_prefix}{ref2.tag}"

    lines: List[str] = []
    all_files = sorted(set(old_assets) | set(new_assets))

    for name in all_files:
        a = old_assets.get(name)
        b = new_assets.get(name)
        old_bytes = None if a is None else integrity._canonical_bytes(a, name)
        new_bytes = None if b is None else integrity._canonical_bytes(b, name)

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

        if name.endswith("unbundle.py"):

            def _sub_version_summary(data_lines):
                text = "".join(data_lines)
                m = re.search(r'blztar = """([\s\S]*?)"""', text)
                if m and m.group(1).strip():
                    summary = vspace.format_list_versions(
                        on_disk_root=repo if repo else None
                    )
                    ph = f'blztar = """\n<- actual omitted base64 lzma tar sequence(s) would start here\n\n$VERSION_SUMMARY\n{summary}\n\nactual omitted base64 lzma tar sequence(s) would end here ->\n"""'
                    text = text[: m.start()] + ph + text[m.end() :]
                    return text.splitlines(True)
                return data_lines

            old_lines = _sub_version_summary(old_lines)
            new_lines = _sub_version_summary(new_lines)

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

        pattern = None
        if test_arg.startswith("--test="):
            pattern = [test_arg.split("=", 1)[1]]
        else:
            pattern = ["meta diff"]
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

    diff_text = render_diff(v1_sel=v1, v2_sel=v2)
    sys.stdout.write(diff_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
