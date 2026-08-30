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
import time
from pathlib import Path
from typing import List, Optional

here = Path(__file__).resolve()
if len(here.parts) >= 3 and here.parts[-3] == "dwimsy" and here.parts[-2] == "meta":
    p = here.parents[2]
    if (p / "dwimsy" / "_version.py").is_file() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dwimsy.meta import integrity, unbundle
from dwimsy.meta.unbundle import extract_b64_lzma_tar
from dwimsy.meta.versions import (
    VersionSpace,
    Stream,
    Layer,
    compute_tree_delta,
    portable_path_error,
)


_BLZTAR_RE = re.compile(
    rb"(?ms)^(?P<prefix>[ \t]*blztar[ \t]*=[ \t]*\"\"\")(?P<data>.*?)(?P<suffix>\"\"\"[ \t]*(?:#.*)?$)"
)


def elide_blztar_bytes(data: bytes) -> bytes:
    """Replace the embedded blztar payload with an empty placeholder."""
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    match = _BLZTAR_RE.search(data)
    if match is None:
        raise ValueError("unbundle.py does not contain a blztar assignment")
    return (
        data[: match.start()]
        + match.group("prefix")
        + b"\n"
        + match.group("suffix")
        + data[match.end() :]
    )


def inject_blztar_bytes(template: bytes, b64_string: str) -> bytes:
    """Inject a base64 payload into an elided unbundle.py template."""
    template = template.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    match = _BLZTAR_RE.search(template)
    if match is None:
        raise ValueError("unbundle.py template does not contain a blztar assignment")
    payload = b"".join(b64_string.encode("ascii").split())
    lines = b"\n".join(payload[i : i + 76] for i in range(0, len(payload), 76))
    replacement = match.group("prefix") + b"\n" + lines + b"\n" + match.group("suffix")
    return template[: match.start()] + replacement + template[match.end() :]


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Locate the root directory of the dwimsy repository or extracted tree."""
    return integrity.find_repo_root(start)


def create_tree_state(repo_root: Path, with_deps: bool = True) -> dict[str, bytes]:
    """Return the deterministic portable file tree used by bundle creation."""
    result: dict[str, bytes] = {}
    invalid_paths: list[tuple[str, str]] = []
    if (repo_root / "dwimsy").is_dir():
        for p in repo_root.rglob("*"):
            rel = p.relative_to(repo_root)
            parts = rel.parts
            if any(part in (".git", "__pycache__", ".pytest_cache") for part in parts):
                continue
            if not with_deps and parts and parts[0] == "deps":
                continue
            if p.suffix in (".pyc", ".wav", ".t88", ".cmt") or p.name.endswith("~"):
                continue
            if p.name == "restore_dwimsy.py" or (
                p.name.startswith("dwimsy_") and p.suffix in (".py", ".pyz")
            ):
                continue
            if p.is_file():
                name = rel.as_posix()
                err = portable_path_error(name)
                if err:
                    invalid_paths.append((name, err))
                    continue
                data = p.read_bytes()
                if name == "dwimsy/meta/unbundle.py":
                    data = elide_blztar_bytes(data)
                result[name] = data
    else:
        embedded_assets = unbundle.materialize_stream0_assets()
        for k, v in embedded_assets.items():
            clean_k = (
                k[len("<dwimsy-bundle>/") :] if k.startswith("<dwimsy-bundle>/") else k
            )
            if not with_deps and (clean_k == "deps" or clean_k.startswith("deps/")):
                continue
            if clean_k == "dwimsy/meta/unbundle.py":
                v = elide_blztar_bytes(v)
            result[clean_k] = v
    if with_deps and not any(k.startswith("deps/") for k in result):
        embedded_assets = unbundle.materialize_stream0_assets()
        for k, v in embedded_assets.items():
            clean_k = (
                k[len("<dwimsy-bundle>/") :] if k.startswith("<dwimsy-bundle>/") else k
            )
            if clean_k.startswith("deps/"):
                result[clean_k] = v

    if invalid_paths:
        details = "\n".join(err for _name, err in invalid_paths)
        raise ValueError("Cannot bundle non-portable paths:\n" + details)

    # If deps are absent on disk, use the embedded dependency shadow.
    if with_deps and not any(k == "deps" or k.startswith("deps/") for k in result):
        # In a checkout, only shadow dependencies explicitly declared by
        # .gitmodules may be restored from the embedded bundle. Standalone
        # bundles have no live .gitmodules and may use the embedded copy.
        declared = set()
        gm = repo_root / ".gitmodules"
        if gm.is_file():
            for line in gm.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"\s*path\s*=\s*(.+?)\s*$", line)
                if m:
                    declared.add(m.group(1).strip().replace("\\", "/"))
        try:
            with unbundle._open_bundle_tar() as src_tar:
                for m in src_tar.getmembers():
                    name = m.name.removeprefix("./")
                    if not (name == "deps" or name.startswith("deps/")):
                        continue
                    dep_root = name.split("/", 2)[:2]
                    dep_path = "/".join(dep_root) if len(dep_root) >= 2 else name
                    if gm.is_file() and not any(
                        dep_path == d or dep_path.startswith(d.rstrip("/") + "/")
                        for d in declared
                    ):
                        continue
                    f = src_tar.extractfile(m) if m.isfile() else None
                    if f is not None:
                        result[name] = f.read()
        except Exception:
            pass
    return result


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
            if p.name == "restore_dwimsy.py" or (
                p.name.startswith("dwimsy_")
                and (p.name.endswith(".py") or p.name.endswith(".pyz"))
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
                        norm = m.name.removeprefix("./")
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
                                    if arcname.endswith(".py") and content.startswith(
                                        b"#!"
                                    ):
                                        tarinfo.mode = 0o755
                                    else:
                                        tarinfo.mode = 0o644
                            fallback_entries[arcname] = tarinfo
            except Exception:
                pass

        if "./dwimsy/meta/unbundle.py" not in disk_entries:
            try:
                unbundle_template = unbundle.get_asset("dwimsy/meta/unbundle.py")
                tarinfo = tarfile.TarInfo(name="./dwimsy/meta/unbundle.py")
                tarinfo.type = tarfile.REGTYPE
                tarinfo.size = len(unbundle_template)
                tarinfo.mode = 0o755
                tarinfo.mtime = int(time.time())
                fallback_entries["./dwimsy/meta/unbundle.py"] = tarinfo
                fallback_data["./dwimsy/meta/unbundle.py"] = unbundle_template
            except Exception:
                pass
        if "./dwimsy/meta/unbundle.py" not in disk_entries:
            try:
                unbundle_template = unbundle.get_asset("dwimsy/meta/unbundle.py")
                tarinfo = tarfile.TarInfo(name="./dwimsy/meta/unbundle.py")
                tarinfo.type = tarfile.REGTYPE
                tarinfo.size = len(unbundle_template)
                tarinfo.mode = 0o755
                tarinfo.mtime = int(time.time())
                fallback_entries["./dwimsy/meta/unbundle.py"] = tarinfo
                fallback_data["./dwimsy/meta/unbundle.py"] = unbundle_template
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
                    if arcname == "./dwimsy/meta/unbundle.py":
                        content = elide_blztar_bytes(content)
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
                        p
                        for arc, p in disk_entries.items()
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
    repo_root: Optional[Path] = None,
    with_deps: bool = True,
    preset: int = (9 | lzma.PRESET_EXTREME),
    version_space: Optional[VersionSpace] = None,
) -> str:
    """Pack the repository or supplied VersionSpace into a standalone bundle."""
    root = find_repo_root(repo_root)
    if version_space is None:
        tar_bytes = create_tar_archive(root, with_deps=with_deps)
        lzma_bytes = lzma.compress(tar_bytes, preset=preset)
        b64_str = base64.b64encode(lzma_bytes).decode("ascii")
    else:
        b64_str = version_space.to_blztar()

    unbundle_file = root / "dwimsy" / "meta" / "unbundle.py"
    if unbundle_file.is_file():
        template = unbundle_file.read_bytes()
    else:
        template = unbundle.get_asset("dwimsy/meta/unbundle.py")
    return inject_blztar_bytes(elide_blztar_bytes(template), b64_str).decode("utf-8")


def write_pyz_bundle(script_text: str, output_path: Path) -> None:
    """Generate a compressed .pyz bundle using stdlib zipapp."""
    import zipapp

    with tempfile.TemporaryDirectory() as staging:
        st_path = Path(staging)
        main_py = st_path / "__main__.py"
        main_py.write_text(script_text, encoding="utf-8")
        try:
            main_py.chmod(0o755)
        except OSError:
            pass
        output_path.parent.mkdir(parents=True, exist_ok=True)
        zipapp.create_archive(
            st_path,
            target=output_path,
            interpreter="/usr/bin/env python3",
            compressed=True,
        )
        try:
            output_path.chmod(0o755)
        except OSError:
            pass


def get_default_bundle_name(
    repo_root: Optional[Path] = None,
    tag: Optional[str] = None,
    with_deps: bool = True,
    is_baseline: bool = False,
) -> str:
    """Derive standard bundle filename."""
    from dwimsy.meta import diff

    root = find_repo_root(repo_root)
    pkg_ver = integrity.version(root=root)
    if is_baseline:
        base_v = pkg_ver.split("+")[0]
        return f"dwimsy_{base_v}_clean.py"
    if not diff.render_diff(root):
        base_v = pkg_ver.split("+")[0]
        clean_tag = f"_{re.sub(r'[^a-zA-Z0-9_.-]', '_', tag)}" if tag else ""
        return f"dwimsy_{base_v}{clean_tag}.py"

    clean_tag = f"_{re.sub(r'[^a-zA-Z0-9_.-]', '_', tag)}" if tag else ""
    return f"dwimsy_{pkg_ver}{clean_tag}.py"


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


def run_meta_bundle(args, stdout=None, stderr=None) -> int:
    """Generate a bundle while preserving the current VersionSpace history."""
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    cwd = Path.cwd().resolve()
    # In standalone mode the Python package itself lives in the in-memory
    # bundle, but `meta bundle` is a disk-facing preparation operation.  If
    # the caller is standing in an extracted dwimsy tree, use that tree as
    # the source rather than the virtual package root.
    if (cwd / "dwimsy" / "__init__.py").is_file():
        root = cwd
    else:
        root = find_repo_root()

    if getattr(args, "status", False):
        res = subprocess.run(
            ["git", "status", "-s"], cwd=root, capture_output=True, text=True
        )
        if res.returncode == 0 and res.stdout.strip():
            print("=== Working Tree Status ===", file=stderr)
            print(res.stdout.strip(), file=stderr)

    if getattr(args, "diff", False):
        from dwimsy.meta.diff import render_diff

        diff_text = render_diff(root)
        if diff_text:
            stdout.write(diff_text)

    raw_b64 = unbundle._get_active_blztar()
    vspace = VersionSpace.from_blztar(raw_b64) if raw_b64 else VersionSpace()
    primary = vspace.streams[0]
    head = primary.get_head_version()
    current_tag = integrity.version(root=root)
    # §1.6.1: Only subsequent overlay layers (ordinal >= 1) may be replaced in place.
    # Layer 0 is unconditionally the complete base snapshot (is_delta=False) and must not
    # be overwritten by a partial delta.
    is_replace = bool(
        head
        and head.ordinal > 0
        and (
            head.tag.split("+")[0].lower() == current_tag.split("+")[0].lower()
            or "+mod." in head.tag.lower()
        )
    )
    if is_replace and head and head.ordinal > 0:
        old_state = primary.materialize_layer_state(head.ordinal - 1)
    else:
        old_state = primary.materialize_layer_state(head.ordinal) if head else {}
    new_state = create_tree_state(root, with_deps=True)
    delta = compute_tree_delta(old_state, new_state) if head else dict(new_state)
    if "dwimsy/_version.py" in new_state:
        delta["dwimsy/_version.py"] = new_state["dwimsy/_version.py"]
    delta = _set_layer_version_tag(delta, current_tag)
    if is_replace:
        primary.append_layer(
            Layer(delta, is_delta=True, version_tag=current_tag), allow_replacement=True
        )
    elif delta or not head:
        primary.append_layer(Layer(delta, is_delta=True, version_tag=current_tag))

    script_text = build_bundle_script(root, with_deps=True, version_space=vspace)
    out_name = getattr(args, "output", None) or vspace.composite_bundle_name(".py")

    # Verify the generated bundle in an isolated subprocess before publishing it.
    with tempfile.TemporaryDirectory(prefix="dwimsy_bundle_") as tmp:
        tmpdir = Path(tmp)
        stage = tmpdir / "bundle.py"
        stage.write_text(script_text, encoding="utf-8")
        stage.chmod(0o755)

        sub_env = dict(os.environ)
        sub_env.pop("DWIMSY_TEST_REPO_ROOT", None)
        sub_env["DWIMSY_BUNDLE_BUILD"] = "1"
        proc = subprocess.run(
            [sys.executable, str(stage), "dwimsy", "-T", "meta integrity"],
            capture_output=True,
            text=True,
            env=sub_env,
        )
        rc = proc.returncode
        if getattr(args, "verbose", 0) and (proc.stdout or proc.stderr):
            if proc.stdout:
                stderr.write(proc.stdout)
            if proc.stderr:
                stderr.write(proc.stderr)
            stderr.flush()
        if rc != 0:
            failed = Path(out_name).with_name(
                Path(out_name).stem
                + f"_failed_{rc}_tests"
                + (Path(out_name).suffix or ".py")
            )
            failed.write_text(script_text, encoding="utf-8")
            failed.chmod(0o755)
            if proc.stderr:
                stderr.write(proc.stderr)
            return 1

    if out_name == "-":
        stdout.write(script_text)
        return 0
    out_path = Path(out_name).resolve()
    is_default_out = not getattr(args, "output", None)
    if out_path.suffix == ".py":
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(script_text, encoding="utf-8")
        out_path.chmod(0o755)
        if is_default_out:
            pyz_out = out_path.with_suffix(".pyz")
            write_pyz_bundle(script_text, pyz_out)
    elif out_path.suffix == ".pyz":
        write_pyz_bundle(script_text, out_path)
    else:
        raise ValueError(f"Unsupported output extension '{out_path.suffix}'")
    print(f"[SUCCESS] Generated bundle -> {out_path}", file=stderr)
    return 0


def run_meta_fetch_deps(args, stdout=None, stderr=None) -> int:
    if stdout is None:
        stdout = sys.stdout
    if stderr is None:
        stderr = sys.stderr
    """CLI handler for 'dwimsy meta fetch-deps'."""
    cwd = Path.cwd().resolve()
    # When invoked from an extracted/relocated tree, that tree is the target
    # for dependency materialization even though the dispatcher itself may
    # have been imported from another checkout.
    if (cwd / "dwimsy" / "__init__.py").is_file():
        repo_root = cwd
    else:
        repo_root = find_repo_root()
    deps_dir = repo_root / "deps"

    # `--version=baseline` is consumed by the universal VersionSpace
    # dispatcher before this handler runs.  Dependency materialization is
    # therefore based on the active embedded payload here; the selected
    # version has already determined that payload.
    use_baseline = not (repo_root / ".git").exists()

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

    if (
        deps_dir.exists()
        and any(deps_dir.iterdir())
        and not getattr(args, "force", False)
    ):
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
    """CLI entrypoint for building standalone bundles in either format."""
    effective = sys.argv[1:] if argv is None else list(argv)
    from dwimsy.cli.dispatch import early_dispatch

    handled, effective = early_dispatch(
        effective, ["meta", "bundle"], use_process_argv0=(argv is None)
    )
    if handled:
        return 0
    if any(a in ("-T", "--test") or a.startswith("--test=") for a in effective):
        test_arg = next(
            a for a in effective if a in ("-T", "--test") or a.startswith("--test=")
        )
        verbosity = 1 + sum(1 for a in effective if a in ("-v", "--verbose"))
        from dwimsy.tests import run_tests

        pattern = (
            [test_arg.split("=", 1)[1]]
            if test_arg.startswith("--test=")
            else ["meta bundle"]
        )
        return run_tests(pattern, verbose=max(verbosity, 1))

    parser = argparse.ArgumentParser(
        prog="dwimsy-bundle",
        description="Build self-extracting dwimsy standalone bundles.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action=integrity._LazyVersionAction,
        version_fn=integrity.version,
    )
    parser.add_argument("-T", "--test", nargs="?", const=True, default=False)
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument(
        "-o", "--output", default=None, help="Output bundle filepath (.py, .pyz, or -)"
    )
    parser.add_argument("--version-include", action="append", default=[])
    parser.add_argument("--version-restrict-to", default=None)
    parser.add_argument("--version-prune", default=None)
    parser.add_argument("--version-splice", default=None)
    parser.add_argument("--version-alt", nargs="?", const=True, default=False)
    args = parser.parse_args(effective)

    cwd = Path.cwd().resolve()
    if (cwd / "dwimsy" / "__init__.py").is_file():
        root = cwd
    else:
        root = integrity.find_repo_root()
        if integrity.is_standalone_bundle() or "<dwimsy-bundle>" in str(__file__):
            root = Path.cwd()
    raw_b64 = unbundle._get_active_blztar()
    vspace = VersionSpace.from_blztar(raw_b64) if raw_b64 else VersionSpace()
    if vspace.streams and root.exists():
        primary = vspace.streams[0]
        head = primary.get_head_version()
        v_tag = integrity.version(root=root).split("+")[0]
        is_replace = bool(
            head
            and (
                head.tag.split("+")[0].lower() == v_tag.split("+")[0].lower()
                or "+mod." in head.tag.lower()
            )
        )
        if is_replace and head and head.ordinal > 0:
            old_state = primary.materialize_layer_state(head.ordinal - 1)
        else:
            old_state = primary.materialize_layer_state(head.ordinal) if head else {}
        new_state = create_tree_state(root, with_deps=True)
        delta = compute_tree_delta(old_state, new_state) if head else new_state
        if "dwimsy/_version.py" in new_state:
            delta["dwimsy/_version.py"] = new_state["dwimsy/_version.py"]
        delta = _set_layer_version_tag(delta, v_tag)
        if is_replace:
            primary.append_layer(
                Layer(delta, is_delta=True, version_tag=v_tag), allow_replacement=True
            )
        elif delta or not head:
            primary.append_layer(Layer(delta, is_delta=True, version_tag=v_tag))
    alt_val = (
        (True, args.version_alt)
        if isinstance(args.version_alt, str)
        else (bool(args.version_alt), None)
    )
    vspace.run_pipeline(
        includes=args.version_include,
        restrict_to=args.version_restrict_to,
        prune=args.version_prune,
        splice=args.version_splice,
        alt=alt_val,
    )
    script_text = build_bundle_script(root, version_space=vspace)

    if args.output == "-":
        sys.stdout.write(script_text)
        return 0
    if args.output is not None:
        p = Path(args.output)
        if p.suffix == ".py":
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(script_text, encoding="utf-8")
        elif p.suffix == ".pyz":
            write_pyz_bundle(script_text, p)
        else:
            print(
                f"error: unsupported output extension '{p.suffix}'. Expected '.py' or '.pyz' (or '-' for stdout).",
                file=sys.stderr,
            )
            return 1
        return 0

    py_name = vspace.composite_bundle_name(".py")
    py_path = root / py_name
    pyz_path = py_path.with_suffix(".pyz")
    py_path.write_text(script_text, encoding="utf-8")
    write_pyz_bundle(script_text, pyz_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
