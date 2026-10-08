"""Org-pack visibility for agent-profile projection (WP04 — FR-006/#2166).

Projection must emit the **charter-activation-admitted** org agents to the host
surface and record them in the projection manifest with a non-builtin
``source_layer``.  These tests drive the *pre-existing* projection surface
(``default_profile_repository`` → ``ProfileProjector.project``) — never WP02's
internal resolver API (C-005) — over a real-format org-pack scratch repo
(C-007), and pin the two-regime contract plus the no-org-packs regression:

* **admitted** (activation absent OR explicitly included) → the org analyst is
  projected with ``source_layer == "org"`` and a non-None ``source_path``;
* **de-activated** (explicit list excluding it) → the org analyst is ABSENT from
  the projected set (NFR-002 negative regime);
* the seeded ``.kittify/agent_profiles`` project profile is preserved in BOTH
  regimes (C-002, project layer untouched);
* **no org packs declared** → projection is byte-identical to a built-in +
  project-layer-only projection (NFR-001).
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

# A real-format org pack: kebab pack name + an org-namespaced profile id.
_PACK_NAME = "orgzilla-governance-pack"
_ORG_ANALYST_ID = "orgzilla-org-analyst"
# A real-format project-layer profile id (lives in ``.kittify/agent_profiles``).
_PROJECT_ID = "projecto-project-architect"
# A real built-in profile id — used to drive the de-activated (exclude) regime.
_BUILTIN_ID = "python-pedro"

_TOOL_KEY = "claude"


def _agent_yaml(profile_id: str, *, name: str, role: str) -> str:
    """Render a minimal-but-valid ``.agent.yaml`` document body."""
    return (
        f"profile-id: {profile_id}\n"
        f"name: {name}\n"
        "description: Profile contributed for projection-visibility fixtures\n"
        'schema-version: "1.0"\n'
        "roles:\n"
        f"  - {role}\n"
        "purpose: >\n"
        "  Profile used to verify charter-activation-aware projection of org-pack\n"
        "  agents onto the host surface and projection manifest.\n"
        "specialization:\n"
        "  primary-focus: >\n"
        "    Organisation- or project-specific tasks for projection fixtures.\n"
        "  avoidance-boundary: unrelated work\n"
    )


def _write_org_pack(repo_root: Path) -> Path:
    """Create a real-format org pack (``<pack>/agent_profiles/<id>.agent.yaml``)."""
    pack_root = repo_root / "org-packs" / _PACK_NAME
    profiles_dir = pack_root / "agent_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / f"{_ORG_ANALYST_ID}.agent.yaml").write_text(
        _agent_yaml(_ORG_ANALYST_ID, name="Orgzilla Org Analyst", role="researcher"),
        encoding="utf-8",
    )
    return pack_root


def _seed_project_profile(repo_root: Path) -> None:
    """Seed a profile into the ``.kittify/agent_profiles`` project layer (C-002)."""
    project_dir = repo_root / ".kittify" / "agent_profiles"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / f"{_PROJECT_ID}.agent.yaml").write_text(
        _agent_yaml(_PROJECT_ID, name="Projecto Project Architect", role="architect"),
        encoding="utf-8",
    )


def _write_config(
    repo_root: Path, pack_root: Path | None, *, activated: list[str] | None
) -> None:
    """Write ``.kittify/config.yaml`` declaring the org pack and activation state.

    ``pack_root`` of ``None`` omits the ``doctrine.org.packs`` declaration (the
    no-org-packs regime).  ``activated`` of ``None`` omits the
    ``activated_agent_profiles`` key (absent regime); a list writes it verbatim.
    """
    data: dict[str, object] = {}
    if pack_root is not None:
        data["charter_packs"] = {
            "org": {"packs": [{"name": _PACK_NAME, "local_path": str(pack_root)}]}
        }
    if activated is not None:
        data["activated_agent_profiles"] = activated
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump(data, fh)


def _project(repo_root: Path) -> dict[str, NativeAgentProfile]:
    """Drive the pre-existing projection surface, keyed by profile URN."""
    repo = default_profile_repository(repo_root)
    projector = ProfileProjector(repo)
    return {p.profile_urn: p for p in projector.project(_TOOL_KEY, repo_root)}


def _urn(profile_id: str) -> str:
    return f"agent_profile:{profile_id}"


# ---------------------------------------------------------------------------
# T011 — two-regime projection (admitted / de-activated) with manifest source_layer
# ---------------------------------------------------------------------------


class TestOrgProjectionTwoRegime:
    def test_admitted_org_profile_projected_with_org_source_layer(
        self, tmp_path: Path
    ) -> None:
        """Activation absent → org analyst projected; manifest entry tagged ``org``."""
        pack_root = _write_org_pack(tmp_path)
        _seed_project_profile(tmp_path)
        _write_config(tmp_path, pack_root, activated=None)

        projected = _project(tmp_path)

        org = projected.get(_urn(_ORG_ANALYST_ID))
        assert org is not None, "admitted org profile must be projected (#2166)"
        # Manifest-provenance correctness is the #2166 acceptance hinge: assert
        # the actual value, not merely presence.
        assert org.source_layer == "org"
        assert org.source_path is not None
        assert org.source_path.endswith(f"{_ORG_ANALYST_ID}.agent.yaml")
        # Project layer preserved (C-002).
        assert _urn(_PROJECT_ID) in projected
        assert projected[_urn(_PROJECT_ID)].source_layer == "project"

    def test_explicit_include_keeps_org_profile_projected(
        self, tmp_path: Path
    ) -> None:
        """Explicit list including the org id → projected with ``org`` provenance."""
        pack_root = _write_org_pack(tmp_path)
        _seed_project_profile(tmp_path)
        _write_config(tmp_path, pack_root, activated=[_ORG_ANALYST_ID])

        projected = _project(tmp_path)

        org = projected.get(_urn(_ORG_ANALYST_ID))
        assert org is not None
        assert org.source_layer == "org"

    def test_deactivated_org_profile_absent_from_projection(
        self, tmp_path: Path
    ) -> None:
        """Explicit list excluding the org id → it is ABSENT (NFR-002 negative)."""
        pack_root = _write_org_pack(tmp_path)
        _seed_project_profile(tmp_path)
        # Activate only a built-in id; the org analyst is de-activated.
        _write_config(tmp_path, pack_root, activated=[_BUILTIN_ID])

        projected = _project(tmp_path)

        assert _urn(_ORG_ANALYST_ID) not in projected
        # No projected entry carries org provenance once the org profile is gated.
        assert all(p.source_layer != "org" for p in projected.values())
        # Project layer still projected in the de-activated regime (C-002).
        assert _urn(_PROJECT_ID) in projected


# ---------------------------------------------------------------------------
# T013 — no-org-packs regression (NFR-001): byte-identical projection
# ---------------------------------------------------------------------------


def _signature(projected: dict[str, NativeAgentProfile]) -> list[tuple[str, str, str | None]]:
    """A stable, order-sensitive projection signature for equality assertions."""
    return [
        (p.profile_urn, p.source_layer, p.source_path)
        for p in sorted(projected.values(), key=lambda n: n.profile_urn)
    ]


class TestNoOrgPacksRegression:
    def test_no_org_packs_projection_is_byte_identical(self, tmp_path: Path) -> None:
        """No ``doctrine.org.packs`` declared → projection == built-in + project only.

        Compares a project that declares an org pack but with NO config against a
        baseline project with no config at all; both must project the identical
        set (no org entry, same ordering / source_layer), proving the org overlay
        contributes nothing when no packs are declared.
        """
        # Baseline: built-in + project layer only, no config, no packs.
        baseline_root = tmp_path / "baseline"
        baseline_root.mkdir()
        _seed_project_profile(baseline_root)
        baseline = _project(baseline_root)

        # Subject: same project layer, an org pack exists on disk but config does
        # NOT declare ``doctrine.org.packs`` → org overlay must stay empty.
        subject_root = tmp_path / "subject"
        subject_root.mkdir()
        _write_org_pack(subject_root)
        _seed_project_profile(subject_root)
        _write_config(subject_root, pack_root=None, activated=None)
        subject = _project(subject_root)

        assert _signature(subject) == _signature(baseline)
        # No org provenance leaks when no packs are declared.
        assert all(p.source_layer != "org" for p in subject.values())
        assert _urn(_ORG_ANALYST_ID) not in subject


if __name__ == "__main__":  # pragma: no cover - manual red-first probe
    raise SystemExit(pytest.main([__file__, "-q"]))
