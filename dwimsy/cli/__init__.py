"""dwimsy.cli - Command-line interfaces and streaming filters."""

from __future__ import annotations


def main(argv=None):
    from dwimsy.cli.__main__ import main as _main

    return _main(argv)


__all__ = ["main"]
