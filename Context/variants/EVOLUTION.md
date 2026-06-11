# Evolution loop — make the pipeline learn from outcomes

The per-JD loop ends at "sent." This is the layer that makes each result improve the *next*
resume, with one job: **keep finding the best way to pass company ATS filters.**

```
apply ──► result.md (outcome + stage)
            │
            ├─ per-app   REJECTION_PIPELINE.md  → diagnose ONE application  → notes.md + result.md
            ├─ cross-app --insights + evolve     → mine patterns ACROSS apps → ATS_LEDGER.md
            └─ feed-fwd  next overlay reads ATS_LEDGER.md first              → compounding gains
```

## The one rule that prevents wasted effort

You never get told "you passed ATS." Infer it from **how far the application got** — and let
the stage decide what (if anything) to change. **Only ATS-stage rejections should drive resume
ATS changes.** A later-stage rejection means the resume already did its job; churning its
keywords would optimize the wrong thing.

| Stage of rejection | What it most likely means | What to optimize |
|---|---|---|
| **Fast auto / early screen, no human** | ATS keyword/parse fail **OR** an auto-knockout | 1) verify PDF text-layer → 2) keyword coverage vs JD must-haves → 3) check sponsorship/location knockout. Fix the real one. |
| **Recruiter screen** | Passed ATS; fit / sponsorship / leveling | Leave the ATS layer. Pursue referral / exact-match reqs. |
| **After interview** | Passed ATS comfortably; resume did its job | **Do NOT churn the resume's ATS layer.** Focus on interview prep / fit. |
| **Offer** | It worked | Capture what worked into `ATS_LEDGER.md`. |

The trap: reading a fast reject as "my keywords were weak" when it was really a sponsorship or
location auto-filter. `--insights` and `REJECTION_PIPELINE.md` exist to tell these apart.

## Recording an outcome (do this first)

Update `Applications/<name>/result.md` — the controlled fields `--insights` keys on:
`Status`, `ATS` (`pass`=reached a human / `fail`=auto-reject / `unknown`), `Stage reached`,
`Why` (keyword gap? auto-knockout?), `Next move`. Then run the per-app `REJECTION_PIPELINE.md`
for the deep diagnosis.

## Evolve the ledger (cross-application — paste to Claude)

Run this after a few new outcomes land:

> **Evolve the ATS ledger.**
> 1. Run `python main.py --insights` and read the scoreboard (ATS-pass rate, the ATS-stage
>    reject list, any PDF text-layer warnings).
> 2. For each ATS-**fail** application, read its `Applications/<name>/jd.txt` + `overlay.yaml`
>    and identify must-haves the JD wanted that my resume did NOT mirror — separating
>    *recoverable* gaps (backbone truly supports it, I just didn't surface it) from *real*
>    gaps (I don't have it) and *auto-knockouts* (sponsorship/location — not a keyword issue).
> 3. Update `Context/variants/ATS_LEDGER.md`: bump seen-counts on recurring gaps, add confirmed
>    winning tactics from ATS-**pass** apps, and record auto-knockout patterns separately.
>    **Anonymize — no company names.**
> 4. Tell me the top 2-3 changes to apply to my next overlay, and any backbone gap worth
>    closing for real (a skill to actually learn / a project to build).

## Feed-forward

Every new overlay starts from the ledger — `PLAYBOOK.md` Step 2 tells Claude to read
`ATS_LEDGER.md` first and apply its confirmed tactics + known gaps before proposing the lens.
That's what makes the loop compound instead of repeating the same misses.
