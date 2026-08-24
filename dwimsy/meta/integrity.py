"""dwimsy.meta.integrity - Canonical source-tree hashing and runtime modification detection.

The integrity hash covers the Python source under ``dwimsy/`` only.  Files are
ordered by their POSIX relative path, source text is normalized to LF line
endings, and the sealed ``__code_hash__`` value in ``_version.py`` is replaced
with the empty sentinel before hashing.  This makes the recorded hash
self-referentially stable.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable, Optional, Tuple

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_VERSION_FILE = _PACKAGE_ROOT / "_version.py"
_HASH_RE = re.compile(
    rb"(?m)^(?P<prefix>[ \t]*__code_hash__[ \t]*=[ \t]*)"
    rb"(?P<quote>['\"])[^'\"]*(?P=quote)(?P<suffix>[ \t]*(?:#.*)?\r?\n?)$"
)


def package_root() -> Path:
    """Return the on-disk ``dwimsy`` package root."""
    return _PACKAGE_ROOT


def source_files(root: Optional[Path] = None) -> Tuple[Path, ...]:
    """Return canonical Python source files in sorted relative-path order."""
    root = Path(root) if root is not None else _PACKAGE_ROOT
    files = [p for p in root.rglob("*.py") if p.is_file()]
    return tuple(sorted(files, key=lambda p: p.relative_to(root).as_posix()))


def _canonical_bytes(path: Path, root: Path) -> bytes:
    """Return normalized bytes for one source file."""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    data = data.replace(b"\r", b"\n")

    if path.resolve() == (root / "_version.py").resolve():
        match = _HASH_RE.search(data)
        if match is None:
            raise ValueError(
                f"{path} does not contain the required __code_hash__ sentinel"
            )
        replacement = (
            match.group("prefix") + match.group("quote") + match.group("quote")
            + match.group("suffix")
        )
        data = data[: match.start()] + replacement + data[match.end() :]

    return data


def canonical_code_hash(root: Optional[Path] = None) -> str:
    """Calculate the canonical SHA-256 hash of the dwimsy Python source tree.

    Each file contributes its POSIX relative path, a NUL separator, its
    normalized source bytes, and a second NUL separator.  Including the path
    prevents two different file layouts from producing the same byte stream.
    """
    root = Path(root) if root is not None else _PACKAGE_ROOT
    digest = hashlib.sha256()
    for path in source_files(root):
        rel = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(rel)
        digest.update(b"\0")
        digest.update(_canonical_bytes(path, root))
        digest.update(b"\0")
    return digest.hexdigest()


def sealed_code_hash() -> str:
    """Return the recorded canonical hash, or ``""`` when unsealed."""
    namespace: dict[str, object] = {}
    source = _VERSION_FILE.read_text(encoding="utf-8")
    exec(compile(source, str(_VERSION_FILE), "exec"), namespace)
    value = namespace.get("__code_hash__", "")
    if not isinstance(value, str):
        raise TypeError("__code_hash__ must be a string")
    return value.lower()


def is_modified(root: Optional[Path] = None) -> bool:
    """Return whether the current source differs from its sealed hash.

    An empty/unsealed hash is considered modified.  That is intentional: an
    unsealed development tree cannot claim to be a canonical baseline.
    """
    current = canonical_code_hash(root)
    sealed = sealed_code_hash()
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
        namespace: dict[str, object] = {}
        source = _VERSION_FILE.read_text(encoding="utf-8")
        exec(compile(source, str(_VERSION_FILE), "exec"), namespace)
        base_version = namespace.get("__version__")
        if not isinstance(base_version, str) or not base_version:
            raise ValueError("__version__ must be a non-empty string")

    if is_modified(root):
        return f"{base_version}+mod.{modification_hash(root)}"
    return base_version


__all__ = [
    "canonical_code_hash",
    "is_modified",
    "modification_hash",
    "package_root",
    "sealed_code_hash",
    "source_files",
    "version",
]
