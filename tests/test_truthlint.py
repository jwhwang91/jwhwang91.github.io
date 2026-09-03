"""Red/green for the JD-independent truthfulness lints (Q1-Q7, Q11-Q14)."""
from portfolio.content import load_yaml
from portfolio.facts import Registry
from portfolio.paths import default_paths
from portfolio.truthlint import lint_resume

POLICY = load_yaml(default_paths().context / "facts" / "phrasing_policy.yaml")


def _registry(claims):
    return Registry(
        employers={"acme-adas": {"organization": "Acme", "org_renderings": ["Acme"],
                                 "official_title": "Eng", "title_renderings": ["Eng"],
                                 "period": {"start": "2020-01", "end": None},
                                 "forbidden_phrases": []}},
        education={}, credentials={}, policy=POLICY, titles={},
        claims=claims, claims_by_id={c["id"]: c for c in claims}, anchors=set(),
    )


SHARED = {"id": "c-shared", "status": "confirmed", "ownership": "shared", "deployment": "production", "metrics": []}
INDEP = {"id": "c-indep", "status": "confirmed", "ownership": "independent", "deployment": "production", "metrics": []}
METRIC = {"id": "c-metric", "status": "confirmed", "ownership": "independent", "deployment": "production",
          "metrics": [{"id": "m", "numbers": [10, 5], "value": "10 to 5", "as_of": "<OWNER TO DATE>"}]}
FORBID = {"id": "c-forbid", "status": "confirmed", "ownership": "independent", "deployment": "production",
          "metrics": [], "forbidden_phrases": ["secret project"]}


def _errs(vs):
    return [v.message for v in vs if v.level == "error"]


def _warns(vs):
    return [v.message for v in vs if v.level == "warning"]


def _exp(text, claims, source="acme-adas"):
    return {"experience": [{"source": source, "bullets": [{"text": text, "claims": claims}]}]}


# --- Q2: verb strength vs ownership ---

def test_overstrong_verb_on_shared_claim_errors():
    r = _exp("Led the brake distribution module.", ["c-shared"])
    assert any("Q2" in m for m in _errs(lint_resume(r, _registry([SHARED]))))


def test_contribution_verb_on_shared_claim_ok():
    r = _exp("Supported the brake distribution tuning.", ["c-shared"])
    assert not any("Q2" in m for m in _errs(lint_resume(r, _registry([SHARED]))))


def test_noun_led_bullet_defaults_to_contribution_with_warn():
    r = {"summary": [{"text": "Production validation of ADAS behavior logic.", "claims": ["c-indep"]}]}
    assert any("Q2" in m for m in _warns(lint_resume(r, _registry([INDEP]))))


# --- Q3: invented metrics ---

def test_orphan_number_errors():
    r = _exp("Developed a system improving accuracy by 42 percent.", ["c-indep"])
    assert any("Q3" in m for m in _errs(lint_resume(r, _registry([INDEP]))))


def test_metric_backed_number_ok():
    r = _exp("Developed tooling cutting trips from 10 to 5.", ["c-metric"])
    assert not any("Q3" in m for m in _errs(lint_resume(r, _registry([METRIC]))))


# --- Q4: metric staleness ---

def test_undated_metric_warns():
    r = _exp("Developed tooling cutting trips from 10 to 5.", ["c-metric"])
    assert any("Q4" in m for m in _warns(lint_resume(r, _registry([METRIC]))))


# --- Q5: missing dates ---

def test_experience_without_employer_anchor_errors():
    r = _exp("Developed a thing.", ["c-indep"], source="ghost-employer")
    assert any("Q5" in m for m in _errs(lint_resume(r, _registry([INDEP]))))


# --- Q7: forbidden phrasing ---

def test_forbidden_phrase_errors():
    r = _exp("Built the secret project end to end.", ["c-forbid"])
    assert any("Q7" in m for m in _errs(lint_resume(r, _registry([FORBID]))))


# --- Q12: vague claims ---

def test_vague_claim_errors():
    r = {"summary": [{"text": "Expert in everything, a world-class engineer.", "claims": ["c-indep"]}]}
    assert any("Q12" in m for m in _errs(lint_resume(r, _registry([INDEP]))))


# --- Q13: duplicated shingle ---

def test_duplicated_shingle_warns():
    dup = "the same six word phrase here"
    r = {"experience": [{"source": "acme-adas", "bullets": [
        {"text": "Developed " + dup + " one.", "claims": ["c-indep"]},
        {"text": "Built " + dup + " two.", "claims": ["c-indep"]},
    ]}]}
    assert any("Q13" in m for m in _warns(lint_resume(r, _registry([INDEP]))))


# --- Q1 + green ---

def test_uncited_bullet_errors():
    r = _exp("Developed a widget.", [])
    assert any("Q1" in m for m in _errs(lint_resume(r, _registry([INDEP]))))


def test_clean_resume_has_no_errors():
    r = _exp("Developed the widget stabilizer.", ["c-indep"])
    assert _errs(lint_resume(r, _registry([INDEP]))) == []


# --- skills section: chips are resume text too (previously invisible to every Q-lint) ---

def _skills(*items, label="Languages & Tooling"):
    return {"skills": [{"label": label, "items": list(items)}]}


def test_skills_chip_matching_a_forbidden_phrase_errors():
    # a chip cites no claim, so EVERY confirmed claim's forbidden_phrases apply:
    # nothing backs the phrasing those bans exist to prevent
    r = _skills("Secret project tooling")
    msgs = _errs(lint_resume(r, _registry([FORBID])))
    assert any("Q7" in m and "skills chip" in m for m in msgs)


def test_skills_chip_with_a_vague_claim_errors():
    r = _skills("Expert in vehicle dynamics")
    assert any("Q12" in m and "skills chip" in m for m in _errs(lint_resume(r, _registry([INDEP]))))


def test_skills_chip_with_a_bare_years_claim_errors():
    # global_forbidden_phrases: a years claim must pass the derived-years check instead
    r = _skills("10+ years of embedded controls")
    assert any("Q7" in m for m in _errs(lint_resume(r, _registry([INDEP]))))


def test_clean_skills_chip_passes():
    assert _errs(lint_resume(_skills("Model-based design"), _registry([INDEP]))) == []


# --- skills support check against the REAL registry + taxonomy (the C/C++ regression) ---

def _live():
    from portfolio.facts import load_registry
    from portfolio.taxonomy import Taxonomy
    p = default_paths()
    return load_registry(p), Taxonomy.load(p)


def test_unbacked_language_chip_is_flagged_against_the_live_registry():
    # `cpp` was removed from every claim's terms[] on 2026-09-03 (the K2 C was autocoded
    # from Simulink; the tc-xcp-bypass C++ was agent-written), so a "C / C++" chip has
    # nothing behind it. This chip shipped on a real submitted resume before the fix.
    from portfolio.truthlint import skills_support_check
    reg, tax = _live()
    vs = skills_support_check(_skills("C / C++"), reg, tax)
    assert any("cpp" in v.message for v in vs if v.level == "error")


def test_backed_chip_passes_against_the_live_registry():
    from portfolio.truthlint import skills_support_check
    reg, tax = _live()
    assert skills_support_check(_skills("MATLAB / Simulink"), reg, tax) == []


def test_a_jd_match_can_justify_a_chip_the_registry_alone_cannot():
    # the gate is allowed to accept a chip a direct/partial JD classification backs;
    # the standalone (classification-free) path stays stricter on purpose
    from portfolio.truthlint import skills_support_check
    reg, tax = _live()
    chip = _skills("C / C++")
    assert skills_support_check(chip, reg, tax) != []
    assert skills_support_check(chip, reg, tax, [{"term": "cpp", "support": "direct"}]) == []


def test_lint_resume_wires_the_support_check_only_when_given_a_taxonomy():
    reg, tax = _live()
    chip = _skills("C / C++")
    assert not any("Q1" in m for m in _errs(lint_resume(chip, reg)))
    assert any("Q1" in m for m in _errs(lint_resume(chip, reg, tax)))
