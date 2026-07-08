"""Legacy CLI compatibility after the package split.

Every legacy flag must still work post-split, and the previously-silent drop of a
typo'd overlay id must now fail loudly. Runs against a tmp-scoped Paths so the
real repo dist/ and Applications/ are never touched.
"""
import dataclasses

import pytest

from portfolio.cli import main
from portfolio.paths import default_paths


def _scoped(tmp_path):
    return dataclasses.replace(
        default_paths(),
        dist=tmp_path / "dist",
        applications=tmp_path / "Applications",
    )


def test_bare_invocation_builds_site(tmp_path):
    paths = _scoped(tmp_path)
    main([], paths=paths)
    assert (paths.dist / "index.html").exists()
    assert (paths.dist / "standalone.html").exists()


def test_list_variants(tmp_path, capsys):
    main(["--list-variants"], paths=_scoped(tmp_path))
    out = capsys.readouterr().out
    assert "adas-controls" in out
    assert "software-ai" in out


def test_insights_empty(tmp_path, capsys):
    # tmp Applications/ is empty -> the no-results branch
    main(["--insights"], paths=_scoped(tmp_path))
    assert "No results yet" in capsys.readouterr().out


def test_variant_build(tmp_path):
    paths = _scoped(tmp_path)
    main(["--variant", "adas-controls"], paths=paths)
    resume = paths.applications / "adas-controls" / "resume.html"
    assert resume.exists()
    html = resume.read_text(encoding="utf-8")
    # adas-controls sets `software: {include: []}` -> the software spine is HIDDEN.
    # (Guards the include: [] vs include-omitted distinction against a falsy-vs-None
    # refactor that would silently un-hide software onto an employer-facing resume.)
    for sw in ("deckflip", "decisioncanvas", "voiceprint"):
        assert sw not in html, sw
    # ...while experiences + toolchains (include omitted) still render.
    assert "hmc-adas" in html
    assert "e2e-xcp-bypass" in html


def test_all_variants_build(tmp_path):
    paths = _scoped(tmp_path)
    main(["--all-variants"], paths=paths)
    adas = (paths.applications / "adas-controls" / "resume.html").read_text(encoding="utf-8")
    swai = (paths.applications / "software-ai" / "resume.html").read_text(encoding="utf-8")
    # Assert the hide/keep distinction in BOTH directions on real shipped variants:
    assert "deckflip" not in adas          # adas-controls hides software (include: [])
    assert "deckflip" in swai              # software-ai keeps software (omitted)
    assert "e2e-xcp-bypass" in adas        # adas-controls keeps toolchains (omitted)
    assert "e2e-xcp-bypass" not in swai    # software-ai hides toolchains (include: [])


def test_new_variant_scaffolds_all_files(tmp_path):
    # Also proves the pre-existing --new-variant crash (KeyError on the literal
    # "{include: []}" brace under str.format) is fixed by the file+replace scaffold.
    paths = _scoped(tmp_path)
    main(["--new-variant", "probe-app"], paths=paths)
    folder = paths.applications / "probe-app"
    for f in ("jd.txt", "overlay.yaml", "notes.md", "result.md"):
        assert (folder / f).exists(), f

    overlay = (folder / "overlay.yaml").read_text(encoding="utf-8")
    assert "probe-app" in overlay                    # {name} substituted
    assert "software: {include: []}" in overlay      # literal YAML brace preserved
    assert "{name}" not in overlay                   # no leftover token


def test_typod_include_id_fails_loudly(tmp_path):
    paths = _scoped(tmp_path)
    app = paths.applications / "typo-app"
    app.mkdir(parents=True)
    (app / "overlay.yaml").write_text(
        "experiences:\n  include: [hmc-adass]\n", encoding="utf-8"
    )
    with pytest.raises(ValueError) as excinfo:
        main(["--variant", "typo-app"], paths=paths)
    msg = str(excinfo.value)
    assert "hmc-adass" in msg          # names the offending id
    assert "hmc-adas" in msg           # nearest-match suggestion


def test_typod_override_id_fails_loudly(tmp_path):
    paths = _scoped(tmp_path)
    app = paths.applications / "typo-ov"
    app.mkdir(parents=True)
    (app / "overlay.yaml").write_text(
        "experiences:\n  overrides:\n    hmc-adazz:\n      hook: x\n", encoding="utf-8"
    )
    with pytest.raises(ValueError) as excinfo:
        main(["--variant", "typo-ov"], paths=paths)
    assert "hmc-adazz" in str(excinfo.value)


def test_missing_variant_fails_loudly(tmp_path):
    # Phase 1 deliverable: "missing files raise with file+key context" — an absent
    # overlay must error (not silently emit a full-backbone resume).
    paths = _scoped(tmp_path)
    with pytest.raises(FileNotFoundError) as excinfo:
        main(["--variant", "no-such-app"], paths=paths)
    msg = str(excinfo.value)
    assert "no-such-app" in msg          # names the missing variant
    assert "--new-variant" in msg        # points at the scaffold command
    assert not (paths.applications / "no-such-app" / "resume.html").exists()


def test_load_yaml_missing_file_raises(tmp_path):
    from portfolio.content import load_yaml

    with pytest.raises(FileNotFoundError) as excinfo:
        load_yaml(tmp_path / "nope.yaml")
    msg = str(excinfo.value)
    assert "Missing context file" in msg
    assert "nope.yaml" in msg


def test_insights_scoreboard_classifies(tmp_path, capsys):
    # Drives the real inference path (parse_result + ats_passed + scoreboard render),
    # which the empty-tree test never reaches.
    paths = _scoped(tmp_path)

    def app(name, body):
        d = paths.applications / name
        d.mkdir(parents=True)
        (d / "result.md").write_text(body, encoding="utf-8")

    app("pass-explicit", "ATS: pass\nStatus: applied\n")
    app("fail-explicit", "ATS: fail\nStatus: rejected\nStage reached: ATS/early screen\n")
    app("pass-inferred", "Status: screening\n")                        # via _HUMAN_STATUSES
    app("fail-inferred", "Status: rejected\nStage reached: ATS auto knockout\n")
    app("unknown", "Status: applied\n")

    main(["--insights"], paths=paths)
    out = capsys.readouterr().out
    assert "Applications: 5" in out
    assert "ATS-pass (reached a human): 2/4" in out   # 2 pass of 4 known
    assert "(+1 unknown)" in out


def test_result_fields_match_scaffold():
    # RESULT_FIELDS is the single source of truth; the scaffold result.md must
    # carry a label line for each (guards against silent field drop / drift).
    from portfolio.tracking import RESULT_FIELDS

    scaffold = (default_paths().scaffold / "result.md").read_text(encoding="utf-8").lower()
    for field in RESULT_FIELDS:
        assert f"{field}:" in scaffold, field
