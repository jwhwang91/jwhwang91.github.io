from __future__ import annotations

import unicodedata
from typing import Any

from .content import load_yaml
from .facts import Registry
from .paths import Paths

# Non-ASCII -> ASCII for the scored plain-text render (score what a worst-case parser sees).
_ASCII = {
    "—": "-", "–": "-", "‒": "-",       # dashes
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "…": "...", "•": "*", "·": "*", "→": "->",
    " ": " ", "≈": "~", "×": "x", "≥": ">=", "≤": "<=",
}

SECTION_ORDER = ["Summary", "Skills", "Experience", "Projects", "Education"]


def to_ascii(text: str) -> str:
    """Faithful transliteration for the scored text — never silently mask an unknown
    glyph, or an excluded term with a non-ASCII char would be invisible to the gate."""
    for uni, asc in _ASCII.items():
        text = text.replace(uni, asc)
    # accented latin (é->e, Bézier->Bezier) + compatibility forms via NFKD, drop marks
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    return "".join(ch if ord(ch) < 128 else "?" for ch in text)


def _period(emp: dict) -> str:
    p = emp.get("period") or {}
    start = (p.get("start") or "").replace("-", ".")
    end = p.get("end")
    end = "Present" if not end else str(end).replace("-", ".")
    return f"{start} - {end}"


def _period_sort_key(registry: Registry, source: str) -> str:
    return ((registry.employers.get(source) or {}).get("period") or {}).get("start") or "0000-00"


def build_context(paths: Paths, resume: dict, registry: Registry) -> dict[str, Any]:
    """Normalize resume.yaml into a render-ready structure (contact + resolved sections)."""
    personal = load_yaml(paths.context / "personal_info.yaml")
    private = load_yaml(paths.private / "personal_private.yaml") if (paths.private / "personal_private.yaml").exists() else {}

    contact = {
        "name": personal.get("display_name") or personal.get("name", ""),
        "email": personal.get("email", ""),
        "phone": private.get("phone", ""),
        "location": personal.get("location", ""),
        "linkedin": (personal.get("linkedin") or {}).get("url", ""),
        "github": (personal.get("github") or {}).get("url", ""),
    }

    def resolve_section(entries):
        out = []
        for e in entries or []:
            emp = registry.employers.get(e["source"]) or {}
            out.append({
                "source": e["source"],
                "organization": emp.get("organization", e["source"]),
                "title": emp.get("official_title", ""),
                "period": _period(emp) if emp else "",
                "bullets": [b.get("text", "") for b in e.get("bullets", []) or []],
            })
        return out

    experience = sorted(resolve_section(resume.get("experience")),
                        key=lambda s: _period_sort_key(registry, s["source"]), reverse=True)
    projects = resolve_section(resume.get("projects"))

    education = []
    if resume.get("education") == "from_registry":
        for ed in registry.education.values():
            education.append({"institute": ed.get("institute", ""), "degree": ed.get("degree", ""),
                              "period": _period(ed), "thesis": ed.get("thesis", "")})
    elif isinstance(resume.get("education"), list):
        education = [{"institute": x, "degree": "", "period": "", "thesis": ""} for x in resume["education"]]

    licenses = []
    for lic_id in (resume.get("extras") or {}).get("licenses", []) or []:
        # extras.licenses holds cert- claim ids; use each claim's verbatim source_quote
        # (the exact license name) so the selection is honored and nothing leaks.
        claim = registry.claims_by_id.get(lic_id)
        if claim:
            name = (claim.get("source_quote") or {}).get("quote") or claim.get("statement", "")
            if name and name != "<placeholder>":
                licenses.append(name)

    return {
        "role_title": resume.get("role_title", ""),
        "contact": contact,
        "summary": [b.get("text", "") for b in resume.get("summary", []) or []],
        "skills": [{"label": s.get("label", ""), "items": s.get("items", [])} for s in resume.get("skills", []) or []],
        "experience": experience,
        "projects": projects,
        "education": education,
        "licenses": licenses,
    }


def render_txt(ctx: dict) -> str:
    """The scored artifact: ASCII plain text, CAPS headings, '- ' bullets."""
    L: list[str] = []
    c = ctx["contact"]
    L.append(c["name"])
    if ctx["role_title"]:
        L.append(ctx["role_title"])
    contact_line = " | ".join(x for x in [c["email"], c["phone"], c["location"], c["linkedin"], c["github"]] if x)
    if contact_line:
        L.append(contact_line)
    L.append("")

    if ctx["summary"]:
        L.append("SUMMARY")
        for t in ctx["summary"]:
            L.append(f"- {t}")
        L.append("")
    if ctx["skills"]:
        L.append("SKILLS")
        for s in ctx["skills"]:
            L.append(f"- {s['label']}: {', '.join(s['items'])}")
        L.append("")
    if ctx["experience"]:
        L.append("EXPERIENCE")
        for e in ctx["experience"]:
            head = " | ".join(x for x in [e["organization"], e["title"], e["period"]] if x)
            L.append(head)
            for b in e["bullets"]:
                L.append(f"- {b}")
        L.append("")
    if ctx["projects"]:
        L.append("PROJECTS")
        for e in ctx["projects"]:
            head = " | ".join(x for x in [e["organization"], e["title"], e["period"]] if x)
            L.append(head)
            for b in e["bullets"]:
                L.append(f"- {b}")
        L.append("")
    if ctx["education"]:
        L.append("EDUCATION")
        for ed in ctx["education"]:
            L.append(" | ".join(x for x in [ed["institute"], ed["degree"], ed["period"]] if x))
        L.append("")
    if ctx["licenses"]:
        L.append("LICENSES")
        L.append("- " + ", ".join(ctx["licenses"]))
        L.append("")

    return to_ascii("\n".join(L).rstrip() + "\n")


def render_md(ctx: dict) -> str:
    L: list[str] = []
    c = ctx["contact"]
    L.append(f"# {c['name']}")
    if ctx["role_title"]:
        L.append(f"**{ctx['role_title']}**")
    contact_line = " | ".join(x for x in [c["email"], c["phone"], c["location"], c["linkedin"], c["github"]] if x)
    if contact_line:
        L.append(contact_line)
    if ctx["summary"]:
        L.append("\n## Summary")
        L += [f"- {t}" for t in ctx["summary"]]
    if ctx["skills"]:
        L.append("\n## Skills")
        L += [f"- **{s['label']}:** {', '.join(s['items'])}" for s in ctx["skills"]]
    for name, key in (("Experience", "experience"), ("Projects", "projects")):
        if ctx[key]:
            L.append(f"\n## {name}")
            for e in ctx[key]:
                L.append(f"### {' | '.join(x for x in [e['organization'], e['title'], e['period']] if x)}")
                L += [f"- {b}" for b in e["bullets"]]
    if ctx["education"]:
        L.append("\n## Education")
        L += [f"- {' | '.join(x for x in [ed['institute'], ed['degree'], ed['period']] if x)}" for ed in ctx["education"]]
    if ctx["licenses"]:
        L.append("\n## Licenses")
        L.append("- " + ", ".join(ctx["licenses"]))
    return "\n".join(L).rstrip() + "\n"


def render_html(env, ctx: dict) -> str:
    return env.get_template("resume_ats.html.j2").render(**ctx)
