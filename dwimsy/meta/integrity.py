#!/usr/bin/env python3
"""dwimsy.meta.integrity - Canonical portable-project hashing and runtime modification detection.

The integrity hash covers the canonical project window used by portable bundles:
native Python code, tests, project metadata, and the dependency paths declared by
``.gitmodules``. Files are ordered by POSIX relative path, text is normalized to LF
line endings, and the sealed ``__code_hash__`` value in ``_version.py`` is replaced
with the empty sentinel before hashing.
"""

from __future__ import annotations

import hashlib
import ast
import fnmatch
import re
import sys
import os
from pathlib import Path
from typing import Iterable, Optional, Tuple

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_BUNDLE_ASSET_CACHE: Optional[dict[str, bytes]] = None
_VERSION_FILE = _PACKAGE_ROOT / "_version.py"
_UNBUNDLE_RE = re.compile(rb'(?ms)^(?P<prefix>[ \t]*blztar[ \t]*=[ \t]*\"\"\")(?:.*?)(?P<suffix>\"\"\"[ \t]*(?:#.*)?$)')
_HASH_RE = re.compile(
    rb"(?m)^(?P<prefix>[ \t]*__code_hash__[ \t]*=[ \t]*)"
    rb"(?P<quote>['\"])[^'\"]*(?P=quote)(?P<suffix>[ \t]*(?:#.*)?\r?\n?)$"
)


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Locate the root directory of the dwimsy repository or extracted tree."""
    if start is not None:
        cur = Path(start).resolve()
        while cur != cur.parent:
            if (cur / "dwimsy").is_dir() and (cur / "dwimsy" / "__init__.py").is_file():
                return cur
            cur = cur.parent
        return Path(start).resolve()

    test_root = os.environ.get("DWIMSY_TEST_REPO_ROOT")
    if test_root:
        candidate = Path(test_root).resolve()
        if (candidate / "dwimsy").is_dir():
            return candidate

    cur = Path.cwd().resolve()
    while cur != cur.parent:
        if (cur / "dwimsy").is_dir() and (cur / "dwimsy" / "__init__.py").is_file():
            return cur
        cur = cur.parent

    cur = Path(__file__).resolve().parent
    while cur != cur.parent:
        if (cur / "dwimsy").is_dir() and (cur / "dwimsy" / "__init__.py").is_file():
            return cur
        cur = cur.parent

    for sp in sys.path:
        if sp:
            p = Path(sp).resolve()
            if (p / "dwimsy").is_dir() and (p / "dwimsy" / "__init__.py").is_file():
                return p

    return Path.cwd().resolve()


def package_root() -> Path:
    """Return the on-disk ``dwimsy`` package root."""
    repo = find_repo_root()
    if (repo / "dwimsy").is_dir():
        return repo / "dwimsy"
    return _PACKAGE_ROOT


def version_file_path(root: Optional[Path] = None) -> Path:
    """Locate on-disk _version.py path."""
    repo = find_repo_root(root) if root is not None else find_repo_root()
    if (repo / "dwimsy" / "_version.py").is_file():
        return repo / "dwimsy" / "_version.py"
    if (repo / "_version.py").is_file():
        return repo / "_version.py"
    return _VERSION_FILE


def canonical_manifest(root: Optional[Path] = None, baseline: bool = False) -> Tuple[str, ...]:
    """Return the canonical portable-project manifest patterns.

    The manifest covers native Python code, tests, canonical project metadata,
    and one lazy recursive glob for each path declared by .gitmodules.
    """
    repo = find_repo_root(root) if root is None else Path(root).resolve()
    patterns = [
        "dwimsy/**/*.py",
        "tests/**/*.py",
        "tests/**/*.md",
        ".gitignore",
        ".gitmodules",
        "LICENSE",
        "README.md",
        "CHANGELOG.md",
    ]
    gitmodules = repo / ".gitmodules"
    gitmodules_text = None
    if not baseline and gitmodules.is_file():
        gitmodules_text = gitmodules.read_text(encoding="utf-8")
    if gitmodules_text is None:
        try:
            from dwimsy.meta import unbundle
            gitmodules_text = unbundle.get_asset_text(".gitmodules")
        except Exception:
            pass
    if gitmodules_text is not None:
        for line in gitmodules_text.splitlines():
            m = re.match(r"\s*path\s*=\s*(\S+)\s*$", line)
            if m:
                path = m.group(1).strip("/")
                patterns.append(f"{path}/**/*")
    return tuple(patterns)


def _manifest_matches(rel_path: str, patterns: Iterable[str]) -> bool:
    """Return whether a normalized relative path belongs to a manifest glob."""
    for pattern in patterns:
        if fnmatch.fnmatchcase(rel_path, pattern):
            return True
        # Treat **/ as zero or more directory components.
        if "**/" in pattern:
            if fnmatch.fnmatchcase(rel_path, pattern.replace("**/", "", 1)):
                return True
        if pattern.endswith("/**/*"):
            prefix = pattern[:-4]
            if rel_path == prefix or rel_path.startswith(prefix + "/"):
                return True
    return False


def source_files(root: Optional[Path] = None) -> Tuple[Path, ...]:
    """Return canonical on-disk files selected by the portable manifest."""
    repo = find_repo_root(root) if root is None else Path(root).resolve()
    patterns = canonical_manifest(repo)
    if not ((repo / "dwimsy").is_dir() and (repo / "dwimsy" / "__init__.py").is_file()):
        return ()
    files = []
    for p in repo.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(repo).as_posix()
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        if _manifest_matches(rel, patterns):
            files.append(p)
    return tuple(sorted(files, key=lambda p: p.relative_to(repo).as_posix()))

def _canonical_bytes(data: bytes, rel_path: str) -> bytes:
    """Return normalized bytes for one source or asset file."""
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if data and not data.endswith(b"\n"):
        data = data + b"\n"
    if rel_path == "dwimsy/meta/unbundle.py":
        match = _UNBUNDLE_RE.search(data)
        if match is None:
            raise ValueError("dwimsy/meta/unbundle.py does not contain a blztar assignment")
        data = (
            data[: match.start()]
            + match.group("prefix")
            + b"\n"
            + match.group("suffix")
            + data[match.end() :]
        )
    if (
        rel_path == "dwimsy/_version.py"
        or rel_path == "_version.py"
        or rel_path.endswith("/_version.py")
    ):
        match = _HASH_RE.search(data)
        if match is None:
            raise ValueError(
                f"{rel_path} does not contain the required __code_hash__ sentinel"
            )
        replacement = (
            match.group("prefix")
            + match.group("quote")
            + match.group("quote")
            + match.group("suffix")
        )
        data = data[: match.start()] + replacement + data[match.end() :]
    return data


def canonical_assets(root: Optional[Path] = None, baseline: bool = False) -> dict[str, bytes]:
    """Return canonical portable-project assets before content normalization."""
    from dwimsy.meta import unbundle

    repo = find_repo_root(root) if root is None else Path(root).resolve()
    patterns = canonical_manifest(repo, baseline=baseline)
    candidates: dict[str, bytes] = {}

    if not baseline:
        for p in source_files(repo):
            candidates[p.relative_to(repo).as_posix()] = p.read_bytes()

    try:
        need_bundle = baseline or not candidates
        if not need_bundle:
            required_top = (".gitignore", ".gitmodules", "LICENSE", "README.md")
            need_bundle = not all(name in candidates for name in required_top)
            if not need_bundle:
                dep_prefixes = [
                    pattern[:-5] for pattern in patterns if pattern.endswith("/**/*")
                ]
                need_bundle = any(
                    not any(rel == prefix or rel.startswith(prefix + "/") for rel in candidates)
                    for prefix in dep_prefixes
                )
        if need_bundle:
            global _BUNDLE_ASSET_CACHE
            if _BUNDLE_ASSET_CACHE is None:
                _BUNDLE_ASSET_CACHE = {
                    (asset[2:] if asset.startswith("./") else asset): unbundle.get_asset(asset)
                    for asset in unbundle.list_assets()
                }
            for rel, data in _BUNDLE_ASSET_CACHE.items():
                if _manifest_matches(rel, patterns) and (baseline or rel not in candidates):
                    candidates[rel] = data
    except Exception:
        if baseline:
            raise
    return dict(sorted(candidates.items()))


def canonical_code_hash(root: Optional[Path] = None, baseline: bool = False) -> str:
    """Calculate the canonical SHA-256 hash of the portable project window."""
    digest = hashlib.sha256()
    for rel, data in canonical_assets(root, baseline=baseline).items():
        cdata = _canonical_bytes(data, rel)
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(cdata)
        digest.update(b"\0")
    return digest.hexdigest()

def _version_values(root: Optional[Path] = None, baseline: bool = False) -> dict[str, str]:
    """Read version metadata from disk or the in-memory portable bundle."""
    v_file = version_file_path(root)
    if v_file.is_file() and not baseline:
        source = v_file.read_text(encoding="utf-8")
        filename = str(v_file)
    else:
        from dwimsy.meta import unbundle

        try:
            source = unbundle.get_asset_text("dwimsy/_version.py")
        except Exception:
            source = unbundle.get_asset_text("_version.py")
        filename = "<dwimsy-bundle>/dwimsy/_version.py"
    tree = ast.parse(source, filename=filename)
    values: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in {"__version__", "__code_hash__"}:
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    values[target.id] = node.value.value
    return values

def sealed_code_hash(root: Optional[Path] = None, baseline: bool = False) -> str:
    """Return the recorded canonical hash, or ``\"\"`` when unsealed."""
    values = _version_values(root)
    return values.get("__code_hash__", "").lower()


def is_modified(root: Optional[Path] = None, baseline: bool = False) -> bool:
    """Return whether the current source differs from its sealed hash.

    An empty/unsealed hash is considered modified. That is intentional: an
    unsealed development tree cannot claim to be a canonical baseline.
    """
    current = canonical_code_hash(root, baseline=baseline)
    sealed = sealed_code_hash(root, baseline=baseline)
    return not sealed or current != sealed


def modification_hash(root: Optional[Path] = None, length: int = 12, baseline: bool = False) -> str:
    """Return the short current canonical hash used for ``+mod.`` versions."""
    if length < 1:
        raise ValueError("length must be positive")
    return canonical_code_hash(root, baseline=baseline)[:length]


def version(base_version: Optional[str] = None, root: Optional[Path] = None) -> str:
    """Return the package version, adding a PEP 440 local ``+mod.`` suffix.

    If no base version is supplied it is read from ``dwimsy._version``.
    """
    if base_version is None:
        values = _version_values(root)
        base_version = values.get("__version__")
        if not base_version:
            try:
                import dwimsy._version as _v_mod

                base_version = getattr(_v_mod, "__version__", None)
            except Exception:
                pass
        if not isinstance(base_version, str) or not base_version:
            raise ValueError("__version__ must be a non-empty string")

    if is_modified(root):
        return f"{base_version}+mod.{modification_hash(root)}"
    return base_version


__all__ = [
    "canonical_assets",
    "canonical_code_hash",
    "canonical_manifest",
    "find_repo_root",
    "is_modified",
    "modification_hash",
    "package_root",
    "sealed_code_hash",
    "source_files",
    "version",
]


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for running dwimsy.meta.integrity directly."""
    import argparse
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
            pattern = ["meta integrity"]
        return run_tests(pattern, verbose=verbosity)

    if any(a == "--help-all" for a in effective):
        effective = ["-h" if a == "--help-all" else a for a in effective]

    parser = argparse.ArgumentParser(
        prog="dwimsy-integrity",
        description="Verify canonical portable-project integrity and hash status.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {version()}",
    )
    parser.add_argument(
        "-T",
        "--test",
        nargs="?",
        const=True,
        default=False,
        help="Run scoped integrity self-tests in-process (optional pattern filter)",
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
        "--baseline",
        action="store_true",
        help="Inspect the embedded portable baseline instead of working tree on disk",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress output and exit with 0 if clean, 1 if modified",
    )
    args = parser.parse_args(effective)

    if args.test is not False:
        from dwimsy.tests import run_tests
        pattern = [args.test] if isinstance(args.test, str) else ["meta integrity"]
        return run_tests(pattern, verbose=max(args.verbose, 1))

    baseline = args.baseline
    current = canonical_code_hash(baseline=baseline)
    sealed = sealed_code_hash(baseline=baseline)
    modified = is_modified(baseline=baseline)
    ver_str = version() if not baseline else _version_values(baseline=True).get("__version__", "")

    if not args.quiet:
        print(f"Canonical hash : {current}")
        print(f"Sealed hash    : {sealed or '(unsealed)'}")
        print(f"Status         : {'MODIFIED' if modified else 'CLEAN'}")
        print(f"Version        : {ver_str}")

    return 1 if modified else 0


if __name__ == "__main__":
    sys.exit(main())
