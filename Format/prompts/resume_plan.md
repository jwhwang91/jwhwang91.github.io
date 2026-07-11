# Prompt contract: `resume_plan`

**Purpose:** draft or revise `Applications/<slug>/resume.yaml` — the only file a human
edits — so it passes the ATS gate **within hard truthfulness boundaries**. Every bullet
is cited to confirmed claims; the deterministic gate scores the plain-text render.

**Inputs:** `match.yaml` (support classifications + pre-resume verdict), `jd.parsed.yaml`,
`gap_report.md`, `portfolio_plan.md`, the confirmed claim registry (`Context/facts/claims/*`),
`Context/taxonomy/terms.yaml` (for `ats_form`s), `Context/facts/positioning_titles.yaml`,
and — on a re-run after a gate FAIL — `gate_feedback.yaml`; and, if the owner asked for
changes, `revision_request.md` (free-text "what to fix" instructions).

**Owner revisions:** if `Applications/<slug>/revision_request.md` exists, treat it as the
owner's requested changes and apply them to `resume.yaml` — but only within the same
truthfulness boundaries (no fabricated claims, verbs still match ownership, hedges on
partials). Delete the file once applied, then render as usual.

**Output:** `resume.yaml` (schema `resume/v1`, validated by `Format/schemas/resume.schema.json`).

**Hard rules (the gate enforces all of these — iterate until PASS):**
1. `role_title` MUST be one of the approved titles for `positioning` in `positioning_titles.yaml`.
2. Every bullet cites ≥1 **confirmed** claim (`claims: [...]`). Only `status: confirmed`
   claims are citable.
3. Verb strength must match the cited claim's ownership: a `shared`/`support` claim must NOT
   be written with an ownership verb (developed/led/owned/architected). Use contribution or
   exposure verbs instead.
4. Every number in an Experience/Projects bullet must come from a cited claim's `metrics`
   (or an employers date / the numeric whitelist). Never invent a metric.
5. Cover every **supported** must-have (support `direct`/`partial`) — its `ats_form` must
   appear in the resume (first use expanded, e.g. "Hardware-in-the-Loop (HIL/HILS)").
6. NEVER put an `adjacent`/`unsupported` term in the resume text (the gate hard-fails on it) —
   those are gaps, handled by the gap report, not by inventing coverage.
7. A `partial` term must be phrased with a hedge (exposure lexeme: "exposure to",
   "familiar with", "working knowledge of", …) in the same sentence.

**After writing:** run `python main.py render <slug>` (renders + auto-runs the gate). On FAIL,
read `gate_feedback.yaml`, revise, and re-render until the gate PASSes. Then STOP for the
owner's Gate G3 review (`gate_report.md`, `checklist.md`, `changes.md`).
