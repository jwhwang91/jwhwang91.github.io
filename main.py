from __future__ import annotations

import argparse
import shutil
import base64
import mimetypes
import re
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape


ROOT = Path(__file__).resolve().parent
CONTEXT = ROOT / "Context"
FORMAT = ROOT / "Format"
TEMPLATES = FORMAT / "templates"
STYLE = ROOT / "Style"
DIST = ROOT / "dist"
VARIANTS = CONTEXT / "variants"
# Generated, ready-to-send job-application resumes, one user-named folder each
# (e.g. "Tesla 1"). Kept OUTSIDE dist/ so the backbone build never wipes them,
# and gitignored because this repo is public.
APPLICATIONS = ROOT / "Applications"


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing context file: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def ensure_clean_dist() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True, exist_ok=True)


def copy_static_files() -> None:
    shutil.copy2(STYLE / "theme.css", DIST / "style.css")
    script_src = FORMAT / "scripts" / "site.js"
    if script_src.exists():
        shutil.copy2(script_src, DIST / "site.js")
    mock_src = ROOT / "_toolchain_ui_mock"
    if mock_src.exists():
        shutil.copytree(mock_src, DIST / "_toolchain_ui_mock", dirs_exist_ok=True)


def make_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def copy_assets(src_dir: Path, out_dir: Path) -> None:
    if src_dir.exists():
        shutil.copytree(src_dir, out_dir, dirs_exist_ok=True)


def load_index_context() -> dict[str, Any]:
    site = load_yaml(CONTEXT / "site.yaml")
    personal = load_yaml(CONTEXT / "personal_info.yaml")
    resume = load_yaml(CONTEXT / "resume.yaml")
    narrative = load_yaml(CONTEXT / "narrative.yaml")
    experiences = load_yaml(CONTEXT / "experiences.yaml").get("experiences", [])
    toolchains = load_yaml(CONTEXT / "toolchain_projects.yaml").get("projects", [])

    return {
        "site": site,
        "personal": personal,
        "resume": resume,
        "narrative": narrative,
        "experiences": experiences,
        "toolchains": toolchains,
    }


def render_index_html(env: Environment, **overrides: Any) -> str:
    context = load_index_context()
    context.update(overrides)
    return env.get_template("index.html.j2").render(**context)


def render_index(env: Environment) -> None:
    html = render_index_html(env)
    (DIST / "index.html").write_text(html, encoding="utf-8")


def render_standalone_index(env: Environment) -> None:
    html = render_index_html(
        env,
        inline_css=(STYLE / "theme.css").read_text(encoding="utf-8"),
        inline_js=load_site_js(),
    )
    html = embed_local_page_links(html, DIST)
    (DIST / "standalone.html").write_text(html, encoding="utf-8")


def load_site_js() -> str:
    script_src = FORMAT / "scripts" / "site.js"
    return script_src.read_text(encoding="utf-8") if script_src.exists() else ""


def file_to_data_uri(path: Path) -> str:
    mime_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def html_to_data_uri(html: str) -> str:
    encoded = base64.b64encode(html.encode("utf-8")).decode("ascii")
    return f"data:text/html;charset=utf-8;base64,{encoded}"


def resolve_local_path(value: str, base_dir: Path) -> Path | None:
    if not value or value.startswith(("#", "mailto:", "tel:", "http://", "https://", "data:", "javascript:")):
        return None

    path_part = value.split("#", 1)[0].split("?", 1)[0]
    if not path_part:
        return None

    resolved = (base_dir / path_part).resolve()
    try:
        resolved.relative_to(DIST.resolve())
    except ValueError:
        return None
    return resolved


def inline_html_assets(html: str, source_file: Path) -> str:
    base_dir = source_file.parent

    def replace_stylesheet(match: re.Match[str]) -> str:
        href = match.group("href")
        css_path = resolve_local_path(href, base_dir)
        if not css_path or not css_path.exists():
            return match.group(0)
        css = inline_css_urls(css_path.read_text(encoding="utf-8"), css_path.parent)
        return f"<style>\n{css}\n</style>"

    html = re.sub(
        r'<link\b(?=[^>]*\brel=["\']stylesheet["\'])(?=[^>]*\bhref=["\'](?P<href>[^"\']+)["\'])[^>]*>',
        replace_stylesheet,
        html,
        flags=re.IGNORECASE,
    )

    def replace_script(match: re.Match[str]) -> str:
        src = match.group("src")
        script_path = resolve_local_path(src, base_dir)
        if not script_path or not script_path.exists():
            return match.group(0)
        return f"<script>\n{script_path.read_text(encoding='utf-8')}\n</script>"

    html = re.sub(
        r'<script\b(?=[^>]*\bsrc=["\'](?P<src>[^"\']+)["\'])[^>]*>\s*</script>',
        replace_script,
        html,
        flags=re.IGNORECASE,
    )

    def replace_src(match: re.Match[str]) -> str:
        quote = match.group("quote")
        src = match.group("src")
        asset_path = resolve_local_path(src, base_dir)
        if not asset_path or not asset_path.exists() or asset_path.suffix.lower() == ".html":
            return match.group(0)
        return f'src={quote}{file_to_data_uri(asset_path)}{quote}'

    return re.sub(
        r'src=(?P<quote>["\'])(?P<src>[^"\']+)(?P=quote)',
        replace_src,
        html,
        flags=re.IGNORECASE,
    )


def inline_css_urls(css: str, base_dir: Path) -> str:
    def replace_url(match: re.Match[str]) -> str:
        raw_url = match.group("url").strip("\"'")
        asset_path = resolve_local_path(raw_url, base_dir)
        if not asset_path or not asset_path.exists():
            return match.group(0)
        return f"url('{file_to_data_uri(asset_path)}')"

    return re.sub(r"url\((?P<url>[^)]+)\)", replace_url, css, flags=re.IGNORECASE)


def make_embedded_detail_page(page_path: Path) -> str:
    html = page_path.read_text(encoding="utf-8")
    html = inline_html_assets(html, page_path)
    html = rewrite_detail_page_links(html, page_path.parent)
    return html_to_data_uri(html)


def rewrite_detail_page_links(html: str, base_dir: Path) -> str:
    def replace_href(match: re.Match[str]) -> str:
        quote = match.group("quote")
        href = match.group("href")
        local_path = resolve_local_path(href, base_dir)
        if not local_path:
            return match.group(0)
        return f'href={quote}javascript:history.back(){quote}'

    return re.sub(
        r'href=(?P<quote>["\'])(?P<href>[^"\']+)(?P=quote)',
        replace_href,
        html,
        flags=re.IGNORECASE,
    )


def embed_local_page_links(html: str, base_dir: Path) -> str:
    def replace_href(match: re.Match[str]) -> str:
        quote = match.group("quote")
        href = match.group("href")
        page_path = resolve_local_path(href, base_dir)
        if not page_path or page_path.suffix.lower() != ".html" or not page_path.exists():
            return match.group(0)
        if page_path == (DIST / "index.html").resolve():
            fragment = href.split("#", 1)[1] if "#" in href else ""
            return f'href={quote}#{fragment}{quote}'
        return f'href={quote}{make_embedded_detail_page(page_path)}{quote}'

    return re.sub(
        r'href=(?P<quote>["\'])(?P<href>[^"\']+)(?P=quote)',
        replace_href,
        html,
        flags=re.IGNORECASE,
    )


def render_experience_pages(env: Environment) -> None:
    site = load_yaml(CONTEXT / "site.yaml")
    personal = load_yaml(CONTEXT / "personal_info.yaml")
    experience_root = CONTEXT / "Experiences"

    for context_file in experience_root.glob("*/context.yaml"):
        detail = load_yaml(context_file)
        exp_dir = context_file.parent
        out_dir = DIST / "experience" / detail["id"]
        out_dir.mkdir(parents=True, exist_ok=True)

        custom_html = exp_dir / "detail.html"
        if custom_html.exists():
            shutil.copy2(custom_html, out_dir / "index.html")
        else:
            html = env.get_template("experience_detail.html.j2").render(site=site, personal=personal, detail=detail)
            (out_dir / "index.html").write_text(html, encoding="utf-8")

        copy_assets(exp_dir / "pictures", out_dir / "assets")


def render_toolchain_pages(env: Environment) -> None:
    site = load_yaml(CONTEXT / "site.yaml")
    toolchains = load_yaml(CONTEXT / "toolchain_projects.yaml").get("projects", [])

    for project in toolchains:
        out_dir = DIST / project["detail_output"]
        out_dir.parent.mkdir(parents=True, exist_ok=True)

        if project.get("source_type") == "html":
            src = ROOT / project["source"]
            if not src.exists():
                raise FileNotFoundError(f"Missing hard-coded detail HTML: {src}")
            shutil.copy2(src, out_dir)
            continue

        src = ROOT / project["source"]
        detail = load_yaml(src)
        html = env.get_template("toolchain_detail.html.j2").render(site=site, personal=load_yaml(CONTEXT / "personal_info.yaml"), detail=detail)
        out_dir.write_text(html, encoding="utf-8")


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
#   Context/variants/<name>/overlay.yaml   (folder: also holds jd.txt + notes.md;
#                                            the per-application "regulated loop")
#   Context/variants/<name>.yaml           (flat lens, e.g. a reusable field focus)
# ---------------------------------------------------------------------------

OVERLAY_TEMPLATE = """\
# Lens for "{name}" — a thin overlay over the backbone (Context/*.yaml).
# It ONLY lists overrides; anything omitted is inherited from the backbone.
# Leaving a value blank would BLANK that field, so keep unused fields commented out.
# This file never edits Context/*.yaml. Build with:
#     python main.py --variant "{name}"
# Output: Applications/{name}/resume.html  (lean, self-contained; case-study links
# point to the live portfolio, so deep case studies are NOT bundled into the resume).

label: ""   # private human note for you, e.g. "Tesla - Autopilot Controls"

# --- site overrides (per key; uncomment only what you want to change) ---
site:
  # title: ""        # headline role line shown under your name
  # headline: ""
  # one_liner: ""
  # keywords:         # Target Roles / ATS keyword strip (replaces the backbone list)
  #   - ""
  # main_focus:       # Professional Summary bullets (replaces the backbone list)
  #   - ""

# --- resume overrides (per key, e.g. reorder/replace a skill group) ---
# resume:
#   skills:
#     software: ["Python", "C++", "..."]

# --- experiences: subset/reorder by id, plus per-id field overrides ---
# backbone ids: hmc-adas, add-k2-tcu, kaist-masters
experiences:
  include: [hmc-adas, add-k2-tcu, kaist-masters]
  # overrides:
  #   hmc-adas:
  #     hook: "..."
  #     bullets: ["...", "..."]              # honest, JD-front-loaded rewrites only
  #     keywords: ["ISO 26262", "AUTOSAR"]   # ATS keyword line under the bullets

# --- toolchains: subset/reorder by id (omit to keep all) ---
# backbone ids: e2e-xcp-bypass, timeseries-ai-training, tos-odp-bev-simulator
toolchains:
  include: [e2e-xcp-bypass, timeseries-ai-training, tos-odp-bev-simulator]
"""

NOTES_TEMPLATE = """\
# Notes - {name}

## JD signal (filled in during analysis)

## Rationale for this overlay (Claude)

## Review feedback (you - the regulation gate: edits, rejections, "tone down X")

## Lessons to carry to the next application
"""


def variant_source(name: str) -> Path | None:
    """Resolve a variant name to its overlay file: folder layout preferred, then flat."""
    folder = VARIANTS / name / "overlay.yaml"
    if folder.exists():
        return folder
    flat = VARIANTS / f"{name}.yaml"
    if flat.exists():
        return flat
    return None


def load_variant(name: str) -> dict[str, Any]:
    src = variant_source(name)
    if src is None:
        raise FileNotFoundError(
            f"No variant '{name}' found under {VARIANTS}.\n"
            f"Scaffold it first:  python main.py --new-variant \"{name}\""
        )
    variant = load_yaml(src)
    variant.setdefault("id", name)
    return variant


def select_and_override(items: list[dict[str, Any]], cfg: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Filter/reorder a list of id'd dicts by cfg['include'] and apply cfg['overrides']."""
    cfg = cfg or {}
    by_id = {item.get("id"): item for item in items}
    include = cfg.get("include")
    selected = [by_id[i] for i in include if i in by_id] if include else list(items)
    overrides = cfg.get("overrides") or {}
    return [{**item, **overrides.get(item.get("id"), {})} for item in selected]


def apply_variant(context: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    if variant.get("site"):
        context["site"] = {**context["site"], **variant["site"]}
    if variant.get("resume"):
        context["resume"] = {**context["resume"], **variant["resume"]}
    context["experiences"] = select_and_override(context["experiences"], variant.get("experiences"))
    context["toolchains"] = select_and_override(context["toolchains"], variant.get("toolchains"))
    context["noindex"] = variant.get("noindex", True)
    return context


def render_application(env: Environment, name: str) -> Path:
    """Render a lean, self-contained resume for one application to Applications/<name>/."""
    context = apply_variant(load_index_context(), load_variant(name))
    portfolio = (context["personal"].get("portfolio") or {}).get("url", "").rstrip("/")
    link_base = f"{portfolio}/" if portfolio else ""

    context.update(
        inline_css=(STYLE / "theme.css").read_text(encoding="utf-8"),
        inline_js=load_site_js(),
        link_base=link_base,            # case-study links -> live portfolio
        home_path=portfolio or "index.html",
        variant_mode=True,
    )
    html = env.get_template("index.html.j2").render(**context)

    out_dir = APPLICATIONS / name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "resume.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def list_variants() -> list[str]:
    if not VARIANTS.exists():
        return []
    names = set()
    for p in VARIANTS.iterdir():
        if p.is_dir() and (p / "overlay.yaml").exists():
            names.add(p.name)
        elif p.is_file() and p.suffix == ".yaml":
            names.add(p.stem)
    return sorted(names)


def scaffold_variant(name: str) -> Path:
    folder = VARIANTS / name
    folder.mkdir(parents=True, exist_ok=True)
    for filename, template in (
        ("jd.txt", ""),
        ("overlay.yaml", OVERLAY_TEMPLATE.format(name=name)),
        ("notes.md", NOTES_TEMPLATE.format(name=name)),
    ):
        path = folder / filename
        if not path.exists():
            path.write_text(template, encoding="utf-8")
    return folder


def build_variant(name: str) -> None:
    out_path = render_application(make_env(), name)
    print(f"Built application resume '{name}': {out_path.relative_to(ROOT)}")
    print("Open it, review, then use Export PDF to send for that job.")


def build_all_variants() -> None:
    names = list_variants()
    if not names:
        print(f"No variants found under {VARIANTS}.")
        return
    env = make_env()
    for name in names:
        out_path = render_application(env, name)
        print(f"Built '{name}': {out_path.relative_to(ROOT)}")


def build() -> None:
    ensure_clean_dist()
    copy_static_files()

    env = make_env()
    render_index(env)
    render_experience_pages(env)
    render_toolchain_pages(env)
    render_standalone_index(env)

    print(f"Built site: {DIST}")
    print("Open dist/index.html in your browser.")
    print("Standalone HTML: dist/standalone.html")
    print("Use the Export PDF button, or browser Print -> Save as PDF.")


if __name__ == "__main__":
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
        help="Build every variant under Context/variants/ into Applications/.",
    )
    parser.add_argument(
        "--new-variant",
        metavar="NAME",
        help="Scaffold Context/variants/NAME/ (jd.txt, overlay.yaml, notes.md), then stop.",
    )
    parser.add_argument(
        "--list-variants",
        action="store_true",
        help="List variants that have an overlay.",
    )
    args = parser.parse_args()

    if args.new_variant:
        folder = scaffold_variant(args.new_variant)
        print(f"Scaffolded variant: {folder.relative_to(ROOT)}")
        print(f"  1. Paste the JD into {(folder / 'jd.txt').relative_to(ROOT)}")
        print("  2. Ask Claude to analyze it and propose the overlay.")
        print(f'  3. Review, then build:  python main.py --variant "{args.new_variant}"')
    elif args.list_variants:
        names = list_variants()
        if not names:
            print('No variants yet. Create one with --new-variant "<name>".')
        else:
            print("Variants:")
            for name in names:
                built = (APPLICATIONS / name / "resume.html").exists()
                print(f"  - {name}{'  (built)' if built else ''}")
    elif args.all_variants:
        build_all_variants()
    elif args.variant:
        build_variant(args.variant)
    else:
        build()
