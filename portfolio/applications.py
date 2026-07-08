from __future__ import annotations

import datetime
import json
import re

import jsonschema
import yaml

from .classify import (JoinIndex, classify_keywords, pre_resume_verdict,
                       render_gap_report, render_portfolio_plan)
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
        pass
    return prof


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
    for c in classifications:
        for cid in c.get("claim_ids", []) or []:
            if cid not in confirmed_ids:
                errors.append(f"'{c.get('term')}' cites non-confirmed claim '{cid}'")
        if c.get("support") == "direct" and not c.get("claim_ids"):
            errors.append(f"direct classification '{c.get('term')}' has no claim_ids")
    if doc.get("queue"):
        errors.append(f"{len(doc['queue'])} unresolved new_term(s) still in queue — classify + move into classifications first")
    if errors:
        for e in errors:
            print(f"[error] {e}")
        print(f"\nmatch confirm FAILED: {len(errors)} error(s).")
        return 1

    profile = _load_candidate_profile(paths)
    verdict = pre_resume_verdict(classifications, doc.get("knockouts", []) or [], profile)
    _append_cache(paths, classifications)

    app = load_yaml(folder / "application.yaml") if (folder / "application.yaml").exists() else {}
    positioning = app.get("positioning", "")
    (folder / "gap_report.md").write_text(
        render_gap_report(slug, classifications, verdict, doc.get("knockouts", []) or [], index, verdict["profile_checked"]),
        encoding="utf-8")
    (folder / "portfolio_plan.md").write_text(render_portfolio_plan(slug, positioning, classifications), encoding="utf-8")

    doc["pre_resume"] = verdict
    doc["confirmed"] = True
    _dump(match_path, doc)
    _advance_status(folder, "matched")

    print(f"Pre-resume verdict: {verdict['verdict']}  (unsupported-must-have ratio U={verdict['U']})")
    if not verdict["profile_checked"]:
        print("  NOTE: Context/candidate_profile.yaml absent — knockout checks skipped (create it to enable).")
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

    for e in errors:
        print(f"[error] {e}")
    print(f"\nvalidate --stage {stage}: {len(errors)} error(s).")
    return 1 if errors else 0
