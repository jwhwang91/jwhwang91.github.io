# Playbook — optimizing the resume for a specific JD

**No GUI needed.** Claude Code is the loop. You do three things: run one command,
paste the JD into a text file, and talk to Claude. Claude proposes; you approve;
the build is deterministic. The backbone (`Context/*.yaml`) and the live site are
never touched.

---

## Top priority: pass the ATS keyword filter

Every variant is optimized **first** to clear automated keyword screening — above
prose elegance or brevity. Concretely, for every skill the backbone TRULY supports:

- **Mirror the JD's exact wording** (JD says "Hardware-in-the-Loop (HIL)" → use
  that exact phrase, not a synonym).
- **Spell out term + acronym** ("Controller Area Network (CAN)") so either matches.
- **Front-load must-haves** in the keyword strip, summary, and per-experience
  `keywords:` lines, then reuse them naturally in the bullets.
- **Match the JD's job-title language** in the resume `title` where truthful.
- **Surface true-but-unnamed skills** (honest keyword recovery) to raise coverage.
- **Parse-clean export:** single-column PDF, standard headings (no multi-column
  scramble).

Bounded by the one rule below: maximize coverage of keywords you *actually have* —
never keyword-stuff a skill you lack. (ATS-first is necessary but not sufficient:
form-level knockouts like visa sponsorship sit outside the resume — see
`REJECTION_PIPELINE.md`.)

---

## Step 0 — one-time, per application: create the folder

```powershell
cd C:\Users\test\PycharmProjects\portfolio
python main.py --new-variant "Tesla 1"
```

Creates `Applications\Tesla 1\` with `jd.txt`, `overlay.yaml`, `notes.md`, `result.md`.
The name (`"Tesla 1"`) is just your label; the build adds `Applications\Tesla 1\resume.html`
to the same folder, and the name never appears on the resume.

## Step 1 — paste the JD

Open `Applications\Tesla 1\jd.txt` and paste the **entire** job posting as plain
text (title, responsibilities, requirements, nice-to-haves — messy copy-paste is fine).
Save as UTF-8. Optionally put the posting URL on the first line.

## Step 2 — ask Claude to analyze + propose (the prompt)

Paste this to Claude (Claude Code), editing the name:

> **Run the JD loop for "Tesla 1".**
> First read `Context/variants/ATS_LEDGER.md` and apply its confirmed tactics +
> known gaps. Then read `Applications/Tesla 1/jd.txt` and the backbone, and fill in
> `overlay.yaml`. **Top priority: maximize ATS keyword-filter pass-through** —
> mirror the JD's exact wording (term + acronym) for every skill my backbone
> truly supports. Tell me:
> 1. the JD's top must-haves and the exact keywords it uses,
> 2. how you mapped them to my experiences/projects (what you surfaced, reordered, reworded),
> 3. the ATS keywords you added and where, and my estimated must-have coverage (e.g. 12/15),
> 4. anything the JD wants that my backbone does NOT support — flag it, do not invent it.
> Keep every bullet truthful to the backbone. Don't build yet — show me the proposal first.

**Optional knobs** — add any of these to the prompt to steer it:

- *Track:* "This is a software/web/AI role — use the software spine" (reframe experience bullets
  around the software, front-load the `software` projects, trim `toolchains`; start from
  `software-ai.yaml`). Or "pure controls role — hide the software section" (start from
  `adas-controls.yaml`, which sets `software: {include: []}`).
- *Focus:* "Lead with controls, not the AI/tooling work" / "lead with the LLM/full-stack work."
- *Length:* "Keep it to one page" / "two pages is fine."
- *Tone:* "Plainer language, less jargon" / "more senior/leadership framing."
- *Must-keep / must-drop:* "Always keep the K2 TCU role" / "drop the KAIST masters for this one."
- *Projects:* "Only show DeckFlip and DecisionCanvas" / "only the XCP validation project."

**Two ready-made starting lenses** (copy + tweak instead of starting blank):
`Context/variants/adas-controls.yaml` (controls/embedded) and
`Context/variants/software-ai.yaml` (software/web/AI). Backbone software ids:
`deckflip`, `decisioncanvas`, `voiceprint`, `pinterest-exporter`, `pathpilot`.

## Step 3 — review (your gate)

Claude shows the proposal + rationale. You either:

- **approve** → say "build it", or
- **send it back** → e.g. "tone down the AI angle, this is a pure controls role",
  "add ISO 26262 to the keyword strip", "merge HMC bullets 2 and 3", "the EKF bullet
  overstates it — soften". You can also just edit `overlay.yaml` by hand.

Nothing is published at any point. Iterate until you're happy.

## Step 4 — build

Claude runs it (or you do):

```powershell
python main.py --variant "Tesla 1"
```

→ `Applications\Tesla 1\resume.html`. Open it, click **Export PDF** (or browser
Print → Save as PDF), and send the PDF. Case-study links point to your live portfolio.

## Step 5 — capture feedback (closes the loop)

Tell Claude: **"log what we changed and why to notes.md."** Those lessons make the
next application's first proposal sharper.

---

## Quick command reference

| command | does |
|---------|------|
| `python main.py --new-variant "<name>"` | scaffold a new application folder |
| `python main.py --variant "<name>"` | build that application's resume |
| `python main.py --list-variants` | list all applications + whether built |
| `python main.py` | rebuild the backbone site only (unchanged) |

## The one rule that never bends

A variant may **reorder, re-emphasize, reword, and select** — but it may never claim
anything the backbone doesn't support. If a JD wants something you don't have, Claude
flags the gap; it does not invent experience.
