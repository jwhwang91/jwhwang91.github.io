from __future__ import annotations

import hashlib
import json
from typing import Any

from .classify import claim_taxonomy_terms
from .facts import Registry, Violation
from .score import score_resume
from .taxonomy import Taxonomy
from .truthlint import detect_class, lint_resume


def _skills_check(resume: dict, classifications: list[dict], registry: Registry,
                  taxonomy: Taxonomy) -> list[Violation]:
    """Q1 for the SKILLS section: a chip must not assert a taxonomy skill that no
    confirmed claim and no supported JD term backs (else a resume could fabricate
    skills the gate never inspects)."""
    supported: set[str] = set()
    for c in registry.citable():
        supported |= claim_taxonomy_terms(c, taxonomy)
    supported |= {cl["term"] for cl in classifications if cl.get("support") in ("direct", "partial")}

    out: list[Violation] = []
    for grp in resume.get("skills", []) or []:
        for item in grp.get("items", []) or []:
            hits = {h.term_id for h in taxonomy.scan(item)}
            unsupported = sorted(h for h in hits if h not in supported)
            if unsupported:
                out.append(Violation("error", "skills",
                                     f"skills chip '{item}' asserts unsupported skill(s) {unsupported} — "
                                     "not backed by any confirmed claim or JD match (Q1)"))
    return out


def evaluate(resume: dict, resume_txt: str, classifications: list[dict], registry: Registry,
             taxonomy: Taxonomy, policy: dict, approved_titles: set[str]) -> tuple[dict, list]:
    """Run the full gate (truthlint Q1-Q14 + score Q8/Q10/Q15-Q20) and return
    (gate_report dict, error list)."""
    violations = list(lint_resume(resume, registry))
    violations += _skills_check(resume, classifications, registry, taxonomy)
    s = score_resume(resume_txt, classifications, taxonomy, policy, resume.get("role_title", ""), approved_titles)
    violations += s["violations"]

    errors = [x for x in violations if x.level == "error"]
    warnings = [x for x in violations if x.level == "warning"]
    U = s["unsupported_ratio"]

    verdict = "FAIL" if errors else ("HIGH_RISK" if U >= 0.5 else "PASS")
    if U >= 0.5:
        recommendation = "Do-Not-Apply-Yet"
    elif U >= 0.25 or s["risky_for_review"]:
        recommendation = "Revise"
    else:
        recommendation = "Apply"

    report = {
        "schema": "gate_report/v1",
        "application": resume.get("application", ""),
        "verdict": verdict,
        "recommendation": recommendation,
        "must_have_coverage": s["coverage"],
        "must_have_pct": s["must_pct"],
        "missing_terms": s["missing_terms"],
        "unsupported_ratio": U,
        "excluded_unsupported": s["excluded_unsupported"],
        "risky_for_review": s["risky_for_review"],
        "errors": [str(e) for e in errors],
        "warnings": [str(w) for w in warnings],
        "pdf_verified": False,
        # binds the submit gate to the exact text that was graded (anti-silent-edit)
        "resume_ats_sha256": hashlib.sha256(resume_txt.encode("utf-8")).hexdigest(),
    }
    return report, errors


def render_gate_md(report: dict) -> str:
    L = [f"# Gate report — {report.get('application', '')}", ""]
    L.append(f"**Verdict: {report['verdict']}**  ·  recommendation: **{report['recommendation']}**")
    L.append("")
    L.append(f"- Must-have coverage: {report['must_have_coverage']} ({report['must_have_pct']}%)")
    L.append(f"- Unsupported-must-have ratio (U): {report['unsupported_ratio']}")
    L.append(f"- PDF verified: {report['pdf_verified']}")
    L.append("")
    if report["missing_terms"]["must"]:
        L.append("## Missing supported must-haves")
        L += [f"- {t}" for t in report["missing_terms"]["must"]]
        L.append("")
    if report["excluded_unsupported"]:
        L.append("## Intentionally excluded (unsupported/adjacent — see gap report)")
        L.append(", ".join(report["excluded_unsupported"]))
        L.append("")
    if report["risky_for_review"]:
        L.append("## Risky for review (defend verbally in an interview)")
        L += [f"- {r['term']} (partial) — cite {', '.join(r['claim_ids'])}" for r in report["risky_for_review"]]
        L.append("")
    if report["errors"]:
        L.append("## Errors (must fix)")
        L += [f"- {e}" for e in report["errors"]]
        L.append("")
    if report["warnings"]:
        L.append("## Warnings")
        L += [f"- {w}" for w in report["warnings"]]
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def render_checklist_md(report: dict) -> str:
    return "\n".join([
        f"# Reviewer checklist — {report.get('application', '')}",
        "",
        "- [ ] Every `risky_for_review` phrasing is one you can defend verbally in an interview",
        "- [ ] Role title matches what you'd say out loud about yourself",
        "- [ ] Metrics current (`as_of` staleness warnings resolved)",
        "- [ ] Gap report reviewed; Do-Not-Apply-Yet items consciously overridden or accepted",
        "- [ ] PDF text layer verified (`pdfcheck` PASS)",
        "- [ ] Contact info correct; portfolio links resolve",
        "- [ ] `jd.txt` unchanged since parse (auto-checked via sha)",
        "",
    ]) + "\n"


def build_audit(resume: dict, registry: Registry, policy: dict) -> dict:
    """Evidence map: every rendered bullet -> cited claims + ownership + detected strength class."""
    out = {"application": resume.get("application", ""), "bullets": []}
    by_id = registry.claims_by_id

    def add(section, bullets):
        for b in bullets or []:
            cls, _ = detect_class(b.get("text", ""), policy)
            claims = [by_id.get(c, {}) for c in b.get("claims", []) or []]
            out["bullets"].append({
                "section": section,
                "text": b.get("text", ""),
                "claims": b.get("claims", []),
                "ownership": [c.get("ownership") for c in claims],
                "strength_class_detected": cls,
                "evidence": [e.get("ref") for c in claims for e in (c.get("evidence") or [])],
            })

    add("Summary", resume.get("summary"))
    for e in resume.get("experience", []) or []:
        add(f"Experience:{e.get('source')}", e.get("bullets"))
    for e in resume.get("projects", []) or []:
        add(f"Projects:{e.get('source')}", e.get("bullets"))
    return out


def render_changes_md(resume: dict, registry: Registry) -> str:
    """Diff each rendered bullet against its cited claims' canonical statements."""
    by_id = registry.claims_by_id
    L = [f"# Changes — {resume.get('application', '')}", "",
         "Each rendered bullet vs the canonical statement(s) of the claim(s) it cites.", ""]

    def emit(section, bullets):
        for b in bullets or []:
            L.append(f"### [{section}] {b.get('text', '')}")
            for cid in b.get("claims", []) or []:
                stmt = (by_id.get(cid) or {}).get("statement", "<unknown claim>")
                L.append(f"- from `{cid}`: {stmt}")
            L.append("")

    emit("Summary", resume.get("summary"))
    for e in resume.get("experience", []) or []:
        emit(f"Experience:{e.get('source')}", e.get("bullets"))
    for e in resume.get("projects", []) or []:
        emit(f"Projects:{e.get('source')}", e.get("bullets"))
    return "\n".join(L).rstrip() + "\n"


def build_gate_feedback(report: dict, taxonomy: Taxonomy) -> dict:
    """On FAIL: the payload /resume-plan consumes to revise resume.yaml (§5.5)."""
    missing = report["missing_terms"]["must"]
    return {
        "missing_supported_must_haves": [
            {"term": t, "ats_form": (taxonomy.by_id[t].ats_form if t in taxonomy.by_id else t),
             "cheapest_fix": f"add a bullet or skills chip using \"{taxonomy.by_id[t].ats_form if t in taxonomy.by_id else t}\""}
            for t in missing
        ],
        "errors": report["errors"],
    }
