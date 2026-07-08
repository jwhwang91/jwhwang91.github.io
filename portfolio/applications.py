from __future__ import annotations

import datetime
import json
import re

import jsonschema
import yaml

from .content import load_yaml
from .facts import Violation
from .jd import jd_sha256, mine_candidates, scan_jd, validate_parsed
from .paths import Paths, rel_to_root
from .taxonomy import Taxonomy

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
