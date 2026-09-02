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

_HERE = Path(__file__).resolve()
if len(_HERE.parts) >= 3 and _HERE.parts[-3] == "dwimsy" and _HERE.parts[-2] == "meta":
    _REPO_ROOT = _HERE.parents[2]
    if (_REPO_ROOT / "dwimsy" / "_version.py").is_file() and str(
        _REPO_ROOT
    ) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))

from dwimsy.meta import bundle, diff, integrity, unbundle, versions


def parse_and_bump_version(
    current: str,
    part: str = "patch",
    release: bool = False,
    dev: bool = False,
) -> str:
    """Derive next version string based on current and increment rules."""
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?(?:-([a-zA-Z0-9_.+-]+))?$", current)
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
    """Update dwimsy/_version.py, README.md, unbundle.py docstring, and CHANGELOG.md with new_version."""
    root = integrity.find_repo_root(repo_root)
    today_str = datetime.date.today().isoformat()

    # 1. Update dwimsy/_version.py
    version_file = root / "dwimsy" / "_version.py"
    if version_file.is_file():
        text = version_file.read_text(encoding="utf-8")
        text = re.sub(
            r'__version__\s*=\s*["\x27][^"\x27]+["\x27]',
            f'__version__ = "{new_version}"',
            text,
        )
        version_file.write_text(text, encoding="utf-8")

    # 2. Update CHANGELOG.md
    changelog_file = root / "CHANGELOG.md"
    if changelog_file.is_file():
        c_text = changelog_file.read_text(encoding="utf-8")
        header = f"## [{new_version}] - {today_str}"
        if header not in c_text:
            msg_entry = (
                f"- {message}"
                if message
                else "- Maintenance release and baseline synchronization."
            )
            entry = f"{header}\n\n### Changed\n{msg_entry}"
            match = re.search(r"(## \[[^\]]+\] - \d{4}-\d{2}-\d{2})", c_text)
            if match:
                prefix = c_text[: match.start()].rstrip() + "\n\n"
                suffix = c_text[match.start() :].lstrip()
                c_text = prefix + entry + "\n\n" + suffix
            else:
                c_text = c_text.rstrip() + "\n\n" + entry + "\n"
            c_text = re.sub(r"\n{3,}", "\n\n", c_text).rstrip() + "\n"
            changelog_file.write_text(c_text, encoding="utf-8")

    # 3. Update README.md
    readme_file = root / "README.md"
    if readme_file.is_file():
        r_text = readme_file.read_text(encoding="utf-8")
        r_text = re.sub(
            r"\*\*Version:\s*([^*]+)\*\*\s*\(([^,)]+,\s*)?\d{4}-\d{2}-\d{2}\)",
            f"**Version: {new_version}** (\\g<2>{today_str})",
            r_text,
        )
        r_text = re.sub(
            r"(### Standalone Bundle Basics[\s\S]*?Version:\s*)[^\n]+",
            f"\\g<1>{new_version} ({today_str})",
            r_text,
        )
        r_text = re.sub(
            r"dwimsy_\d+\.\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9_.-]+)?\.py",
            f"dwimsy_{new_version}.py",
            r_text,
        )
        readme_file.write_text(r_text, encoding="utf-8")

    # 4. Update dwimsy/meta/unbundle.py docstring
    unbundle_file = root / "dwimsy" / "meta" / "unbundle.py"
    if unbundle_file.is_file():
        u_text = unbundle_file.read_text(encoding="utf-8")
        q3 = chr(34) * 3
        new_doc = (
            q3
            + "dwimsy.meta.unbundle - Standalone self-extracting payload and in-memory asset provider.\n\n"
            + "Project Homepage: https://github.com/f-fix/dwimsy\n"
            + f"Version: {new_version} ({today_str})\n\n"
            + "dwimsy - retrocomputing media preservation, demodulation, restoration, and preparation.\n"
            + "A modular toolkit for vintage computer tapes, disks, ROMs, and audio captures.\n\n"
            + f"This standalone script is also distributed as dwimsy_{new_version}.py.\n\n"
            + "Bundle Basics:\n"
            + "To use the embedded dwimsy CLI directly from the bundle:\n"
            + f"  python3 dwimsy_{new_version}.py dwimsy --help\n"
            + f"  python3 dwimsy_{new_version}.py dwimsy --version\n"
            + f"  python3 dwimsy_{new_version}.py dwimsy readme\n"
            + f"  python3 dwimsy_{new_version}.py dwimsy license\n"
            + f"  python3 dwimsy_{new_version}.py dwimsy changelog\n\n"
            + "To extract the repository tree to disk:\n"
            + f"  python3 dwimsy_{new_version}.py meta unbundle /path/to/target --deps\n"
            + q3
        )
        u_text = re.sub(
            r'"""dwimsy\.meta\.unbundle - .*?"""',
            lambda m: new_doc,
            u_text,
            flags=re.DOTALL,
        )
        unbundle_file.write_text(u_text, encoding="utf-8")


def _set_layer_version_tag(
    files: dict[str, bytes], version_tag: str
) -> dict[str, bytes]:
    """Return layer files with _version.py carrying the serialized layer tag."""
    result = dict(files)
    for path in ("dwimsy/_version.py", "_version.py"):
        if path in result:
            text = result[path].decode("utf-8", errors="strict")
            text = re.sub(
                r'(__version__\s*=\s*["\'])[^"\']*(["\'])',
                lambda m: m.group(1) + version_tag + m.group(2),
                text,
                count=1,
            )
            result[path] = text.encode("utf-8")
            break
    return result


def sync_bundle_baseline(
    repo_root: Optional[Path] = None, verbose: bool = False, *, release: bool = False
) -> Path:
    """Synchronize the embedded VersionSpace with the current working tree."""
    root = integrity.find_repo_root(repo_root)
    unbundle_file = root / "dwimsy" / "meta" / "unbundle.py"

    # Preserve the existing stream history and append the current working tree
    # as a delta rather than replacing the history with a flat snapshot.
    space = versions.VersionSpace.from_blztar(unbundle.blztar)
    primary = space.streams[0]
    old_head = primary.get_head_version()
    old_state = primary.materialize_layer_state(old_head.ordinal) if old_head else {}
    new_state = bundle.create_tree_state(root, with_deps=True)
    delta = versions.compute_tree_delta(old_state, new_state)
    if "dwimsy/_version.py" in new_state:
        delta["dwimsy/_version.py"] = new_state["dwimsy/_version.py"]
    new_tag = integrity._version_values(root).get("__version__", "0.1.6.0-dev")
    delta = _set_layer_version_tag(delta, new_tag)
    if old_head and (
        old_head.tag.split("+")[0].lower() == new_tag.split("+")[0].lower()
        or "+mod." in old_head.tag.lower()
    ):
        primary.append_layer(
            versions.Layer(delta, is_delta=True, version_tag=new_tag),
            allow_replacement=True,
        )
    elif delta or not old_head:
        primary.append_layer(versions.Layer(delta, is_delta=True, version_tag=new_tag))

    if release:
        primary.seal_open_dev()
        # The sealed state carries the canonical hash in _version.py; write it
        # back to the live tree before serializing the final bundle.
        sealed_state = primary.materialize_layer_state(0)
        vpath = root / "dwimsy" / "_version.py"
        if "dwimsy/_version.py" in sealed_state:
            vpath.write_bytes(sealed_state["dwimsy/_version.py"])
        elif "_version.py" in sealed_state:
            vpath.write_bytes(sealed_state["_version.py"])

    bundle_script = bundle.build_bundle_script(
        repo_root=root, with_deps=True, version_space=space
    )
    unbundle_file.write_text(bundle_script, encoding="utf-8")
    try:
        unbundle_file.chmod(0o755)
    except OSError:
        pass

    m_b = re.search(r'blztar = """\n([\s\S]*?)\n"""', bundle_script)
    if m_b:
        unbundle.blztar = m_b.group(1)
    integrity.clear_integrity_cache()

    pkg_ver = integrity.version(root=root).split("+")[0]
    bundle_path = root / space.composite_bundle_name(".py")
    bundle_path.write_text(bundle_script, encoding="utf-8")
    try:
        bundle_path.chmod(0o755)
    except OSError:
        pass
    pyz_path = root / space.composite_bundle_name(".pyz")
    try:
        bundle.write_pyz_bundle(bundle_script, pyz_path)
    except Exception:
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
    if not message or not message.strip():
        raise ValueError(
            "A non-empty changelog message is required for every version bump."
        )
    if version_str is None and part not in ("major", "minor", "patch", "rev", "build"):
        raise ValueError(
            "An explicit bump tier (--major, --minor, --patch, or --rev) is required when no target version is supplied."
        )

    root = integrity.find_repo_root(repo_root)
    values = integrity._version_values(root)
    current_ver = values.get("__version__", "0.1.6.0-dev")

    if version_str:
        versions.validate_version_tag(version_str)
        new_ver = version_str
    else:
        new_ver = parse_and_bump_version(
            current_ver, part=part, release=release, dev=dev
        )
        versions.validate_version_tag(new_ver)

    update_version_files(new_ver, repo_root=root, message=message)

    if not no_bundle:
        from dwimsy.tests import run_tests
        import io

        test_buf = io.StringIO()
        old_env = os.environ.get("DWIMSY_BUNDLE_BUILD")
        os.environ["DWIMSY_BUNDLE_BUILD"] = "1"
        try:
            rc = run_tests(repo_root=root, stream=test_buf)
        finally:
            if old_env is None:
                os.environ.pop("DWIMSY_BUNDLE_BUILD", None)
            else:
                os.environ["DWIMSY_BUNDLE_BUILD"] = old_env
        if rc != 0:
            raise RuntimeError(
                f"Cannot bump version: test suite failed with {rc} error(s).\n{test_buf.getvalue()}"
            )

    if not no_bundle:
        bundle_path = sync_bundle_baseline(
            repo_root=root, verbose=verbose, release=release
        )
        if verbose:
            print(
                f"[SUCCESS] Advanced version: {current_ver} -> {new_ver}",
                file=sys.stderr,
            )
            print(
                f"[SUCCESS] Reconstituted unbundle.py and generated {bundle_path.name}",
                file=sys.stderr,
            )
    elif verbose:
        print(
            f"[SUCCESS] Advanced version files to {new_ver} (bundle sync skipped)",
            file=sys.stderr,
        )

    return new_ver


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for running dwimsy.meta.version_bump directly."""
    effective = sys.argv[1:] if argv is None else list(argv)
    from dwimsy.cli.dispatch import early_dispatch

    handled, effective = early_dispatch(
        effective, ["meta", "version-bump"], use_process_argv0=(argv is None)
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
        action=integrity._LazyVersionAction,
        version_fn=integrity.version,
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
        "-v", "--verbose", action="count", default=0, help="Increase output verbosity"
    )
    parser.add_argument(
        "--help-all", action="store_true", help="Show full help documentation and exit"
    )
    parser.add_argument(
        "target_version",
        nargs="?",
        default=None,
        help="Explicit new version string (e.g. '0.1.6.1-dev')",
    )
    parser.add_argument(
        "--set-version",
        dest="set_version",
        default=None,
        help="Explicit new version string (alias for the positional target version)",
    )
    parser.add_argument(
        "--patch", action="store_true", help="Increment patch component (default)"
    )
    parser.add_argument(
        "--minor", action="store_true", help="Increment minor component and reset patch"
    )
    parser.add_argument(
        "--major",
        action="store_true",
        help="Increment major component and reset minor and patch",
    )
    parser.add_argument(
        "--rev", action="store_true", help="Increment fourth revision/build digit"
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Remove '-dev' suffix for a release milestone",
    )
    parser.add_argument(
        "--dev", action="store_true", help="Ensure '-dev' suffix is present"
    )
    parser.add_argument(
        "-m", "--message", default=None, help="Changelog entry description message"
    )
    parser.add_argument(
        "--no-bundle",
        action="store_true",
        help="Update version files without synchronizing bundle baseline",
    )
    args = parser.parse_args(effective)

    if args.target_version is not None and args.set_version is not None:
        parser.error("target_version and --set-version are mutually exclusive")
    explicit_version = (
        args.set_version if args.set_version is not None else args.target_version
    )

    if args.test is not False:
        from dwimsy.tests import run_tests

        pattern = [args.test] if isinstance(args.test, str) else ["meta version-bump"]
        return run_tests(pattern, verbose=max(args.verbose, 1))

    tier_flags = [args.major, args.minor, args.patch, args.rev]
    if sum(bool(x) for x in tier_flags) > 1:
        parser.error("bump tiers are mutually exclusive")
    if explicit_version is None and not any(tier_flags):
        parser.error(
            "specify an explicit target version or a bump tier (--major, --minor, --patch, or --rev)"
        )
    if not args.message or not args.message.strip():
        parser.error("a non-empty changelog message is required (-m/--message)")

    part = "patch"
    if args.major:
        part = "major"
    elif args.minor:
        part = "minor"
    elif args.rev:
        part = "rev"

    try:
        new_ver = bump_version(
            version_str=explicit_version,
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
