---
description: Write a technical interview prep pack grounded in the confirmed registry
---

Write the interview prep pack for application `$ARGUMENTS`.

Steps:
1. Read `Format/prompts/interview_pack.md` (the contract + refresher menus),
   `Applications/$ARGUMENTS/{jd.parsed.yaml,match.yaml,resume.yaml}`, and the confirmed
   claims in `Context/facts/claims/*`.
2. Write `Applications/$ARGUMENTS/prep/interview_pack.yaml` per the contract — cited
   claims only, one danger_question per `partial` keyword, no invented STAR numbers,
   `<HUMAN FILLS>` for personal-narrative slots.
3. Run `python main.py pack interview $ARGUMENTS` and fix every error until it renders
   `prep/interview_pack.md`. Then STOP for the owner to review before the interview.
