"""Deterministic JD scan on the 5 fixtures + the anti-hallucination validators + G1 stamp."""
import dataclasses
from pathlib import Path

import yaml

from portfolio.applications import jd_confirm, jd_parse, new_application
from portfolio.cli import main
from portfolio.jd import jd_sha256, mine_candidates, scan_jd, validate_parsed
from portfolio.paths import default_paths
from portfolio.taxonomy import Taxonomy

JDS = Path(__file__).parent / "fixtures" / "jds"
TAX = Taxonomy.load(default_paths())


def _scan_ids(name, block=None):
    text = (JDS / name).read_text(encoding="utf-8")
    return {h.term_id for h in scan_jd(text, TAX) if block is None or h.block == block}


# --- deterministic scan expectations per fixture ---

def test_tesla_scan():
    ids = _scan_ids("tesla-adas-validation.txt")
    assert {"adas", "scc", "hil", "mil", "target-selection", "log-replay",
            "functional-safety", "canape", "cpp", "python"} <= ids
    assert {"python", "cpp", "canape", "can-fd", "functional-safety", "adas"} <= _scan_ids("tesla-adas-validation.txt", "requirements")


def test_nvidia_scan():
    assert {"perception", "scenario-testing", "log-replay", "python", "cpp",
            "machine-learning", "pytorch", "docker"} <= _scan_ids("nvidia-av-simulation.txt")


def test_applied_intuition_scan():
    assert {"validation-workflow", "scenario-testing", "regression-testing", "log-replay",
            "hil", "sil", "python", "cpp", "docker"} <= _scan_ids("applied-intuition-systems.txt")


def test_fullstack_scan():
    assert {"typescript", "react", "fastapi", "rest-api", "server-sent-events", "llm-pipeline",
            "multi-agent-workflow", "anthropic-claude", "python", "docker"} <= _scan_ids("fullstack-ai-product.txt")


def test_embedded_scan():
    assert {"tcu", "embedded-control", "cpp", "misra-c", "autosar", "can", "can-fd", "uds",
            "hil", "dynamometer", "matlab-simulink", "control-systems"} <= _scan_ids("embedded-controls.txt")


def test_unknown_candidates_surface_new_terms():
    tesla = {c["candidate"] for c in mine_candidates((JDS / "tesla-adas-validation.txt").read_text(), TAX)}
    assert "CARLA" in tesla


def test_a_mined_candidate_stops_being_unknown_once_it_is_a_term():
    """ROS2 used to surface here as an unknown candidate. It was promoted to a real
    taxonomy id on 2026-09-04 (from the Torc R-102814 parse), so the correct behaviour
    now is the opposite: it resolves as a scan hit and no longer appears as unknown.
    That is the whole point of the mine-then-promote loop — this test pins the
    transition so a silent regression in either direction is caught."""
    text = (JDS / "nvidia-av-simulation.txt").read_text()
    assert "ROS2" not in {c["candidate"] for c in mine_candidates(text, TAX)}
    assert any(h.term_id == "ros" for h in scan_jd(text, TAX))


def test_scan_is_deterministic():
    text = (JDS / "tesla-adas-validation.txt").read_text()
    a = [(h.term_id, h.block, h.count) for h in scan_jd(text, TAX)]
    b = [(h.term_id, h.block, h.count) for h in scan_jd(text, TAX)]
    assert a == b


def test_sha_changes_with_text():
    assert jd_sha256("abc") == jd_sha256("abc")
    assert jd_sha256("abc") != jd_sha256("abd")


# --- validators (anti-hallucination) ---

_JD = (JDS / "tesla-adas-validation.txt").read_text(encoding="utf-8")


def test_nonverbatim_quote_fails_validation():
    parsed = {"schema": "jd_parsed/v1", "keywords": [
        {"term": "hil", "requirement": "must", "block": "responsibilities",
         "quote": "This exact sentence is nowhere in the JD."}]}
    errs = [v for v in validate_parsed(parsed, _JD, TAX) if v.level == "error"]
    assert any("verbatim" in v.message for v in errs)


def test_verbatim_quote_passes_validation():
    parsed = {"schema": "jd_parsed/v1", "keywords": [
        {"term": "functional-safety", "requirement": "must", "block": "requirements",
         "quote": "Working knowledge of ISO 26262 functional safety."}]}
    errs = [v for v in validate_parsed(parsed, _JD, TAX) if v.level == "error"]
    assert not any("verbatim" in v.message for v in errs)


def test_unknown_term_fails_validation():
    parsed = {"schema": "jd_parsed/v1", "keywords": [
        {"term": "not-a-real-term", "requirement": "must", "block": "requirements",
         "quote": "Strong Python and C++ scripting for log analysis."}]}
    errs = [v for v in validate_parsed(parsed, _JD, TAX) if v.level == "error"]
    assert any("unknown term" in v.message for v in errs)


def test_dropped_requirements_hit_warns():
    # a JD with a requirements-block term that the parse omits -> coverage warning
    parsed = {"schema": "jd_parsed/v1", "keywords": []}
    warns = [v for v in validate_parsed(parsed, _JD, TAX) if v.level == "warning"]
    assert any("requirements but it is absent" in v.message for v in warns)


# --- end-to-end via the CLI (new -> jd parse -> jd confirm G1) ---

def _scoped(tmp_path):
    return dataclasses.replace(default_paths(), applications=tmp_path / "Applications", dist=tmp_path / "dist")


def _valid_parsed():
    q = {
        "adas": "5+ years in ADAS or autonomous driving validation.",
        "python": "Strong Python and C++ scripting for log analysis.",
        "cpp": "Strong Python and C++ scripting for log analysis.",
        "canape": "Hands-on experience with CANape and CAN-FD.",
        "can-fd": "Hands-on experience with CANape and CAN-FD.",
        "functional-safety": "Working knowledge of ISO 26262 functional safety.",
    }
    kws = [{"term": t, "requirement": "must", "block": "requirements", "quote": s} for t, s in q.items()]
    kws.append({"term": "scc", "requirement": "must", "block": "responsibilities",
                "quote": "Validate Smart Cruise Control (SCC) and Adaptive Cruise Control behavior across driving scenarios."})
    kws.append({"term": "hil", "requirement": "must", "block": "responsibilities",
                "quote": "Build and run Hardware-in-the-Loop (HIL) and Model-in-the-Loop (MIL) test benches."})
    return {
        "schema": "jd_parsed/v1", "company": "Tesla", "role_title": "ADAS Validation Engineer",
        "seniority": "senior", "role_type": "adas-validation",
        "knockouts": [{"type": "work_authorization", "quote": "Must be authorized to work in the US without sponsorship."}],
        "keywords": kws,
    }


def test_end_to_end_parse_and_confirm(tmp_path):
    paths = _scoped(tmp_path)
    slug = "tesla-adas-2026-07"
    new_application(paths, slug, company="Tesla", positioning="adas-av-validation")
    app = paths.applications / slug
    (app / "jd.txt").write_text(_JD, encoding="utf-8")

    # deterministic parse stamps the scan + jd hash
    assert main(["jd", "parse", slug], paths=paths) == 0
    assert (app / "jd.scan.yaml").exists()
    stamped = yaml.safe_load((app / "application.yaml").read_text())["jd_sha256"]
    assert stamped == jd_sha256(_JD)

    # a valid parse confirms (Gate G1) and advances status
    (app / "jd.parsed.yaml").write_text(yaml.safe_dump(_valid_parsed()), encoding="utf-8")
    assert main(["jd", "confirm", slug], paths=paths) == 0
    confirmed = yaml.safe_load((app / "jd.parsed.yaml").read_text())
    assert confirmed["confirmed"] is True
    assert yaml.safe_load((app / "application.yaml").read_text())["status"] == "parsed"


def test_confirm_rejects_doctored_quote(tmp_path):
    paths = _scoped(tmp_path)
    slug = "tesla-doctored"
    new_application(paths, slug)
    app = paths.applications / slug
    (app / "jd.txt").write_text(_JD, encoding="utf-8")
    main(["jd", "parse", slug], paths=paths)

    bad = _valid_parsed()
    bad["keywords"][0]["quote"] = "A requirement that was never in the posting."
    (app / "jd.parsed.yaml").write_text(yaml.safe_dump(bad), encoding="utf-8")
    assert main(["jd", "confirm", slug], paths=paths) == 1  # verbatim check fails


def test_new_rejects_bad_slug_and_duplicate(tmp_path):
    import pytest
    paths = _scoped(tmp_path)
    new_application(paths, "good-slug")
    with pytest.raises(FileExistsError):
        new_application(paths, "good-slug")
    with pytest.raises(ValueError):
        new_application(paths, "Bad_Slug")
