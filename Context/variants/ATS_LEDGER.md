# ATS Optimization Ledger

The **evolving memory** of the pipeline — what actually moves resumes past company ATS
filters, distilled from accumulated outcomes. Every new per-JD overlay should start by reading
this file (see `PLAYBOOK.md` Step 2). Updated by the "evolve the ledger" loop in `EVOLUTION.md`
after results come in.

**This file is committable and PUBLIC — anonymize everything. No company names, no req IDs,
no JD verbatim.** Record patterns ("fast auto-rejects cluster on JDs needing X"), not
employers. Private, named detail stays in each gitignored `Applications/<name>/`.

Signal source: `python main.py --insights` reads every `Applications/<name>/result.md` and
scores **ATS-pass = reached a human** (interview/recruiter) vs **ATS-fail = knocked out before
a human read it**. ATS-pass is *inferred*, never reported by the company.

---

## What passes (confirmed tactics — keep doing)
- **Text-layer PDF.** Export via the browser's **Save as PDF**, never "Microsoft Print to PDF"
  (which outlines glyphs → 0 extractable text → ATS reads a blank page). Verify with
  Ctrl+A/Ctrl+C or `--insights` (it warns on ~0-text PDFs). See `PIPELINE.md` → "Exporting".
- **Term + acronym mirroring.** Render the JD's exact wording for every truly-supported skill,
  spelled-out *and* acronym — e.g. "Hardware-in-the-Loop (HIL)". See `variant-ats-priority`.
- **Front-loaded must-haves** in the keyword strip, summary (`main_focus`), and per-experience
  keyword lines; reused naturally in bullets.
- **Delimited keyword chips.** The template emits an (invisible) comma between chips so they
  extract as "Python, C++" not "PythonC++".

## Recurring ATS-stage gaps (anonymized, with seen-count)
<!-- Missing must-haves that recur across fast-reject JDs. Honest recovery only — surface a
     skill the backbone TRULY supports but didn't show; NEVER invent one. Format:
       - <keyword> (seen Nx) — recoverable? yes/no — note -->
- _(none recorded yet — populate from `--insights` ATS-fail apps)_

## Auto-knockout signals (NOT a keyword problem)
A fast reject is not always an ATS keyword miss — it can be an automated eligibility filter.
Don't "fix keywords" when the real wall is one of these:
- **Visa sponsorship** on high-volume reqs (a sponsorship-needing strong-adjacent fit loses the
  early screen to exact-fit/no-sponsorship). Seen 1x. Lever: referral, exact-match reqs,
  sponsor-friendly employers. See `sponsorship-constraint` / `REJECTION_PIPELINE.md`.
- **Location / relocation** auto-filters.

## Open hypotheses / to test next
- _(add things to try and check against the next batch of outcomes)_
