# Prompt contract: `jd_parse`

**Purpose:** turn a raw job description into a structured, schema-valid
`Applications/<slug>/jd.parsed.yaml`. The deterministic scan has already run
(`python main.py jd parse <slug>` wrote `jd.scan.yaml` and this prompt); your job
is to interpret and structure — **never to invent requirements**.

**Inputs:** the `jd.txt` (verbatim, appended below) and the deterministic scan
(taxonomy hits + unknown candidates). Taxonomy ids live in `Context/taxonomy/terms.yaml`.

**Output:** `Applications/<slug>/jd.parsed.yaml`, conforming to
`Format/schemas/jd_parsed.schema.json`:

```yaml
schema: jd_parsed/v1
source_url: null            # or the posting URL if present on line 1 of jd.txt
company: ""
role_title: ""
seniority: unspecified      # intern|junior|mid|senior|staff|lead|unspecified
role_type: adas-validation  # adas-validation|av-infra|controls-software|embedded|ai-tooling|fullstack-saas|data-simulation-validation
location_policy: {onsite: false, city: null, remote: false}
knockouts:
  - {type: work_authorization, quote: "<verbatim jd.txt substring>"}
keywords:
  - {term: <taxonomy id>, requirement: must, quote: "<verbatim>", block: requirements}
  - {term: <taxonomy id>, requirement: nice, quote: "<verbatim>", block: preferred}
  - new_term:               # only when a real requirement has no taxonomy id yet
      canonical: "ISO 26262"
      suggested_ats_form: "ISO 26262 Functional Safety"
      suggested_aliases: [{text: "functional safety", tier: equivalent}, {text: "FuSa", tier: exact}]
      domain: validation
    requirement: must
    quote: "<verbatim>"
    block: requirements
title_terms: [<taxonomy ids in the title>]
implicit_expectations:
  - {expectation: "on-vehicle debugging comfort", quote: "<verbatim>", block: responsibilities}
```

**Hard rules (the CLI's `jd confirm` enforces these — fix until it passes):**
1. **Every `quote` MUST be a verbatim (whitespace-normalized) substring of `jd.txt`.**
   This single rule kills invented requirements. Copy real phrases, do not reword.
2. Every `keyword.term` must exist in `Context/taxonomy/terms.yaml`. If a real
   requirement has no id, propose it as a `new_term` (do not force a wrong id).
3. **You may not silently drop a deterministic-scan hit found in a `requirements`
   block.** Either include it as a keyword (must/nice/contextual) or mark it
   `false_positive: "<reason>"`. `ambiguous` short aliases (ACC, CAN) may be marked
   `false_positive` with justification.
4. `requirement`: `must` (hard requirement) | `nice` (preferred/bonus) | `contextual`
   (mentioned but not a requirement).

**After writing:** run `python main.py jd confirm <slug>`; resolve any error until it
stamps `confirmed: true` (Gate G1).
