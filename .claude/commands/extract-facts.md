---
description: Bootstrap the proposed claim registry from backbone content (Gate G0)
---

Read `Format/prompts/extract_facts.md` and execute its contract for this repository.

Steps:
1. Read every input file listed in the prompt (the `Context/Experiences/*`,
   `Context/*.yaml`, `Context/software_projects.yaml`, `Context/toolchain_projects.yaml`)
   and `Format/schemas/claim.schema.json`.
2. Write the six claim files under `Context/facts/claims/` — every claim `status: proposed`,
   every `source_quote` a verbatim substring of its cited file, ownership per the source verb,
   `<placeholder>` for anything the source does not support.
3. Run `python main.py --lint-facts` and fix all **errors** to zero (proposed/placeholder
   warnings are expected).
4. STOP and summarize the registry for the owner's **Gate G0** review — do not let any
   downstream phase cite a claim until the owner confirms it.
