"""Alias-matching engine: word boundaries, symbol tokens, tiers, ambiguity, longest-first."""
from portfolio.taxonomy import Alias, Taxonomy, Term


def _tax():
    return Taxonomy([
        Term("scc", "Smart Cruise Control", "Smart Cruise Control (SCC/ACC)", "adas",
             [Alias("SCC", "exact"), Alias("Adaptive Cruise Control", "equivalent"),
              Alias("ACC", "equivalent", ambiguous=True)]),
        Term("hil", "Hardware-in-the-Loop", "Hardware-in-the-Loop (HIL/HILS)", "validation",
             [Alias("HIL", "exact"), Alias("HILS", "exact"), Alias("hardware in the loop", "exact")]),
        Term("adas", "Advanced Driver Assistance Systems", "ADAS", "adas",
             [Alias("ADAS", "exact"), Alias("autonomous driving", "related")]),
        Term("cpp", "C/C++", "C/C++", "embedded", [Alias("C++", "exact"), Alias("C/C++", "exact")]),
        Term("canfd", "CAN-FD", "CAN-FD", "tooling", [Alias("CAN-FD", "exact")]),
    ])


def test_exact_aliases_match_case_insensitively():
    hits = _tax().scan("We run HIL benches, HILS rigs, and hardware in the loop.")
    assert [h.term_id for h in hits].count("hil") == 3


def test_no_match_inside_a_larger_word():
    hits = [h for h in _tax().scan("SCCX differs from a plain SCC bus.") if h.term_id == "scc"]
    assert len(hits) == 1  # matches standalone SCC, not SCCX


def test_symbol_tokens_match():
    tax = _tax()
    assert any(h.term_id == "cpp" for h in tax.scan("Strong C++ background."))
    assert any(h.term_id == "canfd" for h in tax.scan("Experience with CAN-FD networks."))


def test_tiers_are_surfaced():
    hits = {h.alias.lower(): h.tier for h in _tax().scan("Adaptive Cruise Control, ACC, and autonomous driving.")}
    assert hits["adaptive cruise control"] == "equivalent"
    assert hits["acc"] == "equivalent"
    assert hits["autonomous driving"] == "related"


def test_ambiguous_alias_flagged():
    acc = [h for h in _tax().scan("The ACC feature.") if h.alias.upper() == "ACC"][0]
    assert acc.ambiguous is True


def test_longest_alias_wins_at_shared_start():
    hits = _tax().scan("Adaptive Cruise Control validation program.")
    assert any(h.alias == "Adaptive Cruise Control" for h in hits)


def test_has_alias_lookup():
    tax = _tax()
    assert tax.has_alias("HILS") and tax.has_alias("acc")
    assert not tax.has_alias("kubernetes")
