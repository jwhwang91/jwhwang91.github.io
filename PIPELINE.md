# Portfolio Pipeline — end-to-end steps

One **backbone** (your true, field-agnostic resume) → many per-job **applications**, each a
single private folder. This file is the map; the detailed playbooks live in
`Context/variants/`.

```
Backbone (Context/*.yaml)  ──► python main.py            ──► dist/  ──► push ──► live site (HR-facing)
        │
        └─ lens per job ──► Applications/<name>/overlay.yaml ──► python main.py --variant "<name>"
                                                              └─► Applications/<name>/resume.html ──► PDF ──► send
                                                                       │
                                                              result.md + rejection pipeline ──► next application
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
   `experiences.yaml`, `toolchain_projects.yaml`, plus detail pages under
   `Context/Experiences/*/` and `Context/Projects/toolchains/*/`.
2. **Build** → `python main.py` → renders `dist/` (`index.html` + `standalone.html`).
3. **Review** `dist/index.html` in a browser; Export PDF if you want a copy.
4. **Deploy** → commit + push `Context/`, `Format/`, `Style/` to `main`. CI
   (`.github/workflows/deploy.yml`) rebuilds `dist/` and publishes to
   https://jwhwang91.github.io. **Keep it truthful, professional, reversible.**

> Only commit SOURCE changes. `dist/` is rebuilt in CI. `Applications/` and
> `Context/candidate_profile.yaml` are gitignored and must stay private.

---

## Stage B — Per-job application (the regulated loop)

Each application is **one self-contained folder** `Applications/<name>/` holding source,
output, and outcome. `<name>` is your private label (e.g. "Tesla 1") — it never appears on
the resume. Full playbook: `Context/variants/PLAYBOOK.md` and `README.md`.

```
Applications/<name>/
    jd.txt          # 1. pasted job description (input)
    overlay.yaml    # 2. Claude's proposal: which items to surface, order, ATS keywords (you review/edit)
    notes.md        #    rationale + your review feedback + lessons
    result.md       # 5. the outcome — YOU update this
    resume.html     # 4. generated, lean, PDF-ready (case-study links -> live portfolio)
    (PDF / evidence files you add)
```

1. **Ingest** → `python main.py --new-variant "<name>"` scaffolds the folder. Paste the full
   job posting into `Applications/<name>/jd.txt` (UTF-8; posting URL on the first line).
2. **Analyze + propose** → tell Claude: *"run the JD loop for `<name>`."* Claude reads the JD
   + backbone and fills `overlay.yaml`, with rationale in `notes.md`. **Top priority: pass
   the ATS keyword filter** — mirror the JD's exact wording (term + acronym) for every skill
   the backbone *truly* supports; never invent one.
3. **Review (your gate)** → read `overlay.yaml`, edit it directly, or send it back with
   notes. Nothing publishes; the backbone never moves.
4. **Build** → `python main.py --variant "<name>"` → `Applications/<name>/resume.html`. Open
   it, Export PDF, send it. (The resume stays lean — every role/project links to its deep
   case study on the live portfolio, so nothing is duplicated per application.)
5. **Record the outcome** → update `Applications/<name>/result.md` (status / applied date /
   outcome date / stage reached / why / next move) as the application moves.

### Exporting the PDF correctly — DON'T skip this

This is where a perfect resume silently fails ATS. The HTML is text-based and ATS-friendly,
but the **export step can destroy the text layer**, leaving a file that looks pixel-perfect
to a human and reads as **blank** to an ATS.

- **Export with the browser's "Save as PDF"** — in Chrome/Edge, click `Export PDF` (or
  Ctrl+P), set **Destination → "Save as PDF"** (Chromium's Skia/PDF engine, which keeps a
  real, selectable text layer).
- **NEVER use "Microsoft Print to PDF"** (the Windows virtual printer). It converts the text
  to vector outlines → **zero extractable text**. (A previously submitted resume was found to
  have 0 characters across 4 pages because of exactly this.) Avoid any "print to image" path.
- **Verify before you send (10 seconds):** open the PDF, `Ctrl+A` → `Ctrl+C`. If the text
  won't select/copy, the ATS can't read it — re-export. Tell-tale of a bad file: large byte
  size for little content, and no selectable text.
- **Or ask Claude to check it:** drop the exported PDF in `Applications/<name>/` and say
  *"verify the text layer."* A clean file returns the full resume text; a bad one returns
  ~0 characters (no `/Font` resources, Producer "Microsoft: Print To PDF").

Helpers: `python main.py --list-variants` (every application + whether built);
`--all-variants` (rebuild all). Reusable, committable field lenses can live as a flat
`Context/variants/<name>.yaml` instead of a folder.

---

## Stage C — After a rejection / ghost (the diagnosis loop)

When a rejection, a 4+ week ghost, or a "moved forward with other candidates" email arrives
for any `Applications/<name>/`. Full playbook: `Context/variants/REJECTION_PIPELINE.md`.

1. Give Claude the two facts it can't infer: **how fast** the rejection came and **through
   what channel** (auto-email / recruiter / portal flip).
2. Tell Claude: *"run the rejection pipeline for `<name>`."* It classifies the filter, weighs
   sponsorship (see `Context/candidate_profile.yaml`), audits real vs. recoverable gaps, and
   picks a next move (referral / exact-match req / widen funnel / honest keyword recovery /
   resolve auth unknown / stand down).
3. It writes the short outcome to `result.md` and the full diagnosis + a carry-forward lesson
   to `notes.md`, so the next application starts smarter.

---

## Stage D — Evolve (learn across applications)

Stage C diagnoses *one* application; this stage makes the *whole system* better. Full
playbook: `Context/variants/EVOLUTION.md`; the growing knowledge: `Context/variants/ATS_LEDGER.md`.

1. **Score it** → `python main.py --insights` reads every `result.md` and prints ATS
   pass-through (reaching a human = passed the ATS), which applications were knocked out before
   a human read them, and any PDF text-layer warnings.
2. **Evolve the ledger** → tell Claude *"evolve the ATS ledger."* It mines recurring,
   anonymized patterns from the ATS-fail JDs/overlays and updates `ATS_LEDGER.md`.
3. **Feed-forward** → every new overlay starts by reading `ATS_LEDGER.md` (Step 2 of the loop),
   so each result compounds into the next resume.

**The rule that keeps this honest:** only **ATS-stage** rejections drive resume ATS changes. A
post-interview rejection means the resume already cleared ATS — don't churn its keywords; fix
fit/interview instead.

---

## Quick command reference

| Command | What it does |
|---|---|
| `python main.py` | Build the backbone site to `dist/` (what CI runs). |
| `python main.py --new-variant "<name>"` | Scaffold `Applications/<name>/` (jd, overlay, notes, result). |
| `python main.py --variant "<name>"` | Build one application's `resume.html`. |
| `python main.py --all-variants` | Rebuild every application. |
| `python main.py --list-variants` | List applications and whether each is built. |
| `python main.py --insights` | Scoreboard from all `result.md`: ATS pass-through, knockouts, PDF text-layer warnings. |
