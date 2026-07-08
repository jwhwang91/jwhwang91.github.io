"""Support-classification truth table, cache/downgrade, pre-resume verdict, reports."""
import dataclasses
import tempfile
from pathlib import Path

import yaml

from portfolio.classify import (JoinIndex, classify_keywords, pre_resume_verdict,
                                 render_portfolio_plan, EMPHASIS)
from portfolio.facts import Registry
from portfolio.paths import default_paths
from portfolio.taxonomy import Alias, Taxonomy, Term
from portfolio.cli import main


def _tax():
    return Taxonomy([
        Term("hil", "HIL", "HIL", "validation", [Alias("HIL", "exact")]),
        Term("scc", "SCC", "SCC", "adas", [Alias("SCC", "exact")]),
        Term("ros", "ROS", "ROS", "software", [Alias("ROS", "exact")]),
        Term("lidar", "Lidar", "Lidar", "adas", [Alias("lidar", "exact")]),
        Term("welding", "Welding", "Welding", "manufacturing", [Alias("welding", "exact")]),
    ])


def _reg(claims):
    return Registry(employers={}, education={}, credentials={}, policy={}, titles={},
                    claims=claims, claims_by_id={c["id"]: c for c in claims}, anchors=set())


def _claim(cid, terms, ownership="independent", deployment="production", status="confirmed", **extra):
    c = {"id": cid, "terms": terms, "ownership": ownership, "deployment": deployment, "status": status}
    c.update(extra)
    return c


# --- registry-join truth table ---

def test_direct():
    idx = JoinIndex(_reg([_claim("c1", ["hil"], ownership="independent")]), _tax())
    assert idx.classify("hil", "exact")["support"] == "direct"


def test_partial_by_weak_ownership():
    idx = JoinIndex(_reg([_claim("c1", ["scc"], ownership="support")]), _tax())
    assert idx.classify("scc", "exact")["support"] == "partial"


def test_partial_by_related_tier():
    idx = JoinIndex(_reg([_claim("c1", ["hil"], ownership="independent")]), _tax())
    assert idx.classify("hil", "related")["support"] == "partial"


def test_partial_by_prototype_in_production_domain():
    idx = JoinIndex(_reg([_claim("c1", ["hil"], ownership="independent", deployment="prototype")]), _tax())
    assert idx.classify("hil", "exact")["support"] == "partial"


def test_partial_by_term_cap():
    idx = JoinIndex(_reg([_claim("c1", ["hil"], ownership="independent", term_caps={"hil": "partial"})]), _tax())
    assert idx.classify("hil", "exact")["support"] == "partial"


def test_software_personal_is_not_prototype_blocked():
    idx = JoinIndex(_reg([_claim("c1", ["ros"], ownership="independent", deployment="personal")]), _tax())
    assert idx.classify("ros", "exact")["support"] == "direct"


def test_adjacent_same_domain_no_direct_claim():
    idx = JoinIndex(_reg([_claim("c1", ["scc"])]), _tax())  # adas-domain claim exists
    assert idx.classify("lidar", "exact")["support"] == "adjacent"  # lidar is adas, no direct claim


def test_unsupported_no_domain_claim():
    idx = JoinIndex(_reg([_claim("c1", ["scc"])]), _tax())
    assert idx.classify("welding", "exact")["support"] == "unsupported"


def test_only_confirmed_claims_are_joined():
    idx = JoinIndex(_reg([_claim("c1", ["hil"], status="proposed")]), _tax())
    assert idx.classify("hil", "exact")["support"] == "unsupported"  # proposed claim invisible


# --- cache behavior + downgrade ---

def test_cache_hit_then_downgrade():
    tax = _tax()
    idx = JoinIndex(_reg([_claim("c1", ["hil"], ownership="independent")]), tax)
    kws = [{"term": "hil", "requirement": "must", "quote": "q"}]
    tiers = {"hil": "exact"}

    cold, _ = classify_keywords(kws, tiers, idx, {})
    assert cold[0]["support"] == "direct" and cold[0]["source"] == "registry"

    warm, _ = classify_keywords(kws, tiers, idx, {"hil": {"support": "direct", "claim_ids": ["c1"]}})
    assert warm[0]["support"] == "direct" and warm[0]["source"] == "cache"

    # registry changed: c1 gone -> cached entry re-classifies and downgrades
    empty_idx = JoinIndex(_reg([]), tax)
    down, _ = classify_keywords(kws, tiers, empty_idx, {"hil": {"support": "direct", "claim_ids": ["c1"]}})
    assert down[0]["support"] == "unsupported"


def test_new_term_goes_to_queue():
    idx = JoinIndex(_reg([]), _tax())
    resolved, queue = classify_keywords([{"new_term": {"canonical": "Kubernetes"}, "requirement": "nice"}], {}, idx, {})
    assert resolved == [] and len(queue) == 1


# --- pre-resume verdict (§4.4) ---

def _must(term, support):
    return {"term": term, "requirement": "must", "support": support}


def test_verdict_proceed():
    v = pre_resume_verdict([_must("a", "direct"), _must("b", "partial")], [], None)
    assert v["verdict"] == "Proceed" and v["U"] == 0.0


def test_verdict_caution_at_quarter():
    cls = [_must("a", "direct"), _must("b", "direct"), _must("c", "direct"), _must("d", "unsupported")]
    v = pre_resume_verdict(cls, [], None)
    assert v["U"] == 0.25 and v["verdict"] == "Proceed-Caution"


def test_verdict_do_not_apply_at_half():
    v = pre_resume_verdict([_must("a", "unsupported"), _must("b", "direct")], [], None)
    assert v["U"] == 0.5 and v["verdict"] == "Do-Not-Apply-Yet"


def test_knockout_matches_sponsorship_profile():
    ko = [{"type": "work_authorization", "quote": "must be authorized to work in the US without sponsorship"}]
    prof = {"work_authorization": {"us": {"status": "requires-sponsorship"}}}
    v = pre_resume_verdict([_must("a", "direct")], ko, prof)
    assert v["verdict"] == "Do-Not-Apply-Yet" and "work_authorization" in v["knockout_hits"]


def test_absent_profile_skips_knockouts():
    ko = [{"type": "work_authorization", "quote": "without sponsorship"}]
    v = pre_resume_verdict([_must("a", "direct")], ko, None)
    assert v["profile_checked"] is False and v["knockout_hits"] == [] and v["verdict"] == "Proceed"


# --- portfolio plan ordering ---

def test_portfolio_plan_orders_by_positioning():
    out = render_portfolio_plan("x", "adas-av-validation", [{"term": "scc", "support": "direct"}])
    assert "1. hmc-adas" in out
    assert out.index("hmc-adas") < out.index("kaist-masters")


def test_portfolio_plan_unknown_positioning():
    assert "No emphasis map" in render_portfolio_plan("x", "made-up-track", [])


# --- end-to-end via CLI against the REAL registry, incl. determinism ---

def _scoped(tmp):
    # real Context (registry + taxonomy) but tmp-scoped applications + private cache
    return dataclasses.replace(default_paths(), applications=Path(tmp) / "Applications",
                               dist=Path(tmp) / "dist", private=Path(tmp) / "private")


def _confirmed_parse():
    def kw(t, q, b="requirements"):
        return {"term": t, "requirement": "must", "block": b, "quote": q}
    return {"schema": "jd_parsed/v1", "company": "Tesla", "role_title": "ADAS Validation Engineer",
            "seniority": "senior", "role_type": "adas-validation", "confirmed": True,
            "knockouts": [{"type": "work_authorization", "quote": "Must be authorized to work in the US without sponsorship."}],
            "keywords": [
                kw("scc", "Validate Smart Cruise Control (SCC).", "responsibilities"),
                kw("hil", "Hardware-in-the-Loop (HIL) benches."),
                kw("functional-safety", "Working knowledge of ISO 26262."),
                kw("python", "Strong Python scripting."),
            ]}


def test_end_to_end_match_and_confirm(tmp_path):
    paths = _scoped(tmp_path)
    slug = "tesla-e2e"
    main(["new", slug, "--company", "Tesla", "--positioning", "adas-av-validation"], paths=paths)
    app = paths.applications / slug
    (app / "jd.txt").write_text((Path(__file__).parent / "fixtures" / "jds" / "tesla-adas-validation.txt").read_text(), encoding="utf-8")
    (app / "jd.parsed.yaml").write_text(yaml.safe_dump(_confirmed_parse()), encoding="utf-8")

    assert main(["match", slug], paths=paths) == 0
    m1 = yaml.safe_load((app / "match.yaml").read_text())
    support = {c["term"]: c["support"] for c in m1["classifications"]}
    assert support["scc"] == "direct"
    assert support["hil"] == "direct"
    assert support["functional-safety"] in ("adjacent", "unsupported")  # no ISO 26262 claim
    assert support["python"] == "direct"
    assert m1["queue"] == []  # all terms resolve deterministically

    assert main(["match", "confirm", slug], paths=paths) == 0
    m2 = yaml.safe_load((app / "match.yaml").read_text())
    assert m2["confirmed"] is True
    assert m2["pre_resume"]["verdict"] in ("Proceed", "Proceed-Caution", "Do-Not-Apply-Yet")
    assert m2["pre_resume"]["profile_checked"] is False  # no candidate_profile.yaml
    assert (app / "gap_report.md").exists() and (app / "portfolio_plan.md").exists()
    assert yaml.safe_load((app / "application.yaml").read_text())["status"] == "matched"


def test_match_is_reproducible(tmp_path):
    paths = _scoped(tmp_path)
    slug = "repro"
    main(["new", slug], paths=paths)
    app = paths.applications / slug
    (app / "jd.txt").write_text((Path(__file__).parent / "fixtures" / "jds" / "tesla-adas-validation.txt").read_text(), encoding="utf-8")
    (app / "jd.parsed.yaml").write_text(yaml.safe_dump(_confirmed_parse()), encoding="utf-8")
    main(["match", slug], paths=paths)
    first = [(c["term"], c["support"], tuple(c.get("claim_ids", []))) for c in yaml.safe_load((app / "match.yaml").read_text())["classifications"]]
    main(["match", slug], paths=paths)
    second = [(c["term"], c["support"], tuple(c.get("claim_ids", []))) for c in yaml.safe_load((app / "match.yaml").read_text())["classifications"]]
    assert first == second
