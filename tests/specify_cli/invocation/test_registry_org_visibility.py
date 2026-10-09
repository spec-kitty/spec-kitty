"""WP03 T007/T010 — org-pack visibility in the dispatch routing catalog (FR-004).

These tests pin the **two-regime** contract over a real-format org pack (C-007):

* admitted (activation absent OR explicit include) → the activated org profile
  is present in ``ProfileRegistry.list_all()`` (the dispatch routing catalog);
* de-activated (explicit list excluding it) → it is ABSENT;
* in BOTH regimes the existing ``.kittify/profiles`` project profile is still
  present (the project layer is preserved — C-002/FR-007);
* no org packs declared → ``list_all()`` is byte-identical to the project layer
  alone (NFR-001), i.e. the org overlay is empty and never reorders or mutates
  the project/built-in set.

The org overlay is the WP02 activation-filtered subset
(``resolve_activated_org_profiles``); a raw ``org_dirs`` splice is forbidden
(C-008) and is enforced structurally by the WP05 gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.profiles import AgentProfileRepository
from specify_cli.invocation.registry import ProfileRegistry

pytestmark = pytest.mark.fast

_PACK_NAME = "orgzilla-governance-pack"
_ORG_ANALYST_ID = "orgzilla-org-analyst"
# A project-layer profile id shipped under .kittify/profiles — distinct from
# any org-provenance id so the layers never alias.
_PROJECT_ID = "acme-project-implementer"
# A real built-in profile id used in the de-activated activation list so the
# explicit-exclude regime still admits *something* org-orthogonal.
_BUILTIN_ID = "python-pedro"


def _profile_yaml(profile_id: str, *, name: str, role: str) -> str:
    """Render a minimal-but-valid ``.agent.yaml`` document body."""
    return (
        f"profile-id: {profile_id}\n"
        f"name: {name}\n"
        "description: Real-format profile for org-visibility fixtures\n"
        'schema-version: "1.0"\n'
        "roles:\n"
        f"  - {role}\n"
        "purpose: >\n"
        "  Profile used to verify charter-activation-aware dispatch routing.\n"
        "specialization:\n"
        "  primary-focus: >\n"
        "    Verifying activation-aware visibility of agent profiles.\n"
    )


def _write_org_pack(repo_root: Path) -> Path:
    """Create a real-format org pack and return its root directory."""
    pack_root = repo_root / "org-packs" / _PACK_NAME
    profiles_dir = pack_root / "agent_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / f"{_ORG_ANALYST_ID}.agent.yaml").write_text(
        _profile_yaml(_ORG_ANALYST_ID, name="Orgzilla Org Analyst", role="researcher"),
        encoding="utf-8",
    )
    return pack_root


def _write_project_profile(repo_root: Path) -> None:
    """Seed one project-layer profile under ``.kittify/profiles``."""
    project_dir = repo_root / ".kittify" / "profiles"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / f"{_PROJECT_ID}.agent.yaml").write_text(
        _profile_yaml(_PROJECT_ID, name="Acme Project Implementer", role="implementer"),
        encoding="utf-8",
    )


def _write_config(repo_root: Path, pack_root: Path, *, activated: list[str] | None) -> None:
    """Write ``.kittify/config.yaml`` declaring the org pack and activation state."""
    data: dict[str, object] = {
        "charter_packs": {"org": {"packs": [{"name": _PACK_NAME, "local_path": str(pack_root)}]}},
    }
    if activated is not None:
        data["activated_agent_profiles"] = activated
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump(data, fh)


def _ids(registry: ProfileRegistry) -> list[str]:
    return [p.profile_id for p in registry.list_all()]


class TestTwoRegimeOrgVisibility:
    def test_admitted_org_profile_present_project_preserved(self, tmp_path: Path) -> None:
        """Activation absent → org analyst present; project profile preserved."""
        pack_root = _write_org_pack(tmp_path)
        _write_project_profile(tmp_path)
        _write_config(tmp_path, pack_root, activated=None)

        ids = _ids(ProfileRegistry(tmp_path))

        assert _ORG_ANALYST_ID in ids
        assert _PROJECT_ID in ids

    def test_deactivated_org_profile_absent_project_preserved(self, tmp_path: Path) -> None:
        """Explicit list excluding the org id → it is ABSENT; project preserved."""
        pack_root = _write_org_pack(tmp_path)
        _write_project_profile(tmp_path)
        # Activate only a built-in id — the org analyst is excluded.
        _write_config(tmp_path, pack_root, activated=[_BUILTIN_ID])

        ids = _ids(ProfileRegistry(tmp_path))

        assert _ORG_ANALYST_ID not in ids
        # The project layer is never gated by org activation (C-002/FR-007).
        assert _PROJECT_ID in ids

    def test_explicit_include_keeps_org_profile_present(self, tmp_path: Path) -> None:
        """Explicit list including the org id → present (positive control)."""
        pack_root = _write_org_pack(tmp_path)
        _write_project_profile(tmp_path)
        _write_config(tmp_path, pack_root, activated=[_ORG_ANALYST_ID])

        ids = _ids(ProfileRegistry(tmp_path))

        assert _ORG_ANALYST_ID in ids
        assert _PROJECT_ID in ids


class TestNoOrgPacksRegression:
    """T010 — no org packs declared → byte-identical to the project layer (NFR-001)."""

    def test_list_all_byte_identical_to_project_layer(self, tmp_path: Path) -> None:
        """Absence of org packs never perturbs the built-in+project catalog.

        Restored (landing-fold regression fix, charter-sole-door-bypass-
        closure-01KZ3WAA): WP01 unified ``ProfileRegistry``'s builder to
        always compute ``active_languages=infer_repo_languages(repo_root)``.
        A prior revision of that unification made ``infer_repo_languages``
        return an *explicitly empty* list for a ``tmp_path`` with no compiled
        charter/interview data, which narrowed the built-in layer down to
        language-agnostic profiles — breaking byte-identity with a bare,
        unfiltered ``AgentProfileRepository`` baseline and forcing this test
        onto an independently-rebuilt two-primitive baseline instead (with a
        ``._inner`` reach-around fixed in the immediately preceding commit).
        ``infer_repo_languages`` now resolves that "truly nothing configured
        yet" case to ``None`` ("unknown" — admits every scoped profile), so
        the bare, unfiltered baseline is byte-identical to
        ``ProfileRegistry(tmp_path).list_all()`` again, and the original,
        simpler, non-fakeable assertion is restored.
        """
        _write_project_profile(tmp_path)
        # No .kittify/config.yaml org packs at all.
        registry = ProfileRegistry(tmp_path)

        baseline_repo = AgentProfileRepository(
            project_dir=tmp_path / ".kittify" / "profiles",
        )
        baseline_ids = [p.profile_id for p in baseline_repo.list_all()]

        assert _ids(registry) == baseline_ids
        # The org-provenance id never appears when no pack is declared.
        assert _ORG_ANALYST_ID not in _ids(registry)
        # Project profile still resolvable through the project layer.
        assert _PROJECT_ID in _ids(registry)
