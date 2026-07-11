"""One-click end-to-end resume generation for a Discover role.

Runs the full pipeline headlessly in a background thread and exposes live progress via an
in-memory status dict the UI polls:

    new -> scan -> /jd-parse -> confirm G1 -> match -> /jd-match -> confirm G2
        -> /resume-plan -> render (loop until the ATS gate PASSes) -> export PDF

Gates auto-confirm; the truthfulness back-check still makes fabrication impossible (every
bullet must cite a confirmed claim and the ATS gate runs on every render). Requires
JOBOPS_HEADLESS=1 and the `claude` CLI on PATH. Owner "what to fix" feedback is written to
Applications/<slug>/revision_request.md, which the resume-plan step reads and applies.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_TIMEOUT = 300
CLAUDE_TIMEOUT = 900
MAX_RENDER_TRIES = 3
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,80}$")
EFFORTS = {"low", "medium", "high", "xhigh", "max", "ultracode"}

STEPS_FULL = [
    ("new", "Create application"), ("scan", "Scan JD"), ("parse", "Parse JD (Claude)"),
    ("g1", "Confirm parse (G1)"), ("match", "Match vs registry"), ("jdmatch", "Classify keywords (Claude)"),
    ("g2", "Confirm match (G2)"), ("plan", "Draft resume (Claude)"), ("render", "Render + ATS gate"),
    ("pdf", "Export PDF"),
]
STEPS_REVISE = [("plan", "Revise resume (Claude)"), ("render", "Render + ATS gate"), ("pdf", "Export PDF")]

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


# --------------------------------------------------------------------------- helpers
def _apps_dir() -> Path:
    from portfolio.paths import default_paths
    return default_paths().applications


def headless_ready() -> tuple[bool, str]:
    if os.environ.get("JOBOPS_HEADLESS") != "1":
        return False, "Headless mode is off — restart the server with JOBOPS_HEADLESS=1 (needs the `claude` CLI)."
    if not shutil.which("claude"):
        return False, "The `claude` CLI is not on PATH."
    return True, ""


def _cli(args: list[str]) -> dict:
    try:
        p = subprocess.run([sys.executable, "main.py", "--json", *args], cwd=str(REPO_ROOT),
                           capture_output=True, text=True, timeout=CLI_TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timed out: main.py {' '.join(args)}"}
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": (p.stderr or p.stdout or "no output").strip()[:400]}


def _claude(command: str) -> dict:
    model = os.environ.get("JOBOPS_MODEL", "claude-opus-4-8")
    effort = os.environ.get("JOBOPS_EFFORT", "max").strip().lower()
    if effort not in EFFORTS:
        effort = "max"
    # acceptEdits: the skill may WRITE its artifact but cannot run the shell — the orchestrator
    # runs every CLI step, so the headless agent never executes arbitrary commands.
    argv = ["claude", "-p", "--permission-mode", "acceptEdits", "--model", model, "--effort", effort, command]
    try:
        p = subprocess.run(argv, cwd=str(REPO_ROOT), capture_output=True, text=True,
                           timeout=CLAUDE_TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"headless Claude timed out on {command}"}
    return {"ok": p.returncode == 0, "error": (p.stderr or "")[-400:]}


def _chrome() -> str | None:
    for c in ("google-chrome", "chromium", "chromium-browser"):
        if shutil.which(c):
            return shutil.which(c)
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    return mac if Path(mac).exists() else None


def _pdf(slug: str) -> dict:
    out = _apps_dir() / slug / "out"
    html, pdf = out / "resume_ats.html", out / "resume_final.pdf"
    if not html.exists():
        return {"ok": False, "error": "resume_ats.html missing"}
    chrome = _chrome()
    if not chrome:
        return {"ok": False, "error": "no Chrome/Chromium found for PDF export"}
    try:
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf}", html.resolve().as_uri()],
                       capture_output=True, text=True, timeout=120, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "PDF export timed out"}
    return {"ok": pdf.exists(), "error": "" if pdf.exists() else "PDF was not produced"}


def _verdict(slug: str) -> dict | None:
    gr = _apps_dir() / slug / "gate_report.yaml"
    if not gr.exists():
        return None
    try:
        import yaml
        g = yaml.safe_load(gr.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    return {k: g.get(k) for k in ("verdict", "recommendation", "must_have_coverage", "unsupported_ratio")}


# --------------------------------------------------------------------------- status
def _init(slug: str, steps) -> dict:
    return {"slug": slug, "phase": "running", "ok": False, "error": None, "verdict": None, "pdf": False,
            "steps": [{"key": k, "label": l, "state": "pending"} for k, l in steps], "log": []}


def _set(slug: str, key: str, state: str, msg: str | None = None) -> None:
    with _LOCK:
        st = _JOBS.get(slug)
        if not st:
            return
        for s in st["steps"]:
            if s["key"] == key:
                s["state"] = state
        if msg:
            st["log"].append(msg)


def _fail(slug: str, key: str, err: str | None) -> bool:
    _set(slug, key, "fail")
    with _LOCK:
        st = _JOBS.get(slug)
        if st:
            st["phase"], st["error"] = "error", err or "step failed"
    return False


def _finish(slug: str) -> None:
    with _LOCK:
        st = _JOBS.get(slug)
        if st and st["phase"] != "error":
            st["phase"], st["ok"] = "done", True


def status(slug: str) -> dict | None:
    with _LOCK:
        st = _JOBS.get(slug)
        if not st:
            return None
        return json.loads(json.dumps(st))  # cheap deep copy for a stable snapshot


def _step_cli(slug: str, key: str, args: list[str], okmsg: str | None = None) -> bool:
    _set(slug, key, "active")
    r = _cli(args)
    if isinstance(r, dict) and r.get("ok") is False:
        return _fail(slug, key, r.get("error"))
    _set(slug, key, "ok", okmsg)
    return True


def _artifact(slug: str, rel: str) -> Path:
    return _apps_dir() / slug / rel


def _queue_empty(slug: str) -> tuple[bool, str]:
    m = _artifact(slug, "match.yaml")
    if not m.exists():
        return (False, "match.yaml missing after /jd-match")
    try:
        import yaml
        q = (yaml.safe_load(m.read_text(encoding="utf-8")) or {}).get("queue")
    except Exception:
        return (False, "match.yaml unreadable after /jd-match")
    if q:
        return (False, f"{len(q)} keyword(s) still unclassified — /jd-match did not finish")
    return (True, "")


def _step_claude(slug: str, key: str, command: str, verify) -> bool:
    """Run a headless Claude step, then trust the ARTIFACT, not the exit code — under scoped
    (acceptEdits) permissions the skill writes its file but cannot run the CLI to self-confirm."""
    _set(slug, key, "active")
    _claude(command)
    ok, msg = verify()
    if not ok:
        return _fail(slug, key, msg)
    _set(slug, key, "ok")
    return True


# --------------------------------------------------------------------------- pipeline
def _render_loop(slug: str) -> bool:
    resume = _artifact(slug, "resume.yaml")
    for i in range(MAX_RENDER_TRIES):
        _set(slug, "plan", "active")
        _claude(f"/resume-plan {slug}")
        if not resume.exists():
            return _fail(slug, "plan", "headless /resume-plan did not write resume.yaml")
        _set(slug, "plan", "ok")
        _set(slug, "render", "active")
        _cli(["render", slug])
        v = _verdict(slug)
        with _LOCK:
            if _JOBS.get(slug):
                _JOBS[slug]["verdict"] = v
        if v and v.get("verdict") == "PASS":
            _set(slug, "render", "ok", f"Gate PASS — coverage {v.get('must_have_coverage')}")
            return True
        _set(slug, "render", "warn", f"Gate not passing yet (try {i + 1}/{MAX_RENDER_TRIES})")
    return _fail(slug, "render", "resume did not pass the ATS gate after retries")


def _pdf_step(slug: str) -> None:
    _set(slug, "pdf", "active")
    r = _pdf(slug)
    if not r.get("ok"):
        _set(slug, "pdf", "warn", r.get("error") or "PDF export failed")
        return
    with _LOCK:
        if _JOBS.get(slug):
            _JOBS[slug]["pdf"] = True
    _set(slug, "pdf", "ok", "resume_final.pdf ready")


def _run_full(slug: str, company: str, positioning: str, jd_text: str, emphasis: str) -> None:
    try:
        d = _apps_dir() / slug
        _set(slug, "new", "active")
        if not d.exists():
            r = _cli(["new", slug] + (["--company", company] if company else [])
                     + (["--positioning", positioning] if positioning else []))
            if isinstance(r, dict) and r.get("ok") is False:
                _fail(slug, "new", r.get("error"))
                return
        d.mkdir(parents=True, exist_ok=True)
        (d / "jd.txt").write_text(jd_text, encoding="utf-8")
        if emphasis.strip():
            (d / "revision_request.md").write_text(f"Owner emphasis for the draft:\n{emphasis.strip()}\n", encoding="utf-8")
        _set(slug, "new", "ok", f"Application {slug} ready")

        if not _step_cli(slug, "scan", ["jd", "parse", slug]):
            return
        if not _step_claude(slug, "parse", f"/jd-parse {slug}",
                            lambda: (True, "") if _artifact(slug, "jd.parsed.yaml").exists()
                            else (False, "headless /jd-parse did not write jd.parsed.yaml")):
            return
        if not _step_cli(slug, "g1", ["jd", "confirm", slug], "Parse confirmed (G1)"):
            return
        if not _step_cli(slug, "match", ["match", slug]):
            return
        if not _step_claude(slug, "jdmatch", f"/jd-match {slug}", lambda: _queue_empty(slug)):
            return
        if not _step_cli(slug, "g2", ["match", "confirm", slug], "Match confirmed (G2)"):
            return
        if not _render_loop(slug):
            return
        _pdf_step(slug)
        _finish(slug)
    except Exception as e:  # never leave a thread's job stuck in "running"
        _fail(slug, "plan", f"unexpected error: {e}")


def _run_revise(slug: str, feedback: str) -> None:
    try:
        (_apps_dir() / slug / "revision_request.md").write_text(
            f"Owner revision request:\n{feedback.strip()}\n", encoding="utf-8")
        if not _render_loop(slug):
            return
        _pdf_step(slug)
        _finish(slug)
    except Exception as e:
        _fail(slug, "plan", f"unexpected error: {e}")


# --------------------------------------------------------------------------- public API
def start(slug: str, company: str, positioning: str, jd_text: str, emphasis: str = "") -> dict:
    ok, err = headless_ready()
    if not ok:
        return {"ok": False, "error": err}
    if not SLUG_RE.match(slug or ""):
        return {"ok": False, "error": f"invalid slug: {slug!r}"}
    if len((jd_text or "").strip()) < 40:
        return {"ok": False, "error": "paste the full job description first"}
    with _LOCK:
        if _JOBS.get(slug, {}).get("phase") == "running":
            return {"ok": False, "error": "a generation is already running for this application"}
        _JOBS[slug] = _init(slug, STEPS_FULL)
    threading.Thread(target=_run_full, args=(slug, company, positioning, jd_text, emphasis), daemon=True).start()
    return {"ok": True, "slug": slug}


def start_revise(slug: str, feedback: str) -> dict:
    ok, err = headless_ready()
    if not ok:
        return {"ok": False, "error": err}
    if not SLUG_RE.match(slug or "") or not (_apps_dir() / slug).exists():
        return {"ok": False, "error": f"no application {slug!r}"}
    if not (feedback or "").strip():
        return {"ok": False, "error": "describe what to fix"}
    with _LOCK:
        if _JOBS.get(slug, {}).get("phase") == "running":
            return {"ok": False, "error": "a generation is already running for this application"}
        _JOBS[slug] = _init(slug, STEPS_REVISE)
    threading.Thread(target=_run_revise, args=(slug, feedback), daemon=True).start()
    return {"ok": True, "slug": slug}
