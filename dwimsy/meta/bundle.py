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
import tempfile
from pathlib import Path
from typing import List, Optional

for p in Path(__file__).resolve().parents:
    if (p / "dwimsy").is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
        break

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
            if p.name in ("unbundle.py", "restore_dwimsy.py") or (
                p.name.startswith("dwimsy_") and p.name.endswith(".py")
            ):
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
                            tarinfo.mtime = int(m.mtime)
                            tarinfo.uid = 0
                            tarinfo.gid = 0
                            tarinfo.uname = ""
                            tarinfo.gname = ""
                            if m.isdir():
                                tarinfo.mode = 0o755
                            elif m.isfile():
                                f = src_tar.extractfile(m)
                                if f is not None:
                                    content = f.read()
                                    fallback_data[arcname] = content
                                    if arcname.endswith(".py") and content.startswith(b"#!"):
                                        tarinfo.mode = 0o755
                                    else:
                                        tarinfo.mode = 0o644
                            fallback_entries[arcname] = tarinfo
            except Exception:
                pass

        all_arcnames = sorted(set(disk_entries.keys()) | set(fallback_entries.keys()))

        for arcname in all_arcnames:
            if arcname in disk_entries:
                full_p = disk_entries[arcname]
                tarinfo = tarfile.TarInfo(name=arcname)
                tarinfo.uid = 0
                tarinfo.gid = 0
                tarinfo.uname = ""
                tarinfo.gname = ""
                if full_p.is_file():
                    with open(full_p, "rb") as f:
                        content = f.read()
                    tarinfo.type = tarfile.REGTYPE
                    tarinfo.size = len(content)
                    tarinfo.mtime = int(full_p.stat().st_mtime)
                    if arcname.endswith(".py") and content.startswith(b"#!"):
                        tarinfo.mode = 0o755
                    else:
                        tarinfo.mode = 0o644
                    tar.addfile(tarinfo, io.BytesIO(content))
                elif full_p.is_dir():
                    tarinfo.type = tarfile.DIRTYPE
                    tarinfo.mode = 0o755
                    child_files = [
                        p for arc, p in disk_entries.items()
                        if arc.startswith(arcname + "/") and p.is_file()
                    ]
                    if child_files:
                        tarinfo.mtime = max(int(f.stat().st_mtime) for f in child_files)
                    else:
                        tarinfo.mtime = int(full_p.stat().st_mtime)
                    tar.addfile(tarinfo)
            elif arcname in fallback_entries:
                tarinfo = fallback_entries[arcname]
                if tarinfo.isreg():
                    data = fallback_data.get(arcname, b"")
                    tar.addfile(tarinfo, io.BytesIO(data))
                elif tarinfo.isdir():
                    tar.addfile(tarinfo)

    return buf.getvalue()


def build_bundle_script(
    repo_root: Optional[Path] = None, with_deps: bool = True, preset: int = 9
) -> str:
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
        res = subprocess.run(
            ["git", "status", "-s"], cwd=repo_root, capture_output=True, text=True
        )
        if res.returncode == 0 and res.stdout.strip():
            print("=== Working Tree Git Status ===", file=stderr)
            print(res.stdout.strip(), file=stderr)

    if getattr(args, "diff", False):
        res = subprocess.run(
            ["git", "diff"], cwd=repo_root, capture_output=True, text=True
        )
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

    # Multi-phase build
    with_deps = getattr(args, "with_deps", False)
    tag = getattr(args, "tag", None)
    out_name = args.output or get_default_bundle_name(
        repo_root,
        tag=tag,
        with_deps=with_deps,
        is_baseline=False,
    )

    with tempfile.TemporaryDirectory(prefix="dwimsy_bundle_") as tmp:
        tmp_path = Path(tmp)
        # Phase 1: Build stage 1 bundle script in temporary directory
        stage1_script = build_bundle_script(repo_root=repo_root, with_deps=True)
        stage1_bundle_file = tmp_path / "stage1_bundle.py"
        stage1_bundle_file.write_text(stage1_script, encoding="utf-8")

        # Phase 2: Extract stage 1 bundle to an isolated unpacked/ directory with with_deps=False
        unpacked_dir = tmp_path / "unpacked"
        m_b = re.search(r'blztar = """\n([\s\S]*?)\n"""', stage1_script)
        stage1_blztar = m_b.group(1) if m_b else unbundle.blztar
        unbundle.extract_b64_lzma_tar(
            stage1_blztar,
            unpacked_dir,
            self_path=stage1_bundle_file,
            with_deps=False,
        )

        # Phase 3: Rebundle from unpacked/ (verifying in-memory dependency splicing)
        stage2_script = build_bundle_script(repo_root=unpacked_dir, with_deps=True)

        # Phase 4: Run tests on unpacked_dir with os.environ["DWIMSY_BUNDLE_BUILD"] = "1"
        from dwimsy.tests import run_tests

        old_env = os.environ.get("DWIMSY_BUNDLE_BUILD")
        os.environ["DWIMSY_BUNDLE_BUILD"] = "1"
        test_stream = io.StringIO()
        try:
            rc = run_tests(patterns=None, verbose=0, stream=test_stream, repo_root=unpacked_dir)
        finally:
            if old_env is None:
                os.environ.pop("DWIMSY_BUNDLE_BUILD", None)
            else:
                os.environ["DWIMSY_BUNDLE_BUILD"] = old_env

        # Phase 5 & 6
        if rc == 0:
            if out_name == "-":
                stdout.write(stage2_script)
            else:
                out_path = Path(out_name).resolve()
                out_path.write_text(stage2_script, encoding="utf-8")
                try:
                    out_path.chmod(0o755)
                except OSError:
                    pass
                print(f"[SUCCESS] Generated bundle -> {out_path}", file=stderr)
            return 0
        else:
            err_details = test_stream.getvalue()
            out_p = Path(out_name)
            stem = out_p.stem
            suffix = out_p.suffix or ".py"
            failed_name = f"{stem}_failed_{rc}_tests{suffix}"
            if out_name == "-":
                failed_path = Path(failed_name).resolve()
            else:
                failed_path = out_p.with_name(failed_name).resolve()

            failed_path.write_text(stage2_script, encoding="utf-8")
            try:
                failed_path.chmod(0o755)
            except OSError:
                pass
            print(
                f"[FAILURE] Test suite failed ({rc} failed test(s)). Diagnostic bundle saved to {failed_path}\n{err_details}",
                file=stderr,
            )
            return 1


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
        print(
            "[NOTICE] Git submodule update failed or unavailable; falling back to bundled baseline.",
            file=stderr,
        )

    if deps_dir.exists() and any(deps_dir.iterdir()) and not getattr(args, "force", False):
        print(
            f"[NOTICE] '{deps_dir}' already exists and is not empty. Use --force / -f to overwrite.",
            file=stderr,
        )
        return 0

    extracted = unbundle.extract_deps(repo_root)
    print(
        f"[SUCCESS] Materialized {len(extracted)} bundled reference files into {deps_dir}",
        file=stderr,
    )
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
        "-o",
        "--output",
        default=None,
        help="Output script path or '-' for stdout (default: auto-derived)",
    )
    parser.add_argument(
        "-t",
        "--tag",
        default=None,
        help="Optional short descriptive tag/label (e.g. 'parser-fix')",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Directly emit the installed canonical baseline bundle module (dwimsy/meta/unbundle.py) as output without bundling working tree",
    )
    parser.add_argument(
        "--with-deps",
        action="store_true",
        help="Include legacy submodule scaffolding from deps/",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="List uncommitted/modified and untracked files before bundling",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Display working tree git diff on stderr before bundling",
    )
    args = parser.parse_args(argv)
    return run_meta_bundle(args)


if __name__ == "__main__":
    sys.exit(main())
