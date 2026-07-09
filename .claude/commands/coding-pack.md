---
description: Select a coding-round prep pack from the committed problem bank
---

Write the coding prep pack for application `$ARGUMENTS`.

Steps:
1. Read `Format/prompts/coding_pack.md` (the contract), `Applications/$ARGUMENTS/jd.parsed.yaml`,
   `Context/prep/coding_bank.yaml`, and `Context/prep/plans/*`. Ask the owner for
   time-to-interview to choose the plan (2w/4w/8w).
2. Infer the format (embedded-c / practical-python / takehome-plus-medium-lc /
   leetcode-standard) per the contract; override only with a stated `format_override_reason`.
3. Write `Applications/$ARGUMENTS/prep/coding_pack.yaml` — SELECT 20-40 problem ids from the
   bank (never invent one), weighted toward the role's patterns and inside the format's
   difficulty band.
4. Run `python main.py pack coding $ARGUMENTS` and fix every error until it renders
   `prep/coding_pack.md`. Then STOP for the owner to review.
