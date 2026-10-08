"""#4114 — doctrine project-layer profiles in the dispatch routing catalog.

Before #4114, ``ProfileRegistry`` filtered the activation-aware doctrine
service down to the built-in + org provenance layers, so a project-layer
profile authored under ``.kittify/charter-packs/agent_profiles/`` and activated
via ``charter activate agent-profile <id>`` was never routable: the router
saw only built-in/org profiles, and deactivating the shipped profiles left
``dispatch`` with ``ROUTER_NO_MATCH: No profiles available`` even though the
project's own profiles were activated. "Activated" and "routable" silently
diverged.

These tests pin the unified contract: the routing catalog draws from every
doctrine layer the ``activated_agent_profiles`` gate admits — project
included — so activation alone makes a project-layer profile dispatchable,
exactly as it does for a built-in (R3 parity, extended to the project layer).

The legacy ``.kittify/profiles`` invocation project layer stays outside this
contract (still overlaid ungated, still winning on id collision — see
``test_registry_collision_precedence.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.invocation.registry import ProfileRegistry
from specify_cli.invocation.router import ActionRouter

pytestmark = pytest.mark.fast

_PROJECT_ID = "seeker-implementer"
# A real built-in profile id used in activation lists so the explicit-set
# regime still admits *something* layer-orthogonal to the profile under test.
_BUILTIN_ID = "python-pedro"


def _profile_yaml(profile_id: str, *, name: str, role: str) -> str:
    """Render a minimal-but-valid ``.agent.yaml`` document body."""
    return (
        f"profile-id: {profile_id}\n"
        f"name: {name}\n"
        "description: Real-format profile for project-doctrine routing fixtures\n"
        'schema-version: "1.0"\n'
        "roles:\n"
        f"  - {role}\n"
        "purpose: >\n"
        "  Profile used to verify project-layer dispatch routing (#4114).\n"
        "specialization:\n"
        "  primary-focus: >\n"
        "    Verifying activation-aware routing of project-layer agent profiles.\n"
    )


def _write_doctrine_project_profile(repo_root: Path, profile_id: str = _PROJECT_ID) -> None:
    """Seed one doctrine project-layer profile under ``.kittify/charter-packs``."""
    profiles_dir = repo_root / ".kittify" / "charter-packs" / "agent_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / f"{profile_id}.agent.yaml").write_text(
        _profile_yaml(profile_id, name="Seeker Implementer", role="implementer"),
        encoding="utf-8",
    )


def _write_config(repo_root: Path, *, activated: list[str] | None) -> None:
    """Write ``.kittify/config.yaml`` carrying the activation state."""
    data: dict[str, object] = {}
    if activated is not None:
        data["activated_agent_profiles"] = activated
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump(data, fh)


def _write_config_with_charter_pointer(
    repo_root: Path,
    *,
    activated: list[str],
) -> None:
    """Write a migrated config: ``charter:`` pointer + charter.yaml activation.

    This is the shape the #4114 reporter's project carries — activation state
    lives in ``.kittify/charter/charter.yaml`` and ``config.yaml`` points at
    it (pack_context INV-2 two-file read).
    """
    charter_path = repo_root / ".kittify" / "charter" / "charter.yaml"
    charter_path.parent.mkdir(parents=True, exist_ok=True)
    with charter_path.open("w", encoding="utf-8") as fh:
        YAML().dump({"activated_agent_profiles": activated}, fh)
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump({"charter": ".kittify/charter/charter.yaml"}, fh)


def _ids(registry: ProfileRegistry) -> list[str]:
    return [p.profile_id for p in registry.list_all()]


class TestActivatedProjectDoctrineProfileIsRoutable:
    def test_activated_project_profile_present_and_resolvable(self, tmp_path: Path) -> None:
        """``activated_agent_profiles`` including the project id → present."""
        _write_doctrine_project_profile(tmp_path)
        _write_config(tmp_path, activated=[_PROJECT_ID])

        registry = ProfileRegistry(tmp_path)

        assert _PROJECT_ID in _ids(registry)
        assert registry.resolve(_PROJECT_ID).profile_id == _PROJECT_ID

    def test_activated_project_profile_routes_over_deactivated_builtins(
        self,
        tmp_path: Path,
    ) -> None:
        """The #4114 repro: shipped profiles off, project profile on → routes.

        With the activation set naming ONLY the project-layer profile, every
        built-in is gated out of the catalog; an implementer-verb request must
        route to the project profile — never ``ROUTER_NO_MATCH``.
        """
        _write_doctrine_project_profile(tmp_path)
        _write_config(tmp_path, activated=[_PROJECT_ID])

        decision = ActionRouter(ProfileRegistry(tmp_path)).route("Implement the tax module")

        assert decision.profile_id == _PROJECT_ID
        assert decision.action == "implement"

    def test_activated_project_profile_resolves_via_profile_hint(
        self,
        tmp_path: Path,
    ) -> None:
        """``dispatch --profile <project-id>`` resolves the activated profile."""
        _write_doctrine_project_profile(tmp_path)
        _write_config(tmp_path, activated=[_PROJECT_ID])

        decision = ActionRouter(ProfileRegistry(tmp_path)).route(
            "Add a HOUSE constant",
            profile_hint=_PROJECT_ID,
        )

        assert decision.profile_id == _PROJECT_ID
        assert decision.confidence == "exact"

    def test_charter_yaml_pointer_activation_is_honoured(self, tmp_path: Path) -> None:
        """Migrated projects: activation read from charter.yaml gates routing too."""
        _write_doctrine_project_profile(tmp_path)
        _write_config_with_charter_pointer(tmp_path, activated=[_PROJECT_ID])

        registry = ProfileRegistry(tmp_path)

        assert _PROJECT_ID in _ids(registry)


class TestDeactivatedProjectDoctrineProfileIsAbsent:
    def test_activation_set_excluding_project_profile_drops_it(self, tmp_path: Path) -> None:
        """Explicit set naming only a built-in → the project profile is ABSENT."""
        _write_doctrine_project_profile(tmp_path)
        _write_config(tmp_path, activated=[_BUILTIN_ID])

        ids = _ids(ProfileRegistry(tmp_path))

        assert _PROJECT_ID not in ids
        assert _BUILTIN_ID in ids

    def test_everything_deactivated_leaves_catalog_empty(self, tmp_path: Path) -> None:
        """Explicit empty activation set → empty catalog (gate applies to all layers)."""
        _write_doctrine_project_profile(tmp_path)
        _write_config(tmp_path, activated=[])

        registry = ProfileRegistry(tmp_path)

        assert registry.list_all() == []
        assert registry.has_profiles() is False


class TestGateInertRegime:
    def test_no_activation_key_admits_project_profile(self, tmp_path: Path) -> None:
        """Guard: with no activation key the gate is inert — project profile admitted."""
        _write_doctrine_project_profile(tmp_path)
        _write_config(tmp_path, activated=None)

        assert _PROJECT_ID in _ids(ProfileRegistry(tmp_path))

    def test_no_doctrine_dir_leaves_catalog_unchanged(self, tmp_path: Path) -> None:
        """A project with no ``.kittify/charter-packs`` tree sees no new layer (NFR-001)."""
        _write_config(tmp_path, activated=None)

        # No .kittify/charter-packs/ and no .kittify/profiles/: built-ins only.
        ids = _ids(ProfileRegistry(tmp_path))

        assert _BUILTIN_ID in ids
        assert _PROJECT_ID not in ids
