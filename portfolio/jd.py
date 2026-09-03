from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass

from .facts import Violation
from .taxonomy import Taxonomy

BLOCKS = ("responsibilities", "requirements", "preferred", "benefits", "about", "other")

# Heading classifiers, checked in this order (preferred before requirements so
# "Preferred Qualifications" is not swallowed by the "qualifications" rule).
_HEADINGS: list[tuple[str, re.Pattern]] = [
    ("preferred", re.compile(r"(preferred|nice[-\s]?to[-\s]?have|bonus|a plus|desirable|good to have)", re.I)),
    ("requirements", re.compile(r"(requirements?|required|qualifications?|must[-\s]?have|minimum|what you.{0,4}ll (need|bring|have)|basic qualifications|your (skills|profile))", re.I)),
    ("responsibilities", re.compile(r"(responsibilit|what you.{0,4}ll do|the role|day[-\s]?to[-\s]?day|duties|in this role|you will)", re.I)),
    ("benefits", re.compile(r"(benefits|perks|compensation|what we offer|why (join|you))", re.I)),
    ("about", re.compile(r"(about\b|who we are|our (team|mission|company)|company overview)", re.I)),
]

_STOPWORDS = {"AND", "OR", "THE", "FOR", "YOU", "OUR", "ARE", "WILL", "WITH", "NOT", "ALL",
              "USA", "US", "EU", "CV", "PTO", "HR", "OK", "ID", "IT", "AI"}

# Title-case function words a real heading leaves lowercase ("What to Expect").
_TITLE_SMALL_WORDS = {"a", "an", "and", "as", "at", "by", "for", "from", "in",
                      "of", "on", "or", "the", "to", "with"}
_TITLE_WORD = re.compile(r"[A-Za-z][A-Za-z'’‐-]*")


def _title_case_like(s: str) -> bool:
    """Tolerant Title Case. ``str.istitle()`` is too strict for real headings: it
    rejects lowercase function words ("What to Expect") and treats the letter after
    an apostrophe as a new word ("What You'll Bring" -> False), so whole sections of
    Tesla-style JDs were never recognized as headings. Every word that is not a
    function word must still start uppercase, so sentence-case content lines
    ("Strong MATLAB required") are still rejected."""
    words = _TITLE_WORD.findall(s)
    cased = [w for w in words if w.lower() not in _TITLE_SMALL_WORDS]
    return bool(cased) and all(w[0].isupper() for w in cased)


def _is_heading_like(line: str) -> bool:
    s = line.strip().lstrip("#").strip()
    if not s or len(s) > 70:
        return False
    if s.endswith(":") or line.lstrip().startswith("#"):
        return True
    # A colon-less heading must LOOK like a section label (ALL-CAPS or Title Case),
    # not a short sentence — otherwise ordinary requirement lines like "Strong MATLAB
    # required" get misclassified as headings and dropped from the scan.
    return (len(s) <= 55 and not s.endswith(".")
            and not s.startswith(("-", "*", "•", "–", "◦"))
            and (s.isupper() or _title_case_like(s)))


def segment(text: str) -> list[tuple[str, str]]:
    """Assign each non-empty line to a block. Lines before the first heading -> 'other'."""
    out: list[tuple[str, str]] = []
    current = "other"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        matched = None
        if _is_heading_like(line):
            for block, pat in _HEADINGS:
                if pat.search(line):
                    matched = block
                    break
        if matched:
            current = matched
            continue  # the heading line itself is not scanned as content
        out.append((current, line))
    return out


def block_texts(text: str) -> dict[str, str]:
    acc: dict[str, list[str]] = {}
    for block, line in segment(text):
        acc.setdefault(block, []).append(line)
    return {b: "\n".join(lines) for b, lines in acc.items()}


@dataclass
class ScanHit:
    term_id: str
    alias: str
    tier: str
    block: str
    count: int


_TIER_RANK = {"exact": 0, "equivalent": 1, "related": 2}


def scan_jd(text: str, taxonomy: Taxonomy) -> list[ScanHit]:
    """Deterministic taxonomy scan, aggregated by (term_id, block). The reported
    tier is the STRONGEST alias seen (order-independent), not the first."""
    agg: dict[tuple[str, str], ScanHit] = {}
    for block, btext in block_texts(text).items():
        for hit in taxonomy.scan(btext):
            key = (hit.term_id, block)
            if key in agg:
                agg[key].count += 1
                if _TIER_RANK.get(hit.tier, 9) < _TIER_RANK.get(agg[key].tier, 9):
                    agg[key].tier, agg[key].alias = hit.tier, hit.alias
            else:
                agg[key] = ScanHit(hit.term_id, hit.alias, hit.tier, block, 1)
    return sorted(agg.values(), key=lambda h: (h.block, h.term_id))


_CAPS = re.compile(r"\b([A-Z][A-Z0-9]{1,5})\b")
_CAPPHRASE = re.compile(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})\b")
_TECH = re.compile(r"\b(\w+\+\+|\w+\.js|ISO ?\d{4,5}|[A-Z]{2,}[-/][A-Z0-9]{2,})\b")


def mine_candidates(text: str, taxonomy: Taxonomy) -> list[dict]:
    """Surface tokens the taxonomy does not yet know — feeds new_term proposals."""
    out: dict[str, dict] = {}

    def add(cand: str, kind: str):
        if not cand or taxonomy.has_alias(cand):
            return
        key = cand.lower()
        if key in out:
            out[key]["count"] += 1
        else:
            out[key] = {"candidate": cand, "kind": kind, "count": 1}

    for m in _CAPS.finditer(text):
        tok = m.group(1)
        if tok not in _STOPWORDS:
            add(tok, "acronym")
    for m in _TECH.finditer(text):
        add(m.group(1), "tech-shape")
    phrase_counts = Counter(m.group(1) for m in _CAPPHRASE.finditer(text))
    for phrase, n in phrase_counts.items():
        if n >= 2 and not taxonomy.has_alias(phrase):
            out.setdefault(phrase.lower(), {"candidate": phrase, "kind": "repeated-phrase", "count": n})
    return sorted(out.values(), key=lambda d: (-d["count"], d["candidate"]))


def jd_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _quotes(parsed: dict) -> list[tuple[str, str]]:
    """(where, quote) for every quote field in the parsed JD."""
    out: list[tuple[str, str]] = []
    for kw in parsed.get("keywords", []) or []:
        if "quote" in kw:
            out.append(("keyword", kw["quote"]))
    for ko in parsed.get("knockouts", []) or []:
        if "quote" in ko:
            out.append(("knockout", ko["quote"]))
    for ie in parsed.get("implicit_expectations", []) or []:
        if "quote" in ie:
            out.append(("implicit_expectation", ie["quote"]))
    return out


def validate_parsed(parsed: dict, jd_text: str, taxonomy: Taxonomy) -> list[Violation]:
    """Deterministic anti-hallucination checks on a jd.parsed.yaml (§4.2)."""
    v: list[Violation] = []
    norm_jd = _norm(jd_text)

    # every quote must be a non-empty verbatim substring of jd.txt — kills invented
    # requirements (an empty quote must NOT slip through the guard)
    for where, quote in _quotes(parsed):
        if not _norm(quote):
            v.append(Violation("error", where, "quote is empty — every quote must be a verbatim substring of jd.txt"))
        elif _norm(quote) not in norm_jd:
            v.append(Violation("error", where, f"quote is not a verbatim substring of jd.txt: {quote!r}"))

    # every keyword.term must exist in the taxonomy (unless it is a new_term proposal)
    for kw in parsed.get("keywords", []) or []:
        if "new_term" in kw:
            canonical = (kw["new_term"] or {}).get("canonical", "")
            for al in (kw["new_term"].get("suggested_aliases") or []):
                if taxonomy.has_alias(al.get("text", "")):
                    v.append(Violation("warning", "new_term",
                                       f"suggested alias '{al.get('text')}' already exists in the taxonomy"))
            if not canonical:
                v.append(Violation("error", "new_term", "new_term is missing a canonical name"))
        else:
            term = kw.get("term")
            if term and term not in taxonomy.by_id:
                v.append(Violation("error", "keyword", f"unknown term '{term}' (not in taxonomy.yaml)"))

    # a deterministic requirements-block scan hit may not be silently dropped;
    # a term may be dismissed via false_positive INSTEAD of being covered
    kws = parsed.get("keywords", []) or []
    covered = {kw.get("term") for kw in kws if kw.get("term") and not kw.get("false_positive")}
    fp = {kw.get("term") for kw in kws if kw.get("term") and kw.get("false_positive")}
    for hit in scan_jd(jd_text, taxonomy):
        if hit.block == "requirements" and hit.term_id not in covered and hit.term_id not in fp:
            v.append(Violation("warning", "coverage",
                               f"scan found '{hit.term_id}' in requirements but it is absent from keywords "
                               "(mark it must/nice/contextual or false_positive, do not drop)"))
    return v
