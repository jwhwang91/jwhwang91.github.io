"""End-to-end ATS gate: PASS artifacts, coverage FAIL, unclaimable-term error,
acronym enforcement, pdfcheck."""
import dataclasses
from pathlib import Path

import yaml

from portfolio.cli import main
from portfolio.paths import default_paths

SAMPLE = Path(__file__).parent / "fixtures" / "sample_output"
JD = Path(__file__).parent / "fixtures" / "jds" / "tesla-adas-validation.txt"


def _scoped(tmp):
    return dataclasses.replace(default_paths(), applications=Path(tmp) / "Applications",
                               dist=Path(tmp) / "dist", private=default_paths().private)


def _setup(paths, slug="tesla"):
    app = paths.applications / slug
    app.mkdir(parents=True)
    (app / "jd.txt").write_text(JD.read_text(encoding="utf-8"), encoding="utf-8")
    for f in ("jd.parsed.yaml", "match.yaml", "resume.yaml"):
        (app / f).write_text((SAMPLE / f).read_text(encoding="utf-8"), encoding="utf-8")
    (app / "application.yaml").write_text(yaml.safe_dump(
        {"schema": "application/v1", "id": slug, "positioning": "adas-av-validation",
         "status": "matched", "status_history": []}), encoding="utf-8")
    return app


def _report(app):
    return yaml.safe_load((app / "gate_report.yaml").read_text())


def test_gate_passes_end_to_end(tmp_path):
    paths = _scoped(tmp_path)
    app = _setup(paths)
    assert main(["render", "tesla"], paths=paths) == 0
    rep = _report(app)
    assert rep["verdict"] == "PASS"
    assert rep["must_have_coverage"] == "4/4"
    assert rep["recommendation"] == "Apply"
    for f in ("gate_report.md", "checklist.md", "changes.md", "audit.json",
              "out/resume_ats.txt", "out/resume_ats.html", "out/resume_ats.md"):
        assert (app / f).exists(), f
    assert yaml.safe_load((app / "application.yaml").read_text())["status"] == "gated"


def test_removing_supported_must_have_fails_with_feedback(tmp_path):
    paths = _scoped(tmp_path)
    app = _setup(paths)
    r = yaml.safe_load((app / "resume.yaml").read_text())
    r["skills"][0]["items"] = ["Log Replay", "Target Object Selection (TOS/ODP)"]  # drop HIL + MIL
    r["experience"][0]["bullets"] = [b for b in r["experience"][0]["bullets"]
                                     if "HIL" not in b["text"] and "MIL" not in b["text"]]
    (app / "resume.yaml").write_text(yaml.safe_dump(r))
    assert main(["render", "tesla"], paths=paths) == 2       # gate FAIL exits 2
    assert (app / "gate_feedback.yaml").exists()
    assert not (app / "out" / "resume_ats.txt").exists()      # ATS render deleted on FAIL
    fb = yaml.safe_load((app / "gate_feedback.yaml").read_text())
    assert any(m["term"] == "hil" for m in fb["missing_supported_must_haves"])


def test_unsupported_term_in_text_is_error(tmp_path):
    paths = _scoped(tmp_path)
    app = _setup(paths)
    m = yaml.safe_load((app / "match.yaml").read_text())
    m["classifications"].append({"term": "functional-safety", "support": "unsupported",
                                 "requirement": "nice", "matched_tier": "exact", "claim_ids": [], "source": "registry"})
    (app / "match.yaml").write_text(yaml.safe_dump(m))
    r = yaml.safe_load((app / "resume.yaml").read_text())
    r["experience"][0]["bullets"].append(
        {"text": "Worked with ISO 26262 functional safety across the program.",
         "claims": ["hmc-validation-workflow"], "keywords": []})
    (app / "resume.yaml").write_text(yaml.safe_dump(r))
    assert main(["render", "tesla"], paths=paths) == 2
    assert any("Q16" in e for e in _report(app)["errors"])


def test_missing_acronym_expansion_is_error(tmp_path):
    paths = _scoped(tmp_path)
    app = _setup(paths)
    r = yaml.safe_load((app / "resume.yaml").read_text())
    r["skills"][0]["items"] = ["HIL", "Model-in-the-Loop (MIL/MILS)", "Log Replay",
                               "Target Object Selection (TOS/ODP)"]  # bare HIL, no ats_form
    (app / "resume.yaml").write_text(yaml.safe_dump(r))
    main(["render", "tesla"], paths=paths)
    assert any("Q10" in e for e in _report(app)["errors"])


def test_pdfcheck_blocks_textless_pdf(tmp_path):
    paths = _scoped(tmp_path)
    app = _setup(paths)
    main(["render", "tesla"], paths=paths)
    (app / "out" / "resume_final.pdf").write_bytes(b"%PDF-1.4\n%image-only, no text layer\n%%EOF\n")
    assert main(["pdfcheck", "tesla"], paths=paths) == 1


# --- review-finding regressions ---

def test_fabricated_skill_chip_fails(tmp_path):
    paths = _scoped(tmp_path)
    app = _setup(paths)
    r = yaml.safe_load((app / "resume.yaml").read_text())
    r["skills"].append({"label": "Platforms", "items": ["AUTOSAR", "Kubernetes"], "keywords": []})
    (app / "resume.yaml").write_text(yaml.safe_dump(r))
    assert main(["render", "tesla"], paths=paths) == 2
    assert any("skills chip" in e and "Q1" in e for e in _report(app)["errors"])


def test_render_requires_confirmed_match(tmp_path):
    import pytest
    paths = _scoped(tmp_path)
    app = _setup(paths)
    (app / "match.yaml").unlink()  # no match -> gating would be vacuously 100%
    with pytest.raises(FileNotFoundError):
        main(["render", "tesla"], paths=paths)


def test_hedge_must_sit_in_the_terms_own_clause():
    from portfolio.score import score_resume
    from portfolio.taxonomy import Taxonomy
    tax = Taxonomy.load(default_paths())
    policy = yaml.safe_load((default_paths().context / "facts" / "phrasing_policy.yaml").read_text())
    cls = [{"term": "hil", "requirement": "must", "support": "partial", "claim_ids": ["c1"]}]
    # HIL asserted with an ownership verb; the hedge qualifies a DIFFERENT co-mentioned term
    bypass = "- Independently developed Hardware-in-the-Loop (HIL/HILS) benches, with hands-on experience with dynamometer rigs."
    errs = [v.message for v in score_resume(bypass, cls, tax, policy, "", set())["violations"] if "Q17" in v.message]
    assert errs
    # control: hedge in HIL's own clause -> OK
    ok = "- Familiar with Hardware-in-the-Loop (HIL/HILS) benches."
    assert not [v for v in score_resume(ok, cls, tax, policy, "", set())["violations"] if "Q17" in v.message]
