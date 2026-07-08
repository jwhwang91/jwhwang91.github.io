"""Registry semantics: id uniqueness/format, confirmed-requires-evidence,
verbatim source_quote, proposed-not-citable, anchor resolution."""
import dataclasses
from pathlib import Path

import yaml

from portfolio.facts import load_registry, validate_registry
from portfolio.paths import default_paths

FIX = Path(__file__).parent / "fixtures" / "registry_minimal"

EMPLOYERS = """\
employers:
  acme-adas:
    organization: "Acme Motors"
    org_renderings: ["Acme Motors (ACME)", "ACME"]
    official_title: "ADAS Engineer"
    title_renderings: ["ADAS Engineer"]
    period: {start: "2020-01", end: null}
"""
POLICY = """\
strength_classes:
  ownership: {lexemes: [developed]}
  contribution: {lexemes: [supported]}
  exposure: {lexemes: ["familiar with"]}
numeric_whitelist: []
vague_claim_lexicon: []
"""
TITLES = "tracks: {demo: [Demo Engineer]}\n"
SOURCE = "note: Independently developed the gizmo for the team.\n"


def _fixture_paths():
    return dataclasses.replace(default_paths(), root=FIX, context=FIX / "Context")


def _build(tmp, claims):
    facts = tmp / "Context" / "facts" / "claims"
    facts.mkdir(parents=True)
    (tmp / "Context" / "facts" / "employers.yaml").write_text(EMPLOYERS)
    (tmp / "Context" / "facts" / "phrasing_policy.yaml").write_text(POLICY)
    (tmp / "Context" / "facts" / "positioning_titles.yaml").write_text(TITLES)
    (tmp / "Context" / "source.txt").write_text(SOURCE)
    (facts / "c.yaml").write_text(yaml.safe_dump({"claims": claims}))
    return dataclasses.replace(default_paths(), root=tmp, context=tmp / "Context")


def _errors(paths):
    return [v for v in validate_registry(paths) if v.level == "error"]


def _claim(**over):
    c = {
        "id": "acme-gizmo", "status": "confirmed", "anchor": "acme-adas",
        "statement": "Independently developed the gizmo.", "ownership": "independent",
        "deployment": "production",
        "evidence": [{"type": "repo", "ref": "Context/source.txt", "verifiable_by": "public"}],
        "source_quote": {"file": "Context/source.txt", "quote": "Independently developed the gizmo for the team."},
    }
    c.update(over)
    return c


# --- green: the committed fixture is clean ---

def test_fixture_registry_has_no_errors():
    errs = _errors(_fixture_paths())
    assert errs == [], [str(e) for e in errs]


def test_proposed_claim_is_not_citable():
    reg = load_registry(_fixture_paths())
    citable = {c["id"] for c in reg.citable()}
    assert "acme-widget" in citable            # confirmed -> citable
    assert "acme-calibration" not in citable   # proposed -> NOT citable


# --- red: doctored claims must fail ---

def test_non_verbatim_source_quote_fails(tmp_path):
    bad = _claim(source_quote={"file": "Context/source.txt", "quote": "This sentence never appears."})
    assert any("verbatim" in e.message for e in _errors(_build(tmp_path, [bad])))


def test_confirmed_claim_without_evidence_fails(tmp_path):
    bad = _claim()
    del bad["evidence"]
    assert any("evidence" in e.message for e in _errors(_build(tmp_path, [bad])))


def test_duplicate_id_fails(tmp_path):
    assert any("duplicate" in e.message for e in _errors(_build(tmp_path, [_claim(), _claim()])))


def test_unknown_anchor_fails(tmp_path):
    assert any("anchor" in e.message for e in _errors(_build(tmp_path, [_claim(anchor="ghost")])))


def test_bad_id_format_fails(tmp_path):
    # kebab-case pattern rejects underscores / capitals
    assert _errors(_build(tmp_path, [_claim(id="Bad_ID")]))


def test_placeholder_quote_skips_verbatim_check(tmp_path):
    ok = _claim(status="proposed", statement="<placeholder>",
                source_quote={"file": "Context/source.txt", "quote": "<placeholder>"})
    del ok["evidence"]  # proposed does not require evidence
    assert _errors(_build(tmp_path, [ok])) == []
