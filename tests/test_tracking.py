"""Lifecycle state machine, submit hard gate (G4), lessons/EVOLUTION rule, legacy compat."""
import dataclasses
from pathlib import Path

import pytest
import yaml

from portfolio.cli import main
from portfolio.paths import default_paths
from portfolio.tracking import legal_transitions


def _scoped(tmp):
    return dataclasses.replace(default_paths(), applications=Path(tmp) / "Applications",
                               dist=Path(tmp) / "dist", private=default_paths().private)


def _app(paths, slug="a", **over):
    folder = paths.applications / slug
    folder.mkdir(parents=True, exist_ok=True)
    doc = {"schema": "application/v1", "id": slug, "status": "draft", "status_history": []}
    doc.update(over)
    (folder / "application.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    return folder


def _status(paths, slug):
    return yaml.safe_load((paths.applications / slug / "application.yaml").read_text())["status"]


# --- state machine ---

def test_illegal_transition_rejected(tmp_path):
    paths = _scoped(tmp_path)
    _app(paths, "a", status="draft")
    with pytest.raises(ValueError):
        main(["status", "a", "submitted"], paths=paths)   # draft -> submitted is illegal


def test_auto_status_not_settable_by_hand(tmp_path):
    paths = _scoped(tmp_path)
    _app(paths, "a", status="drafted")
    with pytest.raises(ValueError):
        main(["status", "a", "gated"], paths=paths)        # gated is auto-advanced


def test_legal_human_transition(tmp_path):
    paths = _scoped(tmp_path)
    _app(paths, "a", status="gated")
    assert main(["status", "a", "approved"], paths=paths) == 0
    assert _status(paths, "a") == "approved"


def test_withdraw_from_any_and_abandon_pre_submit(tmp_path):
    paths = _scoped(tmp_path)
    _app(paths, "a", status="matched")
    assert main(["status", "a", "withdrawn"], paths=paths) == 0
    _app(paths, "b", status="gated")
    assert main(["status", "b", "abandoned"], paths=paths) == 0


def test_transition_table_shape():
    assert "abandoned" in legal_transitions("draft")
    assert "abandoned" not in legal_transitions("submitted")   # post-submit -> rejected/ghosted, not abandoned
    assert "withdrawn" in legal_transitions("interview")


# --- submit hard gate (G4) ---

def _mk_pdf(text: str) -> bytes:
    esc = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    content = ("BT /F1 12 Tf 72 720 Td (" + esc + ") Tj ET").encode("latin-1", "replace")
    objs = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
            b"<</Length " + str(len(content)).encode() + b">>stream\n" + content + b"\nendstream",
            b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    pdf = b"%PDF-1.4\n"
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offs:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += b"trailer\n<</Size " + str(len(objs) + 1).encode() + b"/Root 1 0 R>>\nstartxref\n" + str(xref).encode() + b"\n%%EOF"
    return pdf


def _approved(paths, slug="s", verdict="PASS", pdf_text=None, jd_sha=None):
    folder = _app(paths, slug, status="approved", jd_sha256=jd_sha)
    (folder / "jd.txt").write_text("JD text", encoding="utf-8")
    out = folder / "out"
    out.mkdir()
    (out / "resume_ats.txt").write_text("RESUME TEXT", encoding="utf-8")
    (folder / "gate_report.yaml").write_text(yaml.safe_dump({"schema": "gate_report/v1", "verdict": verdict}), encoding="utf-8")
    if pdf_text is not None:
        (out / "resume_final.pdf").write_bytes(_mk_pdf(pdf_text))
    return folder


def test_submit_blocked_without_pdf(tmp_path):
    paths = _scoped(tmp_path)
    _approved(paths, "s")
    with pytest.raises(ValueError, match="resume_final.pdf missing"):
        main(["status", "s", "submitted"], paths=paths)


def test_submit_blocked_on_gate_fail(tmp_path):
    paths = _scoped(tmp_path)
    _approved(paths, "s", verdict="FAIL", pdf_text="RESUME TEXT")
    with pytest.raises(ValueError, match="FAIL"):
        main(["status", "s", "submitted"], paths=paths)


def test_submit_blocked_high_risk_without_ack(tmp_path):
    paths = _scoped(tmp_path)
    _approved(paths, "s", verdict="HIGH_RISK", pdf_text="RESUME TEXT")
    with pytest.raises(ValueError, match="HIGH_RISK"):
        main(["status", "s", "submitted"], paths=paths)


def test_submit_blocked_on_textless_pdf(tmp_path):
    paths = _scoped(tmp_path)
    folder = _approved(paths, "s", pdf_text="RESUME TEXT")
    (folder / "out" / "resume_final.pdf").write_bytes(b"%PDF-1.4\n%no text\n%%EOF")
    with pytest.raises(ValueError, match="text-layer"):
        main(["status", "s", "submitted"], paths=paths)


def test_submit_blocked_on_jd_change(tmp_path):
    paths = _scoped(tmp_path)
    _approved(paths, "s", pdf_text="RESUME TEXT", jd_sha="deadbeef")  # stale sha != current jd.txt
    with pytest.raises(ValueError, match="jd.txt changed"):
        main(["status", "s", "submitted"], paths=paths)


def test_submit_succeeds_when_all_preconditions_met(tmp_path):
    paths = _scoped(tmp_path)
    _approved(paths, "s", verdict="PASS", pdf_text="RESUME TEXT")  # jd_sha None -> skipped
    assert main(["status", "s", "submitted"], paths=paths) == 0
    app = yaml.safe_load((paths.applications / "s" / "application.yaml").read_text())
    assert app["status"] == "submitted"
    assert app["submission"]["at"]


# --- lessons compile (EVOLUTION rule + anonymization lint) ---

def _closed_app(paths, slug, company, lessons, stage_reached="", status="rejected"):
    _app(paths, slug, status=status, company=company,
         outcome={"stage_reached": stage_reached}, lessons=lessons)


def test_lessons_rejects_post_ats_ats_scope(tmp_path, capsys):
    paths = _scoped(tmp_path)
    _closed_app(paths, "a", "AcmeCorp", [{"id": "L1", "scope": "ats", "text": "widen keywords"}],
                stage_reached="technical")   # reached a human -> post-ATS
    assert main(["lessons", "compile"], paths=paths) == 0
    out = capsys.readouterr().out
    assert "scope:ats rejected" in out or "post-ATS" in out
    draft = (paths.applications / "_ledger_draft.md").read_text()
    assert "widen keywords" not in draft


def test_lessons_anonymization_lint_fails_on_company(tmp_path):
    paths = _scoped(tmp_path)
    _closed_app(paths, "a", "AcmeCorp", [{"id": "L1", "scope": "targeting", "text": "AcmeCorp wanted ROS2"}])
    assert main(["lessons", "compile"], paths=paths) == 1   # company name leaked -> FAIL


def test_lessons_backbone_gap_goes_to_backlog(tmp_path):
    # scope context to tmp so the BACKLOG.md write never touches the real repo
    paths = dataclasses.replace(_scoped(tmp_path), context=Path(tmp_path) / "Context")
    (paths.context / "variants").mkdir(parents=True)
    _closed_app(paths, "a", "AcmeCorp", [{"id": "L1", "scope": "backbone-gap", "text": "no ROS2 experience"}])
    assert main(["lessons", "compile"], paths=paths) == 0
    assert "no ROS2 experience" in (paths.context / "variants" / "BACKLOG.md").read_text()


def test_lessons_clean_compile(tmp_path):
    paths = _scoped(tmp_path)
    _closed_app(paths, "a", "AcmeCorp", [{"id": "L1", "scope": "ats", "text": "mirror the acronym form"}],
                stage_reached="ats", status="rejected")   # ATS-stage -> allowed
    assert main(["lessons", "compile"], paths=paths) == 0
    assert "mirror the acronym form" in (paths.applications / "_ledger_draft.md").read_text()


# --- track + legacy compat + log ---

def test_track_includes_new_and_legacy(tmp_path, capsys):
    paths = _scoped(tmp_path)
    _app(paths, "new-app", status="gated", company="AcmeCorp")
    legacy = paths.applications / "legacy-app"
    legacy.mkdir(parents=True)
    (legacy / "result.md").write_text("Status: applied\nATS: pass\n", encoding="utf-8")
    assert main(["track"], paths=paths) == 0
    out = capsys.readouterr().out
    assert "new-app" in out and "legacy-app" in out


def test_log_event_appends(tmp_path):
    paths = _scoped(tmp_path)
    _app(paths, "a", status="submitted")
    assert main(["log", "a", "--note", "recruiter emailed"], paths=paths) == 0
    app = yaml.safe_load((paths.applications / "a" / "application.yaml").read_text())
    assert app["events"][-1]["note"] == "recruiter emailed"


# --- review-finding regressions ---

def test_submit_blocked_when_resume_txt_absent(tmp_path):
    paths = _scoped(tmp_path)
    folder = _approved(paths, "s", pdf_text="RESUME TEXT")
    (folder / "out" / "resume_ats.txt").unlink()      # pdf present, txt gone
    with pytest.raises(ValueError, match="resume_ats.txt missing"):
        main(["status", "s", "submitted"], paths=paths)


def test_submit_blocked_when_resume_edited_after_gate(tmp_path):
    paths = _scoped(tmp_path)
    folder = _approved(paths, "s", pdf_text="RESUME TEXT")
    gr = yaml.safe_load((folder / "gate_report.yaml").read_text())
    gr["resume_ats_sha256"] = "0" * 64               # gate graded different content
    (folder / "gate_report.yaml").write_text(yaml.safe_dump(gr))
    with pytest.raises(ValueError, match="changed since the gate"):
        main(["status", "s", "submitted"], paths=paths)


def test_submit_blocked_on_missing_verdict(tmp_path):
    paths = _scoped(tmp_path)
    folder = _approved(paths, "s", pdf_text="RESUME TEXT")
    (folder / "gate_report.yaml").write_text(yaml.safe_dump({"schema": "gate_report/v1"}))  # no verdict
    with pytest.raises(ValueError, match="verdict must be PASS"):
        main(["status", "s", "submitted"], paths=paths)


def test_terminal_status_is_absorbing(tmp_path):
    paths = _scoped(tmp_path)
    _app(paths, "a", status="rejected")
    with pytest.raises(ValueError):
        main(["status", "a", "withdrawn"], paths=paths)   # closed record cannot be mutated


def test_track_skips_malformed_application_yaml(tmp_path, capsys):
    paths = _scoped(tmp_path)
    _app(paths, "good", status="gated", company="AcmeCorp")
    bad = paths.applications / "bad"
    bad.mkdir()
    (bad / "application.yaml").write_text("just a bare string, not a mapping\n")
    assert main(["track"], paths=paths) == 0             # does not crash
    out = capsys.readouterr().out
    assert "good" in out and "skipped malformed" in out


def test_backbone_gap_lesson_is_anonymization_linted(tmp_path):
    paths = dataclasses.replace(_scoped(tmp_path), context=Path(tmp_path) / "Context")
    (paths.context / "variants").mkdir(parents=True)
    _closed_app(paths, "a", "AcmeCorp",
                [{"id": "L1", "scope": "backbone-gap", "text": "saw this at https://acme.example.com/jobs"}])
    assert main(["lessons", "compile"], paths=paths) == 1  # URL in backbone-gap -> FAIL, nothing written
    assert not (paths.context / "variants" / "BACKLOG.md").exists()
