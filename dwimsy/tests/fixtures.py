"""dwimsy.tests.fixtures — central test fixture data registry and discovery pool."""

from __future__ import annotations

import hashlib
import os
import sys
import unittest
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union


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


_RAW_FIXTURE_SPECS: List[Tuple[str, str, int, str, str, str, str]] = [
    # id, filename, size, crc32, md5, sha1, title
    ("pc88_door_door_1200_cmt", "input01.cmt", 26830, "5a5b9ac6", "cf279da2201d40159f6b11551e9ad672", "636a0c6e7dac28cf27a4ac0b7a98cbc1bf272642", "Door Door (Side A) (1983-02) (Enix) [MON-R-GE000]"),
    ("pc88_door_door_1200_t88", "input01.t88", 27200, "fc45f3e0", "fe6238dba1a85b4c7d5683dcf78bca02", "8e03c036b3232708f8f04a8346ea50c1b24fb973", "Door Door (Side A) (1983-02) (Enix) [MON-R-GE000]"),
    ("input02_cmt", "input02.cmt", 26714, "9f5abc75", "21d67a1e6ce5d2ca3244e2d07ffc04b9", "2380232d569b3438778e6fd117bac9e175e9568f", "input02.cmt"),
    ("input03_cmt", "input03.cmt", 26830, "ee199aab", "d077097338059bdc999097d230f1005d", "e454b02ce745b9cae4f51b5da02d5513908f977f", "input03.cmt"),
    ("input03_t88", "input03.t88", 27200, "4c8cd861", "879365c0d0d9f883e7cb01cfc5a90c3a", "cde9f56add518559ec547022fc32668eb2e26bb4", "input03.t88"),
    ("input04_cmt", "input04.cmt", 34201, "bdd8d0c1", "4a9d1813064eab926fc97e625a0eba4a", "9acaac6e73b3430417f4cdb820391348f90427e4", "input04.cmt"),
    ("input04_t88", "input04.t88", 35063, "282b989c", "57d862b1d9b4c08e97128870c427e433", "d9524717754afdda27e388595950c21ed46a565a", "input04.t88"),
    ("pc88_digdug_600_cmt", "input05.cmt", 47766, "d7386780", "b9408c4f78eb00f2b376f564b1fb80a6", "34ed0b17ebc5deb93cb5d20349d18ab31e18c0f6", "Dig Dug (Dempa Micomsoft)"),
    ("pc88_digdug_600_t88", "input05.t88", 48080, "1d85cb72", "5a59fce43a349a1cca8ae9508d2610c5", "e6fa14caa849c712a0911afb323a68f18c127a36", "Dig Dug (Dempa Micomsoft)"),
    ("input06_cmt", "input06.cmt", 46306, "b3a78310", "4b9b9f048b1362d10f46ea6f1e4f647a", "8e9968e08ab413e3ff3aadd2f22ba5ba48e237ea", "input06.cmt"),
    ("input06_t88", "input06.t88", 46560, "9cd6149d", "5c7fb2865059276ab1a5dadd3e4bd591", "2204f949888a49f9568fe1aa1e32665b59d5e965", "input06.t88"),
    ("input07_cmt", "input07.cmt", 15010, "ded0685e", "ea93048cb5fe0cf5cc7e390888b55b1e", "e9abeb712f01f24b4db41edd957e75e2d798a17a", "input07.cmt"),
    ("input07_t88", "input07.t88", 15431, "0b1aa36c", "24f4f130e0ceda29f5a7f9dbe0cdf07d", "d11f53118ae00ba09ca41bdc75ad8cfd16a3c89c", "input07.t88"),
    ("input08_cmt", "input08.cmt", 24228, "3e746ae2", "d9b52c5d97a22394542a241dfab6b430", "d3c40d1516248c6a7438d0ad0eb6c40a67d40fa0", "input08.cmt"),
    ("input08_t88", "input08.t88", 24390, "e61d82a4", "a97861b703ace2d7a913d660f6f3aa95", "14f9d6c1fd468aa8d7ef114d111d7ea2f12e20ad", "input08.t88"),
    ("input09_cmt", "input09.cmt", 181375, "c7e0a435", "573e289886ed3354fc680fded199751c", "0766b79c95acb1dd965f6eeed968efb7b87106ca", "input09.cmt"),
    ("input09_t88", "input09.t88", 184229, "a8a49261", "65d33a13dd120d08037c361593697684", "5242158da1c9f4c448b7a585c33f8f4a1a654f9a", "input09.t88"),
    ("input10_cmt", "input10.cmt", 182201, "dddc8fdb", "eed466358a2bedd53fe4094929a2f42e", "0814df0ecadfc0dde2352970f807d81f96bb3da9", "input10.cmt"),
    ("input10_t88", "input10.t88", 185067, "7ef16909", "dec20cdfc187afaf54a662ba3d3aaeff", "6fbced2176febd4889809ba43d3851e080d06a74", "input10.t88"),
    ("input11_cmt", "input11.cmt", 108413, "4d80e4e0", "50c7dc65b63017295254e8f1f84ff644", "3ee4c5a4818be522b9bf2589890b291ee60345bb", "input11.cmt"),
    ("input11_t88", "input11.t88", 110135, "0fbb75b1", "31021a812407c95d56339b2aa0902e15", "51c14cb515e270dd7a36c37ad984062ca605fc78", "input11.t88"),
    ("input12_cmt", "input12.cmt", 73788, "a9b83ac6", "b03140d678aa4d021d2505010b8d55f2", "9f2ccfa50ae2423676f5768ce3edcb6e69311ddd", "input12.cmt"),
    ("input12_t88", "input12.t88", 74990, "9d23839f", "2c4353cb092bf6be335c86d093111adf", "652a22e08c981686732ee0f7afa0efef2c5ad7b1", "input12.t88"),
    ("input13_cmt", "input13.cmt", 25271, "275c56e6", "a1ba973d862560f4d4f64138fbcc10e2", "1b016b7c25854882c96d20f5b7efb6b6b19e47f2", "input13.cmt"),
    ("input13_t88", "input13.t88", 25849, "ff17d0f0", "3de5bc6d99584c7c11c972e6ed845a49", "24ed52c90c448f27397e51071de4efb1c464a81d", "input13.t88"),
    ("input14_cmt", "input14.cmt", 41180, "f4906029", "a970317f7791dbcb86a3afef2abfe81e", "8f5e2c98dc5ae9ab6e7ff5e6310ad481014d04b0", "input14.cmt"),
    ("input14_t88", "input14.t88", 41758, "999900b2", "7f736d0805524495cb2e8bd07b93e581", "14fa468f21e807c9da916c61839a216c4f7fcfb8", "input14.t88"),
    ("input15_cmt", "input15.cmt", 37076, "46962997", "be5140064637891d40e222c52ff69513", "13a6bf91588996971899c45d78ee2b59df4e7359", "input15.cmt"),
    ("input15_t88", "input15.t88", 37654, "194ebb53", "22b07a29a0e71db4c1cb9a9e8948de6c", "64aafb47f5aed3da429d61c775a0997ce8503836", "input15.t88"),
    ("input16_cmt", "input16.cmt", 4886, "b2eb89e3", "4c55971a323bcd19d9d476e2aa6cd8a3", "70eeba507de79e5d29714f8e5014358bb85d29e8", "input16.cmt"),
    ("input16_t88", "input16.t88", 5048, "80a95445", "957d60aebf427440bcd6a5de91f395df", "7d3a896201d05671bab4d87ccef2dc33d92af653", "input16.t88"),
    ("input17_cmt", "input17.cmt", 9983, "e85a6656", "c8523252c77eb22aff64131181e19cc1", "6a5b81b8568c50bb7e4c43bdeb51fc2a03219b2c", "input17.cmt"),
    ("input17_t88", "input17.t88", 10457, "29482453", "fdf940a963613ef77e0d7b0e89b7088c", "29141be473d7e8d8e21c642b2cb47889c5b7e05a", "input17.t88"),
    ("input18_cmt", "input18.cmt", 12593, "c647a258", "43937d48f62c111d9102b0bfa294fcdf", "d8b7bd1de735d93ec704c2035967839bde4c6f50", "input18.cmt"),
    ("input18_t88", "input18.t88", 12755, "dbbc4b47", "0dbd7c46b8f6eb92d901cd63353f8daa", "d7654f37668294d20d2c669b5b679852a1fa555d", "input18.t88"),
    ("input19_cmt", "input19.cmt", 6059, "385657a4", "905de83ec2b7502b75fb7a470606aaf0", "959a4860afd531f88dfb70b176aa69623d2788b7", "input19.cmt"),
    ("input19_t88", "input19.t88", 6221, "16b20d73", "929e4738c83ce98899167d03fb184607", "947ef5b9455f2f36cacb0506725ff407cccdd6a1", "input19.t88"),
    ("input20_cmt", "input20.cmt", 45153, "96214463", "fb181a90267e2f9592639eace2d716a0", "df15156a2a719c922a8e502a8331b50440137bea", "input20.cmt"),
    ("input20_t88", "input20.t88", 45731, "2d855766", "5991b14cc6b79641d4e62ce3fffaff3e", "cd1c8aae89d5d674a88f61edd6f13985f7f85896", "input20.t88"),
    ("pc88_door_door_1200_wav", "snippet.wav", 414012, "4e1a9921", "50e693b01795caf1beb3e026e92f53f8", "e495dd758f80cc73c62ecc907d02a3fe56f674e0", "Door Door (Enix)"),
    ("pc88_digdug_600_wav", "snippet2.wav", 659500, "e50d589d", "9359473f4869b63f29aeefd7ca9c8dc4", "97d37c0f2842933c8a906accba1c03599f41c8f8", "Dig Dug (Dempa Micomsoft)"),
]

FIXTURE_REGISTRY: Dict[str, FixtureSpec] = {}
FIXTURES_BY_FILENAME: Dict[str, FixtureSpec] = {}
FIXTURES_BY_SHA1: Dict[str, FixtureSpec] = {}

for _fid, _fname, _sz, _crc, _md5, _sha, _title in _RAW_FIXTURE_SPECS:
    _spec = FixtureSpec(
        id=_fid,
        filename=_fname,
        size=_sz,
        crc32=_crc.lower(),
        md5=_md5.lower(),
        sha1=_sha.lower(),
        title=_title,
    )
    FIXTURE_REGISTRY[_fid] = _spec
    FIXTURE_REGISTRY[_fname] = _spec
    FIXTURES_BY_FILENAME[_fname.lower()] = _spec
    FIXTURES_BY_SHA1[_sha.lower()] = _spec

# Common ID aliases
if "pc88_door_door_1200_wav" in FIXTURE_REGISTRY:
    FIXTURE_REGISTRY["snippet_wav"] = FIXTURE_REGISTRY["pc88_door_door_1200_wav"]
    FIXTURE_REGISTRY["door_door_wav"] = FIXTURE_REGISTRY["pc88_door_door_1200_wav"]
if "pc88_digdug_600_wav" in FIXTURE_REGISTRY:
    FIXTURE_REGISTRY["snippet2_wav"] = FIXTURE_REGISTRY["pc88_digdug_600_wav"]
    FIXTURE_REGISTRY["digdug_wav"] = FIXTURE_REGISTRY["pc88_digdug_600_wav"]
if "pc88_door_door_1200_cmt" in FIXTURE_REGISTRY:
    FIXTURE_REGISTRY["input01_cmt"] = FIXTURE_REGISTRY["pc88_door_door_1200_cmt"]
if "pc88_door_door_1200_t88" in FIXTURE_REGISTRY:
    FIXTURE_REGISTRY["input01_t88"] = FIXTURE_REGISTRY["pc88_door_door_1200_t88"]
if "pc88_digdug_600_cmt" in FIXTURE_REGISTRY:
    FIXTURE_REGISTRY["input05_cmt"] = FIXTURE_REGISTRY["pc88_digdug_600_cmt"]
if "pc88_digdug_600_t88" in FIXTURE_REGISTRY:
    FIXTURE_REGISTRY["input05_t88"] = FIXTURE_REGISTRY["pc88_digdug_600_t88"]


def get_fixture_spec(key: Union[str, FixtureSpec]) -> Optional[FixtureSpec]:
    """Look up a FixtureSpec by canonical ID, filename, alias, SHA-1, or FixtureSpec itself."""
    if isinstance(key, FixtureSpec):
        return key
    if not isinstance(key, str):
        return None
    if key in FIXTURE_REGISTRY:
        return FIXTURE_REGISTRY[key]
    k_lower = key.lower()
    if k_lower in FIXTURE_REGISTRY:
        return FIXTURE_REGISTRY[k_lower]
    if k_lower in FIXTURES_BY_FILENAME:
        return FIXTURES_BY_FILENAME[k_lower]
    if k_lower in FIXTURES_BY_SHA1:
        return FIXTURES_BY_SHA1[k_lower]
    return None


def _calc_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


class FixturePool:
    """Content-addressed fixture discovery pool indexing candidate files by SHA-1 hash."""

    def __init__(
        self,
        search_dirs: Optional[Sequence[Union[str, Path]]] = None,
        registry: Optional[Mapping[str, FixtureSpec]] = None,
    ):
        self._registry = registry if registry is not None else FIXTURE_REGISTRY
        self._explicit_dirs = [Path(d) for d in search_dirs] if search_dirs else []
        self._by_sha1: Dict[str, Path] = {}
        self._by_filename: Dict[str, Path] = {}
        self._scanned_dirs: List[Path] = []
        self.rescan()

    def rescan(self) -> None:
        """Scan candidate directories and index all found files by SHA-1."""
        candidate_dirs: List[Path] = []
        for d in self._explicit_dirs:
            if d.exists() and d not in candidate_dirs:
                candidate_dirs.append(d)

        env_dir = os.environ.get("DWIMSY_TEST_FIXTURES")
        if env_dir:
            p = Path(env_dir)
            if p.exists() and p not in candidate_dirs:
                candidate_dirs.append(p)

        pkg_root = Path(__file__).resolve().parent.parent.parent
        for default_rel in [
            pkg_root / "tests" / "fixtures",
            pkg_root / "fixtures",
            Path.cwd() / "tests" / "fixtures",
            Path.cwd() / "fixtures",
            Path.home() / ".local" / "share" / "dwimsy" / "fixtures",
        ]:
            if default_rel.exists() and default_rel not in candidate_dirs:
                candidate_dirs.append(default_rel)

        self._scanned_dirs = candidate_dirs
        self._by_sha1.clear()
        self._by_filename.clear()

        for c_dir in candidate_dirs:
            if c_dir.is_file():
                try:
                    s1 = _calc_sha1(c_dir)
                    self._by_sha1.setdefault(s1, c_dir)
                    self._by_filename.setdefault(c_dir.name.lower(), c_dir)
                except OSError:
                    pass
                continue
            for root, _dirs, files in os.walk(c_dir):
                for f in files:
                    fpath = Path(root) / f
                    try:
                        s1 = _calc_sha1(fpath)
                        self._by_sha1.setdefault(s1, fpath)
                        self._by_filename.setdefault(f.lower(), fpath)
                    except OSError:
                        pass

    def get(self, key: Union[str, FixtureSpec]) -> Optional[Path]:
        """Retrieve path to fixture by spec, ID, filename, or SHA-1 hash."""
        spec = get_fixture_spec(key)
        if spec is not None:
            if spec.sha1.lower() in self._by_sha1:
                return self._by_sha1[spec.sha1.lower()]
            if spec.filename.lower() in self._by_filename:
                cand = self._by_filename[spec.filename.lower()]
                try:
                    if _calc_sha1(cand) == spec.sha1.lower():
                        return cand
                except OSError:
                    pass
        elif isinstance(key, str):
            k_lower = key.lower()
            if k_lower in self._by_sha1:
                return self._by_sha1[k_lower]
            if k_lower in self._by_filename:
                return self._by_filename[k_lower]

        return None

    def require(self, key: Union[str, FixtureSpec]) -> Path:
        """Retrieve path to fixture, raising unittest.SkipTest with informative diagnostic if missing."""
        path = self.get(key)
        if path is None:
            raise unittest.SkipTest(self.skip_reason(key))
        return path

    def skip_reason(self, key: Union[str, FixtureSpec]) -> str:
        """Format the standardized skip diagnostic string for a missing fixture."""
        spec = get_fixture_spec(key)
        if spec is not None:
            return f'Fixture "{spec.display_title}" (SHA1: {spec.sha1}) not found in fixture pool.'
        return f'Fixture "{key}" not found in fixture pool.'


_GLOBAL_POOL: Optional[FixturePool] = None


def get_fixture_pool(search_dirs: Optional[Sequence[Union[str, Path]]] = None) -> FixturePool:
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
