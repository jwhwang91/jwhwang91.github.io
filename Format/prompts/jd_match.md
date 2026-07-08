# Prompt contract: `jd_match`

**Purpose:** classify the JD keywords the deterministic engine could NOT resolve
(the `queue` in `match.yaml` — new_terms with no taxonomy id, or entries flagged
`needs_review`). Deterministic terms are already classified against the confirmed
registry; **do not re-classify them.**

**Inputs:** `Applications/<slug>/match.yaml` (the `queue`), `jd.parsed.yaml`, the
confirmed claim registry (`Context/facts/claims/*.yaml`), `Context/taxonomy/terms.yaml`,
`Context/facts/phrasing_policy.yaml`.

**Output:** for each queued term, move it into `classifications` in `match.yaml` as:

```yaml
- term: <taxonomy id or the new canonical>
  support: direct | partial | adjacent | unsupported
  requirement: must | nice | contextual
  claim_ids: [<confirmed claim ids that support it>]
  matched_tier: exact | equivalent | related
  hedge: "<exposure-class phrasing from phrasing_policy>"   # required iff support == partial
  source: llm
  quote: "<verbatim jd.txt substring>"
```

**Hard rules (validated by `match confirm`):**
1. `support: direct` requires ≥1 cited claim whose `ownership ∈ {independent, shared}`.
   If you cannot cite such a claim, you MUST NOT say `direct` — downgrade to `partial`,
   `adjacent`, or `unsupported`.
2. Every `claim_id` must be a **confirmed** claim (`status: confirmed`). Proposed/retired
   claims are not citable.
3. `partial` requires a `hedge` drawn from the exposure lexemes in `phrasing_policy.yaml`
   ("exposure to", "familiar with", "working knowledge of", …).
4. Never invent support. If no claim supports the term and no confirmed claim shares its
   domain, it is `unsupported` (it goes to the gap report as a real gap).

**After writing:** run `python main.py match confirm <slug>` and resolve any error until
it stamps `confirmed: true` (Gate G2) and renders `gap_report.md` + `portfolio_plan.md`.
