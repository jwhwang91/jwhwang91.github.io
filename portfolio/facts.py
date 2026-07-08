from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

from .content import load_yaml
from .paths import Paths

# Sentinel for a claim whose statement/quote is not yet sourceable and awaits
# owner confirmation at Gate G0. A <placeholder> quote skips the verbatim check.
PLACEHOLDER = "<placeholder>"


@dataclass
class Violation:
    level: str          # "error" | "warning"
    where: str          # file:key context
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.where}: {self.message}"


@dataclass
class Registry:
    employers: dict[str, Any]
    education: dict[str, Any]
    credentials: dict[str, Any]
    policy: dict[str, Any]
    titles: dict[str, Any]
    claims: list[dict[str, Any]] = field(default_factory=list)
    claims_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    anchors: set[str] = field(default_factory=set)

    def citable(self) -> list[dict[str, Any]]:
        """Only confirmed claims may be cited by a resume (proposed/retired never)."""
        return [c for c in self.claims if c.get("status") == "confirmed"]

    def approved_titles(self) -> set[str]:
        out: set[str] = set()
        for titles in self.titles.get("tracks", {}).values():
            out.update(titles)
        return out


def _norm(text: str) -> str:
    """Whitespace-normalize for the verbatim source-quote substring check."""
    return re.sub(r"\s+", " ", text).strip()


def _schema(paths: Paths, name: str) -> dict[str, Any]:
    return json.loads((paths.format_dir / "schemas" / name).read_text(encoding="utf-8"))


def _facts_dir(paths: Paths) -> Path:
    return paths.context / "facts"


def _project_ids(paths: Paths) -> set[str]:
    """Anchor targets for sw-/tc- claims come from the presentation project files."""
    ids: set[str] = set()
    for fname in ("software_projects.yaml", "toolchain_projects.yaml"):
        p = paths.context / fname
        if p.exists():
            for proj in load_yaml(p).get("projects", []):
                if proj.get("id"):
                    ids.add(proj["id"])
    return ids


def load_registry(paths: Paths) -> Registry:
    """Load the fact registry (no validation). Missing optional files -> empty."""
    facts = _facts_dir(paths)
    employers_doc = load_yaml(facts / "employers.yaml") if (facts / "employers.yaml").exists() else {}
    policy = load_yaml(facts / "phrasing_policy.yaml") if (facts / "phrasing_policy.yaml").exists() else {}
    titles = load_yaml(facts / "positioning_titles.yaml") if (facts / "positioning_titles.yaml").exists() else {}

    claims: list[dict[str, Any]] = []
    claims_dir = facts / "claims"
    if claims_dir.exists():
        for cf in sorted(claims_dir.glob("*.yaml")):
            for claim in (load_yaml(cf).get("claims") or []):
                claim["_file"] = str(cf.relative_to(paths.root)) if _under(cf, paths.root) else str(cf)
                claims.append(claim)

    employers = employers_doc.get("employers", {})
    education = employers_doc.get("education", {})
    credentials = employers_doc.get("credentials", {})
    anchors = set(employers) | set(education) | set(credentials) | _project_ids(paths)

    reg = Registry(
        employers=employers,
        education=education,
        credentials=credentials,
        policy=policy,
        titles=titles,
        claims=claims,
        claims_by_id={c["id"]: c for c in claims if "id" in c},
        anchors=anchors,
    )
    return reg


def _under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def validate_registry(paths: Paths) -> list[Violation]:
    """Full validation of Context/facts/**: schema + semantic reference/quote checks.
    Returns a list of Violations (errors + warnings). Empty errors => registry is sound."""
    v: list[Violation] = []
    facts = _facts_dir(paths)

    # --- schema validation of the domain files ---
    for fname, schema_name, key in (
        ("employers.yaml", "employers.schema.json", "employers"),
        ("phrasing_policy.yaml", "phrasing_policy.schema.json", "phrasing_policy"),
        ("positioning_titles.yaml", "positioning_titles.schema.json", "positioning_titles"),
    ):
        fpath = facts / fname
        if not fpath.exists():
            v.append(Violation("error", str(fname), "required facts file is missing"))
            continue
        try:
            jsonschema.validate(load_yaml(fpath), _schema(paths, schema_name))
        except jsonschema.ValidationError as e:
            v.append(Violation("error", f"{fname}:{'/'.join(map(str, e.absolute_path))}", e.message))

    # --- claim files: schema + semantics ---
    claim_schema = _schema(paths, "claim.schema.json")
    reg = load_registry(paths)

    seen_ids: dict[str, str] = {}
    claims_dir = facts / "claims"
    if claims_dir.exists():
        for cf in sorted(claims_dir.glob("*.yaml")):
            rel = str(cf.relative_to(paths.root)) if _under(cf, paths.root) else str(cf)
            try:
                jsonschema.validate(load_yaml(cf), claim_schema)
            except jsonschema.ValidationError as e:
                v.append(Violation("error", f"{rel}:{'/'.join(map(str, e.absolute_path))}", e.message))

    for claim in reg.claims:
        cid = claim.get("id", "<no-id>")
        where = f"{claim.get('_file', '?')}:{cid}"

        # id uniqueness
        if cid in seen_ids:
            v.append(Violation("error", where, f"duplicate claim id (also in {seen_ids[cid]})"))
        else:
            seen_ids[cid] = claim.get("_file", "?")

        # anchor must resolve
        anchor = claim.get("anchor")
        if anchor and anchor not in reg.anchors:
            v.append(Violation("error", where, f"unknown anchor '{anchor}' (not an employer/education/credential/project id)"))

        # confirmed => evidence required
        if claim.get("status") == "confirmed" and not claim.get("evidence"):
            v.append(Violation("error", where, "confirmed claim must carry at least one evidence entry"))

        # verbatim source_quote (the anti-hallucination check)
        sq = claim.get("source_quote") or {}
        quote = (sq.get("quote") or "").strip()
        sfile = sq.get("file")
        if quote and quote != PLACEHOLDER and sfile:
            src = paths.root / sfile
            if not src.exists():
                v.append(Violation("error", where, f"source_quote.file does not exist: {sfile}"))
            elif _norm(quote) not in _norm(src.read_text(encoding="utf-8")):
                v.append(Violation("error", where, f"source_quote is not a verbatim substring of {sfile}"))

        # a proposed claim or placeholder statement is a warning (needs G0), never an error
        if claim.get("status") == "proposed":
            v.append(Violation("warning", where, "proposed claim — not citable until confirmed at Gate G0"))
        if isinstance(claim.get("statement"), str) and PLACEHOLDER in claim["statement"]:
            v.append(Violation("warning", where, "statement contains <placeholder> — owner must supply real content at G0"))

    return v


def sweep_site_consistency(paths: Paths, registry: Registry | None = None) -> list[Violation]:
    """Warn-level Q6 maintenance sweep (MASTER_PLAN §3.7/§12): check that the
    existing Context/*.yaml site files agree with employers.yaml canon. Warn-only
    in v1 — the rich hand-authored detail pages stay authoritative for prose."""
    reg = registry or load_registry(paths)
    v: list[Violation] = []
    exp_file = paths.context / "experiences.yaml"
    if not exp_file.exists():
        return v
    for exp in load_yaml(exp_file).get("experiences", []) or []:
        eid = exp.get("id")
        emp = reg.employers.get(eid)
        if not emp:
            continue
        org = exp.get("organization")
        if org and org not in ([emp.get("organization")] + (emp.get("org_renderings") or [])):
            v.append(Violation("warning", f"experiences.yaml:{eid}", f"organization '{org}' not in employers.yaml renderings"))
        role = exp.get("role")
        if role and role not in ([emp.get("official_title")] + (emp.get("title_renderings") or [])):
            v.append(Violation("warning", f"experiences.yaml:{eid}", f"role '{role}' not in employers.yaml title renderings"))
        m = re.match(r"\s*(\d{4})\.(\d{2})", exp.get("period", "") or "")
        start = (emp.get("period") or {}).get("start")
        if m and start and f"{m.group(1)}-{m.group(2)}" != start:
            v.append(Violation("warning", f"experiences.yaml:{eid}", f"period start {m.group(1)}-{m.group(2)} != employers.yaml {start}"))
    return v
