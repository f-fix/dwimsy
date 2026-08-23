#!/usr/bin/env python3

import sys
from pathlib import Path

# Ensure the package root is on sys.path when invoked via `python3 dwimsy`
pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from dwimsy.cli.main import main

if __name__ == "__main__":
    main()
