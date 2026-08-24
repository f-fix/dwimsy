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
    return integrity.find_repo_root(start)


def create_tar_archive(repo_root: Path, with_deps: bool = True) -> bytes:
    """Create a deterministic in-memory TAR byte stream of the repository tree."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        disk_entries = {}
        for p in repo_root.rglob("*"):
            rel = p.relative_to(repo_root)
            parts = rel.parts

            if any(part in (".git", "__pycache__", ".pytest_cache") for part in parts):
                continue
            if not with_deps and parts and parts[0] == "deps":
                continue
            if p.suffix in (".pyc", ".wav", ".t88", ".cmt") or p.name.endswith("~"):
                continue
            if p.name in ("unbundle.py", "restore_dwimsy.py") or (p.name.startswith("dwimsy_") and p.name.endswith(".py")):
                continue

            arcname = "./" + rel.as_posix()
            disk_entries[arcname] = p

        fallback_entries = {}
        fallback_data = {}
        has_disk_deps = any(arc.startswith("./deps/") for arc in disk_entries.keys())
        if with_deps and not has_disk_deps:
            try:
                with unbundle._open_bundle_tar() as src_tar:
                    for m in src_tar.getmembers():
                        norm = m.name.lstrip("./")
                        if norm == "deps" or norm.startswith("deps/"):
                            arcname = "./" + norm
                            tarinfo = tarfile.TarInfo(name=arcname)
                            tarinfo.type = m.type
                            tarinfo.size = m.size
                            tarinfo.mode = m.mode
                            tarinfo.mtime = m.mtime
                            tarinfo.uid = 0
                            tarinfo.gid = 0
                            tarinfo.uname = ""
                            tarinfo.gname = ""
                            fallback_entries[arcname] = tarinfo
                            if m.isfile():
                                f = src_tar.extractfile(m)
                                if f is not None:
                                    fallback_data[arcname] = f.read()
            except Exception:
                pass

        all_arcnames = sorted(set(disk_entries.keys()) | set(fallback_entries.keys()))

        for arcname in all_arcnames:
            if arcname in disk_entries:
                full_p = disk_entries[arcname]
                tarinfo = tar.gettarinfo(str(full_p), arcname=arcname)
                tarinfo.uid = 0
                tarinfo.gid = 0
                tarinfo.uname = ""
                tarinfo.gname = ""
                if full_p.is_file():
                    with open(full_p, "rb") as f:
                        content = f.read()
                    if arcname.endswith(".py") and content.startswith(b"#!"):
                        tarinfo.mode = 0o755
                    tar.addfile(tarinfo, io.BytesIO(content))
                elif full_p.is_dir():
                    tar.addfile(tarinfo)
            elif arcname in fallback_entries:
                tarinfo = fallback_entries[arcname]
                if tarinfo.isreg():
                    data = fallback_data.get(arcname, b"")
                    if arcname.endswith(".py") and data.startswith(b"#!"):
                        tarinfo.mode = 0o755
                    tar.addfile(tarinfo, io.BytesIO(data))
                elif tarinfo.isdir():
                    tar.addfile(tarinfo)

    return buf.getvalue()


def build_bundle_script(repo_root: Optional[Path] = None, with_deps: bool = True, preset: int = 9) -> str:
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
    with_deps: bool = True,
    is_baseline: bool = False,
) -> str:
    """Derive standard bundle filename."""
    root = find_repo_root(repo_root)
    pkg_ver = integrity.version(root=root)
    if is_baseline:
        base_v = pkg_ver.split("+")[0]
        return f"dwimsy_{base_v}_clean.py"

    clean_tag = f"_{re.sub(r'[^a-zA-Z0-9_.-]', '_', tag)}" if tag else ""
    return f"dwimsy_{pkg_ver}{clean_tag}.py"


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
            script_text = build_bundle_script(repo_root=repo_root, with_deps=True)
        out_name = args.output or get_default_bundle_name(repo_root, is_baseline=True)
    else:
        script_text = build_bundle_script(repo_root=repo_root, with_deps=True)
        out_name = args.output or get_default_bundle_name(
            repo_root,
            tag=getattr(args, "tag", None),
            with_deps=True,
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


def run_meta_fetch_deps(args, stdout=sys.stdout, stderr=sys.stderr) -> int:
    """CLI handler for 'dwimsy meta fetch-deps'."""
    repo_root = find_repo_root()
    deps_dir = repo_root / "deps"

    use_baseline = getattr(args, "baseline", False) or not (repo_root / ".git").exists()

    if not use_baseline:
        res = subprocess.run(
            ["git", "submodule", "update", "--init", "--recursive"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            print(f"[SUCCESS] Updated git submodules in {deps_dir}", file=stderr)
            return 0
        print("[NOTICE] Git submodule update failed or unavailable; falling back to bundled baseline.", file=stderr)

    extracted = unbundle.extract_deps(repo_root)
    print(f"[SUCCESS] Materialized {len(extracted)} bundled reference files into {deps_dir}", file=stderr)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for running dwimsy.meta.bundle directly."""
    parser = argparse.ArgumentParser(
        prog="dwimsy-bundle",
        description="Generate a self-extracting single-file Python unpacker bundle of dwimsy.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {integrity.version()}",
    )
    parser.add_argument(
        "-o", "--output", default=None, help="Output script path or '-' for stdout (default: auto-derived)"
    )
    parser.add_argument(
        "-t", "--tag", default=None, help="Optional short descriptive tag/label (e.g. 'parser-fix')"
    )
    parser.add_argument(
        "--baseline", action="store_true", help="Directly emit the installed canonical baseline bundle module (dwimsy/meta/unbundle.py) as output without bundling working tree"
    )
    parser.add_argument(
        "--with-deps", action="store_true", help="Include legacy submodule scaffolding from deps/"
    )
    parser.add_argument(
        "--status", action="store_true", help="List uncommitted/modified and untracked files before bundling"
    )
    parser.add_argument(
        "--diff", action="store_true", help="Display working tree git diff on stderr before bundling"
    )
    args = parser.parse_args(argv)
    return run_meta_bundle(args)


if __name__ == "__main__":
    sys.exit(main())
