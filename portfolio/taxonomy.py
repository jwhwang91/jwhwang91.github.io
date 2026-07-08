from __future__ import annotations

import re
from dataclasses import dataclass, field

from .content import load_yaml
from .paths import Paths

TIERS = ("exact", "equivalent", "related")


@dataclass
class Alias:
    text: str
    tier: str = "exact"
    ambiguous: bool = False


@dataclass
class Term:
    id: str
    canonical: str
    ats_form: str
    domain: str
    aliases: list[Alias] = field(default_factory=list)


@dataclass
class Hit:
    term_id: str
    alias: str
    tier: str
    ambiguous: bool
    start: int
    end: int


class Taxonomy:
    """Deterministic alias matcher: case-insensitive, non-word-boundary, longest
    alias first. Alias tiers (exact/equivalent/related) drive Phase 4 support caps."""

    def __init__(self, terms: list[Term]):
        self.terms = terms
        self.by_id = {t.id: t for t in terms}
        # lowercased alias text -> (term_id, tier, ambiguous); first definition wins
        self._alias_map: dict[str, tuple[str, str, bool]] = {}
        for t in terms:
            for a in t.aliases:
                self._alias_map.setdefault(a.text.lower(), (t.id, a.tier, a.ambiguous))
        # longest-first alternation so "Adaptive Cruise Control" beats "ACC" at a shared start
        alts = sorted({a.text for t in terms for a in t.aliases}, key=len, reverse=True)
        self._re = re.compile(
            r"(?<!\w)(" + "|".join(re.escape(a) for a in alts) + r")(?!\w)", re.IGNORECASE
        ) if alts else None

    @classmethod
    def load(cls, paths: Paths) -> "Taxonomy":
        doc = load_yaml(paths.context / "taxonomy" / "terms.yaml")
        terms: list[Term] = []
        for t in doc.get("terms", []) or []:
            aliases = [
                Alias(a["text"], a.get("tier", "exact"), bool(a.get("ambiguous", False)))
                for a in (t.get("aliases") or [])
            ]
            terms.append(Term(t["id"], t.get("canonical", ""), t.get("ats_form", ""), t.get("domain", ""), aliases))
        return cls(terms)

    def has_alias(self, text: str) -> bool:
        return text.lower() in self._alias_map

    def scan(self, text: str) -> list[Hit]:
        if not self._re or not text:
            return []
        hits: list[Hit] = []
        for m in self._re.finditer(text):
            info = self._alias_map.get(m.group(1).lower())
            if info:
                tid, tier, amb = info
                hits.append(Hit(tid, m.group(1), tier, amb, m.start(1), m.end(1)))
        return hits
