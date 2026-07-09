# Prompt contract: `coding_pack`

**Purpose:** write `Applications/<slug>/prep/coding_pack.yaml` — a coding-round prep pack.
**Problems are SELECTED from the committed bank, never invented.**

**Inputs:** `jd.parsed.yaml`, `Context/prep/coding_bank.yaml`, `Context/prep/plans/*`,
time-to-interview (ask the owner). The bank's `talking_point`s reference real projects.

**Deterministic format inference** (`portfolio.prep.infer_format`, LLM may override with
`format_override_reason`):
- embedded / C-C++ / MISRA / RTOS signal -> `embedded-c`
- validation/test role + Python scripting / log analysis -> `practical-python`
- startup full-stack -> `takehome-plus-medium-lc`
- otherwise (big-tech DSA) -> `leetcode-standard`

**Output:** `prep/coding_pack.yaml`, schema `coding_pack/v1`. Fields: `format`, `basis`,
`problem_ids` (20-40, chosen from the bank, weighted toward the role's patterns and the
format's difficulty band), `pattern_priority`, `complexity_expectations`, `mock_questions`,
`debug_exercises`, `practical_tasks`, `plan` (2w/4w/8w by time-to-interview).

**Hard rules (validated by `python main.py pack coding <slug>` — fix until it passes):**
1. Every `problem_ids` entry must exist in `coding_bank.yaml`.
2. 20-40 problems.
3. The selected problems' difficulty mix must sit within the format's band
   (leetcode-standard 30/55/15, practical-python 45/45/10, embedded-c 35/50/15,
   takehome-plus-medium-lc 20/65/15; +/- 15pp per bucket).
4. Weight selection toward the role's patterns: `state-machine`/`bit-manipulation` for
   embedded, `log-parsing`/`state-machine` for validation, `graph-topo`/`design`/`dp-1d`
   for AI-fullstack. Prefer problems whose `roles` include this positioning.

**After writing:** run `python main.py pack coding <slug>` and fix every error until it
renders `prep/coding_pack.md`. Then STOP for the owner to review.
