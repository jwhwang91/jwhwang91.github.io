"""JobOps backend contract (MASTER_PLAN §14 Phase 11).

Isolated via JOBOPS_APPLICATIONS so no test touches the real Applications/. Every write
goes through `python main.py --json`, so UI-produced artifacts are byte-identical to the
CLI flow — the acceptance criterion is asserted directly.
"""
import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient   # noqa: E402

SAMPLE = Path(__file__).parent / "fixtures" / "sample_output"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    apps = tmp_path / "Applications"
    apps.mkdir()
    monkeypatch.setenv("JOBOPS_APPLICATIONS", str(apps))
    monkeypatch.delenv("JOBOPS_HEADLESS", raising=False)
    import ui.server as server
    c = TestClient(server.app, base_url="http://127.0.0.1")   # loopback Host passes the guard
    c.apps = apps
    return c


def _seed(client, slug="tesla"):
    r = client.post("/api/new", json={"slug": slug, "company": "Tesla", "positioning": "adas-av-validation"})
    assert r.status_code == 200 and r.json()["ok"]
    app = client.apps / slug
    for f in ("jd.parsed.yaml", "match.yaml", "resume.yaml"):
        (app / f).write_text((SAMPLE / f).read_text(), encoding="utf-8")
    return app


def test_serves_frontend(client):
    idx = client.get("/")
    assert idx.status_code == 200 and "JobOps" in idx.text
    js = client.get("/app.js")
    assert js.status_code == 200 and "screens" in js.text


def test_new_then_summary(client):
    _seed(client)
    r = client.get("/api/app/tesla")
    assert r.status_code == 200
    assert r.json()["summary"]["status"] == "draft"


def test_render_surfaces_gate_and_serves_preview(client):
    _seed(client)
    r = client.post("/api/render", json={"slug": "tesla"})
    body = r.json()
    assert body["summary"]["gate_report"]["verdict"] == "PASS"
    # the rendered HTML artifact is served for preview
    a = client.get("/api/artifact/tesla/out/resume_ats.html")
    assert a.status_code == 200 and "<h1" in a.text.lower()


def test_status_flow(client):
    _seed(client)
    client.post("/api/render", json={"slug": "tesla"})
    r = client.post("/api/status", json={"slug": "tesla", "status": "approved"})
    assert r.json()["summary"]["status"] == "approved"


def test_track_lists_rows(client):
    _seed(client)
    r = client.get("/api/track")
    assert r.json()["rows"][0]["id"] == "tesla"


def test_match_confirm(client):
    _seed(client)
    r = client.post("/api/match/confirm", json={"slug": "tesla"})
    assert r.json()["summary"]["match"]["confirmed"] is True


def test_path_traversal_blocked(client):
    _seed(client)
    r = client.get("/api/artifact/tesla/../../../../etc/hosts")
    assert r.status_code == 404


def test_invalid_slug_rejected(client):
    r = client.post("/api/new", json={"slug": "../evil"})
    assert r.status_code == 400


def test_non_loopback_host_rejected(client):
    # DNS-rebinding defense: a non-loopback Host header must be refused before any handler
    r = client.get("/api/track", headers={"host": "evil.com:8765"})
    assert r.status_code == 400
    assert client.get("/api/track", headers={"host": "127.0.0.1:8765"}).status_code == 200


def test_resume_save_nonexistent_slug_is_404(client):
    r = client.post("/api/resume", json={"slug": "ghost", "yaml_text": "x: 1"})
    assert r.status_code == 404


def test_llm_manual_mode_default(client):
    _seed(client)
    r = client.post("/api/llm/interview-pack", json={"slug": "tesla"})
    body = r.json()
    assert body["mode"] == "manual" and body["command"] == "/interview-pack tesla"


def _fake_claude(monkeypatch):
    """Force headless mode and capture the argv without invoking real Claude."""
    import ui.server as server
    monkeypatch.setenv("JOBOPS_HEADLESS", "1")
    monkeypatch.setattr(server.shutil, "which", lambda name: "/usr/bin/claude")
    cap = {}

    class P:
        returncode, stdout, stderr = 0, "ok", ""

    monkeypatch.setattr(server.subprocess, "run", lambda argv, **kw: (cap.update(argv=argv) or P()))
    return cap


def test_headless_defaults_to_opus_4_8_and_max_effort(client, monkeypatch):
    cap = _fake_claude(monkeypatch)
    r = client.post("/api/llm/interview-pack", json={"slug": "tesla"})
    body = r.json()
    assert body["mode"] == "headless" and body["model"] == "claude-opus-4-8" and body["effort"] == "max"
    assert "--model" in cap["argv"] and "claude-opus-4-8" in cap["argv"]
    assert "--effort" in cap["argv"] and "max" in cap["argv"]


def test_headless_effort_env_override(client, monkeypatch):
    cap = _fake_claude(monkeypatch)
    monkeypatch.setenv("JOBOPS_EFFORT", "high")
    r = client.post("/api/llm/jd-parse", json={"slug": "tesla"})
    assert r.json()["effort"] == "high" and "high" in cap["argv"]


def test_headless_malformed_effort_falls_back_to_max(client, monkeypatch):
    cap = _fake_claude(monkeypatch)
    monkeypatch.setenv("JOBOPS_EFFORT", "turbo!!")   # not a valid level -> default
    r = client.post("/api/llm/jd-parse", json={"slug": "tesla"})
    assert r.json()["effort"] == "max" and "turbo!!" not in cap["argv"]


def test_headless_model_env_override(client, monkeypatch):
    cap = _fake_claude(monkeypatch)
    monkeypatch.setenv("JOBOPS_MODEL", "claude-sonnet-5")
    r = client.post("/api/llm/coding-pack", json={"slug": "tesla"})
    assert r.json()["model"] == "claude-sonnet-5" and "claude-sonnet-5" in cap["argv"]


def test_headless_malformed_model_falls_back(client, monkeypatch):
    cap = _fake_claude(monkeypatch)
    monkeypatch.setenv("JOBOPS_MODEL", "--dangerous flag")   # invalid -> fall back to default
    r = client.post("/api/llm/resume-plan", json={"slug": "tesla"})
    assert r.json()["model"] == "claude-opus-4-8" and "--dangerous flag" not in cap["argv"]


def test_ui_artifact_byte_identical_to_cli(client, tmp_path):
    """Acceptance: a UI-driven render produces the same bytes as a pure CLI render."""
    _seed(client)
    client.post("/api/render", json={"slug": "tesla"})
    ui_txt = (client.apps / "tesla" / "out" / "resume_ats.txt").read_bytes()

    # pure-CLI render into a separate isolated Applications dir
    import dataclasses
    from portfolio.cli import main
    from portfolio.paths import default_paths
    cli_apps = tmp_path / "cli-apps"
    paths = dataclasses.replace(default_paths(), applications=cli_apps, dist=tmp_path / "d",
                                private=default_paths().private)
    cli_apps.mkdir(parents=True)   # `new` creates the tesla/ folder itself
    main(["new", "tesla", "--company", "Tesla", "--positioning", "adas-av-validation"], paths=paths)
    for f in ("jd.parsed.yaml", "match.yaml", "resume.yaml"):
        (cli_apps / "tesla" / f).write_text((SAMPLE / f).read_text(), encoding="utf-8")
    main(["render", "tesla"], paths=paths)
    cli_txt = (cli_apps / "tesla" / "out" / "resume_ats.txt").read_bytes()

    assert ui_txt == cli_txt
