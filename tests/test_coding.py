"""Coding-pack: deterministic format inference + bank-selection validation (MASTER_PLAN §8)."""
import dataclasses
from pathlib import Path

import yaml

from portfolio.cli import main
from portfolio.paths import default_paths
from portfolio.prep import infer_format, validate_coding_pack

BANK = yaml.safe_load((default_paths().context / "prep" / "coding_bank.yaml").read_text())
SAMPLE = Path(__file__).parent / "fixtures" / "sample_output"


def _errs(vs):
    return [v.message for v in vs if v.level == "error"]


def _sample_pack():
    return yaml.safe_load((SAMPLE / "coding_pack.yaml").read_text(encoding="utf-8"))


# --- format inference (acceptance: embedded fixture -> embedded-c) ---

def test_infer_embedded_c_from_embedded_fixture():
    jd = {"role_type": "embedded", "keywords": [{"term": "cpp"}, {"term": "misra-c"}, {"term": "autosar"}]}
    assert infer_format(jd)["format"] == "embedded-c"


def test_infer_embedded_c_from_keywords_only():
    jd = {"role_type": "software", "keywords": [{"term": "rtos"}]}
    assert infer_format(jd)["format"] == "embedded-c"


def test_infer_practical_python_for_validation():
    jd = {"role_type": "adas-validation", "keywords": [{"term": "python"}]}
    assert infer_format(jd)["format"] == "practical-python"


def test_infer_takehome_for_fullstack():
    assert infer_format({"role_type": "fullstack-saas", "keywords": []})["format"] == "takehome-plus-medium-lc"


def test_infer_leetcode_default():
    assert infer_format({"role_type": "backend", "keywords": [{"term": "algorithms"}]})["format"] == "leetcode-standard"


# --- bank integrity (acceptance: state-machine weighted for embedded) ---

def test_bank_has_state_machine_for_embedded():
    emb = [p for p in BANK["problems"] if "embedded-controls" in p["roles"]]
    assert sum(1 for p in emb if p["pattern"] == "state-machine") >= 2


def test_bank_ids_unique_and_patterns_declared():
    ids = [p["id"] for p in BANK["problems"]]
    assert len(ids) == len(set(ids))
    declared = set(BANK["patterns"])
    assert all(p["pattern"] in declared for p in BANK["problems"])


# --- validators ---

def test_sample_pack_validates():
    assert _errs(validate_coding_pack(_sample_pack(), BANK)) == []


def test_out_of_bank_id_rejected():
    pack = _sample_pack()
    pack["problem_ids"] = pack["problem_ids"] + ["cb-not-in-bank"]
    assert any("cb-not-in-bank" in e for e in _errs(validate_coding_pack(pack, BANK)))


def test_count_below_range_rejected():
    pack = _sample_pack()
    pack["problem_ids"] = ["cb-ah-01", "cb-ah-02"]
    assert any("20-40" in e for e in _errs(validate_coding_pack(pack, BANK)))


def test_duplicate_ids_do_not_inflate_count():
    # 10 distinct valid ids each listed twice must NOT pass as a 20-problem set
    distinct = [p["id"] for p in BANK["problems"]][:10]
    pack = {"schema": "coding_pack/v1", "application": "x", "format": "leetcode-standard",
            "problem_ids": distinct + distinct}
    assert any("20-40" in e for e in _errs(validate_coding_pack(pack, BANK)))


def test_infer_format_does_not_misfire_on_logic_technology():
    # 'log' must not match inside 'technology'/'logic' -> general Python role stays leetcode-standard
    jd = {"role_type": "backend", "keywords": [{"term": "python", "quote": "Own our core technology stack and apply sound business logic."}]}
    assert infer_format(jd)["format"] == "leetcode-standard"


def test_infer_format_still_matches_real_log_signal():
    jd = {"role_type": "backend", "keywords": [{"term": "python", "quote": "Analyze drive logs and log-replay output."}]}
    assert infer_format(jd)["format"] == "practical-python"


def test_out_of_band_difficulty_mix_rejected():
    # 20 all-easy problems for leetcode-standard (needs ~55% medium / ~15% hard) -> out of band
    easy = [p["id"] for p in BANK["problems"] if p["difficulty"] == "easy"][:20]
    pack = {"schema": "coding_pack/v1", "application": "x", "format": "leetcode-standard", "problem_ids": easy}
    errs = _errs(validate_coding_pack(pack, BANK))
    assert any("band" in e for e in errs)


# --- CLI end-to-end ---

def test_pack_coding_cli_end_to_end(tmp_path):
    paths = dataclasses.replace(default_paths(), applications=Path(tmp_path) / "Applications",
                                dist=Path(tmp_path) / "dist", private=default_paths().private)
    app = paths.applications / "t"
    (app / "prep").mkdir(parents=True)
    (app / "prep" / "coding_pack.yaml").write_text((SAMPLE / "coding_pack.yaml").read_text(), encoding="utf-8")
    assert main(["pack", "coding", "t"], paths=paths) == 0
    assert (app / "prep" / "coding_pack.md").exists()


def test_pack_coding_cli_rejects_out_of_bank(tmp_path):
    paths = dataclasses.replace(default_paths(), applications=Path(tmp_path) / "Applications",
                                dist=Path(tmp_path) / "dist", private=default_paths().private)
    app = paths.applications / "t"
    (app / "prep").mkdir(parents=True)
    pack = _sample_pack()
    pack["problem_ids"][0] = "cb-does-not-exist"
    (app / "prep" / "coding_pack.yaml").write_text(yaml.safe_dump(pack), encoding="utf-8")
    assert main(["pack", "coding", "t"], paths=paths) == 1
