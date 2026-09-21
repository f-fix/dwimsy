"""dwimsy.tests.fixtures - Central test fixture data registry and discovery pool."""

from __future__ import annotations

import hashlib
import os
import sys
import unittest
import zlib
import json
import re
import tempfile
import base64
import io
import lzma
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union


# FIXTURE-CORE-BEGIN: fixture registry

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union
from pathlib import Path


@dataclass(frozen=True)
class FixtureSpec:
    """Specification of a known test fixture artifact."""

    id: str
    filename: str
    size: int
    crc32: str
    md5: str
    sha1: str
    title: str = ""
    timestamp: Optional[str] = None
    unique_filename: str = ""

    @property
    def sha1_hex(self) -> str:
        return self.sha1.lower()

    @property
    def md5_hex(self) -> str:
        return self.md5.lower()

    @property
    def crc32_hex(self) -> str:
        return self.crc32.lower()

    @property
    def display_title(self) -> str:
        return self.title if self.title else self.filename


_RAW_FIXTURE_SPECS: List[Tuple[str, str, int, str, str, str, str, Optional[str]]] = [
    # id, filename, size, crc32, md5, sha1, title, timestamp
    (
        "pc88_door_door_1200_cmt",
        "input01.cmt",
        26830,
        "5a5b9ac6",
        "cf279da2201d40159f6b11551e9ad672",
        "636a0c6e7dac28cf27a4ac0b7a98cbc1bf272642",
        "Door Door (Side A) (1983-02) (Enix) [MON-R-GE000]",
        "2026-08-15T16:41:31Z",
    ),
    (
        "pc88_door_door_1200_t88",
        "input01.t88",
        27200,
        "fc45f3e0",
        "fe6238dba1a85b4c7d5683dcf78bca02",
        "8e03c036b3232708f8f04a8346ea50c1b24fb973",
        "Door Door (Side A) (1983-02) (Enix) [MON-R-GE000]",
        "2026-08-15T14:57:21Z",
    ),
    (
        "input02_cmt",
        "input02.cmt",
        26714,
        "9f5abc75",
        "21d67a1e6ce5d2ca3244e2d07ffc04b9",
        "2380232d569b3438778e6fd117bac9e175e9568f",
        "input02.cmt",
        "2026-08-15T14:57:15Z",
    ),
    (
        "input03_cmt",
        "input03.cmt",
        26830,
        "ee199aab",
        "d077097338059bdc999097d230f1005d",
        "e454b02ce745b9cae4f51b5da02d5513908f977f",
        "input03.cmt",
        "2026-08-15T15:43:50Z",
    ),
    (
        "input03_t88",
        "input03.t88",
        27200,
        "4c8cd861",
        "879365c0d0d9f883e7cb01cfc5a90c3a",
        "cde9f56add518559ec547022fc32668eb2e26bb4",
        "input03.t88",
        "2026-08-15T15:43:41Z",
    ),
    (
        "input04_cmt",
        "input04.cmt",
        34201,
        "bdd8d0c1",
        "4a9d1813064eab926fc97e625a0eba4a",
        "9acaac6e73b3430417f4cdb820391348f90427e4",
        "input04.cmt",
        "2026-08-15T15:46:47Z",
    ),
    (
        "input04_t88",
        "input04.t88",
        35063,
        "282b989c",
        "57d862b1d9b4c08e97128870c427e433",
        "d9524717754afdda27e388595950c21ed46a565a",
        "input04.t88",
        "2026-08-15T15:46:00Z",
    ),
    (
        "pc88_digdug_600_cmt",
        "input05.cmt",
        47766,
        "d7386780",
        "b9408c4f78eb00f2b376f564b1fb80a6",
        "34ed0b17ebc5deb93cb5d20349d18ab31e18c0f6",
        "Dig Dug (Dempa Micomsoft)",
        "2026-08-15T15:52:20Z",
    ),
    (
        "pc88_digdug_600_t88",
        "input05.t88",
        48080,
        "1d85cb72",
        "5a59fce43a349a1cca8ae9508d2610c5",
        "e6fa14caa849c712a0911afb323a68f18c127a36",
        "Dig Dug (Dempa Micomsoft)",
        "2026-08-15T15:52:13Z",
    ),
    (
        "input06_cmt",
        "input06.cmt",
        46306,
        "b3a78310",
        "4b9b9f048b1362d10f46ea6f1e4f647a",
        "8e9968e08ab413e3ff3aadd2f22ba5ba48e237ea",
        "input06.cmt",
        "2026-08-15T15:53:24Z",
    ),
    (
        "input06_t88",
        "input06.t88",
        46560,
        "9cd6149d",
        "5c7fb2865059276ab1a5dadd3e4bd591",
        "2204f949888a49f9568fe1aa1e32665b59d5e965",
        "input06.t88",
        "2026-08-15T15:53:31Z",
    ),
    (
        "input07_cmt",
        "input07.cmt",
        15010,
        "ded0685e",
        "ea93048cb5fe0cf5cc7e390888b55b1e",
        "e9abeb712f01f24b4db41edd957e75e2d798a17a",
        "input07.cmt",
        "2026-08-15T15:54:28Z",
    ),
    (
        "input07_t88",
        "input07.t88",
        15431,
        "0b1aa36c",
        "24f4f130e0ceda29f5a7f9dbe0cdf07d",
        "d11f53118ae00ba09ca41bdc75ad8cfd16a3c89c",
        "input07.t88",
        "2026-08-15T15:54:36Z",
    ),
    (
        "input08_cmt",
        "input08.cmt",
        24228,
        "3e746ae2",
        "d9b52c5d97a22394542a241dfab6b430",
        "d3c40d1516248c6a7438d0ad0eb6c40a67d40fa0",
        "input08.cmt",
        "2026-08-15T16:42:45Z",
    ),
    (
        "input08_t88",
        "input08.t88",
        24390,
        "e61d82a4",
        "a97861b703ace2d7a913d660f6f3aa95",
        "14f9d6c1fd468aa8d7ef114d111d7ea2f12e20ad",
        "input08.t88",
        "2026-08-15T16:42:53Z",
    ),
    (
        "input09_cmt",
        "input09.cmt",
        181375,
        "c7e0a435",
        "573e289886ed3354fc680fded199751c",
        "0766b79c95acb1dd965f6eeed968efb7b87106ca",
        "input09.cmt",
        "2026-08-15T16:52:22Z",
    ),
    (
        "input09_t88",
        "input09.t88",
        184229,
        "a8a49261",
        "65d33a13dd120d08037c361593697684",
        "5242158da1c9f4c448b7a585c33f8f4a1a654f9a",
        "input09.t88",
        "2026-08-15T16:44:32Z",
    ),
    (
        "input10_cmt",
        "input10.cmt",
        182201,
        "dddc8fdb",
        "eed466358a2bedd53fe4094929a2f42e",
        "0814df0ecadfc0dde2352970f807d81f96bb3da9",
        "input10.cmt",
        "2026-08-15T16:52:22Z",
    ),
    (
        "input10_t88",
        "input10.t88",
        185067,
        "7ef16909",
        "dec20cdfc187afaf54a662ba3d3aaeff",
        "6fbced2176febd4889809ba43d3851e080d06a74",
        "input10.t88",
        "2026-08-15T16:44:32Z",
    ),
    (
        "input11_cmt",
        "input11.cmt",
        108413,
        "4d80e4e0",
        "50c7dc65b63017295254e8f1f84ff644",
        "3ee4c5a4818be522b9bf2589890b291ee60345bb",
        "input11.cmt",
        "2026-08-15T16:52:22Z",
    ),
    (
        "input11_t88",
        "input11.t88",
        110135,
        "0fbb75b1",
        "31021a812407c95d56339b2aa0902e15",
        "51c14cb515e270dd7a36c37ad984062ca605fc78",
        "input11.t88",
        "2026-08-15T16:44:32Z",
    ),
    (
        "input12_cmt",
        "input12.cmt",
        73788,
        "a9b83ac6",
        "b03140d678aa4d021d2505010b8d55f2",
        "9f2ccfa50ae2423676f5768ce3edcb6e69311ddd",
        "input12.cmt",
        "2026-08-15T16:52:22Z",
    ),
    (
        "input12_t88",
        "input12.t88",
        74990,
        "9d23839f",
        "2c4353cb092bf6be335c86d093111adf",
        "652a22e08c981686732ee0f7afa0efef2c5ad7b1",
        "input12.t88",
        "2026-08-15T16:44:32Z",
    ),
    (
        "input13_cmt",
        "input13.cmt",
        25271,
        "275c56e6",
        "a1ba973d862560f4d4f64138fbcc10e2",
        "1b016b7c25854882c96d20f5b7efb6b6b19e47f2",
        "input13.cmt",
        "2026-08-15T16:52:23Z",
    ),
    (
        "input13_t88",
        "input13.t88",
        25849,
        "ff17d0f0",
        "3de5bc6d99584c7c11c972e6ed845a49",
        "24ed52c90c448f27397e51071de4efb1c464a81d",
        "input13.t88",
        "2026-08-15T16:44:32Z",
    ),
    (
        "input14_cmt",
        "input14.cmt",
        41180,
        "f4906029",
        "a970317f7791dbcb86a3afef2abfe81e",
        "8f5e2c98dc5ae9ab6e7ff5e6310ad481014d04b0",
        "input14.cmt",
        "2026-08-15T16:52:23Z",
    ),
    (
        "input14_t88",
        "input14.t88",
        41758,
        "999900b2",
        "7f736d0805524495cb2e8bd07b93e581",
        "14fa468f21e807c9da916c61839a216c4f7fcfb8",
        "input14.t88",
        "2026-08-15T16:44:32Z",
    ),
    (
        "input15_cmt",
        "input15.cmt",
        37076,
        "46962997",
        "be5140064637891d40e222c52ff69513",
        "13a6bf91588996971899c45d78ee2b59df4e7359",
        "input15.cmt",
        "2026-08-15T16:52:23Z",
    ),
    (
        "input15_t88",
        "input15.t88",
        37654,
        "194ebb53",
        "22b07a29a0e71db4c1cb9a9e8948de6c",
        "64aafb47f5aed3da429d61c775a0997ce8503836",
        "input15.t88",
        "2026-08-15T16:44:32Z",
    ),
    (
        "input16_cmt",
        "input16.cmt",
        4886,
        "b2eb89e3",
        "4c55971a323bcd19d9d476e2aa6cd8a3",
        "70eeba507de79e5d29714f8e5014358bb85d29e8",
        "input16.cmt",
        "2026-08-15T16:52:24Z",
    ),
    (
        "input16_t88",
        "input16.t88",
        5048,
        "80a95445",
        "957d60aebf427440bcd6a5de91f395df",
        "7d3a896201d05671bab4d87ccef2dc33d92af653",
        "input16.t88",
        "2026-08-15T16:44:32Z",
    ),
    (
        "input17_cmt",
        "input17.cmt",
        9983,
        "e85a6656",
        "c8523252c77eb22aff64131181e19cc1",
        "6a5b81b8568c50bb7e4c43bdeb51fc2a03219b2c",
        "input17.cmt",
        "2026-08-15T16:52:24Z",
    ),
    (
        "input17_t88",
        "input17.t88",
        10457,
        "29482453",
        "fdf940a963613ef77e0d7b0e89b7088c",
        "29141be473d7e8d8e21c642b2cb47889c5b7e05a",
        "input17.t88",
        "2026-08-15T16:44:32Z",
    ),
    (
        "input18_cmt",
        "input18.cmt",
        12593,
        "c647a258",
        "43937d48f62c111d9102b0bfa294fcdf",
        "d8b7bd1de735d93ec704c2035967839bde4c6f50",
        "input18.cmt",
        "2026-08-15T16:52:24Z",
    ),
    (
        "input18_t88",
        "input18.t88",
        12755,
        "dbbc4b47",
        "0dbd7c46b8f6eb92d901cd63353f8daa",
        "d7654f37668294d20d2c669b5b679852a1fa555d",
        "input18.t88",
        "2026-08-15T16:44:32Z",
    ),
    (
        "input19_cmt",
        "input19.cmt",
        6059,
        "385657a4",
        "905de83ec2b7502b75fb7a470606aaf0",
        "959a4860afd531f88dfb70b176aa69623d2788b7",
        "input19.cmt",
        "2026-08-15T16:52:25Z",
    ),
    (
        "input19_t88",
        "input19.t88",
        6221,
        "16b20d73",
        "929e4738c83ce98899167d03fb184607",
        "947ef5b9455f2f36cacb0506725ff407cccdd6a1",
        "input19.t88",
        "2026-08-15T16:44:32Z",
    ),
    (
        "input20_cmt",
        "input20.cmt",
        45153,
        "96214463",
        "fb181a90267e2f9592639eace2d716a0",
        "df15156a2a719c922a8e502a8331b50440137bea",
        "input20.cmt",
        "2026-08-15T16:52:25Z",
    ),
    (
        "input20_t88",
        "input20.t88",
        45731,
        "2d855766",
        "5991b14cc6b79641d4e62ce3fffaff3e",
        "cd1c8aae89d5d674a88f61edd6f13985f7f85896",
        "input20.t88",
        "2026-08-15T16:44:32Z",
    ),
    (
        "pc88_door_door_1200_wav",
        "snippet.wav",
        414012,
        "4e1a9921",
        "50e693b01795caf1beb3e026e92f53f8",
        "e495dd758f80cc73c62ecc907d02a3fe56f674e0",
        "Door Door (Enix)",
        "2026-08-20T21:12:51Z",
    ),
    (
        "pc88_digdug_600_wav",
        "snippet2.wav",
        659500,
        "e50d589d",
        "9359473f4869b63f29aeefd7ca9c8dc4",
        "97d37c0f2842933c8a906accba1c03599f41c8f8",
        "Dig Dug (Dempa Micomsoft)",
        "2026-08-20T23:03:23Z",
    ),
]


def _compute_unique_filenames(specs: Sequence[FixtureSpec]) -> Dict[str, str]:
    groups: Dict[str, List[FixtureSpec]] = {}
    for s in specs:
        groups.setdefault(s.filename, []).append(s)
    res = {}
    for fname, group in groups.items():
        if len(group) == 1:
            res[group[0].sha1.lower()] = fname
        else:

            def sort_key(item: FixtureSpec):
                ts_key = (0, item.timestamp) if item.timestamp is not None else (1, "")
                return (ts_key, item.sha1.lower())

            sorted_group = sorted(group, key=sort_key)
            winner = sorted_group[0]
            res[winner.sha1.lower()] = fname
            p = Path(fname)
            stem = p.stem
            suffix = p.suffix
            for other in sorted_group[1:]:
                prefix_len = 8
                cand = f"{stem}.{other.sha1[:prefix_len]}{suffix}"
                while any(
                    s != other and cand == f"{stem}.{s.sha1[:prefix_len]}{suffix}"
                    for s in sorted_group
                ):
                    prefix_len += 1
                res[other.sha1.lower()] = f"{stem}.{other.sha1[:prefix_len]}{suffix}"
    return res


_initial_specs = [
    FixtureSpec(
        id=_fid,
        filename=_fname,
        size=_sz,
        crc32=_crc.lower(),
        md5=_md5.lower(),
        sha1=_sha.lower(),
        title=_title,
        timestamp=_ts,
        unique_filename=_fname,
    )
    for _fid, _fname, _sz, _crc, _md5, _sha, _title, _ts in _RAW_FIXTURE_SPECS
]
_unique_map = _compute_unique_filenames(_initial_specs)

FIXTURE_REGISTRY: Dict[str, FixtureSpec] = {}
FIXTURES_BY_FILENAME: Dict[str, FixtureSpec] = {}
FIXTURES_BY_SHA1: Dict[str, FixtureSpec] = {}

for _s in _initial_specs:
    _u_name = _unique_map.get(_s.sha1.lower(), _s.filename)
    _spec = FixtureSpec(
        id=_s.id,
        filename=_s.filename,
        size=_s.size,
        crc32=_s.crc32,
        md5=_s.md5,
        sha1=_s.sha1,
        title=_s.title,
        timestamp=_s.timestamp,
        unique_filename=_u_name,
    )
    FIXTURE_REGISTRY[_spec.id] = _spec
    FIXTURES_BY_FILENAME[_spec.unique_filename] = _spec
    FIXTURES_BY_SHA1[_spec.sha1.lower()] = _spec


def get_fixture_spec(key: str) -> Optional[FixtureSpec]:
    """Look up a fixture specification by ID, filename, unique_filename, or SHA-1 hex digest."""
    if key in FIXTURE_REGISTRY:
        return FIXTURE_REGISTRY[key]
    if key in FIXTURES_BY_FILENAME:
        return FIXTURES_BY_FILENAME[key]
    key_lower = key.lower()
    if key_lower in FIXTURES_BY_SHA1:
        return FIXTURES_BY_SHA1[key_lower]
    key_fold = key.casefold()
    for s in FIXTURE_REGISTRY.values():
        if (
            s.id.casefold() == key_fold
            or s.filename.casefold() == key_fold
            or s.unique_filename.casefold() == key_fold
        ):
            return s
    return None


# FIXTURE-CORE-END


def _calc_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


class FixturePool:
    """Content-addressed fixture discovery pool with lazy fixture-bundle materialization."""

    def __init__(self, search_dirs=None, registry=None):
        self._registry = registry if registry is not None else FIXTURE_REGISTRY
        self._explicit_dirs = [Path(d) for d in search_dirs] if search_dirs else []
        self._by_sha1 = {}
        self._by_filename = {}
        self._bundle_records = {}
        self._bundle_paths = {}
        self._materialized = {}
        self._scanned_dirs = []
        self.rescan()

    def rescan(self):
        candidate_dirs = []
        for d in self._explicit_dirs:
            if d.exists() and d not in candidate_dirs:
                candidate_dirs.append(d)
        env_dir = os.environ.get("DWIMSY_TEST_FIXTURES")
        if env_dir:
            for raw in env_dir.split(os.pathsep):
                p = Path(raw)
                if p.exists() and p not in candidate_dirs:
                    candidate_dirs.append(p)
        test_repo_root = os.environ.get("DWIMSY_TEST_REPO_ROOT")
        if test_repo_root:
            roots = [Path(test_repo_root).resolve()]
        else:
            pkg_root = Path(__file__).resolve().parent.parent.parent
            roots = [pkg_root, Path.cwd(), Path.home() / ".local" / "share" / "dwimsy"]
        for r in roots:
            for sub in ("tests/fixtures", "fixtures"):
                p = r / sub
                if p.exists() and p not in candidate_dirs:
                    candidate_dirs.append(p)
        self._scanned_dirs = candidate_dirs
        self._by_sha1.clear()
        self._by_filename.clear()
        self._bundle_records.clear()
        self._bundle_paths.clear()
        for c_dir in candidate_dirs:
            paths = (
                [c_dir]
                if c_dir.is_file()
                else [Path(root) / f for root, _ds, fs in os.walk(c_dir) for f in fs]
            )
            for fpath in paths:
                try:
                    if fpath.suffix.lower() in (".py", ".pyz"):
                        try:
                            data = fpath.read_bytes()
                            if fpath.suffix.lower() == ".pyz":
                                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                                    data = zf.read("__main__.py")
                            m = re.search(
                                rb'_FIXTURE_BLZTAR\s*=\s*"""\n([\s\S]*?)\n"""', data
                            )
                            if m:
                                raw = base64.b64decode(b"".join(m.group(1).split()))
                                with tarfile.open(
                                    fileobj=io.BytesIO(lzma.decompress(raw)), mode="r:"
                                ) as tar:
                                    for member in tar.getmembers():
                                        if not member.isfile():
                                            continue
                                        m_name = member.name.lstrip("./")
                                        if re.fullmatch(r"[0-9a-f]{40}", m_name, re.I):
                                            sha1_val = m_name.lower()
                                            spec = self._registry.get(
                                                sha1_val
                                            ) or FIXTURES_BY_SHA1.get(sha1_val)
                                            if spec is None:
                                                spec = FixtureSpec(
                                                    id=sha1_val[:12],
                                                    filename=sha1_val,
                                                    size=member.size,
                                                    crc32="",
                                                    md5="",
                                                    sha1=sha1_val,
                                                    title="",
                                                    timestamp=None,
                                                    unique_filename=sha1_val,
                                                )
                                            self._bundle_records[sha1_val] = (
                                                fpath,
                                                {
                                                    "name": spec.unique_filename,
                                                    "sha1": sha1_val,
                                                    "member": m_name,
                                                    "spec": spec,
                                                },
                                            )
                                            self._by_filename.setdefault(
                                                spec.unique_filename.casefold(),
                                                sha1_val,
                                            )
                                            self._by_filename.setdefault(
                                                spec.filename.casefold(), sha1_val
                                            )
                                continue
                        except Exception:
                            pass
                    s1 = _calc_sha1(fpath)
                    self._by_sha1.setdefault(s1, fpath)
                    self._by_filename.setdefault(fpath.name.lower(), fpath)
                except OSError:
                    pass

    def _materialize_bundle(self, sha1):
        """Materialize bundle member using unique_filename and handling move-aside collisions."""
        sha1_clean = sha1.lower()
        item = self._bundle_records.get(sha1_clean)
        if item is None:
            return None
        path, record = item
        spec = record.get("spec") or get_fixture_spec(sha1_clean)
        unique_name = getattr(spec, "unique_filename", None) or getattr(
            spec, "filename", sha1_clean
        )
        dest = Path(tempfile.gettempdir()) / "dwimsy-fixtures" / unique_name

        from dwimsy.meta.unbundle import _timestamp_epoch

        exp_epoch = _timestamp_epoch(getattr(spec, "timestamp", None)) if spec else None

        if (
            dest.is_file()
            and hashlib.sha1(dest.read_bytes()).hexdigest().lower() == sha1_clean
        ):
            if exp_epoch is not None:
                try:
                    os.utime(dest, (exp_epoch, exp_epoch))
                except OSError:
                    pass
            self._materialized[sha1_clean] = dest
            self._by_sha1[sha1_clean] = dest
            return dest

        data = path.read_bytes()
        if path.suffix.lower() == ".pyz":
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                data = zf.read("__main__.py")
        m = re.search(rb'_FIXTURE_BLZTAR\s*=\s*"""\n([\s\S]*?)\n"""', data)
        if not m:
            return None
        raw = base64.b64decode(b"".join(m.group(1).split()))
        with tarfile.open(fileobj=io.BytesIO(lzma.decompress(raw)), mode="r:") as tar:
            m_name = record.get("member", sha1_clean)
            f = tar.extractfile(m_name)
            if f is None:
                return None
            content = f.read()
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() or dest.is_symlink():
                existing = dest.read_bytes()
                if hashlib.sha1(existing).hexdigest().lower() != sha1_clean:
                    ex_sha = hashlib.sha1(existing).hexdigest().lower()
                    aside = dest.with_name(ex_sha)
                    if aside.exists() or aside.is_symlink():
                        aside.unlink()
                    dest.rename(aside)
            dest.write_bytes(content)
            if exp_epoch is not None:
                try:
                    os.utime(dest, (exp_epoch, exp_epoch))
                except OSError:
                    pass
        self._materialized[sha1_clean] = dest
        self._by_sha1[sha1_clean] = dest
        return dest

    def get(self, key):
        spec = get_fixture_spec(key)
        if spec is not None:
            s1 = spec.sha1.lower()
            if s1 in self._by_sha1:
                return self._by_sha1[s1]
            if s1 in self._bundle_records:
                return self._materialize_bundle(s1)
            cand = self._by_filename.get(
                spec.unique_filename.lower()
            ) or self._by_filename.get(spec.filename.lower())
            if isinstance(cand, str) and cand in self._bundle_records:
                return self._materialize_bundle(cand)
            if cand:
                try:
                    if _calc_sha1(cand) == s1:
                        return cand
                except OSError:
                    pass
        elif isinstance(key, str):
            k = key.casefold()
            if k in self._by_sha1:
                return self._by_sha1[k]
            if k in self._bundle_records:
                return self._materialize_bundle(k)
            cand = self._by_filename.get(k)
            if isinstance(cand, str) and cand in self._bundle_records:
                return self._materialize_bundle(cand)
            if cand:
                return cand
        return None

    def require(self, key):
        path = self.get(key)
        if path is None:
            raise unittest.SkipTest(self.skip_reason(key))
        return path

    def skip_reason(self, key):
        spec = get_fixture_spec(key)
        if spec is not None:
            return f'Fixture "{spec.display_title}" (SHA1: {spec.sha1}) not found in fixture pool.'
        return f'Fixture "{key}" not found in fixture pool.'


_GLOBAL_POOL: Optional[FixturePool] = None


def get_fixture_pool(
    search_dirs: Optional[Sequence[Union[str, Path]]] = None,
) -> FixturePool:
    """Get or create the global singleton FixturePool instance."""
    global _GLOBAL_POOL
    if _GLOBAL_POOL is None or search_dirs:
        _GLOBAL_POOL = FixturePool(search_dirs=search_dirs)
    return _GLOBAL_POOL


def find_fixture_path(
    key: Union[str, FixtureSpec],
    subdirs: Tuple[str, ...] = ("set1", "set2", "pc88", ""),
) -> Optional[Path]:
    """Locate a sample fixture file via the global FixturePool."""
    return get_fixture_pool().get(key)
