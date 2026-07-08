from __future__ import annotations

import argparse
from typing import Optional, Sequence

from .applications import (jd_confirm, jd_parse, match, match_confirm,
                           new_application, validate_stage)
from .facts import sweep_site_consistency, validate_registry
from .paths import Paths, default_paths, rel_to_root
from .site import build
from .tracking import print_insights
from .variants import build_all_variants, build_variant, list_variants, scaffold_variant


def build_parser() -> argparse.ArgumentParser:
    # allow_abbrev=False: with --lint-facts alongside --list-variants, prefix
    # abbreviations like --li would be ambiguous — require full flag names.
    parser = argparse.ArgumentParser(description="Build the resume/portfolio site.", allow_abbrev=False)
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
    parser.add_argument(
        "--lint-facts",
        action="store_true",
        help="Validate Context/facts/** (schema + verbatim source quotes + references) and "
             "sweep Context/*.yaml for drift against employers.yaml (warn-level). Exits 1 on errors.",
    )

    # New JD-pipeline subcommands (legacy flags above stay working unchanged).
    sub = parser.add_subparsers(dest="command")

    p_new = sub.add_parser("new", help="Scaffold a new application (application.yaml + jd.txt + notes.md).")
    p_new.add_argument("slug")
    p_new.add_argument("--company", default="")
    p_new.add_argument("--role", default="")
    p_new.add_argument("--url", default="")
    p_new.add_argument("--positioning", default="")

    p_jd = sub.add_parser("jd", help="JD parsing (deterministic scan + LLM parse confirmation).")
    jd_sub = p_jd.add_subparsers(dest="jd_command")
    jd_sub.add_parser("parse", help="Deterministic scan + assemble the LLM prompt.").add_argument("slug")
    jd_sub.add_parser("confirm", help="Gate G1: validate + stamp jd.parsed.yaml, advance status.").add_argument("slug")

    p_match = sub.add_parser("match", help="Classify JD keywords vs the registry. Usage: match <slug> | match confirm <slug>")
    p_match.add_argument("args", nargs="+")

    p_validate = sub.add_parser("validate", help="Validate a stage artifact (schema + registry refs).")
    p_validate.add_argument("slug")
    p_validate.add_argument("--stage", default="all", choices=["jd", "match", "all"])

    return parser


def _run_subcommand(paths: Paths, args: argparse.Namespace) -> Optional[int]:
    """Dispatch the argparse subcommands; returns None if no subcommand was given."""
    command = getattr(args, "command", None)
    if command == "new":
        folder = new_application(paths, args.slug, args.company, args.role, args.url, args.positioning)
        print(f"Scaffolded application: {rel_to_root(folder, paths.root)}")
        print(f"  1. Paste the JD into {rel_to_root(folder / 'jd.txt', paths.root)}")
        print(f"  2. python main.py jd parse {args.slug}")
        return 0
    if command == "jd":
        if getattr(args, "jd_command", None) == "parse":
            return jd_parse(paths, args.slug)
        if getattr(args, "jd_command", None) == "confirm":
            return jd_confirm(paths, args.slug)
        print("usage: python main.py jd {parse|confirm} <slug>")
        return 2
    if command == "match":
        a = args.args
        if len(a) == 2 and a[0] == "confirm":
            return match_confirm(paths, a[1])
        if len(a) == 1 and a[0] != "confirm":
            return match(paths, a[0])
        print("usage: python main.py match <slug> | match confirm <slug>")
        return 2
    if command == "validate":
        return validate_stage(paths, args.slug, args.stage)
    return None


def _lint_facts(paths: Paths) -> int:
    violations = validate_registry(paths) + sweep_site_consistency(paths)
    errors = [x for x in violations if x.level == "error"]
    warnings = [x for x in violations if x.level == "warning"]
    for x in errors:
        print(x)
    for x in warnings:
        print(x)
    print(f"\nlint-facts: {len(errors)} error(s), {len(warnings)} warning(s).")
    if errors:
        print("FAILED — fix the errors above.")
        return 1
    print("OK — registry is structurally sound (warnings are advisory / Gate G0 items).")
    return 0


def main(argv: Optional[Sequence[str]] = None, paths: Optional[Paths] = None) -> Optional[int]:
    """Entry point for `python main.py` and the tests. `paths` is injectable so the
    whole CLI can run against a tmp dir without touching the real repo dist/.
    Returns an int exit code for gating commands (lint-facts), else None."""
    paths = paths or default_paths()
    args = build_parser().parse_args(argv)

    sub_result = _run_subcommand(paths, args)
    if sub_result is not None or getattr(args, "command", None):
        return sub_result

    if args.lint_facts:
        return _lint_facts(paths)
    elif args.new_variant:
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
