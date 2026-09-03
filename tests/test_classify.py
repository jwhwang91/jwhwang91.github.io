"""Support-classification truth table, cache/downgrade, pre-resume verdict, reports."""
import dataclasses
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from portfolio.classify import (JoinIndex, classify_keywords, location_knockouts,
                                 pre_resume_verdict, render_portfolio_plan,
                                 resolve_term_to_taxonomy, EMPHASIS)
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


# --- location knockouts (he is in South Korea with no US authorization) ---

def _kr_profile():
    """Minimal shape of the real (gitignored) Context/candidate_profile.yaml."""
    return {
        "work_authorization": {"kr": "citizen", "us": {"status": "requires-sponsorship"}},
        "locations": {
            "current": {"city": "Seoul", "country": "South Korea"},
            "authorized_now": {"place": "South Korea",
                               "names": ["South Korea", "Korea", "Seoul", "Pangyo"]},
            "relocation": [{"place": "United States", "names": ["United States", "USA", "U.S."],
                            "relocation_ok": True, "requires_sponsorship": True}],
            "remote": {"remote_ok": True, "names": ["fully remote", "work from anywhere"]},
        },
    }


@pytest.mark.parametrize("ko", [
    {"type": "location", "quote": "This role is onsite in Palo Alto, CA."},
    {"type": "location", "quote": "Must be based in Austin, Texas."},
    {"type": "onsite", "quote": "5 days a week in-person at our Fremont factory."},
    {"type": "location", "quote": "Hybrid: 3 days per week in the Mountain View office."},
    {"type": "relocation", "quote": "Relocation to Michigan is required."},
    {"type": "location", "quote": "Remote (US only)."},
    {"type": "location", "quote": "onsite role — location: (unspecified)"},  # unnamed -> fail closed
])
def test_location_knockout_hits_when_he_cannot_be_there(ko):
    v = pre_resume_verdict([_must("a", "direct")], [ko], _kr_profile())
    assert v["knockout_hits"] == [ko["type"]] and v["verdict"] == "Do-Not-Apply-Yet"


@pytest.mark.parametrize("ko", [
    {"type": "location", "quote": "Onsite in Seoul, South Korea."},
    {"type": "location", "quote": "Hybrid from our Pangyo office."},
    {"type": "onsite", "quote": "This role must be based in Korea."},
    {"type": "location", "quote": "Fully remote — work from anywhere."},
])
def test_location_knockout_clears_where_he_may_work(ko):
    v = pre_resume_verdict([_must("a", "direct")], [ko], _kr_profile())
    assert v["knockout_hits"] == [] and v["verdict"] == "Proceed"


def test_us_place_names_are_word_boundary_matched():
    # substring matching would find 'US' inside 'must' and mislabel every knockout
    from portfolio.classify import _mentions
    assert not _mentions("must be based in seoul", ["US"])
    assert _mentions("relocation to the us is required", ["US"])


def test_location_branch_needs_location_data_in_the_profile():
    # a profile with no locations block must not invent a location knockout
    prof = {"work_authorization": {"us": {"status": "requires-sponsorship"}}}
    v = pre_resume_verdict([_must("a", "direct")], [{"type": "location", "quote": "Onsite in Palo Alto."}], prof)
    assert v["knockout_hits"] == [] and v["profile_checked"] is True


def test_sponsorship_branch_still_wins_and_is_unchanged():
    ko = [{"type": "work_authorization",
           "quote": "Must be authorized to work in the US without sponsorship; relocation assistance provided."}]
    v = pre_resume_verdict([_must("a", "direct")], ko, _kr_profile())
    assert v["knockout_hits"] == ["work_authorization"]


# --- synthesizing a location knockout from location_policy (the parser emits none) ---

def test_location_knockout_synthesized_from_onsite_policy():
    # exactly the Tesla shape: knockouts: [] but location_policy says onsite
    kos = location_knockouts({"onsite": True, "city": None, "remote": False}, _kr_profile())
    assert len(kos) == 1
    assert kos[0]["type"] == "location" and kos[0]["source"] == "derived:location_policy"
    assert "not a verbatim JD quote" in kos[0]["quote"]  # never valid inside jd.parsed.yaml


def test_location_knockout_synthesized_from_named_city():
    kos = location_knockouts({"onsite": True, "city": "Palo Alto, CA", "remote": False}, _kr_profile())
    assert len(kos) == 1 and "Palo Alto, CA" in kos[0]["quote"]
    # `place` isolates the work location so _knockout_matches judges it alone
    assert kos[0]["place"] == "Palo Alto, CA"


def test_no_location_knockout_for_a_korean_onsite_role():
    assert location_knockouts({"onsite": True, "city": "Seoul", "remote": False}, _kr_profile()) == []


# --- regressions: the location branch used to fail OPEN on US reqs naming Korea ---

def test_us_req_that_mentions_korea_still_knocks_out():
    # blocked-place-first ordering: naming a relocation target he cannot reach
    # unsponsored decides before any authorized place mentioned in the same text
    ko = {"type": "location",
          "quote": "Onsite in the United States; our Seoul office collaborates closely."}
    v = pre_resume_verdict([_must("a", "direct")], [ko], _kr_profile())
    assert v["knockout_hits"] == ["location"]


def test_korean_as_a_nationality_adjective_is_not_a_place():
    # "Korean OEM partners" / "Korean-English bilingual" must not clear a US req;
    # word boundaries stop `korea` matching inside `korean`
    ko = {"type": "location",
          "quote": "Onsite in Santa Clara, CA. Korean-English bilingual a plus."}
    v = pre_resume_verdict([_must("a", "direct")], [ko], _kr_profile())
    assert v["knockout_hits"] == ["location"]


def test_unknown_city_fails_closed_and_ignores_the_jd_body():
    # an earlier version scanned all of jd.txt, so a US posting mentioning a Seoul
    # office cleared its own location knockout. With no parsed city the answer is a
    # hit — a visible gap_report row the owner can overrule beats a silent clear.
    kos = location_knockouts({"onsite": True, "city": None, "remote": False}, _kr_profile())
    assert len(kos) == 1 and kos[0]["place"] == ""


def test_region_and_country_fill_in_when_city_is_absent():
    kos = location_knockouts({"onsite": True, "country": "South Korea", "remote": False},
                             _kr_profile())
    assert kos == []


def test_no_location_knockout_for_remote_or_silent_policies():
    prof = _kr_profile()
    assert location_knockouts({"onsite": False, "city": None, "remote": True}, prof) == []
    assert location_knockouts({"onsite": False, "city": None, "remote": False}, prof) == []
    assert location_knockouts({"onsite": True, "city": None, "remote": False}, None) == []
    assert location_knockouts(None, prof) == []


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
                kw("cpp", "Basic proficiency with embedded firmware development in C/C++."),
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
    # `cpp` was removed from every claim's terms[] (add-tcu-embedded-c autocoded its C
    # from Simulink; tc-xcp-bypass's C++ was agent-written), so a C/C++ keyword must
    # never score direct proficiency again — scoring direct is what put an unhedged
    # "embedded C/C++" on the resume submitted to Tesla in July 2026.
    assert support["cpp"] in ("adjacent", "unsupported")
    assert m1["queue"] == []  # all terms resolve deterministically

    assert main(["match", "confirm", slug], paths=paths) == 0
    m2 = yaml.safe_load((app / "match.yaml").read_text())
    assert m2["confirmed"] is True
    assert m2["pre_resume"]["verdict"] in ("Proceed", "Proceed-Caution", "Do-Not-Apply-Yet")
    # Context/candidate_profile.yaml is gitignored, so it exists on the owner's
    # machine and not in a fresh clone. Either way the flag must report the truth.
    assert m2["pre_resume"]["profile_checked"] is (paths.context / "candidate_profile.yaml").exists()
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


# --- review-finding regressions ---

def test_credential_terms_are_not_resolved_to_skills():
    from portfolio.taxonomy import Taxonomy
    tax = Taxonomy.load(default_paths())
    assert resolve_term_to_taxonomy("commercial-vehicle-license", tax) == set()  # was wrongly -> commercial-vehicle
    assert resolve_term_to_taxonomy("bachelors-degree", tax) == set()
    assert "typescript" in resolve_term_to_taxonomy("typescript-react", tax)     # legit compound still resolves


def test_unscanned_keyword_defaults_to_related_not_direct():
    idx = JoinIndex(_reg([_claim("c1", ["hil"], ownership="independent")]), _tax())
    resolved, _ = classify_keywords([{"term": "hil", "requirement": "must"}], {}, idx, {})
    assert resolved[0]["support"] == "partial"  # no scan tier -> related -> not free direct


def test_cache_does_not_leak_stale_direct_at_weaker_tier():
    tax = _tax()
    idx = JoinIndex(_reg([_claim("c1", ["hil"], ownership="independent")]), tax)
    cache = {"hil": {"support": "direct", "claim_ids": ["c1"]}}  # confirmed direct in another app
    resolved, _ = classify_keywords([{"term": "hil", "requirement": "must"}], {"hil": "related"}, idx, cache)
    assert resolved[0]["support"] == "partial"  # re-gated to this app's weaker tier


def test_match_confirm_rejects_overclaimed_direct(tmp_path):
    paths = _scoped(tmp_path)
    slug = "overclaim"
    main(["new", slug], paths=paths)
    app = paths.applications / slug
    m = {"schema": "match/v1", "application": slug, "classifications": [
        {"term": "functional-safety", "support": "direct", "requirement": "must",
         "matched_tier": "exact", "claim_ids": ["hmc-scc-emergency-stop"], "source": "llm"}]}
    (app / "match.yaml").write_text(yaml.safe_dump(m), encoding="utf-8")
    # functional-safety has no supporting claim (adjacent); a declared 'direct' must be rejected
    assert main(["match", "confirm", slug], paths=paths) == 1


def test_second_match_uses_the_cache(tmp_path):
    paths = _scoped(tmp_path)
    slug = "cache-e2e"
    main(["new", slug], paths=paths)
    app = paths.applications / slug
    (app / "jd.txt").write_text((Path(__file__).parent / "fixtures" / "jds" / "tesla-adas-validation.txt").read_text(), encoding="utf-8")
    (app / "jd.parsed.yaml").write_text(yaml.safe_dump(_confirmed_parse()), encoding="utf-8")
    main(["match", slug], paths=paths)
    main(["match", "confirm", slug], paths=paths)
    assert (paths.private / "keyword_map.yaml").exists()
    main(["match", slug], paths=paths)  # second run: everything served from cache
    cls = yaml.safe_load((app / "match.yaml").read_text())["classifications"]
    assert cls and all(c["source"] == "cache" for c in cls)


def test_candidate_profile_schema_rejects_malformed_us():
    schema = json.loads((default_paths().format_dir / "schemas" / "candidate_profile.schema.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"work_authorization": {"us": "requires-sponsorship"}}, schema)  # bare string
    jsonschema.validate({"work_authorization": {"us": {"status": "requires-sponsorship"}}}, schema)  # ok
