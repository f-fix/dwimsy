#!/usr/bin/env python3
"""dwimsy.meta.lint - Repository hygiene and style invariant validator."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional

for p in Path(__file__).resolve().parents:
    if (p / "dwimsy").is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
        break

from dwimsy.meta import integrity


def derive_module_name(rel_path: Path) -> str:
    parts = list(rel_path.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def lint_headers(repo_root: Optional[Path] = None) -> List[str]:
    """Verify source file shebangs, docstrings, and forbidden quote syntax."""
    root = integrity.find_repo_root(repo_root)
    py_files = sorted(
        [
            p
            for p in root.rglob("*.py")
            if not p.relative_to(root).as_posix().startswith("deps")
        ]
    )
    errors: List[str] = []
    forbidden_triple = chr(39) * 3

    for p in py_files:
        rel = p.relative_to(root)
        text = p.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not lines:
            errors.append(f"{rel}: empty file")
            continue

        if forbidden_triple in text:
            errors.append(f"{rel}: contains forbidden triple single-quotes")

        has_main = (
            '__name__ == "__main__"' in text or "__name__ == '__main__'" in text
        )
        is_cli = (
            has_main
            or Path(rel).name.startswith("test_")
            or Path(rel).name
            in (
                "__main__.py",
                "unbundle.py",
                "bundle.py",
                "diff.py",
                "integrity.py",
                "version_bump.py",
                "lint.py",
                "t882wav.py",
                "wav2t88.py",
            )
        )

        has_shebang = lines[0].startswith("#!")
        if is_cli and not has_shebang:
            errors.append(f"{rel}: missing `#!/usr/bin/env python3` shebang")
        elif not is_cli and has_shebang:
            errors.append(f"{rel}: unexpected shebang on non-CLI module")

        doc_idx = 1 if has_shebang else 0
        if doc_idx >= len(lines):
            errors.append(f"{rel}: missing docstring on line {doc_idx + 1}")
            continue

        doc_line = lines[doc_idx]
        if not (
            doc_line.startswith(chr(34) * 3)
            or doc_line.startswith('r' + chr(34) * 3)
            or doc_line.startswith('R' + chr(34) * 3)
            or doc_line.startswith(chr(39) * 3)
        ):
            errors.append(
                f"{rel}: line {doc_idx + 1} does not start with docstring quote (got `{doc_line[:30]}`)"
            )
            continue

        expected_mod = derive_module_name(Path(rel))
        expected_prefix = f"{expected_mod} - "
        clean_doc = doc_line.lstrip("rR" + chr(34) + chr(39))
        if not clean_doc.startswith(expected_prefix):
            errors.append(
                f"{rel}: docstring must begin with `{expected_prefix}`, got `{clean_doc[:45]}`"
            )

    return errors


def lint_markdown(repo_root: Optional[Path] = None) -> List[str]:
    """Verify markdown files for forbidden syntax and LaTeX delimiters."""
    root = integrity.find_repo_root(repo_root)
    md_files = sorted(
        [
            p
            for p in root.rglob("*.md")
            if not p.relative_to(root).as_posix().startswith("deps")
        ]
    )
    errors: List[str] = []
    forbidden_triple_single = chr(39) * 3

    for p in md_files:
        rel = p.relative_to(root).as_posix()
        text = p.read_text(encoding="utf-8")

        if forbidden_triple_single in text:
            errors.append(f"{rel}: contains forbidden triple single-quotes")

        for i, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if (
                stripped.startswith("$$")
                and stripped.endswith("$$")
                and len(stripped) > 2
            ):
                continue
            if re.search(r"(?<!\\)\$[^\$]+\$", line) and not re.search(
                r"\$[0-9A-Za-z_-]+", line
            ):
                if any(
                    cmd in line
                    for cmd in (r"\approx", r"\text", r"\frac", r"\cdot", r"\mu")
                ):
                    errors.append(
                        f"{rel}:{i}: contains inline LaTeX math delimiters in text: `{line[:60]}`"
                    )

    return errors


def lint_dashes(repo_root: Optional[Path] = None) -> List[str]:
    """Enforce strict ASCII hyphen-minus policy (no em or en dashes in non-deps)."""
    root = integrity.find_repo_root(repo_root)
    errors: List[str] = []
    targets = sorted(
        [
            p
            for p in root.rglob("*")
            if p.is_file()
            and not p.relative_to(root).as_posix().startswith("deps")
            and p.suffix in (".py", ".md", ".txt", ".sh", ".json", ".toml", ".yaml", ".yml")
        ]
    )
    for p in targets:
        rel = p.relative_to(root).as_posix()
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if "\u2014" in line:
                errors.append(f"{rel}:{i}: contains forbidden em dash (U+2014); use ASCII hyphen-minus '-' instead")
            if "\u2013" in line:
                errors.append(f"{rel}:{i}: contains forbidden en dash (U+2013); use ASCII hyphen-minus '-' instead")
    return errors


def run_all_lints(repo_root: Optional[Path] = None) -> List[str]:
    """Run all repository hygiene checks."""
    errors = []
    errors.extend(lint_headers(repo_root))
    errors.extend(lint_markdown(repo_root))
    errors.extend(lint_dashes(repo_root))
    return errors


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for running dwimsy.meta.lint directly."""
    effective = sys.argv[1:] if argv is None else list(argv)

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
            pattern = ["meta lint"]
        return run_tests(pattern, verbose=verbosity)

    if any(a == "--help-all" for a in effective):
        effective = ["-h" if a == "--help-all" else a for a in effective]

    parser = argparse.ArgumentParser(
        prog="dwimsy-lint",
        description="Verify repository headers, docstrings, markdown syntax, and dash policy.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {integrity.version()}",
    )
    parser.add_argument(
        "-T",
        "--test",
        nargs="?",
        const=True,
        default=False,
        help="Run scoped lint self-tests in-process (optional pattern filter)",
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
        help="Suppress output on success; emit only errors",
    )
    args = parser.parse_args(effective)

    if args.test is not False:
        from dwimsy.tests import run_tests
        pattern = [args.test] if isinstance(args.test, str) else ["meta lint"]
        return run_tests(pattern, verbose=max(args.verbose, 1))

    errors = run_all_lints()
    if errors:
        for err in errors:
            print(f"[FAIL] {err}", file=sys.stderr)
        return 1
    if not args.quiet:
        print("[SUCCESS] All repository lint checks passed cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
