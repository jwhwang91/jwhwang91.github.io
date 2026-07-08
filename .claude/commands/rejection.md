---
description: Diagnose an outcome and fill outcome/lessons in application.yaml
---

Diagnose the outcome for application `$ARGUMENTS`.

Steps:
1. Read `Format/prompts/rejection.md` (the contract), `Applications/$ARGUMENTS/application.yaml`,
   `jd.parsed.yaml`, `match.yaml`, `gap_report.md`, and `Context/candidate_profile.yaml`.
   Ask the owner for the timing, channel, and any recruiter feedback if not recorded.
2. Fill `outcome:` and `lessons:` in `application.yaml` per the contract — separate
   auto-knockout from keyword-gap, and classify honestly (a rejection AFTER reaching a
   human is an `interview` lesson, not `scope: ats`).
3. STOP. The owner runs `python main.py lessons compile` and `/evolve-ledger` when ready.
