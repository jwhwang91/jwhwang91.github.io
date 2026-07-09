"""JobOps — local viewer/orchestrator over the application pipeline (MASTER_PLAN §14 Phase 11).

Design stance: this backend is NOT a second brain. Every WRITE shells out to
`python main.py --json <subcommand>`, so CLI-driven and UI-driven flows produce
byte-identical artifacts. Every READ renders the schema-validated artifacts that already
exist on disk. No pipeline logic is reimplemented here.

Privacy: binds to localhost only; makes zero non-localhost network calls; never bundles,
uploads, or copies Applications/ data. Application data lives in gitignored Applications/
(relocatable via JOBOPS_APPLICATIONS for isolation).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi import Body, FastAPI, HTTPException, Request           # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse  # noqa: E402

from portfolio.cli import _app_summary                              # read-only artifact summary  # noqa: E402
from portfolio.paths import default_paths                           # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,80}$")
CLI_TIMEOUT = 120
# LLM slash-command contracts the runner can drive (same Format/prompts/*.md the CLI uses).
LLM_STEPS = {"jd-parse", "jd-match", "resume-plan", "interview-pack", "coding-pack",
             "rejection", "evolve-ledger"}

app = FastAPI(title="JobOps", docs_url=None, redoc_url=None)

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver"}   # testserver: starlette TestClient


@app.middleware("http")
async def _reject_non_loopback_host(request: Request, call_next):
    """Defeat DNS rebinding: binding to 127.0.0.1 does not stop a browser from resolving an
    attacker domain to loopback, so we must also reject any non-loopback Host header. Without
    this the unauthenticated API could be read/written cross-origin after a rebind."""
    raw = (request.headers.get("host") or "").strip()
    if raw.startswith("["):                                  # [::1]:8765 -> ::1
        host = raw[1:raw.index("]")] if "]" in raw else raw
    else:
        host = raw.rsplit(":", 1)[0] if ":" in raw else raw  # 127.0.0.1:8765 -> 127.0.0.1
    if host not in _LOOPBACK_HOSTS:
        return JSONResponse({"ok": False, "error": f"non-loopback Host rejected: {raw!r}"}, status_code=400)
    return await call_next(request)


# --------------------------------------------------------------------------- helpers

def _valid_slug(slug: str) -> str:
    if not SLUG_RE.match(slug or ""):
        raise HTTPException(400, f"invalid slug: {slug!r}")
    return slug


def run_cli(args: list[str]) -> dict:
    """Run `python main.py --json <args>` at the repo root and return its JSON envelope.
    The child inherits our env (so JOBOPS_APPLICATIONS isolation propagates)."""
    try:
        proc = subprocess.run(
            [sys.executable, "main.py", "--json", *args],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=CLI_TIMEOUT, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"CLI timed out after {CLI_TIMEOUT}s: {' '.join(args)}"}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "exit_code": proc.returncode,
                "error": (proc.stderr or proc.stdout or "no output").strip()[:2000]}


def _app_dir(slug: str) -> Path:
    return default_paths().applications / _valid_slug(slug)


# --------------------------------------------------------------------------- UI shell

@app.get("/", response_class=HTMLResponse)
def index():
    idx = STATIC / "index.html"
    if not idx.exists():
        return HTMLResponse("<h1>JobOps</h1><p>frontend not built</p>", status_code=200)
    return HTMLResponse(idx.read_text(encoding="utf-8"))


@app.get("/app.js")
def appjs():
    return FileResponse(STATIC / "app.js", media_type="application/javascript")


# --------------------------------------------------------------------------- reads (render artifacts)

@app.get("/api/track")
def api_track(open: bool = False, closed: bool = False):
    args = ["track"] + (["--open"] if open else []) + (["--closed"] if closed else [])
    return run_cli(args)


@app.get("/api/app/{slug}")
def api_app(slug: str):
    """Read-only summary of one application's artifacts (no pipeline side effects)."""
    if not _app_dir(slug).exists():
        raise HTTPException(404, f"no application {slug!r}")
    return {"slug": slug, "summary": _app_summary(default_paths(), slug)}


@app.get("/api/artifact/{slug}/{relpath:path}")
def api_artifact(slug: str, relpath: str):
    """Serve one artifact for display. Path-traversal-safe: must resolve inside the app dir."""
    base = _app_dir(slug).resolve()
    target = (base / relpath).resolve()
    if not (target == base or base in target.parents) or not target.is_file():
        raise HTTPException(404, "artifact not found")
    suffix = target.suffix.lower()
    if suffix == ".html":
        return HTMLResponse(target.read_text(encoding="utf-8"))
    if suffix == ".pdf":
        return FileResponse(target, media_type="application/pdf")
    if suffix in (".md", ".txt", ".yaml", ".yml", ".json"):
        return PlainTextResponse(target.read_text(encoding="utf-8"))
    return FileResponse(target)


# --------------------------------------------------------------------------- writes (via the CLI)

@app.post("/api/new")
def api_new(body: dict = Body(...)):
    slug = _valid_slug(body.get("slug", ""))
    args = ["new", slug]
    for flag in ("company", "role", "url", "positioning"):
        if body.get(flag):
            args += [f"--{flag}", body[flag]]
    res = run_cli(args)
    if res.get("ok") and body.get("jd_text"):
        (_app_dir(slug) / "jd.txt").write_text(body["jd_text"], encoding="utf-8")
        res["jd_parse"] = run_cli(["jd", "parse", slug])
    return res


@app.post("/api/jd/confirm")
def api_jd_confirm(body: dict = Body(...)):
    return run_cli(["jd", "confirm", _valid_slug(body.get("slug", ""))])


@app.post("/api/match")
def api_match(body: dict = Body(...)):
    return run_cli(["match", _valid_slug(body.get("slug", ""))])


@app.post("/api/match/confirm")
def api_match_confirm(body: dict = Body(...)):
    return run_cli(["match", "confirm", _valid_slug(body.get("slug", ""))])


@app.post("/api/resume")
def api_resume(body: dict = Body(...)):
    """Save the resume.yaml edit surface (a human edit, as in the CLI flow), then validate."""
    slug = _valid_slug(body.get("slug", ""))
    if not _app_dir(slug).exists():
        raise HTTPException(404, f"no application {slug!r}")
    if "yaml_text" in body:
        (_app_dir(slug) / "resume.yaml").write_text(body["yaml_text"], encoding="utf-8")
    return run_cli(["validate", slug, "--stage", "resume"])


@app.post("/api/render")
def api_render(body: dict = Body(...)):
    return run_cli(["render", _valid_slug(body.get("slug", ""))])


@app.post("/api/status")
def api_status(body: dict = Body(...)):
    slug = _valid_slug(body.get("slug", ""))
    args = ["status", slug, body.get("status", "")]
    if body.get("note"):
        args += ["--note", body["note"]]
    if body.get("acknowledge_risk"):
        args += ["--acknowledge-risk"]
    return run_cli(args)


@app.post("/api/pdfcheck")
def api_pdfcheck(body: dict = Body(...)):
    return run_cli(["pdfcheck", _valid_slug(body.get("slug", ""))])


@app.post("/api/pack/{kind}")
def api_pack(kind: str, body: dict = Body(...)):
    if kind not in ("interview", "coding"):
        raise HTTPException(400, "kind must be interview|coding")
    return run_cli(["pack", kind, _valid_slug(body.get("slug", ""))])


@app.post("/api/log")
def api_log(body: dict = Body(...)):
    return run_cli(["log", _valid_slug(body.get("slug", "")), "--note", body.get("note", "")])


@app.post("/api/lessons/compile")
def api_lessons():
    return run_cli(["lessons", "compile"])


# --------------------------------------------------------------------------- LLM runner

def _headless_enabled() -> bool:
    return os.environ.get("JOBOPS_HEADLESS") == "1" and shutil.which("claude") is not None


@app.post("/api/llm/{step}")
def api_llm(step: str, body: dict = Body(...)):
    """One runner interface for the LLM steps. Defaults to MANUAL (returns the slash
    command to run in Claude Code); with JOBOPS_HEADLESS=1 and claude on PATH it drives
    headless Claude Code executing the same Format/prompts/*.md contract."""
    if step not in LLM_STEPS:
        raise HTTPException(400, f"unknown step {step!r}")
    slug = _valid_slug(body.get("slug", "")) if body.get("slug") else ""
    command = f"/{step} {slug}".strip()
    if not _headless_enabled():
        return {"mode": "manual", "command": command,
                "instruction": f"Run `{command}` in Claude Code (headless off), then continue."}
    try:
        proc = subprocess.run(["claude", "-p", command], cwd=str(REPO_ROOT),
                              capture_output=True, text=True, timeout=900, check=False)
    except subprocess.TimeoutExpired:
        return {"mode": "headless", "command": command, "ok": False,
                "error": f"headless Claude timed out after 900s on {command}"}
    return {"mode": "headless", "command": command, "exit_code": proc.returncode,
            "output": (proc.stdout or "")[-4000:], "error": (proc.stderr or "")[-2000:]}


def serve(host: str = "127.0.0.1", port: int = 8765):
    import uvicorn
    if host not in ("127.0.0.1", "localhost", "::1"):        # privacy: localhost only
        raise SystemExit(f"refusing to bind non-localhost host {host!r}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    serve()
