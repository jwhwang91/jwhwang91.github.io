from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .content import load_index_context, load_yaml
from .inline import embed_local_page_links
from .paths import Paths


def ensure_clean_dist(paths: Paths) -> None:
    if paths.dist.exists():
        shutil.rmtree(paths.dist)
    paths.dist.mkdir(parents=True, exist_ok=True)


def copy_static_files(paths: Paths) -> None:
    shutil.copy2(paths.style / "theme.css", paths.dist / "style.css")
    script_src = paths.format_dir / "scripts" / "site.js"
    if script_src.exists():
        shutil.copy2(script_src, paths.dist / "site.js")
    mock_src = paths.root / "_toolchain_ui_mock"
    if mock_src.exists():
        shutil.copytree(mock_src, paths.dist / "_toolchain_ui_mock", dirs_exist_ok=True)


def make_env(paths: Paths) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(paths.templates)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def copy_assets(src_dir: Path, out_dir: Path) -> None:
    if src_dir.exists():
        shutil.copytree(src_dir, out_dir, dirs_exist_ok=True)


def load_site_js(paths: Paths) -> str:
    script_src = paths.format_dir / "scripts" / "site.js"
    return script_src.read_text(encoding="utf-8") if script_src.exists() else ""


def render_index_html(env: Environment, paths: Paths, **overrides: Any) -> str:
    context = load_index_context(paths)
    context.update(overrides)
    return env.get_template("index.html.j2").render(**context)


def render_index(env: Environment, paths: Paths) -> None:
    html = render_index_html(env, paths)
    (paths.dist / "index.html").write_text(html, encoding="utf-8")


def render_standalone_index(env: Environment, paths: Paths) -> None:
    # Must run AFTER the detail pages exist: embed_local_page_links re-reads the
    # rendered dist/ pages to fold them in as data: URIs.
    html = render_index_html(
        env,
        paths,
        inline_css=(paths.style / "theme.css").read_text(encoding="utf-8"),
        inline_js=load_site_js(paths),
    )
    html = embed_local_page_links(html, paths.dist, paths.dist)
    (paths.dist / "standalone.html").write_text(html, encoding="utf-8")


def render_experience_pages(env: Environment, paths: Paths) -> None:
    site = load_yaml(paths.context / "site.yaml")
    personal = load_yaml(paths.context / "personal_info.yaml")
    experience_root = paths.context / "Experiences"

    for context_file in experience_root.glob("*/context.yaml"):
        detail = load_yaml(context_file)
        exp_dir = context_file.parent
        out_dir = paths.dist / "experience" / detail["id"]
        out_dir.mkdir(parents=True, exist_ok=True)

        custom_html = exp_dir / "detail.html"
        if custom_html.exists():
            shutil.copy2(custom_html, out_dir / "index.html")
        else:
            html = env.get_template("experience_detail.html.j2").render(site=site, personal=personal, detail=detail)
            (out_dir / "index.html").write_text(html, encoding="utf-8")

        copy_assets(exp_dir / "pictures", out_dir / "assets")


def render_toolchain_pages(env: Environment, paths: Paths) -> None:
    site = load_yaml(paths.context / "site.yaml")
    toolchains = load_yaml(paths.context / "toolchain_projects.yaml").get("projects", [])

    for project in toolchains:
        out_dir = paths.dist / project["detail_output"]
        out_dir.parent.mkdir(parents=True, exist_ok=True)

        if project.get("source_type") == "html":
            src = paths.root / project["source"]
            if not src.exists():
                raise FileNotFoundError(f"Missing hard-coded detail HTML: {src}")
            shutil.copy2(src, out_dir)
            continue

        src = paths.root / project["source"]
        detail = load_yaml(src)
        html = env.get_template("toolchain_detail.html.j2").render(
            site=site, personal=load_yaml(paths.context / "personal_info.yaml"), detail=detail
        )
        out_dir.write_text(html, encoding="utf-8")


def build(paths: Paths) -> None:
    ensure_clean_dist(paths)
    copy_static_files(paths)

    env = make_env(paths)
    render_index(env, paths)
    render_experience_pages(env, paths)
    render_toolchain_pages(env, paths)
    render_standalone_index(env, paths)

    print(f"Built site: {paths.dist}")
    print("Open dist/index.html in your browser.")
    print("Standalone HTML: dist/standalone.html")
    print("Use the Export PDF button, or browser Print -> Save as PDF.")
