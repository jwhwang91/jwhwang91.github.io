from __future__ import annotations

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
    build()
