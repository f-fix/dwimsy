#!/usr/bin/env python3
"""dwimsy.meta.bundle - Maintainer tool for building self-extracting dwimsy bundles."""

from __future__ import annotations

import argparse
import base64
import io
import lzma
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import List, Optional

from dwimsy.meta import integrity, unbundle


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Locate the root directory of the dwimsy repository or extracted tree."""
    cur = Path(start).resolve() if start is not None else Path(__file__).resolve().parent.parent.parent
    while cur != cur.parent:
        if (cur / "dwimsy").is_dir() and (cur / "dwimsy" / "__init__.py").is_file():
            return cur
        cur = cur.parent
    return Path(start).resolve() if start is not None else Path(__file__).resolve().parent.parent.parent


def create_tar_archive(repo_root: Path, with_deps: bool = False) -> bytes:
    """Create a deterministic in-memory TAR byte stream of the repository tree."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        entries: List[Path] = []
        for p in repo_root.rglob("*"):
            rel = p.relative_to(repo_root)
            parts = rel.parts

            # Exclude version control, caches, backup files
            if any(part in (".git", "__pycache__", ".pytest_cache") for part in parts):
                continue
            if not with_deps and parts and parts[0] == "deps":
                continue
            if p.suffix in (".pyc", ".wav", ".t88", ".cmt") or p.name.endswith("~"):
                continue
            # Exclude unbundle.py and unpacker scripts
            if p.name in ("unbundle.py", "restore_dwimsy.py") or (p.name.startswith("dwimsy_") and p.name.endswith(".py")):
                continue

            entries.append(rel)

        entries.sort(key=lambda x: x.as_posix())

        for rel in entries:
            full_p = repo_root / rel
            arcname = "./" + rel.as_posix()
            tarinfo = tar.gettarinfo(str(full_p), arcname=arcname)
            tarinfo.uid = 0
            tarinfo.gid = 0
            tarinfo.uname = ""
            tarinfo.gname = ""
            if full_p.is_file():
                with open(full_p, "rb") as f:
                    tar.addfile(tarinfo, f)
            elif full_p.is_dir():
                tar.addfile(tarinfo)

    return buf.getvalue()


def build_bundle_script(repo_root: Optional[Path] = None, with_deps: bool = False, preset: int = 9) -> str:
    """Pack the repository tree into a standalone self-extracting Python script string."""
    root = find_repo_root(repo_root)
    tar_bytes = create_tar_archive(root, with_deps=with_deps)
    lzma_bytes = lzma.compress(tar_bytes, preset=preset)
    b64_str = base64.b64encode(lzma_bytes).decode("ascii")
    b64_lines = "\n".join(b64_str[i : i + 76] for i in range(0, len(b64_str), 76))

    unbundle_file = root / "dwimsy" / "meta" / "unbundle.py"
    if not unbundle_file.is_file():
        unbundle_file = Path(unbundle.__file__).resolve()

    template = unbundle_file.read_text(encoding="utf-8")
    blztar_re = re.compile(r'blztar = """[\s\S]*?"""')
    replacement = f'blztar = """\n{b64_lines}\n"""'
    return blztar_re.sub(replacement, template, count=1)


def get_default_bundle_name(
    repo_root: Optional[Path] = None,
    tag: Optional[str] = None,
    with_deps: bool = False,
    is_baseline: bool = False,
) -> str:
    """Derive standard bundle filename."""
    root = find_repo_root(repo_root)
    pkg_ver = integrity.version(root=root)
    if is_baseline:
        base_v = pkg_ver.split("+")[0]
        return f"dwimsy_{base_v}_clean.py"

    clean_tag = f"_{re.sub(r'[^a-zA-Z0-9_.-]', '_', tag)}" if tag else ""
    deps_tag = "_deps" if with_deps else ""
    return f"dwimsy_{pkg_ver}{clean_tag}{deps_tag}.py"


def run_meta_bundle(args, stdout=sys.stdout, stderr=sys.stderr) -> int:
    """CLI handler for 'dwimsy meta bundle'."""
    repo_root = find_repo_root()

    if getattr(args, "status", False):
        res = subprocess.run(["git", "status", "-s"], cwd=repo_root, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            print("=== Working Tree Git Status ===", file=stderr)
            print(res.stdout.strip(), file=stderr)

    if getattr(args, "diff", False):
        res = subprocess.run(["git", "diff"], cwd=repo_root, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            print("=== Working Tree Git Diff ===", file=stderr)
            print(res.stdout.strip(), file=stderr)

    if getattr(args, "baseline", False):
        unbundle_file = repo_root / "dwimsy" / "meta" / "unbundle.py"
        if unbundle_file.is_file():
            script_text = unbundle_file.read_text(encoding="utf-8")
        else:
            script_text = build_bundle_script(repo_root=repo_root, with_deps=False)
        out_name = args.output or get_default_bundle_name(repo_root, is_baseline=True)
    else:
        script_text = build_bundle_script(repo_root=repo_root, with_deps=getattr(args, "with_deps", False))
        out_name = args.output or get_default_bundle_name(
            repo_root,
            tag=getattr(args, "tag", None),
            with_deps=getattr(args, "with_deps", False),
            is_baseline=False,
        )

    if out_name == "-":
        stdout.write(script_text)
    else:
        out_path = Path(out_name).resolve()
        out_path.write_text(script_text, encoding="utf-8")
        try:
            out_path.chmod(0o755)
        except OSError:
            pass
        print(f"[SUCCESS] Generated bundle -> {out_path}", file=stderr)

    return 0
