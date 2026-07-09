# JobOps — local UI over the application pipeline

A localhost web app that **views and orchestrates** the pipeline. It never reimplements
pipeline logic: every write shells out to `python main.py --json <subcommand>`, and every
screen renders the schema-validated artifacts already on disk. CLI-driven and UI-driven
flows therefore produce byte-identical artifacts.

## Run

```bash
pip install -r requirements.txt          # from the repo root (pipeline deps)
pip install -r ui/requirements.txt       # UI deps (FastAPI/uvicorn)
python -m ui.server                      # serves http://127.0.0.1:8765
```

- **Localhost only.** The server refuses any non-localhost bind and makes zero external
  network calls. All application data stays in the gitignored `Applications/` folder.
- **LLM steps** (parse / match / draft / prep / rejection) default to **manual**: the UI
  shows the `/slash-command` to run in Claude Code. Set `JOBOPS_HEADLESS=1` (with the
  `claude` CLI on PATH) to have the UI drive headless Claude Code executing the same
  `Format/prompts/*.md` contracts — one runner interface, so headless-CLI and a future
  API mode are interchangeable. Headless runs use **Opus 4.8** (`claude-opus-4-8`) by
  default; override with `JOBOPS_MODEL=<model-id>` (e.g. `claude-sonnet-5`). Reasoning
  effort per call defaults to **`max`** (`claude -p --effort max`); override with
  `JOBOPS_EFFORT` (`low`/`medium`/`high`/`xhigh`/`max`; `ultracode` too if your `claude`
  CLI supports it — an unknown value falls back to `max`).
- **Isolate data** (dev/test): `JOBOPS_APPLICATIONS=/tmp/apps python -m ui.server` relocates
  only the private Applications/ dir.

## Screens → artifacts/commands

1. **New** — JD paste → `new` + `jd parse`; keyword/quote confirm (**G1**) → `jd confirm`
2. **Match** — classification confirm (**G2**) → `match confirm`; gap + portfolio-plan panels
3. **Resume** — `resume.yaml` edit → live `resume_ats.html` preview; gate panel; regenerate
4. **Approve & Export** — checklist → `status approved` (**G3**); `pdfcheck`; submit (**G4**)
5. **Prep** — rendered interview + coding packs with progress checkboxes
6. **Tracker** — all-applications table; status/event updates; outcome; lessons draft

**ATS honesty:** the UI shows verdict + coverage % + confidence tier (High/Med/Low) — never
a probability, until a calibration module exists trained on recorded outcomes.
