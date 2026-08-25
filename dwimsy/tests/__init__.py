"""dwimsy.tests - Test discovery, fixture management, and in-process test execution engine."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import List, Optional, Sequence

from dwimsy.meta import unbundle


def find_repo_root(start: Optional[Path] = None) -> Optional[Path]:
    """Locate repo root by searching upward from start, __file__, or current working directory."""
    if start is not None:
        cur = Path(start).resolve()
        while cur != cur.parent:
            if (cur / "dwimsy").is_dir() and (cur / "dwimsy" / "__init__.py").is_file():
                return cur
            cur = cur.parent
        return Path(start).resolve()

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

    return None


def find_disk_tests_dir(start: Optional[Path] = None) -> Optional[Path]:
    """Locate the tests/ directory on disk if present."""
    if start is not None:
        p = Path(start).resolve()
        if (p / "tests").is_dir():
            return p / "tests"
        if p.is_dir() and p.name == "tests":
            return p
    root = find_repo_root(start)
    if root is not None and (root / "tests").is_dir():
        return root / "tests"
    cwd_tests = Path.cwd() / "tests"
    if cwd_tests.is_dir():
        return cwd_tests
    return None


SCOPED_TEST_MAPPINGS = {
    "convert": ["test_cli_filters.py", "test_tape_t88.py", "test_protocols_pc88.py"],
    "inspect": ["test_core_audio.py", "test_core_pulse.py", "test_core_fsk.py"],
    "split": ["test_tape_t88.py", "test_protocols_pc88.py"],
    "join": ["test_tape_t88.py", "test_protocols_pc88.py"],
    "meta": ["test_meta_bundle.py", "test_meta_integrity.py"],
    "t882wav": ["test_core_audio.py", "test_tape_t88.py", "test_cli_filters.py"],
    "wav2t88": [
        "test_core_audio.py",
        "test_core_pulse.py",
        "test_core_fsk.py",
        "test_cli_filters.py",
    ],
    "audio": ["test_core_audio.py"],
    "pulse": ["test_core_pulse.py"],
    "fsk": ["test_core_fsk.py"],
    "tape": ["test_tape_t88.py"],
    "protocols": ["test_protocols_pc88.py"],
    "integrity": ["test_meta_integrity.py"],
    "bundle": ["test_meta_bundle.py"],
    "lint": ["test_lint_headers.py", "test_lint_markdown.py"],
    "readme": ["test_readme_sync.py"],
}


def expand_test_patterns(patterns: Optional[Sequence[str]]) -> List[str]:
    """Expand alias keywords (e.g. 'convert', 'meta', 'audio') into test file patterns."""
    if not patterns:
        return ["test_*.py"]
    expanded: List[str] = []
    for p in patterns:
        p_clean = p.strip().lower()
        if p_clean in SCOPED_TEST_MAPPINGS:
            expanded.extend(SCOPED_TEST_MAPPINGS[p_clean])
        elif p.endswith(".py"):
            expanded.append(p if p.startswith("test_") else f"test_{p}")
        else:
            expanded.append(f"*{p}*.py" if not p.startswith("test_") else f"{p}*.py")
    return list(dict.fromkeys(expanded))


def _extract_tests_from_bundle(target_dir: Path) -> Path:
    """Extract tests/ from embedded blztar into a temp directory."""
    target_dir.mkdir(parents=True, exist_ok=True)
    tests_out = target_dir / "tests"
    tests_out.mkdir(parents=True, exist_ok=True)

    with unbundle._open_bundle_tar() as tar:
        for m in tar.getmembers():
            norm_name = m.name.lstrip("./")
            if norm_name == "tests" or norm_name.startswith("tests/"):
                if m.isfile():
                    f = tar.extractfile(m)
                    if f is not None:
                        dest = target_dir / norm_name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(f.read())
                        if os.access(str(dest), os.X_OK):
                            try:
                                dest.chmod(0o755)
                            except OSError:
                                pass
                elif m.isdir():
                    (target_dir / norm_name).mkdir(parents=True, exist_ok=True)

    return tests_out


def run_tests(
    patterns: Optional[Sequence[str]] = None,
    verbose: int = 1,
    stream=None,
    repo_root: Optional[Path] = None,
) -> int:
    """Discover and run unit tests matching patterns in-process.

    Runs from disk tests/ directory if available, or automatically extracts tests
    from embedded bundle assets into an ephemeral temporary directory.
    """
    if stream is None:
        stream = sys.stderr

    expanded_patterns = expand_test_patterns(patterns)
    disk_tests = find_disk_tests_dir(repo_root)

    # Purge stale test_*, tests, and dwimsy modules from sys.modules
    for mod_name in list(sys.modules.keys()):
        if (
            mod_name.startswith("test_")
            or mod_name == "tests"
            or mod_name.startswith("tests.")
            or mod_name == "dwimsy"
            or mod_name.startswith("dwimsy.")
        ):
            del sys.modules[mod_name]

    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()

    if disk_tests is not None and any(disk_tests.glob("test_*.py")):
        root = disk_tests.parent
        orig_sys_path = list(sys.path)
        if str(disk_tests) in sys.path:
            sys.path.remove(str(disk_tests))
        if str(root) in sys.path:
            sys.path.remove(str(root))
        sys.path.insert(0, str(disk_tests))
        sys.path.insert(0, str(root))
        try:
            for pat in expanded_patterns:
                suite.addTests(
                    loader.discover(
                        start_dir=str(disk_tests),
                        pattern=pat,
                        top_level_dir=str(root),
                    )
                )
            runner = unittest.TextTestRunner(verbosity=verbose, stream=stream)
            result = runner.run(suite)
            num_failed = len(result.failures) + len(result.errors)
            return (
                0 if result.wasSuccessful() else (num_failed if num_failed > 0 else 1)
            )
        finally:
            sys.path[:] = orig_sys_path
    else:
        with tempfile.TemporaryDirectory(prefix="dwimsy_test_") as tmp:
            tmp_path = Path(tmp)
            tests_dir = _extract_tests_from_bundle(tmp_path)
            orig_sys_path = list(sys.path)
            if str(tests_dir) in sys.path:
                sys.path.remove(str(tests_dir))
            if str(tmp_path) in sys.path:
                sys.path.remove(str(tmp_path))
            sys.path.insert(0, str(tests_dir))
            sys.path.insert(0, str(tmp_path))
            try:
                for pat in expanded_patterns:
                    suite.addTests(
                        loader.discover(
                            start_dir=str(tests_dir),
                            pattern=pat,
                            top_level_dir=str(tmp_path),
                        )
                    )
                runner = unittest.TextTestRunner(verbosity=verbose, stream=stream)
                result = runner.run(suite)
                num_failed = len(result.failures) + len(result.errors)
                return (
                    0
                    if result.wasSuccessful()
                    else (num_failed if num_failed > 0 else 1)
                )
            finally:
                sys.path[:] = orig_sys_path
