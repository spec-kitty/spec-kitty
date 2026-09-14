"""CL-005 mission-type roster path-layout SSOT regression (#3427).

The path layout of the layered mission-type roster (where each layer's
``mission_types/`` directory lives) has exactly ONE authority: the public
constants in ``charter.offering.missions.mission_type_repository``
(:data:`ORG_MISSION_TYPES_SUBDIR` / :data:`PROJECT_MISSION_TYPES_RELATIVE`).
Before #3427 the two ``charter.activation`` consumers re-spelled that layout
as inline literals, so an editor moving a layer directory by editing the
authority silently left the layer-namer
(``mission_type_profiles.resolve_action_sequence_layer``) and the
availability catalog (``pack_manager._resolve_layer_candidate``) scanning the
old path -- latent drift filed as #3427 off the #3424 landing pass.

These tests pin all three sites to ONE physical directory per layer, built
from one fixture written at the authority's own path. Each site's own unit
test still passes in isolation if its literal drifts; these cross-site
assertions are what red -- the drift class #3427 exists to close.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from charter.activation.invocation_context import ProjectContext
from charter.activation.mission_type_profiles import resolve_action_sequence_layer
from charter.activation.pack_manager import CharterPackManager, _resolve_layer_candidate
from charter.offering.missions.mission_type_repository import (
    ORG_MISSION_TYPES_SUBDIR,
    PROJECT_MISSION_TYPES_RELATIVE,
    PROJECT_MISSION_TYPES_RELATIVE_TO_KITTYFY_ROOT,
    resolve_layered_mission_types,
)

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class _StubPackContext:
    """Minimal structural stand-in satisfying ``_PackContextLike``.

    Mirrors ``tests/doctrine/missions/test_mission_type_repository.py``'s own
    ``_StubPackContext`` (``pack_roots``, ``repo_root``, ``__hash__``
    synthesized by ``@dataclass(frozen=True)``) so both the layered factory
    and the layer-namer accept the same context object in one test.
    """

    pack_roots: tuple[Path, ...]
    repo_root: Path


def _write_mission_type(directory: Path, mission_type_id: str) -> Path:
    """Write a minimal, schema-valid roster file and return its path.

    Same body as ``tests/charter/test_pack_manager.py``'s own helper: the
    availability catalog's mission-type branch scans through the same
    schema-validating primitive as the layered factory, so a fixture that is
    not a genuinely valid ``MissionType`` raises instead of resolving.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{mission_type_id}.yaml"
    path.write_text(
        f"schema_version: 1\nid: {mission_type_id}\ndisplay_name: {mission_type_id.title()}\n",
        encoding="utf-8",
    )
    return path


class TestMissionTypePathLayoutSingleAuthority:
    """The three CL-005 sites resolve ONE directory per layer (#3427).

    ``setup``/``teardown`` clear the layered factory's cache (its documented
    same-key staleness contract) so each test walks its own fixture.
    """

    def setup_method(self) -> None:
        resolve_layered_mission_types.cache_clear()

    def teardown_method(self) -> None:
        resolve_layered_mission_types.cache_clear()

    def test_project_layer_directory_agrees_across_all_three_sites(self, tmp_path: Path) -> None:
        """A project-layer type written at the authority's path is resolved,
        labelled ``"project"``, and catalogued from that SAME directory by
        the layered factory, the layer-namer, and the availability catalog.
        """
        repo = tmp_path / "repo"
        authority_dir = repo.joinpath(*PROJECT_MISSION_TYPES_RELATIVE)
        probe = _write_mission_type(authority_dir, "probe-type")
        assert probe.is_file()  # the fixture itself sits at the authority path

        ctx = _StubPackContext(pack_roots=(), repo_root=repo)

        # Site 1 -- the authority's own layered roster resolves the type.
        roster = resolve_layered_mission_types((), ctx)
        assert "probe-type" in roster

        # Site 2 -- the layer-namer labels the SAME file "project".
        layer = resolve_action_sequence_layer("probe-type", mission_types_dirs=(), pack_context=ctx)
        assert layer == "project"

        # Site 3 -- the availability catalog scans the SAME directory, both
        # through the candidate resolver and the full manager path.
        candidate = _resolve_layer_candidate("project", repo / ".kittify", None, "missions/mission_types", layered=False)
        assert candidate == authority_dir
        detailed = CharterPackManager().list_available_detailed(
            ProjectContext(repo_root=repo),
            kind="mission-type",
            layer_roots={"project": repo / ".kittify"},
        )
        probe_entries = [entry for entry in detailed if entry.artifact_id == "probe-type"]
        assert [entry.layer for entry in probe_entries] == ["project"]

    def test_org_layer_directory_agrees_across_all_three_sites(self, tmp_path: Path) -> None:
        """An org-layer type written at the authority's path is resolved,
        labelled ``"org"``, and catalogued from that SAME directory by the
        layered factory, the layer-namer, and the availability catalog.
        """
        org_root = tmp_path / "org-pack"
        authority_dir = org_root / ORG_MISSION_TYPES_SUBDIR
        _write_mission_type(authority_dir, "probe-org")

        ctx = _StubPackContext(pack_roots=(org_root,), repo_root=tmp_path / "repo-without-project-layer")

        roster = resolve_layered_mission_types((), ctx)
        assert "probe-org" in roster

        layer = resolve_action_sequence_layer("probe-org", mission_types_dirs=(), pack_context=ctx)
        assert layer == "org"

        candidate = _resolve_layer_candidate("org", org_root, None, "missions/mission_types", layered=False)
        assert candidate == authority_dir
        detailed = CharterPackManager().list_available_detailed(
            ProjectContext(repo_root=org_root),
            kind="mission-type",
            layer_roots={"org": org_root},
        )
        probe_entries = [entry for entry in detailed if entry.artifact_id == "probe-org"]
        assert [entry.layer for entry in probe_entries] == ["org"]

    def test_pack_manager_project_base_is_authority_leading_segment(self, tmp_path: Path) -> None:
        """The base ``layer_roots["project"]`` hands pack_manager is the repo
        root joined with the authority's LEADING ``.kittify`` segment -- the
        invariant that makes the derived under-``.kittify`` tail constant the
        correct join for that base point.

        If the authority's leading segment ever moves, this pins the
        reconciliation point instead of letting pack_manager's join silently
        diverge by one directory level.
        """
        # Lazy: keeps the specify_cli CLI surface out of this module's import
        # time for the charter test shard.
        from specify_cli.cli.commands.charter._layer_roots import resolve_layer_roots

        repo = tmp_path / "repo"
        (repo / ".kittify" / "doctrine").mkdir(parents=True)

        roots = resolve_layer_roots(repo)

        assert roots["project"] == repo.joinpath(PROJECT_MISSION_TYPES_RELATIVE[0])
        # The full join from that base reproduces the authority's own path.
        assert roots["project"].joinpath(*PROJECT_MISSION_TYPES_RELATIVE_TO_KITTYFY_ROOT) == repo.joinpath(*PROJECT_MISSION_TYPES_RELATIVE)
