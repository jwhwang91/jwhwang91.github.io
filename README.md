# Resume / Portfolio Static Site Generator v3

> **New here?**
> - To run the per-job **application pipeline** (JD → keyword match → truthfulness-gated resume →
>   verified PDF → interview/coding prep → tracking → learning), read the one-file operator
>   guide: **[`WORKFLOW.md`](WORKFLOW.md)**.
> - For the high-level map (backbone → live site, plus the loop), see [`PIPELINE.md`](PIPELINE.md).
> - This README documents the **static-site generator** internals (the backbone that deploys).

This version follows the redesigned strategy:

- Main page is a Notion-like, PDF-exportable resume.
- Main page uses short, AI/human-attention keywords.
- Experience section now owns the main-root career projects:
  - KAIST Master's Thesis - Turret Motion Stabilization
  - ADD K2 TCU SW Development - Perfect V-Cycle
  - HMC Commercial Vehicle Lvl2 ADAS
- Selected Projects now focuses only on toolchain projects:
  - E2E GUI XCP Bypassing App
  - E2E GUI Time-Series AI Model Training Platform
  - TOS/ODP MATLAB Simulink Bird-Eye-View Simulator
- K2 TCU detail page includes rendered images from the original PDF.
- Project/detail links reuse named browser tabs instead of opening duplicate tabs when possible.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Build

```bash
python main.py
```

Open:

```text
dist/index.html
```

Standalone single-file version:

```text
dist/standalone.html
```

This file embeds the main page CSS/JS plus local detail pages and their image assets.

## Export PDF

Open `dist/index.html`, then either:

- click `Export PDF`, or
- use browser Print -> Save as PDF.


## Personal info file

Personal/contact information is separated into:

```text
Context/personal_info.yaml
```

Edit this file for:

```text
email
phone
LinkedIn
GitHub
full portfolio URL
optional links
```

This keeps personal contact data separate from the portfolio narrative in `site.yaml`.



## Custom HTML for experience detail pages

If an experience page needs a more polished, architecture-heavy layout than the generic template,
you can place a dedicated HTML file here:

```text
Context/Experiences/<experience_folder>/detail.html
```

If `detail.html` exists, `main.py` will copy that file directly to:

```text
dist/experience/<experience-id>/index.html
```

This is the recommended approach for pages like:
- master's thesis architecture pages,
- system-design pages,
- pages with custom math / proof layout,
- pages where slide crops alone look too naive.

## Turning a thesis slide into a styled detail page

For the master's thesis page, the source images are stored here:

```text
Context/Experiences/kaist_masters/pictures/
```

The page text is controlled here:

```text
Context/Experiences/kaist_masters/context.yaml
```

To update the page:

1. Replace or add images in the `pictures/` folder.
2. Edit `context.yaml`.
3. Add each image under the `images:` list.
4. Run:

```bash
python main.py
```

The generated page will be:

```text
dist/experience/kaist-masters/index.html
```

## Where to edit

Main resume strategy:

```text
Context/site.yaml          # dual-track identity: title, headline, ATS keywords, summary
Context/resume.yaml        # education + skills (ordered list of {label, items} groups)
Context/narrative.yaml
Context/experiences.yaml
```

The backbone is **dual-track**: alongside the automotive `toolchain_projects.yaml`, a second
project spine lives in `Context/software_projects.yaml` (web / AI / desktop products —
DeckFlip, DecisionCanvas, Voiceprint, Pinterest Exporter, PathPilot). Both render on the public
site; per-job variants pivot to whichever spine the JD wants (see `Context/variants/`).

Experience detail pages:

```text
Context/Experiences/*/context.yaml
Context/Experiences/*/pictures/
```

Toolchain projects (automotive / validation tooling, with generated detail pages):

```text
Context/toolchain_projects.yaml
Context/Projects/toolchains/*/context.yaml
Context/Projects/toolchains/*/pictures/
Context/Projects/toolchains/*/format/
```

Software / web / AI / desktop products (link out to live deployments + repos; no detail pages):

```text
Context/software_projects.yaml   # ids: deckflip, decisioncanvas, voiceprint, pinterest-exporter, pathpilot
```

## Hard-coded project HTML

For projects where you provide a complete HTML file later, place it under that project's `format/` folder and set:

```yaml
source_type: "html"
source: "Context/Projects/toolchains/project_folder/format/detail.html"
```
