"""dwimsy.meta.diff - Compare a working tree with the embedded baseline."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Optional

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


__all__ = ["render_diff"]
