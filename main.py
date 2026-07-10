#!/usr/bin/env python3
"""Thin entry-point shim — all logic lives in the ``portfolio/`` package.

Every legacy flag is unchanged and handled by :func:`portfolio.cli.main`:

    python main.py                    build the public site into dist/
    python main.py --variant NAME     build one job-tailored resume
    python main.py --new-variant NAME scaffold Applications/NAME/
    python main.py --list-variants    list variants that have an overlay
    python main.py --all-variants     build every variant
    python main.py --insights         outcome scoreboard from Applications/*/result.md
    python main.py ui                 launch the local JobOps web app + open the browser
                                      (--headless drives Claude for LLM steps; --port / --no-open)
"""
from __future__ import annotations

import sys

from portfolio.cli import main

if __name__ == "__main__":
    # main() raises on user error (so tests can assert the exception) and returns an
    # exit code for gating commands; the shim turns both into a clean CLI outcome.
    try:
        raise SystemExit(main())
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
