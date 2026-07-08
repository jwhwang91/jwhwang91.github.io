"""Schemas round-trip the real fact files and reject violation fixtures."""
import copy
import json

import jsonschema
import pytest

from portfolio.content import load_yaml
from portfolio.paths import default_paths

SCHEMAS = default_paths().format_dir / "schemas"


def _schema(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_real_domain_files_validate():
    facts = default_paths().context / "facts"
    jsonschema.validate(load_yaml(facts / "employers.yaml"), _schema("employers.schema.json"))
    jsonschema.validate(load_yaml(facts / "phrasing_policy.yaml"), _schema("phrasing_policy.schema.json"))
    jsonschema.validate(load_yaml(facts / "positioning_titles.yaml"), _schema("positioning_titles.schema.json"))


def test_real_claim_files_validate():
    schema = _schema("claim.schema.json")
    claims_dir = default_paths().context / "facts" / "claims"
    files = list(claims_dir.glob("*.yaml"))
    assert files, "no claim files found"
    for cf in files:
        jsonschema.validate(load_yaml(cf), schema)


VALID_CLAIM = {
    "claims": [{
        "id": "x-demo", "status": "proposed", "anchor": "acme",
        "statement": "Did a thing.", "ownership": "shared", "deployment": "prototype",
        "source_quote": {"file": "f.yaml", "quote": "Did a thing."},
    }]
}


def test_valid_claim_accepted():
    jsonschema.validate(VALID_CLAIM, _schema("claim.schema.json"))


@pytest.mark.parametrize("mutate", [
    lambda c: c["claims"][0].pop("id"),                     # missing required
    lambda c: c["claims"][0].pop("source_quote"),           # missing required
    lambda c: c["claims"][0].update(status="published"),    # bad status enum
    lambda c: c["claims"][0].update(ownership="boss"),       # bad ownership enum
    lambda c: c["claims"][0].update(deployment="live"),      # bad deployment enum
    lambda c: c["claims"][0].update(id="Bad_ID"),            # violates kebab-case pattern
])
def test_invalid_claims_rejected(mutate):
    doc = copy.deepcopy(VALID_CLAIM)
    mutate(doc)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, _schema("claim.schema.json"))
