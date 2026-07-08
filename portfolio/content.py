from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .paths import Paths


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing context file: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_index_context(paths: Paths) -> dict[str, Any]:
    ctx = paths.context
    site = load_yaml(ctx / "site.yaml")
    personal = load_yaml(ctx / "personal_info.yaml")
    resume = load_yaml(ctx / "resume.yaml")
    narrative = load_yaml(ctx / "narrative.yaml")
    experiences = load_yaml(ctx / "experiences.yaml").get("experiences", [])
    toolchains = load_yaml(ctx / "toolchain_projects.yaml").get("projects", [])
    # Second spine of the backbone: self-built software / web / AI / desktop
    # products (DeckFlip, DecisionCanvas, etc.). Optional file so the build never
    # breaks if it's absent; an empty list just hides the section.
    software_path = ctx / "software_projects.yaml"
    software = load_yaml(software_path).get("projects", []) if software_path.exists() else []

    return {
        "site": site,
        "personal": personal,
        "resume": resume,
        "narrative": narrative,
        "experiences": experiences,
        "toolchains": toolchains,
        "software": software,
    }
