"""Org-tier governance-profile fail-loud coverage through the PRODUCTION path.

Two tiers author governance selections; before mission #3629 only the built-in
tier was read and guarded. An org pack carries its governance at
``<pack_root>/mission_types/<type>/governance-profile.yaml`` -- a path no
extraction pass ever read, so an org-tier ``selected_*`` typo was neither minted
into the DRG nor caught (a total no-op). This module pins the net-new behaviour
as delivered on the SAME path the runtime consumers (``mission_step_contracts``
executor and ``charter.action_governance_bundle``) use:

* :func:`doctrine.drg.org_governance.collect_org_governance_scope_edges` +
  :func:`doctrine.drg.org_pack_loader._collect_governance_scope_edges` mint the
  org-tier ``mission_type --scope--> <artifact>`` edges so a selection reaches
  the merged DRG (T014); and
* :func:`charter._drg_helpers.load_validated_graph` runs
  :func:`doctrine.drg.validator.assert_valid` on the fully-merged graph, whose
  :func:`~doctrine.drg.validator.validate_dangling_references` escalates a
  dangling governance-scope target to :class:`~doctrine.drg.validator.DRGValidationError`
  naming the offending node. No separate governance-scope guard is needed: a bad
  ``selected_*`` becomes an ordinary dangling scope edge that the existing merged-
  graph validation already raises on.

The fail-loud is driven end-to-end through the production loader chain
(``.kittify/config.yaml`` -> :func:`charter.drg.load_org_drg` ->
:func:`~charter._drg_helpers.load_validated_graph`) -- the exact call the
executor and action-doctrine-bundle make -- plus the edge-minting is asserted
directly (a valid selection mints its scope edge; a fictional one becomes a
dangling edge the validation raises on).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from charter.activation._drg_helpers import load_validated_graph
from charter.activation.drg_activation import load_org_drg
from charter.offering.drg.models import Relation
from charter.offering.drg.validator import DRGValidationError

pytestmark = [pytest.mark.unit, pytest.mark.corpus]

# A real built-in mission type + a real built-in agent profile, so the scope
# edge's *source* resolves and only a fictional *target* can dangle.
_MISSION_TYPE = "plan"
_VALID_PROFILE = "analyst-annie"
_FICTIONAL_PROFILE = "does-not-exist"


def _write_org_pack(pack_root: Path, selected_agent_profiles: list[str]) -> None:
    """Materialise an org pack whose per-type governance profile selects profiles.

    Writes the ``drg/fragment.yaml`` :func:`load_org_pack` requires plus the
    org-tier ``mission_types/<type>/governance-profile.yaml`` the loader reads.
    """
    drg_dir = pack_root / "drg"
    drg_dir.mkdir(parents=True)
    (drg_dir / "fragment.yaml").write_text("nodes: []\nedges: []\n", encoding="utf-8")

    profile_dir = pack_root / "mission_types" / _MISSION_TYPE
    profile_dir.mkdir(parents=True)
    (profile_dir / "governance-profile.yaml").write_text(
        yaml.safe_dump(
            {
                "id": _MISSION_TYPE,
                "mission_type": _MISSION_TYPE,
                "selected_agent_profiles": selected_agent_profiles,
            }
        ),
        encoding="utf-8",
    )


def _register_pack(repo_root: Path, pack_root: Path) -> None:
    """Register *pack_root* as an org pack in ``.kittify/config.yaml``."""
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        yaml.safe_dump({"charter_packs": {"org": {"packs": [{"name": "gov-pack", "local_path": str(pack_root)}]}}}),
        encoding="utf-8",
    )


def _load_merged_via_production_path(repo_root: Path):
    """Load the merged DRG exactly as the runtime consumers do.

    Mirrors ``mission_step_contracts.executor`` and
    ``charter.action_governance_bundle``:
    ``load_validated_graph(repo_root, org_fragments=load_org_drg(repo_root, strict=False))``.
    Raises :class:`DRGValidationError` (via ``assert_valid``) on a dangling
    governance-scope target.
    """
    fragments = load_org_drg(repo_root, strict=False)
    return load_validated_graph(repo_root, org_fragments=fragments)


# ---------------------------------------------------------------------------
# Production path: config.yaml -> load_org_drg -> load_validated_graph
# ---------------------------------------------------------------------------


class TestOrgGovernanceScopeProductionPath:
    def test_fictional_selection_fails_loud_naming_the_target(self, tmp_path: Path) -> None:
        """A nonexistent ``selected_*`` becomes a dangling scope edge that the
        merged-graph validation raises on -- the production fail-loud, no
        dedicated governance-scope guard needed."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        pack_root = tmp_path / "pack"
        _write_org_pack(pack_root, [_FICTIONAL_PROFILE])
        _register_pack(repo_root, pack_root)

        with pytest.raises(
            DRGValidationError,
            match=rf"agent_profile:{_FICTIONAL_PROFILE}",
        ):
            _load_merged_via_production_path(repo_root)

    def test_valid_selection_resolves_and_mints_its_scope_edge(self, tmp_path: Path) -> None:
        """A resolvable selection does not raise and reaches the merged DRG as a
        ``mission_type --scope--> agent_profile`` edge."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        pack_root = tmp_path / "pack"
        _write_org_pack(pack_root, [_VALID_PROFILE])
        _register_pack(repo_root, pack_root)

        merged = _load_merged_via_production_path(repo_root)

        scope_targets = {edge.target for edge in merged.edges if edge.source == f"mission_type:{_MISSION_TYPE}" and edge.relation is Relation.SCOPE}
        assert f"agent_profile:{_VALID_PROFILE}" in scope_targets, (
            "the org-tier governance selection must reach the merged DRG as a mission_type --scope--> edge, not be silently unread"
        )


# ---------------------------------------------------------------------------
# Edge-minting in isolation (the real fix WP04 keeps)
# ---------------------------------------------------------------------------


class TestOrgGovernanceScopeEdgeMinting:
    def test_org_loader_mints_scope_edge_for_selection(self, tmp_path: Path) -> None:
        """``load_org_pack`` projects a ``selected_*`` entry into a
        ``mission_type --scope--> <artifact>`` fragment edge (T014)."""
        from charter.offering.drg.org_pack_loader import load_org_pack

        pack_root = tmp_path / "pack"
        _write_org_pack(pack_root, [_VALID_PROFILE])

        fragment = load_org_pack("gov-pack", pack_root, 1)

        minted = {(edge.source, str(edge.relation), edge.target) for edge in fragment.edges}
        assert (
            f"mission_type:{_MISSION_TYPE}",
            "scope",
            f"agent_profile:{_VALID_PROFILE}",
        ) in minted

    def test_fictional_selection_is_minted_as_a_scope_edge(self, tmp_path: Path) -> None:
        """A fictional ``selected_*`` is still minted -- it becomes a dangling
        scope edge in the fragment, which the merged-graph validation (not a
        pre-merge single-pack read) then raises on."""
        from charter.offering.drg.org_pack_loader import load_org_pack

        pack_root = tmp_path / "pack"
        _write_org_pack(pack_root, [_FICTIONAL_PROFILE])

        fragment = load_org_pack("gov-pack", pack_root, 1)

        minted = {(edge.source, str(edge.relation), edge.target) for edge in fragment.edges}
        assert (
            f"mission_type:{_MISSION_TYPE}",
            "scope",
            f"agent_profile:{_FICTIONAL_PROFILE}",
        ) in minted
