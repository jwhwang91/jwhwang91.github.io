"""Regressions for the Phase 3 adversarial-review findings."""
from pathlib import Path

import pytest

from portfolio.cli import build_parser
from portfolio.jd import block_texts, scan_jd, validate_parsed
from portfolio.paths import default_paths
from portfolio.taxonomy import Taxonomy

TAX = Taxonomy.load(default_paths())
_JD = (Path(__file__).parent / "fixtures" / "jds" / "tesla-adas-validation.txt").read_text(encoding="utf-8")


def test_sentence_like_requirement_line_not_misclassified_as_heading():
    # Finding: short content lines containing 'required'/'a plus' were treated as
    # headings and dropped. They must stay content and be scanned in-block.
    text = ("Requirements:\n"
            "Strong knowledge of MATLAB required\n"
            "Functional safety experience is a plus\n"
            "Solid grounding in vehicle dynamics and CAN bus\n")
    reqs = {h.term_id for h in scan_jd(text, TAX) if h.block == "requirements"}
    assert {"matlab-simulink", "functional-safety", "vehicle-dynamics", "can"} <= reqs


def test_all_caps_and_title_headings_still_segment():
    text = "RESPONSIBILITIES\nBuild HIL benches\nRequirements\nStrong C++ and Python\n"
    hits = scan_jd(text, TAX)
    by_block = {}
    for h in hits:
        by_block.setdefault(h.block, set()).add(h.term_id)
    assert "hil" in by_block.get("responsibilities", set())
    assert {"cpp", "python"} <= by_block.get("requirements", set())


def test_strongest_tier_is_order_independent():
    a = {h.term_id: h.tier for h in scan_jd("Work on autonomous driving and ADAS features.", TAX)}
    b = {h.term_id: h.tier for h in scan_jd("Work on ADAS and autonomous driving features.", TAX)}
    assert a["adas"] == "exact" and b["adas"] == "exact"  # ADAS(exact) beats autonomous driving(related)


def test_empty_quote_is_rejected():
    parsed = {"schema": "jd_parsed/v1", "keywords": [
        {"term": "hil", "requirement": "must", "block": "requirements", "quote": ""}]}
    errs = [v for v in validate_parsed(parsed, _JD, TAX) if v.level == "error"]
    assert any("empty" in v.message for v in errs)


def test_false_positive_clears_coverage_warning():
    jd = "Requirements:\nWe can teach you the CAN bus on the job\n"
    parsed = {"schema": "jd_parsed/v1", "keywords": [
        {"term": "can", "requirement": "contextual", "block": "requirements",
         "quote": "We can teach you the CAN bus on the job", "false_positive": "generic english / mentioned only"}]}
    warns = [v for v in validate_parsed(parsed, jd, TAX) if v.level == "warning"]
    assert not any("'can'" in v.message for v in warns)


def test_what_youll_bring_is_a_requirements_heading():
    # Finding: the requirements heading regex only knew "What You'll Need", and
    # _is_heading_like used str.istitle(), which returns False for "You'll" (the
    # letter after an apostrophe must be uppercase) and for lowercase function
    # words. Tesla-style JDs therefore produced NO requirements block at all.
    text = ("What to Expect\n"
            "We validate vehicle software before release.\n"
            "What You’ll Do\n"
            "Build HIL benches\n"
            "What You’ll Bring\n"
            "Experience with HIL/SIL environments and simulation-based validation\n"
            "Compensation and Benefits\n"
            "401(k) with employer match\n")
    blocks = block_texts(text)
    assert "requirements" in blocks
    assert "HIL/SIL" in blocks["requirements"]
    assert "Build HIL benches" in blocks["responsibilities"]
    assert "401(k)" in blocks["benefits"]
    assert {h.term_id for h in scan_jd(text, TAX) if h.block == "requirements"} >= {"hil", "sil"}


@pytest.mark.parametrize("heading,block", [
    ("What You'll Need", "requirements"),
    ("What You’ll Have", "requirements"),
    ("What You’ll Bring", "requirements"),
    ("Minimum Qualifications", "requirements"),
    ("Nice to Have", "preferred"),
    ("What You’ll Do", "responsibilities"),
    ("About the Role", "responsibilities"),
])
def test_apostrophe_and_function_word_headings_segment(heading, block):
    hits = scan_jd(f"{heading}\nStrong C++ and Python\n", TAX)
    assert {h.block for h in hits} == {block}


def test_tolerant_title_case_still_rejects_sentence_content():
    # the loosened heading check must not start eating ordinary requirement lines
    from portfolio.jd import _is_heading_like
    assert not _is_heading_like("Strong knowledge of MATLAB required")
    assert not _is_heading_like("Minimum 2 years’ experience utilizing the skills above")
    assert not _is_heading_like("Functional safety experience is a plus")
    assert _is_heading_like("What to Expect")
    assert _is_heading_like("Compensation and Benefits")


def test_flag_abbreviations_are_disabled():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--li"])  # ambiguous prefix now rejected, not silently resolved
    assert build_parser().parse_args(["--list-variants"]).list_variants is True
