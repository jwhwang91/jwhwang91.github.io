from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from jinja2 import Environment

from .content import load_index_context, load_yaml
from .paths import Paths, rel_to_root
from .site import load_site_js, make_env

# ---------------------------------------------------------------------------
# Per-job-description variants — the regulated loop
#
# A variant is a thin "lens" over the backbone (Context/*.yaml): it ONLY lists
# overrides; anything omitted is inherited. The default build (`python main.py`)
# is unchanged and never builds variants, so the public site is always the
# backbone. A variant renders a LEAN, self-contained resume to
# Applications/<name>/resume.html — case-study links point to the live portfolio,
# so deep case studies live there and are never bundled into each resume.
#
# Two source layouts are supported:
#   Applications/<name>/overlay.yaml   (per-application folder — also holds jd.txt,
#                                        notes.md, result.md, and the rendered
#                                        resume.html; the "regulated loop")
#   Context/variants/<name>.yaml       (flat lens, e.g. a reusable field focus)
#
# Scaffold templates live as files under Format/scaffold/ (jd.txt, overlay.yaml,
# notes.md, result.md); scaffold_variant substitutes the literal "{name}" token.
# ---------------------------------------------------------------------------

_SCAFFOLD_FILES = ("jd.txt", "overlay.yaml", "notes.md", "result.md")


def _read_scaffold(paths: Paths, filename: str) -> str:
    path = paths.scaffold / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing scaffold template: {path}")
    return path.read_text(encoding="utf-8")


def variant_source(paths: Paths, name: str) -> Path | None:
    """Resolve a variant name to its overlay file.

    Per-application folder preferred (Applications/<name>/overlay.yaml — source and
    output now live together there), then a flat reusable lens
    (Context/variants/<name>.yaml).
    """
    folder = paths.applications / name / "overlay.yaml"
    if folder.exists():
        return folder
    flat = paths.variants / f"{name}.yaml"
    if flat.exists():
        return flat
    return None


def load_variant(paths: Paths, name: str) -> dict[str, Any]:
    src = variant_source(paths, name)
    if src is None:
        raise FileNotFoundError(
            f"No variant '{name}' found under {paths.applications / name / 'overlay.yaml'} "
            f"or {paths.variants / (name + '.yaml')}.\n"
            f"Scaffold it first:  python main.py --new-variant \"{name}\""
        )
    variant = load_yaml(src)
    variant.setdefault("id", name)
    return variant


def _check_ids(ids: list[Any], known: list[Any], section: str, field: str) -> None:
    """Fail loudly on a typo'd id, with a nearest-match suggestion (fixes the old
    silent-drop of misspelled include:/overrides: entries)."""
    known_str = [str(k) for k in known]
    for i in ids:
        if i not in known:
            hint = difflib.get_close_matches(str(i), known_str, n=1)
            suggestion = f" Did you mean '{hint[0]}'?" if hint else ""
            where = f"'{section}' " if section else ""
            raise ValueError(
                f"Unknown id '{i}' in {where}{field}:.{suggestion} "
                f"Known ids: {', '.join(known_str) or '(none)'}."
            )


def select_and_override(
    items: list[dict[str, Any]], cfg: dict[str, Any] | None, section: str = ""
) -> list[dict[str, Any]]:
    """Filter/reorder a list of id'd dicts by cfg['include'] and apply cfg['overrides']."""
    cfg = cfg or {}
    by_id = {item.get("id"): item for item in items}
    known = [k for k in by_id if k is not None]
    include = cfg.get("include")
    # `include` omitted (None) -> keep all in backbone order. An explicit empty
    # list (`include: []`) means "show none" -> hide the section (e.g. a pure-
    # controls variant hides the software spine). Don't conflate the two.
    if include is None:
        selected = list(items)
    else:
        _check_ids(include, known, section, "include")
        selected = [by_id[i] for i in include]
    overrides = cfg.get("overrides") or {}
    if overrides:
        _check_ids(list(overrides), known, section, "overrides")
    return [{**item, **overrides.get(item.get("id"), {})} for item in selected]


def apply_variant(context: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    if variant.get("site"):
        context["site"] = {**context["site"], **variant["site"]}
    if variant.get("resume"):
        context["resume"] = {**context["resume"], **variant["resume"]}
    context["experiences"] = select_and_override(context["experiences"], variant.get("experiences"), "experiences")
    context["toolchains"] = select_and_override(context["toolchains"], variant.get("toolchains"), "toolchains")
    context["software"] = select_and_override(context.get("software", []), variant.get("software"), "software")
    context["noindex"] = variant.get("noindex", True)
    return context


def render_application(paths: Paths, env: Environment, name: str) -> Path:
    """Render a lean, self-contained resume for one application to Applications/<name>/."""
    context = apply_variant(load_index_context(paths), load_variant(paths, name))
    portfolio = (context["personal"].get("portfolio") or {}).get("url", "").rstrip("/")
    link_base = f"{portfolio}/" if portfolio else ""

    context.update(
        inline_css=(paths.style / "theme.css").read_text(encoding="utf-8"),
        inline_js=load_site_js(paths),
        link_base=link_base,            # case-study links -> live portfolio
        home_path=portfolio or "index.html",
        variant_mode=True,
    )
    html = env.get_template("index.html.j2").render(**context)

    out_dir = paths.applications / name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "resume.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def list_variants(paths: Paths) -> list[str]:
    names = set()
    if paths.applications.exists():
        for p in paths.applications.iterdir():
            if p.is_dir() and (p / "overlay.yaml").exists():
                names.add(p.name)
    if paths.variants.exists():
        for p in paths.variants.iterdir():
            if p.is_file() and p.suffix == ".yaml":
                names.add(p.stem)
    return sorted(names)


def scaffold_variant(paths: Paths, name: str) -> Path:
    folder = paths.applications / name
    folder.mkdir(parents=True, exist_ok=True)
    for filename in _SCAFFOLD_FILES:
        path = folder / filename
        if not path.exists():
            content = _read_scaffold(paths, filename).replace("{name}", name)
            path.write_text(content, encoding="utf-8")
    return folder


def build_variant(paths: Paths, name: str) -> None:
    out_path = render_application(paths, make_env(paths), name)
    print(f"Built application resume '{name}': {rel_to_root(out_path, paths.root)}")
    print("Open it, review, then use Export PDF to send for that job.")


def build_all_variants(paths: Paths) -> None:
    names = list_variants(paths)
    if not names:
        print(f"No variants found under {paths.variants}.")
        return
    env = make_env(paths)
    for name in names:
        out_path = render_application(paths, env, name)
        print(f"Built '{name}': {rel_to_root(out_path, paths.root)}")
