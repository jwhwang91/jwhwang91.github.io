# WORKFLOW — running the whole loop

This is the one document that runs the application pipeline end to end: from a pasted
job description to a truthfulness-gated resume, a verified PDF, prep packs, a tracked
submission, and a learning loop after the outcome. If you read only one file, read this one.

Two layers, one rule:
- **Backbone** (`Context/*.yaml`) is the single source of truth — your true, confirmed
  career facts. A resume only *selects, reorders, and rewords* what the backbone supports.
- **Applications** (`Applications/<slug>/`, gitignored) hold everything generated per job.
- **The rule that never bends:** nothing is ever asserted beyond a **confirmed claim**.
  LLM proposes → Python validates → human approves. Five human gates (G0–G4).

Design mantra: *LLM proposes, Python disposes, human approves. Score extracted text, not intent.*

---

## 0. One-time setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py --lint-facts        # backbone consistency check
python -m pytest -q                # full test suite should be green
```

Put your private contact data in `Context/private/personal_private.yaml` (gitignored):

```yaml
phone: "+NN-NN-XXXX-XXXX"
```

It is merged into the resume contact line at render time and never enters the tracked tree.

### Gate G0 — confirm bootstrap facts (once)

The claim registry (`Context/facts/claims/*.yaml`) is the source of truth for what you may
say. Review each claim and flip `status: proposed → confirmed`; only **confirmed** claims are
citable. `retired` claims are kept for history but never used. Re-run `python main.py
--lint-facts` until green. You only repeat this when you add new claims (e.g. after building
a new project).

---

## 1. The per-application loop

`<slug>` is your private label for the job (e.g. `tesla-adas-validation-2026-07`); it never
appears on the resume. Each numbered step maps to a row in the table below. LLM steps are
Claude Code slash commands (`/jd-parse`, etc.); everything else is `python main.py …`.

| # | Step | Who | Command |
|---|------|-----|---------|
| 1 | Scaffold + paste JD | you | `python main.py new <slug> --company X --positioning adas-av-validation` → paste into `Applications/<slug>/jd.txt` |
| 2 | Parse JD | py+LLM | `python main.py jd parse <slug>` → `/jd-parse <slug>` → `jd.parsed.yaml` |
| 3 | **G1** confirm parse | you | `python main.py jd confirm <slug>` — 60-sec skim; each keyword shows its verbatim JD quote |
| 4 | Classify support | py+LLM | `python main.py match <slug>` → `/jd-match <slug>` → `match.yaml` |
| 5 | **G2** confirm match | you | `python main.py match confirm <slug>` → writes `gap_report.md` + `portfolio_plan.md`, status → `matched` |
| 6 | Draft resume | LLM | `/resume-plan <slug>` → `resume.yaml` (cited bullets only) |
| 7 | Finalize draft | you | edit `resume.yaml`; `python main.py validate <slug> --stage resume` → status `drafted` |
| 8 | Render + gate | py | `python main.py render <slug>` → `out/resume_ats.{txt,html,md}` + `gate_report.{yaml,md}` + `checklist.md` + `changes.md` + `audit.json`; PASS → status `gated`; FAIL → fix `resume.yaml`, back to step 6 |
| 9 | **G3** approve | you | review `gate_report.md` / `checklist.md` / `changes.md`; `python main.py status <slug> approved` |
| 10 | Export + verify PDF | you+py | browser **Save as PDF** → `out/resume_final.pdf`; `python main.py pdfcheck <slug>` |
| 11 | Prep packs | LLM+py | `/interview-pack <slug>` → `pack interview`; `/coding-pack <slug>` → `pack coding` |
| 12 | **G4** submit | you | `python main.py status <slug> submitted` — the hard gate (see below) |
| 13 | Log events | you | `python main.py log <slug> --note "recruiter call"`; `python main.py status <slug> screen\|interview\|offer\|hired\|rejected\|ghosted` |
| 14 | Outcome + lessons | LLM | `/rejection <slug>` → fills `outcome:` + `lessons:` in `application.yaml` |
| 15 | Evolve | py+LLM+you | `python main.py lessons compile` → `/evolve-ledger` → you commit the `ATS_LEDGER.md` edit |

**Status auto-advance:** `jd confirm`→`parsed`, `match confirm`→`matched`, first passing
`validate --stage resume`→`drafted`, gate PASS→`gated`. You set only `approved`, `submitted`,
and post-submission statuses. Auto statuses can't be set by hand.

---

## 2. The five gates

- **G0 — bootstrap facts.** Only `confirmed` claims are citable (§0).
- **G1 — parse.** Every parsed keyword carries a verbatim JD quote; you confirm the reading.
- **G2 — match.** You confirm each keyword's support level (`direct`/`partial`/`adjacent`/
  `unsupported`). The cache learns your confirmed resolutions.
- **G3 — gated package.** The resume passed the truthfulness gate; you read the report and approve.
- **G4 — submit (hard gate).** `status <slug> submitted` mechanically refuses unless **all** hold:
  status is `approved`; gate verdict is `PASS` (or `HIGH_RISK` with `--acknowledge-risk`);
  `out/resume_final.pdf` exists and passes the text-layer check; `resume_ats.txt` is unchanged
  since the gate ran; and `jd.txt` is unchanged since parse. You cannot send an ungated,
  text-less, or silently-edited resume.

---

## 3. Exporting the PDF correctly — do not skip

The HTML is ATS-friendly, but the **export step can destroy the text layer**, leaving a file
that looks perfect to a human and reads as **blank** to an ATS.

- **Use the browser's "Save as PDF"** (Chrome/Edge → Ctrl+P → Destination *Save as PDF*).
- **Never "Microsoft Print to PDF"** — it rasterizes text to outlines → zero extractable text.
- **Verify:** `python main.py pdfcheck <slug>` compares the PDF's text layer to `resume_ats.txt`
  (must be ≥0.98 similar). G4 runs this again — a bad PDF cannot be submitted.

---

## 4. Prep packs

- **Interview:** `/interview-pack <slug>` writes `prep/interview_pack.yaml`; `python main.py
  pack interview <slug>` validates (cited claims confirmed, one danger-question per `partial`
  keyword, STAR numbers traced to real metrics, no forbidden phrasing) and renders the `.md`.
- **Coding:** `/coding-pack <slug>` selects problems from the committed bank
  (`Context/prep/coding_bank.yaml`); `python main.py pack coding <slug>` checks all ids exist,
  count is 20–40, and the difficulty mix fits the inferred format band, then renders the `.md`.

---

## 5. Tracking + learning

- `python main.py track [--open|--closed|--csv]` — table of every application (new + legacy).
- `python main.py log <slug> --note "…"` — append an event.
- `python main.py status <slug> <status>` — advance the lifecycle (validated transitions).
- `python main.py lessons compile` — aggregate lessons from **closed** applications into an
  anonymization-linted `Applications/_ledger_draft.md`. Only ATS-stage lessons feed the ATS
  ledger (a post-interview rejection means the resume already passed — that's an interview
  lesson). `backbone-gap` lessons append to `Context/variants/BACKLOG.md` (build something,
  then bootstrap a new confirmed claim). Nothing auto-writes to the registry or taxonomy.

---

## 6. Dev-mode regenerate ritual (keep the public site byte-identical)

Every code change must leave the public site output unchanged. Before committing pipeline code:

```bash
python main.py                     # rebuild dist/
python -m pytest -q                # includes the site-regression golden test
python main.py --lint-facts        # backbone consistency
python scripts/privacy_guard.py    # no private path or phone in the tree
```

`tests/test_site_regression.py` asserts `dist/` is byte-identical to the committed golden
render, so a refactor that changes the site fails loudly.

---

## 7. Sample outputs

A fully worked, anonymized example lives in `tests/fixtures/sample_output/` — the Tesla
fixture end to end: `jd.parsed.yaml`, `match.yaml`, `resume_ats.{txt,html,md}`,
`gate_report.{yaml,md}`, `checklist.md`, `changes.md`, `audit.json`, `interview_pack.{yaml,md}`,
`coding_pack.{yaml,md}`. Read these to see exactly what each stage produces.

---

## 8. Legacy site + variant commands (still supported)

The original static-site flow is unchanged and still works: `python main.py` (build site),
`--new-variant`/`--variant`/`--all-variants`/`--list-variants`/`--insights`. See `PIPELINE.md`
for the backbone (Stage A) and the lightweight overlay-variant path.

---

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `render` exits 2 with a `gate_report` FAIL | Truthfulness violation. Read `gate_feedback` + `gate_report.md`; fix `resume.yaml` (unsupported term, missing hedge, unbacked number); re-run from step 6. |
| `status submitted` refused | A G4 precondition failed — the message lists which (not approved / verdict not PASS / PDF missing or text-less / resume or JD changed). Fix and retry. |
| `pack interview` fails on a `partial` keyword | Add a `danger_questions` entry for it (anti-overclaim net); it also requires a confirmed `match.yaml`. |
| `pack coding` fails on difficulty mix | Re-select `problem_ids` so the mix fits the format band (±15pp); ids must exist in the bank. |
| `pdfcheck` FAIL | The export lost the text layer — re-export via *Save as PDF* (§3). |
| `--lint-facts` red | A claim references a missing anchor or a retired claim is cited; fix the registry. |
| A number was rejected | It isn't in any cited claim's metrics — use a real metric or `<placeholder>`; never invent one. |
