from __future__ import annotations

import re
from typing import Any

from .facts import Violation
from .taxonomy import Taxonomy

# JD-dependent ATS checks (MASTER_PLAN §4.4 + §12: Q8, Q10, Q15-Q17, Q20). All run on
# the plain-text render (resume_ats.txt) — score what a worst-case parser sees.


def _aliases(taxonomy: Taxonomy, term: str) -> list[str]:
    t = taxonomy.by_id.get(term)
    if not t:
        return [term.replace("-", " "), term]
    return [t.canonical] + [a.text for a in t.aliases]


def _present(text: str, alias: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, re.IGNORECASE) is not None


def _term_present(text: str, taxonomy: Taxonomy, term: str) -> bool:
    return any(_present(text, a) for a in _aliases(taxonomy, term))


def _count(text: str, taxonomy: Taxonomy, term: str) -> int:
    # count DISTINCT mentions (lines that reference the term), not the sum of every
    # alias hit — an ats_form like "Hardware-in-the-Loop (HIL/HILS)" packs several
    # alias forms in one mention and must not read as keyword stuffing.
    return sum(1 for ln in text.splitlines() if _term_present(ln, taxonomy, term))


def _ats_form(taxonomy: Taxonomy, term: str) -> str:
    t = taxonomy.by_id.get(term)
    return t.ats_form if t else term


def score_resume(resume_txt: str, classifications: list[dict], taxonomy: Taxonomy,
                 policy: dict, role_title: str, approved_titles: set[str]) -> dict[str, Any]:
    """Return {violations, coverage, unsupported_ratio, placement, missing_terms, risky}."""
    v: list[Violation] = []
    must = [c for c in classifications if c.get("requirement") == "must"]
    supported_must = [c for c in must if c.get("support") in ("direct", "partial")]
    weak_must = [c for c in must if c.get("support") in ("adjacent", "unsupported")]

    # --- Q15: every SUPPORTED must-have must appear in the text (coverage must be 100%) ---
    present, missing = [], []
    for c in supported_must:
        (present if _term_present(resume_txt, taxonomy, c["term"]) else missing).append(c["term"])
    for term in missing:
        v.append(Violation("error", "coverage", f"supported must-have '{term}' is missing from the resume (Q15)"))
    coverage = f"{len(present)}/{len(supported_must)}"
    must_pct = round(100 * len(present) / len(supported_must), 1) if supported_must else 100.0

    # --- Q16: an adjacent/unsupported term must NOT appear (truthfulness back-check) ---
    for c in weak_must + [c for c in classifications if c.get("support") in ("adjacent", "unsupported")]:
        if _term_present(resume_txt, taxonomy, c["term"]):
            v.append(Violation("error", "truthfulness", f"unsupported/adjacent term '{c['term']}' appears in the resume (Q16)"))

    # --- Q10: acronym first-use expansion — a present must-have must show its ats_form ---
    for c in supported_must:
        if _term_present(resume_txt, taxonomy, c["term"]):
            form = _ats_form(taxonomy, c["term"])
            if form and form not in resume_txt:
                v.append(Violation("error", "formatting", f"'{c['term']}' first use must expand to \"{form}\" (Q10)"))

    # --- Q8: keyword stuffing ---
    for c in must + [c for c in classifications if c.get("requirement") == "nice"]:
        n = _count(resume_txt, taxonomy, c["term"])
        if n > 6:
            v.append(Violation("error", "stuffing", f"'{c['term']}' occurs {n} times (>6) (Q8)"))
        elif n > 4:
            v.append(Violation("warning", "stuffing", f"'{c['term']}' occurs {n} times (>4) (Q8)"))

    # --- Q17: hedge integrity — a partial keyword must co-occur with an allowlisted hedge ---
    hedges = policy.get("strength_classes", {}).get("exposure", {}).get("lexemes", []) or []
    sentences = re.split(r"(?<=[.!?])\s+|\n", resume_txt)
    for c in [c for c in classifications if c.get("support") == "partial"]:
        if _term_present(resume_txt, taxonomy, c["term"]):
            hit_sentences = [s for s in sentences if _term_present(s, taxonomy, c["term"])]
            if not any(any(h.lower() in s.lower() for h in hedges) for s in hit_sentences):
                v.append(Violation("error", "hedge", f"partial term '{c['term']}' used without a hedge phrase (Q17)"))

    # --- Q19: role_title must be an approved positioning title ---
    if role_title and role_title not in approved_titles:
        v.append(Violation("error", "positioning", f"role_title '{role_title}' is not in positioning_titles.yaml (Q19)"))

    # --- Q20: unsupported-must-have ratio ---
    U = round(len(weak_must) / len(must), 3) if must else 0.0

    risky = [{"term": c["term"], "support": "partial", "claim_ids": c.get("claim_ids", [])}
             for c in classifications if c.get("support") == "partial"]

    return {
        "violations": v,
        "coverage": coverage,
        "must_pct": must_pct,
        "missing_terms": {"must": missing, "nice": []},
        "unsupported_ratio": U,
        "excluded_unsupported": [c["term"] for c in weak_must],
        "risky_for_review": risky,
    }
