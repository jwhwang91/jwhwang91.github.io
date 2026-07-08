# Prompt contract: `evolve_ledger`

**Purpose:** turn the anonymized `Applications/_ledger_draft.md` (produced by
`python main.py lessons compile`) into a proposed edit to the **public**
`Context/variants/ATS_LEDGER.md` — cross-application patterns only, never a single
company's story.

**Inputs:** `Applications/_ledger_draft.md` (already anonymization-linted — no company
names or URLs), the current `Context/variants/ATS_LEDGER.md`.

**Output:** a proposed diff/addition to `Context/variants/ATS_LEDGER.md` describing the
*pattern* (e.g. "AV-simulation JDs consistently want 'scenario-based testing' phrased with
the CARLA/AV-sim vocabulary — mirror it when the backbone supports it"). The human commits.

**Hard rules:**
1. The ledger is **public** (this repo deploys to a public site). NEVER introduce a company
   name, req URL, or JD-verbatim line — only anonymized, generalized patterns.
2. Only ATS-stage learnings belong here. Post-interview lessons are interview-prep, not ledger.
3. Never modify the claim registry, taxonomy, or Context backbone from a lesson — the ledger
   is guidance for the next overlay/draft, not a truth source.

**After writing:** the owner reviews and commits the `ATS_LEDGER.md` edit by hand.
