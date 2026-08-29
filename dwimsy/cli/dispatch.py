"""dwimsy.cli.dispatch - universal early CLI dispatch."""

from __future__ import annotations
import sys
from typing import List, Optional, Tuple

UNIVERSAL_HELP = "Universal options: -a/--argv0 NAME, --version=TAG, --version-list, --version-include*=SRC, --version-restrict-to=PATTERN, --version-prune=PATTERN, --version-splice=SPEC, --version-alt[=TAG], and --version-help are processed left-to-right before command-specific options."


def early_dispatch(
    argv: List[str], current_command: List[str], *, use_process_argv0: bool
) -> Tuple[bool, List[str]]:
    from dwimsy.meta.unbundle import (
        parse_early_pipeline_flags,
        resolve_argv0_command,
        get_invocation_path,
        VERSION_SPACE_HELP,
    )

    pipeline, remaining = parse_early_pipeline_flags(list(argv))
    raw_argv0 = pipeline["argv0"] or (
        sys.argv[0] if use_process_argv0 and sys.argv else "dwimsy"
    )
    argv0 = get_invocation_path(raw_argv0) if raw_argv0 else ""
    target = resolve_argv0_command(argv0)

    if pipeline.get("print_version"):
        from dwimsy.meta.integrity import version as get_version

        snapshot = (
            pipeline["effective_version"] if pipeline.get("version") else get_version()
        )
        prog = (
            f"dwimsy-{current_command[0]}"
            if current_command and current_command[0] not in ("dwimsy", "meta")
            else (
                "dwimsy meta"
                if current_command and current_command[0] == "meta"
                else "dwimsy"
            )
        )
        print(f"{prog} {snapshot}")
        return True, remaining

    if pipeline.get("early_exit") == "version-help":
        print(VERSION_SPACE_HELP)
        return True, remaining

    if pipeline.get("early_exit") == "version-list":
        from dwimsy.meta.unbundle import detect_self_location

        is_chk, r_root = detect_self_location(argv0)
        output = pipeline["version_list_snapshot"] or pipeline[
            "vspace"
        ].format_list_versions(
            on_disk_root=r_root if is_chk else None, selected=pipeline["selected_ref"]
        )
        print(output)
        return True, remaining

    if pipeline.get("test_mode"):
        from dwimsy.tests import run_tests

        pattern = (
            [pipeline["test_pattern"]]
            if pipeline.get("test_pattern")
            else current_command
        )
        test_verbose = max(
            1,
            1
            + pipeline.get("short_v_count", 0)
            + pipeline.get("explicit_verbose_count", 0),
        )
        rc = run_tests(pattern, verbose=test_verbose)
        sys.exit(rc)

    pipeline_only = bool(
        pipeline.get("argv0_overridden")
        or pipeline["include"]
        or pipeline["restrict_to"]
        or pipeline["prune"]
        or pipeline["splice"]
        or pipeline["alt"][0]
        or pipeline["version"] is not None
    )
    if pipeline_only:
        from dwimsy.meta import unbundle

        unbundle.bootstrap_in_memory_cli(list(argv))
        return True, remaining
    if target and target[0] != current_command[0]:
        from dwimsy.cli.__main__ import main as cli_main

        cli_main(list(target) + remaining)
        return True, remaining
    return False, remaining
