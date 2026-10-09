"""Built-in end-to-end characterization pin for governance-profile fail-loud (#3629 p2).

WP03 / T013. The built-in guard
(:func:`doctrine.drg.migration.extractor.assert_governance_scope_edges_resolve`)
is already wired into :func:`~doctrine.drg.migration.extractor.generate_graph`
and its unit tests exercise it against *synthetic* edges. This module drives the
whole ``generate_graph`` pipeline against a real, fully-minted node universe so
the WIRING (not just the pure check) is pinned: a fictional ``selected_*`` id in
a built-in ``governance-profile.yaml`` must raise a ``ValueError`` naming
``mission_type:field=id``, and a valid selection must not raise.

This is a **characterization pin**, not a red-first bug fix (squad finding G8):
the guard already passes on arrival. It exists to protect the existing wiring
from silent regression, and it asserts the full ``mission_type:field=id`` token
shape that the extractor's own end-to-end test only partially checks.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from charter.offering.drg.migration.extractor import generate_graph

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]

# tests/charter_offering/drg/migration/ -> repo root is four parents up.
_REPO_ROOT = Path(__file__).resolve().parents[4]

_RESEARCH_PROFILE_REL = Path("missions") / "research" / "governance-profile.yaml"
_EMPTY_AGENT_PROFILES_MARKER = "selected_agent_profiles: []"


def _copy_real_pack_root(tmp_path: Path) -> Path:
    """Copy the shipped ``packs/built-in`` tree so a test may mutate a profile.

    ``generate_graph`` reads the missions root under the given doctrine root, so
    a real copy is the smallest fixture that exercises every minting pass the
    guard depends on (artifact/action/discovery/mission-type/step-contract).
    """
    pack_copy = tmp_path / "pack-root"
    shutil.copytree(_REPO_ROOT / "packs" / "built-in", pack_copy)
    return pack_copy


def _inject_selected_agent_profile(pack_root: Path, selected_id: str) -> None:
    """Replace research's empty ``selected_agent_profiles`` with one bare id."""
    profile_path = pack_root / _RESEARCH_PROFILE_REL
    original = profile_path.read_text(encoding="utf-8")
    assert _EMPTY_AGENT_PROFILES_MARKER in original, (
        "fixture drift: research governance-profile.yaml no longer ships an empty selected_agent_profiles list to mutate"
    )
    profile_path.write_text(
        original.replace(
            _EMPTY_AGENT_PROFILES_MARKER,
            f"selected_agent_profiles:\n  - {selected_id}",
            1,
        ),
        encoding="utf-8",
    )


class TestGenerateGraphGovernanceScopeWiring:
    """End-to-end pin on ``generate_graph``'s governance-scope fail-loud wiring."""

    def test_fictional_selection_raises_naming_mission_type_field_and_id(self, tmp_path: Path) -> None:
        pack_root = _copy_real_pack_root(tmp_path)
        _inject_selected_agent_profile(pack_root, "does-not-exist")

        with pytest.raises(
            ValueError,
            match=r"research:selected_agent_profiles=does-not-exist",
        ):
            generate_graph(pack_root, tmp_path / "output" / "graph.yaml")

    def test_valid_selection_does_not_raise(self, tmp_path: Path) -> None:
        pack_root = _copy_real_pack_root(tmp_path)
        # ``researcher-robbie`` is a real shipped agent_profile, so selecting it is
        # a resolvable governance selection -- the guard must stay silent.
        _inject_selected_agent_profile(pack_root, "researcher-robbie")

        graph = generate_graph(pack_root, tmp_path / "output" / "graph.yaml")

        scope_edge_targets = {edge.target for edge in graph.edges if edge.source == "mission_type:research" and edge.relation.value == "scope"}
        assert "agent_profile:researcher-robbie" in scope_edge_targets, "a valid governance selection must mint its mission_type --scope--> edge, not be dropped"
