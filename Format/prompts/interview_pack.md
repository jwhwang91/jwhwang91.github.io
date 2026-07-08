# Prompt contract: `interview_pack`

**Purpose:** write `Applications/<slug>/prep/interview_pack.yaml` — a technical
interview prep pack grounded in the confirmed claim registry and this JD.

**Inputs:** `jd.parsed.yaml`, `match.yaml`, `resume.yaml`, the confirmed claim registry
(`Context/facts/claims/*`), `positioning`. **Compose from the refresher menu for the
positioning track below — do not invent facts.**

**Output:** `prep/interview_pack.yaml`, schema `interview_pack/v1` (validated by
`Format/schemas/interview_pack.schema.json`). Sections: `format_forecast`,
`likely_topics`, `resume_deep_dive`, `danger_questions`, `project_walkthroughs`,
`system_design`, `behavioral`, `questions_to_ask`, `gaps_to_prep`, `refreshers_plan`.

**Hard rules (validated by `python main.py pack interview <slug>` — fix until it passes):**
1. Every cited `claims:`/`anchor:` id must be a **confirmed** claim.
2. **One `danger_questions` entry per `partial` keyword in `match.yaml`** — each with a
   `truthful_boundary` stating exactly what you did and did NOT own. This is the
   anti-overclaim safety net; the validator fails if any partial keyword is uncovered.
3. Any digit in a `project_walkthroughs[].result` must match a cited claim's
   `metrics[].numbers` (or the numeric whitelist), else write `<placeholder>`. Never
   invent a number.
4. `behavioral` STAR entries anchor to claim ids and never invent events; leave personal
   narrative slots as `<HUMAN FILLS>`.
5. No forbidden phrasing (the registry's per-claim + global forbidden phrases are scanned).

## Refresher menus (static — compose, don't invent)

**ADAS/AV validation** (tracks `adas-av-validation`, `vehicle-systems-validation`):
EKF/Kalman derivations; vehicle dynamics (bicycle model, understeer); CAN/CAN-FD/UDS/XCP;
HIL/MIL architecture; false-positive vs false-negative triage; scenario-based / log-replay
testing; ISO 26262 vocabulary (exposure-level unless a claim says more).

**Embedded/controls** (track `embedded-controls`):
state machines; clutch/actuator control; loop shaping; Time Delay Estimation (KAIST anchor);
real-time constraints; HILS; MISRA-C awareness; plant modeling / V-cycle.

**AI / full-stack** (tracks `ai-tooling-fullstack`, `systems-ai-automation` — the latter also
pulls the ADAS validation-toolchain topics): LLM pipeline design (DeckFlip multi-pass anchor);
schema-constrained generation; async DAG execution (DecisionCanvas Kahn topological-sort anchor);
Supabase/realtime; frontend/backend boundaries; testing strategy (Vitest/Playwright/pytest
anchors); product tradeoffs.

**After writing:** run `python main.py pack interview <slug>` and fix every error until it
renders `prep/interview_pack.md`. Then STOP for the owner to review before the interview.
