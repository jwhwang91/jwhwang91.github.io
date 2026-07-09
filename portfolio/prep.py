from __future__ import annotations

import re
from typing import Any

from .facts import Registry, Violation

# ---------------------------------------------------------------------------
# Interview-pack validators (MASTER_PLAN §7). The LLM writes interview_pack.yaml;
# these deterministic checks keep it honest: cited claims must be confirmed, every
# `partial` keyword needs a danger question, STAR result digits must trace to a
# registry metric, and no forbidden phrasing may appear.
# ---------------------------------------------------------------------------


def _all_text(pack: dict) -> str:
    parts: list[str] = []

    def walk(x):
        if isinstance(x, str):
            parts.append(x)
        elif isinstance(x, list):
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            for i in x.values():
                walk(i)

    walk(pack)
    return "\n".join(parts)


def _cited_claims(pack: dict) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for e in pack.get("resume_deep_dive", []) or []:
        refs += [("resume_deep_dive", c) for c in e.get("claims", []) or []]
    for e in pack.get("project_walkthroughs", []) or []:
        refs += [("project_walkthrough", c) for c in e.get("claims", []) or []]
    for e in pack.get("behavioral", []) or []:
        refs += [("behavioral", c) for c in e.get("claims", []) or []]
    for e in pack.get("system_design", []) or []:
        if e.get("anchor"):
            refs.append(("system_design", e["anchor"]))
    return refs


def _allowed_floats(claim_ids: list[str], registry: Registry, whitelist_nums: set[str]) -> set[float]:
    out: set[float] = set()
    for n in whitelist_nums:
        try:
            out.add(float(n))
        except ValueError:
            pass
    for cid in claim_ids:
        for m in (registry.claims_by_id.get(cid, {}) or {}).get("metrics", []) or []:
            for n in m.get("numbers", []):
                try:
                    out.add(float(n))
                except (ValueError, TypeError):
                    pass
    return out


def _digit_violations(where: str, text: str, claim_ids: list[str], registry: Registry,
                      whitelist_nums: set[str]) -> list[Violation]:
    """Every number in a narrative field must trace to a cited claim's metric (full-token
    numeric match, no integer-part fallback), unless the field IS a bare <placeholder>."""
    text = text or ""
    if text.strip() == "<placeholder>":
        return []
    allowed = _allowed_floats(claim_ids, registry, whitelist_nums)
    out: list[Violation] = []
    for num in re.findall(r"\d+(?:\.\d+)?", text.replace("<placeholder>", " ")):
        try:
            ok = float(num) in allowed
        except ValueError:
            ok = False
        if not ok:
            out.append(Violation("error", where,
                                 f"{where}: number '{num}' not backed by a cited claim metric "
                                 "(use a real registry metric or <placeholder>)"))
    return out


def validate_pack(pack: dict, match: dict, registry: Registry, policy: dict) -> list[Violation]:
    v: list[Violation] = []
    citable = {c["id"] for c in registry.citable()}

    # every cited claim/anchor must be a confirmed claim
    for where, cid in _cited_claims(pack):
        if cid not in citable:
            v.append(Violation("error", where, f"cites non-confirmed/unknown claim '{cid}'"))

    # every `partial` keyword in the match needs a danger question (anti-overclaim)
    partials = {c.get("term") for c in (match.get("classifications") or []) if c.get("support") == "partial"}
    covered = {d.get("keyword") for d in (pack.get("danger_questions") or [])}
    for p in sorted(partials - covered):
        v.append(Violation("error", "danger_questions",
                           f"partial keyword '{p}' has no danger_question (anti-overclaim safety net)"))

    # every digit in a persuasive narrative field must trace to a cited claim's metric —
    # not just the STAR `result`, since fabricated numbers hide in action/answer_sketch/star.
    whitelist_nums: set[str] = set()
    for tok in (policy or {}).get("numeric_whitelist", []) or []:
        whitelist_nums.update(re.findall(r"\d+", tok))
    for w in pack.get("project_walkthroughs", []) or []:
        cids = w.get("claims", []) or []
        for field in ("situation", "task", "action", "result"):
            v += _digit_violations(f"walkthrough '{w.get('title', '?')}' {field}", w.get(field, ""), cids, registry, whitelist_nums)
    for e in pack.get("resume_deep_dive", []) or []:
        v += _digit_violations("answer_sketch", e.get("answer_sketch", ""), e.get("claims", []) or [], registry, whitelist_nums)
    for e in pack.get("behavioral", []) or []:
        v += _digit_violations("behavioral.star", e.get("star", ""), e.get("claims", []) or [], registry, whitelist_nums)
    for e in pack.get("system_design", []) or []:
        v += _digit_violations("system_design.skeleton", e.get("skeleton", ""),
                               [e["anchor"]] if e.get("anchor") else [], registry, whitelist_nums)

    # forbidden-phrasing scan over the whole pack
    patterns = list((policy or {}).get("global_forbidden_phrases", []) or [])
    for _, cid in _cited_claims(pack):
        patterns += (registry.claims_by_id.get(cid, {}) or {}).get("forbidden_phrases", []) or []
    text = _all_text(pack)
    for pat in patterns:
        try:
            if re.search(pat, text, re.IGNORECASE):
                v.append(Violation("error", "forbidden", f"forbidden phrasing matched /{pat}/"))
        except re.error:
            pass
    return v


def render_pack_md(pack: dict) -> str:
    L = [f"# Interview prep — {pack.get('application', '')}", "",
         f"Positioning: **{pack.get('positioning', '')}**", ""]

    def section(title, items, fmt):
        if not items:
            return
        L.append(f"## {title}")
        for it in items:
            L.append(fmt(it))
        L.append("")

    section("Format forecast", pack.get("format_forecast"),
            lambda r: f"- **{r.get('round')}** — {r.get('basis')}")
    section("Likely topics", pack.get("likely_topics"),
            lambda t: f"- [{t.get('depth')}] {t.get('topic')} (predicted by `{t.get('predicts')}`)")
    if pack.get("resume_deep_dive"):
        L.append("## Resume deep-dive")
        for e in pack["resume_deep_dive"]:
            L.append(f"### {e.get('bullet')}")
            for q in e.get("questions", []) or []:
                L.append(f"- Q: {q}")
            L.append(f"- A: {e.get('answer_sketch')}")
            L.append("")
    if pack.get("danger_questions"):
        L.append("## Danger questions (partial claims — stay inside the truthful boundary)")
        for d in pack["danger_questions"]:
            L.append(f"- **{d.get('keyword')}**: {d.get('truthful_boundary')}")
        L.append("")
    if pack.get("project_walkthroughs"):
        L.append("## Project walkthroughs (STAR)")
        for w in pack["project_walkthroughs"]:
            L.append(f"### {w.get('title')}")
            for k in ("situation", "task", "action", "result"):
                if w.get(k):
                    L.append(f"- **{k.title()}:** {w[k]}")
            L.append("")
    section("System design", pack.get("system_design"),
            lambda s: f"- {s.get('prompt')}" + (f"\n  - skeleton: {s.get('skeleton')}" if s.get('skeleton') else ""))
    section("Behavioral", pack.get("behavioral"), lambda b: f"- {b.get('prompt')}" + (f" — {b.get('star')}" if b.get('star') else ""))
    section("Questions to ask", [{"q": q} for q in pack.get("questions_to_ask", []) or []], lambda x: f"- {x['q']}")
    section("Honest gaps to prep", [{"g": g} for g in pack.get("gaps_to_prep", []) or []], lambda x: f"- {x['g']}")
    section("Refreshers plan", pack.get("refreshers_plan"),
            lambda r: f"- {r.get('topic')}" + (f" (~{r.get('hours')}h)" if r.get('hours') else ""))
    return "\n".join(L).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Coding pack (MASTER_PLAN §8): problems are SELECTED from a committed bank, never
# generated. Deterministic format inference + selection validation.
# ---------------------------------------------------------------------------

CODING_FORMATS = {
    "leetcode-standard": {"easy": 0.30, "medium": 0.55, "hard": 0.15},
    "practical-python": {"easy": 0.45, "medium": 0.45, "hard": 0.10},
    "embedded-c": {"easy": 0.35, "medium": 0.50, "hard": 0.15},
    "takehome-plus-medium-lc": {"easy": 0.20, "medium": 0.65, "hard": 0.15},
}
_MIX_TOLERANCE = 0.15


def infer_format(jd_parsed: dict) -> dict:
    """Deterministic coding-round format from the parsed JD (LLM may override w/ reason)."""
    role_type = (jd_parsed.get("role_type") or "")
    kws = {k.get("term") for k in (jd_parsed.get("keywords") or []) if k.get("term")}
    text = (" ".join((k.get("quote") or "") for k in (jd_parsed.get("keywords") or [])) + " " + role_type).lower()
    if role_type in ("embedded", "controls-software") or (kws & {"cpp", "misra-c", "autosar", "rtos"}):
        return {"format": "embedded-c", "basis": "embedded / C-C++ / MISRA / RTOS signal"}
    if role_type in ("adas-validation", "data-simulation-validation") or \
            (re.search(r"\blog(s|-replay| replay| analysis)?\b", text) and "python" in kws):
        return {"format": "practical-python", "basis": "validation/test role with Python scripting / log analysis"}
    if role_type == "fullstack-saas":
        return {"format": "takehome-plus-medium-lc", "basis": "startup full-stack signal"}
    return {"format": "leetcode-standard", "basis": "general DSA / big-tech signal"}


def validate_coding_pack(pack: dict, bank: dict) -> list[Violation]:
    from collections import Counter
    v: list[Violation] = []
    by_id = {p["id"]: p for p in (bank.get("problems") or [])}
    # de-dupe first: duplicated ids must not inflate the 20-40 count or skew the mix
    ids = list(dict.fromkeys(pack.get("problem_ids") or []))

    for pid in ids:
        if pid not in by_id:
            v.append(Violation("error", "problem_ids", f"problem '{pid}' is not in coding_bank.yaml (problems are selected, not invented)"))
    if not (20 <= len(ids) <= 40):
        v.append(Violation("error", "problem_ids", f"{len(ids)} problems selected — must be 20-40"))

    band = CODING_FORMATS.get(pack.get("format"))
    valid = [by_id[i] for i in ids if i in by_id]
    if band and valid:
        counts = Counter(p.get("difficulty", "medium") for p in valid)
        for diff, target in band.items():
            actual = counts.get(diff, 0) / len(valid)
            if abs(actual - target) > _MIX_TOLERANCE:
                v.append(Violation("error", "difficulty",
                                   f"{diff} share {actual:.0%} is outside the {pack.get('format')} band "
                                   f"(~{target:.0%} +/- {_MIX_TOLERANCE:.0%})"))
    return v


def render_coding_pack_md(pack: dict, bank: dict) -> str:
    by_id = {p["id"]: p for p in (bank.get("problems") or [])}
    L = [f"# Coding prep — {pack.get('application', '')}", "",
         f"Format: **{pack.get('format', '')}**  ·  plan: **{pack.get('plan', '-')}**",
         f"Basis: {pack.get('basis', '')}"]
    if pack.get("format_override_reason"):
        L.append(f"Override: {pack['format_override_reason']}")
    L.append("")
    if pack.get("pattern_priority"):
        L.append("## Pattern priority")
        L.append(" -> ".join(pack["pattern_priority"]))
        L.append("")
    L.append("## Problems")
    for pid in pack.get("problem_ids", []) or []:
        p = by_id.get(pid, {})
        L.append(f"- [ ] `{pid}` [{p.get('difficulty', '?')}] {p.get('title', '(unknown)')} "
                 f"({p.get('source', '')}) — {p.get('pattern', '')}")
        if p.get("talking_point"):
            L.append(f"      talk: {p['talking_point']}")
    L.append("")
    for title, key in (("Complexity expectations", "complexity_expectations"),):
        if pack.get(key):
            L.append(f"## {title}")
            L += [f"- **{c.get('pattern')}:** {c.get('expectation')}" for c in pack[key]]
            L.append("")
    for title, key in (("Mock questions", "mock_questions"), ("Debug / code-review exercises", "debug_exercises"),
                       ("Practical tasks", "practical_tasks")):
        if pack.get(key):
            L.append(f"## {title}")
            L += [f"- {x}" for x in pack[key]]
            L.append("")
    return "\n".join(L).rstrip() + "\n"
