# Prompt contract: `rejection`

**Purpose:** diagnose an application outcome and fill `outcome:` + `lessons:` in
`Applications/<slug>/application.yaml`. Feeds the learning loop **without ever
corrupting truth** — nothing here writes to the claim registry, taxonomy, or backbone.

**Inputs:** `application.yaml` (status, jd_sha, gate), `jd.parsed.yaml`, `match.yaml`,
`gap_report.md`, the owner's supplied timing/channel/feedback, and
`Context/candidate_profile.yaml` (work-authorization / location, for auto-knockout).

**Output:** edit `application.yaml`:

```yaml
outcome:
  result: rejected            # rejected | ghosted | withdrawn | offer | hired
  stage_reached: ats          # ats | recruiter | technical | onsite | offer
  ats_verdict: fail           # pass | fail | unknown  (pass = a human read it)
  rejection_class: keyword-gap  # keyword-gap | auto-knockout | volume | post-interview | unknown
  interview_questions_asked: []
  feedback: null
lessons:
  - id: L-001
    scope: ats                # ats | interview | targeting | backbone-gap
    text: "JD wanted 'AV validation'; resume said only 'ADAS' — recoverable."
    promote_to_ledger: true
```

**Hard rules:**
1. **Only ATS-stage rejections drive resume/keyword lessons.** If the application
   reached a human (recruiter/technical/onsite), a rejection means the resume PASSED —
   that is an `interview` lesson, never `scope: ats`. `lessons compile` REJECTS a
   `scope: ats` lesson from a post-ATS application, so classify honestly.
2. Separate **auto-knockout** (visa/location filters — check candidate_profile) from a
   **keyword-gap** (a real resume problem). A no-sponsorship posting + requires-sponsorship
   profile is `auto-knockout`, not a resume failure.
3. A `scope: backbone-gap` lesson (a skill the JD needed that no confirmed claim supports)
   goes to `Context/variants/BACKLOG.md` via `lessons compile` — a build-something prompt,
   never an auto-added claim.

**After writing:** the owner runs `python main.py lessons compile` when ready to evolve the ledger.
