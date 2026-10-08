"""R2 — id-collision precedence in the dispatch routing catalog honours ``_LAYER_RANK``.

The canonical layer precedence is project > org > builtin. The routing catalog
must therefore let an org profile that reuses a BUILT-IN id overlay it (org
wins), while an org profile reusing a (legacy ``.kittify/profiles``) PROJECT id
does NOT win (project wins). The previous ``setdefault`` merge gave the built-in
precedence over org — the opposite of ``_LAYER_RANK`` — which this pins shut.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.invocation.registry import ProfileRegistry

pytestmark = pytest.mark.fast

_PACK_NAME = "orgzilla-governance-pack"
# An org profile that REUSES a real built-in id (collision with builtin).
_BUILTIN_COLLISION_ID = "python-pedro"
_ORG_PEDRO_NAME = "Org Pedro Overlay"
# An org profile that REUSES a legacy-project id (collision with project).
_SHARED_PROJECT_ID = "acme-shared-implementer"
_PROJECT_NAME = "Acme Project Implementer"
_ORG_SHARED_NAME = "Org Shared Implementer"


def _profile_yaml(profile_id: str, *, name: str, role: str) -> str:
    return (
        f"profile-id: {profile_id}\n"
        f"name: {name}\n"
        "description: Collision-precedence fixture profile\n"
        'schema-version: "1.0"\n'
        "roles:\n"
        f"  - {role}\n"
        "purpose: >\n"
        "  Profile used to verify _LAYER_RANK collision precedence in routing.\n"
        "specialization:\n"
        "  primary-focus: >\n"
        "    Verifying layer precedence on id collision.\n"
    )


def _write_org_pack(repo_root: Path) -> Path:
    pack_root = repo_root / "org-packs" / _PACK_NAME
    profiles_dir = pack_root / "agent_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / f"{_BUILTIN_COLLISION_ID}.agent.yaml").write_text(
        _profile_yaml(_BUILTIN_COLLISION_ID, name=_ORG_PEDRO_NAME, role="implementer"),
        encoding="utf-8",
    )
    (profiles_dir / f"{_SHARED_PROJECT_ID}.agent.yaml").write_text(
        _profile_yaml(_SHARED_PROJECT_ID, name=_ORG_SHARED_NAME, role="implementer"),
        encoding="utf-8",
    )
    return pack_root


def _write_legacy_project_profile(repo_root: Path) -> None:
    project_dir = repo_root / ".kittify" / "profiles"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / f"{_SHARED_PROJECT_ID}.agent.yaml").write_text(
        _profile_yaml(_SHARED_PROJECT_ID, name=_PROJECT_NAME, role="implementer"),
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


def test_org_overlays_builtin_id_in_routing(tmp_path: Path) -> None:
    """Org reusing a built-in id wins in ``ProfileRegistry.list_all()`` (org > builtin)."""
    pack_root = _write_org_pack(tmp_path)
    _write_config(tmp_path, pack_root)

    by_id = {p.profile_id: p for p in ProfileRegistry(tmp_path).list_all()}

    assert _BUILTIN_COLLISION_ID in by_id
    assert by_id[_BUILTIN_COLLISION_ID].name == _ORG_PEDRO_NAME


def test_project_wins_over_org_id_in_routing(tmp_path: Path) -> None:
    """Org reusing a legacy-project id does NOT win — project wins (project > org)."""
    pack_root = _write_org_pack(tmp_path)
    _write_legacy_project_profile(tmp_path)
    _write_config(tmp_path, pack_root)

    by_id = {p.profile_id: p for p in ProfileRegistry(tmp_path).list_all()}

    assert _SHARED_PROJECT_ID in by_id
    assert by_id[_SHARED_PROJECT_ID].name == _PROJECT_NAME
