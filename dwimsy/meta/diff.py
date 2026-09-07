#!/usr/bin/env python3
"""dwimsy.meta.diff - Version-labeled unified diff engine comparing trees across streams."""

from __future__ import annotations

import argparse
import difflib
import io
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

for p in Path(__file__).resolve().parents:
    if (p / "dwimsy").is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
        break

from dwimsy.meta import integrity, unbundle
from dwimsy.meta.unbundle import safe_page, PagedHelpAction
from dwimsy.meta.versions import VersionSpace, VersionRef


def render_diff(
    root: Optional[Path] = None,
    v1_sel: Optional[str] = None,
    v2_sel: Optional[str] = None,
) -> str:
    """Return a version-labeled unified diff between versions or working tree."""
    cwd = Path.cwd().resolve()
    if root is not None:
        repo = Path(root).resolve()
    elif integrity.is_standalone_bundle():
        repo = None
    elif (cwd / "dwimsy" / "__init__.py").is_file():
        repo = cwd
    else:
        repo = integrity.find_repo_root(None)

    raw_b64 = unbundle._get_active_blztar()
    vspace = VersionSpace.from_blztar(raw_b64) if raw_b64 else VersionSpace()

    def _is_dir_target(target: Optional[str]) -> bool:
        if not target:
            return False
        if target in (".", "./"):
            return True
        try:
            p = Path(target)
            return p.is_dir() and (p / "dwimsy").is_dir()
        except Exception:
            return False

    if _is_dir_target(v1_sel) and v2_sel is None:
        target1 = "primary"
        target2 = v1_sel
    else:
        target1 = v1_sel or "baseline"
        target2 = v2_sel or "unbundled"

    def _resolve_target(
        target: str,
    ) -> Tuple[Dict[str, bytes], str, Optional[VersionSpace]]:
        if _is_dir_target(target):
            if target in (".", "./") and repo is not None:
                explicit_root = Path(repo).resolve()
            else:
                explicit_root = Path(target).resolve()
            is_checkout = (explicit_root / "dwimsy").is_dir() and (
                explicit_root / "dwimsy" / "__init__.py"
            ).is_file()
            if not is_checkout:
                raise ValueError(
                    f"Version selector '{target}' could not be resolved: directory is not a dwimsy checkout."
                )
            assets = integrity.canonical_assets(explicit_root, baseline=False)
            chk_ver = integrity.version(root=explicit_root)
            tag = f"dwimsy_{chk_ver}"

            vsp = None
            unb_data = assets.get("dwimsy/meta/unbundle.py")
            if unb_data:
                m = re.search(
                    r'blztar\s*=\s*"""([\s\S]*?)"""',
                    unb_data.decode("utf-8", errors="replace"),
                )
                if m and m.group(1).strip():
                    try:
                        vsp = VersionSpace.from_blztar(m.group(1).strip())
                    except Exception:
                        vsp = None
            if vsp is None:
                vsp = vspace
            return assets, tag, vsp

        if target == "unbundled":
            is_checkout = bool(
                repo
                and (repo / "dwimsy").is_dir()
                and (repo / "dwimsy" / "__init__.py").is_file()
            )
            if not is_checkout or (
                integrity.is_standalone_bundle()
                and (repo is None or "<dwimsy-bundle>" in str(repo))
            ):
                raise ValueError(
                    "Version selector 'unbundled' could not be resolved: standalone bundle does not implicitly compare with the current working directory.\n"
                    "To compare the portable bundle version with an on-disk checkout, explicitly specify the target:\n"
                    "  dwimsy meta diff primary .\n"
                    "  dwimsy meta diff [VERSION] /path/to/checkout\n"
                    "or explicitly import the checkout as an alternate stream with:\n"
                    "  --version-include-primary=. primary alt1"
                )
            assets = integrity.canonical_assets(repo, baseline=False)
            tag = f"dwimsy_{integrity.version(root=repo)}"
            return assets, tag, vspace
        elif target == "baseline":
            b_ref = vspace.resolve_version_ref("baseline")
            if b_ref is not None:
                s_b, ord_b, ref_b = b_ref
                assets = s_b.materialize_layer_state(ord_b)
                tag = f"dwimsy_{ref_b.tag}"
                from dwimsy.meta.versions import Stream

                vsp_b = VersionSpace(
                    [
                        Stream(
                            s_b.index,
                            s_b.name,
                            s_b.layers[: ord_b + 1],
                            source=s_b.source,
                        )
                    ]
                )
            else:
                assets = integrity.canonical_assets(repo, baseline=True)
                tag = f"dwimsy_{integrity._version_values(repo, baseline=True).get('__version__', '0.1.6.0')}"
                vsp_b = vspace
            return assets, tag, vsp_b
        elif target == "primary":
            p_ref = vspace.resolve_version_ref("primary")
            if p_ref is not None:
                s_p, ord_p, ref_p = p_ref
                assets = s_p.materialize_layer_state(ord_p)
                tag = f"dwimsy_{ref_p.tag}"
                from dwimsy.meta.versions import Stream

                vsp_p = VersionSpace(
                    [
                        Stream(
                            s_p.index,
                            s_p.name,
                            s_p.layers[: ord_p + 1],
                            source=s_p.source,
                        )
                    ]
                )
            else:
                assets = integrity.canonical_assets(repo, baseline=False)
                tag = f"dwimsy_{integrity._version_values(repo, baseline=False).get('__version__', '0.1.6.0')}"
                vsp_p = vspace
            return assets, tag, vsp_p
        else:
            res = vspace.resolve_version_ref(target)
            if res is None:
                raise ValueError(f"Version selector '{target}' could not be resolved.")
            s, ord_idx, ref = res
            assets = s.materialize_layer_state(ord_idx)
            stream_prefix = f"alt{s.index}_" if s.index > 0 else ""
            tag = f"dwimsy_{stream_prefix}{ref.tag}"
            from dwimsy.meta.versions import Stream

            streams_sliced = []
            for st_i in vspace.streams:
                if st_i.index == s.index:
                    streams_sliced.append(
                        Stream(
                            st_i.index,
                            st_i.name,
                            st_i.layers[: ord_idx + 1],
                            source=st_i.source,
                        )
                    )
                else:
                    # Slice other streams to matching semver if available, else full
                    streams_sliced.append(
                        Stream(
                            st_i.index, st_i.name, list(st_i.layers), source=st_i.source
                        )
                    )
            vsp_t = VersionSpace(streams_sliced)
            return assets, tag, vsp_t

    old_assets, v1_tag, vsp1 = _resolve_target(target1)
    new_assets, v2_tag, vsp2 = _resolve_target(target2)

    def _canonical_tree(assets: Dict[str, bytes]) -> Dict[str, bytes]:
        return {
            name: data
            for name, data in assets.items()
            if not (
                any(part == ".git" for part in Path(name).parts)
                or any(part == "__pycache__" for part in Path(name).parts)
                or name.endswith(".pyc")
            )
        }

    old_assets = _canonical_tree(old_assets)
    new_assets = _canonical_tree(new_assets)

    lines: List[str] = []
    all_files = sorted(set(old_assets) | set(new_assets))

    for name in all_files:
        a = old_assets.get(name)
        b = new_assets.get(name)

        def _format_file_bytes(
            data: Optional[bytes], side_vspace: Optional[VersionSpace]
        ) -> Optional[bytes]:
            if data is None:
                return None
            if not name.endswith("unbundle.py"):
                return integrity._canonical_bytes(data, name)
            text = (
                data.replace(b"\r\n", b"\n")
                .replace(b"\r", b"\n")
                .decode("utf-8", errors="replace")
            )
            m = re.search(r'blztar\s*=\s*"""([\s\S]*?)"""', text)
            if not m:
                return integrity._canonical_bytes(data, name)
            summary = (
                side_vspace.format_list_versions(on_disk_root=None, selected=None)
                if side_vspace is not None
                else vspace.format_list_versions(on_disk_root=None, selected=None)
            )
            ph = (
                'blztar = """\n'
                "<- actual omitted base64 lzma tar sequence(s) would start here\n\n"
                "$VERSION_SUMMARY\n" + summary + "\n\n"
                "actual omitted base64 lzma tar sequence(s) would end here ->\n"
                '"""'
            )
            res_text = text[: m.start()] + ph + text[m.end() :]
            if not res_text.endswith("\n"):
                res_text += "\n"
            return res_text.encode("utf-8")

        old_bytes = _format_file_bytes(a, vsp1)
        new_bytes = _format_file_bytes(b, vsp2)

        if old_bytes == new_bytes:
            continue

        if old_bytes is None:
            old_lines = []
            old_label = "/dev/null"
        else:
            old_lines = old_bytes.decode("utf-8", errors="replace").splitlines(True)
            old_label = f"{v1_tag}/{name}"

        if new_bytes is None:
            new_lines = []
            new_label = "/dev/null"
        else:
            new_lines = new_bytes.decode("utf-8", errors="replace").splitlines(True)
            new_label = f"{v2_tag}/{name}"

        diff = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=old_label,
                tofile=new_label,
            )
        )
        if diff:
            lines.append(f"diff --git {old_label} {new_label}\n")
            lines.extend(diff)

    return "".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for running dwimsy.meta.diff directly."""
    effective = sys.argv[1:] if argv is None else list(argv)
    from dwimsy.cli.dispatch import early_dispatch

    handled, effective = early_dispatch(
        effective, ["meta", "diff"], use_process_argv0=(argv is None)
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

        pattern = (
            [test_arg.split("=", 1)[1]]
            if test_arg.startswith("--test=")
            else ["meta diff"]
        )
        return run_tests(pattern, verbose=verbosity)

    if any(a == "--help-all" for a in effective):
        effective = ["-h" if a == "--help-all" else a for a in effective]

    from dwimsy.meta.integrity import version as get_version

    parser = argparse.ArgumentParser(
        prog="dwimsy-diff",
        description="Version-labeled unified diff engine.",
        add_help=False,
    )
    parser.add_argument(
        "-h",
        "--help",
        action=PagedHelpAction,
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
        help="Run scoped diff self-tests in-process (optional pattern filter)",
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
    parser.add_argument("-r", "--root", default=None, help="Target repository root")
    parser.add_argument(
        "versions",
        nargs="*",
        default=[],
        help="Optional version tags or selectors to compare (e.g. [VER1] [VER2])",
    )
    args = parser.parse_args(effective)

    if args.test is not False:
        from dwimsy.tests import run_tests

        pattern = [args.test] if isinstance(args.test, str) else ["meta diff"]
        return run_tests(pattern, verbose=max(args.verbose, 1))

    v1 = args.versions[0] if len(args.versions) > 0 else None
    v2 = args.versions[1] if len(args.versions) > 1 else None

    try:
        diff_text = render_diff(root=getattr(args, "root", None), v1_sel=v1, v2_sel=v2)
        safe_page(diff_text)
        return 0
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
