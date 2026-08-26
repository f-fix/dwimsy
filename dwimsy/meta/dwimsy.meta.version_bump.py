#!/usr/bin/env python3
"""dwimsy.meta.version_bump - Automated version bumping, changelog recording, and bundle synchronization."""

from __future__ import annotations

import argparse
import datetime
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

for p in Path(__file__).resolve().parents:
    if (p / "dwimsy").is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
        break

from dwimsy.meta import bundle, diff, integrity, unbundle


def parse_and_bump_version(
    current: str,
    part: str = "patch",
    release: bool = False,
    dev: bool = False,
) -> str:
    """Derive next version string based on current and increment rules."""
    m = re.match(
        r"^(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?(?:-([a-zA-Z0-9_.-]+))?$", current
    )
    if not m:
        raise ValueError(f"Cannot parse version string: {current}")
    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3))
    rev = int(m.group(4) or 0)
    has_rev = m.group(4) is not None
    suffix = m.group(5)

    if part == "major":
        major += 1
        minor = 0
        patch = 0
        rev = 0
    elif part == "minor":
        minor += 1
        patch = 0
        rev = 0
    elif part == "patch":
        patch += 1
        rev = 0
    elif part in ("rev", "build"):
        rev += 1
        has_rev = True

    is_dev = False
    if release:
        is_dev = False
    elif dev:
        is_dev = True
    elif suffix and "dev" in suffix:
        is_dev = True

    dev_suffix = "-dev" if is_dev else ""
    if has_rev:
        return f"{major}.{minor}.{patch}.{rev}{dev_suffix}"
    return f"{major}.{minor}.{patch}{dev_suffix}"


def update_version_files(
    new_version: str,
    repo_root: Optional[Path] = None,
    message: Optional[str] = None,
) -> None:
    """Update dwimsy/_version.py, README.md, and CHANGELOG.md with new_version."""
    root = integrity.find_repo_root(repo_root)

    # 1. Update dwimsy/_version.py
    version_file = root / "dwimsy" / "_version.py"
    if version_file.is_file():
        text = version_file.read_text(encoding="utf-8")
        text = re.sub(
            r'__version__\s*=\s*["\'][^"\']+["\']',
            f'__version__ = "{new_version}"',
            text,
        )
        version_file.write_text(text, encoding="utf-8")

    # 2. Update README.md
    readme_file = root / "README.md"
    if readme_file.is_file():
        r_text = readme_file.read_text(encoding="utf-8")
        r_text = re.sub(
            r"\*\*Version:\s*[^)]+\*\*",
            f"**Version: {new_version}**",
            r_text,
        )
        readme_file.write_text(r_text, encoding="utf-8")

    # 3. Update CHANGELOG.md
    changelog_file = root / "CHANGELOG.md"
    today_str = datetime.date.today().isoformat()
    if changelog_file.is_file():
        c_text = changelog_file.read_text(encoding="utf-8")
        header = f"## [{new_version}] - {today_str}"
        if header not in c_text:
            msg_entry = f"- {message}\n" if message else "- Maintenance release and baseline synchronization.\n"
            entry = f"\n{header}\n\n### Changed\n{msg_entry}\n"
            match = re.search(r"(## \[[^\]]+\] - \d{4}-\d{2}-\d{2})", c_text)
            if match:
                c_text = c_text[: match.start()] + entry + c_text[match.start() :]
            else:
                c_text += entry
            changelog_file.write_text(c_text, encoding="utf-8")


def sync_bundle_baseline(
    repo_root: Optional[Path] = None, verbose: bool = False
) -> Path:
    """Rebuild the standalone bundle from the live working tree and sync unbundle.py."""
    root = integrity.find_repo_root(repo_root)
    unbundle_file = root / "dwimsy" / "meta" / "unbundle.py"

    bundle_script = bundle.build_bundle_script(repo_root=root, with_deps=True)
    unbundle_file.write_text(bundle_script, encoding="utf-8")
    try:
        unbundle_file.chmod(0o755)
    except OSError:
        pass

    m_b = re.search(r'blztar = """\n([\s\S]*?)\n"""', bundle_script)
    if m_b:
        unbundle.blztar = m_b.group(1)
    integrity._BUNDLE_ASSET_CACHE = None

    diff_text = diff.render_diff(root)
    if diff_text:
        raise RuntimeError(f"Baseline diff is not clean after bundle synchronization:\n{diff_text}")

    pkg_ver = integrity.version(root=root)
    default_bundle_name = f"dwimsy_{pkg_ver}.py"
    bundle_path = root / default_bundle_name
    bundle_path.write_text(bundle_script, encoding="utf-8")
    try:
        bundle_path.chmod(0o755)
    except OSError:
        pass

    return bundle_path


def bump_version(
    version_str: Optional[str] = None,
    part: str = "patch",
    release: bool = False,
    dev: bool = False,
    message: Optional[str] = None,
    no_bundle: bool = False,
    repo_root: Optional[Path] = None,
    verbose: bool = False,
) -> str:
    """Advance revision, update metadata files, and optionally synchronize the baseline bundle."""
    root = integrity.find_repo_root(repo_root)
    values = integrity._version_values(root)
    current_ver = values.get("__version__", "0.1.6.0-dev")

    if version_str:
        new_ver = version_str
    else:
        new_ver = parse_and_bump_version(
            current_ver, part=part, release=release, dev=dev
        )

    update_version_files(new_ver, repo_root=root, message=message)

    if not no_bundle:
        bundle_path = sync_bundle_baseline(repo_root=root, verbose=verbose)
        if verbose:
            print(f"[SUCCESS] Advanced version: {current_ver} -> {new_ver}", file=sys.stderr)
            print(f"[SUCCESS] Reconstituted unbundle.py and generated {bundle_path.name}", file=sys.stderr)
    elif verbose:
        print(f"[SUCCESS] Advanced version files to {new_ver} (bundle sync skipped)", file=sys.stderr)

    return new_ver


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for running dwimsy.meta.version_bump directly."""
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
            pattern = ["meta version-bump"]
        return run_tests(pattern, verbose=verbosity)

    if any(a == "--help-all" for a in effective):
        effective = ["-h" if a == "--help-all" else a for a in effective]

    parser = argparse.ArgumentParser(
        prog="dwimsy-version-bump",
        description="Advance version revision, record changelog, and synchronize bundle baseline.",
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
        help="Run scoped version-bump self-tests in-process (optional pattern filter)",
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
        "target_version",
        nargs="?",
        default=None,
        help="Explicit new version string (e.g. '0.1.6.1-dev')",
    )
    parser.add_argument(
        "--patch",
        action="store_true",
        help="Increment patch component (default)",
    )
    parser.add_argument(
        "--minor",
        action="store_true",
        help="Increment minor component and reset patch",
    )
    parser.add_argument(
        "--major",
        action="store_true",
        help="Increment major component and reset minor and patch",
    )
    parser.add_argument(
        "--rev",
        action="store_true",
        help="Increment fourth revision/build digit",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Remove '-dev' suffix for a release milestone",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Ensure '-dev' suffix is present",
    )
    parser.add_argument(
        "-m",
        "--message",
        default=None,
        help="Changelog entry description message",
    )
    parser.add_argument(
        "--no-bundle",
        action="store_true",
        help="Update version files without synchronizing bundle baseline",
    )
    args = parser.parse_args(effective)

    if args.test is not False:
        from dwimsy.tests import run_tests
        pattern = [args.test] if isinstance(args.test, str) else ["meta version-bump"]
        return run_tests(pattern, verbose=max(args.verbose, 1))

    part = "patch"
    if args.major:
        part = "major"
    elif args.minor:
        part = "minor"
    elif args.rev:
        part = "rev"

    try:
        new_ver = bump_version(
            version_str=args.target_version,
            part=part,
            release=args.release,
            dev=args.dev,
            message=args.message,
            no_bundle=args.no_bundle,
            verbose=args.verbose > 0,
        )
        print(f"Version bumped to {new_ver}")
        return 0
    except Exception as e:
        print(f"Error bumping version: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
