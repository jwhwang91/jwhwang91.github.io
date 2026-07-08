#!/usr/bin/env python3
"""Thin entry-point shim — all logic lives in the ``portfolio/`` package.

Every legacy flag is unchanged and handled by :func:`portfolio.cli.main`:

    python main.py                    build the public site into dist/
    python main.py --variant NAME     build one job-tailored resume
    python main.py --new-variant NAME scaffold Applications/NAME/
    python main.py --list-variants    list variants that have an overlay
    python main.py --all-variants     build every variant
    python main.py --insights         outcome scoreboard from Applications/*/result.md
"""
from __future__ import annotations

from portfolio.cli import main

if __name__ == "__main__":
    main()
