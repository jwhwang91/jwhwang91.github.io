#!/usr/bin/env python3
"""Privacy guard for the public jwhwang91.github.io repository.

Fails (exit 1) when a private or sensitive artifact would be exposed in the
public git tree. It checks three things:

  1. No file under a private path is tracked or staged
     (_source_references/, dist/, __pycache__/, .idea/, Context/private/,
     Applications/), and no *.pyc file is tracked/staged.
  2. The owner's private phone number does not appear in tracked/staged public
     content.
  3. No Applications/ file is tracked (covered by rule 1's Applications/ prefix).

Usage:
    python scripts/privacy_guard.py            # scan the tracked tree (CI use)
    python scripts/privacy_guard.py --staged   # also scan staged additions (pre-commit)

The guard scans the union of `git ls-files` (tracked) and, with --staged, the
staged additions/modifications (`git diff --cached --diff-filter=ACM`).
Deletions never fail the guard, so `git rm -r --cached <private path>` is the
correct way to remediate an already-tracked private path.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import re

# Paths that must never appear in the public tree. A tracked/staged file whose
# path starts with any of these prefixes is a violation.
FORBIDDEN_PREFIXES = (
    "_source_references/",
    "dist/",
    "__pycache__/",
    ".idea/",
    "Context/private/",
    "Applications/",
)

# The sensitive number is reconstructed from fragments so this guard file does
# not itself contain the contiguous string it searches for.
_NN1, _NN2 = "5775", "1863"
PHONE_RE = re.compile(rf"\+?82[-\s.]?0?10[-\s.]?{_NN1}[-\s.]?{_NN2}")

# Excluded from the *content* scan only (never from the path scan): this guard
# holds the number fragments above, and the private YAML legitimately holds the
# number but is gitignored so it is never tracked/staged anyway.
CONTENT_SCAN_SKIP = {
    "scripts/privacy_guard.py",
    ".githooks/pre-commit",
    "Context/private/personal_private.yaml",
}

# Binary / asset extensions we do not scan for the phone string.
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".pptx", ".ico",
    ".woff", ".woff2", ".ttf", ".otf", ".zip", ".pyc",
}


def _git(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _candidate_files(check_staged: bool) -> list[str]:
    files = set(_git(["ls-files"]))
    if check_staged:
        files.update(_git(["diff", "--cached", "--name-only", "--diff-filter=ACM"]))
    return sorted(files)


def _read(path: str) -> str | None:
    p = Path(path)
    if p.exists():
        try:
            return p.read_text(encoding="utf-8", errors="ignore")
        except (OSError, ValueError):
            return None
    # Staged but not on disk: read the staged blob.
    blob = subprocess.run(
        ["git", "show", f":{path}"], capture_output=True, text=True, check=False
    )
    return blob.stdout if blob.returncode == 0 else None


def main(argv: list[str]) -> int:
    check_staged = "--staged" in argv
    candidates = _candidate_files(check_staged)
    violations: list[str] = []

    # 1) forbidden-path / Applications / *.pyc check
    for f in candidates:
        if f.endswith(".pyc") or any(f.startswith(p) for p in FORBIDDEN_PREFIXES):
            violations.append(f"private path tracked/staged: {f}")

    # 2) phone-number content scan
    for f in candidates:
        if f in CONTENT_SCAN_SKIP or Path(f).suffix.lower() in BINARY_EXTS:
            continue
        text = _read(f)
        if text and PHONE_RE.search(text):
            violations.append(f"private phone number found in tracked/staged content: {f}")

    if violations:
        sys.stderr.write("PRIVACY GUARD FAILED — refusing to expose private data:\n")
        for v in violations:
            sys.stderr.write(f"  - {v}\n")
        sys.stderr.write(
            "\nRemediation:\n"
            "  * `git rm -r --cached <path>` to untrack a private path (keeps it on disk)\n"
            "  * move private contact data into Context/private/ (gitignored)\n"
            "  * unstage any file that still contains the phone number, then re-stage\n"
        )
        return 1

    scope = "tracked+staged" if check_staged else "tracked"
    print(f"privacy guard OK — scanned {len(candidates)} {scope} files, no exposure found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
