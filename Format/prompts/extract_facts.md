# Prompt contract: `extract_facts`

**Purpose:** bootstrap the source-of-truth claim registry (`Context/facts/claims/*.yaml`)
by extracting **proposed** claims from the existing backbone content. Every claim is
`status: proposed` and non-citable until the owner confirms it at **Gate G0**.

**Inputs (read these, never invent paths):**
- `Context/Experiences/*/context.yaml` and `Context/Experiences/*/detail.html`
- `Context/experiences.yaml`, `Context/resume.yaml`, `Context/narrative.yaml`
- `Context/software_projects.yaml`, `Context/toolchain_projects.yaml`
- `Context/facts/employers.yaml` (anchors), `Format/schemas/claim.schema.json` (shape)

**Output:** one file per group under `Context/facts/claims/`
(`hmc.yaml`, `add-k2.yaml`, `kaist.yaml`, `software.yaml`, `toolchains.yaml`, `education.yaml`),
each `{claims: [ <claim>, ... ]}` conforming to `Format/schemas/claim.schema.json`.

**Hard rules (the anti-hallucination contract):**
1. `status: proposed` for **every** claim. The owner flips `proposed → confirmed` at G0.
2. `source_quote.quote` MUST be an **exact, contiguous, verbatim substring** of the file
   named in `source_quote.file` (whitespace runs may differ — a validator normalizes them).
   `portfolio/facts.py` rejects any quote that is not a literal substring.
3. If no source supports a claim, set `source_quote.quote` and `statement` to the sentinel
   `<placeholder>` and add a `notes:` explaining what the owner must supply at G0.
4. `ownership` derives from the **source verb**, never inflated: "Independently developed" ⇒
   `independent`; "Participated in"/"Supported"/"Worked on" ⇒ `shared`/`support`; passive
   familiarity ⇒ `exposure`. No explicit ownership on team/research work ⇒ default `shared`.
5. `deployment`: `production` only if the source frames it so; `prototype` if the source says
   "not a deployed production tool"; `research` for academic; `personal` for self-built products.
6. Never fabricate a metric. Include `metrics[]` only if the digits appear verbatim in source;
   use `as_of: "<OWNER TO DATE>"` when the source gives no date.
7. Add `forbidden_phrases` where the source implies a constraint (e.g. an unshipped product must
   not be called "published", a private repo url must never be printed).

**After writing:** run `python main.py --lint-facts` and fix every **error** to zero
(warnings for `proposed`/`<placeholder>` are expected and are the Gate G0 to-do list).

**Then STOP** and present the registry to the owner for Gate G0 confirmation. No downstream
phase (match, resume, prep) may cite a claim until the owner confirms it.
