"""Unit tests for the authoritative commit-surface rule (mission ``coord-commit-surface-authority`` WP01).

Exhaustive matrix coverage of the two pure functions in
``specify_cli.coordination.surface_authority`` plus the runtime no-op/wrong-surface
classifier, the canonical exit-code mapping, and the layering guard (the module
must NOT import ``specify_cli.cli.*``).

Contract: ``kitty-specs/coord-commit-surface-authority-01M1M553/contracts/authoritative-surface.md``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, MissionTopology
from specify_cli.coordination.surface_authority import (
    REMEDY_PROTECTED_PRIMARY,
    REMEDY_WRONG_SURFACE,
    NoOp,
    Refuse,
    RouteToCoord,
    SurfaceVerdict,
    _classify_noncommit_outcome,
    _exit_code_for,
    resolve_surface_authority,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PRIMARY_TARGET = "main"
_COORD_REF = "kitty/mission-my-slug-ABCD1234"

# Representative kinds for each partition (the rule keys on the PRIMARY vs COORD
# partition, not on the specific member).
_PRIMARY_KIND = MissionArtifactKind.SPEC
_COORD_KIND = MissionArtifactKind.STATUS_STATE

_COORD_TOPOLOGIES = (MissionTopology.COORD, MissionTopology.LANES_WITH_COORD)
_ALL_TOPOLOGIES = (
    MissionTopology.SINGLE_BRANCH,
    MissionTopology.LANES,
    MissionTopology.COORD,
    MissionTopology.LANES_WITH_COORD,
)


# ---------------------------------------------------------------------------
# T002/T003 — resolve_surface_authority (full matrix)
# ---------------------------------------------------------------------------


def _expected_verdict(*, is_coord_kind: bool, topology: MissionTopology, protected: bool) -> SurfaceVerdict:
    """Independent re-derivation of the contract §2 rules 1–4 (oracle for the matrix)."""
    routes_coord = topology in _COORD_TOPOLOGIES
    use_coord = routes_coord and is_coord_kind
    if use_coord:
        if protected:
            return SurfaceVerdict("coordination", _COORD_REF, RouteToCoord())
        return SurfaceVerdict("primary", _PRIMARY_TARGET, None)
    if protected:
        return SurfaceVerdict("primary", _PRIMARY_TARGET, Refuse(REMEDY_PROTECTED_PRIMARY))
    return SurfaceVerdict("primary", _PRIMARY_TARGET, None)


@pytest.mark.parametrize("artifact_kind", [_PRIMARY_KIND, _COORD_KIND])
@pytest.mark.parametrize("topology", _ALL_TOPOLOGIES)
@pytest.mark.parametrize("primary_protected", [True, False])
@pytest.mark.parametrize("current_is_primary", [True, False])
def test_resolve_surface_authority_full_matrix(
    artifact_kind: MissionArtifactKind,
    topology: MissionTopology,
    primary_protected: bool,
    current_is_primary: bool,
) -> None:
    current_branch = _PRIMARY_TARGET if current_is_primary else "feature/x"
    verdict = resolve_surface_authority(
        topology,
        _PRIMARY_TARGET,
        primary_protected,
        current_branch,
        artifact_kind,
        coord_ref=_COORD_REF,
    )
    expected = _expected_verdict(
        is_coord_kind=artifact_kind is _COORD_KIND,
        topology=topology,
        protected=primary_protected,
    )
    assert verdict == expected, f"kind={artifact_kind.name} topology={topology.name} protected={primary_protected} current_is_primary={current_is_primary}"
    # Exit-code parity for the resolved verdict.
    expected_exit = 1 if isinstance(expected.non_committable, Refuse) else 0
    assert _exit_code_for(verdict.non_committable) == expected_exit


def test_verdict_independent_of_checkout() -> None:
    """The decision keys on TARGET protection, not the current checkout (contract §1 tripwire)."""
    on_primary = resolve_surface_authority(MissionTopology.COORD, _PRIMARY_TARGET, True, _PRIMARY_TARGET, _COORD_KIND, coord_ref=_COORD_REF)
    on_feature = resolve_surface_authority(MissionTopology.COORD, _PRIMARY_TARGET, True, "feature/x", _COORD_KIND, coord_ref=_COORD_REF)
    assert on_primary == on_feature


def test_route_to_coord_lifecycle_kind_coord_protected() -> None:
    """Rule 1: lifecycle-kind, coord topology, protected primary → RouteToCoord, exit 0."""
    verdict = resolve_surface_authority(
        MissionTopology.LANES_WITH_COORD,
        _PRIMARY_TARGET,
        True,
        "feature/x",
        _COORD_KIND,
        coord_ref=_COORD_REF,
    )
    assert verdict.surface == "coordination"
    assert verdict.ref == _COORD_REF
    assert isinstance(verdict.non_committable, RouteToCoord)
    assert _exit_code_for(verdict.non_committable) == 0


def test_coord_kind_unprotected_routes_to_primary() -> None:
    """Rule 2: coord-kind on an UNPROTECTED primary → coord routing inert → primary, committable."""
    verdict = resolve_surface_authority(MissionTopology.COORD, _PRIMARY_TARGET, False, "feature/x", _COORD_KIND)
    assert verdict.surface == "primary"
    assert verdict.ref == _PRIMARY_TARGET
    assert verdict.non_committable is None


def test_planning_kind_protected_primary_refuses() -> None:
    """Rule 3: planning-kind on a protected primary → Refuse, exit 1, with the shared remedy."""
    verdict = resolve_surface_authority(MissionTopology.COORD, _PRIMARY_TARGET, True, _PRIMARY_TARGET, _PRIMARY_KIND)
    assert verdict.surface == "primary"
    assert isinstance(verdict.non_committable, Refuse)
    assert verdict.non_committable.remedy == REMEDY_PROTECTED_PRIMARY
    assert _exit_code_for(verdict.non_committable) == 1


def test_primary_kind_unprotected_commits_directly() -> None:
    """Rule 4: primary-kind on an unprotected branch → primary, committable."""
    verdict = resolve_surface_authority(MissionTopology.SINGLE_BRANCH, "feature/x", False, "feature/x", _PRIMARY_KIND)
    assert verdict.surface == "primary"
    assert verdict.ref == "feature/x"
    assert verdict.non_committable is None


def test_coord_ref_defaults_to_primary_target_when_omitted() -> None:
    """A coordination verdict without an explicit coord_ref falls back to primary_target."""
    verdict = resolve_surface_authority(MissionTopology.COORD, _PRIMARY_TARGET, True, _PRIMARY_TARGET, _COORD_KIND)
    assert verdict.surface == "coordination"
    assert verdict.ref == _PRIMARY_TARGET


def test_coord_kind_under_non_coord_topology_on_protected_refuses() -> None:
    """A coord-kind under a NON-coord topology lands on primary; protected → Refuse (no coord route)."""
    verdict = resolve_surface_authority(MissionTopology.LANES, _PRIMARY_TARGET, True, _PRIMARY_TARGET, _COORD_KIND)
    assert verdict.surface == "primary"
    assert isinstance(verdict.non_committable, Refuse)


# ---------------------------------------------------------------------------
# Rule 5 — _classify_noncommit_outcome (wrong-surface→Refuse, no-op→NoOp)
# ---------------------------------------------------------------------------


def test_classify_wrong_surface_is_refuse_never_noop() -> None:
    """The load-bearing rule: ``no_op_wrong_surface`` maps to Refuse, NOT a NoOp."""
    outcome = _classify_noncommit_outcome("no_op_wrong_surface")
    assert isinstance(outcome, Refuse)
    assert outcome.remedy == REMEDY_WRONG_SURFACE
    assert _exit_code_for(outcome) == 1


@pytest.mark.parametrize(
    "status,reason,expected_reason",
    [
        ("unchanged", "no_op_already_committed", "no_op_already_committed"),
        ("unchanged", "no_op_no_changes", "no_op_no_changes"),
        ("unchanged", None, "no_op"),
        ("no_op_already_committed", None, "no_op_already_committed"),
        ("no_op_no_changes", None, "no_op_no_changes"),
    ],
)
def test_classify_genuine_noop_is_noop_exit_0(status: str, reason: str | None, expected_reason: str) -> None:
    outcome = _classify_noncommit_outcome(status, reason)
    assert isinstance(outcome, NoOp)
    assert outcome.reason == expected_reason
    assert _exit_code_for(outcome) == 0


def test_classify_committed_is_none() -> None:
    assert _classify_noncommit_outcome("committed") is None


def test_classify_error_is_none() -> None:
    """An error is a failure handled separately — not a surface verdict."""
    assert _classify_noncommit_outcome("error") is None


def test_classify_unknown_status_fails_loud() -> None:
    with pytest.raises(ValueError, match="Unrecognized commit outcome status"):
        _classify_noncommit_outcome("mystery")


# ---------------------------------------------------------------------------
# _exit_code_for mapping
# ---------------------------------------------------------------------------


def test_exit_code_for_mapping() -> None:
    assert _exit_code_for(None) == 0
    assert _exit_code_for(RouteToCoord()) == 0
    assert _exit_code_for(NoOp("no_op")) == 0
    assert _exit_code_for(Refuse("remedy")) == 1


# ---------------------------------------------------------------------------
# Layering guard — coordination/ must NOT import cli/
# ---------------------------------------------------------------------------


def _module_path() -> Path:
    import specify_cli.coordination.surface_authority as mod

    path = mod.__file__
    assert path is not None
    return Path(path)


def test_module_has_no_cli_imports() -> None:
    """``coordination.surface_authority`` must not import ``specify_cli.cli.*`` (layering)."""
    tree = ast.parse(_module_path().read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("specify_cli.cli"):
            offenders.append(node.module)
        elif isinstance(node, ast.Import):
            offenders.extend(alias.name for alias in node.names if alias.name.startswith("specify_cli.cli"))
    assert offenders == [], f"coordination module imports cli layer: {offenders}"
