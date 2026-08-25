"""dwimsy.meta.integrity - Canonical source-tree hashing and runtime modification detection.

The integrity hash covers the canonical source and test files of the project.
Files are ordered by their POSIX relative path, source text is normalized to LF line
endings, and the sealed ``__code_hash__`` value in ``_version.py`` is replaced
with the empty sentinel before hashing. This makes the recorded hash
self-referentially stable.
"""

from __future__ import annotations

import hashlib
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


def source_files(root: Optional[Path] = None) -> Tuple[Path, ...]:
    """Return canonical source and test files in sorted relative-path order."""
    repo = find_repo_root(root) if root is None else Path(root)
    if (repo / "dwimsy").is_dir() and (repo / "dwimsy" / "__init__.py").is_file():
        files: list[Path] = []
        for top_name in (".gitignore", ".gitmodules", "LICENSE", "README.md"):
            p = repo / top_name
            if p.is_file():
                files.append(p)
        for p in (repo / "dwimsy").rglob("*.py"):
            if p.is_file() and p.name != "unbundle.py":
                files.append(p)
        if (repo / "tests").is_dir():
            for p in (repo / "tests").rglob("*"):
                if p.is_file() and p.suffix in (".py", ".md"):
                    files.append(p)
        return tuple(sorted(files, key=lambda p: p.relative_to(repo).as_posix()))
    elif (repo / "_version.py").is_file() or (repo / "__init__.py").is_file():
        files = [
            p for p in repo.rglob("*.py") if p.is_file() and p.name != "unbundle.py"
        ]
        return tuple(sorted(files, key=lambda p: p.relative_to(repo).as_posix()))
    else:
        files = [
            p
            for p in repo.rglob("*")
            if p.is_file()
            and p.name != "unbundle.py"
            and (
                p.suffix in (".py", ".md")
                or p.name in (".gitignore", ".gitmodules", "LICENSE", "README.md")
            )
        ]
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
    """Calculate the canonical SHA-256 hash of the dwimsy source and test tree.

    Each file contributes its POSIX relative path, a NUL separator, its
    normalized source bytes, and a second NUL separator. Including the path
    prevents two different file layouts from producing the same byte stream.
    """
    from dwimsy.meta import unbundle

    repo = find_repo_root(root) if root is None else Path(root)
    digest = hashlib.sha256()

    if (repo / "dwimsy").is_dir() and (repo / "dwimsy" / "__init__.py").is_file():
        canonical_rel_paths = []
        for top_name in (".gitignore", ".gitmodules", "LICENSE", "README.md"):
            canonical_rel_paths.append(top_name)
        for p in sorted((repo / "dwimsy").rglob("*.py")):
            if p.is_file() and p.name != "unbundle.py":
                canonical_rel_paths.append(p.relative_to(repo).as_posix())
        if (repo / "tests").is_dir():
            for p in sorted((repo / "tests").rglob("*")):
                if p.is_file() and p.suffix in (".py", ".md"):
                    canonical_rel_paths.append(p.relative_to(repo).as_posix())
        else:
            try:
                for a in unbundle.list_assets():
                    if (
                        a.startswith("tests/")
                        and (a.endswith(".py") or a.endswith(".md"))
                    ) or a in (".gitignore", ".gitmodules", "LICENSE", "README.md"):
                        if a not in canonical_rel_paths:
                            canonical_rel_paths.append(a)
            except Exception:
                pass

        for rel in sorted(set(canonical_rel_paths)):
            disk_p = repo / rel
            if disk_p.is_file():
                raw = disk_p.read_bytes()
            else:
                try:
                    raw = unbundle.get_asset(rel)
                except Exception:
                    continue
            cdata = _canonical_bytes(raw, rel)
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(cdata)
            digest.update(b"\0")
    else:
        for p in source_files(repo):
            rel = p.relative_to(repo).as_posix()
            cdata = _canonical_bytes(p.read_bytes(), rel)
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(cdata)
            digest.update(b"\0")

    return digest.hexdigest()


def sealed_code_hash(root: Optional[Path] = None) -> str:
    """Return the recorded canonical hash, or ``\"\"`` when unsealed."""
    v_file = version_file_path(root)
    namespace: dict[str, object] = {}
    source = v_file.read_text(encoding="utf-8")
    exec(compile(source, str(v_file), "exec"), namespace)
    value = namespace.get("__code_hash__", "")
    if not isinstance(value, str):
        raise TypeError("__code_hash__ must be a string")
    return value.lower()


def is_modified(root: Optional[Path] = None) -> bool:
    """Return whether the current source differs from its sealed hash.

    An empty/unsealed hash is considered modified. That is intentional: an
    unsealed development tree cannot claim to be a canonical baseline.
    """
    v_file = version_file_path(root)
    if not v_file.is_file():
        return False
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
        v_file = version_file_path(root)
        if v_file.is_file():
            namespace: dict[str, object] = {}
            source = v_file.read_text(encoding="utf-8")
            exec(compile(source, str(v_file), "exec"), namespace)
            base_version = namespace.get("__version__")
        else:
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
    "find_repo_root",
    "is_modified",
    "modification_hash",
    "package_root",
    "sealed_code_hash",
    "source_files",
    "version",
]
