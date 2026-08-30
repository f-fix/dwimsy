#!/usr/bin/env python3
"""dwimsy.meta.lint - Repository hygiene and style invariant validator."""

from __future__ import annotations

import argparse
import ast
import re
import sys
import unicodedata
from pathlib import Path
from typing import List, Optional

for p in Path(__file__).resolve().parents:
    if (p / "dwimsy").is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
        break

from dwimsy.meta import integrity, versions
from dwimsy.meta.bundle import GitIgnoreMatcher

_UNBUNDLE_RE = re.compile(
    rb"(?ms)^[ \t]*blztar[ \t]*=[ \t]*\"\"\"(?:.*?)\"\"\"[ \t]*(?:#.*)?$"
)


def derive_module_name(rel_path: Path) -> str:
    parts = list(rel_path.parts)
    if not parts:
        return ""
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def expected_docstring_identity(path: Path) -> str | None:
    """Return the expected module identity, with the narrow relocatable unbundle carve-out."""
    p = Path(path).resolve()

    # Derive the ordinary expected identity from the path first.  This is also
    # the fallback for relocated/corrupted copies and therefore cannot be
    # weakened by the unbundle exception.
    repo_root = integrity.find_repo_root(p)
    if repo_root is not None and repo_root.is_dir():
        try:
            rel = p.relative_to(repo_root)
            ordinary = derive_module_name(rel)
        except ValueError:
            ordinary = derive_module_name(Path(p.name))
    elif "dwimsy" in p.parts:
        idx = max(i for i, part in enumerate(p.parts) if part == "dwimsy")
        ordinary = derive_module_name(Path(*p.parts[idx:]))
    elif "tests" in p.parts:
        idx = max(i for i, part in enumerate(p.parts) if part == "tests")
        ordinary = derive_module_name(Path(*p.parts[idx:]))
    else:
        ordinary = derive_module_name(Path(p.name))

    try:
        data = p.read_bytes()
        doc = ""
        if p.suffix == ".pyc":
            # A relocated pyc has no useful filesystem package context.  Read
            # the code object directly from the pyc payload instead of asking
            # an import loader to interpret its stale filename.
            import marshal

            if len(data) >= 16:
                co = marshal.loads(data[16:])
                if getattr(co, "co_consts", None) and isinstance(co.co_consts[0], str):
                    doc = co.co_consts[0]
        else:
            import ast

            tree = ast.parse(data.decode("utf-8"), filename=str(p))
            doc = ast.get_docstring(tree, clean=False) or ""

        first = doc.splitlines()[0] if doc else ""
        if first.startswith("dwimsy.meta.unbundle -") and (
            b'blztar = """' in data or (p.suffix == ".pyc" and b"blztar" in data)
        ):
            return "dwimsy.meta.unbundle"
    except Exception:
        pass

    return ordinary


def lint_headers(repo_root: Optional[Path] = None) -> List[str]:
    """Verify source file shebangs, docstrings, and forbidden quote syntax."""
    root = integrity.find_repo_root(repo_root)
    py_files = sorted(
        [
            p
            for p in root.rglob("*.py")
            if not (
                p.as_posix().startswith("deps/")
                or "/deps/" in p.as_posix()
                or "<dwimsy-bundle>/deps/" in p.as_posix()
            )
            and not (
                p.name.startswith("dwimsy_")
                and (p.name.endswith(".py") or p.name.endswith(".pyz"))
            )
            and not (
                p.name.startswith("dwimsy_")
                and (p.name.endswith(".py") or p.name.endswith(".pyz"))
            )
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
            'if __name__ == "__main__":' in text or "if __name__ == '__main__':" in text
        )

        first_line = lines[0]
        shebang_present = first_line.startswith("#!")
        if has_main and not shebang_present:
            errors.append(f"{rel}: missing executable shebang line")
        elif not has_main and shebang_present:
            errors.append(f"{rel}: unexpected shebang in non-main module")

        doc_idx = 1 if shebang_present else 0
        if doc_idx >= len(lines):
            errors.append(f"{rel}: missing module docstring")
            continue

        doc_line = lines[doc_idx]
        if not doc_line.startswith('"""'):
            errors.append(
                f"{rel}: line {doc_idx + 1} does not start with triple double-quotes"
            )
            continue

        expected_prefix = expected_docstring_identity(p)
        if expected_prefix:
            prefix = f'"""{expected_prefix} - '
            if not doc_line.startswith(prefix):
                errors.append(
                    f"{rel}: docstring should start with '{prefix}', found '{doc_line[:40]}...'"
                )

    return errors


def lint_filenames(repo_root: Optional[Path] = None) -> List[str]:
    """Verify Unicode NFKC filename portability, character sets, and naming conventions."""
    root = integrity.find_repo_root(repo_root)
    errors: List[str] = []
    seen_keys: dict[str, Path] = {}
    gitignore = GitIgnoreMatcher(root)

    for p in sorted(root.rglob("*")):
        if ".git" in p.parts or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(root)
        rel_posix = rel.as_posix()
        if rel_posix.startswith("deps/") or rel_posix == "deps":
            continue
        if gitignore.matches(rel_posix, is_dir=p.is_dir()):
            continue

        key = versions.collision_key(rel_posix)
        if key in seen_keys:
            errors.append(
                f"Filename collision (NFKC casefold): '{rel_posix}' collides with '{seen_keys[key].as_posix()}'"
            )
        else:
            seen_keys[key] = rel

        for part in rel.parts:
            if not re.match(r"^\.?[0-9A-Za-z._+-]+$", part):
                errors.append(
                    f"Invalid characters in path component '{part}' of '{rel_posix}'"
                )

        if p.is_file() and p.suffix == ".py":
            if rel.parts[0] in ("dwimsy", "tests") and not rel.name.startswith(
                "dwimsy_"
            ):
                if not re.match(r"^[a-z0-9_]+\.py$", p.name):
                    errors.append(
                        f"Python source file '{rel_posix}' must be lowercase snake_case.py"
                    )

    return errors


def lint_markdown(repo_root: Optional[Path] = None) -> List[str]:
    """Verify markdown documentation formatting and rules."""
    root = integrity.find_repo_root(repo_root)
    md_files = sorted(
        [
            p
            for p in root.rglob("*.md")
            if not (
                p.as_posix().startswith("deps/")
                or "/deps/" in p.as_posix()
                or "<dwimsy-bundle>/deps/" in p.as_posix()
            )
            and not (
                p.name.startswith("dwimsy_")
                and (p.name.endswith(".py") or p.name.endswith(".pyz"))
            )
        ]
    )
    errors: List[str] = []

    for p in md_files:
        rel = p.relative_to(root)
        text = p.read_text(encoding="utf-8")

        if "\u2014" in text or "\u2013" in text:
            errors.append(f"{rel}: contains forbidden Unicode em/en dashes")
        if "\n\n\n\n" in text:
            errors.append(f"{rel}: contains more than three consecutive newlines")

        lines = text.splitlines()
        for idx, line in enumerate(lines, start=1):
            if line.rstrip() != line:
                errors.append(f"{rel}:{idx}: trailing whitespace")
            if "\t" in line:
                errors.append(f"{rel}:{idx}: contains tab character")

    return errors


def lint_duplicates(repo_root: Optional[Path] = None) -> List[str]:
    """Verify that non-deps Python files do not contain duplicate function, async function, class, or method definitions."""
    root = integrity.find_repo_root(repo_root)
    py_files = sorted(
        [
            p
            for p in root.rglob("*.py")
            if not (
                p.as_posix().startswith("deps/")
                or "/deps/" in p.as_posix()
                or "<dwimsy-bundle>/deps/" in p.as_posix()
            )
            and not (
                p.name.startswith("dwimsy_")
                and (p.name.endswith(".py") or p.name.endswith(".pyz"))
            )
        ]
    )
    errors: List[str] = []

    class _DuplicateVisitor(ast.NodeVisitor):
        def __init__(self, rel_path: str):
            self.rel_path = rel_path
            self.scopes = [{}]
            self.dups: List[str] = []

        def _check_and_register(self, name: str, lineno: int, kind: str):
            current_scope = self.scopes[-1]
            if name in current_scope:
                prev_lineno = current_scope[name]
                self.dups.append(
                    f"{self.rel_path}:{lineno}: duplicate {kind} '{name}' (previously defined on line {prev_lineno})"
                )
            else:
                current_scope[name] = lineno

        def visit_FunctionDef(self, node: ast.FunctionDef):
            self._check_and_register(node.name, node.lineno, "function/method")
            self.scopes.append({})
            self.generic_visit(node)
            self.scopes.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            self._check_and_register(node.name, node.lineno, "async function/method")
            self.scopes.append({})
            self.generic_visit(node)
            self.scopes.pop()

        def visit_ClassDef(self, node: ast.ClassDef):
            self._check_and_register(node.name, node.lineno, "class")
            self.scopes.append({})
            self.generic_visit(node)
            self.scopes.pop()

    for p in py_files:
        rel = p.relative_to(root).as_posix()
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"), filename=rel)
            visitor = _DuplicateVisitor(rel)
            visitor.visit(tree)
            errors.extend(visitor.dups)
        except Exception as exc:
            errors.append(f"{rel}: failed to parse AST: {exc}")

    return errors


def run_all_lints(repo_root: Optional[Path] = None) -> List[str]:
    """Run all repository lint checks and return combined list of errors."""
    return (
        lint_headers(repo_root)
        + lint_markdown(repo_root)
        + lint_filenames(repo_root)
        + lint_duplicates(repo_root)
    )


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for running dwimsy.meta.lint directly."""
    import argparse

    effective = sys.argv[1:] if argv is None else list(argv)
    from dwimsy.cli.dispatch import early_dispatch

    handled, effective = early_dispatch(
        effective, ["meta", "lint"], use_process_argv0=(argv is None)
    )
    if handled:
        return 0
    from dwimsy.cli.dispatch import early_dispatch

    handled, effective = early_dispatch(
        effective, ["meta", "lint"], use_process_argv0=(argv is None)
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
            pattern = ["meta lint"]
        return run_tests(pattern, verbose=verbosity)

    if any(a == "--help-all" for a in effective):
        effective = ["-h" if a == "--help-all" else a for a in effective]

    from dwimsy.meta.integrity import version as get_version

    parser = argparse.ArgumentParser(
        prog="dwimsy-lint",
        description="Verify repository hygiene, docstrings, headers, and filename portability.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
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
    args = parser.parse_args(effective)

    if args.test is not False:
        from dwimsy.tests import run_tests

        pattern = [args.test] if isinstance(args.test, str) else ["meta lint"]
        return run_tests(pattern, verbose=max(args.verbose, 1))

    all_errors = run_all_lints()
    if all_errors:
        for err in all_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    if args.verbose:
        print("All repository lint checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
