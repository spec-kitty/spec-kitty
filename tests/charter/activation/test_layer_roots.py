"""``charter.activation.layer_roots``: the project layer root is the project pack root (FR-016)."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.invocation_context import ProjectContext
from charter.activation.layer_roots import resolve_layer_roots, resolve_org_root_chain
from charter.activation.pack_manager import ActiveCharterManager
from charter.offering.missions.mission_type_repository import (
    PROJECT_MISSION_TYPES_RELATIVE,
    resolve_layered_mission_types,
)
from kernel.charter_pack_paths import project_pack_root

pytestmark = pytest.mark.unit


def _write_org_config(repo: Path, *pack_dirs: Path) -> None:
    lines = ["charter_packs:", "  org:", "    packs:"]
    for index, pack_dir in enumerate(pack_dirs):
        lines += [f"      - name: org-{index}", f"        local_path: {pack_dir}"]
    (repo / ".kittify").mkdir(parents=True, exist_ok=True)
    (repo / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestProjectLayerRoot:
    def test_migrated_layout_resolves_the_project_pack_root(self, tmp_path: Path) -> None:
        (tmp_path / ".kittify" / "charter-packs").mkdir(parents=True)

        roots = resolve_layer_roots(tmp_path)

        assert roots["project"] == tmp_path / ".kittify" / "charter-packs"
        assert roots["project"] == project_pack_root(tmp_path)

    def test_the_retired_root_is_not_a_project_layer(self, tmp_path: Path, recwarn: pytest.WarningsRecorder) -> None:
        """FR-011: ``.kittify/doctrine/`` alone is no project layer (and no warning)."""
        (tmp_path / ".kittify" / "doctrine").mkdir(parents=True)

        roots = resolve_layer_roots(tmp_path)

        assert "project" not in roots
        assert not recwarn.list

    def test_migrated_layout_wins_over_a_stale_legacy_tree(self, tmp_path: Path) -> None:
        (tmp_path / ".kittify" / "charter-packs").mkdir(parents=True)
        (tmp_path / ".kittify" / "doctrine").mkdir(parents=True)

        assert resolve_layer_roots(tmp_path)["project"] == tmp_path / ".kittify" / "charter-packs"

    def test_neither_layout_has_no_project_key(self, tmp_path: Path) -> None:
        (tmp_path / ".kittify").mkdir()

        assert "project" not in resolve_layer_roots(tmp_path)


class TestOrgLayerRootUnchanged:
    def test_first_existing_org_pack_is_the_org_root(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        missing, first, second = tmp_path / "missing", tmp_path / "first", tmp_path / "second"
        first.mkdir()
        second.mkdir()
        _write_org_config(repo, missing, first, second)

        roots = resolve_layer_roots(repo)

        assert roots["org"] == first
        assert resolve_org_root_chain(repo) == [first, second]

    def test_no_org_pack_has_no_org_key(self, tmp_path: Path) -> None:
        (tmp_path / ".kittify").mkdir()

        assert "org" not in resolve_layer_roots(tmp_path)
        assert resolve_org_root_chain(tmp_path) == []


class TestProjectMissionTypesWithMigratedLayout:
    """T012 step 4: the project mission-type roster stays at
    ``.kittify/missions/mission_types/`` (outside the pack) and is still listed
    once the project layer root is the project pack root."""

    def setup_method(self) -> None:
        resolve_layered_mission_types.cache_clear()

    def teardown_method(self) -> None:
        resolve_layered_mission_types.cache_clear()

    def test_project_mission_type_is_listed(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / ".kittify" / "charter-packs").mkdir(parents=True)
        roster = repo.joinpath(*PROJECT_MISSION_TYPES_RELATIVE)
        roster.mkdir(parents=True)
        (roster / "probe-type.yaml").write_text("schema_version: 1\nid: probe-type\ndisplay_name: Probe Type\n", encoding="utf-8")

        detailed = ActiveCharterManager().list_available_detailed(
            ProjectContext(repo_root=repo),
            kind="mission-type",
            layer_roots=resolve_layer_roots(repo),
        )

        assert [entry.layer for entry in detailed if entry.artifact_id == "probe-type"] == ["project"]

    def test_control_without_the_roster_file_nothing_is_listed(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / ".kittify" / "charter-packs").mkdir(parents=True)

        detailed = ActiveCharterManager().list_available_detailed(
            ProjectContext(repo_root=repo),
            kind="mission-type",
            layer_roots=resolve_layer_roots(repo),
        )

        assert not [entry for entry in detailed if entry.artifact_id == "probe-type"]
