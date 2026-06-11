# Rejection pipeline — what to do after a "no"

The per-JD loop (see `PLAYBOOK.md`) ends when you send the resume. This pipeline
picks up at the rejection and turns it into a sharper next move instead of a
silent dead end. Claude runs it with you; you make the calls.

It always reads `Context/candidate_profile.yaml` first, so the **visa-sponsorship
reality is weighed every time** — that fact alone changes how a rejection should
be read (a sponsorship-needing "adjacent fit" loses early/auto screens that an
"exact fit, no sponsorship" candidate clears, so a rejection is often NOT a
resume-quality signal).

---

## When to run it

You got a rejection, a ghost (4+ weeks silence after applying), or an "moved
forward with other candidates" email for any application that has a folder under
`Applications/<name>/`.

## The prompt (paste to Claude)

> **Run the rejection pipeline for "<name>".**
> Read `Context/candidate_profile.yaml`, `Applications/<name>/jd.txt`,
> `overlay.yaml`, and `notes.md`. Then:
> 1. **Classify the filter** — auto/early screen vs. recruiter vs. later stage,
>    using the timing and channel I give you.
> 2. **Weigh sponsorship** — given my authorization status, how much of this was
>    likely the sponsorship bar vs. fit?
> 3. **Gap audit** — list the JD must-haves I did NOT match exactly (named tools,
>    domain framing), separating *real* gaps from *true-but-unsurfaced* ones I
>    could honestly add.
> 4. **Decide the next move** — pick from the Next-move menu below and say why.
> 5. Write the full diagnosis into the `## Outcome & post-rejection diagnosis`
>    section of `notes.md`, update `result.md` (status, outcome date, stage, why,
>    next move), and add one carry-forward line to `## Lessons to carry to the
>    next application`.

Give Claude the two facts it can't infer: **how fast** the rejection came, and
**through what channel** (auto-email, recruiter note, portal status flip).

## Classify the filter (timing → likely cause)

| Signal | Most likely | Implication |
|--------|-------------|-------------|
| Minutes–hours, generic email | Auto knockout on a form question | Resume was never read — check authorization/location/must-have knockout |
| 1–3 days | Early recruiter/keyword screen, or batch close | Fit + sponsorship weighed together; exact-match gaps matter most |
| 1+ weeks | Human recruiter pass, or req filled | Closer call; referral or a stronger-matched req is the lever |
| 4+ weeks silence | Volume burial | Not about you specifically — referral or fresher req |

## Next-move menu (pick one or more)

1. **Referral, then re-apply** — highest-value lever for a sponsorship candidate;
   routes past the volume screen to a human who can champion sponsorship.
2. **Re-aim at an exact-match req** — same/another employer, but a req that fits
   the backbone exactly (HIL / embedded validation / controls / dyno test-bench)
   rather than a flagship/adjacent one. Flips "adjacent fit" → "exact fit".
3. **Widen the funnel** — apply to the sponsor-friendly `target_employers` in the
   profile who prize this exact profile.
4. **Honest keyword recovery** — surface a true-but-unnamed skill in the backbone
   (e.g. SIL if MIL work qualifies, OO design for existing Python/C++) and rebuild.
5. **Resolve an authorization unknown** — establish sponsorship reality for a
   non-US market (e.g. Germany / EU Blue Card) to open a less harsh funnel.
6. **Stand down on this req** — if it was a pure sponsorship/location knockout,
   don't burn effort re-applying cold; log the lesson and move on.

## The one rule (same as the loop)

Diagnosis never invents experience. A gap is flagged, not filled. Keyword recovery
only surfaces things the backbone already truthfully supports.
