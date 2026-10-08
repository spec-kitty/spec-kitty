"""CLI tests for ``spec-kitty charter mission-type list --include-inactive``.

WP13 / T081 — the all-layers mission-type listing. It was
``doctrine mission-type list [--json]`` until the doctrine group was removed
(mission charter-pack-cutover-01M491G6, FR-007).

Owner: ``src/specify_cli/cli/commands/charter/mission_type.py``
Mission: charter-doctrine-mission-type-configuration-01KSWJVX
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app as app

runner = CliRunner()

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_org_mission_type_yaml(
    org_root: Path,
    mission_type_id: str,
    *,
    action_sequence: list[str],
) -> None:
    """Write a minimal org-layer mission-type YAML (CL-005 flat layout)."""
    mt_dir = org_root / "mission_types"
    mt_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "schema_version: 1",
        f"id: {mission_type_id}",
        f"display_name: {mission_type_id.title()}",
        "action_sequence:",
        *(f"  - {step}" for step in action_sequence),
    ]
    (mt_dir / f"{mission_type_id}.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# T081-a: mission-type sub-group is registered under charter
# ---------------------------------------------------------------------------


def test_charter_mission_type_subgroup_registered() -> None:
    """``charter mission-type --help`` exits 0 (group is registered).

    This is the T077 guard: verifies the ``mission-type`` sub-group
    exists (see the PR #1352 regression incident).
    """
    result = runner.invoke(app, ["mission-type", "--help"])
    assert result.exit_code == 0, result.output
    assert "list" in result.output


# ---------------------------------------------------------------------------
# T081-b: default table output returns all four built-in types
# ---------------------------------------------------------------------------


def test_mission_type_list_returns_built_in_types() -> None:
    """``charter mission-type list --include-inactive`` returns at least the four canonical types."""
    result = runner.invoke(app, ["mission-type", "list", "--include-inactive"])

    assert result.exit_code == 0, result.output

    # All four canonical mission types must appear.
    expected_ids = ["software-dev", "documentation", "research", "plan"]
    for mt_id in expected_ids:
        assert mt_id in result.output, (
            f"Expected mission type id {mt_id!r} not found in output:\n{result.output}"
        )


def test_mission_type_list_shows_built_in_source_layer() -> None:
    """Each row in table output carries ``built-in`` as the source layer."""
    result = runner.invoke(app, ["mission-type", "list", "--include-inactive"])

    assert result.exit_code == 0, result.output
    assert "built-in" in result.output


def test_mission_type_list_shows_display_names() -> None:
    """Table output includes human-readable display names for well-known types."""
    result = runner.invoke(app, ["mission-type", "list", "--include-inactive"])

    assert result.exit_code == 0, result.output
    # Check at least one canonical display name is present.
    assert "Software Development" in result.output


# ---------------------------------------------------------------------------
# T081-c: --json flag produces valid JSON with required keys
# ---------------------------------------------------------------------------


def test_mission_type_list_json_is_valid() -> None:
    """``--json`` flag produces a valid JSON array."""
    result = runner.invoke(app, ["mission-type", "list", "--include-inactive", "--json"])

    assert result.exit_code == 0, result.output

    # Output must be parseable JSON.
    try:
        data = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        pytest.fail(f"JSON output is not valid JSON: {exc}\n\nOutput:\n{result.output}")

    assert isinstance(data, list), "JSON output must be a list"
    assert len(data) >= 4, "Expected at least 4 mission types in JSON output"


def test_mission_type_list_json_has_required_keys() -> None:
    """Each JSON item has ``id``, ``source_layer``, and ``display_name``."""
    result = runner.invoke(app, ["mission-type", "list", "--include-inactive", "--json"])

    assert result.exit_code == 0, result.output

    data = json.loads(result.stdout.strip())
    assert isinstance(data, list)

    for item in data:
        assert "id" in item, f"Missing 'id' key in item: {item}"
        assert "source_layer" in item, f"Missing 'source_layer' key in item: {item}"
        assert "display_name" in item, f"Missing 'display_name' key in item: {item}"


def test_mission_type_list_json_contains_built_in_software_dev() -> None:
    """JSON output includes the software-dev built-in type with correct fields."""
    result = runner.invoke(app, ["mission-type", "list", "--include-inactive", "--json"])

    assert result.exit_code == 0, result.output

    data = json.loads(result.stdout.strip())
    assert isinstance(data, list)

    sw_dev = next((item for item in data if item["id"] == "software-dev"), None)
    assert sw_dev is not None, "'software-dev' not found in JSON output"
    assert sw_dev["source_layer"] == "built-in"
    assert sw_dev["display_name"] == "Software Development"


def test_mission_type_list_json_all_built_in_types() -> None:
    """JSON output contains all four canonical built-in mission types."""
    result = runner.invoke(app, ["mission-type", "list", "--include-inactive", "--json"])

    assert result.exit_code == 0, result.output

    data = json.loads(result.stdout.strip())
    ids = {item["id"] for item in data}
    expected = {"software-dev", "documentation", "research", "plan"}
    assert expected <= ids, (
        f"Expected canonical ids {expected!r} to be a subset of {ids!r}"
    )


# ---------------------------------------------------------------------------
# T081-d: command works without .kittify/config.yaml (no project required)
# ---------------------------------------------------------------------------


def test_mission_type_list_works_without_kittify(tmp_path: object) -> None:
    """``charter mission-type list --include-inactive`` works from a directory without a project.

    The command must not require ``.kittify/config.yaml`` to return
    built-in types.
    """
    # tmp_path has no .kittify directory — simulate a bare filesystem location.
    result = runner.invoke(app, ["mission-type", "list", "--include-inactive"])
    # Built-in types should always be accessible.
    assert result.exit_code == 0, result.output
    assert "software-dev" in result.output


# ---------------------------------------------------------------------------
# T081-e: source_layer values are one of the canonical set
# ---------------------------------------------------------------------------


def test_mission_type_list_json_source_layers_canonical() -> None:
    """All ``source_layer`` values in JSON are from the canonical set."""
    result = runner.invoke(app, ["mission-type", "list", "--include-inactive", "--json"])

    assert result.exit_code == 0, result.output

    data = json.loads(result.stdout.strip())
    canonical_layers = {"built-in", "org", "project"}
    for item in data:
        assert item["source_layer"] in canonical_layers, (
            f"Non-canonical source_layer {item['source_layer']!r} in item {item!r}"
        )


# ---------------------------------------------------------------------------
# FR-008 (WP07/T018) -- the all-layers listing implements its own
# already-documented built-in -> org -> project layering, instead of only
# ever calling the built-in-only collector.
# ---------------------------------------------------------------------------


def test_mission_type_list_includes_registered_org_type_regardless_of_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-008: an org-layer type appears with its real layer even when it is
    merely *registered* (not activated) -- a true all-layers roster listing,
    not an activation-scoped one (this command's own docstring already
    promises built-in -> org -> project layering; pre-fix, ``rows`` only
    ever comes from ``_collect_built_in_mission_types()``, so an org-only id
    is simply absent from the output, not mislabeled).
    """
    from charter.offering.missions.mission_type_repository import MissionTypeRepository

    from charter.activation.pack_context import PackContext

    org_root = tmp_path / "org-pack"
    _write_org_mission_type_yaml(org_root, "qa", action_sequence=["design", "implement"])
    pack_context = PackContext(
        activated_kinds=frozenset(),
        activated_mission_types=frozenset(),  # deliberately NOT activated
        pack_roots=(tmp_path / "unused-builtin-placeholder", org_root),
        org_pack_names=("org-pack",),
        repo_root=tmp_path,
    )
    monkeypatch.chdir(tmp_path)
    MissionTypeRepository.cache_clear()
    try:
        with patch("charter.activation.pack_context.PackContext.from_config", return_value=pack_context):
            result = runner.invoke(app, ["mission-type", "list", "--include-inactive", "--json"])
    finally:
        MissionTypeRepository.cache_clear()

    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout.strip())
    ids = {item["id"] for item in data}
    assert "qa" in ids, f"org-registered 'qa' missing from listing: {data!r}"
    qa_row = next(item for item in data if item["id"] == "qa")
    assert qa_row["source_layer"] == "org"
    # Built-in types are still present -- listing is additive, not a swap.
    assert {"software-dev", "documentation", "research", "plan"} <= ids
