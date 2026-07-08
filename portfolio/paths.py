from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    """Resolved filesystem layout for one build.

    Replaces the module-level path globals the generator used to carry, so the
    whole pipeline can run against a temporary directory (tests, tmp builds)
    without monkeypatching. Build one with :meth:`from_root`, or derive a
    dir-scoped variant with ``dataclasses.replace(default_paths(), dist=...)``.
    """

    root: Path
    context: Path
    format_dir: Path
    templates: Path
    style: Path
    dist: Path
    variants: Path
    applications: Path
    scaffold: Path
    private: Path

    @classmethod
    def from_root(cls, root: Path) -> "Paths":
        root = Path(root).resolve()
        context = root / "Context"
        format_dir = root / "Format"
        return cls(
            root=root,
            context=context,
            format_dir=format_dir,
            templates=format_dir / "templates",
            style=root / "Style",
            dist=root / "dist",
            variants=context / "variants",
            applications=root / "Applications",
            scaffold=format_dir / "scaffold",
            private=context / "private",
        )


# The repo root is the directory that contains this ``portfolio/`` package.
REPO_ROOT = Path(__file__).resolve().parent.parent


def default_paths() -> Paths:
    """Paths for the real repository checkout."""
    return Paths.from_root(REPO_ROOT)


def rel_to_root(path: Path, root: Path) -> Path:
    """``path`` relative to ``root`` for display; falls back to the absolute path
    when ``path`` is outside ``root`` (e.g. a tmp-scoped build under test)."""
    try:
        return path.relative_to(root)
    except ValueError:
        return path
