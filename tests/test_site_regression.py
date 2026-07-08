"""Golden-structure regression for the public site build.

Asserts key sections/pages/links are present (not byte equality) and that the
standalone inliner path survives the package split. Builds into a tmp dir via a
dir-scoped Paths, so the real repo dist/ is never touched.
"""
import dataclasses

from portfolio.paths import default_paths
from portfolio.site import build


def _scoped(tmp_path):
    return dataclasses.replace(
        default_paths(),
        dist=tmp_path / "dist",
        applications=tmp_path / "Applications",
    )


def test_build_produces_core_pages(tmp_path):
    paths = _scoped(tmp_path)
    build(paths)
    dist = paths.dist

    assert (dist / "index.html").exists()
    assert (dist / "standalone.html").exists()
    assert (dist / "style.css").exists()

    index = (dist / "index.html").read_text(encoding="utf-8")
    assert "Jae Woong Hwang" in index
    assert "jwhwang91@gmail.com" in index

    # detail pages built and linked
    for exp in ("hmc-adas", "add-k2-tcu", "kaist-masters"):
        assert (dist / "experience" / exp / "index.html").exists()
        assert f'href="experience/{exp}/index.html"' in index
    for tool in ("e2e-xcp-bypass", "timeseries-ai-training", "tos-odp-bev-simulator"):
        assert (dist / "toolchains" / tool / "index.html").exists()


def test_phone_not_in_public_site(tmp_path):
    # Phase 0 privacy invariant: the phone number must never render publicly.
    paths = _scoped(tmp_path)
    build(paths)
    for name in ("index.html", "standalone.html"):
        assert "XXXX-XXXX" not in (paths.dist / name).read_text(encoding="utf-8")


def test_standalone_inliner_survives_split(tmp_path):
    # The standalone build inlines CSS (<style>) and folds each detail page in as
    # a data:text/html URI — prove that machinery still runs post-split.
    paths = _scoped(tmp_path)
    build(paths)
    standalone = (paths.dist / "standalone.html").read_text(encoding="utf-8")
    assert "<style>" in standalone
    assert "data:text/html" in standalone          # detail pages embedded
    assert 'href="style.css"' not in standalone     # CSS inlined, not external
