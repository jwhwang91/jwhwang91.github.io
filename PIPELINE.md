# Portfolio Pipeline — end-to-end steps

One **backbone** (your true, field-agnostic resume) → many per-job **applications**, each a
single private folder. This file is the map. **The full operator guide is [`WORKFLOW.md`](WORKFLOW.md)** —
read that to run the loop; the strategy playbooks live in `Context/variants/`.

```
Backbone (Context/*.yaml)  ──► python main.py            ──► dist/  ──► push ──► live site (HR-facing)
        │
        └─ per job ──► Applications/<slug>/  (new → jd parse → match → resume → render+gate → pdfcheck → submit)
                                            └─► out/resume_final.pdf ──► send   +   prep/ interview & coding packs
                                                     │
                                            track · outcome · lessons compile ──► ATS_LEDGER ──► next application
```

Two truths that never bend:
- **The backbone is the single source of truth.** A variant only *selects, reorders, and
  rewords* what the backbone already supports — it never invents a skill. See
  `Context/variants/variant-ats-priority` rules in `PLAYBOOK.md`.
- **The live site is HR-facing.** Only the backbone deploys; applications are private and
  gitignored. Nothing is live until you push.

---

## Stage A — The backbone (the live portfolio)

1. **Edit** the source of truth in `Context/`: `site.yaml`, `resume.yaml`, `narrative.yaml`,
   `experiences.yaml`, `toolchain_projects.yaml` (automotive / validation tooling),
   `software_projects.yaml` (web / AI / desktop products), plus detail pages under
   `Context/Experiences/*/` and `Context/Projects/toolchains/*/`.

   > **Dual-track backbone.** Two project spines coexist: the automotive `toolchains` and the
   > `software` products (DeckFlip, DecisionCanvas, Voiceprint, Pinterest Exporter, PathPilot).
   > The public site shows both; each per-job variant pivots to whichever the JD wants.
2. **Build** → `python main.py` → renders `dist/` (`index.html` + `standalone.html`).
3. **Review** `dist/index.html` in a browser; Export PDF if you want a copy.
4. **Deploy** → commit + push `Context/`, `Format/`, `Style/` to `main`. CI
   (`.github/workflows/deploy.yml`) rebuilds `dist/` and publishes to
   https://jwhwang91.github.io. **Keep it truthful, professional, reversible.**

> Only commit SOURCE changes. `dist/` is rebuilt in CI. `Applications/` and
> `Context/candidate_profile.yaml` are gitignored and must stay private.

---

## Stage B — Per-job application (the regulated pipeline)

Each application is **one self-contained folder** `Applications/<slug>/` holding every
artifact from first paste to post-mortem. `<slug>` is your private label — it never appears on
the resume. **Run it from [`WORKFLOW.md`](WORKFLOW.md)** (the step-by-step table + gates);
the short version:

```
Applications/<slug>/
    jd.txt                 # 1. pasted JD (input)
    jd.parsed.yaml         # 2. parsed keywords, each with a verbatim JD quote
    match.yaml             # 3. per-keyword support (direct/partial/adjacent/unsupported)
    gap_report.md          #    coverage + pre-resume recommendation
    resume.yaml            # 4. the draft (cited bullets only)
    out/resume_ats.{txt,html,md}, resume_final.pdf   # 5. rendered + exported
    gate_report.{yaml,md}, checklist.md, changes.md, audit.json   # 6. the truthfulness gate
    prep/interview_pack.{yaml,md}, coding_pack.{yaml,md}          # 7. prep packs
    application.yaml       # 8. the tracking record (status, events, outcome, lessons)
```

1. **Scaffold + paste** → `python main.py new <slug> --company X --positioning <track>`; paste
   the JD into `jd.txt`.
2. **Parse → match → draft → render** → `jd parse` / `match` / `/resume-plan` / `render`, each
   gated by a human confirm (G1–G3). The **gate scores `resume_ats.txt` and re-verifies the
   PDF text layer** — it asserts nothing beyond a confirmed claim.
3. **Export + verify PDF** → browser *Save as PDF* → `pdfcheck`.
4. **Submit (G4)** → `python main.py status <slug> submitted` — the hard gate; mechanically
   refuses an ungated, text-less, or silently-edited resume.

**Top priority is still to pass the ATS keyword filter** — mirror the JD's exact wording
(term + acronym) for every skill the backbone *truly* supports; never invent one. The
deterministic validators enforce exactly that.

### Exporting the PDF correctly — DON'T skip this

The HTML is ATS-friendly, but the **export step can destroy the text layer**, leaving a file
that looks perfect to a human and reads as **blank** to an ATS.

- **Export with the browser's "Save as PDF"** (Chrome/Edge → Ctrl+P → Destination *Save as PDF*).
- **NEVER "Microsoft Print to PDF"** — it rasterizes text to outlines → zero extractable text.
- **Verify:** `python main.py pdfcheck <slug>` (≥0.98 similarity to `resume_ats.txt`); the G4
  submit gate runs it again, so a bad PDF cannot be sent.

---

## Stage C — After a rejection / ghost (the diagnosis loop)

1. Give Claude the two facts it can't infer: **how fast** the rejection came and **through
   what channel** (auto-email / recruiter / portal flip); log them with
   `python main.py log <slug> --note "…"` and advance `status <slug> rejected|ghosted|…`.
2. `/rejection <slug>` classifies the filter (auto-knockout vs keyword-gap), weighs
   sponsorship (`Context/candidate_profile.yaml`), and fills `outcome:` + `lessons:` in
   `application.yaml`. See `Context/variants/REJECTION_PIPELINE.md` for the strategy.

---

## Stage D — Evolve (learn across applications)

Stage C diagnoses *one* application; this stage makes the *whole system* better.
Full strategy: `Context/variants/EVOLUTION.md`; the growing knowledge: `ATS_LEDGER.md`.

1. **Track** → `python main.py track [--open|--closed|--csv]` for the scoreboard (new
   applications + legacy folders).
2. **Compile lessons** → `python main.py lessons compile` aggregates lessons from **closed**
   applications into an anonymization-linted `Applications/_ledger_draft.md`; `backbone-gap`
   lessons append to `Context/variants/BACKLOG.md`.
3. **Evolve the ledger** → `/evolve-ledger` proposes an anonymized `ATS_LEDGER.md` edit; **you
   commit it**. Nothing auto-writes to the registry or taxonomy.

**The rule that keeps this honest:** only **ATS-stage** rejections drive resume ATS changes. A
post-interview rejection means the resume already cleared ATS — that's an interview lesson.
`lessons compile` enforces this in code.

---

## Quick command reference

Full detail in [`WORKFLOW.md`](WORKFLOW.md). Pipeline (new):

| Command | What it does |
|---|---|
| `python main.py` | Build the backbone site to `dist/` (what CI runs). |
| `new <slug> --company X --positioning <track>` | Scaffold an application + `jd.txt`. |
| `jd parse <slug>` / `jd confirm <slug>` | Parse JD, then confirm (G1). |
| `match <slug>` / `match confirm <slug>` | Classify support, then confirm (G2); writes gap + plan. |
| `validate <slug> --stage resume` | Validate the finalized `resume.yaml` draft. |
| `render <slug>` | Render `out/` + run the truthfulness gate (→ `gated` on PASS). |
| `status <slug> <status>` | Advance the lifecycle (`approved`/`submitted`/…); submit is the G4 hard gate. |
| `pdfcheck <slug>` | Verify the exported PDF text layer. |
| `pack interview <slug>` / `pack coding <slug>` | Validate + render the prep packs. |
| `track` / `log <slug> --note` / `lessons compile` | Scoreboard, event log, ledger draft. |

Legacy site/variant commands (still supported): `--new-variant`, `--variant`,
`--all-variants`, `--list-variants`, `--insights` — see [`WORKFLOW.md`](WORKFLOW.md) §8.
