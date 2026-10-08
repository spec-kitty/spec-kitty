"""R2 — id-collision precedence in agent-profile projection honours ``_LAYER_RANK``.

Projection merges the activation-admitted org overlay onto the built-in +
project-doctrine repository via ``AgentProfileRepository.register_overlay``,
which applies project > org > builtin precedence. An org profile reusing a
BUILT-IN id therefore projects with ``source_layer == "org"`` (org wins), while
an org profile reusing a (``.kittify/agent_profiles``) PROJECT id keeps
``source_layer == "project"`` (project wins).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.tool_surface.model import NativeAgentProfile
from specify_cli.tool_surface.profiles.projection import (
    ProfileProjector,
    default_profile_repository,
)

pytestmark = pytest.mark.fast

_PACK_NAME = "orgzilla-governance-pack"
_BUILTIN_COLLISION_ID = "python-pedro"
_SHARED_PROJECT_ID = "acme-shared-architect"
_TOOL_KEY = "claude"


def _agent_yaml(profile_id: str, *, name: str, role: str) -> str:
    return (
        f"profile-id: {profile_id}\n"
        f"name: {name}\n"
        "description: Collision-precedence projection fixture\n"
        'schema-version: "1.0"\n'
        "roles:\n"
        f"  - {role}\n"
        "purpose: >\n"
        "  Profile used to verify _LAYER_RANK precedence in projection.\n"
        "specialization:\n"
        "  primary-focus: >\n"
        "    Verifying layer precedence on id collision in projection.\n"
        "  avoidance-boundary: unrelated work\n"
    )


def _write_org_pack(repo_root: Path) -> Path:
    pack_root = repo_root / "org-packs" / _PACK_NAME
    profiles_dir = pack_root / "agent_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / f"{_BUILTIN_COLLISION_ID}.agent.yaml").write_text(
        _agent_yaml(_BUILTIN_COLLISION_ID, name="Org Pedro", role="implementer"),
        encoding="utf-8",
    )
    (profiles_dir / f"{_SHARED_PROJECT_ID}.agent.yaml").write_text(
        _agent_yaml(_SHARED_PROJECT_ID, name="Org Architect", role="architect"),
        encoding="utf-8",
    )
    return pack_root


def _seed_project_doctrine_profile(repo_root: Path) -> None:
    project_dir = repo_root / ".kittify" / "agent_profiles"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / f"{_SHARED_PROJECT_ID}.agent.yaml").write_text(
        _agent_yaml(_SHARED_PROJECT_ID, name="Project Architect", role="architect"),
        encoding="utf-8",
    )


def _write_config(repo_root: Path, pack_root: Path) -> None:
    data: dict[str, object] = {
        "charter_packs": {"org": {"packs": [{"name": _PACK_NAME, "local_path": str(pack_root)}]}},
    }
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump(data, fh)


def _project(repo_root: Path) -> dict[str, NativeAgentProfile]:
    repo = default_profile_repository(repo_root)
    projector = ProfileProjector(repo)
    return {p.profile_urn: p for p in projector.project(_TOOL_KEY, repo_root)}


def _urn(profile_id: str) -> str:
    return f"agent_profile:{profile_id}"


def test_org_overlays_builtin_id_in_projection(tmp_path: Path) -> None:
    """Org reusing a built-in id projects with ``source_layer == 'org'`` (org > builtin)."""
    pack_root = _write_org_pack(tmp_path)
    _write_config(tmp_path, pack_root)

    projected = _project(tmp_path)

    entry = projected.get(_urn(_BUILTIN_COLLISION_ID))
    assert entry is not None
    assert entry.source_layer == "org"


def test_project_wins_over_org_id_in_projection(tmp_path: Path) -> None:
    """Org reusing a project id keeps ``source_layer == 'project'`` (project > org)."""
    pack_root = _write_org_pack(tmp_path)
    _seed_project_doctrine_profile(tmp_path)
    _write_config(tmp_path, pack_root)

    projected = _project(tmp_path)

    entry = projected.get(_urn(_SHARED_PROJECT_ID))
    assert entry is not None
    assert entry.source_layer == "project"
