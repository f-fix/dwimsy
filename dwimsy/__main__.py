#!/usr/bin/env python3
"""dwimsy.__main__ - Top-level CLI entrypoint for running dwimsy via python3 -m dwimsy."""

from __future__ import annotations

import sys
from pathlib import Path

pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.cli import main

if __name__ == "__main__":
    sys.exit(main())
