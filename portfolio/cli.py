from __future__ import annotations

import argparse
from typing import Optional, Sequence

from .paths import Paths, default_paths, rel_to_root
from .site import build
from .tracking import print_insights
from .variants import build_all_variants, build_variant, list_variants, scaffold_variant


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the resume/portfolio site.")
    parser.add_argument(
        "--variant",
        metavar="NAME",
        help="Build one job-tailored resume into Applications/NAME/resume.html "
             '(e.g. --variant "Tesla 1").',
    )
    parser.add_argument(
        "--all-variants",
        action="store_true",
        help="Build every application under Applications/ (plus flat Context/variants/*.yaml lenses).",
    )
    parser.add_argument(
        "--new-variant",
        metavar="NAME",
        help="Scaffold Applications/NAME/ (jd.txt, overlay.yaml, notes.md, result.md), then stop.",
    )
    parser.add_argument(
        "--list-variants",
        action="store_true",
        help="List variants that have an overlay.",
    )
    parser.add_argument(
        "--insights",
        action="store_true",
        help="Scoreboard from Applications/*/result.md: ATS pass-through + which apps were "
             "knocked out before a human read them. Feeds the evolving ATS playbook.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None, paths: Optional[Paths] = None) -> None:
    """Entry point for `python main.py` and the tests. `paths` is injectable so the
    whole CLI can run against a tmp dir without touching the real repo dist/."""
    paths = paths or default_paths()
    args = build_parser().parse_args(argv)

    if args.new_variant:
        folder = scaffold_variant(paths, args.new_variant)
        print(f"Scaffolded variant: {rel_to_root(folder, paths.root)}")
        print(f"  1. Paste the JD into {rel_to_root(folder / 'jd.txt', paths.root)}")
        print("  2. Ask Claude to analyze it and propose the overlay.")
        print(f'  3. Review, then build:  python main.py --variant "{args.new_variant}"')
    elif args.list_variants:
        names = list_variants(paths)
        if not names:
            print('No variants yet. Create one with --new-variant "<name>".')
        else:
            print("Variants:")
            for name in names:
                built = (paths.applications / name / "resume.html").exists()
                print(f"  - {name}{'  (built)' if built else ''}")
    elif args.insights:
        print_insights(paths)
    elif args.all_variants:
        build_all_variants(paths)
    elif args.variant:
        build_variant(paths, args.variant)
    else:
        build(paths)
