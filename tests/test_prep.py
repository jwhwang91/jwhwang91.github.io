"""Interview-pack validators: claim refs, partial->danger, STAR digits, forbidden phrasing."""
import dataclasses
from pathlib import Path

import pytest
import yaml

from portfolio.cli import main
from portfolio.facts import load_registry
from portfolio.paths import default_paths
from portfolio.prep import render_pack_md, validate_pack

SAMPLE = Path(__file__).parent / "fixtures" / "sample_output"
REG = load_registry(default_paths())
POLICY = yaml.safe_load((default_paths().context / "facts" / "phrasing_policy.yaml").read_text())


def _pack():
    return yaml.safe_load((SAMPLE / "interview_pack.yaml").read_text(encoding="utf-8"))


def _match():
    return yaml.safe_load((SAMPLE / "match.yaml").read_text(encoding="utf-8"))


def _errs(vs):
    return [v.message for v in vs if v.level == "error"]


def test_valid_sample_pack_passes():
    assert _errs(validate_pack(_pack(), _match(), REG, POLICY)) == []


def test_partial_keyword_requires_danger_question():
    match = {"classifications": [{"term": "canape", "support": "partial", "requirement": "nice"}]}
    errs = _errs(validate_pack(_pack(), match, REG, POLICY))   # sample has danger_questions: []
    assert any("canape" in e and "danger" in e for e in errs)


def test_adding_the_danger_question_clears_it():
    match = {"classifications": [{"term": "canape", "support": "partial", "requirement": "nice"}]}
    pack = _pack()
    pack["danger_questions"] = [{"keyword": "canape", "truthful_boundary": "exposure-level tooling only"}]
    assert not any("danger" in e for e in _errs(validate_pack(pack, match, REG, POLICY)))


def test_unbacked_star_digit_fails():
    pack = _pack()
    pack["project_walkthroughs"][0]["result"] = "Cut scenario-debugging time by 73 percent."  # 73 invented
    assert any("73" in e for e in _errs(validate_pack(pack, {}, REG, POLICY)))


def test_backed_star_digit_ok():
    # sample result cites hmc-bev-replay-metric (numbers 10, 5, 4, 5)
    assert not any("not backed" in e for e in _errs(validate_pack(_pack(), {}, REG, POLICY)))


def test_placeholder_result_skips_digit_check():
    pack = _pack()
    pack["project_walkthroughs"][0]["result"] = "Improved by <placeholder>%."
    assert not any("not backed" in e for e in _errs(validate_pack(pack, {}, REG, POLICY)))


def test_unconfirmed_claim_ref_fails():
    pack = _pack()
    pack["resume_deep_dive"][0]["claims"] = ["not-a-real-claim"]
    assert any("not-a-real-claim" in e for e in _errs(validate_pack(pack, {}, REG, POLICY)))


def test_forbidden_phrasing_fails():
    pack = _pack()
    pack["behavioral"] = [{"prompt": "I have 10 years of experience across the field.", "star": "x", "claims": []}]
    assert any("forbidden" in e for e in _errs(validate_pack(pack, {}, REG, POLICY)))


def test_render_md():
    md = render_pack_md(_pack())
    assert "# Interview prep" in md and "## Project walkthroughs" in md and "## Likely topics" in md


def test_pack_interview_cli_end_to_end(tmp_path):
    paths = dataclasses.replace(default_paths(), applications=Path(tmp_path) / "Applications",
                                dist=Path(tmp_path) / "dist", private=default_paths().private)
    app = paths.applications / "t"
    (app / "prep").mkdir(parents=True)
    (app / "match.yaml").write_text((SAMPLE / "match.yaml").read_text(), encoding="utf-8")
    (app / "prep" / "interview_pack.yaml").write_text((SAMPLE / "interview_pack.yaml").read_text(), encoding="utf-8")
    assert main(["pack", "interview", "t"], paths=paths) == 0
    assert (app / "prep" / "interview_pack.md").exists()


def test_pack_interview_rejects_deleted_danger_question(tmp_path):
    # acceptance: a partial keyword whose danger_question was deleted fails validation
    paths = dataclasses.replace(default_paths(), applications=Path(tmp_path) / "Applications",
                                dist=Path(tmp_path) / "dist", private=default_paths().private)
    app = paths.applications / "t"
    (app / "prep").mkdir(parents=True)
    match = _match()
    match["classifications"].append({"term": "canape", "support": "partial", "requirement": "nice",
                                     "matched_tier": "exact", "claim_ids": ["add-can-tooling"]})
    (app / "match.yaml").write_text(yaml.safe_dump(match), encoding="utf-8")
    (app / "prep" / "interview_pack.yaml").write_text((SAMPLE / "interview_pack.yaml").read_text(), encoding="utf-8")
    assert main(["pack", "interview", "t"], paths=paths) == 1   # canape partial, no danger question


# --- review-finding regressions (digit-fabrication holes) ---

def test_fabricated_number_in_action_field_fails():
    pack = _pack()
    pack["project_walkthroughs"][0]["action"] = "Cut false positives by 95% and shipped to 40 vehicles."
    assert any("95" in e for e in _errs(validate_pack(pack, {}, REG, POLICY)))


def test_fabricated_number_in_answer_sketch_fails():
    pack = _pack()
    pack["resume_deep_dive"][0]["answer_sketch"] = "Delivered a 40% latency reduction across 12 subsystems."
    assert any("40" in e for e in _errs(validate_pack(pack, {}, REG, POLICY)))


def test_placeholder_substring_does_not_disable_digit_check():
    pack = _pack()
    pack["project_walkthroughs"][0]["result"] = "Reduced false detections by 87% <placeholder>"
    assert any("87" in e for e in _errs(validate_pack(pack, {}, REG, POLICY)))


def test_decimal_fabrication_fails_even_when_integer_is_backed():
    pack = _pack()
    pack["project_walkthroughs"][0]["result"] = "Cut trips from 10 to 5.9 (each 4.87 hours)."
    errs = _errs(validate_pack(pack, {}, REG, POLICY))
    assert any("5.9" in e for e in errs) and any("4.87" in e for e in errs)


def test_pack_interview_requires_confirmed_match(tmp_path):
    paths = dataclasses.replace(default_paths(), applications=Path(tmp_path) / "Applications",
                                dist=Path(tmp_path) / "dist", private=default_paths().private)
    app = paths.applications / "t"
    (app / "prep").mkdir(parents=True)
    (app / "prep" / "interview_pack.yaml").write_text((SAMPLE / "interview_pack.yaml").read_text(), encoding="utf-8")
    with pytest.raises(FileNotFoundError):   # no confirmed match -> vacuous partial->danger net
        main(["pack", "interview", "t"], paths=paths)
