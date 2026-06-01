# Per-JD resume variants — the regulated loop

One **backbone** (the `Context/*.yaml` files), many **lenses**. Each job application
gets its own folder here. Claude only ever *proposes* an `overlay.yaml`; you approve;
`main.py` deterministically merges and renders. The backbone and the live site at
https://jwhwang91.github.io are never touched.

## Layout

```
Context/variants/<name>/        <- source + proposal (e.g. "Tesla 1", "Rivian 2") — gitignored
    jd.txt          # the pasted job description (input)
    overlay.yaml    # Claude's PROPOSAL: which items to surface, ordering, ATS keywords (you review/edit)
    notes.md        # rationale + your review feedback + lessons for next time

Applications/<name>/            <- generated, ready to send — gitignored, NOT wiped by the backbone build
    resume.html     # lean, self-contained, PDF-ready; case-study links -> live portfolio
```

A flat `Context/variants/<name>.yaml` (no folder) also works for a reusable field
lens you might want to commit publicly (e.g. `adas-controls.yaml`).

## The loop

1. **Ingest** — `python main.py --new-variant "Tesla 1"`, then paste the JD into
   `Context/variants/Tesla 1/jd.txt`.
2. **Analyze + Propose** — ask Claude (Claude Code): *"run the loop for Tesla 1."*
   Claude reads the JD + backbone and fills in `overlay.yaml` with a plain-English rationale.
3. **Review (the gate — you)** — read it, edit `overlay.yaml` directly, or send it back
   with notes. Nothing is published; the backbone never moves.
4. **Build** — `python main.py --variant "Tesla 1"` -> `Applications/Tesla 1/resume.html`.
   Open it, Export PDF, send it.
5. **Feedback** — your edits/notes go in `notes.md` so the next application starts smarter.

`python main.py --list-variants` shows every variant and whether it's been built.

## Why the resume stays lean

Every variant prints your portfolio URL and links each role/project to its case study on
the live site. So the resume carries summaries + ATS keywords only — the deep technical
case studies stay at https://jwhwang91.github.io and are never duplicated per application.

## overlay.yaml schema

A thin lens; anything omitted is inherited from the backbone. `--new-variant` writes a
fully commented template. Backbone ids: experiences `hmc-adas`, `add-k2-tcu`,
`kaist-masters`; toolchains `e2e-xcp-bypass`, `timeseries-ai-training`,
`tos-odp-bev-simulator`.

| key | effect |
|-----|--------|
| `site:` | per-key override of `title`, `headline`, `one_liner`, `keywords` (ATS strip), `main_focus` (summary) |
| `resume:` | per-key override, e.g. a `skills` group |
| `experiences: {include, overrides}` | subset/reorder by id; per-id `hook`, `bullets`, `keywords` (ATS line) |
| `toolchains: {include, overrides}` | subset/reorder by id |
| `noindex` | defaults true |
