#!/usr/bin/env python3
"""dwimsy.meta.integrity - Canonical portable-project hashing and runtime modification detection.

The integrity hash covers the canonical project window used by portable bundles:
native Python code, tests, project metadata, and the dependency paths declared by
``.gitmodules``. Files are ordered by POSIX relative path, text is normalized to LF
line endings, and the sealed ``__code_hash__`` value in ``_version.py`` is replaced
with the empty sentinel before hashing.
"""

from __future__ import annotations

import argparse

import hashlib
import ast
import fnmatch
import re
import sys
import os
from pathlib import Path
from typing import Iterable, Optional, Tuple, List, Set, Dict, Any

for p in Path(__file__).resolve().parents:
    if (p / "dwimsy").is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
        break

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_BUNDLE_ASSET_CACHE: Optional[dict[str, bytes]] = None
_HASH_CACHE: dict[tuple, tuple[tuple, str]] = {}


def clear_integrity_cache():
    """Clear integrity hash and bundle asset caches."""
    global _HASH_CACHE, _BUNDLE_ASSET_CACHE
    _HASH_CACHE.clear()
    _BUNDLE_ASSET_CACHE = None


def _repo_fingerprint(repo: Path, baseline: bool) -> tuple:
    if baseline:
        return (str(repo), True)
    files = source_files(repo)
    mtimes = []
    for f in files:
        try:
            st = f.stat()
            mtimes.append((f.relative_to(repo).as_posix(), st.st_mtime_ns, st.st_size))
        except OSError:
            pass
    return (str(repo), False, tuple(mtimes))


def get_latest_release_info(root: Optional[Path] = None) -> tuple[str, str]:
    """Retrieve (version, UTC timestamp) for the most recent changelog entry.

    New changelog entries use second-exact ISO-8601 UTC timestamps.  Older
    date-only entries remain readable and are normalized to midnight UTC.
    """
    repo = find_repo_root(root) if root is not None else find_repo_root()
    c_file = repo / "CHANGELOG.md"
    c_text = None
    if c_file.is_file():
        try:
            c_text = c_file.read_text(encoding="utf-8")
        except OSError:
            pass
    if c_text is None:
        try:
            from dwimsy.meta import unbundle

            c_text = unbundle.get_asset_text("CHANGELOG.md")
        except Exception:
            pass
    if c_text:
        m = re.search(
            r"## \[([^\]]+)\] - " r"(\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}Z)?)",
            c_text,
        )
        if m:
            stamp = m.group(2)
            if "T" not in stamp:
                stamp += "T00:00:00Z"
            return (m.group(1), stamp)
    v = _version_values(root).get("__version__", "0.1.6.0-dev")
    return (v, "2026-08-26T00:00:00Z")


_VERSION_FILE = _PACKAGE_ROOT / "_version.py"
_UNBUNDLE_RE = re.compile(
    rb"(?ms)^(?P<prefix>[ \t]*blztar[ \t]*=[ \t]*\"\"\")(?:.*?)(?P<suffix>\"\"\"[ \t]*(?:#.*)?$)"
)
_HASH_RE = re.compile(
    rb"(?m)^(?P<prefix>[ \t]*__code_hash__[ \t]*=[ \t]*)"
    rb"(?P<quote>['\"])[^'\"]*(?P=quote)(?P<suffix>[ \t]*(?:#.*)?\r?\n?)$"
)


def is_standalone_bundle() -> bool:
    """Return True when code is being served by the relocatable bundle bootstrap."""
    try:
        from dwimsy.meta import unbundle

        is_checkout, repo_root = unbundle.detect_self_location()
        if is_checkout and repo_root is not None:
            return False

        main_mod = sys.modules.get("__main__")
        if (
            main_mod is sys.modules.get("dwimsy.meta.unbundle")
            and hasattr(main_mod, "blztar")
            and hasattr(main_mod, "bootstrap_in_memory_cli")
        ):
            return True

        for finder in sys.meta_path:
            if (
                finder.__class__.__name__ == "BundleFinder"
                and getattr(finder, "on_disk_root", None) is None
                and getattr(finder, "_index", None)
                and getattr(finder, "b64_string", "").strip()
            ):
                return True

        mod = sys.modules.get("dwimsy.meta.unbundle")
        mod_file = str(getattr(mod, "__file__", ""))
        if "<dwimsy-bundle>" in mod_file:
            return True

        return True
    except Exception:
        return False


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Locate the root directory of the dwimsy repository or extracted tree."""
    if start is not None:
        cur = Path(start).resolve()
        while cur != cur.parent:
            if (cur / "dwimsy").is_dir() and (cur / "dwimsy" / "__init__.py").is_file():
                return cur
            cur = cur.parent
        return Path(start).resolve()

    test_root = os.environ.get("DWIMSY_TEST_REPO_ROOT")
    if test_root:
        candidate = Path(test_root).resolve()
        if (candidate / "dwimsy").is_dir() and (
            candidate / "dwimsy" / "__init__.py"
        ).is_file():
            return candidate

    if is_standalone_bundle():
        return _PACKAGE_ROOT.parent

    cur = Path.cwd().resolve()
    while cur != cur.parent:
        if (cur / "dwimsy").is_dir() and (cur / "dwimsy" / "__init__.py").is_file():
            return cur
        cur = cur.parent

    cur = Path(__file__).resolve().parent
    while cur != cur.parent:
        if (cur / "dwimsy").is_dir() and (cur / "dwimsy" / "__init__.py").is_file():
            return cur
        cur = cur.parent

    for sp in sys.path:
        if sp:
            p = Path(sp).resolve()
            if (p / "dwimsy").is_dir() and (p / "dwimsy" / "__init__.py").is_file():
                return p

    return Path.cwd().resolve()


def package_root() -> Path:
    """Return the on-disk ``dwimsy`` package root."""
    repo = find_repo_root()
    if (repo / "dwimsy").is_dir():
        return repo / "dwimsy"
    return _PACKAGE_ROOT


def version_file_path(root: Optional[Path] = None) -> Path:
    """Locate on-disk _version.py path."""
    repo = find_repo_root(root) if root is not None else find_repo_root()
    if (repo / "dwimsy" / "_version.py").is_file():
        return repo / "dwimsy" / "_version.py"
    if (repo / "_version.py").is_file():
        return repo / "_version.py"
    return _VERSION_FILE


class GitIgnoreRule:
    def __init__(
        self,
        is_negation: bool,
        directory_only: bool,
        exact_regex: re.Pattern,
        prefix_regex: re.Pattern,
    ):
        self.is_negation = is_negation
        self.directory_only = directory_only
        self.exact_regex = exact_regex
        self.prefix_regex = prefix_regex


class GitIgnoreMatcher:
    """Evaluates relative paths against repo .gitignore rules in pure Python."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        files: Optional[dict[str, bytes]] = None,
    ):
        self.repo_root = Path(repo_root).resolve() if repo_root is not None else None
        self.rules: List[GitIgnoreRule] = []
        if files is not None:
            self._load_rules_from_files(files)
        elif self.repo_root is not None:
            self._load_rules_from_disk()

    def _load_rules_from_files(self, files: dict[str, bytes]) -> None:
        gi_keys = [
            k
            for k in files
            if Path(k).name == ".gitignore"
            and not any(part == ".git" for part in Path(k).parts)
        ]
        gi_keys.sort(key=lambda k: len(Path(k).parts))
        for k in gi_keys:
            rel_dir = Path(k).parent.as_posix()
            if rel_dir == ".":
                rel_dir = ""
            text = files[k].decode("utf-8", errors="replace")
            self._parse_gitignore_text(text, rel_dir)

    def _load_rules_from_disk(self) -> None:
        if self.repo_root is None or not self.repo_root.is_dir():
            try:
                from dwimsy.meta import unbundle

                text = unbundle.get_asset_text(".gitignore")
                self._parse_gitignore_text(text, "")
            except Exception:
                pass
            return

        gitignore_files: List[Path] = []
        for p in self.repo_root.rglob(".gitignore"):
            if any(part == ".git" for part in p.parts):
                continue
            gitignore_files.append(p)

        gitignore_files.sort(key=lambda p: len(p.parts))

        if not gitignore_files:
            try:
                from dwimsy.meta import unbundle

                text = unbundle.get_asset_text(".gitignore")
                self._parse_gitignore_text(text, "")
            except Exception:
                pass
            return

        for gf in gitignore_files:
            try:
                rel_dir = gf.parent.relative_to(self.repo_root).as_posix()
                if rel_dir == ".":
                    rel_dir = ""
                text = gf.read_text(encoding="utf-8", errors="replace")
                self._parse_gitignore_text(text, rel_dir)
            except Exception:
                pass

    def _parse_gitignore_text(self, text: str, base_dir_rel: str) -> None:
        for raw_line in text.splitlines():
            line = raw_line.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue

            is_negation = False
            if line.startswith("!"):
                is_negation = True
                line = line[1:]

            if line.startswith(r"\#") or line.startswith(r"\!"):
                line = line[1:]

            line = re.sub(r"(?<!\\)(?:\\\\)*\s+$", "", line)
            line = line.replace(r"\ ", " ")
            if not line:
                continue

            directory_only = False
            if line.endswith("/"):
                directory_only = True
                line = line[:-1]

            anchored = line.startswith("/")
            has_slash = "/" in line.lstrip("/")
            line = line.lstrip("/")

            i = 0
            n = len(line)
            res: List[str] = []
            while i < n:
                c = line[i]
                if c == "*":
                    if i + 1 < n and line[i + 1] == "*":
                        if i + 2 < n and line[i + 2] == "/":
                            res.append(r"(?:.+/)?")
                            i += 3
                        elif i > 0 and line[i - 1] == "/":
                            res.append(r".*")
                            i += 2
                        else:
                            res.append(r".*")
                            i += 2
                    else:
                        res.append(r"[^/]*")
                        i += 1
                elif c == "?":
                    res.append(r"[^/]")
                    i += 1
                elif c == "[":
                    j = i + 1
                    if j < n and line[j] in ("!", "^"):
                        j += 1
                    if j < n and line[j] == "]":
                        j += 1
                    while j < n and line[j] != "]":
                        j += 1
                    if j < n:
                        class_content = line[i + 1 : j]
                        if class_content.startswith("!"):
                            class_content = "^" + class_content[1:]
                        res.append(f"[{class_content}]")
                        i = j + 1
                    else:
                        res.append(r"\[")
                        i += 1
                else:
                    res.append(re.escape(c))
                    i += 1

            pattern_re = "".join(res)
            base_prefix = re.escape(base_dir_rel.strip("/"))
            if base_prefix:
                base_prefix += "/"

            if anchored or has_slash:
                exact_re = f"^{base_prefix}{pattern_re}$"
                prefix_re = f"^{base_prefix}{pattern_re}/.*$"
            else:
                exact_re = f"^{base_prefix}(?:.+/)?{pattern_re}$"
                prefix_re = f"^{base_prefix}(?:.+/)?{pattern_re}/.*$"

            try:
                compiled_exact = re.compile(exact_re)
                compiled_prefix = re.compile(prefix_re)
                self.rules.append(
                    GitIgnoreRule(
                        is_negation=is_negation,
                        directory_only=directory_only,
                        exact_regex=compiled_exact,
                        prefix_regex=compiled_prefix,
                    )
                )
            except re.error:
                pass

    def matches(self, rel_path: str | Path, is_dir: bool = False) -> bool:
        path_obj = Path(rel_path)
        parts = path_obj.parts
        if (
            any(p == ".git" or p == "__pycache__" for p in parts)
            or path_obj.suffix == ".pyc"
        ):
            return True
        posix_path = path_obj.as_posix().strip("/")
        if not posix_path:
            return False

        matched = False
        for rule in self.rules:
            if is_dir:
                if rule.exact_regex.match(posix_path) or rule.prefix_regex.match(
                    posix_path + "/"
                ):
                    matched = not rule.is_negation
            else:
                if rule.directory_only:
                    if rule.prefix_regex.match(posix_path):
                        matched = not rule.is_negation
                else:
                    if rule.exact_regex.match(posix_path) or rule.prefix_regex.match(
                        posix_path
                    ):
                        matched = not rule.is_negation

        return matched


def get_git_command(args: Optional[Any] = None) -> Optional[str]:
    """Return the configured git executable command, or None if git is disabled."""
    if args is not None:
        if getattr(args, "without_git", False):
            return None
        with_git = getattr(args, "with_git", None)
        if with_git is not None and with_git is not False:
            return with_git if isinstance(with_git, str) and with_git else "git"
    if os.environ.get("DWIMSY_WITHOUT_GIT") == "1":
        return None
    env_git = os.environ.get("DWIMSY_GIT")
    if env_git:
        return env_git
    return "git"


def canonical_manifest(
    root: Optional[Path] = None, baseline: bool = False
) -> Tuple[str, ...]:
    """Return the canonical portable-project manifest patterns.

    The manifest covers native Python code, tests, canonical project metadata,
    and one lazy recursive glob for each path declared by .gitmodules.
    """
    repo = find_repo_root(root) if root is None else Path(root).resolve()
    patterns = [
        "dwimsy/**/*.py",
        "tests/**/*.py",
        "tests/**/*.md",
        ".gitignore",
        ".gitmodules",
        "LICENSE",
        "README.md",
        "CHANGELOG.md",
    ]
    gitmodules = repo / ".gitmodules"
    gitmodules_text = None
    if not baseline and gitmodules.is_file():
        gitmodules_text = gitmodules.read_text(encoding="utf-8")
    if gitmodules_text is None:
        try:
            from dwimsy.meta import unbundle

            gitmodules_text = unbundle.get_asset_text(".gitmodules")
        except Exception:
            pass
    if gitmodules_text is not None:
        for line in gitmodules_text.splitlines():
            m = re.match(r"\s*path\s*=\s*(\S+)\s*$", line)
            if m:
                path = m.group(1).strip("/")
                patterns.append(f"{path}/**/*")
    return tuple(patterns)


def _manifest_matches(rel_path: str, patterns: Iterable[str]) -> bool:
    """Return whether a normalized relative path belongs to a manifest glob."""
    for pattern in patterns:
        if fnmatch.fnmatchcase(rel_path, pattern):
            return True
        # Treat **/ as zero or more directory components.
        if "**/" in pattern:
            if fnmatch.fnmatchcase(rel_path, pattern.replace("**/", "", 1)):
                return True
        if pattern.endswith("/**/*"):
            prefix = pattern[:-4]
            if rel_path == prefix or rel_path.startswith(prefix + "/"):
                return True
    return False


def source_files(root: Optional[Path] = None) -> Tuple[Path, ...]:
    """Return canonical on-disk files selected by the portable manifest."""
    repo = find_repo_root(root) if root is None else Path(root).resolve()
    patterns = canonical_manifest(repo)
    if not ((repo / "dwimsy").is_dir() and (repo / "dwimsy" / "__init__.py").is_file()):
        return ()
    gitignore = GitIgnoreMatcher(repo)
    files = []
    for p in repo.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(repo).as_posix()
        if any(part == ".git" for part in p.parts) or "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        if gitignore.matches(rel, is_dir=False):
            continue
        if _manifest_matches(rel, patterns):
            files.append(p)
    return tuple(sorted(files, key=lambda p: p.relative_to(repo).as_posix()))


def _canonical_bytes(data: bytes, rel_path: str) -> bytes:
    """Return normalized bytes for one source or asset file."""
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if data and not data.endswith(b"\n"):
        data = data + b"\n"
    if rel_path == "dwimsy/meta/unbundle.py":
        match = _UNBUNDLE_RE.search(data)
        if match is None:
            raise ValueError(
                "dwimsy/meta/unbundle.py does not contain a blztar assignment"
            )
        data = (
            data[: match.start()]
            + match.group("prefix")
            + b"\n"
            + match.group("suffix")
            + data[match.end() :]
        )
    if (
        rel_path == "dwimsy/_version.py"
        or rel_path == "_version.py"
        or rel_path.endswith("/_version.py")
    ):
        match = _HASH_RE.search(data)
        if match is None:
            raise ValueError(
                f"{rel_path} does not contain the required __code_hash__ sentinel"
            )
        replacement = (
            match.group("prefix")
            + match.group("quote")
            + match.group("quote")
            + match.group("suffix")
        )
        data = data[: match.start()] + replacement + data[match.end() :]
    return data


def canonical_assets(
    root: Optional[Path] = None, baseline: bool = False
) -> dict[str, bytes]:
    """Return canonical portable-project assets before content normalization."""
    from dwimsy.meta import unbundle

    repo = find_repo_root(root) if root is None else Path(root).resolve()
    patterns = canonical_manifest(repo, baseline=baseline)
    candidates: dict[str, bytes] = {}

    if not baseline:
        for p in source_files(repo):
            candidates[p.relative_to(repo).as_posix()] = p.read_bytes()

    try:
        need_bundle = baseline or not candidates
        if not need_bundle:
            required_top = (".gitignore", ".gitmodules", "LICENSE", "README.md")
            need_bundle = not all(name in candidates for name in required_top)
            if not need_bundle:
                dep_prefixes = [
                    pattern[:-5] for pattern in patterns if pattern.endswith("/**/*")
                ]
                need_bundle = any(
                    not any(
                        rel == prefix or rel.startswith(prefix + "/")
                        for rel in candidates
                    )
                    for prefix in dep_prefixes
                )
        if need_bundle:
            global _BUNDLE_ASSET_CACHE
            if _BUNDLE_ASSET_CACHE is None:
                _BUNDLE_ASSET_CACHE = {}
                raw_assets = unbundle.materialize_stream0_assets()
                for name, data in raw_assets.items():
                    norm = name[2:] if name.startswith("./") else name
                    if norm.startswith("<dwimsy-bundle>/"):
                        norm = norm[len("<dwimsy-bundle>/") :]
                    _BUNDLE_ASSET_CACHE[norm] = data
            for rel, data in _BUNDLE_ASSET_CACHE.items():
                if _manifest_matches(rel, patterns) and (
                    baseline or rel not in candidates
                ):
                    candidates[rel] = data
    except Exception:
        if baseline:
            raise
    return dict(sorted(candidates.items()))


def canonical_code_hash(root: Optional[Path] = None, baseline: bool = False) -> str:
    """Calculate the canonical SHA-256 hash of the portable project window."""
    repo = find_repo_root(root) if root is None else Path(root).resolve()
    key = (str(repo), baseline)
    fp = _repo_fingerprint(repo, baseline)
    if key in _HASH_CACHE and _HASH_CACHE[key][0] == fp:
        return _HASH_CACHE[key][1]

    digest = hashlib.sha256()
    for rel, data in canonical_assets(root, baseline=baseline).items():
        cdata = _canonical_bytes(data, rel)
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(cdata)
        digest.update(b"\0")
    result = digest.hexdigest()
    _HASH_CACHE[key] = (fp, result)
    return result


def _version_values(
    root: Optional[Path] = None, baseline: bool = False
) -> dict[str, str]:
    """Read version metadata from disk or the in-memory portable bundle."""
    v_file = version_file_path(root)
    if v_file.is_file() and not baseline:
        source = v_file.read_text(encoding="utf-8")
        filename = str(v_file)
    else:
        from dwimsy.meta import unbundle

        try:
            source = unbundle.get_asset_text("dwimsy/_version.py")
        except Exception:
            source = unbundle.get_asset_text("_version.py")
        filename = "<dwimsy-bundle>/dwimsy/_version.py"
    tree = ast.parse(source, filename=filename)
    values: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in {
                "__version__",
                "__code_hash__",
            }:
                if isinstance(node.value, ast.Constant) and isinstance(
                    node.value.value, str
                ):
                    values[target.id] = node.value.value
    return values


def sealed_code_hash(root: Optional[Path] = None, baseline: bool = False) -> str:
    """Return the recorded canonical hash, or ``\"\"`` when unsealed."""
    values = _version_values(root)
    return values.get("__code_hash__", "").lower()


def is_modified(root: Optional[Path] = None, baseline: bool = False) -> bool:
    """Return whether the current source differs from its sealed hash or baseline payload.

    In standalone bundle mode without explicit root override, returns False (Spec §4.4).
    """
    test_root = os.environ.get("DWIMSY_TEST_REPO_ROOT")
    if (
        test_root
        and (
            root is None or str(Path(root).resolve()) == str(Path(test_root).resolve())
        )
        and not baseline
        and (is_standalone_bundle() or "<dwimsy-bundle>" in str(__file__))
    ):
        return False
    if (
        root is None
        and not baseline
        and (is_standalone_bundle() or "<dwimsy-bundle>" in str(__file__))
    ):
        return False
    repo = find_repo_root(root) if root is not None else find_repo_root()
    if is_standalone_bundle() and (
        "<dwimsy-bundle>" in str(repo) or repo == _PACKAGE_ROOT.parent
    ):
        return False
    if not ((repo / "dwimsy").is_dir() and (repo / "dwimsy" / "__init__.py").is_file()):
        return False
    sealed = sealed_code_hash(repo, baseline=baseline)
    if not sealed:
        try:
            cur_hash = canonical_code_hash(repo, baseline=False)
            declared_v = (
                _version_values(repo, baseline=False)
                .get("__version__", "")
                .split("+mod.")[0]
            )
            if declared_v:
                from dwimsy.meta import unbundle, versions

                raw_b64 = None
                unb_f = repo / "dwimsy" / "meta" / "unbundle.py"
                if unb_f.is_file():
                    m = re.search(
                        r'blztar\s*=\s*"""([\s\S]*?)"""',
                        unb_f.read_text(encoding="utf-8", errors="replace"),
                    )
                    if m and m.group(1).strip():
                        raw_b64 = m.group(1).strip()
                if not raw_b64:
                    raw_b64 = unbundle._get_active_blztar()
                if raw_b64:
                    vs = versions.VersionSpace.from_blztar(raw_b64)
                    res = vs.resolve_version_ref(declared_v)
                    if res is not None:
                        s, ord_idx, ref = res
                        expected_h = ref.content_hash or s.compute_content_hash(ord_idx)
                        if cur_hash == expected_h:
                            return False
            return cur_hash != canonical_code_hash(repo, baseline=True)
        except Exception:
            return True
    return canonical_code_hash(repo, baseline=baseline) != sealed


def modification_hash(
    root: Optional[Path] = None, length: int = 12, baseline: bool = False
) -> str:
    """Return the short current canonical hash used for ``+mod.`` versions."""
    if length < 1:
        raise ValueError("length must be positive")
    return canonical_code_hash(root, baseline=baseline)[:length]


def version(base_version: Optional[str] = None, root: Optional[Path] = None) -> str:
    """Return the package version, adding a PEP 440 local ``+mod.`` suffix.

    If no base version is supplied it is read from ``dwimsy._version``.
    A portable bundle with no explicit root is hermetic: its version comes
    from the embedded payload and its host checkout is never inspected.
    """
    if base_version is None:
        values = _version_values(root)
        base_version = values.get("__version__")
        if not base_version:
            try:
                import dwimsy._version as _v_mod

                base_version = getattr(_v_mod, "__version__", None)
            except Exception:
                pass
        if not isinstance(base_version, str) or not base_version:
            raise ValueError("__version__ must be a non-empty string")

    if "+mod." in base_version:
        base_version = base_version.split("+mod.")[0]

    if root is None and is_standalone_bundle():
        return base_version

    if is_modified(root):
        return f"{base_version}+mod.{modification_hash(root)}"
    return base_version


def version_banner(
    prog: str = "dwimsy",
    root: Optional[Path] = None,
    verbose: bool = False,
    version_tag: Optional[str] = None,
    timestamp: Optional[str] = None,
    content_hash: Optional[str] = None,
) -> str:
    """Format standard --version output with version, UTC timestamp, and content hash."""
    if root is None and is_standalone_bundle() and not (version_tag or content_hash):
        from dwimsy.meta import unbundle, versions

        raw_b64 = unbundle._get_active_blztar()
        vs = (
            versions.VersionSpace.from_blztar(raw_b64)
            if raw_b64
            else versions.VersionSpace()
        )
        selected = vs.resolve_selection("primary")
        if selected and selected.first:
            sel = selected.first
            layer = sel.stream.layers[sel.ordinal]
            v_tag = sel.version.tag
            c_hash = layer.code_hash or sel.version.content_hash or ""
            if timestamp is None:
                timestamp = vs.get_layer_timestamp(layer)
        else:
            v_tag = version()
            c_hash = ""
    else:
        repo = find_repo_root(root) if root is not None else find_repo_root()
        v_tag = version_tag or version(root=repo)
        c_hash = content_hash or canonical_code_hash(repo, baseline=False)

    if timestamp is None:
        try:
            from dwimsy.meta import unbundle, versions

            raw_b64 = unbundle._get_active_blztar()
            if raw_b64:
                vs = versions.VersionSpace.from_blztar(raw_b64)
                res = vs.resolve_version_ref(v_tag.split("+")[0])
                if res is not None:
                    s_t, ord_t, _ = res
                    timestamp = vs.get_layer_timestamp(s_t.layers[ord_t])
        except Exception:
            pass
    if timestamp is None:
        try:
            files = source_files(repo)
            max_mt = max((f.stat().st_mtime for f in files if f.exists()), default=0)
            if max_mt > 0:
                import datetime

                timestamp = datetime.datetime.fromtimestamp(
                    max_mt, tz=datetime.timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass
    if timestamp is None:
        _, dt_str = get_latest_release_info(repo)
        timestamp = f"{dt_str}T00:00:00Z"

    h_str = c_hash if verbose else c_hash[:12]
    if h_str:
        return f"{prog} {v_tag} ({timestamp} {h_str})"
    return f"{prog} {v_tag}"


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for running dwimsy.meta.integrity directly."""
    import argparse

    effective = sys.argv[1:] if argv is None else list(argv)
    from dwimsy.cli.dispatch import early_dispatch

    handled, effective = early_dispatch(
        effective, ["meta", "integrity"], use_process_argv0=(argv is None)
    )
    if handled:
        return 0

    test_arg = None
    for a in effective:
        if a in ("-T", "--test") or a.startswith("--test="):
            test_arg = a
            break
    if test_arg is not None:
        verbosity = 1
        for a in effective:
            if a in ("-v", "--verbose"):
                verbosity = max(verbosity + 1, 2)
            elif a.startswith("-") and len(a) > 1 and all(c == "v" for c in a[1:]):
                verbosity = max(verbosity + len(a) - 1, 2)
        from dwimsy.tests import run_tests

        pattern = None
        if test_arg.startswith("--test="):
            pattern = [test_arg.split("=", 1)[1]]
        else:
            pattern = ["meta integrity"]
        return run_tests(pattern, verbose=verbosity)

    if any(a == "--help-all" for a in effective):
        effective = ["-h" if a == "--help-all" else a for a in effective]

    parser = argparse.ArgumentParser(
        prog="dwimsy-integrity",
        description="Verify canonical portable-project integrity and hash status.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {version()}",
    )
    parser.add_argument(
        "-T",
        "--test",
        nargs="?",
        const=True,
        default=False,
        help="Run scoped integrity self-tests in-process (optional pattern filter)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase output verbosity",
    )
    parser.add_argument(
        "--help-all",
        action="store_true",
        help="Show full help documentation and exit",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress output and exit with 0 if clean, 1 if modified",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Check the embedded clean baseline instead of the working tree",
    )
    args = parser.parse_args(effective)

    if args.test is not False:
        from dwimsy.tests import run_tests

        pattern = [args.test] if isinstance(args.test, str) else ["meta integrity"]
        return run_tests(pattern, verbose=max(args.verbose, 1))

    baseline = bool(args.baseline)
    current = canonical_code_hash(baseline=baseline)
    sealed = sealed_code_hash()
    modified = is_modified(baseline=baseline)
    ver_str = version()

    if not args.quiet:
        print(f"Canonical hash : {current}")
        print(f"Sealed hash    : {sealed or '(unsealed)'}")
        print(f"Status         : {'MODIFIED' if modified else 'CLEAN'}")
        print(f"Version        : {ver_str}")

    return 1 if modified else 0


if __name__ == "__main__":
    sys.exit(main())


class _LazyVersionAction(argparse.Action):
    """Only evaluates version function if -V or --version is present in CLI arguments."""

    def __init__(
        self,
        option_strings,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help="show program's version number and exit",
        version_fn=None,
    ):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help,
        )
        self.version_fn = version_fn

    def __call__(self, parser, namespace, values, option_string=None):
        prog = getattr(parser, "prog", "dwimsy")
        verbose = getattr(namespace, "verbose", 0)
        is_verbose = verbose > 0 if isinstance(verbose, int) else bool(verbose)
        msg = version_banner(prog=prog, verbose=is_verbose)
        parser._print_message(f"{msg}\n", sys.stdout)
        parser.exit()
