"""dwimsy.meta.versions - Multi-stream version reconciliation, layer decoding, and pipeline execution."""

from __future__ import annotations

import base64
import fnmatch
import hashlib
import io
import lzma
import os
import re
import sys
import tarfile
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

_RETAIN_POINT_RELEASES = 3
_RETAIN_MINOR_RELEASES = 3
_RETAIN_MAJOR_RELEASES = 3

_BLZTAR_RE = re.compile(
    rb"(?ms)^(?P<prefix>[ \t]*blztar[ \t]*=[ \t]*\"\"\")(?:.*?)(?P<suffix>\"\"\"[ \t]*(?:#.*)?$)"
)

_DWIMSY_COMMANDS = {
    "meta",
    "unbundle",
    "bundle",
    "version-bump",
    "diff",
    "integrity",
    "lint",
    "convert",
    "inspect",
    "split",
    "join",
    "t882wav",
    "wav2t88",
}

_DWIMSY_ROLES = {"primary", "baseline", "unbundled", "alt"}

REMOVAL_MARKER_PREFIX = ".wh."
DIR_REMOVAL_MARKER_FILE = ".wh..wh..opq"
_HOST_INVALID_CHARS = set('<>:"|?*')
_HOST_RESERVED_NAMES = (
    {"CON", "PRN", "AUX", "NUL", "CLOCK$"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def to_host_fs_component_name(component: str) -> str:
    """Return a Windows/DOS-portable component name, preserving valid names."""
    if not component or component in (".", ".."):
        return component
    invalid = (
        any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in component)
        or any(ch in _HOST_INVALID_CHARS for ch in component)
        or component.endswith(".")
        or component.startswith(" ")
        or component.endswith(" ")
    )
    stem = component.rsplit(".", 1)[0]
    reserved = stem.rstrip(" .").upper() in _HOST_RESERVED_NAMES
    if not invalid and not reserved:
        return component
    # Encode the complete offending stem for reserved device names; otherwise
    # encode only bytes that cannot occur in a portable component.
    if reserved:
        suffix = ""
        if "." in component:
            suffix = component[component.rfind(".") :]
        return "".join(f"%{b:02X}" for b in stem.encode("utf-8")) + suffix
    out = []
    for ch in component:
        if ord(ch) < 0x20 or ord(ch) == 0x7F or ch in _HOST_INVALID_CHARS:
            out.extend(f"%{b:02X}" for b in ch.encode("utf-8"))
        else:
            out.append(ch)
    return "".join(out).rstrip(".")


def portable_path_error(path: str) -> Optional[str]:
    """Return a diagnostic for the first non-portable path component."""
    for component in Path(path).parts:
        if component in (".", ".."):
            continue
        converted = to_host_fs_component_name(component)
        if component.startswith(REMOVAL_MARKER_PREFIX):
            return f"path '{path}' contains disallowed removal-marker component '{component}'."
        if component != converted:
            return f"path '{path}' contains disallowed component '{component}'.\nSuggested safe rename: '{Path(path).parent.joinpath(converted, Path(path).name).as_posix() if Path(path).name == component else str(Path(path).parent / converted)}'"
    return None


def collision_key(s: str) -> str:
    """Return the NFKC casefolded canonical collision key for string s."""
    return unicodedata.normalize("NFKC", s).casefold()


def validate_version_tag(tag: str) -> None:
    """Validate user version tag according to strict character and reserved keyword rules."""
    if not tag:
        raise ValueError("Version tag cannot be empty.")

    tag_lower = tag.lower()

    if tag_lower == "sealed" or tag_lower.endswith("_sealed"):
        raise ValueError(
            f"Version tag '{tag}' cannot be 'sealed' or end with '_sealed' (reserved)."
        )

    if tag_lower in _DWIMSY_COMMANDS:
        raise ValueError(f"Version tag '{tag}' cannot be a dwimsy command word.")
    if tag_lower in _DWIMSY_ROLES:
        raise ValueError(f"Version tag '{tag}' cannot be a dwimsy role name.")

    if (
        tag_lower.startswith("primary_")
        or tag_lower.startswith("baseline_")
        or tag_lower.startswith("unbundled_")
    ):
        raise ValueError(f"Version tag '{tag}' cannot start with reserved prefix.")
    if tag_lower.startswith("alt0_") or tag_lower == "alt0":
        raise ValueError("alt0_ is not valid; use 'primary_' or a bare tag.")
    if re.match(r"^alt\d+_", tag_lower) or re.match(r"^alt\d+$", tag_lower):
        raise ValueError(f"Version tag '{tag}' cannot start with 'altN_' prefix.")

    if ".." in tag:
        raise ValueError(f"Version tag '{tag}' cannot contain consecutive dots.")

    if not re.match(r"^[0-9A-Za-z](?:[0-9A-Za-z._+-]*[0-9A-Za-z])?$", tag):
        raise ValueError(f"Version tag '{tag}' contains invalid characters.")


def parse_semver(tag: str) -> Tuple[int, int, int, int, bool, str]:
    """Parse a version tag into a sortable semver tuple.

    DWIMSY permits local ``+mod.<hash>`` tags.  Their ordering semantics are
    those of their base version, so build metadata is ignored for ordering.
    """
    t = tag
    if "_" in t:
        t = t.split("_")[-1]

    m = re.match(
        r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?"
        r"(?:-([0-9A-Za-z._+-]+))?(?:\+([0-9A-Za-z._+-]+))?$",
        t,
    )
    if m:
        major = int(m.group(1) or 0)
        minor = int(m.group(2) or 0)
        patch = int(m.group(3) or 0)
        rev = int(m.group(4) or 0)
        suffix = m.group(5) or ""
        build = m.group(6) or ""
        return (major, minor, patch, rev, suffix == "", suffix or build)
    return (0, 0, 0, 0, False, tag)


_B64_BLOCK_RE = re.compile(rb"[A-Za-z0-9+/]+={1,2}|[A-Za-z0-9+/]+")


def decode_multiblock_base64(b64_text: str | bytes) -> bytes:
    """Decode standard and multi-block Base64 strings with optional padding boundaries."""
    if isinstance(b64_text, str):
        raw = b"".join(b64_text.encode("ascii", errors="ignore").split())
    else:
        raw = b"".join(b64_text.split())
    if not raw:
        return b""
    if b"=" not in raw or (raw.endswith(b"=") and b"=" not in raw[:-2]):
        try:
            return base64.b64decode(raw)
        except Exception:
            pass
    chunks = []
    for m in _B64_BLOCK_RE.finditer(raw):
        blk = m.group(0)
        try:
            chunks.append(base64.b64decode(blk))
        except Exception:
            pass
    return b"".join(chunks)


def encode_multiblock_base64(data: bytes) -> str:
    """Encode bytes into Base64 wrapped at 76 columns."""
    b64 = base64.b64encode(data).decode("ascii")
    lines = [b64[i : i + 76] for i in range(0, len(b64), 76)]
    return "\n".join(lines)


def demux_lzma_streams(raw_bytes: bytes) -> Tuple[List[bytes], List[bytes]]:
    """Demux concatenated LZMA streams using LZMADecompressor eof and unused_data boundaries."""
    uncompressed_streams: List[bytes] = []
    compressed_chunks: List[bytes] = []
    buf = raw_bytes
    while buf:
        decomp = lzma.LZMADecompressor()
        try:
            out = decomp.decompress(buf)
            if not decomp.eof:
                break
        except Exception:
            break
        consumed_len = len(buf) - len(decomp.unused_data)
        compressed_chunks.append(buf[:consumed_len])
        uncompressed_streams.append(out)
        buf = decomp.unused_data
    return uncompressed_streams, compressed_chunks


class VersionRef:
    """Reference to a version within a version space."""

    def __init__(
        self,
        stream_index: int,
        stream_name: str,
        tag: str,
        sealed: bool,
        ordinal: int,
        source: str,
        content_hash: str,
    ):
        self.stream_index = stream_index
        self.stream_name = stream_name
        self.tag = tag
        self.sealed = sealed
        self.ordinal = ordinal
        self.source = source
        self.content_hash = content_hash

    @property
    def qualified_tag(self) -> str:
        if self.stream_index == 0:
            return f"primary_{self.tag}"
        return f"{self.stream_name}_{self.tag}"

    def __repr__(self) -> str:
        return f"VersionRef(stream={self.stream_name}, tag={self.tag}, sealed={self.sealed}, ordinal={self.ordinal}, hash={self.content_hash[:8]})"


class Layer:
    """A single TAR archive layer (base snapshot, delta overlay, or sealed historical release)."""

    def __init__(
        self,
        files: Dict[str, bytes],
        tar_bytes: Optional[bytes] = None,
        is_delta: bool = False,
        version_tag: Optional[str] = None,
        code_hash: Optional[str] = None,
    ):
        self.files = {}
        for k, v in files.items():
            clean_k = (
                k[len("<dwimsy-bundle>/") :] if k.startswith("<dwimsy-bundle>/") else k
            )
            self.files[clean_k] = v

        if (
            "dwimsy/meta/unbundle.py" in self.files
            or "./dwimsy/meta/unbundle.py" in self.files
        ):
            try:
                from dwimsy.meta.unbundle import elide_blztar_bytes
            except ImportError:

                def elide_blztar_bytes(data: bytes) -> bytes:
                    match = re.search(
                        rb"(?ms)^(?P<prefix>[ \t]*blztar[ \t]*=[ \t]*\"\"\")(?:.*?)(?P<suffix>\"\"\"[ \t]*(?:#.*)?$)",
                        data,
                    )
                    if match:
                        return (
                            data[: match.start()]
                            + match.group("prefix")
                            + b"\n"
                            + match.group("suffix")
                            + data[match.end() :]
                        )
                    return data

            if "dwimsy/meta/unbundle.py" in self.files:
                self.files["dwimsy/meta/unbundle.py"] = elide_blztar_bytes(
                    self.files["dwimsy/meta/unbundle.py"]
                )
            if "./dwimsy/meta/unbundle.py" in self.files:
                self.files["./dwimsy/meta/unbundle.py"] = elide_blztar_bytes(
                    self.files["./dwimsy/meta/unbundle.py"]
                )

        self.tar_bytes = tar_bytes
        self.is_delta = is_delta
        self.version_tag = version_tag or self._extract_version_tag()
        self.code_hash = (
            code_hash if code_hash is not None else self._extract_code_hash()
        )
        self.sealed = bool(self.code_hash and self.code_hash.strip())

    def _extract_version_tag(self) -> str:
        v_data = self.files.get("dwimsy/_version.py") or self.files.get("_version.py")
        if v_data:
            text = v_data.decode("utf-8", errors="ignore")
            m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
            if m:
                return m.group(1)
        return "0.1.6.0-dev"

    def _extract_code_hash(self) -> str:
        v_data = self.files.get("dwimsy/_version.py") or self.files.get("_version.py")
        if v_data:
            text = v_data.decode("utf-8", errors="ignore")
            m = re.search(r'__code_hash__\s*=\s*["\']([^"\']*)["\']', text)
            if m:
                return m.group(1)
        return ""

    def get_tar_bytes(self) -> bytes:
        if self.tar_bytes is not None:
            return self.tar_bytes
        bio = io.BytesIO()
        with tarfile.open(fileobj=bio, mode="w:") as tar:
            for name in sorted(self.files.keys()):
                data = self.files[name]
                ti = tarfile.TarInfo(name=name)
                ti.size = len(data)
                ti.mtime = 1700000000
                ti.mode = (
                    0o755
                    if (name.endswith(".py") and data.startswith(b"#!"))
                    else 0o644
                )
                tar.addfile(ti, io.BytesIO(data))
        self.tar_bytes = bio.getvalue()
        return self.tar_bytes


class Stream:
    """A stream representing a line of history (primary or altN)."""

    def __init__(
        self,
        index: int,
        name: str,
        layers: Optional[List[Layer]] = None,
        raw_lzma_bytes: Optional[bytes] = None,
        source: str = "",
    ):
        self.index = index
        self.name = name
        self.layers: List[Layer] = list(layers) if layers is not None else []
        self.raw_lzma_bytes = raw_lzma_bytes
        self.source = source or ("dwimsy" if index == 0 else f"alt{index}")

    def copy(self) -> Stream:
        new_layers = [
            Layer(
                dict(lyr.files),
                lyr.tar_bytes,
                lyr.is_delta,
                lyr.version_tag,
                lyr.code_hash,
            )
            for lyr in self.layers
        ]
        return Stream(
            self.index, self.name, new_layers, self.raw_lzma_bytes, self.source
        )

    def mark_mutated(self):
        self.raw_lzma_bytes = None

    def get_open_dev_layer_count(self) -> int:
        """Return the number of open dev layers on top of base snapshot."""
        if not self.layers:
            return 0
        count = 0
        for lyr in self.layers[1:]:
            if not lyr.sealed:
                count += 1
            else:
                break
        return count

    def materialize_layer_state(self, layer_idx: int) -> Dict[str, bytes]:
        """Materialize the full asset dictionary for a specific layer index."""
        if not self.layers or layer_idx < 0 or layer_idx >= len(self.layers):
            return {}

        target_lyr = self.layers[layer_idx]
        if not target_lyr.is_delta:
            return dict(target_lyr.files)

        state: Dict[str, bytes] = dict(self.layers[0].files)
        for i in range(1, layer_idx + 1):
            lyr = self.layers[i]
            for fname, fdata in lyr.files.items():
                p = Path(fname)
                if p.name.startswith(".wh."):
                    real_name = (
                        (p.parent / p.name[4:]).as_posix()
                        if str(p.parent) != "."
                        else p.name[4:]
                    )
                    state.pop(real_name, None)
                else:
                    state[fname] = fdata
        return state

    def compute_content_hash(self, layer_idx: int) -> str:
        """Compute canonical code hash for layer at layer_idx."""
        state = self.materialize_layer_state(layer_idx)
        from dwimsy.meta import integrity

        digest = hashlib.sha256()
        for rel in sorted(state.keys()):
            data = state[rel]
            cdata = integrity._canonical_bytes(data, rel)
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(cdata)
            digest.update(b"\0")
        return digest.hexdigest()

    def get_versions(self) -> List[VersionRef]:
        """Return list of VersionRefs in this stream."""
        if not self.layers:
            return []

        refs: List[VersionRef] = []
        open_count = self.get_open_dev_layer_count()

        for i in range(open_count + 1):
            if i < len(self.layers):
                lyr = self.layers[i]
                chash = self.compute_content_hash(i)
                mat = self.materialize_layer_state(i)
                v_data = mat.get("dwimsy/_version.py") or mat.get("_version.py")
                tag = lyr.version_tag
                sealed = lyr.sealed
                if v_data:
                    t = v_data.decode("utf-8", errors="ignore")
                    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', t)
                    if m:
                        tag = m.group(1)
                    m2 = re.search(r'__code_hash__\s*=\s*["\']([^"\']*)["\']', t)
                    if m2:
                        sealed = bool(m2.group(1).strip())
                refs.append(
                    VersionRef(
                        stream_index=self.index,
                        stream_name=self.name,
                        tag=tag,
                        sealed=sealed,
                        ordinal=i,
                        source=self.source,
                        content_hash=chash,
                    )
                )

        for i in range(open_count + 1, len(self.layers)):
            lyr = self.layers[i]
            chash = self.compute_content_hash(i)
            mat = self.materialize_layer_state(i)
            v_data = mat.get("dwimsy/_version.py") or mat.get("_version.py")
            tag = lyr.version_tag
            sealed = True
            if v_data:
                t = v_data.decode("utf-8", errors="ignore")
                m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', t)
                if m:
                    tag = m.group(1)
            refs.append(
                VersionRef(
                    stream_index=self.index,
                    stream_name=self.name,
                    tag=tag,
                    sealed=sealed,
                    ordinal=i,
                    source=self.source,
                    content_hash=chash,
                )
            )
        return refs

    def get_head_version(self) -> Optional[VersionRef]:
        """Return the head VersionRef of this stream."""
        versions = self.get_versions()
        if not versions:
            return None
        open_count = self.get_open_dev_layer_count()
        if open_count < len(versions):
            return versions[open_count]
        return versions[-1]

    def seal_open_dev(self) -> None:
        """Seal open development layers into a single standalone base snapshot."""
        if not self.layers:
            return
        self.mark_mutated()
        open_count = self.get_open_dev_layer_count()
        head_state = self.materialize_layer_state(open_count)

        from dwimsy.meta import integrity

        digest = hashlib.sha256()
        for rel in sorted(head_state.keys()):
            data = head_state[rel]
            cdata = integrity._canonical_bytes(data, rel)
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(cdata)
            digest.update(b"\0")
        code_hash = digest.hexdigest()

        for v_path in ["dwimsy/_version.py", "_version.py"]:
            if v_path in head_state:
                raw_v = head_state[v_path]
                match = integrity._HASH_RE.search(raw_v)
                if match:
                    rep = (
                        match.group("prefix")
                        + match.group("quote")
                        + code_hash.encode("ascii")
                        + match.group("quote")
                        + match.group("suffix")
                    )
                    head_state[v_path] = (
                        raw_v[: match.start()] + rep + raw_v[match.end() :]
                    )
                break

        old_base = self.layers[0]
        new_base_layer = Layer(head_state, is_delta=False, code_hash=code_hash)

        historical_layers = []
        if old_base.sealed:
            historical_layers.append(old_base)
        for i in range(open_count + 1, len(self.layers)):
            historical_layers.append(self.layers[i])

        historical_layers.sort(
            key=lambda lyr: parse_semver(lyr.version_tag), reverse=True
        )
        self.layers = [new_base_layer] + historical_layers
        if self.index == 0:
            self.apply_retention()

    def apply_retention(self) -> None:
        """Apply primary stream historical retention limits."""
        if self.index != 0:
            return
        open_count = self.get_open_dev_layer_count()
        if len(self.layers) <= open_count + 1:
            return

        historical = self.layers[open_count + 1 :]
        historical.sort(key=lambda lyr: parse_semver(lyr.version_tag), reverse=True)

        surviving = []
        point_counts: Dict[Tuple[int, int], int] = {}
        minor_counts: Dict[int, int] = {}
        major_set: Set[int] = set()

        for lyr in historical:
            sem = parse_semver(lyr.version_tag)
            maj, mino, pat, rev, is_rel, suffix = sem

            if maj not in major_set and len(major_set) >= _RETAIN_MAJOR_RELEASES:
                warnings.warn(
                    f"[NOTICE] Pruning historical release '{lyr.version_tag}' from primary stream: exceeds major retention limit (max {_RETAIN_MAJOR_RELEASES} major)",
                    UserWarning,
                    stacklevel=2,
                )
                self.mark_mutated()
                continue

            m_count = minor_counts.get(maj, 0)
            if m_count >= _RETAIN_MINOR_RELEASES and (maj, mino) not in point_counts:
                warnings.warn(
                    f"[NOTICE] Pruning historical release '{lyr.version_tag}' from primary stream: exceeds minor retention limit (max {_RETAIN_MINOR_RELEASES} minor)",
                    UserWarning,
                    stacklevel=2,
                )
                self.mark_mutated()
                continue

            p_count = point_counts.get((maj, mino), 0)
            if p_count >= _RETAIN_POINT_RELEASES:
                warnings.warn(
                    f"[NOTICE] Pruning historical release '{lyr.version_tag}' from primary stream: exceeds point retention limit (max {_RETAIN_POINT_RELEASES} point)",
                    UserWarning,
                    stacklevel=2,
                )
                self.mark_mutated()
                continue

            major_set.add(maj)
            if (maj, mino) not in point_counts:
                minor_counts[maj] = minor_counts.get(maj, 0) + 1
            point_counts[(maj, mino)] = p_count + 1
            surviving.append(lyr)

        self.layers = self.layers[: open_count + 1] + surviving

    def append_layer(self, layer: Layer, allow_replacement: bool = False) -> None:
        """Append layer enforcing writing invariants (§1.1.1, §1.4)."""
        if not self.layers:
            if layer.is_delta:
                raise ValueError(
                    "Layer 0 must be a complete base snapshot (is_delta=False)."
                )
            self.layers.append(layer)
            self.mark_mutated()
            return

        tag_lower = layer.version_tag.lower()
        head = self.layers[-1]
        base_head = head.version_tag.split("+")[0].lower()
        base_new = layer.version_tag.split("+")[0].lower()
        if allow_replacement and "+mod." in head.version_tag.lower():
            head_base_semver = parse_semver(base_head)
            new_base_semver = parse_semver(base_new)
            if base_head == base_new or new_base_semver > head_base_semver:
                self.layers[-1] = layer
                self.mark_mutated()
                return
        elif allow_replacement and base_head == base_new:
            self.layers[-1] = layer
            self.mark_mutated()
            return

        if any(l.version_tag.lower() == tag_lower for l in self.layers):
            raise ValueError(
                f"Cannot add duplicate version tag '{layer.version_tag}' to stream '{self.name}' (§1.1.1 violation)."
            )

        initial_semver = parse_semver(self.layers[0].version_tag)
        curr_semver = parse_semver(layer.version_tag)
        is_tip = curr_semver >= initial_semver

        if is_tip:
            if layer.code_hash:
                raise ValueError(
                    f"Sealed layer cannot be appended in tip sequence for stream '{self.name}'."
                )
            if not layer.is_delta:
                raise ValueError(
                    f"Tip sequence overlay layer after Layer 0 must be an incremental delta (is_delta=True) for stream '{self.name}'."
                )
            if any("+mod." in l.version_tag.lower() for l in self.layers):
                raise ValueError(
                    f"Cannot append layer following terminal '+mod' layer in tip sequence for stream '{self.name}'."
                )
            tip_layers = [
                l for l in self.layers if parse_semver(l.version_tag) >= initial_semver
            ]
            if tip_layers and curr_semver <= parse_semver(tip_layers[-1].version_tag):
                raise ValueError(
                    f"Tip sequence layer semver '{layer.version_tag}' must be strictly greater than preceding layer '{tip_layers[-1].version_tag}'."
                )
        else:
            if not layer.code_hash:
                raise ValueError(
                    f"Post-tip historical layer '{layer.version_tag}' must be sealed with non-empty code hash."
                )
            if layer.is_delta or any(
                p.name.startswith(".wh.") for p in [Path(f) for f in layer.files]
            ):
                raise ValueError(
                    f"Post-tip sealed release '{layer.version_tag}' must be complete snapshot without removal markers."
                )
            sealed_layers = [
                l for l in self.layers if parse_semver(l.version_tag) < initial_semver
            ]
            if sealed_layers and curr_semver >= parse_semver(
                sealed_layers[-1].version_tag
            ):
                raise ValueError(
                    f"Post-tip sealed release semver '{layer.version_tag}' must be strictly decreasing from '{sealed_layers[-1].version_tag}'."
                )

        self.layers.append(layer)
        self.mark_mutated()

    def encode_lzma_bytes(self) -> bytes:
        """Encode this stream into compressed LZMA bytes with memory readback validation."""
        if self.raw_lzma_bytes is not None:
            return self.raw_lzma_bytes
        if not self.layers:
            self.raw_lzma_bytes = lzma.compress(b"")
            return self.raw_lzma_bytes

        tar_buffers = []
        for lyr in self.layers:
            tar_buffers.append(lyr.get_tar_bytes())

        concat_tars = b"".join(tar_buffers)

        # Roundtrip readback validation in memory before accepting serialized payload
        readback_layers = parse_tar_layers_from_bytes(
            concat_tars, stream_name=self.name
        )
        if len(readback_layers) != len(self.layers):
            raise RuntimeError(
                f"Serialization readback validation failed for stream '{self.name}': expected {len(self.layers)} layers, got {len(readback_layers)}."
            )

        self.raw_lzma_bytes = lzma.compress(
            concat_tars, preset=(9 | lzma.PRESET_EXTREME)
        )
        return self.raw_lzma_bytes


def compute_tree_delta(
    base_state: Dict[str, bytes], new_state: Dict[str, bytes]
) -> Dict[str, bytes]:
    """Compute delta layer files (added, modified, and .wh. removal marker files) between base_state and new_state."""
    delta_files: Dict[str, bytes] = {}

    for name, data in new_state.items():
        if name not in base_state or base_state[name] != data:
            delta_files[name] = data

    for name in base_state:
        if name not in new_state:
            p = Path(name)
            wh_name = (
                (p.parent / f".wh.{p.name}").as_posix()
                if str(p.parent) != "."
                else f".wh.{p.name}"
            )
            delta_files[wh_name] = b""

    return delta_files


def compute_raw_tar_hash(files: Dict[str, bytes]) -> str:
    """Compute canonical hash of files dictionary for +mod tag derivation."""
    digest = hashlib.sha256()
    for name in sorted(files.keys()):
        data = files[name]
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if data and not data.endswith(b"\n"):
            data = data + b"\n"
        if name.endswith("_version.py"):
            match = re.search(
                rb"(?m)^(?P<prefix>[ \t]*__code_hash__[ \t]*=[ \t]*)(?P<quote>[\'\"])[^\'\"]*(?P=quote)(?P<suffix>[ \t]*(?:#.*)?\r?\n?)$",
                data,
            )
            if match:
                data = (
                    data[: match.start()]
                    + match.group("prefix")
                    + match.group("quote")
                    + match.group("quote")
                    + match.group("suffix")
                    + data[match.end() :]
                )
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def parse_tar_layers_from_bytes(
    raw_tar_bytes: bytes, stream_name: str = "primary"
) -> List[Layer]:
    """Parse concatenated TAR layers from raw bytes with strict semver & position-based invariant validation (§1.1.1)."""
    if not raw_tar_bytes or all(b == 0 for b in raw_tar_bytes):
        return []

    layers: List[Layer] = []
    seen_semvers: Set[Tuple] = set()
    offset = 0
    total = len(raw_tar_bytes)

    in_tip = True
    initial_semver: Optional[Tuple] = None
    last_tip_semver: Optional[Tuple] = None
    last_sealed_semver: Optional[Tuple] = None
    has_mod_in_tip = False
    base_state: Dict[str, bytes] = {}
    materialized_state: Dict[str, bytes] = {}

    while offset < total:
        remaining = raw_tar_bytes[offset:]
        if not remaining or all(b == 0 for b in remaining):
            break

        tar_bio = io.BytesIO(remaining)
        try:
            with tarfile.open(fileobj=tar_bio, mode="r:") as tar:
                files: Dict[str, bytes] = {}
                for m in tar:
                    if m.isfile():
                        norm_name = m.name[2:] if m.name.startswith("./") else m.name
                        f = tar.extractfile(m)
                        files[norm_name] = f.read() if f is not None else b""

                consumed = tar_bio.tell()
                if consumed % 512 != 0:
                    consumed += 512 - (consumed % 512)
                while (
                    offset + consumed < total
                    and raw_tar_bytes[offset + consumed : offset + consumed + 512]
                    == b"\x00" * 512
                ):
                    consumed += 512

                layer_bytes = raw_tar_bytes[offset : offset + consumed]
                offset += consumed

                has_wh = any(Path(name).name.startswith(".wh.") for name in files)
                l_idx = len(layers)

                # Extract version tag & code_hash from layer or materialized state
                v_data = (
                    files.get("dwimsy/_version.py")
                    or files.get("_version.py")
                    or materialized_state.get("dwimsy/_version.py")
                    or materialized_state.get("_version.py")
                )
                tag_str = ""
                sealed = False
                if v_data:
                    t = v_data.decode("utf-8", errors="ignore")
                    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', t)
                    if m:
                        tag_str = m.group(1)
                    m2 = re.search(r'__code_hash__\s*=\s*["\']([^"\']*)["\']', t)
                    if m2:
                        sealed = bool(m2.group(1).strip())

                if not tag_str:
                    tag_str = "0.1.6.0-dev" if l_idx == 0 else f"0.1.6.{l_idx}-dev"

                is_mod_layer = "+mod." in tag_str
                curr_semver = parse_semver(tag_str)

                # Update in-memory materialized state
                if l_idx == 0 or (
                    initial_semver is not None and curr_semver < initial_semver
                ):
                    materialized_state = dict(files)
                    if l_idx == 0:
                        base_state = dict(files)
                else:
                    for name, data in files.items():
                        p = Path(name)
                        if p.name.startswith(".wh."):
                            real_name = (
                                (p.parent / p.name[4:]).as_posix()
                                if str(p.parent) != "."
                                else p.name[4:]
                            )
                            materialized_state.pop(real_name, None)
                        else:
                            materialized_state[name] = data

                # =============================================================
                # STRICT SEMVER & POSITION INVARIANTS (§1.1.1)
                # =============================================================
                if l_idx == 0:
                    initial_semver = curr_semver
                    last_tip_semver = curr_semver
                    has_mod_in_tip = is_mod_layer
                    seen_semvers.add(curr_semver)
                    lyr = Layer(
                        files,
                        tar_bytes=layer_bytes,
                        is_delta=False,
                        version_tag=tag_str,
                        code_hash=(
                            m2.group(1).strip() if (v_data and m2 and sealed) else ""
                        ),
                    )
                    layers.append(lyr)
                    continue

                if in_tip and curr_semver >= initial_semver:
                    # Invariant 1: Only the first entry in tip sequence is allowed to be sealed
                    if sealed:
                        reason = f"sealed tar encountered at layer {l_idx} in open development tip sequence; only layer 0 may be sealed."
                        if stream_name == "primary":
                            raise RuntimeError(
                                f"Primary stream tip sequence constraint violation at layer {l_idx}: {reason}"
                            )
                        else:
                            warn_msg = f"warning: alternate stream '{stream_name}' invalidated: {reason}"
                            warnings.warn(warn_msg, UserWarning, stacklevel=2)
                            return []

                    # Invariant 2: Strict Monotonic Increasing Semver Check in Tip Sequence
                    if curr_semver <= last_tip_semver or curr_semver in seen_semvers:
                        reason = f"semver '{tag_str}' is not strictly greater than preceding tip semver (duplicate or decreasing order)."
                        if stream_name == "primary":
                            raise RuntimeError(
                                f"Primary stream tip sequence constraint violation at layer {l_idx}: {reason}"
                            )
                        else:
                            warn_msg = f"warning: alternate stream '{stream_name}' invalidated: {reason}"
                            warnings.warn(warn_msg, UserWarning, stacklevel=2)
                            return []

                    # Invariant 3: Only the LAST tar in the tip sequence is allowed to be +mod
                    if has_mod_in_tip:
                        reason = f"layer {l_idx} follows a preceding '+mod' layer in tip sequence; '+mod' must be terminal."
                        if stream_name == "primary":
                            raise RuntimeError(
                                f"Primary stream tip sequence constraint violation at layer {l_idx}: {reason}"
                            )
                        else:
                            warn_msg = f"warning: alternate stream '{stream_name}' invalidated: {reason}"
                            warnings.warn(warn_msg, UserWarning, stacklevel=2)
                            return []

                    last_tip_semver = curr_semver
                    has_mod_in_tip = is_mod_layer
                    seen_semvers.add(curr_semver)
                    lyr = Layer(
                        files, tar_bytes=layer_bytes, is_delta=True, version_tag=tag_str
                    )
                    layers.append(lyr)
                    continue

                elif curr_semver < initial_semver:
                    in_tip = False

                    # Invariant 4: Only sealed entries are allowed after tip sequence
                    if not sealed:
                        warnings.warn(
                            f"warning: stream '{stream_name}' unsealed release '{tag_str}' encountered in sealed release area; truncating stream (§1.1.1)",
                            UserWarning,
                            stacklevel=2,
                        )
                        break

                    # Invariant 5: Sealed releases MUST be complete snapshots (no .wh. removal markers allowed!)
                    if has_wh:
                        warnings.warn(
                            f"warning: stream '{stream_name}' sealed release at layer {l_idx} contains removal markers; truncating stream (§1.1.1)",
                            UserWarning,
                            stacklevel=2,
                        )
                        break

                    # Invariant 6: Strict Monotonic Decreasing Semver Check in Sealed Area
                    if (
                        last_sealed_semver is not None
                        and curr_semver >= last_sealed_semver
                    ):
                        warnings.warn(
                            f"warning: stream '{stream_name}' sealed release '{tag_str}' is not strictly decreasing; truncating stream (§1.1.1)",
                            UserWarning,
                            stacklevel=2,
                        )
                        break

                    last_sealed_semver = curr_semver
                    seen_semvers.add(curr_semver)
                    lyr = Layer(
                        files,
                        tar_bytes=layer_bytes,
                        is_delta=False,
                        version_tag=tag_str,
                        code_hash=(m2.group(1).strip() if (v_data and m2) else ""),
                    )
                    layers.append(lyr)
                    continue
                else:
                    warnings.warn(
                        f"warning: stream '{stream_name}' encountered invalid semver sequence at '{tag_str}'; truncating stream",
                        UserWarning,
                        stacklevel=2,
                    )
                    break

        except (RuntimeError, ValueError):
            raise
        except Exception as e:
            if stream_name == "primary" and len(layers) == 0:
                raise RuntimeError(
                    f"Failed to parse base development layer in primary stream: {e}"
                ) from e
            else:
                warnings.warn(
                    f"warning: one or more no-longer-readable old versions were ejected from --version history; tar parsing failed while reading an older sealed release: {e}",
                    UserWarning,
                    stacklevel=2,
                )
                break

    return layers


@dataclass(frozen=True)
class Selection:
    """One immutable position-bound version selection."""

    stream: Stream
    ordinal: int
    version: VersionRef

    @property
    def stream_index(self) -> int:
        return self.stream.index


@dataclass(frozen=True)
class SelectionSet:
    """Immutable one-or-more selection references bound at one argv position."""

    items: Tuple[Selection, ...]

    def __bool__(self) -> bool:
        return bool(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, index):
        return self.items[index]

    @property
    def is_multi(self) -> bool:
        return len(self.items) > 1

    @property
    def first(self) -> Optional[Selection]:
        return self.items[0] if self.items else None

    @classmethod
    def empty(cls) -> "SelectionSet":
        return cls(())

    @classmethod
    def single(
        cls, stream: Stream, ordinal: int, version: VersionRef
    ) -> "SelectionSet":
        return cls((Selection(stream, ordinal, version),))


class VersionSpace:
    """The collection of all streams and their version history."""

    def __init__(self, streams: Optional[List[Stream]] = None):
        self.streams: List[Stream] = list(streams) if streams is not None else []
        if not self.streams:
            self.streams = [Stream(0, "primary")]

    @classmethod
    def from_blztar(cls, b64_text: str | bytes) -> VersionSpace:
        """Decode and demux VersionSpace from base64 blztar representation."""
        raw_bytes = decode_multiblock_base64(b64_text)
        if not raw_bytes:
            return cls([Stream(0, "primary")])

        uncompressed_streams, compressed_chunks = demux_lzma_streams(raw_bytes)
        if not uncompressed_streams:
            return cls([Stream(0, "primary")])

        streams: List[Stream] = []
        for idx, uncompressed in enumerate(uncompressed_streams):
            s_name = "primary" if idx == 0 else f"alt{idx}"
            c_chunk = compressed_chunks[idx] if idx < len(compressed_chunks) else None
            layers = parse_tar_layers_from_bytes(uncompressed, stream_name=s_name)
            streams.append(
                Stream(
                    index=idx,
                    name=s_name,
                    layers=layers,
                    raw_lzma_bytes=c_chunk,
                    source="." if idx == 0 else f"alt{idx}",
                )
            )

        return cls(streams)

    def to_blztar(self) -> str:
        """Encode VersionSpace to base64 blztar string with memory readback validation (§1.3)."""
        compressed_blocks = []
        for s in self.streams:
            if getattr(s, "raw_lzma_bytes", None) is not None and not getattr(
                s, "mutated", False
            ):
                c = s.raw_lzma_bytes
            else:
                c = s.encode_lzma_bytes()
            compressed_blocks.append(c)

        concat_lzma = b"".join(compressed_blocks)
        b64_res = encode_multiblock_base64(concat_lzma)

        # In-memory roundtrip validation (§1.3)
        rb_vs = VersionSpace.from_blztar(b64_res)
        if len(rb_vs.streams) != len(self.streams):
            raise RuntimeError(
                f"VersionSpace.to_blztar serialization readback validation failed: expected {len(self.streams)} streams, got {len(rb_vs.streams)}."
            )
        for s_orig, s_rb in zip(self.streams, rb_vs.streams):
            if len(s_orig.layers) != len(s_rb.layers):
                raise RuntimeError(
                    f"VersionSpace.to_blztar readback failed for stream '{s_orig.name}': expected {len(s_orig.layers)} layers, got {len(s_rb.layers)}."
                )
            for ordinal, (l_orig, l_rb) in enumerate(zip(s_orig.layers, s_rb.layers)):
                if l_orig.version_tag != l_rb.version_tag:
                    raise RuntimeError(
                        f"VersionSpace.to_blztar readback failed for stream '{s_orig.name}': tag mismatch '{l_orig.version_tag}' vs '{l_rb.version_tag}'."
                    )
                if s_orig.compute_content_hash(ordinal) != s_rb.compute_content_hash(
                    ordinal
                ):
                    raise RuntimeError(
                        f"VersionSpace.to_blztar readback failed for stream '{s_orig.name}': content hash mismatch in layer '{l_orig.version_tag}'."
                    )

        return b64_res

    def renumber_streams(self):
        """Renumber streams so primary is 0 and alternates are alt1, alt2, ..."""
        for idx, s in enumerate(self.streams):
            s.index = idx
            s.name = "primary" if idx == 0 else f"alt{idx}"

    def get_all_versions(self) -> List[VersionRef]:
        """Return all VersionRefs across all streams."""
        all_refs: List[VersionRef] = []
        for s in self.streams:
            all_refs.extend(s.get_versions())
        return all_refs

    def resolve_selection(
        self, selector: str, unbundled_dir: Optional[Path] = None
    ) -> SelectionSet:
        """Resolve a selector to an immutable SelectionSet at this position."""
        sel = selector.strip()
        sel_lower = sel.lower()

        if (
            sel_lower.endswith("_sealed")
            and sel_lower not in ("sealed", "primary_sealed", "alt_sealed")
            and not re.match(r"^alt\d+_sealed$", sel_lower)
        ):
            raise ValueError(f"Invalid single-version selector '{selector}'.")
        if sel_lower == "*_sealed":
            raise ValueError(
                "'*_sealed' is a filter set selector, not valid as a single-version selector."
            )
        if sel_lower == "unbundled":
            return SelectionSet.empty()

        if sel_lower == "baseline":
            p_stream = self.streams[0]
            refs = p_stream.get_versions()
            refs = [
                v
                for v in refs
                if not v.tag.lower().split("+", 1)[-1].startswith("mod.")
            ]
            if not refs:
                return SelectionSet.empty()
            v = max(refs, key=lambda ref: (parse_semver(ref.tag), ref.ordinal))
            return SelectionSet.single(p_stream, v.ordinal, v)

        if sel_lower == "primary":
            p_stream = self.streams[0]
            head = p_stream.get_head_version()
            return (
                SelectionSet.single(p_stream, head.ordinal, head)
                if head
                else SelectionSet.empty()
            )

        if sel_lower in ("sealed", "primary_sealed"):
            p_stream = self.streams[0]
            for v in reversed(p_stream.get_versions()):
                if v.sealed:
                    return SelectionSet.single(p_stream, v.ordinal, v)
            return SelectionSet.empty()

        if sel_lower == "alt":
            items = []
            for s in self.streams[1:]:
                head = s.get_head_version()
                if head:
                    items.append(Selection(s, head.ordinal, head))
            return SelectionSet(tuple(items))

        if sel_lower == "alt_sealed":
            items = []
            for s in self.streams[1:]:
                for v in reversed(s.get_versions()):
                    if v.sealed:
                        items.append(Selection(s, v.ordinal, v))
                        break
            return SelectionSet(tuple(items))

        m_alt_sealed = re.match(r"^alt(\d+)_sealed$", sel_lower)
        if m_alt_sealed:
            idx = int(m_alt_sealed.group(1))
            if idx < len(self.streams):
                s = self.streams[idx]
                for v in reversed(s.get_versions()):
                    if v.sealed:
                        return SelectionSet.single(s, v.ordinal, v)
            return SelectionSet.empty()

        m_alt = re.match(r"^alt(\d+)$", sel_lower)
        if m_alt:
            idx = int(m_alt.group(1))
            if idx < len(self.streams):
                s = self.streams[idx]
                head = s.get_head_version()
                if head:
                    return SelectionSet.single(s, head.ordinal, head)
            return SelectionSet.empty()

        if sel_lower.startswith("primary_"):
            bare = sel[8:]
            p_stream = self.streams[0]
            for v in p_stream.get_versions():
                if v.tag.lower() == bare.lower():
                    return SelectionSet.single(p_stream, v.ordinal, v)
            return SelectionSet.empty()

        m_alt_tag = re.match(r"^alt(\d+)_(.+)$", sel, re.IGNORECASE)
        if m_alt_tag:
            idx = int(m_alt_tag.group(1))
            bare = m_alt_tag.group(2)
            if idx < len(self.streams):
                s = self.streams[idx]
                for v in s.get_versions():
                    if v.tag.lower() == bare.lower():
                        return SelectionSet.single(s, v.ordinal, v)
            return SelectionSet.empty()

        for s in self.streams:
            for v in s.get_versions():
                if v.tag.lower() == sel_lower:
                    return SelectionSet.single(s, v.ordinal, v)
        return SelectionSet.empty()

    def resolve_version_ref(self, selector: str, unbundled_dir: Optional[Path] = None):
        """Compatibility wrapper for legacy single-version callers."""
        selection = self.resolve_selection(selector, unbundled_dir=unbundled_dir)
        item = selection.first
        return (item.stream, item.ordinal, item.version) if item else None

    def match_versions(self, pattern: str) -> List[Tuple[Stream, int, VersionRef]]:
        """Match versions across streams according to filter pattern / selector taxonomy."""
        pat = pattern.strip()
        pat_lower = pat.lower()
        matched: List[Tuple[Stream, int, VersionRef]] = []

        if pat_lower == "*_sealed":
            for s in self.streams:
                for v in s.get_versions():
                    if v.sealed:
                        matched.append((s, v.ordinal, v))
            return matched

        if pat_lower in ("sealed", "primary_sealed"):
            p_stream = self.streams[0]
            for v in p_stream.get_versions():
                if v.sealed:
                    matched.append((p_stream, v.ordinal, v))
            return matched

        if pat_lower == "alt_sealed":
            for s in self.streams[1:]:
                for v in s.get_versions():
                    if v.sealed:
                        matched.append((s, v.ordinal, v))
            return matched

        m_alt_sealed = re.match(r"^alt(\d+)_sealed$", pat_lower)
        if m_alt_sealed:
            idx = int(m_alt_sealed.group(1))
            if idx < len(self.streams):
                s = self.streams[idx]
                for v in s.get_versions():
                    if v.sealed:
                        matched.append((s, v.ordinal, v))
            return matched

        if pat_lower == "primary":
            p_stream = self.streams[0]
            for v in p_stream.get_versions():
                matched.append((p_stream, v.ordinal, v))
            return matched

        if pat_lower in ("alt", "alt*"):
            for s in self.streams[1:]:
                for v in s.get_versions():
                    matched.append((s, v.ordinal, v))
            return matched

        m_alt = re.match(r"^alt(\d+)$", pat_lower)
        if m_alt:
            idx = int(m_alt.group(1))
            if idx < len(self.streams):
                s = self.streams[idx]
                for v in s.get_versions():
                    matched.append((s, v.ordinal, v))
            return matched

        if pat_lower.startswith("primary_"):
            sub_pat = pat[8:]
            p_stream = self.streams[0]
            for v in p_stream.get_versions():
                if fnmatch.fnmatchcase(v.tag.lower(), sub_pat.lower()):
                    matched.append((p_stream, v.ordinal, v))
            return matched

        m_alt_pat = re.match(r"^alt(\d+)_(.+)$", pat, re.IGNORECASE)
        if m_alt_pat:
            idx = int(m_alt_pat.group(1))
            sub_pat = m_alt_pat.group(2)
            if idx < len(self.streams):
                s = self.streams[idx]
                for v in s.get_versions():
                    if fnmatch.fnmatchcase(v.tag.lower(), sub_pat.lower()):
                        matched.append((s, v.ordinal, v))
            return matched

        for s in self.streams:
            for v in s.get_versions():
                if fnmatch.fnmatchcase(v.tag.lower(), pat_lower) or fnmatch.fnmatchcase(
                    v.qualified_tag.lower(), pat_lower
                ):
                    matched.append((s, v.ordinal, v))
        return matched

    def include_source(
        self, src: str | Path, stream_filter: Optional[str] = None
    ) -> None:
        """Statically extract blztar from source (file, pyz, or directory) and append streams as altN_."""
        src_path = Path(src).resolve()
        b64_found = None

        if src_path.is_dir():
            target_unbundle = src_path / "dwimsy" / "meta" / "unbundle.py"
            if target_unbundle.is_file():
                data = target_unbundle.read_bytes()
                m = _BLZTAR_RE.search(data)
                if m:
                    b64_found = data[m.start("prefix") : m.end("suffix")]
        elif src_path.is_file():
            import zipfile

            if zipfile.is_zipfile(src_path):
                with zipfile.ZipFile(src_path, "r") as zf:
                    for name in ("__main__.py", "dwimsy/meta/unbundle.py"):
                        if name in zf.namelist():
                            data = zf.read(name)
                            m = _BLZTAR_RE.search(data)
                            if m:
                                b64_found = data[m.start("prefix") : m.end("suffix")]
                                break
            if b64_found is None:
                data = src_path.read_bytes()
                m = _BLZTAR_RE.search(data)
                if m:
                    b64_found = data[m.start("prefix") : m.end("suffix")]

        if b64_found is None:
            raise FileNotFoundError(
                f"Could not statically extract blztar payload from '{src}'"
            )

        other_space = VersionSpace.from_blztar(b64_found)
        src_display = str(src)
        for s in other_space.streams:
            if stream_filter == "primary" and s.index != 0:
                continue
            if stream_filter == "alt" and s.index == 0:
                continue
            if (
                stream_filter
                and stream_filter.startswith("alt")
                and stream_filter[3:].isdigit()
            ):
                if s.index != int(stream_filter[3:]):
                    continue
            new_s = s.copy()
            new_s.source = src_display
            new_s.mark_mutated()
            self.streams.append(new_s)
        self.renumber_streams()

    def restrict_to(self, pattern: str) -> None:
        """Allow-list filter: retain only versions/streams matching pattern."""
        matches = self.match_versions(pattern)
        if not matches:
            raise ValueError(f"No versions matched '--restrict-to={pattern}'")

        retained_by_stream: Dict[int, Set[int]] = {}
        for s, ord_idx, v in matches:
            retained_by_stream.setdefault(s.index, set()).add(ord_idx)

        new_streams: List[Stream] = []
        for s in self.streams:
            if s.index not in retained_by_stream:
                continue
            ord_set = retained_by_stream[s.index]
            if len(ord_set) == len(s.layers):
                new_streams.append(s.copy())
                continue

            filtered_layers = []
            open_count = s.get_open_dev_layer_count()
            surviving_ordinals = sorted(ord_set)
            base_ord = surviving_ordinals[0]
            base_mat = s.materialize_layer_state(base_ord)
            v_ref = next(
                v for st, o, v in matches if st.index == s.index and o == base_ord
            )
            base_lyr = Layer(
                base_mat,
                is_delta=False,
                version_tag=v_ref.tag,
                code_hash=s.layers[base_ord].code_hash,
            )
            filtered_layers.append(base_lyr)

            prev_mat = base_mat
            for ord_idx in surviving_ordinals[1:]:
                if ord_idx <= open_count:
                    curr_mat = s.materialize_layer_state(ord_idx)
                    delta_files = compute_tree_delta(prev_mat, curr_mat)
                    v_ref = next(
                        v
                        for st, o, v in matches
                        if st.index == s.index and o == ord_idx
                    )
                    filtered_layers.append(
                        Layer(
                            delta_files,
                            is_delta=True,
                            version_tag=v_ref.tag,
                            code_hash=s.layers[ord_idx].code_hash,
                        )
                    )
                    prev_mat = curr_mat
                else:
                    filtered_layers.append(s.layers[ord_idx])

            new_s = Stream(s.index, s.name, filtered_layers, source=s.source)
            new_s.mark_mutated()
            new_streams.append(new_s)

        if not new_streams:
            raise ValueError(f"No versions survived '--restrict-to={pattern}'")
        self.streams = new_streams
        self.renumber_streams()

    def prune(self, pattern: str) -> None:
        """Deny-list filter: discard versions/streams matching pattern."""
        matches = self.match_versions(pattern)
        if not matches:
            return

        pruned_by_stream: Dict[int, Set[int]] = {}
        for s, ord_idx, v in matches:
            pruned_by_stream.setdefault(s.index, set()).add(ord_idx)

        new_streams: List[Stream] = []
        for s in self.streams:
            if s.index not in pruned_by_stream:
                new_streams.append(s.copy())
                continue
            pruned_set = pruned_by_stream[s.index]
            surviving_ordinals = [
                i for i in range(len(s.layers)) if i not in pruned_set
            ]
            if not surviving_ordinals:
                continue

            open_count = s.get_open_dev_layer_count()
            filtered_layers = []
            base_ord = surviving_ordinals[0]
            base_mat = s.materialize_layer_state(base_ord)
            v_tag = s.layers[base_ord].version_tag
            base_lyr = Layer(
                base_mat,
                is_delta=False,
                version_tag=v_tag,
                code_hash=s.layers[base_ord].code_hash,
            )
            filtered_layers.append(base_lyr)

            prev_mat = base_mat
            for ord_idx in surviving_ordinals[1:]:
                if ord_idx <= open_count:
                    curr_mat = s.materialize_layer_state(ord_idx)
                    delta_files = compute_tree_delta(prev_mat, curr_mat)
                    filtered_layers.append(
                        Layer(
                            delta_files,
                            is_delta=True,
                            version_tag=s.layers[ord_idx].version_tag,
                            code_hash=s.layers[ord_idx].code_hash,
                        )
                    )
                    prev_mat = curr_mat
                else:
                    filtered_layers.append(s.layers[ord_idx])

            new_s = Stream(s.index, s.name, filtered_layers, source=s.source)
            new_s.mark_mutated()
            new_streams.append(new_s)

        if not new_streams:
            raise ValueError(f"Pruning '{pattern}' would leave empty version space")
        self.streams = new_streams
        self.renumber_streams()

    def branch_selection(self, selection: SelectionSet) -> None:
        """Branch from an immutable SelectionSet using the v8.6 single/multi rules."""
        if not selection:
            self.branch_alt(None)
            return
        if selection.is_multi:
            for item in selection.items:
                state = item.stream.materialize_layer_state(item.ordinal)
                shadow = Stream(
                    len(self.streams),
                    f"alt{len(self.streams)}",
                    [
                        Layer(
                            state,
                            is_delta=False,
                            version_tag=item.version.tag,
                            code_hash=None,
                        )
                    ],
                    source=item.stream.source,
                )
                self.streams.append(shadow)
            self.renumber_streams()
            return
        item = selection.first
        self.branch_alt(item.version.tag if item else None)

    def branch_alt(self, tag: Optional[str] = None) -> None:
        """Create a new primary stream branching from one selected version."""
        target_state: Dict[str, bytes] = {}
        target_tag = tag or "0.1.6.0-dev"

        if tag:
            selection = self.resolve_selection(tag)
            if not selection:
                raise ValueError(f"Cannot branch --alt from unknown version '{tag}'")
            if selection.is_multi:
                self.branch_selection(selection)
                return
            item = selection.first
            target_state = item.stream.materialize_layer_state(item.ordinal)
            target_tag = item.version.tag
        else:
            p_stream = self.streams[0]
            head = p_stream.get_head_version()
            if head:
                target_state = p_stream.materialize_layer_state(head.ordinal)
                target_tag = head.tag

        new_base = Layer(target_state, is_delta=False, version_tag=target_tag)
        new_primary = Stream(0, "primary", [new_base], source=".")
        shifted_streams = [new_primary]
        for s in self.streams:
            s_copy = s.copy()
            s_copy.mark_mutated()
            shifted_streams.append(s_copy)
        self.streams = shifted_streams
        self.renumber_streams()

    def splice(self, pattern: str) -> None:
        """Splice layers into historical sequence with dry-run safety hash verification."""
        matches = self.match_versions(pattern)
        if not matches:
            raise ValueError(f"No version matched splice pattern '{pattern}'")

        target_stream = self.streams[0]
        pre_splice_hashes = {
            v.tag: v.content_hash for v in target_stream.get_versions()
        }

        test_stream = target_stream.copy()
        test_stream.mark_mutated()

        for s, ord_idx, v in matches:
            donor_state = s.materialize_layer_state(ord_idx)
            donor_layer = Layer(
                donor_state,
                is_delta=False,
                version_tag=v.tag,
                code_hash=s.layers[ord_idx].code_hash,
            )

            open_count = test_stream.get_open_dev_layer_count()
            base_and_open = test_stream.layers[: open_count + 1]
            historical = test_stream.layers[open_count + 1 :]

            existing_idx = None
            for idx_h, lyr_h in enumerate(historical):
                if lyr_h.version_tag.lower() == v.tag.lower():
                    existing_idx = idx_h
                    break

            if existing_idx is not None:
                historical[existing_idx] = donor_layer
            elif base_and_open[0].version_tag.lower() == v.tag.lower():
                base_and_open[0] = donor_layer
            else:
                historical.append(donor_layer)

            historical.sort(key=lambda lyr: parse_semver(lyr.version_tag), reverse=True)
            test_stream.layers = base_and_open + historical

        post_splice_versions = test_stream.get_versions()
        for v in post_splice_versions:
            if v.tag in pre_splice_hashes:
                if v.content_hash != pre_splice_hashes[v.tag]:
                    raise RuntimeError(
                        f"splice aborted: would alter sealed history at '{v.tag}' in stream '{target_stream.name}'; "
                        f"this stream has diverged since the fork point and needs manual reconciliation, not an automatic splice."
                    )

        self.streams[0] = test_stream

    def run_pipeline(
        self,
        includes: Optional[List[str]] = None,
        restrict_to: Optional[str] = None,
        prune: Optional[str] = None,
        splice: Optional[str] = None,
        alt: Optional[Tuple[bool, Optional[str]]] = None,
    ) -> None:
        """Run the sequential transformation pipeline strictly left-to-right."""
        if includes:
            for inc in includes:
                self.include_source(inc)
        if restrict_to:
            self.restrict_to(restrict_to)
        if prune:
            self.prune(prune)
        if splice:
            self.splice(splice)
        if alt and alt[0]:
            self.branch_alt(alt[1])

    def composite_bundle_name(self, extension: str = ".py") -> str:
        """Generate multi-stream composite bundle name with uniform ,altN notation."""
        if not self.streams:
            return f"dwimsy_0.1.6.0-dev{extension}"

        parts: List[str] = []
        prev_ver = ""

        for idx, s in enumerate(self.streams):
            head = s.get_head_version()
            ver = head.tag if head else "0.1.6.0-dev"
            if idx == 0:
                parts.append(ver)
                prev_ver = ver
            else:
                if ver == prev_ver:
                    parts.append(f",alt{idx}")
                else:
                    parts.append(f",alt{idx}_{ver}")
                prev_ver = ver

        base_name = "dwimsy_" + "".join(parts)
        if not extension.startswith("."):
            extension = f".{extension}"
        return f"{base_name}{extension}"

    def get_layer_timestamp(
        self, layer: Layer, default_time: Optional[str] = None
    ) -> str:
        """Derive ISO 8601 UTC timestamp for a layer from TAR mtime or CHANGELOG.md."""
        import datetime

        if getattr(layer, "tar_bytes", None):
            try:
                import tarfile, io

                with tarfile.open(
                    fileobj=io.BytesIO(layer.tar_bytes), mode="r:"
                ) as tar:
                    mtimes = [
                        m.mtime for m in tar if m.mtime > 0 and m.mtime != 1700000000
                    ]
                    if mtimes:
                        return datetime.datetime.fromtimestamp(
                            max(mtimes), tz=datetime.timezone.utc
                        ).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pass
        c_data = layer.files.get("CHANGELOG.md")
        if c_data:
            try:
                c_text = c_data.decode("utf-8", errors="ignore")
                tag_escaped = re.escape(layer.version_tag or "")
                m = re.search(
                    rf"## \[{tag_escaped}\] - (\d{{4}}-\d{{2}}-\d{{2}})", c_text
                )
                if not m:
                    m = re.search(
                        r"## \[([^\]]+)\] - (\d{{4}}-\d{{2}}-\d{{2}})", c_text
                    )
                if m:
                    dt = m.group(1 if not m.group(2) else 2)
                    return f"{dt}T00:00:00Z"
            except Exception:
                pass
        return default_time or "2026-08-30T00:00:00Z"

    def format_list_versions(
        self,
        on_disk_root: Optional[Path] = None,
        selected: Optional[SelectionSet] = None,
        verbose: bool = False,
    ) -> str:
        """Format the output of --list-versions according to the complete specification."""
        all_refs = self.get_all_versions()

        if selected is None and on_disk_root is None:
            selected = self.resolve_selection("primary")

        hash_to_tags: Dict[str, List[str]] = {}
        for ref in all_refs:
            hash_to_tags.setdefault(ref.content_hash, []).append(ref.qualified_tag)

        lines = []

        unbundled_tag = None
        unbundled_hash = None
        if (
            on_disk_root is not None
            and (on_disk_root / "dwimsy" / "__init__.py").is_file()
        ):
            from dwimsy.meta import integrity

            unbundled_hash = integrity.canonical_code_hash(on_disk_root, baseline=False)
            unbundled_tag = integrity.version(root=on_disk_root)
            hash_to_tags.setdefault(unbundled_hash, []).append("unbundled")

        baseline_ref = self.resolve_version_ref("baseline")
        baseline_stream = baseline_ref[0] if baseline_ref is not None else None
        baseline_ordinal = baseline_ref[1] if baseline_ref is not None else None
        baseline_hash = (
            baseline_ref[2].content_hash if baseline_ref is not None else None
        )

        unbundled_is_baseline = bool(
            unbundled_hash is not None
            and baseline_hash is not None
            and unbundled_hash == baseline_hash
        )

        if (
            unbundled_tag is not None
            and unbundled_hash is not None
            and not unbundled_is_baseline
        ):
            peers = [
                t for t in hash_to_tags.get(unbundled_hash, []) if t != "unbundled"
            ]
            peer_toks = [f"={t}" for t in peers]
            ann_tokens = ["=unbundled"] + peer_toks
            ann_str = f"[{', '.join(ann_tokens)}]" if ann_tokens else ""
            unb_ts = "2026-08-30T00:00:00Z"
            if on_disk_root is not None:
                try:
                    files = integrity.source_files(on_disk_root)
                    max_mt = max(
                        (f.stat().st_mtime for f in files if f.exists()), default=0
                    )
                    if max_mt > 0:
                        import datetime

                        unb_ts = datetime.datetime.fromtimestamp(
                            max_mt, tz=datetime.timezone.utc
                        ).strftime("%Y-%m-%dT%H:%M:%SZ")
                except Exception:
                    pass
            unb_h_str = unbundled_hash if verbose else unbundled_hash[:12]
            lines.append(
                f"  [unbundled] {unbundled_tag:<20} {unb_ts}  {unb_h_str}  {ann_str:<34} [=unbundled: .]"
            )

        for s in self.streams:
            versions = sorted(
                s.get_versions(), key=lambda v: (parse_semver(v.tag), v.ordinal)
            )
            open_count = s.get_open_dev_layer_count()
            head_ver = (
                versions[open_count]
                if open_count < len(versions)
                else (versions[-1] if versions else None)
            )

            for v in versions:
                lyr = s.layers[v.ordinal]
                kw_tokens = []
                if s.index == 0:
                    if baseline_stream is s and v.ordinal == baseline_ordinal:
                        kw_tokens.append("=baseline")
                        if head_ver and v.ordinal == head_ver.ordinal:
                            kw_tokens.append("=primary")
                            if unbundled_is_baseline:
                                kw_tokens.append("=unbundled")
                        elif unbundled_is_baseline:
                            kw_tokens.append("=unbundled")
                    elif head_ver and v.ordinal == head_ver.ordinal:
                        kw_tokens.append("=primary")
                    else:
                        kw_tokens.append("=~primary")
                    if v.sealed:
                        if v.ordinal == versions[-1].ordinal or (
                            head_ver and v.ordinal == head_ver.ordinal
                        ):
                            kw_tokens.append("=sealed")
                            kw_tokens.append("=primary_sealed")
                        else:
                            kw_tokens.append("=~sealed")
                            kw_tokens.append("=~primary_sealed")
                else:
                    if head_ver and v.ordinal == head_ver.ordinal:
                        if s.index == 1:
                            kw_tokens.append("=alt")
                        kw_tokens.append(f"={s.name}")
                    else:
                        kw_tokens.append(f"=~{s.name}")
                    if v.sealed:
                        kw_tokens.append(f"=~{s.name}_sealed")
                        kw_tokens.append("=~alt_sealed")

                if selected is not None:
                    for item in selected:
                        if item.stream is s:
                            if v.ordinal == item.ordinal:
                                kw_tokens.append("=selected")
                            elif parse_semver(v.tag) < parse_semver(item.version.tag):
                                kw_tokens.append("=~selected")

                peer_list = [
                    t
                    for t in hash_to_tags.get(v.content_hash, [])
                    if t != v.qualified_tag and t != "unbundled"
                ]
                if unbundled_hash == v.content_hash and not unbundled_is_baseline:
                    peer_list.append("unbundled")
                peer_toks = [f"={t}" for t in peer_list]

                all_toks = kw_tokens + peer_toks
                ann_str = f"[{', '.join(all_toks)}]" if all_toks else ""

                prefix = "[primary]" if s.index == 0 else f"{s.name}_"
                display_tag = (
                    f"{prefix} {v.tag}" if s.index == 0 else f"{s.name}_{v.tag}"
                )

                role_status = (
                    "=" if (head_ver and v.ordinal == head_ver.ordinal) else "=~"
                )
                role_name = "primary" if s.index == 0 else s.name
                prov_str = f"[{role_status}{role_name}: {v.source}]"

                ts = self.get_layer_timestamp(lyr)
                h_str = v.content_hash if verbose else v.content_hash[:12]
                lines.append(
                    f"  {display_tag:<24} {ts}  {h_str}  {ann_str:<34} {prov_str}"
                )

        return "\n".join(lines)
