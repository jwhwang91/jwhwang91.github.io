from __future__ import annotations

import re
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
SUPPORT_RANK = {"unsupported": 0, "adjacent": 1, "partial": 2, "direct": 3}
# Domains where a production-implying JD term should hedge against a prototype-only claim.
PRODUCTION_DOMAINS = {"adas", "controls", "embedded", "validation", "tooling"}
# Claim-term suffixes that name a credential, not a skill — never resolve to a skill
# keyword (e.g. "commercial-vehicle-license" must not count as commercial-vehicle ADAS work).
_CREDENTIAL_SUFFIXES = ("-license", "-degree", "-certification", "-cert")

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
    if term_str.endswith(_CREDENTIAL_SUFFIXES):
        return set()
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
        # a keyword the deterministic scan never hit has no exact/equivalent alias
        # evidence -> default to 'related' so it caps at partial, never a free 'direct'.
        tier = tiers.get(term, "related")
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
    """Re-gate a cached classification for the CURRENT application. A registry-
    derivable term (a taxonomy id) is ALWAYS re-joined, so a weaker current JD tier,
    a demoted claim ownership, a new prototype/term_cap, or a vanished claim all
    downgrade automatically and no stale-too-strong support leaks across applications
    (upgrades therefore require a fresh confirm, which is correct). The cache only
    preserves LLM classifications the registry cannot derive (new_terms)."""
    if term in index.taxonomy.by_id:
        return index.classify(term, tier)
    live_ids = {c["id"] for c in index.by_term.get(term, [])}
    cached_ids = [cid for cid in (cached.get("claim_ids") or []) if cid in live_ids]
    if cached.get("support") in ("direct", "partial") and not cached_ids:
        return {"support": "unsupported", "claim_ids": []}
    return {"support": cached.get("support"), "claim_ids": cached_ids}


# --- scoring & pre-resume verdict (§4.4) ---

# Cues that mark a knockout as being about WHERE the work is performed. Matched
# against quote + type, so `type: location` alone is enough to route here.
_LOCATION_CUES = ("location", "onsite", "on-site", "on site", "in-person", "in person",
                  "relocat", "hybrid", "must be based", "based in", "must live", "commut")
LOCATION_KNOCKOUT_TYPE = "location"


def _place_names(entry: Any) -> list[str]:
    """The JD spellings that identify one place, from a profile locations entry."""
    if isinstance(entry, dict):
        names = entry.get("names") or ([entry["place"]] if entry.get("place") else [])
        return [str(n) for n in names]
    if isinstance(entry, (list, tuple, set)):
        return [str(n) for n in entry]
    return [str(entry)] if entry else []


def _mentions(text: str, names: list[str]) -> bool:
    """Word-boundary, case-insensitive place-name match on already-lowercased text.
    Boundaries are mandatory: a bare substring test fires 'US' inside 'must'."""
    return any(re.search(rf"(?<![a-z0-9]){re.escape(n.strip().lower())}(?![a-z0-9])", text)
               for n in names if n and n.strip())


def _location_matches(q: str, profile: dict) -> bool:
    """True when a location/onsite knockout names somewhere he cannot work.

    Order matters and is deliberate: a BLOCKED place named in the text decides
    BEFORE an authorized one. US automotive postings routinely name Korea ("our
    Seoul office", "Korean OEM partners"), so checking `authorized_now` first
    would let every one of them clear.

    Fails CLOSED: only a place he may already work in, an unrestricted-remote
    phrase, or a relocation target that costs the employer nothing he might
    refuse clears the knockout. An unnamed or unrecognized location stays a hit —
    an onsite req he cannot reach is exactly what this exists to catch.

    KNOWN BOUND: this judges whatever text it is handed. Callers should hand it
    the work location alone (see the `place` key set by `location_knockouts`).
    Given free prose that names both a blocked and an authorized place, only the
    blocked-first ordering below protects it; prose naming ONLY an authorized
    place still clears, which is why the parser should emit location knockouts
    whose quote is the posting's stated location, not a sentence."""
    locs = profile.get("locations") or {}
    if not isinstance(locs, dict) or not locs:
        return False  # no location data in the profile -> nothing to judge against
    # 1. Relocation targets decide first, and blocked wins: if the text names two
    #    and either needs sponsorship he does not have, the req is still a hit.
    verdicts = [not (entry.get("relocation_ok") and not entry.get("requires_sponsorship"))
                for entry in locs.get("relocation") or []
                if isinstance(entry, dict) and _mentions(q, _place_names(entry))]
    if verdicts:
        return any(verdicts)
    # 2. No relocation target named -> the role may sit where he already works.
    if _mentions(q, _place_names(locs.get("authorized_now"))):
        return False  # the role sits where he can already work, today, unsponsored
    remote = locs.get("remote") or {}
    if isinstance(remote, dict) and remote.get("remote_ok") and _mentions(q, _place_names(remote.get("names"))):
        return False  # explicitly hire-from-anywhere remote
    return True


def _knockout_matches(knockout: dict, profile: dict) -> bool:
    q = (str(knockout.get("quote", "")) + " " + str(knockout.get("type", ""))).lower()
    us = (profile.get("work_authorization") or {}).get("us") or {}
    if any(k in q for k in ("sponsor", "authorized to work", "citizen", "clearance", "security clearance")):
        if isinstance(us, dict) and us.get("status") == "requires-sponsorship":
            return True
    if any(k in q for k in _LOCATION_CUES):
        # Judge the work location alone whenever the caller isolated it into
        # `place` (location_knockouts does). Falling back to the whole quote is a
        # last resort: free prose regularly names a second, irrelevant place.
        place = str(knockout.get("place") or "").strip().lower()
        return _location_matches(place or q, profile)
    return False


def location_knockouts(location_policy: dict | None, profile: dict | None) -> list[dict]:
    """Synthesize the location knockout a JD implies but rarely states outright.

    Parsers fill `location_policy: {onsite, city, remote}` and leave `knockouts: []`,
    so an onsite US req produced no auto-knockout at all. Returns a `{type, quote}`
    entry (the shape `render_gap_report` and `_knockout_matches` consume) ONLY when
    the policy actually conflicts with the profile — a satisfiable location emits
    nothing rather than a "clear" row of noise. The quote is explicitly labelled
    derived: it is NOT a verbatim jd.txt substring and must never be written into
    jd.parsed.yaml, whose quotes are verbatim-checked by `validate_parsed`.

    `place` carries the stated work location on its own so `_knockout_matches`
    judges the location and nothing else. This deliberately does NOT scan the JD
    body: an earlier version did, and a US posting that mentioned a Seoul office
    cleared its own location knockout. With no parsed location the answer is a
    hit — a false auto-knockout is a visible row in gap_report.md the owner can
    overrule, while a false clear is silent."""
    if not profile or not isinstance(location_policy, dict):
        return []
    locs = profile.get("locations") or {}
    if not isinstance(locs, dict) or not locs:
        return []
    onsite = location_policy.get("onsite") is True
    city = " ".join(str(location_policy.get(k) or "").strip()
                    for k in ("city", "region", "country")).strip()
    if location_policy.get("remote") is True and not onsite:
        return []  # a remote req imposes no place; a real blocker would be an explicit knockout
    if not onsite and not city:
        return []  # the parse asserts nothing about presence -> derive nothing
    ko = {"type": LOCATION_KNOCKOUT_TYPE,
          "quote": f"onsite role — location: {city or '(unspecified)'} "
                   f"(derived from location_policy in jd.parsed.yaml; not a verbatim JD quote)",
          "place": city,
          "source": "derived:location_policy"}
    return [ko] if _knockout_matches(ko, profile) else []


def pre_resume_verdict(classifications: list[dict], knockouts: list[dict],
                       candidate_profile: dict | None) -> dict:
    # every must-have counts; anything not solidly supported (adjacent/unsupported/
    # missing/invalid) is weak so an unclassified must-have can't deflate U.
    must = [c for c in classifications if c.get("requirement") == "must"]
    weak = [c for c in must if c.get("support") not in ("direct", "partial")]
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
