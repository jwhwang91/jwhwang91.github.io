from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Standalone-page inliner: folds the built dist/ into a single self-contained
# HTML file (CSS/JS/images embedded, detail pages folded in as data: URIs). All
# path resolution is confined to `dist` so a crafted href can never escape it.
# ---------------------------------------------------------------------------


def file_to_data_uri(path: Path) -> str:
    mime_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def html_to_data_uri(html: str) -> str:
    encoded = base64.b64encode(html.encode("utf-8")).decode("ascii")
    return f"data:text/html;charset=utf-8;base64,{encoded}"


def resolve_local_path(value: str, base_dir: Path, dist: Path) -> Path | None:
    if not value or value.startswith(("#", "mailto:", "tel:", "http://", "https://", "data:", "javascript:")):
        return None

    path_part = value.split("#", 1)[0].split("?", 1)[0]
    if not path_part:
        return None

    resolved = (base_dir / path_part).resolve()
    try:
        resolved.relative_to(dist.resolve())
    except ValueError:
        return None
    return resolved


def inline_html_assets(html: str, source_file: Path, dist: Path) -> str:
    base_dir = source_file.parent

    def replace_stylesheet(match: re.Match[str]) -> str:
        href = match.group("href")
        css_path = resolve_local_path(href, base_dir, dist)
        if not css_path or not css_path.exists():
            return match.group(0)
        css = inline_css_urls(css_path.read_text(encoding="utf-8"), css_path.parent, dist)
        return f"<style>\n{css}\n</style>"

    html = re.sub(
        r'<link\b(?=[^>]*\brel=["\']stylesheet["\'])(?=[^>]*\bhref=["\'](?P<href>[^"\']+)["\'])[^>]*>',
        replace_stylesheet,
        html,
        flags=re.IGNORECASE,
    )

    def replace_script(match: re.Match[str]) -> str:
        src = match.group("src")
        script_path = resolve_local_path(src, base_dir, dist)
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
        asset_path = resolve_local_path(src, base_dir, dist)
        if not asset_path or not asset_path.exists() or asset_path.suffix.lower() == ".html":
            return match.group(0)
        return f'src={quote}{file_to_data_uri(asset_path)}{quote}'

    return re.sub(
        r'src=(?P<quote>["\'])(?P<src>[^"\']+)(?P=quote)',
        replace_src,
        html,
        flags=re.IGNORECASE,
    )


def inline_css_urls(css: str, base_dir: Path, dist: Path) -> str:
    def replace_url(match: re.Match[str]) -> str:
        raw_url = match.group("url").strip("\"'")
        asset_path = resolve_local_path(raw_url, base_dir, dist)
        if not asset_path or not asset_path.exists():
            return match.group(0)
        return f"url('{file_to_data_uri(asset_path)}')"

    return re.sub(r"url\((?P<url>[^)]+)\)", replace_url, css, flags=re.IGNORECASE)


def make_embedded_detail_page(page_path: Path, dist: Path) -> str:
    html = page_path.read_text(encoding="utf-8")
    html = inline_html_assets(html, page_path, dist)
    html = rewrite_detail_page_links(html, page_path.parent, dist)
    return html_to_data_uri(html)


def rewrite_detail_page_links(html: str, base_dir: Path, dist: Path) -> str:
    def replace_href(match: re.Match[str]) -> str:
        quote = match.group("quote")
        href = match.group("href")
        local_path = resolve_local_path(href, base_dir, dist)
        if not local_path:
            return match.group(0)
        return f'href={quote}javascript:history.back(){quote}'

    return re.sub(
        r'href=(?P<quote>["\'])(?P<href>[^"\']+)(?P=quote)',
        replace_href,
        html,
        flags=re.IGNORECASE,
    )


def embed_local_page_links(html: str, base_dir: Path, dist: Path) -> str:
    def replace_href(match: re.Match[str]) -> str:
        quote = match.group("quote")
        href = match.group("href")
        page_path = resolve_local_path(href, base_dir, dist)
        if not page_path or page_path.suffix.lower() != ".html" or not page_path.exists():
            return match.group(0)
        if page_path == (dist / "index.html").resolve():
            fragment = href.split("#", 1)[1] if "#" in href else ""
            return f'href={quote}#{fragment}{quote}'
        return f'href={quote}{make_embedded_detail_page(page_path, dist)}{quote}'

    return re.sub(
        r'href=(?P<quote>["\'])(?P<href>[^"\']+)(?P=quote)',
        replace_href,
        html,
        flags=re.IGNORECASE,
    )
