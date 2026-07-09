"""--json contract for every UI-wired subcommand (MASTER_PLAN §14 Phase 11).

stdout must be a single valid JSON envelope; the command runs identically to non-JSON mode.
"""
import contextlib
import dataclasses
import io
import json
from pathlib import Path

import pytest

from portfolio.cli import main
from portfolio.paths import default_paths

SAMPLE = Path(__file__).parent / "fixtures" / "sample_output"


def _paths(tmp):
    return dataclasses.replace(default_paths(), applications=Path(tmp) / "Applications",
                               dist=Path(tmp) / "dist", private=default_paths().private)


def _json(argv, paths):
    """Run `main` with argv, capture stdout, assert it's a single JSON object, return it."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main(argv, paths=paths)
    return json.loads(buf.getvalue())   # raises if stdout is not pure JSON


def _seed(paths, slug="tesla"):
    _json(["--json", "new", slug, "--company", "Tesla", "--positioning", "adas-av-validation"], paths)
    app = paths.applications / slug
    for f in ("jd.parsed.yaml", "match.yaml", "resume.yaml"):
        (app / f).write_text((SAMPLE / f).read_text(), encoding="utf-8")
    return app


def test_new_json_envelope(tmp_path):
    d = _json(["--json", "new", "t", "--company", "Tesla"], _paths(tmp_path))
    assert d["command"] == "new" and d["ok"] and d["exit_code"] == 0
    assert d["summary"]["status"] == "draft" and d["summary"]["company"] == "Tesla"


def test_render_json_surfaces_gate(tmp_path):
    paths = _paths(tmp_path)
    _seed(paths)
    d = _json(["--json", "render", "tesla"], paths)
    g = d["summary"]["gate_report"]
    assert g["verdict"] == "PASS" and g["must_have_coverage"] == "4/4"
    assert "out/resume_ats.html" in d["summary"]["artifacts"]
    # ATS honesty: no probability field is emitted
    assert "probability" not in g and "probability" not in d["summary"]


def test_status_json_advances(tmp_path):
    paths = _paths(tmp_path)
    _seed(paths)
    _json(["--json", "render", "tesla"], paths)
    d = _json(["--json", "status", "tesla", "approved"], paths)
    assert d["ok"] and d["summary"]["status"] == "approved"


def test_track_json_rows(tmp_path):
    paths = _paths(tmp_path)
    _seed(paths)
    d = _json(["--json", "track"], paths)
    assert isinstance(d["rows"], list) and d["rows"][0]["id"] == "tesla"


def test_match_json_slug_resolution(tmp_path):
    paths = _paths(tmp_path)
    _seed(paths)
    d = _json(["--json", "match", "confirm", "tesla"], paths)
    assert d["command"] == "match" and d["slug"] == "tesla"
    assert d["summary"]["match"]["confirmed"] is True


def test_error_case_is_ok_false(tmp_path):
    d = _json(["--json", "render", "does-not-exist"], _paths(tmp_path))
    assert d["ok"] is False and d["exit_code"] == 1 and d.get("error")


def test_json_only_applies_to_subcommands(tmp_path):
    # --json without a subcommand must not hijack the site build (returns None, builds site)
    paths = _paths(tmp_path)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["--json", "--list-variants"], paths=paths)
    # --list-variants ran (not JSON-wrapped); output is the human listing, not a JSON envelope
    with pytest.raises(json.JSONDecodeError):
        json.loads(buf.getvalue())


def test_all_wired_subcommands_emit_valid_json(tmp_path):
    paths = _paths(tmp_path)
    app = _seed(paths)
    _json(["--json", "render", "tesla"], paths)
    (app / "prep").mkdir(exist_ok=True)
    for f in ("interview_pack.yaml", "coding_pack.yaml"):
        (app / "prep" / f).write_text((SAMPLE / f).read_text(), encoding="utf-8")
    # each must produce a parseable envelope with the core keys
    for argv in (["jd", "parse", "tesla"], ["validate", "tesla", "--stage", "resume"],
                 ["gate", "tesla"], ["pdfcheck", "tesla"], ["pack", "interview", "tesla"],
                 ["pack", "coding", "tesla"], ["log", "tesla", "--note", "x"]):
        d = _json(["--json", *argv], paths)
        assert set(("command", "ok", "exit_code", "messages")) <= set(d)
