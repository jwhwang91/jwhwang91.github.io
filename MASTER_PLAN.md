# MASTER PLAN — JD-Specific Resume / Portfolio / Interview-Prep Pipeline

> **Status:** Architecture plan authored by Fable (planning model). To be executed by Claude Opus 4.8.
> **Prime directive:** Maximize ATS pass probability **within hard truthfulness boundaries**. The first gate is a machine, not a recruiter — but no generated claim may ever exceed what the source-of-truth registry supports.
> **Repo:** `jwhwang91.github.io` — currently a YAML-driven static portfolio generator (`main.py`, 725 lines) with a manual, prompt-driven JD-adaptation loop under `Context/variants/` and per-application folders under gitignored `Applications/`.

---

## 0. Executive Summary of Decisions

| Decision | Choice |
|---|---|
| Code layout | Split `main.py` into a `portfolio/` package; `main.py` stays a thin shim; **all legacy flags keep working** (CI, playbooks, and docs embed them) |
| Canonical resume artifact | `resume.yaml` — structured, per-bullet `claims:[]` + `keywords:[]` citations. Humans edit **only** this file. All renders (txt/html/md/pdf) are derived |
| Scored artifact | `out/resume_ats.txt` — the deterministic plain-text render. Score what a worst-case ATS parser sees, never the YAML intent |
| Truth source | New `Context/facts/` claim registry (kebab-case IDs like `hmc-scc-emergency-stop`); existing `Context/*.yaml` stay as presentation views, lint-checked against the registry |
| Support classification | **Computed** per (JD term × claims) join — not stored on facts. Cached after one-time human confirmation in a **gitignored** keyword map |
| Keyword vocabulary | Central `Context/taxonomy/terms.yaml` with alias tiers `exact / equivalent / related`; committed (pure domain knowledge, no personal data) |
| Division of labor | **LLM proposes, deterministic Python disposes, human approves.** Every LLM output is schema-validated YAML with verbatim-quote and claim-ID checks. Zero LLM in scoring/gating |
| LLM runtime (v1) | Claude Code local mode: repo-local slash commands wrapping `Format/prompts/*.md`; API mode later through the same prompt files |
| ATS gate | Hard gate on: format lint errors = 0, supported must-have coverage = 100%, unsupported-must-have ratio thresholds. **No composite numeric score in v1** (no calibration data yet) |
| PDF | v1: manual browser Save-as-PDF + **mandatory** text-layer verification (pypdf extract, `SequenceMatcher ≥ 0.98` vs `resume_ats.txt`). Playwright automation later |
| DOCX | Deferred. Trigger: an ATS-ledger-recorded rejection attributable to PDF parsing. Implementation then: `python-docx` walker over `resume.yaml` |
| Tracking | `application.yaml` per application with an enforced status state machine; `status submitted` is a mechanical hard gate. `result.md` retired (compat reader kept) |
| Privacy | **Phase 0, before anything else**: untrack `_source_references/` (raw Hyundai material is public today), untrack `dist/`, `__pycache__`, `.idea/`; move phone number out of the public repo; pre-commit + CI guards |
| Korean | v1 is English-only. Korean JD aliases / Korean resume output staged explicitly for later — acknowledged, not forgotten |

---

## 1. Current Repository Assessment

### 1.1 What the repo already does well (preserve)

- **The backbone/overlay model** (`select_and_override` + `apply_variant`, main.py:401–451). "Backbone is truth; variants only select / reorder / reword, never invent" is the repo's best design decision and is exactly the invariant the automated system must mechanize. Merge semantics are clean and diffable: omitted `include` = inherit all; `include: []` = hide section; per-id shallow `overrides`.
- **Per-application folders** (`Applications/<name>/` with `jd.txt`, `overlay.yaml`, `notes.md`, `result.md`, `resume.html`), gitignored. Already the natural unit for the whole pipeline; keep and extend.
- **The documented human/LLM loop** (`PIPELINE.md` Stages A–D; `Context/variants/PLAYBOOK.md`, `ATS_LEDGER.md`, `REJECTION_PIPELINE.md`, `EVOLUTION.md`). Three ideas in it are genuinely sophisticated and must be encoded in code, not lost:
  1. **Only ATS-stage rejections drive keyword changes** (post-interview rejections mean the resume passed — fix interview prep instead).
  2. **Auto-knockout vs keyword-gap separation** (visa/location filters are not resume problems).
  3. **Public-anonymized ledger vs private per-application folders** privacy split.
- **The outcome scoreboard** (`parse_result` / `gather_results` / `ats_passed` / `print_insights`, main.py:539–653) — tri-state ATS inference from controlled vocabulary; the seed of the tracker.
- **ATS text-layer mechanics already solved in templates**: `kw-sep` invisible-comma chip delimiters, `.print-only` URL echoes, `noindex` on variants, `variant-compact` one-page print mode, the "never Microsoft Print to PDF" discipline.
- **Deploy flow**: CI rebuilds `dist/` from scratch and publishes only `dist/`; `Applications/` can never reach the published artifact.

### 1.2 What is fragile (fix before extension)

1. **Silent failure modes**: `select_and_override` silently drops typo'd ids (main.py:437) — a misspelled `include:` entry deletes a resume section with no warning; `copy_static_files`/`copy_assets` silently skip; `pdf_text_warning` swallows all exceptions; `result.md` parsing drops misspelled fields.
2. **Module-level path globals** (main.py:16–26) referenced by nearly every function — nothing is testable without monkeypatching. Zero tests exist.
3. **Template dual-use landmine**: `index.html.j2` renders both the public site and every resume variant (switched by `variant_mode`). A site redesign silently reflows already-tuned one-page resumes.
4. **Shallow merges clobber data**: an overlay overriding `resume.skills` replaces all groups; empty-string values blank fields by design but with no guard.
5. **Implicit build ordering**: `render_standalone_index` must run last (re-reads rendered `dist/` files); enforced only by call sequence.
6. **Undeclared dependency**: `pypdf` is used by the documented ATS safety net but absent from `requirements.txt` — the check silently does nothing on fresh installs.
7. **Scaffold templates and controlled vocabularies live as Python string constants** (main.py:306–398, 533–536) that must be kept in sync by hand.
8. **No schema validation anywhere** — YAML shape is defined only by template usage; malformed files give bare `KeyError` tracebacks.

### 1.3 Privacy findings (urgent — Phase 0)

The repo is `jwhwang91.github.io`, so the **entire git tree is public**, independent of what Pages serves:

- **`_source_references/` is fully committed and public**, including `HMC_Portfolio_정리.pptx` (internal-looking Hyundai deck), `past_portfolio.pdf`, and Hyundai vehicle photos. It is not in `.gitignore` at all. This is the single worst exposure in the repo.
- **Personal phone number** (redacted here; the `phone` field in `Context/personal_info.yaml`) is committed and rendered into the indexed public site (`dist/index.html`, `dist/standalone.html` — no `noindex` on the main site).
- **`dist/` is committed AND rebuilt in CI** — dead weight that doubles the exposure surface and drifts from what is live.
- `__pycache__/main.cpython-311.pyc` and `.idea/` are tracked noise.
- Correctly private already: `Applications/` (gitignored, zero tracked files — executor must re-verify with `git ls-files Applications/`), `Context/candidate_profile.yaml` (gitignored, doesn't exist yet).

Also flagged: any **new** data file that charts the job search (keyword-support cache with `unsupported` entries, tracking exports) must default to gitignored — employers read this repo.

### 1.4 Refactoring verdict

- **Split `main.py`** into a `portfolio/` package along the natural seams (see §14 Phase 1): `paths.py`, `content.py`, `site.py`, `inline.py`, `variants.py`, `tracking.py`, `cli.py` — plus new pipeline modules. `main.py` remains the entry point with byte-compatible legacy flags (`--variant`, `--new-variant`, `--list-variants`, `--all-variants`, `--insights`, bare invocation).
- **Give the ATS resume its own template** (`resume_ats.html.j2`), fully independent of `index.html.j2`. The existing pretty `resume.html` path stays as the optional human/referral variant.
- **Do not touch unless necessary**: the rich hand-authored `Context/Experiences/*/context.yaml` detail pages (their prose quality is the point — they become lint-checked, never generated), the standalone.html inliner machinery, the deploy workflow's basic shape, `Style/theme.css` site styling.
- **YAML evolution**: existing `Context/*.yaml` files stay as render inputs. A new `Context/facts/` registry becomes the truth authority (§3); a linter binds the two. Never retrofit claim metadata into presentation files.
- **GitHub Pages evolution**: stop committing `dist/`; add `paths:` filtering to the deploy trigger so tracker-adjacent commits don't redeploy the site; add a CI guard asserting no private path is tracked.

---

## 2. Target System Vision

### 2.1 The product

One repo = one **job-application operating system** with three layers:

1. **Truth layer** (committed): claim registry + taxonomy + backbone site content. Slow-changing, human-confirmed, machine-validated.
2. **Pipeline layer** (committed code + prompts): deterministic parsers, matchers, scorers, gates, renderers; LLM prompt contracts; slash commands.
3. **Application layer** (gitignored): one folder per JD holding every generated artifact and the tracking record, from first paste to post-mortem.

Per JD, the system produces: **(1)** ATS-optimized truthful resume (yaml → txt/html/md/pdf), **(2)** keyword-match + gap analysis, **(3)** portfolio emphasis plan, **(4)** technical interview pack, **(5)** coding interview pack, **(6)** a tracked application record with feedback loop.

### 2.2 Design principles

1. **LLM proposes, Python disposes, human approves.** Every LLM step emits schema-validated YAML. Deterministic validators check claim-ID existence, verbatim JD quotes, verb-strength vs ownership, forbidden phrasing. Humans gate at five fixed points (G0–G4, §2.3).
2. **Score extracted text, not intent.** The gate runs on `resume_ats.txt` and re-verifies the actual PDF text layer.
3. **Select, don't generate**, wherever selection suffices: coding problems come from a curated bank; headline titles from an approved list; hedge phrases from an allowlist.
4. **The CLI is a stage machine; Claude Code is the worker.** Each command checks prerequisites and prints the exact next action.
5. **Learning never mutates truth.** Lessons flow to the anonymized public ledger or to a learn-before-apply backlog — never automatically into `Context/` backbone or the registry.
6. **Fail loudly.** Every silent-skip in the current code becomes a validation error with file+key context.

### 2.3 End-to-end user workflow

| # | Step | Actor | Command / artifact |
|---|---|---|---|
| 0 | One-time: confirm bootstrap facts (**Gate G0**) | Human | review `Context/facts/` proposals, flip `status: proposed → confirmed` |
| 1 | Scaffold application, paste JD | Human | `python main.py new tesla-adas-validation-2026-07 --company Tesla --positioning adas-av-validation` → paste into `jd.txt` |
| 2 | Parse JD | Python + LLM | `python main.py jd parse <slug>` (deterministic scan + prompt assembly) → `/jd-parse <slug>` in Claude Code → `jd.parsed.yaml` |
| 3 | Confirm parse (**Gate G1**) | Human | `python main.py jd confirm <slug>` — 60-second skim; every keyword shows its verbatim JD quote |
| 4 | Classify support | Python + LLM | `python main.py match <slug>` (cache-resolve; queues only unresolved terms) → `/jd-match <slug>` → `match.yaml` |
| 5 | Confirm classifications (**Gate G2**) | Human | `python main.py match confirm <slug>` (status → `matched`) — cache updated; renders `gap_report.md` (with pre-resume recommendation) + `portfolio_plan.md` |
| 6 | Go / no-go | Human | read `gap_report.md`; if pre-resume verdict is `Do-Not-Apply-Yet`, `status abandoned` and/or add a BACKLOG item |
| 7 | Draft resume | LLM | `/resume-plan <slug>` → `resume.yaml` (cited bullets only) |
| 8 | Finalize resume draft | Human | edit `resume.yaml` directly; `python main.py validate <slug> --stage resume` (status → `drafted`) |
| 9 | Render + gate | Python | `python main.py render <slug>` → `out/resume_ats.{txt,html,md}` + `gate_report.{yaml,md}` + `checklist.md` + `changes.md` + `audit.json` (status → `gated` on PASS); FAIL → loop to step 7 with `gate_feedback` |
| 10 | Approve gated package (**Gate G3**) | Human | review `gate_report.md`, `checklist.md`, `changes.md`; `python main.py status <slug> approved` |
| 11 | Export + verify PDF | Human + Python | browser Save-as-PDF → `out/resume_final.pdf`; `python main.py pdfcheck <slug>` (blocks on missing text layer) |
| 12 | Prep packs | LLM + Python | `/interview-pack <slug>`, `/coding-pack <slug>` → validated + rendered under `prep/` |
| 13 | Submit (**Gate G4** — hard gate) | Human | `python main.py status <slug> submitted` — refuses without status `approved`, gate PASS (or acknowledged risk), verified PDF, unchanged `jd.txt` |
| 14 | Track events | Human | `python main.py log <slug> --note "recruiter email"` ; `python main.py status <slug> interview` |
| 15 | Outcome + lessons | LLM | `/rejection <slug>` → fills `outcome:` + `lessons:` in `application.yaml` |
| 16 | Evolve | Python + LLM + Human | `python main.py lessons compile` → anonymization-linted draft → `/evolve-ledger` → human commits `ATS_LEDGER.md` update |

**Status auto-advance**: `jd confirm` → `parsed`; `match confirm` → `matched`; first passing `validate --stage resume` → `drafted`; gate PASS inside `render`/`gate` → `gated`. Humans set only `approved`, `submitted`, and post-submission statuses.

---

## 3. Source-of-Truth Data Architecture

### 3.1 Layout

```
Context/
  facts/                          # committed, public-safe by construction
    employers.yaml                # canonical org names / titles / dates — the drift anchor
    positioning_titles.yaml       # approved headline titles per positioning track
    phrasing_policy.yaml          # verb-strength lexicons, tier rules, numeric whitelist
    claims/
      hmc.yaml                    # claim ids prefixed hmc-
      add-k2.yaml                 # add-
      kaist.yaml                  # kaist-
      software.yaml               # sw-
      toolchains.yaml             # tc-
      education.yaml              # edu- / cert-
  taxonomy/
    terms.yaml                    # alias/expansion table — committed (domain knowledge only)
  private/                        # gitignored (NEW .gitignore entry: /Context/private/)
    keyword_map.yaml              # human-confirmed JD-term → support cache (charts skill gaps → private)
    redlines.yaml                 # literal never-print strings (internal signal names, etc.)
    personal_private.yaml         # phone number + any other contact data kept off the public site
  candidate_profile.yaml          # gitignored (already in .gitignore); schema defined in §3.6
```

### 3.2 Claim record schema (`Format/schemas/claim.schema.json`; kebab-case IDs, immutable — evolve via `superseded_by`)

```yaml
# Context/facts/claims/hmc.yaml (illustrative excerpt with real content)
claims:
  - id: hmc-scc-emergency-stop
    status: confirmed              # proposed | confirmed | retired  (only confirmed is citable)
    confidence: high               # high | medium | low — how defensibly the owner can discuss this
                                   # claim under interview pressure. low ⇒ bullet strength capped at
                                   # contribution class and the claim is always listed in risky_for_review
    anchor: hmc-adas               # key into employers.yaml (or project id for sw-/tc-)
    statement: >
      Independently developed and validated SCC emergency-stop behavior
      (driver-incapacitated safe-stop) for selected production-facing
      commercial-vehicle SCC/L2 ADAS workflows.
    ownership: independent         # independent | shared | support | exposure
    deployment: production         # production | prototype | research | personal
    terms: [scc, adas, state-machine, functional-safety]   # taxonomy term ids (see §4.1)
    term_caps: {functional-safety: partial}   # this claim supports the term only as hedged exposure
    metrics: []                    # empty ⇒ validator bans ALL numbers in bullets citing only this claim
    forbidden_phrases:
      - "(owned|led|architected) the (full|entire|end-to-end) (SCC|L2|ADAS)"
    disclosure:
      public_safe: true
      omitted: [internal state names, thresholds, calibration values]
    evidence:
      - {type: internal, ref: "HMC commercial-vehicle production programs, 2021.03–present", verifiable_by: employer}
      - {type: site, ref: "Context/Experiences/hmc_adas/context.yaml#case_studies[0]", verifiable_by: public}
    interview:
      topics: [state-machines, fail-safe-design, driver-monitoring-handover]
      coding_relevance: [state-machine-implementation, c-cpp]
    source_quote:                  # REQUIRED at bootstrap; informational after G0 confirmation
      file: Context/Experiences/hmc_adas/context.yaml
      quote: "Independently developed and validated SCC emergency-stop behavior for selected production-facing commercial-vehicle ADAS workflows."

  - id: hmc-bev-replay-metric
    status: confirmed
    anchor: hmc-adas
    statement: >
      Used BEV replay of real logs through production TOS/ODP target-selection logic
      to debug bus-only-lane false-detection cases before real-vehicle confirmation.
    ownership: independent
    deployment: production
    terms: [target-selection, log-replay, bev, simulation]
    metrics:
      - id: trip-reduction
        numbers: [10, 5]
        value: "≈10 → ≈5 repeated road-test trips per false-detection issue"
        method: "count of repeated bus-only-lane validation trips before/after replay workflow"
        as_of: "<OWNER TO DATE>"
        allowed_renderings:
          - "from about 10 trips to about 5"
          - "reduced repeated road-test loops by ~50%"
          - "cut scenario-debugging test time by about half"
      - id: trip-duration
        numbers: [4, 5]
        value: "4–5 hours per trip"
        method: "typical duration of one bus road-test trip"
        allowed_renderings: ["each trip taking 4–5 hours"]
    evidence:
      - {type: site, ref: "Context/Experiences/hmc_adas/context.yaml#case_studies[3]", verifiable_by: public}
      - {type: repo, ref: "Context/toolchain_projects.yaml#tos-odp-bev-simulator", verifiable_by: public}
    interview: {topics: [resimulation-architecture, false-positive-triage], coding_relevance: [python-data-pipeline]}
    source_quote: {file: Context/Experiences/hmc_adas/context.yaml, quote: "Reduced repeated bus-only-lane road-test loops from about 10 trips to about 5 for similar false-detection issues."}

  - id: hmc-foc-brake-distribution
    status: confirmed
    anchor: hmc-adas
    statement: >
      Participated in rule-based front-target brake-distribution work (auxiliary vs foundation
      brake split from ego speed, forward-target speed, speed gradient, relative distance,
      required deceleration) within SCC/FOC tuning.
    ownership: shared              # "Participated" in source — verb ceiling is CONTRIBUTION class
    deployment: production
    terms: [longitudinal-control, ebs, braking, scc]
    forbidden_phrases: ["(designed|owned|led) the brake distribution"]
    evidence: [{type: site, ref: "Context/Experiences/hmc_adas/context.yaml#case_studies[2]", verifiable_by: public}]
    source_quote: {file: Context/Experiences/hmc_adas/context.yaml, quote: "<verbatim line>"}
```

```yaml
# Context/facts/claims/software.yaml (excerpt — machine-readable negative constraint that
# today exists only as a YAML comment)
claims:
  - id: sw-pathpilot-app
    status: confirmed
    anchor: pathpilot
    statement: >
      Built PathPilot, a Swift/SwiftUI+AppKit macOS file manager (StoreKit one-time Pro unlock,
      security-scoped bookmarks, Trash-only deletes, undo, no telemetry). App Store listing
      finalized but not yet live.
    ownership: independent
    deployment: prototype          # NOT published — deployment field carries the constraint
    terms: [swift, macos-development, desktop-apps]
    forbidden_phrases:
      - "published (App Store|Mac App Store) app"
      - "available on the App Store"
      - "github\\.com/jwhwang91/pathpilot"     # private repo — never print the URL
    evidence:
      - {type: live, ref: "https://jwhwang91.github.io/pathpilot-site/", verifiable_by: public}
      - {type: repo_private, ref: "~70 Swift files, private repo", verifiable_by: self}
```

Facts the owner's brief mentions but the backbone doesn't yet support (e.g. **LFA** — backbone says only "SCC/L2") are bootstrapped as `status: proposed` with `statement: <placeholder>` and are **not citable** until the owner confirms them at Gate G0.

**Bootstrap inventory (~30 claims, trimmed for one-person curation):**
`hmc-scc-emergency-stop, hmc-ekf-roadradius, hmc-foc-brake-distribution, hmc-scc-tuning-state-transition, hmc-bev-replay-metric, hmc-target-selection, hmc-validation-workflow, hmc-platforms, hmc-patents, hmc-ai-toolchains, hmc-lfa-validation(proposed)`; `add-clutch-adaptation, add-plant-modeling, add-hils-validation, add-dyno-field-test, add-can-tooling`; `kaist-turret-stabilization, kaist-tde-control, kaist-kalman-fusion, kaist-hardware-verification`; `sw-deckflip-pipeline, sw-deckflip-editor, sw-decisioncanvas-engine, sw-voiceprint, sw-pinterest-oauth, sw-pathpilot-app`; `tc-xcp-bypass, tc-timeseries-ai, tc-bev-simulator`; `edu-ucla-bs, edu-kaist-ms, cert-class1-license, cert-trailer-license`.

### 3.3 Drift anchors — `employers.yaml`

One canonical name/title/date per employer; every rendering anywhere must match:

```yaml
employers:
  hmc-adas:
    organization: "Hyundai Motor Company"
    org_renderings: ["Hyundai Motor Company (HMC)", "Hyundai Motor Company", "HMC"]
    official_title: "Commercial Vehicle ADAS Controls & Validation Engineer"
    title_renderings:
      - "Commercial Vehicle ADAS Controls & Validation Engineer"
      - "ADAS Controls & Validation Engineer (Commercial Vehicles)"
    period: {start: 2021-03, end: null}
    forbidden_phrases: ["(Senior|Staff|Lead|Principal) .* Engineer, Hyundai"]  # never claim unheld rank
  add-k2-tcu:
    organization: "Agency for Defense Development (ADD), Ground Technology Research Institute"
    official_title: "Researcher - TCU Application Software"
    period: {start: 2017-09, end: 2021-03}
  kaist-masters:
    organization: "Korea Advanced Institute of Science and Technology (KAIST)"
    official_title: "Graduate Researcher"
    period: {start: 2015-03, end: 2017-08}
education:
  ucla:  {institute: UCLA,  degree: "B.S. Mechanical Engineering", period: {start: 2010-09, end: 2014-06}}
  kaist: {institute: KAIST, degree: "M.S. Robotics", period: {start: 2015-03, end: 2017-08},
          thesis: "Controller Design for Motion Stabilization of a Turret on a Moving Platform"}
derived:
  years_of_experience: {from: add-k2-tcu.period.start, rule: floor}   # "N+ years" must satisfy N ≤ floor(computed)
```

### 3.4 `phrasing_policy.yaml` — the mechanical hedging engine

```yaml
strength_classes:
  ownership:      # requires EVERY cited claim: ownership = independent
    lexemes: [developed, designed, built, architected, owned, created, implemented, led,
              "independently developed", engineered, authored]
  contribution:   # requires every cited claim: ownership ∈ {independent, shared}
    lexemes: ["contributed to", "participated in", supported, "worked on", "co-developed",
              improved, tuned, validated, analyzed, tested]
  exposure:       # the ONLY class allowed when any cited claim is ownership: support|exposure,
                  # or when the JD term maps through a `related` alias / term_caps: partial
    lexemes: ["exposure to", "familiar with", "hands-on experience with",
              "built related tooling for", "adjacent experience in", "working knowledge of"]
detection:        # noun-led bullets are legal (fixes fail-closed misfire on "Production validation of…")
  rule: >
    Scan the whole bullet for lexemes; the STRONGEST class found anywhere is the bullet's class.
    If no lexeme is found, class = contribution and a lint WARNING names the inferred class.
    Any ownership-class lexeme present while a cited claim disallows it ⇒ hard fail.
numeric_whitelist: ["2D", "L2", "A4", "J1939", "CAN-FD", "K2", "OAuth 2.0", "ISO 26262"]
vague_claim_lexicon:        # §12 detection — lint error in resume text
  - "expert in"
  - "world-class"
  - "responsible for the entire"
  - "involved in (various|numerous)"
  - "results-driven"
global_forbidden_phrases:
  - "\\b(9|10|11)\\+? years"   # any years-claim must pass the derived-years check instead
```

### 3.5 `positioning_titles.yaml`

Headline titles are positioning statements, not employment titles; they must come from this approved list (validator-enforced):

```yaml
tracks:
  vehicle-systems-validation: ["Vehicle Systems Validation Engineer", "ADAS Validation Engineer"]
  adas-av-validation: ["ADAS/AV Validation Engineer", "ADAS Controls & Behavior-Logic Engineer"]
  embedded-controls: ["Embedded Controls Software Engineer", "Controls Software Engineer"]
  ai-tooling-fullstack: ["Software & AI Application Engineer", "Full-Stack AI Engineer"]
  systems-ai-automation: ["Systems Engineer — AI Automation", "Software & Systems Engineer"]
```

### 3.6 `candidate_profile.yaml` (gitignored; consumed by knockout logic and the rejection pipeline)

```yaml
work_authorization:
  kr: citizen
  us: {status: requires-sponsorship, notes: ""}
  eu: {status: unknown, notes: "EU Blue Card path unresolved"}
locations: {current: "South Korea", relocation: open, remote: preferred}
target_employers: []          # feeds REJECTION_PIPELINE "widen funnel" move
constraints: []               # e.g. earliest start date
```

Validated by `Format/schemas/candidate_profile.schema.json`; scaffolded by Phase 4 (`match` prints a creation hint when missing). **Absent-file rule**: knockout checks skip with a visible printed notice — same convention as the gitignored `redlines.yaml` (§12 Q7).

### 3.7 Migration path

Existing `Context/*.yaml` files are **not** rewritten. A build-time linter (§12, T7/T11) checks dates/titles/orgs in them against `employers.yaml` (warning-level first, error later) and, post-G0, checks that summary bullets trace to claims. The rich `context.yaml` detail pages stay hand-authored forever.

---

## 4. JD Parsing and Matching Engine

### 4.1 Keyword taxonomy — `Context/taxonomy/terms.yaml`

Central, committed, zero personal data. Alias matching is deterministic: case-insensitive, word-boundary, longest-match-first regex alternation. **Alias tiers is the core modeling decision:**

| tier | meaning | matching effect | claiming effect |
|---|---|---|---|
| `exact` | same thing, different spelling (HIL/HILS) | full match | substitutable freely |
| `equivalent` | industry synonym / OEM brand name (SCC ↔ ACC) | full match | claimable as direct; resume prints both forms |
| `related` | same family, not identical (LFA vs LKA vs lane centering) | match, but caps support at `partial` | requires hedged phrasing |

```yaml
terms:
  - id: scc
    canonical: "Smart Cruise Control"
    ats_form: "Smart Cruise Control (SCC / Adaptive Cruise Control)"   # exact first-use string
    domain: adas
    aliases:
      - {text: "SCC", tier: exact, ambiguous: false}
      - {text: "Adaptive Cruise Control", tier: equivalent}
      - {text: "ACC", tier: equivalent, ambiguous: true}   # ambiguous short aliases require confirm
  - id: hil
    canonical: "Hardware-in-the-Loop"
    ats_form: "Hardware-in-the-Loop (HIL/HILS)"
    domain: validation
    aliases: [{text: HIL, tier: exact}, {text: HILS, tier: exact}, {text: "hardware in the loop", tier: exact}]
  - id: ekf
    canonical: "Extended Kalman Filter"
    ats_form: "Extended Kalman Filter (EKF)"
    domain: controls
    aliases:
      - {text: EKF, tier: exact}
      - {text: "Kalman filter", tier: equivalent}
      - {text: "sensor fusion", tier: related}
  - id: adas
    canonical: "Advanced Driver Assistance Systems"
    ats_form: "Advanced Driver Assistance Systems (ADAS)"
    domain: adas
    aliases:
      - {text: ADAS, tier: exact}
      - {text: "L2 automation", tier: equivalent}
      - {text: "autonomous driving", tier: related}   # AV ≠ ADAS: deliberate partial cap
  # ... seed ≈ 60 terms derived from the 5 JD fixtures, across domains:
  # adas, controls, embedded, validation, software, ai_llm, tooling.
  # Grown organically: every human-confirmed new_term proposal is appended.
```

`ambiguous: true` aliases (ACC, CAN in prose) never auto-force their way into the must-confirm list — the LLM may mark scanned hits `false_positive` with justification; the human confirm decides.

### 4.2 JD ingestion & parsing

**Input**: `Applications/<slug>/jd.txt` — raw UTF-8 paste, optional posting URL on line 1 (unchanged from today; the human types nothing twice).

**Deterministic pass** (`portfolio/jd.py`):
1. Segment by heading regexes into blocks: `responsibilities | requirements | preferred | benefits | about | other`; extract bullets.
2. Run the taxonomy automaton → `{term_id, alias_matched, tier, block_type, count}` hits.
3. Mine `unknown_candidates`: ALL-CAPS tokens (2–6 chars, minus stopwords), repeated Capitalized Phrases, tech-shape tokens (`\w+\+\+`, `\w+\.js`, `ISO ?\d{4,5}`).

**LLM pass** — `Format/prompts/jd_parse.md`, output `jd.parsed.yaml`:

```yaml
schema: jd_parsed/v1
source_url: "https://…"            # or null
company: "Tesla"
role_title: "ADAS Validation Engineer"
seniority: senior                   # intern|junior|mid|senior|staff|lead|unspecified
role_type: adas-validation          # adas-validation | av-infra | controls-software | embedded |
                                    # ai-tooling | fullstack-saas | data-simulation-validation
location_policy: {onsite: true, city: "Palo Alto, CA", remote: false}
knockouts:
  - {type: work_authorization, quote: "must be authorized to work in the US without sponsorship"}
keywords:
  # requirement enum: must | nice | contextual
  - {term: hil, requirement: must, quote: "experience with HIL test benches", block: requirements}
  - {term: scc, requirement: must, quote: "adaptive cruise control feature validation", block: requirements}
  - {term: jira, requirement: nice, quote: "familiarity with Jira is a plus", block: preferred}
  - new_term:
      canonical: "ISO 26262"
      suggested_ats_form: "ISO 26262 Functional Safety"
      suggested_aliases: [{text: "functional safety", tier: equivalent}, {text: FuSa, tier: exact}]
      domain: validation
    requirement: must
    quote: "working knowledge of ISO 26262"
    block: requirements
title_terms: [adas, validation]
implicit_expectations:              # unwritten-but-implied expectations, each anchored to a JD quote
  - {expectation: "on-vehicle debugging comfort", quote: "field testing at our proving grounds", block: responsibilities}
  - {expectation: "cross-functional work with perception team", quote: "partner closely with Autopilot perception", block: about}
```

**Deterministic validators (the anti-hallucination layer):**
- jsonschema validation.
- Every `quote` must be a **verbatim (whitespace-normalized) substring of `jd.txt`** — this single check kills invented requirements.
- Every `term` must exist in `terms.yaml`; `new_term.canonical` must not already be an alias (validator rewrites + logs).
- Every deterministic-scan hit in a `requirements` block must appear in `keywords` — the LLM may downgrade to `contextual` or mark `false_positive: <reason>`, but may not silently drop.
- **Gate G1**: `jd confirm` prints term | must/nice | quote table; stamps `confirmed: true`.

### 4.3 Support classification (`portfolio/classify.py`)

**Deterministic resolution first** (per JD keyword, in order):
1. **Cache lookup** in gitignored `Context/private/keyword_map.yaml` → hit = zero LLM.
2. **Registry join**: claims where `term_id ∈ claim.terms`, honoring `term_caps`:
   - ≥1 claim with `ownership ∈ {independent, shared}` AND JD matched via `exact|equivalent` alias → **direct**
   - claims exist but best ownership is `support|exposure`, OR matched via `related` alias, OR `deployment: prototype` for a production-implying term, OR `term_caps` says partial → **partial** (hedge mandatory)
   - no term match but ≥1 claim shares the term's `domain` → **adjacent**
   - otherwise → **unsupported**
3. Unresolved (`new_term`s, `needs_review` flags) → LLM queue (`Format/prompts/jd_match.md`), whose output per keyword is `{term, support, claim_ids, hedge, rationale, suggested_resume_phrasing}` with validators: `direct` requires ≥1 cited claim with qualifying ownership (auto-downgrade + log otherwise); `partial` requires hedge ∈ allowlist; phrasing must contain the term's `ats_form` and must not contain ownership-inflating verbs when claims are `shared/support`.

**Gate G2**: `match confirm` — y/n/edit per fresh classification; confirmed entries append to the cache with a date stamp. When the registry changes, the CLI prints "N cached entries may be stale — re-confirm" (no sha-machinery in v1; downgrades automatic on next join, upgrades always re-gated).

**Determinism guarantee**: warm cache + confirmed parse ⇒ re-running the pipeline on the same `jd.txt` performs zero LLM calls and is byte-reproducible.

### 4.4 Scoring & risk (all deterministic, on `resume_ats.txt`)

- **MustHaveCoverage** = present supported must-haves ÷ supported must-haves. **Gate metric: must be 100%.**
- **Coverage%** (reported per must/nice class): presence of any `exact|equivalent` alias (`related` counts 0.5), weighted by placement.
- **Placement rule** per must-have: appears in Skills **and** ≥1 body section (Experience|Projects) = full; single section = warn; Summary-only = warn.
- **Unsupported-must-have ratio** `U` = |must-haves classified adjacent/unsupported| ÷ |must-haves|: `U ≥ 0.50` → HIGH_RISK / Do-Not-Apply-Yet; `0.25 ≤ U < 0.50` → elevated / Revise cap.
- **TitleAlign**: token overlap between `resume.role_title` and JD title after canonicalization; title must be in `positioning_titles.yaml` (else format error).
- **Stuffing clamp**: any keyword >4 occurrences = warn, >6 = error; Summary with taxonomy-term tokens >35% = error.
- **Confidence** High/Medium/Low: High = ≥90% keywords cache/registry-resolved AND parse confirmed; Medium ≥60%; else Low (also forced Low when no requirements block was detected).
- **No composite numeric score in v1** — thresholds would be false precision with zero calibration data. Revisit once `ats_gate` records correlate with real outcomes in the ledger.

**Recommendation logic — computed at two stages:**

1. **Pre-resume verdict** (emitted by `match confirm` into `match.yaml` + `gap_report.md`; uses only confirmed classifications + knockouts, no resume text — nothing has been rendered yet):
```
Do-Not-Apply-Yet  if U ≥ 0.50, or a knockout matches candidate_profile (e.g. no-sponsorship posting
                  + requires-sponsorship profile). If candidate_profile.yaml is absent, knockout
                  checks are skipped with a visible printed notice (never silently).
Proceed-Caution   if 0.25 ≤ U < 0.50
Proceed           otherwise
```
2. **Final verdict** (emitted by the gate into `gate_report.yaml`, after scoring `resume_ats.txt`):
```
Do-Not-Apply-Yet  if U ≥ 0.50 or an unwaived knockout remains
Revise            if 0.25 ≤ U < 0.50, or any risky_for_review item not yet human-acked
Apply             otherwise, given gate PASS + verified PDF
```

---

## 5. Resume Variant Generation Strategy

### 5.1 Canonical artifact — `resume.yaml` (the only file humans edit)

```yaml
schema: resume/v1
application: tesla-adas-validation-2026-07
positioning: adas-av-validation
role_title: "ADAS Validation Engineer"        # must be in positioning_titles.yaml
summary:
  - text: "Commercial-vehicle ADAS validation engineer with production experience across
      Smart Cruise Control (SCC / Adaptive Cruise Control) behavior logic, spanning
      Model-in-the-Loop (MIL), Hardware-in-the-Loop (HIL/HILS), dynamometer, and real-vehicle testing."
    claims: [hmc-scc-emergency-stop, hmc-validation-workflow]
    keywords: [scc, hil, mil]
skills:
  - label: "Validation & Test"
    items: ["Hardware-in-the-Loop (HIL/HILS)", "Model-in-the-Loop (MIL)", "log replay", "CANape",
            "XCP over CAN-FD", "MF4", "dSPACE"]
    keywords: [hil, mil, log-replay, canape, xcp, dspace]
experience:
  - source: hmc-adas                # backbone experience id; role/org/dates pulled from employers.yaml
    bullets:
      - text: "Reduced repeated real-bus road-test loops from about 10 trips to about 5 (each 4–5 hours)
          by replaying production logs through Target Object Selection (TOS/ODP) logic in a
          Bird's-Eye-View (BEV) simulator for bus-only-lane false-detection cases."
        claims: [hmc-bev-replay-metric]
        keywords: [target-selection, log-replay, bev, simulation]
      - text: "Participated in front-target brake-distribution design splitting auxiliary vs foundation
          braking based on ego speed, target speed gradient, and required deceleration."
        claims: [hmc-foc-brake-distribution]     # ownership: shared ⇒ "led/owned/designed" would hard-fail
        keywords: [longitudinal-control, ebs]
projects: []                        # same bullet shape, sourced from sw-/tc- claims
education: from_registry            # rendered from employers.yaml education block
extras: {licenses: [cert-class1-license, cert-trailer-license]}
```

### 5.2 Renderers (`portfolio/resume_render.py`)

- `out/resume_ats.txt` — plain text, CAPS headings, `- ` bullets, all non-ASCII transliterated (`— · →` → ASCII). **The scored artifact.**
- `out/resume_ats.html` — from `Format/templates/resume_ats.html.j2`: single `<main>`, semantic `h1/h2/ul`, **one column, no grid/flex column splits, no tables, no icons, no images**, ~40 lines inline CSS (`@page A4 12mm`, `break-inside: avoid`). Completely independent of `index.html.j2` — site redesigns can never reflow sent resumes.
- `out/resume_ats.md` — for humans/diffs.
- `out/resume_pretty.html` — optional, for referrals (`--style pretty|both`). **Data flow (one direction, no hand-edited overlay in the new pipeline):** `render --style pretty` deterministically derives an in-memory overlay from `resume.yaml` (section selection, ordering, bullet texts) and feeds it to the existing variant renderer. The referral version can therefore never say what the ATS version may not. `Format/scaffold/overlay.yaml` remains only for the legacy `--new-variant` compat path; new-pipeline applications never hand-edit overlays.
- Section order fixed: `Summary, Skills, Experience, Projects, Education` (empty sections omitted). Experience entries render one `Organization | Title | YYYY.MM – YYYY.MM|Present` line each, reverse-chronological, dates from `employers.yaml` only.
- Contact header: `email | phone | location | linkedin | github` — phone merged in from gitignored `Context/private/personal_private.yaml` at render time only.

### 5.3 PDF and DOCX

- **v1 PDF**: human opens `resume_ats.html`, browser Save-as-PDF → `out/resume_final.pdf`. Then **mandatory** `pdfcheck`: pypdf text extraction, `difflib.SequenceMatcher.ratio() ≥ 0.98` vs `resume_ats.txt` (whitespace-normalized). Below threshold → hard block (makes the "Microsoft Print to PDF" trap structurally impossible). Playwright/Chromium automation is a later phase — do not add the dependency in v1.
- **DOCX**: deferred. Trigger condition: an ATS-ledger entry recording a rejection attributable to PDF parsing. Implementation then: `python-docx` walker over `resume.yaml` — no template work needed because the YAML is the contract.

### 5.4 Generated reports (all deterministic, per application)

1. **`gate_report.yaml` + `gate_report.md`** — verdict PASS/FAIL/HIGH_RISK; must-have and nice-to-have coverage counts and %; `missing_terms: {must: [...], nice: [...]}` (explicit missing-critical-terms list, present on every run, not just FAIL); per-keyword placement table (Summary/Skills/Experience/Projects + count); terms included per section; `excluded_unsupported` list (intentionally omitted terms → gap report); `risky_for_review` list (every `partial` hedged phrasing with its bullet ref, plus every `confidence: low` claim cited); stuffing flags; formatting results; confidence; final recommendation; `pdf_verified`.
2. **`gap_report.md`** — each unsupported/adjacent must-have + its JD quote + nearest claims + a learn-before-apply suggestion slot (LLM fills suggestions; deterministic code fills the rest). Carries the **pre-resume recommendation** computed by `match` (§4.4) so the go/no-go decision happens before any resume drafting.
3. **`changes.md`** (changed-bullets report) — diff of `resume.yaml` bullets vs (a) the cited claims' canonical `statement`s and (b) the previous application with the same positioning, so the owner sees exactly what was rephrased and why.
4. **`audit.json`** (evidence map) — every rendered bullet → `{claims, ownership, strength_class_detected, evidence refs, checks_passed}`. Claim IDs never appear in the rendered resume itself.
5. **`checklist.md`** (reviewer checklist) — rendered per application before submission:
   - [ ] Every `risky_for_review` phrasing is one you can defend verbally in an interview
   - [ ] Role title matches what you'd say out loud about yourself
   - [ ] Metrics current (`as_of` staleness warnings resolved)
   - [ ] Gap report reviewed; Do-Not-Apply-Yet items consciously overridden or accepted
   - [ ] PDF text layer verified (`pdfcheck` PASS)
   - [ ] Contact info correct; portfolio links resolve (auto-checked, human confirms)
   - [ ] `jd.txt` unchanged since parse (auto-checked via sha)

### 5.5 Regenerate-on-failure loop (dev-mode explicit)

On gate FAIL the CLI: writes the failure payload (missing terms + their `ats_form` + cited claim ids + cheapest-fix suggestion per term) into `gate_feedback:` inside the application folder, keeps `gate_report.*`, deletes only the ATS render outputs, exits 2, and prints:
`Gate FAILED (2 supported must-haves missing). Run /resume-plan <slug> in Claude Code — it reads gate_feedback and revises resume.yaml. Then: python main.py render <slug>`.
**In local dev mode the loop is human-mediated by design** — there is no hidden auto-retry; the slash command consumes `gate_feedback` on re-entry. (API mode later adds auto-retry ≤3 with the same payload.) The loop can only add/move **supported** terms — the truthfulness back-check (lint error on any adjacent/unsupported term appearing in the text) makes it impossible to "fix" coverage by inventing.

---

## 6. Portfolio Variant Strategy

The public site stays broad and untouched (hard constraint). Application-specific emphasis is delivered as:

1. **`portfolio_plan.md` per application** (deliverable #3; deterministic render from confirmed `match.yaml` + the application's positioning, written by `match confirm` and refreshed by `gate` — implemented in Phase 4): recommended project order, which case-study detail pages to link from the resume, per-project one-line excerpts to reuse, and the public-safe boundary reminders from claim `disclosure` fields. Default emphasis map:
   - ADAS/AV validation → `hmc-adas` case studies, `tc-bev-simulator`, `tc-timeseries-ai`, then controls background
   - Embedded/controls → `add-k2-tcu`, `hmc-adas` (controls-facing bullets), `kaist-masters`
   - AI tooling / full-stack → `sw-deckflip-pipeline`, `sw-decisioncanvas-engine`, `sw-pathpilot-app`, `sw-voiceprint`
   - AI automation / systems → `sw-decisioncanvas-engine`, `sw-deckflip-pipeline`, `tc-xcp-bypass`, HMC toolchains
2. **The pretty resume variant** (existing overlay engine) carries the same ordering for referral audiences.
3. **Deferred (opt-in later, flagged as a public-site change):** `Context/focus_profiles.yaml` compiled into the currently-empty `site.js` enabling `https://jwhwang91.github.io/?focus=adas-validation` client-side reordering/highlighting. One deploy, zero forks, ATS-invisible. Not in v1 because it modifies public-site behavior.

---

## 7. Technical Interview Preparation Pack

**LLM step** `/interview-pack <slug>` → `prep/interview_pack.yaml`, deterministically validated, rendered to `prep/interview_pack.md` via template. Inputs: `jd.parsed.yaml`, `match.yaml`, `resume.yaml`, claim registry, positioning.

Schema (validated sections):
- `format_forecast` — likely rounds, with `basis` quoting JD lines.
- `likely_topics` — ranked; each cites the JD keyword that predicts it and marks `depth: deep|skim` (deep = you claim it; skim = adjacent).
- `resume_deep_dive` — one entry **per resume bullet**: likely questions + `answer_sketch` grounded in the cited claims.
- `danger_questions` — **REQUIRED: one entry per `partial` keyword in `match.yaml`** (validator fails otherwise — this is the anti-overclaim safety net). Each has `truthful_boundary` text, e.g. for brake distribution: *"I participated in the front-target brake-distribution design — the auxiliary/foundation split logic — but I did not own the module. What I independently owned was SCC emergency-stop behavior and the RoadRadius EKF fusion."*
- `project_walkthroughs` — 2–3 STAR case studies; `result` fields containing digits must match a registry metric or be an explicit `<placeholder>` (validator-enforced; no invented numbers).
- `system_design` — prompts with skeletons anchored to real artifacts (e.g. "design a regression-validation pipeline for an ADAS stack" anchored to the TOS/ODP BEV simulator).
- `behavioral` — STAR bank; LLM anchors to claim ids, **never invents events**; personal-narrative slots left as `<HUMAN FILLS>`.
- `questions_to_ask`, `gaps_to_prep` (honest lines for unsupported must-haves), `refreshers_plan` (hours + order).

**Per-positioning refresher menus ship as static data** inside `Format/prompts/interview_pack.md` so the LLM composes rather than invents. Three menus cover the five positioning tracks via an explicit map:
- **ADAS/AV validation menu** (tracks `adas-av-validation`, `vehicle-systems-validation`): EKF/Kalman derivations, vehicle dynamics (bicycle model, understeer), CAN/CAN-FD/UDS/XCP, HIL architecture, false-positive/false-negative triage, scenario-based testing, ISO 26262 vocabulary (exposure-level unless registry says more).
- **Embedded/controls menu** (track `embedded-controls`): state machines, clutch/actuator control, loop shaping, TDE (KAIST anchor), real-time constraints, HILS, MISRA-C awareness.
- **AI/full-stack menu** (tracks `ai-tooling-fullstack`, `systems-ai-automation`; the latter additionally pulls the validation-toolchain topics from the ADAS menu): LLM pipeline design (DeckFlip multi-pass anchor), schema-constrained generation, async DAG execution (DecisionCanvas Kahn-sort anchor), Supabase/realtime, frontend/backend boundaries, testing strategy (Vitest/Playwright/pytest anchors), product tradeoffs.

Validators: all claim ids exist; forbidden-phrasing scan over all text; every partial keyword has a danger question; digit check as above.

---

## 8. Coding Interview Preparation Pack

**Key decision: problems are selected, never generated.** A committed, human-reviewed bank — `Context/prep/coding_bank.yaml`, **40–60 problems** at bootstrap (LLM-drafted once, owner-approved) — is filtered deterministically; the LLM only infers format and writes tailoring notes.

```yaml
# Context/prep/coding_bank.yaml (excerpt)
patterns: [arrays-hashing, two-pointers, sliding-window, stack, binary-search, linked-list,
           trees-bfs-dfs, heap, intervals, graph-bfs-dfs, graph-topo, dp-1d, matrix, strings,
           design, bit-manipulation, state-machine, log-parsing]
problems:
  - id: cb-topo-01
    pattern: graph-topo
    title: "Course Schedule II"
    source: "LeetCode 210"
    difficulty: medium
    roles: [ai-tooling-fullstack, systems-ai-automation, adas-av-validation]
    talking_point: "Same Kahn's-algorithm topological sort shipped in DecisionCanvas's async
                    execution engine — say so if it comes up."
    template: Context/prep/templates/graph_topo.py
  - id: cb-sm-02
    pattern: state-machine
    title: "Design a debounced gear-shift state machine from an event stream"
    source: "custom (domain)"
    difficulty: medium
    roles: [embedded-controls, vehicle-systems-validation]
    talking_point: "Mirrors K2 TCU shift-state / driver-intent decision logic."
```

**Deterministic format inference** (`portfolio/prep.py` rules; LLM may override with stated reason):
- JD says "data structures & algorithms" / big-tech signal → `leetcode-standard` (difficulty mix 30/55/15 easy/med/hard)
- validation/test role + "Python scripting"/"log analysis" → `practical-python` (45/45/10; log-parsing, time-series windowing, state-machine problems weighted up)
- embedded C/C++/RTOS/MISRA → `embedded-c` (bit manipulation, pointers, state machines, concurrency-lite)
- startup full-stack → `takehome-plus-medium-lc`

**`prep/coding_pack.yaml`**: inferred format + basis; 20–40 selected problem ids (validator: all exist in bank, count in range, difficulty mix within the format's band); pattern priority list; Python implementation templates (from `Context/prep/templates/*.py` — pattern skeletons with complexity notes); complexity expectations per pattern; 3–5 mock interview questions; 2 debugging/code-review exercises; practical tasks relevant to the role (e.g. MF4-style log parsing for validation roles); and a **2/4/8-week plan** chosen by time-to-interview from `Context/prep/plans/` templates. Plans are **pattern-first for an experience-strong / LC-weaker candidate**: each session = 20-min pattern template review → 1 easy warm-up → 1–2 mediums. Progress tracking is a checklist inside `coding_pack.md` (no spaced-repetition CLI in v1).

---

## 9. Application Tracking and Feedback Loop

### 9.1 `application.yaml` (single tracking truth per application)

```yaml
schema: application/v1
id: tesla-adas-validation-2026-07
company: Tesla
role_title: "ADAS Validation Engineer"
req_url: "https://…"
positioning: adas-av-validation
channel: careers-page              # careers-page | linkedin | referral | recruiter
location: "Palo Alto, CA (on-site)"
visa_sponsorship: unknown          # unknown | required-by-me | posting-says-no | confirmed-yes
created: 2026-07-07
jd_sha256: "…"                     # stamped at parse; submit blocks if jd.txt changed
status: gated
status_history:                    # a legal trace through the state machine (§9.2)
  - {status: draft,   at: 2026-07-07}
  - {status: parsed,  at: 2026-07-07}
  - {status: matched, at: 2026-07-07}
  - {status: drafted, at: 2026-07-08}
  - {status: gated,   at: 2026-07-08, note: "gate PASS, High"}
gate: {verdict: PASS, confidence: High, recommendation: Apply,
       must_have_supported_present: "11/11", risk_acknowledged: false}
submission: {at: null, resume_artifact: out/resume_final.pdf, resume_sha256: null}
events: []                         # appended by `log` (freeform note + date; no typed vocabulary in v1)
outcome:
  result: null                     # rejected | ghosted | withdrawn | offer | hired
  stage_reached: null              # ats | recruiter | technical | onsite | offer
  ats_verdict: null                # pass | fail | unknown (keep today's tri-state inference)
  rejection_class: null            # keyword-gap | auto-knockout | volume | post-interview | unknown
  interview_questions_asked: []    # actual technical/coding questions — feeds future packs
  feedback: null
lessons:
  - id: L-001
    scope: ats                     # ats | interview | targeting | backbone-gap
    text: "JD used 'Autonomous Vehicle (AV) validation' — resume said only ADAS; recoverable."
    promote_to_ledger: true
```

### 9.2 Lifecycle state machine (enforced by `status`)

```
draft → parsed → matched → drafted → gated → approved → submitted
submitted → screen → interview → offer → hired
any-post-submitted → rejected | ghosted        any-pre-submitted → abandoned        any → withdrawn
gated → drafted (regenerate loop)              approved → gated (resume edited ⇒ re-gate forced)
```

Statuses `parsed/matched/drafted/gated` are auto-advanced by their commands (§2.3); humans set only `approved`, `submitted`, and post-submission statuses. **`status submitted` is the hard gate (G4)**: requires status `approved`, gate PASS (or HIGH_RISK + explicit `--acknowledge-risk`, recorded forever), `out/resume_final.pdf` present with passing text-layer check, unchanged `jd_sha256`. Mechanically impossible to send an ungated, text-less, or silently-edited resume.

### 9.3 Learning without corrupting truth

- `python main.py lessons compile` → aggregates `lessons:` from closed applications → **anonymization-linted** draft (`Applications/_ledger_draft.md`, gitignored; lint fails on company names, req URLs, JD verbatim) → human reviews → `/evolve-ledger` drafts the `ATS_LEDGER.md` edit → human commits.
- **The EVOLUTION.md rule becomes code**: `lessons compile` **rejects** `scope: ats` lessons from applications whose `stage_reached` is post-ATS, printing the rule ("post-interview rejections mean the resume passed — this is an interview lesson").
- `scope: backbone-gap` lessons append to `Context/variants/BACKLOG.md` — the learn-before-apply list (e.g. "ROS2 requested 3×, unsupported — build a small project before the next AV-sim application").
- Nothing ever writes to `Context/*.yaml`, the claim registry, or the taxonomy automatically.
- `result.md` is retired; a compat reader in `portfolio/tracking.py` still counts legacy folders in `track`/insights.

---

## 10. CLI / UX Design

Argparse subcommands in `portfolio/cli.py`; `main.py` stays the entry point. **Compat shims**: bare `python main.py` → `site`; `--new-variant X` → `new`; `--variant X` → `render X --style pretty`; `--all-variants`, `--list-variants`, `--insights` → mapped with a one-line deprecation pointer. CI and every playbook keep working unmodified.

| Command | Reads | Writes | Fails when |
|---|---|---|---|
| `site` | Context/, Format/, Style/ | `dist/` | backbone YAML invalid |
| `new <slug> [--company --role --url --positioning]` | `Format/scaffold/` | `Applications/<slug>/{application.yaml,jd.txt,notes.md}` | slug exists / not `[a-z0-9-]+` |
| `jd parse <slug>` | jd.txt, taxonomy | deterministic scan + assembled prompt (prints path for Claude Code) | jd.txt missing/empty |
| `jd confirm <slug>` | jd.parsed.yaml | stamps `confirmed` | validation errors |
| `match <slug>` | jd.parsed, registry, keyword_map, candidate_profile | resolved classifications + LLM queue prompt | unconfirmed parse |
| `match confirm <slug>` | match.yaml | appends `Context/private/keyword_map.yaml`; renders `gap_report.md` (pre-resume recommendation) + `portfolio_plan.md` | invalid claim refs |
| `validate <slug> [--stage jd\|match\|resume\|prep\|all]` | stage artifact + schema + registry | exit code + violation list | schema violation, unknown claim id, forbidden phrasing |
| `render <slug> [--style ats\|pretty\|both] [--keep-failed]` | resume.yaml, templates | `out/*` + auto-runs gate; on FAIL removes ATS renders, keeps reports, exits 2 | gate FAIL; HIGH_RISK needs later `--acknowledge-risk` at submit |
| `gate <slug> [--verify-only]` | rendered txt + match + parse | `gate_report.{yaml,md}`, `checklist.md`, `changes.md`, `audit.json` | FAIL → exit 2 |
| `pdfcheck <slug>` | out/*.pdf | verdict | text similarity < 0.98 → exit 2 |
| `pack interview <slug>` / `pack coding <slug>` | prep yaml + schemas + bank | validated + rendered md | validation errors |
| `status <slug> <status> [--note --acknowledge-risk]` | application.yaml | status + history | illegal transition; submit preconditions |
| `log <slug> --note "..." [--date]` | application.yaml | appends event | — |
| `track [--open --closed --csv]` | all application.yaml (+ legacy result.md) | stdout table / gitignored CSV | — |
| `lessons compile` | closed apps' lessons | `Applications/_ledger_draft.md` | anonymization lint failure |
| `lint-facts` | Context/facts/** | violation report | schema/reference errors |

**Stage-gating UX**: every command that lacks a prerequisite prints the exact next action (e.g. `gate` with no `match.yaml`: `Missing match.yaml — run: /jd-match tesla-adas-validation-2026-07 in Claude Code.`).

`WORKFLOW.md` at repo root becomes the one document that runs the whole loop (§2.3 table + troubleshooting).

---

## 11. LLM Integration Strategy

### 11.1 Now (v1 — local developer mode, not over-engineered)

- **Prompt contracts** live in `Format/prompts/`: `jd_parse.md`, `jd_match.md`, `resume_plan.md`, `interview_pack.md`, `coding_pack.md`, `rejection.md`, `evolve_ledger.md`, `extract_facts.md` (bootstrap). Each specifies: exact inputs (the CLI assembles them), the exact output file, and the output JSON-schema.
- **Repo-local slash commands** in `.claude/commands/` are thin wrappers: "Read `Format/prompts/<name>.md`; execute for slug `$ARGUMENTS`; write only the specified output file; then run `python main.py validate <slug> --stage <s>` and fix violations until exit 0." The validator loop happens **inside the Claude Code session** — that is the dev-mode equivalent of auto-retry.
- **Deterministic everything else**: segmentation, taxonomy scan, cache resolution, registry joins, scoring, gating, rendering, tracking, lints. If the LLM disappeared tomorrow, parsing/scoring/gating of an existing resume still works.

### 11.2 Later (explicitly deferred)

- API mode: `portfolio/llm.py` runner over the same prompt files (Claude API first), with programmatic retry ≤3 feeding validator errors back.
- Playwright headless PDF; DOCX renderer; Korean JD aliases + Korean resume output; composite ATS score calibrated against ledger outcomes; `?focus=` portfolio profiles; `refresh-metrics` auto re-measurement of repo-stat claims; spaced-repetition prep tracking.

### 11.3 What is deterministic vs LLM vs human (single reference table)

| Step | Deterministic Python | LLM | Human |
|---|---|---|---|
| Registry bootstrap | schema + quote validation | extract proposed facts | **G0 confirm** |
| JD parse | segment, scan, mine candidates, validate quotes | interpret + structure | **G1 confirm** |
| Support classification | cache + registry join | classify unresolved only | **G2 confirm** |
| Resume draft | render, score, gate, reports | draft/revise `resume.yaml` | edit the YAML directly |
| Gated package | status tracking | — | **G3 approve** (`status approved` after gate PASS) |
| PDF | text-layer verification | — | export via browser |
| Interview/coding packs | validate refs, select problems, render | compose pack content | review before interview |
| Submit | precondition enforcement | — | **G4 submit** |
| Feedback | lesson-scope rules, anonymization lint | rejection diagnosis, ledger draft | commit ledger edit |

---

## 12. Safety, Truthfulness, and Quality Gates

Each check runs in exactly **one runtime module** (no triple enforcement): **structural** checks run on `resume.yaml`, **textual** checks run on `resume_ats.txt`, and **template-contract** assertions run at test time. Module assignment:
- `portfolio/truthlint.py` (Phase 2, JD-independent): Q1–Q7, Q11–Q14
- resume validator, `validate --stage resume` (Phase 5, application-aware but JD-text-independent): Q18, Q19
- scorer/gate, `portfolio/{score,gate}.py` (Phase 5, JD-dependent): Q8, Q10, Q15–Q17, Q20
- test-time template contract: the structural half of Q9 (single-column / no-tables / heading whitelist asserted against `resume_ats.html.j2`); the textual half (ASCII, date format, ordering) runs in truthlint
- repo-wide sweep of `Context/*.yaml` site files against `employers.yaml` (the maintenance half of Q6) runs in `lint-facts`, warn-level in v1

| # | Detection (owner's list) | Home | Check | Severity |
|---|---|---|---|---|
| Q1 | Unsupported skill claims | structural | every bullet cites ≥1 `confirmed` claim; every skills/keyword chip resolves through taxonomy to ≥1 claim's terms | error |
| Q2 | Overclaiming verbs | structural | strength-class detection (§3.4) vs cited claims' ownership; `shared/support` claims reject ownership-class lexemes | error |
| Q3 | Invented metrics | textual (scoped to Experience/Projects bullets) | every digit-token matches a cited claim's `metrics[].numbers`, an `employers.yaml` date, or the numeric whitelist | error |
| Q4 | Metric staleness | structural | `as_of` + staleness window exceeded | warn → checklist |
| Q5 | Missing dates | structural | every experience entry resolves to an `employers.yaml` period with start and end/Present | error |
| Q6 | Inconsistent titles/dates/orgs | structural + repo lint | all renderings must match `employers.yaml` canon (also run against `Context/*.yaml` site files: warn v1, error later) | error |
| Q7 | Forbidden phrasing | textual | regex scan: global + per-claim + per-employer + gitignored `redlines.yaml` (skipped-with-notice if absent, e.g. CI) | error |
| Q8 | Keyword stuffing | textual | per-keyword count >4 warn / >6 error; Summary taxonomy-token ratio >35% error | warn/error |
| Q9 | ATS-hostile formatting | template contract + textual | heading whitelist; no tables/images/multi-column; ASCII normalization; date format `YYYY.MM – YYYY.MM\|Present`; reverse-chronological order | error |
| Q10 | Acronym expansion | textual | first occurrence of each must-have term must be its `ats_form` ("Hardware-in-the-Loop (HIL/HILS)") | error (owner lists it as hard requirement) |
| Q11 | Too-long bullets | structural | bullet >200 chars warn, >280 error | warn/error |
| Q12 | Vague claims | textual | `vague_claim_lexicon` scan | error |
| Q13 | Duplicated phrases | textual | any 6-word shingle appearing in ≥2 bullets | warn |
| Q14 | Too many projects / overlong resume | structural | >4 projects warn; estimated render length >2 pages warn (1-page target per positioning config) | warn |
| Q15 | Missing supported must-haves | textual | MustHaveCoverage < 100% | **gate FAIL → regenerate** |
| Q16 | Unclaimable terms present | textual | any `adjacent`/`unsupported` term's alias found in resume text | error (truthfulness back-check — regeneration cannot cheat) |
| Q17 | Hedge integrity | textual | every `partial` keyword co-occurs with an allowlisted hedge in the same sentence | error |
| Q18 | Portfolio/resume mismatch | structural | every case-study link resolves to an existing built `dist/` page or whitelisted live URL; claims cited in the resume must not contradict `disclosure` boundaries of linked pages | error |
| Q19 | Overbroad positioning | structural | `role_title` ∈ `positioning_titles.yaml` for the declared track | error |
| Q20 | High-risk application | gate | unsupported-must-have ratio ≥ 0.50 → HIGH_RISK, no submit without `--acknowledge-risk` | gate |

Human-facing output: `checklist.md` (§5.4) plus the gate report's `risky_for_review` section. A resume cannot reach `submitted` with any error-severity finding.

---

## 13. Testing Plan

Framework: `pytest`; everything runs against tmp dirs via the `Paths` dataclass (no monkeypatching module globals). Add `pytest`, `jsonschema`, `pypdf` to `requirements.txt` (split dev deps if desired).

**Fixtures** (`tests/fixtures/`):
- `jds/tesla-adas-validation.txt`, `jds/nvidia-av-simulation.txt`, `jds/applied-intuition-systems.txt`, `jds/fullstack-ai-product.txt`, `jds/embedded-controls.txt` — realistic synthetic JDs, each with an expected `jd.parsed.expected.yaml` keyword set and expected support classifications against the fixture registry.
- `registry_minimal/` — tiny synthetic claim registry + employers + policy for red/green tests.
- `resume_fixtures/` — hand-built `resume.yaml` + `resume_ats.txt` pairs: one fully valid, one per failure class.

**Test files and what they prove:**

| File | Coverage |
|---|---|
| `test_site_regression.py` | golden-structure test of `dist/index.html` + `standalone.html` build (assert key sections/links present, not byte equality); **inliner path survives the package split**; ATS templates never leak into `dist/` |
| `test_cli_compat.py` | bare invocation, `--variant`, `--new-variant`, `--list-variants`, `--insights` all still work post-split; plus a smoke pass over every **new** subcommand against a fixture application (each runs, exits with a documented code, prints its next-action hint when prerequisites are missing) |
| `test_schemas.py` | every artifact schema round-trips valid fixtures and rejects violation fixtures |
| `test_facts_registry.py` | ID uniqueness/format, confirmed-requires-evidence, source_quote verbatim check at bootstrap, proposed-not-citable |
| `test_truthlint.py` | red/green per the truthlint set (Q1–Q7, Q11–Q14): over-strong verb on shared claim, orphan number, forbidden phrase, stale-metric warn, missing dates, vague-claim lexicon, duplicated shingle, noun-led bullet defaults to contribution+warn |
| `test_taxonomy.py` | alias matching (word boundary, `C++`, `CAN-FD`), tier caps, ambiguous-alias flagging |
| `test_jd_parse.py` | segmentation on all 5 fixtures; quote-verbatim validator kills a doctored parse; scan-hit-may-not-be-dropped rule |
| `test_classify.py` | registry-join truth table (ownership × alias-tier × deployment → support); cache hit path; downgrade-on-registry-change |
| `test_score_gate.py` | must-have miss ⇒ FAIL; placement rules; stuffing clamp; acronym-expansion error; adjacent/unsupported-term presence error (Q16); hedge-integrity error (Q17); unsupported-ratio → HIGH_RISK; both recommendation stages; regenerate feedback payload written; **`audit.json` evidence map**: every rendered bullet resolves to its cited claims with correct ownership/strength attribution |
| `test_render.py` | resume.yaml → txt/html determinism; ASCII transliteration; heading whitelist; date rendering from employers.yaml; phone merged only from private file |
| `test_tracking.py` | full transition matrix (legal + illegal); submit hard-gate preconditions; lessons stage-rule rejection; anonymization lint; legacy `result.md` compat reader |
| `test_prep.py` | pack validators: partial-keyword ⇒ danger-question required; problem ids exist; difficulty distribution bands; digits-in-STAR-results rule |
| `test_privacy_guard.py` | guard script fails on tracked `Applications/`/`_source_references/` paths and on the phone-number string in staged content |

**CI** (`.github/workflows/`): keep `deploy.yml` (add `paths:` filter); add `validate.yml` running `pytest` + `lint-facts` + the privacy guard on every push/PR.

---

## 14. File-by-File Implementation Plan (for Opus 4.8)

Small, safe phases. Each phase = one or a few commits, tests green before moving on. **Never fabricate registry content — extract from existing files and mark `proposed` anything not literally present.**

### Phase 0 — Privacy & hygiene (no behavior change) 🔴 do first
- **Modify** `.gitignore`: add `/_source_references/`, `/dist/`, `/Context/private/`, `__pycache__/` (already there but pyc is tracked), `.idea/`, `Applications/_track.csv`, `Applications/_ledger_draft.md`.
- **Run** `git rm -r --cached _source_references/ dist/ __pycache__ .idea/` (files stay on disk). Verify `git ls-files Applications/` is empty.
- **Create** `Context/private/personal_private.yaml` (phone moved here); **modify** `Context/personal_info.yaml` (remove phone), `Format/templates/index.html.j2` (render contact without phone when absent — check all `personal.phone` consumers).
- **Create** `.githooks/pre-commit` + `scripts/privacy_guard.py` (fails on private paths tracked/staged or the phone string); document `git config core.hooksPath .githooks`.
- **Modify** `requirements.txt`: add `pypdf`, `jsonschema`, `pytest`.
- **Modify** `.github/workflows/deploy.yml`: `paths:` filter (`Context/**`, `Format/**`, `Style/**`, `main.py`, `portfolio/**`, excluding private paths).
- **Report to owner (do not execute)**: recommendation to purge `_source_references/` and the phone number from git **history** via `git filter-repo` — separate owner sign-off required (public-repo history rewrite).
- **Acceptance**: site builds byte-identically (except phone); `git ls-files` shows no private paths; deploy still works.

### Phase 1 — Package split + test safety net
- **Create** `portfolio/{__init__,paths,content,site,inline,variants,tracking,cli}.py` — mechanical move of main.py functions along the seams in §1.4; `Paths` dataclass replaces module globals; `main.py` becomes a shim delegating to `portfolio.cli:main` with all legacy flags.
- **Create** `Format/scaffold/{overlay.yaml,notes.md,jd.txt}` (moved out of Python strings; `RESULT_FIELDS` vocab generated from one source).
- **Fix silent failures**: unknown ids in `include:`/`overrides:` now raise with nearest-match suggestion; missing files raise with file+key context.
- **Create** `tests/test_site_regression.py`, `tests/test_cli_compat.py`.
- **Acceptance**: `python main.py` output structurally identical; all legacy flags work; tests green; typo'd overlay id fails loudly.

### Phase 2 — Claim registry + truth linting
- **Create** `Context/facts/{employers,positioning_titles,phrasing_policy}.yaml` (content per §3.3–3.5); `Format/schemas/{claim,employers,phrasing_policy}.schema.json`; `portfolio/facts.py` (load/validate/alias-index); `portfolio/truthlint.py` (JD-independent checks Q1–Q7, Q11–Q14 per the §12 module map); `lint-facts` CLI (includes the warn-level `Context/*.yaml` consistency sweep).
- **Create** `Format/prompts/extract_facts.md` + `.claude/commands/extract-facts.md`; run the bootstrap extraction (LLM proposes ~30 claims from existing Context files, all `status: proposed` with `source_quote`).
- **Owner Gate G0**: confirm/correct claims (expect placeholders for LFA scope, metric `as_of` dates, ADD ownership).
- **Create** `tests/{test_facts_registry,test_truthlint,test_schemas}.py` + `tests/fixtures/registry_minimal/`.
- **Acceptance**: `lint-facts` green on the confirmed registry; date/title consistency warnings against existing site YAML are reported (warn level); a doctored fact (bad quote, missing evidence) fails.

### Phase 3 — Taxonomy + JD ingestion
- **Create** `Context/taxonomy/terms.yaml` (~60 seed terms derived from the 5 fixture JDs + registry terms); `portfolio/{taxonomy,jd}.py`; `Format/schemas/jd_parsed.schema.json`; `Format/prompts/jd_parse.md`; `.claude/commands/jd-parse.md`; CLI `new`, `jd parse`, `jd confirm`; scaffold `application.yaml` (minimal fields now).
- **Create** `tests/fixtures/jds/*` (5 JDs + expected parses), `tests/{test_taxonomy,test_jd_parse}.py`.
- **Acceptance**: `jd parse` on each fixture produces the expected deterministic scan; a doctored `jd.parsed.yaml` with a non-verbatim quote fails validation; `jd confirm` stamps.

### Phase 4 — Matching & classification
- **Create** `portfolio/classify.py`; `Format/schemas/{match,candidate_profile}.schema.json`; `Format/prompts/jd_match.md`; `.claude/commands/jd-match.md`; gitignored `Context/private/keyword_map.yaml` (created on first confirm); `gap_report.md` renderer (with pre-resume recommendation, §4.4) + `portfolio_plan.md` renderer (§6, written by `match confirm`); `candidate_profile.yaml` scaffold hint (knockout checks skip with a visible notice when the file is absent); CLI `match`, `match confirm`, `validate --stage match`.
- **Create** `tests/test_classify.py` (join truth table, cache behavior, downgrade rules, pre-resume recommendation logic, absent-candidate_profile notice, portfolio_plan ordering per positioning).
- **Acceptance**: fixture JDs classify correctly against the fixture registry (e.g. Tesla fixture: `scc/hil/log-replay` direct; `iso-26262` unsupported → gap report; `lidar` adjacent → excluded); `gap_report.md` carries the pre-resume verdict and `portfolio_plan.md` orders projects per the §6 emphasis map; second run of the same JD = zero unresolved terms.

### Phase 5 — Resume generation + ATS gate
- **Create** `Format/templates/{resume_ats.html.j2,resume_ats.txt.j2,resume_ats.md.j2}`; `Format/schemas/{resume,gate_report}.schema.json`; `portfolio/{resume_render,score,gate}.py` (JD-dependent checks Q8, Q10, Q15–Q17, Q20; resume validator adds Q18–Q19 per the §12 module map); `Format/prompts/resume_plan.md`; `.claude/commands/resume-plan.md`; CLI `render`, `gate [--verify-only]`, `pdfcheck`, `validate --stage resume`; pretty-style render derived from `resume.yaml` (§5.2).
- **Reports**: `gate_report.{yaml,md}` (incl. `missing_terms`), `checklist.md`, `changes.md`, `audit.json`, `gate_feedback` write-back on FAIL.
- **Create** `tests/{test_render,test_score_gate}.py` + resume fixtures.
- **Create** `tests/fixtures/sample_output/` — committed, anonymized end-to-end sample outputs for the Tesla ADAS Validation fixture: `jd.parsed.yaml`, `match.yaml`, `gap_report.md`, `portfolio_plan.md`, `resume.yaml`, `resume_ats.txt/html`, `gate_report.md`, `checklist.md`, `changes.md` (doubles as living documentation; §15 rule 7).
- **Acceptance**: end-to-end on the Tesla fixture with a canned `resume.yaml`: gate PASS artifacts produced; removing a supported must-have flips to FAIL with correct `gate_feedback`; inserting an unsupported term ("ROS2") is an error regardless of coverage; `pdfcheck` blocks a text-less PDF; acronym first-use expansion enforced; sample outputs committed.

### Phase 6 — Application tracker
- **Modify/Create**: `Format/schemas/application.schema.json`; `portfolio/tracking.py` (state machine, submit hard gate, events, legacy `result.md` compat reader); CLI `status`, `log`, `track`, `lessons compile` + anonymization lint; `Context/variants/BACKLOG.md`; `Format/prompts/{rejection,evolve_ledger}.md` + slash commands.
- **Create** `tests/test_tracking.py`.
- **Acceptance**: illegal transitions rejected; `submitted` blocked without gate PASS + verified PDF + unchanged jd sha; `lessons compile` rejects post-interview `scope: ats` lessons and fails on non-anonymized text; `track` includes legacy folders.

### Phase 7 — Technical interview pack
- **Create** `Format/schemas/interview_pack.schema.json`; `Format/templates/interview_pack.md.j2`; `Format/prompts/interview_pack.md` (with the three positioning refresher menus as static data); `.claude/commands/interview-pack.md`; `portfolio/prep.py` (validators); CLI `pack interview`.
- **Acceptance**: pack for the Tesla fixture validates; deleting a danger-question for a partial keyword fails validation; a digit in a STAR result not backed by a metric fails.

### Phase 8 — Coding interview pack
- **Create** `Context/prep/coding_bank.yaml` (40–60 problems — LLM-drafted, owner-approved before commit), `Context/prep/templates/*.py` (~10 pattern skeletons), `Context/prep/plans/{2w,4w,8w}.md`; `Format/schemas/coding_pack.schema.json`; `Format/templates/coding_pack.md.j2`; `Format/prompts/coding_pack.md`; `.claude/commands/coding-pack.md`; CLI `pack coding`; format-inference rules in `portfolio/prep.py`.
- **Acceptance**: embedded-controls fixture infers `embedded-c` format with state-machine problems weighted; validator rejects out-of-bank ids and out-of-band difficulty mixes.

### Phase 9 — Docs + workflow polish
- **Create** `WORKFLOW.md` (the §2.3 loop, troubleshooting, dev-mode regenerate ritual, links to the Phase 5 sample outputs); **modify** `README.md` (new commands), `PIPELINE.md` (point stages at the new pipeline), `Context/variants/PLAYBOOK.md` (mark superseded steps, keep strategy content); extend `tests/fixtures/sample_output/` with the Phase 7/8 prep-pack samples.
- **Acceptance**: a newcomer can run the full loop from WORKFLOW.md alone.

### Phase 10 — CI validation
- **Create** `.github/workflows/validate.yml`: pytest + `lint-facts` + privacy guard on push/PR.
- **Acceptance**: CI green; a PR adding a tracked file under `Applications/` fails CI.

---

## 15. Final Opus Execution Prompt

Copy-paste the following to Claude Opus 4.8 in Claude Code at the repo root:

```
You are executing MASTER_PLAN.md at the root of this repository (jwhwang91.github.io) — read it fully
before touching anything. It is the authoritative architecture for evolving this portfolio generator
into a JD-specific resume / ATS-gate / interview-prep / application-tracking pipeline.

Ground rules:
1. Execute the phases in §14 strictly in order (Phase 0 → 10). One phase at a time. Make small,
   reviewable commits (one logical change each); never combine phases in a commit.
2. Preserve existing site behavior exactly: `python main.py` must keep producing the same public site
   (dist/index.html, standalone.html, detail pages), and every legacy CLI flag (--variant,
   --new-variant, --list-variants, --all-variants, --insights) must keep working. Phase 1's regression
   and compat tests exist to prove this — write them before refactoring, then keep them green.
3. Run the test suite after every phase; do not proceed with red tests.
4. NEVER fabricate resume content. When bootstrapping Context/facts/, extract only what is literally
   present in Context/*.yaml, Context/Experiences/*/context.yaml, and the variant lenses. Anything
   the owner's goals mention that the files do not support (e.g. LFA scope, metric dates, ADD
   ownership level) must be created as status: proposed with <placeholder> fields — then STOP and
   report to the owner for Gate G0 confirmation before any resume-generation phase uses the registry.
5. Phase 0 (privacy) comes before everything: untrack _source_references/, dist/, __pycache__, .idea/;
   move the phone number to gitignored Context/private/personal_private.yaml; add the privacy guard.
   Do NOT rewrite git history yourself — print the git filter-repo recommendation and wait for the
   owner's explicit sign-off.
6. All LLM-facing behavior is implemented as prompt files under Format/prompts/ plus thin
   .claude/commands/ wrappers plus deterministic validators — do not implement API calls in v1.
7. Phase 5 includes producing sample outputs end-to-end for the Tesla ADAS Validation fixture
   (jd.parsed.yaml, match.yaml, gap_report.md, portfolio_plan.md, resume.yaml, resume_ats.txt/html,
   gate_report.md, checklist.md, changes.md) using canned fixture data, committed under
   tests/fixtures/sample_output/; Phases 7/8 extend it with the prep packs.
8. Document as you go: WORKFLOW.md is a deliverable, not an afterthought; update README.md and
   PIPELINE.md in Phase 9.
9. If at any point the source-of-truth data is insufficient to proceed truthfully, or a plan detail
   conflicts with what you find in the repo, stop and report the conflict with your recommendation —
   do not improvise resume claims or silently deviate from MASTER_PLAN.md.
10. Acceptance criteria at the end of each §14 phase are binding. State explicitly in each phase's
    final commit message which criteria you verified and how.
```

---

## Appendix A — Why these choices (for the record)

- **`resume.yaml` over `resume.md`**: per-bullet claim+keyword citations make truth-checking and coverage attribution structural rather than string-greppy; a bespoke markdown parser would lose the references. The plain-text render is still what gets scored, so "score what the parser sees" is preserved.
- **Computed support classification over stored tiers**: support is a relation between a JD term and your claims, not a property of a fact. Storing it would require workarounds (tier overrides) the moment one fact supports different terms differently.
- **No composite ATS score in v1**: weights like 0.70/0.15/0.15 and thresholds like 55/75 are false precision without outcome data. Gate on the three things that are true by construction: format cleanliness, 100% supported-must-have coverage, and the unsupported ratio. Calibrate a score later from the ledger.
- **Keyword-support cache gitignored**: a committed map enumerating `iso-26262: unsupported` is a public list of your gaps in the exact repo a recruiter will open.
- **Problems selected from a bank, not generated**: hallucinated problem lists are the fastest way to waste prep time; a curated bank with per-problem talking points ties prep back to your real projects (DecisionCanvas → topological sort; K2 TCU → state machines).
- **Submit hard-gate as the keystone UX**: it converts every safety property in this plan from advice into a precondition — an ungated, text-less, or silently-edited resume becomes mechanically unsendable.
