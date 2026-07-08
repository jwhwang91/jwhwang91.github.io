from __future__ import annotations

import re
import sys
from pathlib import Path

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
