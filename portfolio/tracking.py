from __future__ import annotations

import csv as _csv
import datetime
import hashlib
import re
import sys
from pathlib import Path

from .content import load_yaml
from .paths import Paths

# ---------------------------------------------------------------------------
# Evolving pipeline — turn accumulated outcomes into ATS optimization.
#
# Each Applications/<name>/result.md carries a few controlled-vocab fields
# (Status, ATS, Stage reached, ...). gather_results() parses them and
# print_insights() (`--insights`) prints a deterministic scoreboard: how often
# the resume passed the company ATS filter (proxied by reaching a human), and
# which applications were knocked out before a human ever read them. The
# countable facts live here; pattern mining + ledger synthesis is Claude's job
# (see Context/variants/EVOLUTION.md + ATS_LEDGER.md).
#
# RESULT_FIELDS is the single source of truth for the field vocabulary; the
# Format/scaffold/result.md template must carry a "Label:" line for each (a
# regression test asserts they stay in sync).
# ---------------------------------------------------------------------------

RESULT_FIELDS = ("status", "ats", "applied", "outcome date", "stage reached", "why", "next move")
# Statuses/stages that imply a human read the resume (i.e. it cleared the ATS).
_HUMAN_STATUSES = {"screening", "interview", "offer", "hired"}
_HUMAN_STAGES = {"recruiter", "technical", "onsite", "offer"}


def parse_result(path: Path) -> dict[str, str]:
    """Parse a result.md into {field: value}, skipping unfilled <!-- ... --> placeholders."""
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z][A-Za-z ]*?):\s*(.*)$", line)
        if not m:
            continue
        key = m.group(1).strip().lower()
        if key not in RESULT_FIELDS:
            continue
        value = m.group(2).strip()
        if not value or value.startswith("<!--"):
            continue  # placeholder / unfilled
        data[key] = value
    return data


def gather_results(paths: Paths) -> list[dict[str, str]]:
    """One parsed record per application that has a result.md (with its folder name)."""
    if not paths.applications.exists():
        return []
    records = []
    for folder in sorted(paths.applications.iterdir()):
        result = folder / "result.md"
        if folder.is_dir() and result.exists():
            rec = parse_result(result)
            rec["name"] = folder.name
            records.append(rec)
    return records


def ats_passed(rec: dict[str, str]) -> bool | None:
    """True/False if known (explicit ATS field wins; else inferred from stage/status)."""
    ats = rec.get("ats", "").lower()
    if ats in ("pass", "fail"):
        return ats == "pass"
    if ats == "unknown":
        return None
    status = rec.get("status", "").lower()
    stage = rec.get("stage reached", "").lower()
    if status in _HUMAN_STATUSES or any(s in stage for s in _HUMAN_STAGES):
        return True
    if status == "rejected" and ("ats" in stage or "early" in stage or "auto" in stage):
        return False
    return None


def pdf_text_warning(folder: Path) -> str | None:
    """Best-effort: warn if a folder's PDF has ~no extractable text (the Print-to-PDF trap)."""
    pdfs = list(folder.glob("*.pdf"))
    if not pdfs:
        return None
    try:
        from pypdf import PdfReader
    except Exception:
        return None
    for pdf in pdfs:
        try:
            text = "".join((p.extract_text() or "") for p in PdfReader(str(pdf)).pages)
        except Exception:
            continue
        if len(text.strip()) < 50:
            return f"{pdf.name}: ~0 extractable text — re-export via browser 'Save as PDF'"
    return None


def print_insights(paths: Paths) -> None:
    # result.md content (and these defaults) may hold non-ASCII; keep the Windows
    # console from choking (cp949/cp1252) by forcing a tolerant UTF-8 stdout.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    records = gather_results(paths)
    if not records:
        print("No results yet. Outcomes are recorded in Applications/<name>/result.md.")
        return

    passed = [r for r in records if ats_passed(r) is True]
    failed = [r for r in records if ats_passed(r) is False]
    unknown = [r for r in records if ats_passed(r) is None]

    print(f"Applications: {len(records)}")
    by_status: dict[str, int] = {}
    for r in records:
        by_status[r.get("status", "—").lower()] = by_status.get(r.get("status", "—").lower(), 0) + 1
    print("  by status:", ", ".join(f"{k}:{v}" for k, v in sorted(by_status.items())))

    known = len(passed) + len(failed)
    rate = f"{len(passed)}/{known}" if known else "0/0"
    print(f"ATS-pass (reached a human): {rate}" + (f"   (+{len(unknown)} unknown)" if unknown else ""))

    if failed:
        print("\nATS-stage rejects (knocked out before a human read it):")
        for r in failed:
            why = r.get("why", "—")
            nxt = r.get("next move", "")
            print(f"  - {r['name']}: {why}" + (f"  -> {nxt}" if nxt else ""))
        print("  Note: a fast reject can be a keyword gap OR an auto-knockout (sponsorship/location).")
        print("  Mine the pattern: see Context/variants/EVOLUTION.md, then evolve ATS_LEDGER.md.")

    print("\nPer-application:")
    print(f"  {'name':<34} {'status':<10} {'ats':<8} {'stage':<16} outcome")
    for r in records:
        ap = ats_passed(r)
        ats = "pass" if ap is True else "fail" if ap is False else "?"
        print(f"  {r['name'][:33]:<34} {r.get('status','—')[:9]:<10} {ats:<8} "
              f"{r.get('stage reached','—')[:15]:<16} {r.get('outcome date','—')}")

    warnings = [(r["name"], w) for r in records
                if (w := pdf_text_warning(paths.applications / r["name"]))]
    if warnings:
        print("\nPDF text-layer WARNINGS (ATS would read these as blank):")
        for name, w in warnings:
            print(f"  ! {name}: {w}")


# ---------------------------------------------------------------------------
# Application lifecycle state machine + tracker (MASTER_PLAN §9). application.yaml
# is the single tracking truth per application; result.md is retired (the reader
# above is kept as a legacy compat path for track/insights).
# ---------------------------------------------------------------------------

_TERMINAL = {"hired", "rejected", "ghosted", "abandoned", "withdrawn"}
_PRE_SUBMIT = {"draft", "parsed", "matched", "drafted", "gated", "approved"}
_AUTO = {"parsed", "matched", "drafted", "gated"}   # advanced by their commands, not by hand
_POST_ATS = {"recruiter", "technical", "onsite", "offer"}

STATUS_FLOW = {
    "draft": {"parsed"},
    "parsed": {"matched"},
    "matched": {"drafted"},
    "drafted": {"gated"},
    "gated": {"approved", "drafted"},               # gated -> drafted = regenerate loop
    "approved": {"submitted", "gated"},             # approved -> gated = re-gate after edit
    "submitted": {"screen", "interview", "offer", "hired", "rejected", "ghosted"},
    "screen": {"interview", "offer", "hired", "rejected", "ghosted"},
    "interview": {"offer", "hired", "rejected", "ghosted"},
    "offer": {"hired", "rejected"},
}


def _today() -> str:
    return datetime.date.today().isoformat()


def _dump(path, doc) -> None:
    import yaml
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=4096), encoding="utf-8")


def legal_transitions(current: str) -> set[str]:
    nxt = set(STATUS_FLOW.get(current, set()))
    if current not in _TERMINAL:                    # terminal statuses are absorbing
        nxt.add("withdrawn")                        # any non-terminal -> withdrawn
        if current in _PRE_SUBMIT:
            nxt.add("abandoned")                    # any pre-submit -> abandoned
    return nxt


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pdf_text_ratio(pdf: Path, txt: Path) -> float:
    import difflib
    try:
        from pypdf import PdfReader
        extracted = "".join((p.extract_text() or "") for p in PdfReader(str(pdf)).pages)
    except Exception:
        extracted = ""
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    return difflib.SequenceMatcher(None, norm(extracted), norm(txt.read_text(encoding="utf-8"))).ratio()


def _check_submit_gate(paths: Paths, slug: str, app: dict, acknowledge_risk: bool) -> None:
    """Gate G4 — mechanically impossible to send an ungated, text-less, or silently
    edited resume. Raises ValueError listing every failed precondition."""
    folder = paths.applications / slug
    errs: list[str] = []
    if app.get("status") != "approved":
        errs.append(f"status must be 'approved' (is '{app.get('status')}')")

    gate_report = folder / "gate_report.yaml"
    gr = load_yaml(gate_report) if gate_report.exists() else None
    if gr is None:
        errs.append(f"no gate_report.yaml — run: python main.py render {slug}")
    else:
        verdict = gr.get("verdict")
        if verdict == "PASS":
            pass
        elif verdict == "HIGH_RISK" and acknowledge_risk:
            pass
        elif verdict == "HIGH_RISK":
            errs.append("gate verdict is HIGH_RISK — re-run with --acknowledge-risk to submit anyway")
        else:
            errs.append(f"gate verdict must be PASS to submit (is '{verdict}')")

    pdf, txt = folder / "out" / "resume_final.pdf", folder / "out" / "resume_ats.txt"
    if not pdf.exists():
        errs.append("out/resume_final.pdf missing (export resume_ats.html to PDF first)")
    elif not txt.exists():
        errs.append(f"out/resume_ats.txt missing — run: python main.py render {slug}")
    elif _pdf_text_ratio(pdf, txt) < 0.98:
        errs.append("PDF text-layer check FAILED (run: python main.py pdfcheck " + slug + ")")
    # bind the submitted resume to the exact text the gate graded
    if gr and txt.exists() and gr.get("resume_ats_sha256") \
            and _sha256_text(txt.read_text(encoding="utf-8")) != gr["resume_ats_sha256"]:
        errs.append("resume_ats.txt changed since the gate ran — re-render/re-gate before submitting")

    jd = folder / "jd.txt"
    if jd.exists() and app.get("jd_sha256") and _sha256_text(jd.read_text(encoding="utf-8")) != app["jd_sha256"]:
        errs.append("jd.txt changed since parse (jd_sha256 mismatch) — re-parse the JD")

    if errs:
        raise ValueError("cannot submit:\n  - " + "\n  - ".join(errs))


def set_status(paths: Paths, slug: str, status: str, note: str | None = None,
               acknowledge_risk: bool = False) -> int:
    folder = paths.applications / slug
    app_path = folder / "application.yaml"
    if not app_path.exists():
        raise FileNotFoundError(f"{app_path} missing — run: python main.py new {slug}")
    app = load_yaml(app_path)
    current = app.get("status", "draft")

    if status in _AUTO:
        raise ValueError(f"'{status}' is auto-advanced by its command (jd confirm / match confirm / render) — not set by hand")
    if status not in legal_transitions(current):
        raise ValueError(f"illegal transition {current} -> {status}. Allowed from {current}: {sorted(legal_transitions(current))}")

    if status == "submitted":
        _check_submit_gate(paths, slug, app, acknowledge_risk)
        sub = app.setdefault("submission", {})
        sub["at"] = _today()
        pdf = folder / "out" / "resume_final.pdf"
        sub["resume_sha256"] = _sha256_text(pdf.read_bytes().decode("latin-1")) if pdf.exists() else None
        if acknowledge_risk:
            app.setdefault("gate", {})["risk_acknowledged"] = True

    app["status"] = status
    entry = {"status": status, "at": _today()}
    if note:
        entry["note"] = note
    app.setdefault("status_history", []).append(entry)
    _dump(app_path, app)
    print(f"Status: {current} -> {status}" + (f"  ({note})" if note else ""))
    return 0


def log_event(paths: Paths, slug: str, note: str, date: str | None = None) -> int:
    app_path = paths.applications / slug / "application.yaml"
    if not app_path.exists():
        raise FileNotFoundError(f"{app_path} missing — run: python main.py new {slug}")
    app = load_yaml(app_path)
    app.setdefault("events", []).append({"at": date or _today(), "note": note})
    _dump(app_path, app)
    print(f"Logged event for {slug}: {note}")
    return 0


def track_rows(paths: Paths, open_only: bool = False, closed_only: bool = False) -> list[dict]:
    """The tracker table as data — shared by the CLI table, --csv, and the UI's --json."""
    rows = []
    if paths.applications.exists():
        for folder in sorted(paths.applications.iterdir()):
            if not folder.is_dir():
                continue
            ap = folder / "application.yaml"
            if ap.exists():
                try:
                    a = load_yaml(ap)
                except Exception as e:                  # one bad file must not abort the listing
                    print(f"  skipped malformed {folder.name}/application.yaml: {e}")
                    continue
                rows.append({"id": a.get("id", folder.name), "company": a.get("company", ""),
                             "status": a.get("status", "?"), "verdict": (a.get("gate") or {}).get("verdict", ""),
                             "outcome": (a.get("outcome") or {}).get("result", "") or ""})
            elif (folder / "result.md").exists():   # legacy compat
                rec = parse_result(folder / "result.md")
                rows.append({"id": folder.name, "company": "(legacy)", "status": rec.get("status", "legacy"),
                             "verdict": rec.get("ats", ""), "outcome": rec.get("status", "")})

    def closed(r):
        return r["status"] in _TERMINAL
    return [r for r in rows if (not open_only or not closed(r)) and (not closed_only or closed(r))]


def track(paths: Paths, open_only: bool = False, closed_only: bool = False, csv: bool = False) -> int:
    rows = track_rows(paths, open_only, closed_only)

    if csv:
        out = paths.applications / "_track.csv"
        with out.open("w", newline="", encoding="utf-8") as f:
            w = _csv.DictWriter(f, fieldnames=["id", "company", "status", "verdict", "outcome"])
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote {out} ({len(rows)} rows).")
        return 0

    print(f"  {'id':40} {'company':16} {'status':11} {'gate':6} outcome")
    for r in rows:
        print(f"  {r['id'][:39]:40} {r['company'][:15]:16} {r['status']:11} {r['verdict']:6} {r['outcome']}")
    print(f"\n{len(rows)} application(s).")
    return 0


def _is_post_ats(app: dict) -> bool:
    stage = ((app.get("outcome") or {}).get("stage_reached") or "").lower()
    return app.get("status") in {"screen", "interview", "offer", "hired"} or any(s in stage for s in _POST_ATS)


_CORP = re.compile(r"\b(inc|corp|corporation|llc|ltd|limited|co|gmbh|plc|ag|sa|kk|pvt)\.?\b", re.IGNORECASE)
_URL = re.compile(r"https?://|\bwww\.\S+|\b[\w.-]+\.(?:com|org|net|io|co|ai|gov|edu|dev|app)\b/?", re.IGNORECASE)
_ANON_STOP = {"the", "and", "for", "inc", "our", "you", "with"}


def _company_tokens(company: str) -> set[str]:
    name = re.sub(r"[^\w\s]", " ", _CORP.sub(" ", company))
    return {t for t in name.split() if len(t) >= 3 and t.lower() not in _ANON_STOP}


def _anon_violations(text: str, companies: set[str]) -> list[str]:
    """PII lint for the PUBLIC ledger/backlog: company tokens (suffix-stripped) and URLs."""
    out = []
    for comp in companies:
        for tok in _company_tokens(comp):
            if re.search(r"\b" + re.escape(tok) + r"\b", text, re.IGNORECASE):
                out.append(f"company token '{tok}' (from '{comp}') present")
                break
    if _URL.search(text):
        out.append("a URL / bare domain is present")
    return out


def _load_apps(paths: Paths) -> list[dict]:
    apps = []
    if paths.applications.exists():
        for f in sorted(paths.applications.iterdir()):
            ap = f / "application.yaml"
            if ap.exists():
                try:
                    apps.append(load_yaml(ap))
                except Exception as e:                  # one malformed file must not abort the run
                    print(f"  skipped malformed {f.name}/application.yaml: {e}")
    return apps


def lessons_compile(paths: Paths) -> int:
    """Aggregate lessons from CLOSED applications into an anonymized ledger draft.
    Enforces the EVOLUTION rule (scope:ats from a post-ATS app is rejected) and an
    anonymization lint over BOTH the ledger draft and the public BACKLOG additions."""
    apps = _load_apps(paths)
    companies = {a.get("company", "") for a in apps if a.get("company") and a.get("company") != "(legacy)"}

    lines, backlog_adds, rule_rejects = [], [], []
    for a in apps:
        if a.get("status") not in _TERMINAL:
            continue
        for L in a.get("lessons", []) or []:
            scope = (L.get("scope") or "").strip().lower()   # canonicalize (ATS -> ats)
            text = L.get("text", "")
            if scope == "ats" and _is_post_ats(a):
                rule_rejects.append(f"L[{L.get('id')}] '{text[:50]}' — reached a human (post-ATS); the resume PASSED. "
                                    "This is an INTERVIEW lesson, not an ATS one (EVOLUTION rule).")
                continue
            if scope == "backbone-gap":
                backlog_adds.append(text)
                continue
            lines.append(f"- ({scope}) {text}")

    draft = "# Ledger draft (anonymized) — review before promoting to ATS_LEDGER.md\n\n" + "\n".join(lines) + "\n"
    # lint the ledger draft AND the public backlog additions before writing either
    anon = _anon_violations(draft + "\n" + "\n".join(backlog_adds), companies)

    for r in rule_rejects:
        print(f"[rule] {r}")
    if anon:
        for a in anon:
            print(f"[anonymization] {a}")
        print(f"\nlessons compile FAILED: {len(anon)} anonymization violation(s) — nothing written (the ledger/backlog are public).")
        return 1

    (paths.applications / "_ledger_draft.md").write_text(draft, encoding="utf-8")
    if backlog_adds:
        backlog = paths.context / "variants" / "BACKLOG.md"
        head = backlog.read_text(encoding="utf-8") if backlog.exists() else "# Backlog — learn-before-apply\n"
        backlog.write_text(head.rstrip() + "\n" + "\n".join(f"- {b}" for b in backlog_adds) + "\n", encoding="utf-8")
    print(f"Wrote Applications/_ledger_draft.md ({len(lines)} lesson(s)); "
          f"{len(backlog_adds)} backbone-gap -> BACKLOG.md; {len(rule_rejects)} scope:ats rejected.")
    return 0
