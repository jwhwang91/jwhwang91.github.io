from __future__ import annotations

import re
from typing import Any, Iterator

from .facts import Registry, Violation

# ---------------------------------------------------------------------------
# JD-independent truthfulness lints (MASTER_PLAN §12: Q1-Q7, Q11-Q14).
#
# These run on a parsed resume.yaml (structure per §5.1) against the confirmed
# claim registry + phrasing_policy. Structural checks read resume fields; textual
# checks read the bullet text. The resume-generation pipeline (Phase 5) wires
# this in; here it is a standalone, fixture-tested library.
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[A-Za-z']+")


def _iter_bullets(resume: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for b in resume.get("summary", []) or []:
        yield "Summary", b
    for exp in resume.get("experience", []) or []:
        for b in exp.get("bullets", []) or []:
            yield "Experience", b
    for proj in resume.get("projects", []) or []:
        for b in proj.get("bullets", []) or []:
            yield "Projects", b


def _lexeme_present(text: str, lexeme: str) -> bool:
    return re.search(r"\b" + re.escape(lexeme) + r"\b", text, re.IGNORECASE) is not None


def detect_class(text: str, policy: dict[str, Any]) -> tuple[str, bool]:
    """Return (strength_class, found_a_lexeme). Strongest class present wins;
    if none is found, class defaults to 'contribution' with found=False (a warn)."""
    classes = policy.get("strength_classes", {})
    for cls in ("ownership", "contribution", "exposure"):
        for lex in classes.get(cls, {}).get("lexemes", []):
            if _lexeme_present(text, lex):
                return cls, True
    return "contribution", False


def _numbers(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?", text)


def lint_resume(resume: dict[str, Any], registry: Registry) -> list[Violation]:
    """Run the JD-independent truthfulness lints. Returns errors + warnings."""
    v: list[Violation] = []
    policy = registry.policy or {}
    by_id = registry.claims_by_id

    # --- Q5: every experience entry resolves to an employer period (structural) ---
    for exp in resume.get("experience", []) or []:
        src = exp.get("source")
        emp = registry.employers.get(src) if src else None
        if emp is None:
            v.append(Violation("error", f"experience:{src}", "experience source has no employers.yaml anchor (Q5)"))
        elif not (emp.get("period") or {}).get("start"):
            v.append(Violation("error", f"experience:{src}", "employer period is missing a start date (Q5)"))

    # --- Q6 (structural half): resume org/title renderings match employer canon ---
    for exp in resume.get("experience", []) or []:
        src = exp.get("source")
        emp = registry.employers.get(src) if src else None
        if emp:
            org = exp.get("organization")
            if org and org not in ([emp.get("organization")] + (emp.get("org_renderings") or [])):
                v.append(Violation("error", f"experience:{src}", f"organization '{org}' is not an approved employers.yaml rendering (Q6)"))
            title = exp.get("role_title") or exp.get("title")
            if title and title not in ([emp.get("official_title")] + (emp.get("title_renderings") or [])):
                v.append(Violation("error", f"experience:{src}", f"title '{title}' is not an approved employers.yaml rendering (Q6)"))

    # --- Q14: too many projects (structural) ---
    nproj = len(resume.get("projects", []) or [])
    if nproj > 4:
        v.append(Violation("warning", "projects", f"{nproj} projects (>4) — consider trimming (Q14)"))

    all_bullet_shingles: dict[tuple[str, ...], int] = {}

    for section, b in _iter_bullets(resume):
        text = (b.get("text") or "").strip()
        cited_ids = b.get("claims") or []
        cited = [by_id[c] for c in cited_ids if c in by_id]
        where = f"{section} bullet"

        # --- Q1: every bullet cites >=1 confirmed claim (structural) ---
        if not cited_ids:
            v.append(Violation("error", where, "bullet cites no claim (Q1)"))
        for cid in cited_ids:
            claim = by_id.get(cid)
            if claim is None:
                v.append(Violation("error", where, f"cited claim '{cid}' does not exist (Q1)"))
            elif claim.get("status") != "confirmed":
                v.append(Violation("error", where, f"cited claim '{cid}' is not confirmed — not citable (Q1)"))

        # --- Q2: verb strength vs cited claims' ownership (structural) ---
        cls, found = detect_class(text, policy)
        if not found:
            v.append(Violation("warning", where, "no strength lexeme found — defaulting to contribution class (Q2)"))
        for claim in cited:
            own = claim.get("ownership")
            if cls == "ownership" and own != "independent":
                v.append(Violation("error", where, f"ownership-class verb but cited claim '{claim.get('id')}' is {own} (Q2)"))
            elif cls == "contribution" and own in ("support", "exposure"):
                v.append(Violation("error", where, f"contribution-class verb but cited claim '{claim.get('id')}' is {own} (Q2)"))

        # --- Q3: invented metrics — every digit traces to a cited metric / date / whitelist (textual) ---
        if section in ("Experience", "Projects") and text:
            scrubbed = text
            for token in policy.get("numeric_whitelist", []):
                scrubbed = scrubbed.replace(token, " ")
            allowed: set[str] = set()
            for claim in cited:
                for m in claim.get("metrics", []) or []:
                    allowed.update(str(n) for n in m.get("numbers", []))
            for emp in registry.employers.values():
                for key in ("start", "end"):
                    val = (emp.get("period") or {}).get(key)
                    if isinstance(val, str):
                        allowed.update(re.findall(r"\d+", val))
            for num in _numbers(scrubbed):
                if num not in allowed and num.split(".")[0] not in allowed:
                    v.append(Violation("error", where, f"number '{num}' not backed by a cited metric/date/whitelist (Q3)"))

        # --- Q4: metric staleness (structural) ---
        for claim in cited:
            for m in claim.get("metrics", []) or []:
                as_of = m.get("as_of")
                if not as_of or "OWNER" in str(as_of) or "placeholder" in str(as_of).lower():
                    v.append(Violation("warning", where, f"cited metric '{m.get('id')}' has no confirmed as_of date (Q4)"))

        # --- Q7: forbidden phrasing (textual): global + per-employer + per-claim ---
        patterns = list(policy.get("global_forbidden_phrases", []) or [])
        for exp in resume.get("experience", []) or []:
            emp = registry.employers.get(exp.get("source"))
            if emp:
                patterns += emp.get("forbidden_phrases", []) or []
        for claim in cited:
            patterns += claim.get("forbidden_phrases", []) or []
        for pat in patterns:
            try:
                if re.search(pat, text, re.IGNORECASE):
                    v.append(Violation("error", where, f"forbidden phrasing matched /{pat}/ (Q7)"))
            except re.error:
                pass

        # --- Q11: bullet length (structural) ---
        if len(text) > 280:
            v.append(Violation("error", where, f"bullet is {len(text)} chars (>280) (Q11)"))
        elif len(text) > 200:
            v.append(Violation("warning", where, f"bullet is {len(text)} chars (>200) (Q11)"))

        # --- Q12: vague claims (textual) ---
        for pat in policy.get("vague_claim_lexicon", []) or []:
            try:
                if re.search(pat, text, re.IGNORECASE):
                    v.append(Violation("error", where, f"vague claim matched /{pat}/ (Q12)"))
            except re.error:
                pass

        # --- Q13: duplicated 6-word shingles across bullets (textual) ---
        words = [w.lower() for w in _WORD.findall(text)]
        for i in range(len(words) - 5):
            shingle = tuple(words[i:i + 6])
            all_bullet_shingles[shingle] = all_bullet_shingles.get(shingle, 0) + 1

    for shingle, count in all_bullet_shingles.items():
        if count >= 2:
            v.append(Violation("warning", "resume", f"phrase '{' '.join(shingle)}' repeats across bullets (Q13)"))

    return v
