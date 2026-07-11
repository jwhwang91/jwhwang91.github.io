---
description: Draft or revise resume.yaml so it passes the ATS gate (truthfully)
---

Draft or revise the resume for application `$ARGUMENTS`.

Steps:
1. Read `Format/prompts/resume_plan.md` (the contract), `Applications/$ARGUMENTS/match.yaml`,
   `jd.parsed.yaml`, `gap_report.md`, `portfolio_plan.md`, and — if present —
   `gate_feedback.yaml` (the payload from the last gate FAIL) and `revision_request.md`
   (the owner's free-text "what to fix" instructions). Read the confirmed claims in
   `Context/facts/claims/*` and the `ats_form`s in `Context/taxonomy/terms.yaml`.
   If `revision_request.md` exists, apply those changes (within the same truthfulness
   boundaries), then delete the file.
2. Write `Applications/$ARGUMENTS/resume.yaml` per the contract: cited bullets only, verbs
   matching each claim's ownership, no invented numbers, every supported must-have covered
   with its expanded `ats_form`, no adjacent/unsupported term in the text, hedges on partials.
3. Run `python main.py render $ARGUMENTS` (renders + auto-runs the gate). If it FAILs (exit 2),
   read `gate_feedback.yaml`, revise `resume.yaml`, and re-render until the gate PASSes. The
   loop can only add/move SUPPORTED terms — the truthfulness back-check makes inventing coverage
   impossible. Then STOP for the owner's Gate G3 review.
   **If the shell is unavailable** (e.g. a headless run where `render` is permission-denied),
   do NOT retry it — just write `resume.yaml` and STOP. An orchestrator renders it and, on a
   gate FAIL, re-invokes you with `gate_feedback.yaml` to revise.
