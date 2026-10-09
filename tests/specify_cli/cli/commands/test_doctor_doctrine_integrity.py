"""CLI test: `spec-kitty doctor charter-packs` wires the FR-013 cross-grain scan (#2666).

``charter.activation.action_grain.scan_builtin_cross_grain_duplicates`` (WP02/WP04) already
enumerates every shipped mission type and raises
``charter.activation.mission_type_profiles.CrossGrainDoubleDeclarationError`` the moment one
artifact URN is declared in both a mission type's *type grain*
(``governance-profile.yaml``) and its *action grain* (``actions/*/index.yaml``).
Before this WP that scan had **no ``src`` caller** — it was only exercised by
``tests/charter_offering/drg/test_cross_grain_integrity.py``, so a real collision in a
project/org-authored mission type would never surface outside pytest.

This test proves the scan is now load-bearing through
``spec-kitty doctor charter-packs --json``: a synthetic built-in tree with a
deliberate type/action collision must flip the command to RC=1 with a
structured finding in the JSON payload; a disjoint synthetic tree must leave
the command healthy (RC=0, no finding). The synthetic-tree construction
mirrors the ``TestNonVacuityTwin`` fixture in
``tests/charter_offering/drg/test_cross_grain_integrity.py`` — same production seam
(``MissionTypeProfileRepository`` -> the type grain / action grain union),
just driven through the real CLI instead of calling the union function
directly, and pointed at the scan's root via a monkeypatch of the
module-level ``charter.activation.mission_type_profile_repository.builtin_missions_root``
accessor rather than an explicit ``built_in_dir=`` argument (the CLI path
calls ``scan_builtin_cross_grain_duplicates()`` with no arguments, which
resolves its root via ``charter.activation.action_grain``'s direct call to
``builtin_missions_root()`` — WP06 (#2668) promoted that accessor to a
public module-level function and demoted
``MissionTypeProfileRepository._default_built_in_dir`` to a thin delegate
that calls it too, so patching the classmethod no longer reaches the scan's
own root resolution; the module-level function is the single seam that
covers both call sites).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctor import app as doctor_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


def _write_mission_type_roster(built_in_root: Path, mission_type: str, *, action: str) -> None:
    """Write ``mission_types/<mission_type>.yaml`` (the roster the scan enumerates)."""
    mission_types_dir = built_in_root / "mission_types"
    mission_types_dir.mkdir(parents=True, exist_ok=True)
    (mission_types_dir / f"{mission_type}.yaml").write_text(
        f"schema_version: 1\n"
        f"id: {mission_type}\n"
        f'display_name: "Synthetic Mission Type"\n'
        f"action_sequence:\n  - {action}\n",
        encoding="utf-8",
    )


def _write_colliding_tree(built_in_root: Path, *, mission_type: str, action: str, colliding_urn: str) -> None:
    """Author a synthetic built-in tree where ``colliding_urn`` is declared in
    both ``mission_type``'s type grain and its ``action`` action grain — the
    same fixture shape as ``TestNonVacuityTwin`` in
    ``tests/charter_offering/drg/test_cross_grain_integrity.py``, T013.
    """
    _write_mission_type_roster(built_in_root, mission_type, action=action)

    type_dir = built_in_root / mission_type
    type_dir.mkdir(parents=True, exist_ok=True)
    (type_dir / "governance-profile.yaml").write_text(
        f"id: {mission_type}\nmission_type: {mission_type}\nselected_directives:\n  - {colliding_urn}\n",
        encoding="utf-8",
    )

    action_dir = type_dir / "actions" / action
    action_dir.mkdir(parents=True, exist_ok=True)
    (action_dir / "index.yaml").write_text(
        f"action: {action}\ndirectives:\n  - {colliding_urn}\n",
        encoding="utf-8",
    )


def _write_disjoint_tree(built_in_root: Path, *, mission_type: str, action: str) -> None:
    """Author a synthetic built-in tree whose type grain and action grain are disjoint."""
    _write_mission_type_roster(built_in_root, mission_type, action=action)

    type_dir = built_in_root / mission_type
    type_dir.mkdir(parents=True, exist_ok=True)
    (type_dir / "governance-profile.yaml").write_text(
        f"id: {mission_type}\nmission_type: {mission_type}\nselected_directives:\n  - 001-type-only\n",
        encoding="utf-8",
    )

    action_dir = type_dir / "actions" / action
    action_dir.mkdir(parents=True, exist_ok=True)
    (action_dir / "index.yaml").write_text(
        f"action: {action}\ndirectives:\n  - 002-action-only\n",
        encoding="utf-8",
    )


@pytest.fixture
def kittify_project(tmp_path: Path) -> Path:
    """A minimal spec-kitty project root — no org packs, no project doctrine."""
    project_root = tmp_path / "project"
    kittify = project_root / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\n", encoding="utf-8"
    )
    return project_root


def _invoke_doctrine_json(project_root: Path, built_in_root: Path) -> tuple[int, dict[str, object]]:
    with (
        patch(
            "charter.activation.mission_type_profile_repository.builtin_missions_root",
            return_value=built_in_root,
        ),
        patch(
            "specify_cli.cli.commands.doctor.locate_project_root",
            return_value=project_root,
        ),
    ):
        result = runner.invoke(doctor_app, ["charter-packs", "--json"])
    payload = json.loads(result.output)
    return result.exit_code, payload


def test_doctor_doctrine_json_rc1_on_synthetic_cross_grain_collision(
    kittify_project: Path, tmp_path: Path
) -> None:
    """A built-in type/action URN collision flips `doctor charter-packs --json` to RC=1."""
    built_in_root = tmp_path / "colliding-built-in"
    _write_colliding_tree(
        built_in_root,
        mission_type="twin-type",
        action="implement",
        colliding_urn="099-fake-directive",
    )

    exit_code, payload = _invoke_doctrine_json(kittify_project, built_in_root)

    assert exit_code == 1, payload
    assert payload["profile_health"]["healthy"] is False
    org_drg = payload["org_drg"]
    findings = org_drg.get("cross_grain_collisions")
    assert isinstance(findings, list) and findings, org_drg
    finding = findings[0]
    assert finding["kind"] == "directives"
    assert finding["artifact"] == "099-fake-directive"
    assert any("099-fake-directive" in str(err) for err in org_drg.get("errors", []))


def test_doctor_doctrine_human_renders_loud_collision_line(
    kittify_project: Path, tmp_path: Path
) -> None:
    """The human (non-``--json``) surface prints a loud cross-grain block too."""
    built_in_root = tmp_path / "colliding-built-in-human"
    _write_colliding_tree(
        built_in_root,
        mission_type="twin-type-human",
        action="implement",
        colliding_urn="099-fake-directive-human",
    )

    with (
        patch(
            "charter.activation.mission_type_profile_repository.builtin_missions_root",
            return_value=built_in_root,
        ),
        patch(
            "specify_cli.cli.commands.doctor.locate_project_root",
            return_value=kittify_project,
        ),
    ):
        result = runner.invoke(doctor_app, ["charter-packs"])

    assert result.exit_code == 1, result.output
    assert "Cross-grain doctrine-integrity violation" in result.output
    assert "099-fake-directive-human" in result.output


def test_doctor_doctrine_json_rc0_on_disjoint_builtin_tree(
    kittify_project: Path, tmp_path: Path
) -> None:
    """A disjoint synthetic built-in tree leaves the report healthy (RC=0, no finding)."""
    built_in_root = tmp_path / "clean-built-in"
    _write_disjoint_tree(built_in_root, mission_type="twin-type-clean", action="implement")

    exit_code, payload = _invoke_doctrine_json(kittify_project, built_in_root)

    assert exit_code == 0, payload
    assert payload["profile_health"]["healthy"] is True
    org_drg = payload["org_drg"]
    assert not org_drg.get("cross_grain_collisions")
    assert not org_drg.get("errors")
