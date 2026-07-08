---
description: Classify unresolved JD keywords against the confirmed registry (Gate G2)
---

Classify the unresolved keywords for application `$ARGUMENTS`.

Steps:
1. Read `Format/prompts/jd_match.md` (the contract) and `Applications/$ARGUMENTS/match.yaml`.
   The deterministic engine already classified everything it could; only the `queue`
   (new_terms / needs_review) needs you. If there is no `match.yaml`, run
   `python main.py match $ARGUMENTS` first.
2. For each queued term, move it into `classifications` per the contract — `direct` only
   with a confirmed claim of qualifying ownership, `partial` only with a hedge, otherwise
   `adjacent`/`unsupported`. Never invent support.
3. Run `python main.py match confirm $ARGUMENTS` and fix any error until it stamps
   `confirmed: true` and renders `gap_report.md` + `portfolio_plan.md`. Then STOP for the
   owner's Gate G2 review + the go/no-go on the pre-resume verdict.
