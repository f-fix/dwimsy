#!/usr/bin/env python3
"""dwimsy.meta.diff - Compare a working tree with the embedded baseline."""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path
from typing import List, Optional

for p in Path(__file__).resolve().parents:
    if (p / "dwimsy").is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
        break

from dwimsy.meta import integrity


def render_diff(root: Optional[Path] = None) -> str:
    """Return a unified diff between the current tree and embedded baseline."""
    current = integrity.canonical_assets(root, baseline=False)
    baseline = integrity.canonical_assets(root, baseline=True)
    lines = []
    for name in sorted(set(current) | set(baseline)):
        a = baseline.get(name)
        b = current.get(name)
        old_bytes = None if a is None else integrity._canonical_bytes(a, name)
        new_bytes = None if b is None else integrity._canonical_bytes(b, name)
        if old_bytes == new_bytes:
            continue
        if old_bytes is None or new_bytes is None:
            old = [] if old_bytes is None else old_bytes.decode("utf-8", errors="replace").splitlines(True)
            new = [] if new_bytes is None else new_bytes.decode("utf-8", errors="replace").splitlines(True)
        else:
            try:
                old = old_bytes.decode("utf-8").splitlines(True)
                new = new_bytes.decode("utf-8").splitlines(True)
            except UnicodeDecodeError:
                lines.append(f"diff --git a/{name} b/{name}\n")
                lines.append(f"Binary files a/{name} and b/{name} differ\n")
                continue
        lines.append(f"diff --git a/{name} b/{name}\n")
        lines.extend(difflib.unified_diff(
            old, new, fromfile=f"a/{name}", tofile=f"b/{name}", lineterm="\n"
        ))
    return "".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for running dwimsy.meta.diff directly."""
    effective = sys.argv[1:] if argv is None else list(argv)

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

    parser = argparse.ArgumentParser(
        prog="dwimsy-diff",
        description="Show unified diff between the current working tree and embedded baseline.",
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
        "-r",
        "--root",
        default=None,
        help="Target repository root to compare (default: auto-detected)",
    )
    args = parser.parse_args(effective)

    if args.test is not False:
        from dwimsy.tests import run_tests
        pattern = [args.test] if isinstance(args.test, str) else ["meta diff"]
        return run_tests(pattern, verbose=max(args.verbose, 1))

    root_path = Path(args.root).resolve() if args.root else None
    diff_text = render_diff(root_path)
    if diff_text:
        sys.stdout.write(diff_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
