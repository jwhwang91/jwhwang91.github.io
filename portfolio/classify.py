from __future__ import annotations

from collections import defaultdict
from typing import Any

from .facts import Registry
from .taxonomy import Taxonomy

# ---------------------------------------------------------------------------
# Support classification (MASTER_PLAN §4.3-4.4). Deterministic registry join:
# a JD keyword (a taxonomy id) is matched against the CONFIRMED claim registry.
#
# Claim registry terms are free strings (e.g. "hardware-in-the-loop", "hils")
# while JD keywords are taxonomy ids (e.g. "hil"). We reconcile by resolving each
# claim term string through the taxonomy (its aliases already cover the spellings).
# ---------------------------------------------------------------------------

OWN_RANK = {"independent": 3, "shared": 2, "support": 1, "exposure": 0}
# Domains where a production-implying JD term should hedge against a prototype-only claim.
PRODUCTION_DOMAINS = {"adas", "controls", "embedded", "validation", "tooling"}

# §6 portfolio emphasis map: positioning track -> ordered emphasis anchors.
EMPHASIS = {
    "adas-av-validation": ["hmc-adas", "tc-bev-simulator", "tc-timeseries-ai", "add-k2-tcu", "kaist-masters"],
    "vehicle-systems-validation": ["hmc-adas", "tc-bev-simulator", "tc-timeseries-ai", "add-k2-tcu", "kaist-masters"],
    "embedded-controls": ["add-k2-tcu", "hmc-adas", "kaist-masters", "tc-bev-simulator"],
    "ai-tooling-fullstack": ["sw-deckflip-pipeline", "sw-decisioncanvas-engine", "sw-pathpilot-app", "sw-voiceprint", "sw-pinterest-oauth"],
    "systems-ai-automation": ["sw-decisioncanvas-engine", "sw-deckflip-pipeline", "tc-xcp-bypass", "tc-timeseries-ai", "hmc-ai-toolchains"],
}


def resolve_term_to_taxonomy(term_str: str, taxonomy: Taxonomy) -> set[str]:
    """A claim's free-string term -> taxonomy ids. Exact id first, else scan a
    space-normalized form so 'hardware-in-the-loop'/'hils' both resolve to 'hil'."""
    if term_str in taxonomy.by_id:
        return {term_str}
    return {h.term_id for h in taxonomy.scan(term_str.replace("-", " "))}


def claim_taxonomy_terms(claim: dict[str, Any], taxonomy: Taxonomy) -> set[str]:
    out: set[str] = set()
    for t in claim.get("terms", []) or []:
        out |= resolve_term_to_taxonomy(t, taxonomy)
    return out


class JoinIndex:
    """Confirmed-claim index for the registry join, keyed by taxonomy id + domain."""

    def __init__(self, registry: Registry, taxonomy: Taxonomy):
        self.taxonomy = taxonomy
        self.by_term: dict[str, list[dict]] = defaultdict(list)
        self.by_domain: dict[str, list[str]] = defaultdict(list)
        for c in registry.citable():
            terms = claim_taxonomy_terms(c, taxonomy)
            for t in terms:
                self.by_term[t].append(c)
            for d in {taxonomy.by_id[t].domain for t in terms if t in taxonomy.by_id}:
                self.by_domain[d].append(c["id"])

    def classify(self, term: str, matched_tier: str) -> dict[str, Any]:
        """Classify one JD keyword -> direct | partial | adjacent | unsupported."""
        claims = self.by_term.get(term, [])
        term_domain = self.taxonomy.by_id[term].domain if term in self.taxonomy.by_id else None
        if claims:
            direct_ids = []
            for c in claims:
                own_ok = c.get("ownership") in ("independent", "shared")
                tier_ok = matched_tier in ("exact", "equivalent")
                capped = (c.get("term_caps") or {}).get(term) == "partial"
                proto_block = c.get("deployment") == "prototype" and term_domain in PRODUCTION_DOMAINS
                if own_ok and tier_ok and not capped and not proto_block:
                    direct_ids.append(c["id"])
            if direct_ids:
                return {"support": "direct", "claim_ids": direct_ids}
            return {"support": "partial", "claim_ids": [c["id"] for c in claims], "hedge_required": True}
        if term_domain and self.by_domain.get(term_domain):
            return {"support": "adjacent", "claim_ids": [], "domain": term_domain}
        return {"support": "unsupported", "claim_ids": []}


def classify_keywords(keywords: list[dict], tiers: dict[str, str], index: JoinIndex,
                      cache: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """Return (resolved classifications, unresolved LLM queue). `keywords` are the
    confirmed jd.parsed.yaml keyword entries; `tiers` maps term -> strongest scan tier."""
    resolved: list[dict] = []
    queue: list[dict] = []
    for kw in keywords:
        if "new_term" in kw:
            queue.append({"new_term": kw["new_term"], "requirement": kw.get("requirement"),
                          "quote": kw.get("quote"), "reason": "new_term — not in taxonomy, needs LLM classification"})
            continue
        term = kw.get("term")
        if not term:
            continue
        tier = tiers.get(term, "equivalent")
        cached = cache.get(term)
        if cached:
            entry = _reclassify_cached(term, cached, tier, index)
            entry["source"] = "cache"
        else:
            entry = index.classify(term, tier)
            entry["source"] = "registry"
        entry.update(term=term, requirement=kw.get("requirement"), matched_tier=tier, quote=kw.get("quote"))
        resolved.append(entry)
    return resolved, queue


def _reclassify_cached(term: str, cached: dict, tier: str, index: JoinIndex) -> dict:
    """Use a cached classification, but re-verify its claim_ids are still confirmed;
    if the join is now weaker, downgrade automatically (upgrades require re-gating)."""
    live_ids = {c["id"] for c in index.by_term.get(term, [])}
    cached_ids = [cid for cid in (cached.get("claim_ids") or []) if cid in live_ids]
    if cached.get("support") in ("direct", "partial") and not cached_ids:
        # every cited claim vanished -> re-run the join fresh
        return index.classify(term, tier)
    return {"support": cached.get("support"), "claim_ids": cached_ids}


# --- scoring & pre-resume verdict (§4.4) ---

def _knockout_matches(knockout: dict, profile: dict) -> bool:
    q = (str(knockout.get("quote", "")) + " " + str(knockout.get("type", ""))).lower()
    us = (profile.get("work_authorization") or {}).get("us") or {}
    if any(k in q for k in ("sponsor", "authorized to work", "citizen", "clearance", "security clearance")):
        if isinstance(us, dict) and us.get("status") == "requires-sponsorship":
            return True
    return False


def pre_resume_verdict(classifications: list[dict], knockouts: list[dict],
                       candidate_profile: dict | None) -> dict:
    must = [c for c in classifications if c.get("requirement") == "must" and c.get("support")]
    weak = [c for c in must if c["support"] in ("adjacent", "unsupported")]
    U = round(len(weak) / len(must), 3) if must else 0.0

    profile_checked = candidate_profile is not None
    knockout_hits = ([k.get("type") for k in knockouts if _knockout_matches(k, candidate_profile)]
                     if profile_checked else [])

    if U >= 0.5 or knockout_hits:
        verdict = "Do-Not-Apply-Yet"
    elif U >= 0.25:
        verdict = "Proceed-Caution"
    else:
        verdict = "Proceed"
    return {
        "U": U,
        "verdict": verdict,
        "missing_must_haves": [c["term"] for c in weak],
        "knockout_hits": knockout_hits,
        "profile_checked": profile_checked,
    }


# --- report renderers (deterministic) ---

def render_gap_report(slug: str, classifications: list[dict], verdict: dict,
                      knockouts: list[dict], index: JoinIndex, profile_checked: bool) -> str:
    lines = [f"# Gap report — {slug}", ""]
    lines.append(f"**Pre-resume verdict: {verdict['verdict']}**  "
                 f"(unsupported-must-have ratio U = {verdict['U']})")
    lines.append("")
    if verdict["verdict"] == "Do-Not-Apply-Yet":
        lines.append("> Half or more of the must-haves are unsupported, or a knockout matched. "
                     "Consider a learn-before-apply project or abandoning this application.")
    elif verdict["verdict"] == "Proceed-Caution":
        lines.append("> A meaningful share of must-haves is unsupported — proceed, but the resume "
                     "will carry visible gaps. Review below before drafting.")
    else:
        lines.append("> Must-have coverage is strong. Proceed to resume drafting.")
    lines.append("")

    if not profile_checked:
        lines.append("_Knockout checks SKIPPED: Context/candidate_profile.yaml is absent "
                     "(work-authorization/location not evaluated)._")
        lines.append("")
    elif knockouts:
        lines.append("## Knockouts")
        for k in knockouts:
            hit = k.get("type") in verdict["knockout_hits"]
            mark = "MATCH (auto-knockout)" if hit else "clear"
            lines.append(f"- [{mark}] {k.get('type')}: \"{k.get('quote', '')}\"")
        lines.append("")

    weak = [c for c in classifications if c.get("requirement") == "must"
            and c.get("support") in ("adjacent", "unsupported")]
    lines.append("## Missing / weak must-haves")
    if not weak:
        lines.append("_None — every must-have is direct or partial._")
    for c in weak:
        term = c["term"]
        near = index.by_domain.get((c.get("domain") or ""), [])[:3]
        near_txt = f" nearest claims (same domain): {', '.join(near)}" if near else " no adjacent claims"
        lines.append(f"- **{term}** ({c['support']}) — quote: \"{c.get('quote', '')}\".{near_txt}")
        lines.append(f"  - learn-before-apply: <LLM fills a concrete suggestion for '{term}'>")
    lines.append("")

    partials = [c for c in classifications if c.get("support") == "partial"]
    if partials:
        lines.append("## Partial (hedge required on the resume)")
        for c in partials:
            lines.append(f"- {c['term']} — cite {', '.join(c.get('claim_ids', []))} with hedged phrasing")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_portfolio_plan(slug: str, positioning: str, classifications: list[dict]) -> str:
    order = EMPHASIS.get(positioning)
    lines = [f"# Portfolio emphasis plan — {slug}", "", f"Positioning: **{positioning or '(unset)'}**", ""]
    if not order:
        lines.append(f"_No emphasis map for positioning '{positioning}'. "
                     f"Known tracks: {', '.join(sorted(EMPHASIS))}._")
        return "\n".join(lines) + "\n"
    lines.append("## Recommended project / experience order")
    for i, anchor in enumerate(order, 1):
        lines.append(f"{i}. {anchor}")
    lines.append("")
    direct = [c["term"] for c in classifications if c.get("support") == "direct"]
    if direct:
        lines.append("## Lead with these directly-supported keywords")
        lines.append(", ".join(sorted(set(direct))))
        lines.append("")
    return "\n".join(lines) + "\n"
