"""resume.yaml -> txt/html/md rendering: structure, ASCII, employer lines, ordering."""
from pathlib import Path

import yaml

from portfolio.facts import load_registry
from portfolio.paths import default_paths
from portfolio.resume_render import build_context, render_md, render_txt

SAMPLE = Path(__file__).parent / "fixtures" / "sample_output"


def _resume():
    return yaml.safe_load((SAMPLE / "resume.yaml").read_text(encoding="utf-8"))


def _ctx():
    return build_context(default_paths(), _resume(), load_registry(default_paths()))


def test_txt_has_all_sections_and_caps_headings():
    txt = render_txt(_ctx())
    for h in ("SUMMARY", "SKILLS", "EXPERIENCE", "EDUCATION"):
        assert h in txt
    assert "Jae Woong Hwang" in txt


def test_txt_is_pure_ascii():
    assert render_txt(_ctx()).isascii()


def test_experience_header_from_employers_registry():
    txt = render_txt(_ctx())
    assert "Hyundai Motor Company | Commercial Vehicle ADAS Controls & Validation Engineer | 2021.03 - Present" in txt


def test_education_from_registry():
    txt = render_txt(_ctx())
    assert "University of California Los Angeles (UCLA)" in txt
    assert "Korea Advanced Institute of Science and Technology (KAIST)" in txt


def test_acronym_ats_form_present():
    assert "Hardware-in-the-Loop (HIL/HILS)" in render_txt(_ctx())


def test_phone_merged_from_private_file():
    # the private phone is merged into the resume render (never the public site)
    txt = render_txt(_ctx())
    priv = default_paths().private / "personal_private.yaml"
    if priv.exists():
        phone = yaml.safe_load(priv.read_text()).get("phone")
        if phone:
            assert phone in txt


def test_reverse_chronological_ordering():
    reg = load_registry(default_paths())
    resume = {"schema": "resume/v1", "application": "x", "positioning": "p", "role_title": "r",
              "experience": [
                  {"source": "add-k2-tcu", "bullets": [{"text": "b", "claims": []}]},   # 2017
                  {"source": "hmc-adas", "bullets": [{"text": "b", "claims": []}]},      # 2021
              ]}
    txt = render_txt(build_context(default_paths(), resume, reg))
    assert txt.index("Hyundai Motor Company") < txt.index("Agency for Defense Development")


def test_md_renders():
    md = render_md(_ctx())
    assert md.startswith("# Jae Woong Hwang")
    assert "## Experience" in md


def test_non_ascii_transliterated_not_masked():
    from portfolio.resume_render import to_ascii
    assert to_ascii("Bezier cafe resume") == "Bezier cafe resume"
    assert to_ascii("naïve résumé") == "naive resume"   # naïve résumé
    assert "?" not in to_ascii("Développé")                  # accents -> ascii, not '?'


def test_licenses_resolve_by_claim_id_no_leak():
    reg = load_registry(default_paths())
    resume = {"schema": "resume/v1", "application": "x", "positioning": "p", "role_title": "r",
              "extras": {"licenses": ["cert-class1-license"]}}
    ctx = build_context(default_paths(), resume, reg)
    assert any("Class 1" in lic for lic in ctx["licenses"])
    assert not any("Trailer" in lic for lic in ctx["licenses"])   # only the requested id
