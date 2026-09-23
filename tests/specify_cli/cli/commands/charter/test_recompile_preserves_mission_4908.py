"""Red-first regression: charter recompile discards the recorded mission type (#4908).

Root cause (SSOT violation, ``kitty-specs/silent-destructive-write-hardening-01M355VK/``
WP01): ``charter activate``/``deactivate`` and ``charter pack apply --compile``
refresh the derived ``catalog`` section of an already-compiled ``charter.yaml``
via :func:`specify_cli.cli.commands.charter.generate._load_interview_for_generate`
called with ``from_interview=False`` (a #2940 guard so a malformed
``answers.yaml`` cannot abort a recompile) and ``resolved_mission_type=None``
(neither call site threads the project's own recorded mission type through).
Before this fix, that combination fell straight through to the
``resolved_mission = resolved_mission_type or "software-dev"`` literal at
``generate.py:249`` -- so ANY recompile on a non-``software-dev`` project
silently flipped ``catalog.mission`` (and therefore ``catalog.template_set``,
and the resolved reference set) to the wrong mission, reported exit 0, and
wrote no backup.

This test reproduces the flip through the real CLI entry points on an
*established, config-governed* project (``.kittify/config.yaml`` already
carries ``activated_directives`` -- the FR-018 "configured project" state, so
the compiled reference set is config-derived rather than the "no config yet"
all-built-ins convenience default, keeping the before/after reference-count
comparison apples to apples): generate a ``research`` charter
(``charter generate --mission-type research``, the project's genuine
mission-type declaration), then run a single, ordinary ``charter activate
directive 025-boy-scout-rule`` with no ``--mission-type`` flag at all --
exactly the operator action issue #4908 pins. Contract:
``contracts/hardening-contract.md`` WP01 clause (``catalog.mission == M``,
``catalog.template_set == M-default``, ``catalog.references`` superset).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.charter_yaml_io import read_catalog_field, read_catalog_mission
from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.charter.generate import (
    _read_catalog_mission_from_charter_yaml,
    _resolve_recorded_mission_type,
)

pytestmark = [pytest.mark.regression, pytest.mark.integration]

runner = CliRunner()

# Real, stable built-in directive (mirrors the pinning convention already
# established by ``test_activate_recompile_4785.py``'s ``_REAL_DIRECTIVE_STEM``,
# and the exact id the issue's own QA repro names). Deliberately NOT part of
# the seeded ``activated_directives`` baseline below, so activating it is a
# genuine addition (proves the superset clause, not just a no-op re-activate).
_REAL_DIRECTIVE_STEM = "025-boy-scout-rule"
_BASELINE_DIRECTIVE_STEM = "001-architectural-integrity-standard"


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True, capture_output=True)


def _seed_configured_project(repo: Path) -> None:
    """Seed ``.kittify/config.yaml`` as an already-configured (FR-018) project.

    Writing ``activated_directives`` (even a single entry) up front puts the
    project past the "unconfigured -> all-built-ins fallback" bootstrap state
    BEFORE the first compile, so the before/after reference-count comparison
    in the test below isolates the #4908 mission-recompile behavior from the
    orthogonal, correct-by-design FR-018 narrowing that happens the first
    time any project moves from "no activation config at all" to "config
    governs" (a state transition, not a per-recompile regression).
    """
    kittify = repo / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        f"activated_directives:\n- {_BASELINE_DIRECTIVE_STEM}\nactivated_kinds:\n- directives\nmission_type_activations:\n- research\n",
        encoding="utf-8",
    )


def _invoke_generate(repo: Path, *args: str) -> object:
    """Run ``charter generate`` with ``repo`` as cwd.

    ``generate`` resolves its root from ``Path.cwd()``
    (``resolve_charter_write_root``) and ``find_repo_root()`` -- neither
    accepts a ``--repo-root`` option (unlike ``activate``/``pack apply``) --
    so a real ``os.chdir`` round trip is required, mirroring
    ``tests/charter/test_active_languages_idempotency.py``'s
    ``_invoke_generate`` helper.
    """
    old_cwd = os.getcwd()
    try:
        os.chdir(repo)
        return runner.invoke(charter_app, ["generate", *args], catch_exceptions=False)
    finally:
        os.chdir(old_cwd)


def _activate(repo: Path, *args: str) -> object:
    return runner.invoke(
        charter_app,
        ["activate", "--repo-root", str(repo), *args],
        catch_exceptions=False,
    )


def _read_catalog(repo: Path) -> dict:
    yaml = YAML(typ="safe")
    charter_yaml_path = repo / ".kittify" / "charter" / "charter.yaml"
    document = yaml.load(charter_yaml_path.read_text(encoding="utf-8"))
    return document["catalog"]


def test_activate_recompile_preserves_recorded_mission_type(tmp_path: Path) -> None:
    """#4908: a plain ``charter activate`` on a ``research`` project must not
    flip ``catalog.mission``/``catalog.template_set`` to ``software-dev`` or
    drop any previously-resolved ``catalog.references`` entry."""
    _git_init(tmp_path)
    _seed_configured_project(tmp_path)

    generated = _invoke_generate(tmp_path, "--mission-type", "research", "--no-from-interview")
    assert generated.exit_code == 0, generated.output

    before = _read_catalog(tmp_path)
    assert before["mission"] == "research", "test setup invariant: the initial generate must record mission=research"
    assert before["template_set"] == "research-default"
    ids_before = {reference["id"] for reference in before["references"]}
    assert not any("DIRECTIVE_025" in reference_id for reference_id in ids_before), (
        "test setup invariant: the activated directive must be a genuine addition, not already present in the baseline catalog"
    )

    activated = _activate(tmp_path, "directive", _REAL_DIRECTIVE_STEM)
    assert activated.exit_code == 0, activated.output

    after = _read_catalog(tmp_path)

    assert after["mission"] == "research", (
        f"charter activate must not silently discard the project's recorded mission type -- got {after['mission']!r} (before: {before['mission']!r})"
    )
    assert after["template_set"] == "research-default", (
        f"charter activate must not silently flip the resolved template_set -- got {after['template_set']!r} (before: {before['template_set']!r})"
    )

    ids_after = {reference["id"] for reference in after["references"]}
    assert ids_before <= ids_after, f"charter activate must not drop any previously-resolved catalog reference -- dropped: {sorted(ids_before - ids_after)}"
    assert any("DIRECTIVE_025" in reference_id for reference_id in ids_after), "charter activate must add the newly-activated directive to catalog.references"


# ---------------------------------------------------------------------------
# T005 -- focused unit tests for the SSOT-read helpers
# ---------------------------------------------------------------------------


def _write_charter_yaml(repo: Path, *, mission: str | None) -> None:
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    catalog_line = f"  mission: {mission}\n" if mission is not None else ""
    (charter_dir / "charter.yaml").write_text(
        f"schema_version: '2.0.0'\ncatalog:\n{catalog_line}  references: []\n",
        encoding="utf-8",
    )


def _write_answers_yaml(repo: Path, *, mission: str) -> Path:
    answers_dir = repo / ".kittify" / "charter" / "interview"
    answers_dir.mkdir(parents=True, exist_ok=True)
    answers_path = answers_dir / "answers.yaml"
    answers_path.write_text(f"mission: {mission}\n", encoding="utf-8")
    return answers_path


def test_read_catalog_mission_returns_none_when_charter_yaml_absent(tmp_path: Path) -> None:
    assert _read_catalog_mission_from_charter_yaml(tmp_path) is None


def test_read_catalog_mission_returns_recorded_value(tmp_path: Path) -> None:
    _write_charter_yaml(tmp_path, mission="research")

    assert _read_catalog_mission_from_charter_yaml(tmp_path) == "research"


def test_read_catalog_mission_returns_none_on_malformed_yaml(tmp_path: Path) -> None:
    """A corrupt ``charter.yaml`` must degrade to ``None``, never raise."""
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.yaml").write_text("catalog: [unterminated\n", encoding="utf-8")

    assert _read_catalog_mission_from_charter_yaml(tmp_path) is None


def test_resolve_recorded_mission_type_prefers_charter_yaml_catalog_mission(
    tmp_path: Path,
) -> None:
    """(a): ``charter.yaml`` present with ``catalog.mission: research`` wins."""
    _write_charter_yaml(tmp_path, mission="research")
    answers_path = _write_answers_yaml(tmp_path, mission="documentation")

    assert _resolve_recorded_mission_type(tmp_path, answers_path) == "research"


def test_resolve_recorded_mission_type_falls_back_to_answers_yaml(
    tmp_path: Path,
) -> None:
    """(b): no compiled ``charter.yaml`` yet -- ``answers.yaml`` ``mission:`` wins."""
    answers_path = _write_answers_yaml(tmp_path, mission="documentation")

    assert _resolve_recorded_mission_type(tmp_path, answers_path) == "documentation"


def test_resolve_recorded_mission_type_falls_back_to_literal_with_no_ssot(
    tmp_path: Path,
) -> None:
    """Neither SSOT present (brand-new project) -- the last-resort literal."""
    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"

    assert _resolve_recorded_mission_type(tmp_path, answers_path) == "software-dev"


def test_resolve_recorded_mission_type_malformed_answers_does_not_abort(
    tmp_path: Path,
) -> None:
    """(c): malformed ``answers.yaml`` must not raise (the #2940 guard) -- with
    no compiled ``charter.yaml`` either, resolution falls through all the way
    to the last-resort literal rather than propagating the parse failure."""
    answers_dir = tmp_path / ".kittify" / "charter" / "interview"
    answers_dir.mkdir(parents=True, exist_ok=True)
    answers_path = answers_dir / "answers.yaml"
    answers_path.write_text("not: [a, valid, mapping\n", encoding="utf-8")

    assert _resolve_recorded_mission_type(tmp_path, answers_path) == "software-dev"


def test_resolve_recorded_mission_type_malformed_answers_falls_back_to_compiled_mission(
    tmp_path: Path,
) -> None:
    """(c), established-store variant: a malformed ``answers.yaml`` must not
    abort, and must not even shadow an already-compiled ``charter.yaml``'s
    recorded mission -- ``catalog.mission`` (SSOT priority 1) is read first."""
    _write_charter_yaml(tmp_path, mission="research")
    answers_dir = tmp_path / ".kittify" / "charter" / "interview"
    answers_dir.mkdir(parents=True, exist_ok=True)
    answers_path = answers_dir / "answers.yaml"
    answers_path.write_text("not: [a, valid, mapping\n", encoding="utf-8")

    assert _resolve_recorded_mission_type(tmp_path, answers_path) == "research"


# ---------------------------------------------------------------------------
# T010 -- shared ``catalog.mission`` accessor (Finding B, #4993)
# ---------------------------------------------------------------------------


def test_read_catalog_field_returns_none_when_charter_yaml_absent(tmp_path: Path) -> None:
    assert read_catalog_field(tmp_path, "mission") is None
    assert read_catalog_mission(tmp_path) is None


def test_read_catalog_field_returns_recorded_value(tmp_path: Path) -> None:
    _write_charter_yaml(tmp_path, mission="research")

    assert read_catalog_field(tmp_path, "mission") == "research"
    assert read_catalog_mission(tmp_path) == "research"


def test_read_catalog_field_returns_none_when_catalog_section_absent(tmp_path: Path) -> None:
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.yaml").write_text("schema_version: '2.0.0'\n", encoding="utf-8")

    assert read_catalog_field(tmp_path, "mission") is None


def test_read_catalog_field_returns_none_when_field_absent_from_catalog(tmp_path: Path) -> None:
    _write_charter_yaml(tmp_path, mission=None)

    assert read_catalog_field(tmp_path, "mission") is None


def test_read_catalog_field_returns_none_on_malformed_yaml(tmp_path: Path) -> None:
    """A corrupt ``charter.yaml`` must degrade to ``None``, never raise."""
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.yaml").write_text("catalog: [unterminated\n", encoding="utf-8")

    assert read_catalog_field(tmp_path, "mission") is None


def test_read_catalog_field_resolves_quoted_commented_value_identically(tmp_path: Path) -> None:
    """A quoted ``catalog.mission`` value with a trailing inline comment must
    resolve to the same plain string as an unquoted, uncommented one -- the
    accessor's canonical ruamel round-trip parser (``preserve_quotes``) must
    not leak quote markers or comment text into the returned value."""
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.yaml").write_text(
        'schema_version: "2.0.0"\ncatalog:\n  mission: "research"  # recorded at compile time\n  references: []\n',
        encoding="utf-8",
    )

    assert read_catalog_field(tmp_path, "mission") == "research"
    assert read_catalog_mission(tmp_path) == "research"


def test_generate_reader_and_shared_accessor_resolve_identical_value(tmp_path: Path) -> None:
    """AC-B1: both former readers resolve the SAME value through the one
    shared accessor for a normal charter."""
    _write_charter_yaml(tmp_path, mission="research")

    assert _read_catalog_mission_from_charter_yaml(tmp_path) == read_catalog_mission(tmp_path) == "research"


def test_generate_reader_and_shared_accessor_agree_on_absent_result(tmp_path: Path) -> None:
    """AC-B2: absent ``catalog.mission`` yields the same absent result to
    every caller."""
    _write_charter_yaml(tmp_path, mission=None)

    assert _read_catalog_mission_from_charter_yaml(tmp_path) is None
    assert read_catalog_mission(tmp_path) is None


def test_catalog_mission_has_exactly_one_reader_outside_the_shared_accessor() -> None:
    """AC-B3 / NFR-003 / SC-002 grep proof: no second ``catalog.mission``
    parser survives outside ``charter_yaml_io.read_catalog_field`` /
    ``read_catalog_mission``. Issue #4993 claimed three readers; the true
    count was two (the claimed third read ``catalog.languages``) -- both
    now delegate, so a direct ``catalog["mission"]`` / ``catalog.get(
    "mission")`` read anywhere in ``src/`` other than the accessor itself is
    a regression."""
    repo_root = Path(__file__).resolve().parents[5]
    accessor_path = repo_root / "src" / "charter" / "activation" / "charter_yaml_io.py"
    pattern = re.compile(r"""catalog(\.get\(|\[)["']mission["']""")

    hits: list[str] = []
    for path in (repo_root / "src").rglob("*.py"):
        if path == accessor_path:
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            hits.append(str(path.relative_to(repo_root)))

    assert hits == [], f"catalog.mission must be read only through charter.activation.charter_yaml_io.read_catalog_mission -- found direct reads in: {hits}"
