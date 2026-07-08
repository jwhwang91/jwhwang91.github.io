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
