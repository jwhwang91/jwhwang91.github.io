---
description: Parse a job description into a schema-valid jd.parsed.yaml (Gate G1)
---

Parse the job description for application `$ARGUMENTS`.

Steps:
1. Read `Format/prompts/jd_parse.md` (the contract), `Applications/$ARGUMENTS/jd.txt`
   (the raw JD), and `Applications/$ARGUMENTS/jd.scan.yaml` (the deterministic scan).
   If `jd.scan.yaml` is missing, run `python main.py jd parse $ARGUMENTS` first.
2. Write `Applications/$ARGUMENTS/jd.parsed.yaml` per the contract — every `quote`
   a verbatim substring of `jd.txt`, every `term` a real `Context/taxonomy/terms.yaml`
   id (or a `new_term` proposal), and no requirements-block scan hit silently dropped.
3. Run `python main.py jd confirm $ARGUMENTS` and fix any validation error until it
   stamps `confirmed: true`. Then STOP for the owner's Gate G1 skim.
