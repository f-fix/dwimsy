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

from dwimsy.meta import integrity, unbundle, versions
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


from dwimsy.meta.integrity import GitIgnoreRule, GitIgnoreMatcher, get_git_command


def _canonical_layer_mtimes(root: Path, names) -> tuple[int, dict[str, int]]:
    """Return one newest on-disk mtime for the supplied changed files rounded to 2-second timestamp."""
    mtimes = {}
    for name in names:
        fp = root / name
        if fp.is_file():
            try:
                mtimes[name] = int(round(fp.stat().st_mtime / 2.0) * 2)
            except OSError:
                pass
    raw_mtime = max(mtimes.values()) if mtimes else int(time.time())
    layer_mtime = int(round(raw_mtime / 2.0) * 2)
    return layer_mtime, {name: layer_mtime for name in names}


def create_tree_state(repo_root: Path, with_deps: bool = True) -> dict[str, bytes]:
    """Return the deterministic portable file tree used by bundle creation."""
    result: dict[str, bytes] = {}
    invalid_paths: list[tuple[str, str]] = []
    seen_case_keys: dict[str, str] = {}
    gitignore = GitIgnoreMatcher(repo_root)
    manifest = integrity.canonical_manifest(repo_root)
    if (repo_root / "dwimsy").is_dir():
        for p in repo_root.rglob("*"):
            rel = p.relative_to(repo_root)
            parts = rel.parts
            if any(part in (".git", "__pycache__", ".pytest_cache") for part in parts):
                continue
            if not with_deps and parts and parts[0] == "deps":
                continue
            rel_name = rel.as_posix()
            if p.is_file() and not integrity._manifest_matches(rel_name, manifest):
                continue
            if gitignore.matches(rel_name, is_dir=p.is_dir()):
                continue
            if p.suffix in (".pyc", ".wav", ".t88", ".cmt") or p.name.endswith("~"):
                continue
            if p.name == "restore_dwimsy.py" or (
                p.name.startswith("dwimsy_") and p.suffix in (".py", ".pyz")
            ):
                continue

            ckey = versions.path_collision_key(rel_name)
            if ckey in seen_case_keys and seen_case_keys[ckey] != rel_name:
                raise ValueError(
                    f"Cannot bundle repository with NFKC case-fold collision: '{seen_case_keys[ckey]}' and '{rel_name}'"
                )
            seen_case_keys[ckey] = rel_name

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

        if invalid_paths:
            details = "\n".join(f"{name}: {err}" for name, err in invalid_paths)
            raise ValueError(f"Cannot bundle non-portable paths:\n{details}")
    else:
        embedded_assets = unbundle.materialize_stream0_assets()
        for k, v in embedded_assets.items():
            clean_k = (
                k[len("<dwimsy-bundle>/") :] if k.startswith("<dwimsy-bundle>/") else k
            )
            if not with_deps and (clean_k == "deps" or clean_k.startswith("deps/")):
                continue
            if not integrity._manifest_matches(clean_k, manifest):
                continue
            if gitignore.matches(clean_k, is_dir=False):
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
            if clean_k.startswith("deps/") and integrity._manifest_matches(
                clean_k, manifest
            ):
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
    gitignore = GitIgnoreMatcher(repo_root)
    manifest = integrity.canonical_manifest(repo_root)
    with tarfile.open(fileobj=buf, mode="w") as tar:
        disk_entries = {}
        for p in repo_root.rglob("*"):
            rel = p.relative_to(repo_root)
            parts = rel.parts

            if any(part in (".git", "__pycache__", ".pytest_cache") for part in parts):
                continue
            if not with_deps and parts and parts[0] == "deps":
                continue
            rel_name = rel.as_posix()
            if p.is_file() and not integrity._manifest_matches(rel_name, manifest):
                continue
            if gitignore.matches(rel_name, is_dir=p.is_dir()):
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
                        if (norm == "deps" or norm.startswith("deps/")) and (
                            norm == "deps"
                            or integrity._manifest_matches(norm, manifest)
                        ):
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
        # The canonical manifest is an allow-list, not merely an integrity/hash
        # aid.  Reconstruct only parent directories needed by manifest-selected
        # files so stray build artifacts can never enter the archive.
        selected_entries = dict(disk_entries)
        for arcname, path in list(disk_entries.items()):
            if not path.is_file():
                selected_entries.pop(arcname, None)
        parent_dirs = {}
        for arcname, path in selected_entries.items():
            parent = Path(arcname).parent
            while str(parent) not in (".", ""):
                parent_arc = parent.as_posix()
                if not parent_arc.startswith("./"):
                    parent_arc = "./" + parent_arc
                dir_path = repo_root / parent_arc[2:]
                if dir_path.is_dir() and not gitignore.matches(
                    parent_arc[2:], is_dir=True
                ):
                    parent_dirs[parent_arc] = dir_path
                parent = parent.parent
        disk_entries = {**parent_dirs, **selected_entries}
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
    preset: Optional[int] = None,
    version_space: Optional[VersionSpace] = None,
) -> str:
    """Pack the repository or supplied VersionSpace into a standalone bundle."""
    root = find_repo_root(repo_root)
    if preset is None:
        preset = (
            1
            if (
                os.environ.get("DWIMSY_TEST_MODE")
                or os.environ.get("DWIMSY_BUNDLE_BUILD")
            )
            else (9 | lzma.PRESET_EXTREME)
        )
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


def verify_bundle_roundtrip(script_text: str, repo_root: Optional[Path] = None) -> None:
    """Verify candidate bundle extraction and canonical rebundling are lossless."""
    root = find_repo_root(repo_root)
    from dwimsy.meta import integrity as _integrity

    with tempfile.TemporaryDirectory(prefix="dwimsy_roundtrip_") as tmp:
        tmpdir = Path(tmp)
        candidate = tmpdir / "candidate.py"
        candidate.write_text(script_text, encoding="utf-8")
        candidate.chmod(0o755)
        extracted = tmpdir / "extracted"
        extracted.mkdir()
        proc = subprocess.run(
            [
                sys.executable,
                str(candidate),
                "meta",
                "unbundle",
                str(extracted),
                "--deps",
                "--force",
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "DWIMSY_REBUNDLE_VERIFYING": "1"},
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "Bundle round-trip extraction failed"
                + (f": {proc.stderr.strip()}" if proc.stderr.strip() else "")
            )

        # The round-trip invariant is candidate -> extraction -> canonical rebundle.
        # Do not compare the extracted tree to the current checkout here: a bundle
        # is allowed to represent a historical version that intentionally differs
        # from the checkout used to run this verifier.
        rebuilt = build_bundle_script(extracted, with_deps=True)
        candidate_canonical = _integrity._canonical_bytes(
            script_text.encode("utf-8"), "dwimsy/meta/unbundle.py"
        )
        rebuilt_canonical = _integrity._canonical_bytes(
            rebuilt.encode("utf-8"), "dwimsy/meta/unbundle.py"
        )
        if candidate_canonical != rebuilt_canonical:
            raise RuntimeError(
                "Bundle round-trip canonical rebundle differs from candidate"
            )


def write_pyz_bundle(
    script_text: str,
    output_path: Path,
    timestamp: Optional[str] = None,
) -> None:
    """Generate an executable compressed .pyz bundle using zipfile with deterministic UTC timestamp."""
    import zipfile
    import datetime

    dt_utc = None
    if timestamp:
        try:
            dt_utc = datetime.datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            ).astimezone(datetime.timezone.utc)
        except Exception:
            pass

    if dt_utc is None:
        try:
            m_b = re.search(r'blztar = """\n([\s\S]*?)\n"""', script_text)
            if m_b:
                from dwimsy.meta import versions

                sp = versions.VersionSpace.from_blztar(m_b.group(1))
                if sp.streams and sp.streams[0].layers:
                    head_v = sp.streams[0].get_head_version()
                    if head_v:
                        ts_str = sp.get_layer_timestamp(
                            sp.streams[0].layers[head_v.ordinal]
                        )
                        if ts_str:
                            dt_utc = datetime.datetime.fromisoformat(
                                ts_str.replace("Z", "+00:00")
                            ).astimezone(datetime.timezone.utc)
        except Exception:
            pass

    if dt_utc is None:
        dt_utc = datetime.datetime.now(datetime.timezone.utc)

    rounded_epoch = int(round(dt_utc.timestamp() / 2.0) * 2)
    dt_utc = datetime.datetime.fromtimestamp(
        rounded_epoch, tz=datetime.timezone.utc
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    content_bytes = script_text.encode("utf-8")

    with open(output_path, "wb") as f:
        f.write(b"#!/usr/bin/env python3\n")
        with zipfile.ZipFile(f, "w") as zf:
            zinfo = zipfile.ZipInfo(
                "__main__.py",
                date_time=(
                    dt_utc.year,
                    dt_utc.month,
                    dt_utc.day,
                    dt_utc.hour,
                    dt_utc.minute,
                    dt_utc.second,
                ),
            )
            zinfo.compress_type = zipfile.ZIP_DEFLATED
            zinfo.external_attr = 0o100755 << 16
            zf.writestr(zinfo, content_bytes)

    try:
        output_path.chmod(0o755)
    except OSError:
        pass
    try:
        os.utime(output_path, (rounded_epoch, rounded_epoch))
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
    updated = False
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
            updated = True
            break
    if not updated:
        result["dwimsy/_version.py"] = (
            f'"""dwimsy._version - Project version and sealed build identifier."""\n\n__version__ = "{version_tag}"\n__code_hash__ = ""\n'.encode(
                "utf-8"
            )
        )
    return result


def run_meta_bundle(args, stdout=None, stderr=None) -> int:
    """Generate a bundle while preserving the current VersionSpace history."""
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    cwd = Path.cwd().resolve()
    if (cwd / "dwimsy" / "__init__.py").is_file():
        root = cwd
    else:
        root = find_repo_root()

    git_bin = get_git_command(args)
    if getattr(args, "status", False) and git_bin and (root / ".git").exists():
        res = subprocess.run(
            [git_bin, "status", "-s"], cwd=root, capture_output=True, text=True
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
    baseline = bool(getattr(args, "baseline", False))
    new_state = create_tree_state(root, with_deps=True)

    head_is_mod = bool(head and "+mod." in head.tag.lower())

    if baseline:
        if head_is_mod and len(primary.layers) > 1:
            primary.layers.pop()
            primary.mark_mutated()
    elif head_is_mod and head and head.ordinal > 0:
        base_state = primary.materialize_layer_state(head.ordinal - 1)
        delta = compute_tree_delta(base_state, new_state)
        if not delta:
            primary.layers.pop()
            primary.mark_mutated()
        else:
            d_layer_mtime, d_mtimes = _canonical_layer_mtimes(root, delta)
            declared_base = current_tag.split("+")[0]
            mod_hash = integrity.modification_hash(root)
            mod_tag = f"{declared_base}+mod.{mod_hash}"
            delta = _set_layer_version_tag(delta, mod_tag)
            primary.append_layer(
                Layer(
                    delta,
                    is_delta=True,
                    version_tag=mod_tag,
                    mtime=d_layer_mtime,
                    file_mtimes=d_mtimes,
                ),
                allow_replacement=True,
            )
    elif not head:
        d_layer_mtime, d_mtimes = _canonical_layer_mtimes(root, new_state)
        primary.append_layer(
            Layer(
                dict(new_state),
                is_delta=False,
                version_tag=current_tag,
                mtime=d_layer_mtime,
                file_mtimes=d_mtimes,
            )
        )
    else:
        head_state = primary.materialize_layer_state(head.ordinal)
        delta = compute_tree_delta(head_state, new_state)
        if delta and integrity.is_modified(root):
            d_layer_mtime, d_mtimes = _canonical_layer_mtimes(root, delta)
            declared_base = current_tag.split("+")[0]
            mod_hash = integrity.modification_hash(root)
            mod_tag = f"{declared_base}+mod.{mod_hash}"
            delta = _set_layer_version_tag(delta, mod_tag)
            primary.append_layer(
                Layer(
                    delta,
                    is_delta=True,
                    version_tag=mod_tag,
                    mtime=d_layer_mtime,
                    file_mtimes=d_mtimes,
                )
            )

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

    if not os.environ.get("DWIMSY_REBUNDLE_VERIFYING"):
        verify_bundle_roundtrip(script_text, repo_root=root)

    if out_name == "-":
        stdout.write(script_text)
        return 0
    if getattr(args, "dry_run", False):
        out_path = Path(out_name).resolve()
        print("[DRY-RUN] Would generate bundle:", file=stderr)
        print(f"  {out_path}", file=stderr)
        if out_path.suffix == ".py":
            print(f"  {out_path.with_suffix('.pyz')}", file=stderr)
        return 0
    layer_ts = None
    if vspace.streams and vspace.streams[0].layers:
        head_v = vspace.streams[0].get_head_version()
        if head_v:
            layer_ts = vspace.get_layer_timestamp(
                vspace.streams[0].layers[head_v.ordinal]
            )
    if not layer_ts:
        _, layer_ts = integrity.get_latest_release_info(root)

    out_path = Path(out_name).resolve()
    is_default_out = not getattr(args, "output", None)
    generated_paths = [out_path]
    if out_path.suffix == ".py":
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(script_text, encoding="utf-8")
        out_path.chmod(0o755)
        if layer_ts:
            try:
                ts_ep = unbundle._timestamp_epoch(layer_ts)
                if ts_ep is not None:
                    os.utime(out_path, (ts_ep, ts_ep))
            except OSError:
                pass
        if is_default_out:
            pyz_out = out_path.with_suffix(".pyz")
            write_pyz_bundle(script_text, pyz_out, timestamp=layer_ts)
            try:
                pyz_out.chmod(0o755)
            except OSError:
                pass
            generated_paths.append(pyz_out)
    elif out_path.suffix == ".pyz":
        write_pyz_bundle(script_text, out_path, timestamp=layer_ts)
        try:
            out_path.chmod(0o755)
        except OSError:
            pass
    else:
        raise ValueError(f"Unsupported output extension '{out_path.suffix}'")
    if len(generated_paths) == 1:
        print(f"[SUCCESS] Generated bundle -> {generated_paths[0]}", file=stderr)
    else:
        print("[SUCCESS] Generated bundles:", file=stderr)
        for generated in generated_paths:
            print(f"  {generated}", file=stderr)
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
    git_bin = get_git_command(args)
    use_baseline = (
        bool(getattr(args, "baseline", False))
        or not (repo_root / ".git").exists()
        or git_bin is None
    )

    if not use_baseline and git_bin:
        res = subprocess.run(
            [git_bin, "submodule", "update", "--init", "--recursive"],
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
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Bundle clean baseline without working tree delta",
    )
    parser.add_argument(
        "-t", "--tag", default=None, help="Optional short descriptive tag/label"
    )
    parser.add_argument(
        "--with-deps",
        action="store_true",
        help="Include legacy submodule scaffolding from deps/",
    )
    parser.add_argument(
        "--without-git",
        action="store_true",
        help="Do not invoke external git binary across all operations",
    )
    parser.add_argument(
        "--with-git",
        nargs="?",
        const="git",
        default=None,
        help="Enable external git binary or specify custom path",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="List uncommitted/modified and untracked files",
    )
    parser.add_argument(
        "--diff", action="store_true", help="Display working tree diff before bundling"
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force bundle emission, overwriting collisions",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build bundle in memory/temp and display manifest without writing output",
    )
    parser.add_argument(
        "--help-all", action="store_true", help="Show full help documentation and exit"
    )
    parser.add_argument("--version-include", action="append", default=[])
    parser.add_argument("--version-restrict-to", default=None)
    parser.add_argument("--version-prune", default=None)
    parser.add_argument("--version-splice", default=None)
    parser.add_argument("--version-alt", nargs="?", const=True, default=False)
    args = parser.parse_args(effective)

    # Keep the standalone maintainer entry point behaviorally aligned with
    # `dwimsy meta bundle` for the shared baseline/dry-run modes.
    if args.baseline or args.dry_run:
        return run_meta_bundle(args)

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
        d_mtimes = {}
        for name in delta:
            fp = root / name
            if fp.is_file():
                try:
                    d_mtimes[name] = int(fp.stat().st_mtime)
                except OSError:
                    pass
        d_layer_mtime = max(d_mtimes.values()) if d_mtimes else int(time.time())
        d_mtimes = {name: d_layer_mtime for name in delta}
        if is_replace:
            primary.append_layer(
                Layer(
                    delta,
                    is_delta=True,
                    version_tag=v_tag,
                    mtime=d_layer_mtime,
                    file_mtimes=d_mtimes,
                ),
                allow_replacement=True,
            )
        elif delta or not head:
            primary.append_layer(
                Layer(
                    delta,
                    is_delta=True,
                    version_tag=v_tag,
                    mtime=d_layer_mtime,
                    file_mtimes=d_mtimes,
                )
            )
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

    main_ts = None
    if vspace.streams and vspace.streams[0].layers:
        head_v = vspace.streams[0].get_head_version()
        if head_v:
            main_ts = vspace.get_layer_timestamp(
                vspace.streams[0].layers[head_v.ordinal]
            )
    if not main_ts:
        _, main_ts = integrity.get_latest_release_info(root)
    main_epoch = unbundle._timestamp_epoch(main_ts)

    py_name = vspace.composite_bundle_name(".py")
    py_path = root / py_name
    pyz_path = py_path.with_suffix(".pyz")
    py_path.write_text(script_text, encoding="utf-8")
    try:
        py_path.chmod(0o755)
    except OSError:
        pass
    if main_epoch is not None:
        try:
            os.utime(py_path, (main_epoch, main_epoch))
        except OSError:
            pass
    write_pyz_bundle(script_text, pyz_path, timestamp=main_ts)
    try:
        pyz_path.chmod(0o755)
    except OSError:
        pass
    if main_epoch is not None:
        try:
            os.utime(pyz_path, (main_epoch, main_epoch))
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
