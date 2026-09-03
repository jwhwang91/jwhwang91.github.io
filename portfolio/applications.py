from __future__ import annotations

import datetime
import json
import re

import jsonschema
import yaml

from .classify import (SUPPORT_RANK, JoinIndex, classify_keywords, location_knockouts,
                       pre_resume_verdict, render_gap_report, render_portfolio_plan)
from .content import load_yaml
from .facts import Violation, load_registry
from .jd import jd_sha256, mine_candidates, scan_jd, validate_parsed
from .paths import Paths, rel_to_root
from .taxonomy import Taxonomy

_TIER_RANK = {"exact": 0, "equivalent": 1, "related": 2}

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _today() -> str:
    return datetime.date.today().isoformat()


def _dump(path, doc) -> None:
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=4096), encoding="utf-8")


def _jd_schema(paths: Paths) -> dict:
    return json.loads((paths.format_dir / "schemas" / "jd_parsed.schema.json").read_text(encoding="utf-8"))


def new_application(paths: Paths, slug: str, company: str = "", role: str = "",
                    url: str = "", positioning: str = "") -> "object":
    """Scaffold Applications/<slug>/ for the new pipeline (application.yaml + jd.txt + notes.md)."""
    if not SLUG_RE.match(slug):
        raise ValueError(f"slug must be kebab-case [a-z0-9-]+, got {slug!r}")
    folder = paths.applications / slug
    if folder.exists():
        raise FileExistsError(f"application already exists: {folder}")
    folder.mkdir(parents=True)

    today = _today()
    app = {
        "schema": "application/v1",
        "id": slug,
        "company": company or "",
        "role_title": role or "",
        "positioning": positioning or "",
        "req_url": url or "",
        "status": "draft",
        "created": today,
        "jd_sha256": None,
        "status_history": [{"status": "draft", "at": today}],
    }
    _dump(folder / "application.yaml", app)
    (folder / "jd.txt").write_text("", encoding="utf-8")

    notes_tpl = paths.scaffold / "notes.md"
    notes = notes_tpl.read_text(encoding="utf-8").replace("{name}", slug) if notes_tpl.exists() else f"# Notes - {slug}\n"
    (folder / "notes.md").write_text(notes, encoding="utf-8")
    return folder


def _advance_status(folder, status: str) -> None:
    app_path = folder / "application.yaml"
    if not app_path.exists():
        return
    app = load_yaml(app_path)
    if app.get("status") != status:
        app["status"] = status
        app.setdefault("status_history", []).append({"status": status, "at": _today()})
        _dump(app_path, app)


def jd_parse(paths: Paths, slug: str) -> int:
    """Deterministic pass: segment + taxonomy scan + mine candidates; stamp the jd
    hash and write the LLM prompt. The LLM step (/jd-parse) writes jd.parsed.yaml."""
    folder = paths.applications / slug
    jd = folder / "jd.txt"
    if not jd.exists() or not jd.read_text(encoding="utf-8").strip():
        raise FileNotFoundError(f"jd.txt is missing or empty: {jd} — paste the job description first")

    text = jd.read_text(encoding="utf-8")
    tax = Taxonomy.load(paths)
    hits = scan_jd(text, tax)
    candidates = mine_candidates(text, tax)
    sha = jd_sha256(text)

    scan_doc = {
        "jd_sha256": sha,
        "hits": [{"term": h.term_id, "alias": h.alias, "tier": h.tier, "block": h.block, "count": h.count} for h in hits],
        "unknown_candidates": candidates,
    }
    _dump(folder / "jd.scan.yaml", scan_doc)

    app_path = folder / "application.yaml"
    if app_path.exists():
        app = load_yaml(app_path)
        app["jd_sha256"] = sha
        _dump(app_path, app)

    (folder / "jd_parse.prompt.md").write_text(_assemble_prompt(paths, slug, text, scan_doc), encoding="utf-8")

    print(f"Deterministic scan -> {rel_to_root(folder / 'jd.scan.yaml', paths.root)}: "
          f"{len(hits)} taxonomy hits, {len(candidates)} unknown candidates.")
    print(f"Next: run  /jd-parse {slug}  in Claude Code (it reads Format/prompts/jd_parse.md and")
    print(f"      writes {slug}/jd.parsed.yaml). Then:  python main.py jd confirm {slug}")
    return 0


def _assemble_prompt(paths: Paths, slug: str, jd_text: str, scan: dict) -> str:
    contract = paths.format_dir / "prompts" / "jd_parse.md"
    head = contract.read_text(encoding="utf-8") if contract.exists() else "# jd_parse contract missing"
    hits = "\n".join(f"  - {h['term']} ({h['tier']}) in {h['block']} x{h['count']}" for h in scan["hits"]) or "  (none)"
    cands = "\n".join(f"  - {c['candidate']} [{c['kind']}] x{c['count']}" for c in scan["unknown_candidates"]) or "  (none)"
    return (f"{head}\n\n---\n\n# Application: {slug}\n\n"
            f"## Deterministic scan (taxonomy hits — the LLM must not drop requirements-block hits)\n{hits}\n\n"
            f"## Unknown candidates (consider new_term proposals)\n{cands}\n\n"
            f"## jd.txt (verbatim — every quote you emit must be a substring of this)\n\n{jd_text}\n")


def _confirm_table(parsed: dict) -> None:
    print(f"\nParse for {parsed.get('company', '?')} — {parsed.get('role_title', '?')} "
          f"({parsed.get('seniority', '?')}, {parsed.get('role_type', '?')})")
    print(f"  {'term':28} {'req':10} quote")
    for kw in parsed.get("keywords", []) or []:
        term = kw.get("term") or ("new:" + (kw.get("new_term") or {}).get("canonical", "?"))
        print(f"  {term[:27]:28} {kw.get('requirement', '?'):10} {kw.get('quote', '')[:70]}")
    for ko in parsed.get("knockouts", []) or []:
        print(f"  ! KNOCKOUT [{ko.get('type')}]: {ko.get('quote', '')[:70]}")


def jd_confirm(paths: Paths, slug: str) -> int:
    """Gate G1: validate jd.parsed.yaml (schema + verbatim quotes + term existence),
    show the confirm table, stamp confirmed:true, advance status -> parsed."""
    folder = paths.applications / slug
    parsed_path = folder / "jd.parsed.yaml"
    if not parsed_path.exists():
        raise FileNotFoundError(f"{parsed_path} missing — run /jd-parse {slug} in Claude Code first")

    parsed = load_yaml(parsed_path)
    jd_text = (folder / "jd.txt").read_text(encoding="utf-8")
    tax = Taxonomy.load(paths)

    violations: list[Violation] = []
    try:
        jsonschema.validate(parsed, _jd_schema(paths))
    except jsonschema.ValidationError as e:
        violations.append(Violation("error", f"schema:{'/'.join(map(str, e.absolute_path))}", e.message))
    else:
        violations += validate_parsed(parsed, jd_text, tax)

    errors = [v for v in violations if v.level == "error"]
    for v in violations:
        print(v)
    if errors:
        print(f"\njd confirm FAILED: {len(errors)} error(s) — fix jd.parsed.yaml and retry.")
        return 1

    _confirm_table(parsed)
    parsed["confirmed"] = True
    _dump(parsed_path, parsed)
    _advance_status(folder, "parsed")
    print(f"\nConfirmed (Gate G1). Status -> parsed.")
    return 0


# ---------------------------------------------------------------------------
# match / match confirm (Gate G2) — support classification against the registry
# ---------------------------------------------------------------------------

def _schema_json(paths: Paths, name: str) -> dict:
    return json.loads((paths.format_dir / "schemas" / name).read_text(encoding="utf-8"))


def _cache_path(paths: Paths):
    return paths.private / "keyword_map.yaml"


def _load_cache(paths: Paths) -> dict:
    p = _cache_path(paths)
    return (load_yaml(p).get("entries") if p.exists() else {}) or {}


def _append_cache(paths: Paths, classifications: list[dict]) -> None:
    p = _cache_path(paths)
    p.parent.mkdir(parents=True, exist_ok=True)
    entries = _load_cache(paths)
    for c in classifications:
        entries[c["term"]] = {"support": c["support"], "claim_ids": c.get("claim_ids", []), "confirmed_at": _today()}
    _dump(p, {"entries": entries})


def _load_candidate_profile(paths: Paths):
    p = paths.context / "candidate_profile.yaml"
    if not p.exists():
        return None
    prof = load_yaml(p)
    try:
        jsonschema.validate(prof, _schema_json(paths, "candidate_profile.schema.json"))
    except jsonschema.ValidationError:
        # fail-closed: a malformed profile must NOT silently disable knockout checks
        print("  WARNING: Context/candidate_profile.yaml is malformed — knockout checks skipped.")
        return None
    return prof


def _knockouts_with_location(folder, doc: dict, profile) -> list[dict]:
    """The JD's own knockouts plus any location knockout derived from the parsed
    `location_policy`. Parsers routinely emit `knockouts: []` while recording an
    onsite policy, so without this the location branch of the knockout check would
    never see anything to judge. Deduped on (type, quote) so re-running
    `match confirm` cannot stack duplicates."""
    knockouts = list(doc.get("knockouts") or [])
    parsed_path = folder / "jd.parsed.yaml"
    parsed = load_yaml(parsed_path) if parsed_path.exists() else {}
    seen = {(k.get("type"), k.get("quote")) for k in knockouts if isinstance(k, dict)}
    for ko in location_knockouts(parsed.get("location_policy"), profile):
        if (ko["type"], ko["quote"]) not in seen:
            knockouts.append(ko)
    return knockouts


def _require_confirmed_parse(folder):
    parsed_path = folder / "jd.parsed.yaml"
    if not parsed_path.exists():
        raise FileNotFoundError(f"{parsed_path} missing — run /jd-parse then `jd confirm` first")
    parsed = load_yaml(parsed_path)
    if not parsed.get("confirmed"):
        raise ValueError(f"jd.parsed.yaml is not confirmed — run: python main.py jd confirm {folder.name}")
    return parsed


def _tiers(jd_text: str, taxonomy: Taxonomy) -> dict[str, str]:
    tiers: dict[str, str] = {}
    for h in scan_jd(jd_text, taxonomy):
        if h.term_id not in tiers or _TIER_RANK[h.tier] < _TIER_RANK[tiers[h.term_id]]:
            tiers[h.term_id] = h.tier
    return tiers


def match(paths: Paths, slug: str) -> int:
    """Classify JD keywords against the confirmed registry (cache -> registry join),
    queueing only unresolved new_terms for the LLM."""
    from collections import Counter

    folder = paths.applications / slug
    parsed = _require_confirmed_parse(folder)
    jd_text = (folder / "jd.txt").read_text(encoding="utf-8")
    tax = Taxonomy.load(paths)
    index = JoinIndex(load_registry(paths), tax)

    resolved, queue = classify_keywords(parsed.get("keywords", []) or [], _tiers(jd_text, tax), index, _load_cache(paths))
    doc = {
        "schema": "match/v1", "application": slug, "jd_sha256": jd_sha256(jd_text),
        "classifications": resolved, "queue": queue,
        "knockouts": parsed.get("knockouts", []) or [], "confirmed": False,
    }
    _dump(folder / "match.yaml", doc)

    counts = Counter(c["support"] for c in resolved)
    print(f"Classified {len(resolved)} keywords: " + ", ".join(f"{k}:{v}" for k, v in sorted(counts.items())))
    if queue:
        (folder / "jd_match.prompt.md").write_text(
            f"# jd-match queue for {slug}\n\nClassify these unresolved new_terms against the registry, "
            f"then edit match.yaml:\n\n" + "\n".join(f"- {q.get('new_term', {}).get('canonical', '?')}: {q.get('quote', '')}" for q in queue),
            encoding="utf-8")
        print(f"{len(queue)} unresolved new_term(s) -> run /jd-match {slug} in Claude Code, then edit match.yaml.")
    print(f"Next: review, then  python main.py match confirm {slug}")
    return 0


def match_confirm(paths: Paths, slug: str) -> int:
    """Gate G2: validate classifications, compute the pre-resume verdict, cache the
    confirmations, render gap_report.md + portfolio_plan.md, advance status."""
    folder = paths.applications / slug
    match_path = folder / "match.yaml"
    if not match_path.exists():
        raise FileNotFoundError(f"{match_path} missing — run: python main.py match {slug}")

    doc = load_yaml(match_path)
    reg = load_registry(paths)
    index = JoinIndex(reg, Taxonomy.load(paths))
    confirmed_ids = {c["id"] for c in reg.citable()}
    classifications = doc.get("classifications", []) or []

    errors = []
    try:
        jsonschema.validate(doc, _schema_json(paths, "match.schema.json"))
    except jsonschema.ValidationError as e:
        errors.append(f"schema:{'/'.join(map(str, e.absolute_path))}: {e.message}")
    tax = index.taxonomy
    for c in classifications:
        for cid in c.get("claim_ids", []) or []:
            if cid not in confirmed_ids:
                errors.append(f"'{c.get('term')}' cites non-confirmed claim '{cid}'")
        if c.get("support") == "direct" and not c.get("claim_ids"):
            errors.append(f"direct classification '{c.get('term')}' has no claim_ids")
        # re-gate an LLM/edited classification: declared support may not EXCEED what
        # the registry join actually supports (anti-overclaim, MASTER_PLAN §4.3).
        if c.get("term") in tax.by_id:
            derived = index.classify(c["term"], c.get("matched_tier", "related"))
            if SUPPORT_RANK.get(c.get("support"), 0) > SUPPORT_RANK.get(derived["support"], 0):
                errors.append(f"'{c.get('term')}' declares {c.get('support')} but the registry "
                              f"join supports only {derived['support']}")
    if doc.get("queue"):
        errors.append(f"{len(doc['queue'])} unresolved new_term(s) still in queue — classify + move into classifications first")
    if errors:
        for e in errors:
            print(f"[error] {e}")
        print(f"\nmatch confirm FAILED: {len(errors)} error(s).")
        return 1

    profile = _load_candidate_profile(paths)
    knockouts = _knockouts_with_location(folder, doc, profile)
    verdict = pre_resume_verdict(classifications, knockouts, profile)
    _append_cache(paths, classifications)

    app = load_yaml(folder / "application.yaml") if (folder / "application.yaml").exists() else {}
    positioning = app.get("positioning", "")
    (folder / "gap_report.md").write_text(
        render_gap_report(slug, classifications, verdict, knockouts, index, verdict["profile_checked"]),
        encoding="utf-8")
    (folder / "portfolio_plan.md").write_text(render_portfolio_plan(slug, positioning, classifications), encoding="utf-8")

    doc["knockouts"] = knockouts
    doc["pre_resume"] = verdict
    doc["confirmed"] = True
    _dump(match_path, doc)
    _advance_status(folder, "matched")

    print(f"Pre-resume verdict: {verdict['verdict']}  (unsupported-must-have ratio U={verdict['U']})")
    if not verdict["profile_checked"]:
        print("  NOTE: Context/candidate_profile.yaml absent — knockout checks skipped (create it to enable).")
    if verdict["knockout_hits"]:
        print(f"  AUTO-KNOCKOUT: {', '.join(str(h) for h in verdict['knockout_hits'])} — see gap_report.md")
    if verdict["missing_must_haves"]:
        print(f"  Missing must-haves: {', '.join(verdict['missing_must_haves'])}")
    print(f"Wrote gap_report.md + portfolio_plan.md. Status -> matched (Gate G2).")
    return 0


def validate_stage(paths: Paths, slug: str, stage: str) -> int:
    """`validate --stage jd|match|all` — schema + registry-reference checks."""
    folder = paths.applications / slug
    tax = Taxonomy.load(paths)
    errors: list[str] = []

    def check_schema(path, schema_name):
        if not path.exists():
            return [f"{path.name} missing"]
        try:
            jsonschema.validate(load_yaml(path), _schema_json(paths, schema_name))
            return []
        except jsonschema.ValidationError as e:
            return [f"{path.name}: {e.message}"]

    if stage in ("jd", "all"):
        errors += check_schema(folder / "jd.parsed.yaml", "jd_parsed.schema.json")
        if (folder / "jd.parsed.yaml").exists() and (folder / "jd.txt").exists():
            errors += [v.message for v in validate_parsed(
                load_yaml(folder / "jd.parsed.yaml"), (folder / "jd.txt").read_text(encoding="utf-8"), tax)
                if v.level == "error"]
    if stage in ("match", "all"):
        errors += check_schema(folder / "match.yaml", "match.schema.json")
        if (folder / "match.yaml").exists():
            cids = {c["id"] for c in load_registry(paths).citable()}
            for c in load_yaml(folder / "match.yaml").get("classifications", []) or []:
                for cid in c.get("claim_ids", []) or []:
                    if cid not in cids:
                        errors.append(f"match.yaml: unknown/unconfirmed claim '{cid}'")
    if stage in ("resume", "all"):
        errors += check_schema(folder / "resume.yaml", "resume.schema.json")
        if (folder / "resume.yaml").exists():
            reg = load_registry(paths)
            cids = {c["id"] for c in reg.citable()}
            titles = reg.approved_titles()
            resume = load_yaml(folder / "resume.yaml")
            if resume.get("role_title") and resume["role_title"] not in titles:
                errors.append(f"resume.yaml: role_title '{resume['role_title']}' not in positioning_titles.yaml (Q19)")
            for sec in ("summary",):
                for b in resume.get(sec, []) or []:
                    for cid in b.get("claims", []) or []:
                        if cid not in cids:
                            errors.append(f"resume.yaml: bullet cites non-confirmed claim '{cid}'")
            for grp in ("experience", "projects"):
                for e in resume.get(grp, []) or []:
                    for b in e.get("bullets", []) or []:
                        for cid in b.get("claims", []) or []:
                            if cid not in cids:
                                errors.append(f"resume.yaml: bullet cites non-confirmed claim '{cid}'")

    for e in errors:
        print(f"[error] {e}")
    print(f"\nvalidate --stage {stage}: {len(errors)} error(s).")
    return 1 if errors else 0


# ---------------------------------------------------------------------------
# render / gate / pdfcheck (Phase 5)
# ---------------------------------------------------------------------------

def render_resume(paths: Paths, slug: str, style: str = "ats") -> int:
    """Render resume.yaml -> out/resume_ats.{txt,html,md}, then auto-run the gate."""
    from .resume_render import build_context, render_html, render_md, render_txt
    from .site import make_env

    folder = paths.applications / slug
    resume_path = folder / "resume.yaml"
    if not resume_path.exists():
        raise FileNotFoundError(f"{resume_path} missing — run /resume-plan {slug} to draft it")
    resume = load_yaml(resume_path)
    try:
        jsonschema.validate(resume, _schema_json(paths, "resume.schema.json"))
    except jsonschema.ValidationError as e:
        raise ValueError(f"resume.yaml schema error at {'/'.join(map(str, e.absolute_path))}: {e.message}")

    reg = load_registry(paths)
    ctx = build_context(paths, resume, reg)
    out = folder / "out"
    out.mkdir(parents=True, exist_ok=True)
    resume_txt = render_txt(ctx)
    (out / "resume_ats.txt").write_text(resume_txt, encoding="utf-8")
    (out / "resume_ats.md").write_text(render_md(ctx), encoding="utf-8")
    (out / "resume_ats.html").write_text(render_html(make_env(paths), ctx), encoding="utf-8")
    print(f"Rendered {rel_to_root(out, paths.root)}/resume_ats.{{txt,html,md}}")
    return _run_gate(paths, slug, resume, resume_txt)


def _run_gate(paths: Paths, slug: str, resume: dict, resume_txt: str) -> int:
    from .gate import (build_audit, build_gate_feedback, evaluate,
                       render_changes_md, render_checklist_md, render_gate_md)

    folder = paths.applications / slug
    reg = load_registry(paths)
    tax = Taxonomy.load(paths)
    policy = load_yaml(paths.context / "facts" / "phrasing_policy.yaml")
    match_path = folder / "match.yaml"
    if not match_path.exists() or not load_yaml(match_path).get("confirmed"):
        raise FileNotFoundError(
            f"a confirmed match.yaml is required before gating (else coverage is vacuously 100%) — "
            f"run: python main.py match confirm {slug}")
    classifications = load_yaml(match_path).get("classifications", []) or []

    report, errors = evaluate(resume, resume_txt, classifications, reg, tax, policy, reg.approved_titles())
    out = folder / "out"
    out.mkdir(parents=True, exist_ok=True)
    _dump(folder / "gate_report.yaml", report)
    (folder / "gate_report.md").write_text(render_gate_md(report), encoding="utf-8")
    (folder / "checklist.md").write_text(render_checklist_md(report), encoding="utf-8")
    (folder / "changes.md").write_text(render_changes_md(resume, reg), encoding="utf-8")
    (folder / "audit.json").write_text(json.dumps(build_audit(resume, reg, policy), indent=2), encoding="utf-8")

    app_path = folder / "application.yaml"
    if app_path.exists():
        app = load_yaml(app_path)
        app["gate"] = {"verdict": report["verdict"], "recommendation": report["recommendation"],
                       "must_have_coverage": report["must_have_coverage"], "risk_acknowledged": (app.get("gate") or {}).get("risk_acknowledged", False)}
        _dump(app_path, app)

    if report["verdict"] == "FAIL":
        _dump(folder / "gate_feedback.yaml", build_gate_feedback(report, tax))
        for f in ("resume_ats.txt", "resume_ats.html", "resume_ats.md"):
            (out / f).unlink(missing_ok=True)
        print(f"Gate FAILED ({len(errors)} error(s)). See gate_report.md; wrote gate_feedback.yaml.")
        print(f"Run /resume-plan {slug} (it reads gate_feedback), then: python main.py render {slug}")
        return 2

    _advance_status(folder, "gated")
    if report["verdict"] == "HIGH_RISK":
        print(f"Gate HIGH_RISK (coverage {report['must_have_coverage']}, U={report['unsupported_ratio']}): "
              f"recommendation={report['recommendation']} — DO NOT apply without acknowledging the risk. Status -> gated.")
    else:
        print(f"Gate PASS: coverage {report['must_have_coverage']}, U={report['unsupported_ratio']}, "
              f"recommendation={report['recommendation']}. Status -> gated.")
    return 0


def gate(paths: Paths, slug: str, verify_only: bool = False) -> int:
    """Re-run the gate on the already-rendered out/resume_ats.txt."""
    folder = paths.applications / slug
    txt_path = folder / "out" / "resume_ats.txt"
    if not txt_path.exists():
        raise FileNotFoundError(f"{txt_path} missing — run: python main.py render {slug}")
    resume = load_yaml(folder / "resume.yaml")
    return _run_gate(paths, slug, resume, txt_path.read_text(encoding="utf-8"))


def pdfcheck(paths: Paths, slug: str) -> int:
    """Hard block a PDF whose text layer does not match resume_ats.txt (>=0.98)."""
    import difflib

    folder = paths.applications / slug
    pdf = folder / "out" / "resume_final.pdf"
    txt_path = folder / "out" / "resume_ats.txt"
    if not txt_path.exists():
        raise FileNotFoundError(f"{txt_path} missing — run: python main.py render {slug}")
    if not pdf.exists():
        raise FileNotFoundError(f"{pdf} missing — open resume_ats.html and Save-as-PDF (never 'Microsoft Print to PDF')")
    try:
        from pypdf import PdfReader
    except Exception:
        print("pypdf not installed — cannot verify PDF text layer.")
        return 1

    try:
        extracted = "".join((p.extract_text() or "") for p in PdfReader(str(pdf)).pages)
    except Exception:
        extracted = ""  # unparseable / image-only PDF -> no text layer -> will FAIL below
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    ratio = difflib.SequenceMatcher(None, norm(extracted), norm(txt_path.read_text(encoding="utf-8"))).ratio()
    if ratio >= 0.98:
        print(f"pdfcheck PASS (text-layer similarity {ratio:.3f}).")
        return 0
    print(f"pdfcheck FAIL (similarity {ratio:.3f} < 0.98) — the PDF has no usable text layer. "
          "Re-export via browser 'Save as PDF'.")
    return 1


def pack_interview(paths: Paths, slug: str) -> int:
    """Validate the LLM-written prep/interview_pack.yaml (schema + claim refs +
    partial->danger + digit checks + forbidden phrasing) and render it to markdown."""
    from .prep import render_pack_md, validate_pack

    folder = paths.applications / slug
    pack_path = folder / "prep" / "interview_pack.yaml"
    if not pack_path.exists():
        raise FileNotFoundError(f"{pack_path} missing — run /interview-pack {slug} in Claude Code first")
    pack = load_yaml(pack_path)

    try:
        jsonschema.validate(pack, _schema_json(paths, "interview_pack.schema.json"))
    except jsonschema.ValidationError as e:
        print(f"[error] schema:{'/'.join(map(str, e.absolute_path))}: {e.message}")
        print("\npack interview FAILED: schema violation.")
        return 1

    reg = load_registry(paths)
    match_path = folder / "match.yaml"
    if not match_path.exists() or not load_yaml(match_path).get("confirmed"):
        raise FileNotFoundError(
            f"a confirmed match.yaml is required (else the partial->danger-question net is vacuous) — "
            f"run: python main.py match confirm {slug}")
    match = load_yaml(match_path)
    policy = load_yaml(paths.context / "facts" / "phrasing_policy.yaml")
    violations = validate_pack(pack, match, reg, policy)
    for v in violations:
        print(v)
    if [v for v in violations if v.level == "error"]:
        print(f"\npack interview FAILED: {len([v for v in violations if v.level == 'error'])} error(s).")
        return 1

    (folder / "prep").mkdir(parents=True, exist_ok=True)
    (folder / "prep" / "interview_pack.md").write_text(render_pack_md(pack), encoding="utf-8")
    print(f"Interview pack valid -> {rel_to_root(folder / 'prep' / 'interview_pack.md', paths.root)}")
    return 0


def pack_coding(paths: Paths, slug: str) -> int:
    """Validate the LLM-written prep/coding_pack.yaml against the committed bank
    (all ids in bank, count 20-40, difficulty mix within the format band) and render it."""
    from .prep import render_coding_pack_md, validate_coding_pack

    folder = paths.applications / slug
    pack_path = folder / "prep" / "coding_pack.yaml"
    if not pack_path.exists():
        raise FileNotFoundError(f"{pack_path} missing — run /coding-pack {slug} in Claude Code first")
    bank_path = paths.context / "prep" / "coding_bank.yaml"
    if not bank_path.exists():
        raise FileNotFoundError(f"{bank_path} missing — the coding problem bank must be committed first")
    pack, bank = load_yaml(pack_path), load_yaml(bank_path)

    try:
        jsonschema.validate(pack, _schema_json(paths, "coding_pack.schema.json"))
    except jsonschema.ValidationError as e:
        print(f"[error] schema:{'/'.join(map(str, e.absolute_path))}: {e.message}")
        print("\npack coding FAILED: schema violation.")
        return 1

    violations = validate_coding_pack(pack, bank)
    for v in violations:
        print(v)
    if [v for v in violations if v.level == "error"]:
        print(f"\npack coding FAILED: {len([v for v in violations if v.level == 'error'])} error(s).")
        return 1

    (folder / "prep").mkdir(parents=True, exist_ok=True)
    (folder / "prep" / "coding_pack.md").write_text(render_coding_pack_md(pack, bank), encoding="utf-8")
    print(f"Coding pack valid -> {rel_to_root(folder / 'prep' / 'coding_pack.md', paths.root)}")
    return 0
