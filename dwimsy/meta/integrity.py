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
from pathlib import Path
from typing import Iterable, Optional, Tuple

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_VERSION_FILE = _PACKAGE_ROOT / "_version.py"
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


def canonical_manifest(root: Optional[Path] = None) -> Tuple[str, ...]:
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
    ]
    gitmodules = repo / ".gitmodules"
    gitmodules_text = None
    if gitmodules.is_file():
        gitmodules_text = gitmodules.read_text(encoding="utf-8")
    else:
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
        if rel == "dwimsy/meta/unbundle.py":
            continue
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


def canonical_code_hash(root: Optional[Path] = None) -> str:
    """Calculate the canonical SHA-256 hash of the portable project window.

    Each selected file contributes its POSIX relative path, a NUL separator,
    normalized content bytes, and a second NUL separator. The launcher
    ``dwimsy/meta/unbundle.py`` is excluded because it contains the bundle
    payload itself and is therefore generated from the files being hashed.
    """
    from dwimsy.meta import unbundle

    repo = find_repo_root(root) if root is None else Path(root).resolve()
    patterns = canonical_manifest(repo)
    candidates = {}

    for p in source_files(repo):
        candidates[p.relative_to(repo).as_posix()] = p.read_bytes()

    # A portable bundle may carry canonical assets even when they are not on
    # disk. Only open/decompress the embedded payload when the on-disk window
    # is incomplete; normal source checkouts should not pay that cost.
    required_top = (".gitignore", ".gitmodules", "LICENSE", "README.md")
    needs_fallback = not all(name in candidates for name in required_top)
    if not needs_fallback:
        dep_prefixes = [
            pattern[:-5] for pattern in patterns if pattern.endswith("/**/*")
        ]
        if dep_prefixes and not all(
            any(rel == prefix or rel.startswith(prefix + "/") for rel in candidates)
            for prefix in dep_prefixes
        ):
            needs_fallback = True
    try:
        if needs_fallback:
            for asset in unbundle.list_assets():
                rel = asset[2:] if asset.startswith("./") else asset
                if rel == "dwimsy/meta/unbundle.py":
                    continue
                if _manifest_matches(rel, patterns) and rel not in candidates:
                    candidates[rel] = unbundle.get_asset(rel)
    except Exception:
        pass

    digest = hashlib.sha256()
    for rel in sorted(candidates):
        cdata = _canonical_bytes(candidates[rel], rel)
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(cdata)
        digest.update(b"\0")
    return digest.hexdigest()


def _version_values(root: Optional[Path] = None) -> dict[str, str]:
    """Read version metadata from disk or the in-memory portable bundle."""
    v_file = version_file_path(root)
    if v_file.is_file():
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

def sealed_code_hash(root: Optional[Path] = None) -> str:
    """Return the recorded canonical hash, or ``\"\"`` when unsealed."""
    values = _version_values(root)
    return values.get("__code_hash__", "").lower()


def is_modified(root: Optional[Path] = None) -> bool:
    """Return whether the current source differs from its sealed hash.

    An empty/unsealed hash is considered modified. That is intentional: an
    unsealed development tree cannot claim to be a canonical baseline.
    """
    current = canonical_code_hash(root)
    sealed = sealed_code_hash(root)
    return not sealed or current != sealed


def modification_hash(root: Optional[Path] = None, length: int = 12) -> str:
    """Return the short current canonical hash used for ``+mod.`` versions."""
    if length < 1:
        raise ValueError("length must be positive")
    return canonical_code_hash(root)[:length]


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
