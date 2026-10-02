"""Red-first unit tests for the kind-aware write-side placement partition.

Mission ``write-surface-coherence-01KVTVZS`` WP01 (FR-001, FR-002, FR-004,
FR-010; DIRECTIVE_034 red-first).

The READ side has been kind-aware via :func:`artifact_home_for` since #2090; the
WRITE side (:func:`resolve_placement_only`) was kind-BLIND — it routed purely by
stored topology and returned the coordination ref for EVERY artifact under
coordination topology. WP01 re-partitions the planning + identity kinds onto the
primary ``target_branch`` for every topology shape and makes the write-side
projection consult the kind.

These tests pin the partition at the lowest level through the **pre-existing**
entry points (:func:`artifact_home_for` and :func:`resolve_placement_only`):

- a primary kind (``SPEC``) resolves to the primary surface / ``target_branch``
  even on a coordination-topology mission (the correctness change);
- a coord kind (``STATUS_STATE``) still resolves to the coordination branch;
- a flattened mission routes both kinds to ``target_branch`` (unchanged);
- ``resolve_placement_only`` requires the ``kind`` keyword — a no-kind call is a
  ``TypeError``, not a silent default (DECISION 1, the no-silent-flip contract).

Fixture data uses a real 26-char ULID ``mission_id`` and the derived 8-char
``mid8`` so the resolver exercises real-shaped identity, not a short fake slug.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import CommitTarget, MissionArtifactKind, MissionTopology, resolve_placement_only
from mission_runtime.artifacts import artifact_home_for
from mission_runtime.artifacts import kind_is_coordination_residue

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

# Realistic identity: a real 26-char Crockford ULID and its 8-char mid8 prefix.
_MISSION_ID = "01KVTVZS5P3QY7M8N0RAB4CDEF"
_MID8 = _MISSION_ID[:8]
_MISSION_SLUG = "write-surface-coherence-01KVTVZS"
_TARGET_BRANCH = "feat/write-surface-coherence"
# A real-shaped coordination ref: ``kitty/mission-<slug>-<mid8>``.
_COORD_BRANCH = f"kitty/mission-{_MISSION_SLUG}-{_MID8}"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    (r / ".kittify").mkdir()
    (r / ".kittify" / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\n", encoding="utf-8"
    )
    return r


def _build_mission(
    repo_root: Path,
    *,
    coordination_branch: str | None = None,
) -> None:
    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "mission_slug": _MISSION_SLUG,
        "mission_type": "software-dev",
        "target_branch": _TARGET_BRANCH,
        "friendly_name": "Write-surface coherence",
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (feature_dir / "tasks").mkdir()
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "fixture")


# ---------------------------------------------------------------------------
# artifact_home_for — read/write/commit home of a primary kind is primary
# ---------------------------------------------------------------------------


def test_artifact_home_for_spec_is_primary() -> None:
    placement_ref = CommitTarget(ref=_COORD_BRANCH)

    home = artifact_home_for(MissionArtifactKind.SPEC, placement_ref)

    assert home.read_surface == "primary"
    assert home.write_surface == "primary"
    # The commit target for a primary kind is the resolved primary ref, not the
    # coordination ref the caller happened to pass.
    assert home.commit_target == placement_ref
    # The dead ``ignores_primary_coord_residue`` field was retired (IC-07g /
    # WP17, zero external consumers) — assert the real residue authority instead.
    assert kind_is_coordination_residue(MissionArtifactKind.SPEC, MissionTopology.COORD) is False


def test_artifact_home_for_status_state_stays_placement() -> None:
    placement_ref = CommitTarget(ref=_COORD_BRANCH)

    home = artifact_home_for(MissionArtifactKind.STATUS_STATE, placement_ref)

    assert home.read_surface == "coord"
    assert home.write_surface == "coord"
    assert home.commit_target == placement_ref
    assert kind_is_coordination_residue(MissionArtifactKind.STATUS_STATE, MissionTopology.COORD) is True


def test_decision_ledger_is_primary() -> None:
    """R13 (WP12, FR-009, #5023): the decision ledger resolves the PRIMARY home.

    #3928 classified ``DECISION_LEDGER`` COORD, but its own reads/writes
    (``decisions/service.py::_ledger_dir``) already resolved PRIMARY (#4966
    AC-D2) -- the split forked ``spec-commit``'s routing (#5023). This WP
    reverses the classification to match the write side: at the WP base the
    kind is still COORD, so this assertion is RED there and GREEN once T065
    moves ``DECISION_LEDGER`` into ``_PRIMARY_ARTIFACT_KINDS``.
    """
    placement_ref = CommitTarget(ref=_COORD_BRANCH)

    home = artifact_home_for(MissionArtifactKind.DECISION_LEDGER, placement_ref)

    assert home.read_surface == "primary"
    assert home.write_surface == "primary"
    assert home.commit_target == placement_ref
    assert kind_is_coordination_residue(MissionArtifactKind.DECISION_LEDGER, MissionTopology.COORD) is False


def test_artifact_home_for_primary_metadata_is_partition_aware() -> None:
    """``PRIMARY_METADATA`` resolves the PRIMARY surface with a routed commit target.

    coord-write-placement-closure-01KYCF83 WP02 (T006, FR-002): the prior
    read-anchored ``commit_target=None`` special-case arm was deleted so
    ``PRIMARY_METADATA`` falls through to the generic ``_PRIMARY_ARTIFACT_KINDS``
    arm like every other primary planning kind, carrying the resolved
    ``placement_ref`` -- required for meta writes (``write_meta`` /
    ``_flip_phase`` / ``_bake_mission_number``) to route through the port. The
    sentinel-inertness audit (T005) confirmed the sole port consumer
    (``resolution.py:949``) never branched on ``None``-as-skip-commit, so this
    flip is a pure widening, not a behavioral break for existing consumers.
    """
    placement_ref = CommitTarget(ref=_COORD_BRANCH)

    home = artifact_home_for(MissionArtifactKind.PRIMARY_METADATA, placement_ref)

    assert home.read_surface == "primary"
    assert home.write_surface == "primary"
    assert home.commit_target == placement_ref


# ---------------------------------------------------------------------------
# resolve_placement_only — the write-side projection is kind-aware
# ---------------------------------------------------------------------------


def test_spec_resolves_to_target_branch_under_coordination(repo: Path) -> None:
    """A primary kind routes to the primary ``target_branch`` even under coord.

    Pre-fix the kind-blind resolver returned the coordination branch for ALL
    artifacts; this is the correctness change WP01 establishes.
    """
    _build_mission(repo, coordination_branch=_COORD_BRANCH)
    _git(repo, "branch", _COORD_BRANCH)

    placement = resolve_placement_only(repo, _MISSION_SLUG, kind=MissionArtifactKind.SPEC)

    assert placement.ref == _TARGET_BRANCH
    assert placement.ref != _COORD_BRANCH


def test_status_state_resolves_to_coordination_branch(repo: Path) -> None:
    """A coord kind still routes to the coordination branch under coord topology."""
    _build_mission(repo, coordination_branch=_COORD_BRANCH)
    _git(repo, "branch", _COORD_BRANCH)

    placement = resolve_placement_only(
        repo, _MISSION_SLUG, kind=MissionArtifactKind.STATUS_STATE
    )

    assert placement.ref == _COORD_BRANCH


def test_flattened_routes_both_kinds_to_target_branch(repo: Path) -> None:
    """A flattened mission (no coordination branch) routes both kinds to target."""
    _build_mission(repo)  # no coordination branch → flattened

    spec_placement = resolve_placement_only(
        repo, _MISSION_SLUG, kind=MissionArtifactKind.SPEC
    )
    status_placement = resolve_placement_only(
        repo, _MISSION_SLUG, kind=MissionArtifactKind.STATUS_STATE
    )

    assert spec_placement.ref == _TARGET_BRANCH
    assert status_placement.ref == _TARGET_BRANCH


# ---------------------------------------------------------------------------
# DECISION 1 — kind is REQUIRED (no silent default flip)
# ---------------------------------------------------------------------------


def test_resolve_placement_only_requires_kind(repo: Path) -> None:
    """Calling without ``kind`` is a ``TypeError`` — not a silent default.

    A default kind would silently flip every un-threaded caller coord→primary the
    moment WP01 lands; a required keyword forces every call site to declare intent.
    """
    _build_mission(repo, coordination_branch=_COORD_BRANCH)
    _git(repo, "branch", _COORD_BRANCH)

    with pytest.raises(TypeError):
        resolve_placement_only(repo, _MISSION_SLUG)  # type: ignore[call-arg]
