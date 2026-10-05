"""Tests for commit_router.commit_for_mission (WP02 / T009; write-surface-coherence WP02).

Covers:
- Coordination kind under coord topology → materialises coordination worktree +
  lands on coord branch.
- Primary kind → direct commit (no materialiser called), even under coord topology
  (write-surface-coherence WP02: the planning→coord route is removed).
- Idempotent (unchanged artifact → ``unchanged`` status).
- #1718 preserved: materialisation happens at the commit boundary, not at read time.
- NEGATIVE variant: stubbing the materialiser causes a test failure (proves the
  materialiser is actually called on the coordination path).

``commit_for_mission`` now takes a REQUIRED ``kind`` keyword
(write-surface-coherence WP02): a ``_PRIMARY_ARTIFACT_KINDS`` member resolves to
the primary ``target_branch`` for every topology and NEVER routes through
coordination; a coordination kind keeps the topology-routed placement. The
fixtures stub ``resolve_placement_only`` (the kind-aware placement),
``resolve_topology`` (the routing topology), AND ``_resolve_mission_target_branch``
(the primary ref the router compares the placement against) so the three legs
stay consistent.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from typing import TYPE_CHECKING

import pytest

from mission_runtime import MissionArtifactKind, is_primary_artifact_kind
from specify_cli.coordination.commit_outcome import (
    COORD_RECORD_IN_ROOT_CHECKOUT,
    COORD_SEED_FORK_REFUSED,
    COORDINATION_BRANCH_DELETED,
    COORDINATION_WORKTREE_UNMATERIALIZED,
    PATH_UNROUTABLE,
    PROTECTED_BRANCH_REFUSED,
    STATUS_LOCK_HELD,
    WRONG_SURFACE,
    PathFate,
    commit_outcome_exit_code,
)
from specify_cli.git.protection_policy import ProtectionPolicy

if TYPE_CHECKING:
    from specify_cli.coordination.commit_router import CommitRouterResult
    from tests.terminus.conftest import CoordMission

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# A coordination ref vs the primary target branch the router compares against.
_PRIMARY_BRANCH = "main"
_COORD_REF = "kitty/mission-my-slug-ABCD1234"


def _patch_primary_target(ref: str = _PRIMARY_BRANCH) -> object:
    """Patch the router's primary-target-branch read.

    ``commit_for_mission`` derives ``use_coord`` from the kind-aware placement by
    comparing ``placement.ref`` against the mission's primary ``target_branch``
    (write-surface-coherence WP02). Unit fixtures have no real meta.json, so this
    pins the primary ref deterministically.
    """
    return patch(
        "specify_cli.coordination.commit_router._resolve_mission_target_branch",
        return_value=ref,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_policy(*, protected: bool) -> ProtectionPolicy:
    """Return a ProtectionPolicy that either protects or does not protect 'main'."""
    branches: frozenset[str] = frozenset({"main"}) if protected else frozenset()
    return ProtectionPolicy(protected_branches=branches, operator_hatch_active=False)


def _make_coord_target() -> object:
    """Return a ref-only CommitTarget for a coordination placement."""
    from mission_runtime import CommitTarget

    return CommitTarget(ref=_COORD_REF)


def _make_primary_target() -> object:
    """Return a ref-only CommitTarget for a primary placement."""
    from mission_runtime import CommitTarget

    return CommitTarget(ref=_PRIMARY_BRANCH)


def _patch_topology(coord: bool) -> object:
    """Patch the router's stored-topology read (FR-001b: routing reads topology).

    ``commit_for_mission`` decides coord-vs-primary from the WP02 STORED topology
    via ``routes_through_coordination(resolve_topology(...))`` — no longer from a
    per-ref ``CommitTarget.kind``. The fixtures stub ``resolve_placement_only`` for
    the ref; this stubs ``resolve_topology`` for the routing decision so the two
    legs stay consistent (COORD ⇒ coord routing; SINGLE_BRANCH ⇒ primary).
    """
    from mission_runtime import MissionTopology

    topology = MissionTopology.COORD if coord else MissionTopology.SINGLE_BRANCH
    return patch(
        "specify_cli.coordination.commit_router.resolve_topology",
        return_value=topology,
    )


# ---------------------------------------------------------------------------
# Helper: a minimal CommitResult-like object
# ---------------------------------------------------------------------------


class _FakeCommitResult:
    sha = "abc1234567890"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_unprotected_direct_commit(tmp_path: Path) -> None:
    """Unprotected placement → safe_commit called directly; no materialiser."""
    policy = _make_policy(protected=False)
    primary_target = _make_primary_target()
    mission_slug = "001-my-mission"
    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")

    materialise_calls: list[object] = []

    with (
        _patch_topology(coord=False),
        _patch_primary_target(),
        patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            return_value=primary_target,
        ),
        patch(
            "specify_cli.coordination.commit_router._materialise_coord_worktree",
            side_effect=lambda *a, **kw: materialise_calls.append(a) or (tmp_path, (artifact,)),
        ),
        patch(
            "specify_cli.coordination.commit_router.safe_commit",
            return_value=_FakeCommitResult(),
        ),
    ):
        from specify_cli.coordination.commit_router import commit_for_mission

        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug=mission_slug,
            files=(artifact,),
            message="Add spec",
            policy=policy,
            kind=MissionArtifactKind.SPEC,
        )

    assert result.status == "committed"
    assert result.placement_ref == _PRIMARY_BRANCH
    # The materialiser must NOT have been called on the unprotected path.
    assert len(materialise_calls) == 0
    # WP05 T025: a single-group (the common fast path) batch gets exactly one
    # SurfaceOutcome, "primary", carrying the committed path.
    assert len(result.surfaces) == 1
    assert result.surfaces[0].surface == "primary"
    assert result.surfaces[0].branch == _PRIMARY_BRANCH
    assert result.surfaces[0].status == "committed"
    assert result.surfaces[0].committed == ("spec.md",)


@pytest.mark.parametrize(
    "kind",
    [
        MissionArtifactKind.SPEC,
        # friction-remediation-01M43DRV (#5552): contracts/ is plan output, a
        # pre-tasks kind -- the finalize-tasks hatch would silently revert.
        MissionArtifactKind.CONTRACT,
    ],
    ids=lambda kind: kind.value,
)
def test_protected_primary_refusal_names_mission_create_for_pre_tasks_kind(tmp_path: Path, kind: MissionArtifactKind) -> None:
    """Protected primary placement, PRE-TASKS kind → ``agent mission create`` remedy.

    ``SPEC`` is a pre-tasks kind (write-surface-coherence): no ``tasks/``
    directory exists yet for this mission, so the FR-012
    ``finalize-tasks --target-branch`` escape hatch cannot persist durably
    (mission_finalize.py reverts an override written before the missing-
    ``tasks/`` gate). At this stage nothing but a regenerable spec.md is at
    risk, so the working remedy is starting a mission on a feature branch,
    not retargeting the stuck one (#255 fix-round-2, squad pass 2 MAJOR).
    """
    policy = _make_policy(protected=True)
    primary_target = _make_primary_target()
    mission_slug = "001-my-mission"
    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")

    with (
        _patch_topology(coord=True),
        _patch_primary_target(),
        patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            return_value=primary_target,
        ),
        patch(
            "specify_cli.coordination.commit_router.safe_commit",
            return_value=_FakeCommitResult(),
        ) as safe_commit,
    ):
        from specify_cli.coordination.commit_router import commit_for_mission

        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug=mission_slug,
            files=(artifact,),
            message="Add spec",
            policy=policy,
            kind=kind,
        )

    assert result.status == "no_op_wrong_surface"
    assert result.placement_ref == _PRIMARY_BRANCH
    assert result.diagnostic is not None
    assert f"spec-kitty agent mission create {mission_slug} --start-branch <feature-branch>" in result.diagnostic
    assert "spec-kitty mission create --start-branch" not in result.diagnostic
    assert "finalize-tasks --mission" not in result.diagnostic
    safe_commit.assert_not_called()


def test_protected_primary_refusal_names_real_finalize_tasks_command(tmp_path: Path) -> None:
    """Protected primary placement, TASKS-STAGE kind → ``finalize-tasks`` remedy.

    The mission named by ``mission_slug`` already has a ``tasks/`` directory
    at this kind (``WORK_PACKAGE_TASK``), so the remedy is the FR-012
    ``finalize-tasks --target-branch`` escape hatch that persists onto the
    EXISTING mission's meta.json -- not ``agent mission create``, which mints
    a fresh ULID per call and would leave a second, empty mission behind.
    """
    policy = _make_policy(protected=True)
    primary_target = _make_primary_target()
    mission_slug = "001-my-mission"
    artifact = tmp_path / "WP01.md"
    artifact.write_text("# WP01\n", encoding="utf-8")

    with (
        _patch_topology(coord=True),
        _patch_primary_target(),
        patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            return_value=primary_target,
        ),
        patch(
            "specify_cli.coordination.commit_router.safe_commit",
            return_value=_FakeCommitResult(),
        ) as safe_commit,
    ):
        from specify_cli.coordination.commit_router import commit_for_mission

        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug=mission_slug,
            files=(artifact,),
            message="Add WP01",
            policy=policy,
            kind=MissionArtifactKind.WORK_PACKAGE_TASK,
        )

    assert result.status == "no_op_wrong_surface"
    assert result.placement_ref == _PRIMARY_BRANCH
    assert result.diagnostic is not None
    assert f"spec-kitty agent mission finalize-tasks --mission {mission_slug} --target-branch <feature-branch>" in result.diagnostic
    assert "spec-kitty mission create --start-branch" not in result.diagnostic
    assert "agent mission create" not in result.diagnostic
    safe_commit.assert_not_called()


def test_protected_coord_placement_materialises(tmp_path: Path) -> None:
    """Coordination kind under coord topology → materialiser called; artifact on coord branch.

    A coordination kind (``ACCEPTANCE_MATRIX``) keeps the topology-routed coord
    placement, so the router materialises the coord worktree (C-001) — unchanged
    by write-surface-coherence WP02 (only PRIMARY kinds were re-routed off coord).
    Exemplar swapped from ``ANALYSIS_REPORT`` (re-homed PRIMARY by FR-003,
    coord-commit-integrity) to a still-COORD kind so the coord-routing coverage
    survives the re-home.
    """
    policy = _make_policy(protected=True)
    coord_target = _make_coord_target()
    mission_slug = "001-my-mission"
    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")

    coord_artifact = tmp_path / ".worktrees" / "coord" / "kitty-specs" / mission_slug / "spec.md"
    coord_artifact.parent.mkdir(parents=True)
    coord_artifact.write_text("# Spec\n", encoding="utf-8")

    materialise_calls: list[object] = []

    def _fake_materialise(repo_root, mission_slug, placement, files, **kwargs):
        materialise_calls.append((repo_root, mission_slug, placement))
        return coord_artifact.parent.parent.parent.parent, (coord_artifact,)

    with (
        _patch_topology(coord=True),
        _patch_primary_target(),
        patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            return_value=coord_target,
        ),
        patch(
            "specify_cli.coordination.commit_router._materialise_coord_worktree",
            side_effect=_fake_materialise,
        ),
        patch(
            "specify_cli.coordination.commit_router.safe_commit",
            return_value=_FakeCommitResult(),
        ),
    ):
        from specify_cli.coordination.commit_router import commit_for_mission

        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug=mission_slug,
            files=(artifact,),
            message="Add acceptance matrix",
            policy=policy,
            kind=MissionArtifactKind.ACCEPTANCE_MATRIX,
        )

    assert result.status == "committed"
    assert result.placement_ref == _COORD_REF
    # Materialiser MUST have been called.
    assert len(materialise_calls) == 1


# ---------------------------------------------------------------------------
# WP05 T025 — ``surfaces`` for a genuinely split (mixed-partition) batch.
# ---------------------------------------------------------------------------


def _fake_resolve_placement_only_by_partition(_repo_root: Path, _mission_slug: str, *, kind: MissionArtifactKind, owned: object | None = None) -> object:
    """Kind-aware placement stub: a PRIMARY kind resolves to the primary ref, else the coord ref."""
    from mission_runtime import is_primary_artifact_kind

    return _make_primary_target() if is_primary_artifact_kind(kind) else _make_coord_target()


def test_mixed_batch_populates_surfaces_primary_then_coordination(tmp_path: Path) -> None:
    """``CommitRouterResult.surfaces`` carries BOTH groups' outcomes, PRIMARY first (contract rule 1)."""
    mission_slug = "001-my-mission"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    tasks_file = feature_dir / "tasks.md"
    tasks_file.write_text("# Tasks\n", encoding="utf-8")
    matrix_file = feature_dir / "acceptance-matrix.json"
    matrix_file.write_text("{}", encoding="utf-8")

    coord_worktree = tmp_path / ".worktrees" / "coord"
    coord_worktree.mkdir(parents=True)

    def _fake_materialise(repo_root: Path, _mission_slug: str, _placement: object, files: tuple[Path, ...], **_kwargs: object) -> tuple[Path, tuple[Path, ...]]:
        staged: list[Path] = []
        for src in files:
            dst = coord_worktree / src.relative_to(repo_root)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            staged.append(dst)
        return coord_worktree, tuple(staged)

    with (
        _patch_topology(coord=True),
        _patch_primary_target(),
        patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            side_effect=_fake_resolve_placement_only_by_partition,
        ),
        patch(
            "specify_cli.coordination.commit_router._materialise_coord_worktree",
            side_effect=_fake_materialise,
        ),
        patch(
            "specify_cli.coordination.commit_router.safe_commit",
            return_value=_FakeCommitResult(),
        ),
    ):
        from specify_cli.coordination.commit_router import commit_for_mission

        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug=mission_slug,
            files=(tasks_file, matrix_file),
            message="chore: finalize tasks",
            policy=_make_policy(protected=False),
            kind=MissionArtifactKind.TASKS_INDEX,
        )

    assert result.status == "committed"
    assert len(result.surfaces) == 2, f"expected one SurfaceOutcome per partition group, got {result.surfaces!r}"
    primary_surface, coord_surface = result.surfaces
    assert primary_surface.surface == "primary"
    assert primary_surface.branch == _PRIMARY_BRANCH
    assert primary_surface.status == "committed"
    assert primary_surface.committed == ("kitty-specs/001-my-mission/tasks.md",)
    assert coord_surface.surface == "coordination"
    assert coord_surface.branch == _COORD_REF
    assert coord_surface.status == "committed"
    assert coord_surface.committed == (".worktrees/coord/kitty-specs/001-my-mission/acceptance-matrix.json",)
    # Legacy fields stay the caller-partition (TASKS_INDEX -> PRIMARY) projection.
    assert result.placement_ref == _PRIMARY_BRANCH


def test_mixed_batch_error_on_one_group_still_carries_both_surfaces(tmp_path: Path) -> None:
    """A real git error on ONE group of a split batch never masks the OTHER group's outcome in ``surfaces`` (FR-007)."""
    mission_slug = "001-my-mission"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    tasks_file = feature_dir / "tasks.md"
    tasks_file.write_text("# Tasks\n", encoding="utf-8")
    matrix_file = feature_dir / "acceptance-matrix.json"
    matrix_file.write_text("{}", encoding="utf-8")

    coord_worktree = tmp_path / ".worktrees" / "coord"
    coord_worktree.mkdir(parents=True)

    def _fake_materialise(repo_root: Path, _mission_slug: str, _placement: object, files: tuple[Path, ...], **_kwargs: object) -> tuple[Path, tuple[Path, ...]]:
        staged: list[Path] = []
        for src in files:
            dst = coord_worktree / src.relative_to(repo_root)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            staged.append(dst)
        return coord_worktree, tuple(staged)

    calls = {"n": 0}

    def _flaky_safe_commit(**_kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeCommitResult()
        raise subprocess.CalledProcessError(1, ["git", "commit"], stderr="fatal: lock denied")

    with (
        _patch_topology(coord=True),
        _patch_primary_target(),
        patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            side_effect=_fake_resolve_placement_only_by_partition,
        ),
        patch(
            "specify_cli.coordination.commit_router._materialise_coord_worktree",
            side_effect=_fake_materialise,
        ),
        patch("specify_cli.coordination.commit_router.safe_commit", side_effect=_flaky_safe_commit),
    ):
        from specify_cli.coordination.commit_router import commit_for_mission

        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug=mission_slug,
            files=(tasks_file, matrix_file),
            message="chore: finalize tasks",
            policy=_make_policy(protected=False),
            kind=MissionArtifactKind.TASKS_INDEX,
        )

    assert result.status == "error"
    assert len(result.surfaces) == 2, f"an error on one group must not drop the other group's surface: {result.surfaces!r}"
    primary_surface, coord_surface = result.surfaces
    assert primary_surface.surface == "primary"
    assert primary_surface.status == "committed"
    assert coord_surface.surface == "coordination"
    assert coord_surface.status == "error"
    assert coord_surface.refused


def test_idempotent_unchanged(tmp_path: Path) -> None:
    """safe_commit raises 'nothing to commit' → status is 'unchanged'."""
    policy = _make_policy(protected=False)
    from mission_runtime import CommitTarget

    primary_target = CommitTarget(ref="main")
    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")

    exc = subprocess.CalledProcessError(1, ["git", "commit"])
    exc.stderr = "nothing to commit, working tree clean"

    with (
        _patch_topology(coord=False),
        _patch_primary_target(),
        patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            return_value=primary_target,
        ),
        patch(
            "specify_cli.coordination.commit_router.safe_commit",
            side_effect=exc,
        ),
    ):
        from specify_cli.coordination.commit_router import commit_for_mission

        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug="001-my-mission",
            files=(artifact,),
            message="Add spec",
            policy=policy,
            kind=MissionArtifactKind.SPEC,
        )

    assert result.status == "unchanged"


def test_1718_no_materialisation_at_read_time(tmp_path: Path) -> None:
    """#1718: the materialiser is NOT called before commit_for_mission is invoked."""
    # This test proves that _materialise_coord_worktree is only called INSIDE
    # commit_for_mission (at the commit boundary), never at import/read time.
    materialise_calls: list[object] = []
    policy = _make_policy(protected=True)

    from mission_runtime import CommitTarget

    coord_target = CommitTarget(ref="kitty/mission-x-ABCD1234")
    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")
    coord_artifact = tmp_path / "coord-spec.md"
    coord_artifact.write_text("# Spec\n", encoding="utf-8")

    def _fake_materialise(repo_root, mission_slug, placement, files, **kwargs):
        materialise_calls.append("called")
        return tmp_path, (coord_artifact,)

    with patch(
        "specify_cli.coordination.commit_router._materialise_coord_worktree",
        side_effect=_fake_materialise,
    ):
        # Import the module — materialiser should NOT be called just by importing.
        import importlib

        import specify_cli.coordination.commit_router as _mod

        importlib.reload(_mod)
        assert len(materialise_calls) == 0, "Materialiser called at import/read time!"

        # Only called when commit_for_mission is explicitly invoked.
        from mission_runtime import MissionTopology

        with (
            patch.object(_mod, "resolve_topology", return_value=MissionTopology.COORD),
            patch.object(_mod, "resolve_placement_only", return_value=coord_target),
            patch.object(_mod, "_resolve_mission_target_branch", return_value=_PRIMARY_BRANCH),
            patch.object(_mod, "_materialise_coord_worktree", side_effect=_fake_materialise),
            patch.object(_mod, "safe_commit", return_value=_FakeCommitResult()),
        ):
            _mod.commit_for_mission(
                repo_root=tmp_path,
                mission_slug="001-x",
                files=(artifact,),
                message="m",
                policy=policy,
                kind=MissionArtifactKind.ACCEPTANCE_MATRIX,
            )

    assert len(materialise_calls) == 1


def test_negative_stubbed_materialiser_causes_wrong_result(tmp_path: Path) -> None:
    """NEGATIVE: when materialiser is stubbed to return the PRIMARY path, the router
    must be caught committing to the wrong surface.

    The materialiser's job is to stage artifacts in the COORDINATION worktree, not in
    the primary checkout (``tmp_path``).  This test proves the materialiser is
    load-bearing: when it is replaced by a stub that silently returns the primary path,
    ``safe_commit`` receives ``worktree_root == tmp_path`` (primary), which is the
    wrong surface.  The assertion is:

        worktree_root passed to safe_commit MUST NOT be tmp_path (the primary checkout)

    If the gate inside commit_for_mission that checks placement/surface ever regresses
    (e.g. materialise-then-retry is replaced by a direct primary commit), this test
    goes RED because safe_commit would again receive ``worktree_root == tmp_path``.
    """
    policy = _make_policy(protected=True)
    from mission_runtime import CommitTarget

    coord_target = CommitTarget(ref="kitty/mission-x-ABCD1234")
    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")

    # A fake coord worktree path — distinct from tmp_path (the primary checkout).
    coord_worktree = tmp_path / ".worktrees" / "coord"
    coord_worktree.mkdir(parents=True)
    coord_artifact = coord_worktree / "spec.md"
    coord_artifact.write_text("# Spec\n", encoding="utf-8")

    # Stub that returns the PRIMARY path — wrong surface.
    def _stub_materialise_primary(*args, **kwargs):
        return tmp_path, (artifact,)

    # Real-ish stub that returns the COORD worktree path — correct surface.
    def _stub_materialise_coord(*args, **kwargs):
        return coord_worktree, (coord_artifact,)

    safe_commit_calls: list[dict] = []

    def _spy_safe_commit(**kwargs):
        safe_commit_calls.append(dict(kwargs))
        return _FakeCommitResult()

    # --- Scenario A: stub returns PRIMARY path (regression / no-op materialiser) ---
    # safe_commit receives worktree_root == tmp_path → wrong surface.
    safe_commit_calls.clear()
    with (
        _patch_topology(coord=True),
        _patch_primary_target(),
        patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            return_value=coord_target,
        ),
        patch(
            "specify_cli.coordination.commit_router._materialise_coord_worktree",
            side_effect=_stub_materialise_primary,
        ),
        patch(
            "specify_cli.coordination.commit_router.safe_commit",
            side_effect=_spy_safe_commit,
        ),
    ):
        from specify_cli.coordination.commit_router import commit_for_mission

        commit_for_mission(
            repo_root=tmp_path,
            mission_slug="001-x",
            files=(artifact,),
            message="m",
            policy=policy,
            kind=MissionArtifactKind.ACCEPTANCE_MATRIX,
        )

    # Discriminating assertion: when materialiser returns primary, safe_commit lands
    # on the PRIMARY checkout — this is the bug this test must catch.
    assert len(safe_commit_calls) == 1
    wrong_surface_root = safe_commit_calls[0]["worktree_root"]
    assert wrong_surface_root == tmp_path, f"Expected stub-materialiser to route to primary (tmp_path); got {wrong_surface_root!r} instead."

    # --- Scenario B: materialiser returns COORD path (correct behaviour) ---
    # safe_commit must NOT receive tmp_path as worktree_root.
    safe_commit_calls.clear()
    with (
        _patch_topology(coord=True),
        _patch_primary_target(),
        patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            return_value=coord_target,
        ),
        patch(
            "specify_cli.coordination.commit_router._materialise_coord_worktree",
            side_effect=_stub_materialise_coord,
        ),
        patch(
            "specify_cli.coordination.commit_router.safe_commit",
            side_effect=_spy_safe_commit,
        ),
    ):
        commit_for_mission(
            repo_root=tmp_path,
            mission_slug="001-x",
            files=(artifact,),
            message="m",
            policy=policy,
            kind=MissionArtifactKind.ACCEPTANCE_MATRIX,
        )

    assert len(safe_commit_calls) == 1
    correct_surface_root = safe_commit_calls[0]["worktree_root"]
    # The commit MUST land on the coord worktree, not on the primary checkout.
    assert correct_surface_root != tmp_path, "Correct materialiser should route to coord worktree, not primary (tmp_path)."
    assert correct_surface_root == coord_worktree


# ---------------------------------------------------------------------------
# write-surface-coherence WP02 / T011 — RED-FIRST caller-convergence tests
# ---------------------------------------------------------------------------
#
# These pin the FR-003 / C-005 unification: a PRIMARY artifact kind (spec / plan /
# tasks / metadata) committed under COORD topology lands on the PRIMARY target
# branch and NEVER materialises the coordination worktree — the planning→coord
# route is removed. A COORD kind (analysis-report / status) keeps routing to
# coordination (C-001). On PRE-WP02 code, ``commit_for_mission`` routed every
# planning artifact through coordination whenever the topology routed coord, so
# the SPEC-on-coord assertion below goes RED on the unfixed tree (proven by
# revert+restore).


def test_primary_kind_under_coord_topology_does_not_route_to_coord(tmp_path: Path) -> None:
    """RED-FIRST: a SPEC (primary kind) under COORD topology lands on PRIMARY, not coord.

    Pre-WP02 the router routed planning artifacts to coordination whenever the
    stored topology routed coord. WP02 derives routing from the kind-aware
    placement: a primary kind resolves to the primary ``target_branch`` and the
    materialiser is NEVER engaged. The discriminating assertions are:

    * the materialiser was NOT called (no coord worktree),
    * ``safe_commit`` received ``worktree_root == repo_root`` (the primary),
    * ``placement_ref`` is the PRIMARY branch.
    """
    policy = _make_policy(protected=False)
    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")

    # The kind-aware resolver returns the PRIMARY ref for a primary kind (this is
    # WP01's behavior); the topology still routes coord. The router must trust the
    # placement, not the topology, for a primary kind.
    from mission_runtime import CommitTarget

    primary_placement = CommitTarget(ref=_PRIMARY_BRANCH)

    materialise_calls: list[object] = []
    safe_commit_calls: list[dict] = []

    with (
        _patch_topology(coord=True),  # topology routes coord …
        _patch_primary_target(),  # … but the primary target is "main" …
        patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            return_value=primary_placement,  # … and the SPEC placement IS "main".
        ),
        patch(
            "specify_cli.coordination.commit_router._materialise_coord_worktree",
            side_effect=lambda *a, **kw: materialise_calls.append(a) or (tmp_path, (artifact,)),
        ),
        patch(
            "specify_cli.coordination.commit_router.safe_commit",
            side_effect=lambda **kw: safe_commit_calls.append(kw) or _FakeCommitResult(),
        ),
    ):
        from specify_cli.coordination.commit_router import commit_for_mission

        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug="001-my-mission",
            files=(artifact,),
            message="Add spec",
            policy=policy,
            kind=MissionArtifactKind.SPEC,
        )

    # The materialiser MUST NOT have been called — no planning→coord route.
    assert len(materialise_calls) == 0, (
        "SPEC (primary kind) under coord topology materialised the coordination worktree — the planning→coord route was not removed (write-surface-coherence WP02)."
    )
    assert len(safe_commit_calls) == 1
    assert safe_commit_calls[0]["worktree_root"] == tmp_path, "SPEC commit did not land on the primary checkout."
    assert result.status == "committed"
    assert result.placement_ref == _PRIMARY_BRANCH


def test_analysis_report_under_coord_topology_routes_to_primary(tmp_path: Path) -> None:
    """FR-003 re-home: ANALYSIS_REPORT (now PRIMARY) under COORD topology lands PRIMARY.

    INVERTS the pre-re-home ``…still_routes_to_coord`` flip-test (#2463 landmine).
    ``ANALYSIS_REPORT`` was re-homed COORD→PRIMARY (data-model.md / FR-003), so it
    now follows the SAME no-coord-transit path ``SPEC`` does: the materialiser is
    NEVER engaged and the report commits directly to the primary ``target_branch``.
    Asserting the PRIMARY truth (NOT re-asserting the old coord routing) is the
    point — running this "green toward coord" would REVERSE the re-home.

    This is a STUBBED router unit test (like its ``SPEC`` sibling); the
    NON-FAKEABLE partition proof (real resolver + committed refs) lives in
    ``tests/architectural/test_write_surface_placement_guard.py`` and
    ``tests/coordination/test_analysis_report_rehome.py``. Coord-routing coverage
    is preserved by ``test_protected_coord_placement_materialises`` (now keyed on
    ``ACCEPTANCE_MATRIX``). Discriminating assertions mirror the ``SPEC`` test:
    materialiser NOT called, safe_commit lands on the primary checkout,
    ``placement_ref`` is the primary branch.
    """
    policy = _make_policy(protected=False)
    artifact = tmp_path / "analysis-report.md"
    artifact.write_text("# Analysis\n", encoding="utf-8")

    # The kind-aware resolver returns the PRIMARY ref for the re-homed ANALYSIS_REPORT
    # kind (mirroring the real ``resolve_placement_only`` post-re-home); the topology
    # still routes coord, but the router must trust the placement for a primary kind.
    from mission_runtime import CommitTarget

    primary_placement = CommitTarget(ref=_PRIMARY_BRANCH)

    materialise_calls: list[object] = []
    safe_commit_calls: list[dict] = []

    with (
        _patch_topology(coord=True),  # topology routes coord …
        _patch_primary_target(),  # … but the primary target is "main" …
        patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            return_value=primary_placement,  # … and ANALYSIS_REPORT's placement IS "main".
        ),
        patch(
            "specify_cli.coordination.commit_router._materialise_coord_worktree",
            side_effect=lambda *a, **kw: materialise_calls.append(a) or (tmp_path, (artifact,)),
        ),
        patch(
            "specify_cli.coordination.commit_router.safe_commit",
            side_effect=lambda **kw: safe_commit_calls.append(kw) or _FakeCommitResult(),
        ),
    ):
        from specify_cli.coordination.commit_router import commit_for_mission

        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug="001-my-mission",
            files=(artifact,),
            message="Add analysis report",
            policy=policy,
            kind=MissionArtifactKind.ANALYSIS_REPORT,
        )

    # The re-homed PRIMARY kind MUST NOT materialise the coord worktree.
    assert len(materialise_calls) == 0, (
        "ANALYSIS_REPORT (re-homed PRIMARY) materialised the coordination worktree — the re-home did not remove its coord transit (FR-003)."
    )
    assert len(safe_commit_calls) == 1
    assert safe_commit_calls[0]["worktree_root"] == tmp_path, "ANALYSIS_REPORT commit did not land on the primary checkout."
    assert result.status == "committed"
    assert result.placement_ref == _PRIMARY_BRANCH


# ---------------------------------------------------------------------------
# write-surface-coherence WP05 / T023 — DECISION 8 runtime guard
# ---------------------------------------------------------------------------
#
# Once planning no longer transits coord (WP02/WP03), the coord-staging helper is
# reachable ONLY for coordination kinds. A PRIMARY kind arriving at
# ``_materialise_coord_worktree`` means a caller mis-routed a planning artifact
# onto the coordination branch — the RUNTIME guard (DECISION 8) must raise, not
# silently stage. This is the test for the guard added in T020. On pre-WP05 code
# the helper had no guard and would proceed into ``CoordinationWorkspace.resolve``,
# so the ``pytest.raises`` below goes RED (no exception) — proven by revert+restore.


def test_materialise_coord_worktree_rejects_primary_kind(tmp_path: Path) -> None:
    """DECISION 8: a PRIMARY kind reaching ``_materialise_coord_worktree`` raises.

    The guard fires at the staging entry BEFORE any worktree resolution, so a
    planning artifact can never be staged onto the coordination branch. The test
    calls the helper directly (the entry point the guard protects) with a real
    primary kind (``SPEC``) and a realistic coord-worktree-style placement, and
    asserts the typed :class:`PrimaryKindReachedCoordStagingError` is raised.
    """
    from mission_runtime import CommitTarget
    from specify_cli.coordination.commit_router import (
        PrimaryKindReachedCoordStagingError,
        _materialise_coord_worktree,
    )

    artifact = tmp_path / "kitty-specs" / "001-write-surface" / "spec.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("# Spec\n", encoding="utf-8")
    coord_placement = CommitTarget(ref="kitty/mission-write-surface-01KVTVZS3A4B5C6D")

    with pytest.raises(PrimaryKindReachedCoordStagingError):
        _materialise_coord_worktree(
            tmp_path,
            "001-write-surface",
            coord_placement,
            (artifact,),
            kind=MissionArtifactKind.SPEC,
        )


def test_materialise_coord_worktree_allows_coord_kind(tmp_path: Path) -> None:
    """A COORD kind passes the PRIMARY-kind guard and reaches its coord surface.

    The complement of the guard test: a coordination kind (``ACCEPTANCE_MATRIX``)
    must NOT trip :class:`PrimaryKindReachedCoordStagingError`. Exemplar swapped from
    ``ANALYSIS_REPORT`` (re-homed PRIMARY by FR-003 — it would now correctly TRIP the
    guard) to a still-COORD kind so the "coord kind passes the guard" coverage
    survives the re-home.

    coord-commit-surface-authority WP04 (DD-3 / INV-3): the former assertion observed
    "guard did not fire" via the SILENT mid8-None → primary fallback. That fallback
    is now a fail-loud :class:`CoordWorktreeResolutionError` (no silent misroute), so
    this test drives a HEALTHY coord path (resolvable mid8 + resolvable worktree)
    instead — proving the PRIMARY-kind guard did not fire and the COORD path
    proceeded to its coordination surface.
    """
    from mission_runtime import CommitTarget
    from specify_cli.coordination import commit_router
    from specify_cli.coordination.commit_router import _materialise_coord_worktree

    artifact = tmp_path / "kitty-specs" / "001-write-surface" / "acceptance-matrix.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}\n", encoding="utf-8")
    coord_placement = CommitTarget(ref="kitty/mission-write-surface-01KVTVZS3A4B5C6D")
    coord_worktree = tmp_path / ".worktrees" / "coord"
    staged = coord_worktree / "kitty-specs" / "001-write-surface" / "acceptance-matrix.json"

    with (
        patch.object(commit_router, "_resolve_mid8", return_value="01KVTVZS"),
        patch(
            "specify_cli.coordination.workspace.CoordinationWorkspace.resolve",
            return_value=coord_worktree,
        ),
        patch.object(commit_router, "_stage_artifacts_in_coord_worktree", return_value=[staged]),
    ):
        worktree_root, paths = _materialise_coord_worktree(
            tmp_path,
            "001-write-surface",
            coord_placement,
            (artifact,),
            kind=MissionArtifactKind.ACCEPTANCE_MATRIX,
        )

    # The PRIMARY-kind guard did NOT raise, and the coord kind reached its coord surface.
    assert worktree_root == coord_worktree
    assert paths == (staged,)


def test_coord_staging_keeps_matrices_but_skips_rehomed_analysis_report(
    tmp_path: Path,
) -> None:
    """Coord-kind-caller regression (FR-003): the copy2-drop is NARROW.

    Enumerates the coordination-partition artifacts a ``commit_for_mission``
    coord-kind caller stages and proves ``_stage_artifacts_in_coord_worktree``:

    * STILL copies the genuinely-COORD ``acceptance-matrix.json`` /
      ``issue-matrix.md`` into the coord worktree (write-in-coord-home preserved —
      the copy2 path is KEPT for them), and
    * SKIPS the re-homed ``analysis-report.md`` (now PRIMARY) so no second (coord)
      copy is made.

    Without this guard an over-broad copy-drop would turn "silently copied" into
    "silently missing" for the other coord kinds. It is the "prove write-in-coord-
    home BEFORE the copy is removed" net the DoD calls for.
    """
    from specify_cli.coordination.commit_router import (
        _stage_artifacts_in_coord_worktree,
    )

    repo_root = tmp_path / "repo"
    coord_worktree = tmp_path / "coord"
    specs = repo_root / "kitty-specs" / "001-demo"
    specs.mkdir(parents=True)
    acceptance = specs / "acceptance-matrix.json"
    acceptance.write_text("{}\n", encoding="utf-8")
    issue = specs / "issue-matrix.md"
    issue.write_text("# issues\n", encoding="utf-8")
    analysis = specs / "analysis-report.md"
    analysis.write_text("# analysis\n", encoding="utf-8")

    coord_files = _stage_artifacts_in_coord_worktree([acceptance, issue, analysis], coord_worktree, repo_root)

    coord_specs = coord_worktree / "kitty-specs" / "001-demo"
    acc_dst = coord_specs / "acceptance-matrix.json"
    iss_dst = coord_specs / "issue-matrix.md"
    ana_dst = coord_specs / "analysis-report.md"

    # COORD matrices ARE staged (copy2 KEPT) — write-in-coord-home preserved.
    assert acc_dst.exists(), "acceptance-matrix.json was not staged to the coord worktree"
    assert iss_dst.exists(), "issue-matrix.md was not staged to the coord worktree"
    assert acc_dst in coord_files
    assert iss_dst in coord_files

    # Re-homed analysis-report is SKIPPED — no coord copy (write surface == read surface).
    assert not ana_dst.exists(), "analysis-report.md was copied to coord — copy-drop failed"
    assert ana_dst not in coord_files
    assert analysis not in coord_files


def test_coord_staging_keeps_a_status_log_already_in_the_coord_worktree(tmp_path: Path) -> None:
    """A STATUS_STATE path that already lives in the coord worktree is committed in place.

    The STATUS_STATE skip exists so a stale PRIMARY copy of the status log is never
    copied over the coord one (#1589). A log the caller hands over from the coord
    worktree itself needs no copy: dropping it made ``commit_for_mission`` report
    ``no_op_already_committed`` while the log stayed modified and uncommitted there.
    The primary copy is still skipped, never copied.
    """
    from specify_cli.coordination.commit_router import (
        _stage_artifacts_in_coord_worktree,
    )

    repo_root = tmp_path / "repo"
    coord_worktree = repo_root / ".worktrees" / "001-demo-coord"
    coord_log = coord_worktree / "kitty-specs" / "001-demo" / "status.events.jsonl"
    coord_log.parent.mkdir(parents=True)
    coord_log.write_text('{"coord": true}\n', encoding="utf-8")
    primary_log = repo_root / "kitty-specs" / "001-demo" / "status.events.jsonl"
    primary_log.parent.mkdir(parents=True)
    primary_log.write_text('{"stale": true}\n', encoding="utf-8")

    coord_files = _stage_artifacts_in_coord_worktree([coord_log, primary_log], coord_worktree, repo_root)

    assert coord_files == [coord_log]
    assert coord_log.read_text(encoding="utf-8") == '{"coord": true}\n', "the primary copy was copied over the coord log"


@pytest.mark.parametrize(
    "foreign_log",
    [
        pytest.param(
            Path(".worktrees") / "002-other-coord" / "kitty-specs" / "002-other" / "status.events.jsonl",
            id="sibling-mission-coord-worktree",
        ),
        pytest.param(
            Path(".worktrees") / "001-demo-coord" / ".worktrees" / "x" / "kitty-specs" / "001-demo" / "status.events.jsonl",
            id="nested-inside-this-coord-worktree",
        ),
    ],
)
def test_coord_staging_drops_a_status_log_from_another_worktree(tmp_path: Path, foreign_log: Path) -> None:
    """Only a status log directly in THIS coordination worktree is kept (#5353).

    A sibling Mission's coordination worktree, or a worktree nested inside this
    one, holds a status log that is not this Mission's: it is neither committed
    in place nor copied.
    """
    from specify_cli.coordination.commit_router import (
        _stage_artifacts_in_coord_worktree,
    )

    repo_root = tmp_path / "repo"
    coord_worktree = repo_root / ".worktrees" / "001-demo-coord"
    own_log = coord_worktree / "kitty-specs" / "001-demo" / "status.events.jsonl"
    other_log = repo_root / foreign_log
    for log in (own_log, other_log):
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text('{"row": 1}\n', encoding="utf-8")

    coord_files = _stage_artifacts_in_coord_worktree([own_log, other_log], coord_worktree, repo_root)

    assert coord_files == [own_log]


def test_coord_staging_keeps_its_own_status_log_through_a_symlinked_repo_root(tmp_path: Path) -> None:
    """The in-worktree check compares resolved paths, so a symlinked ``repo_root`` still keeps the log."""
    from specify_cli.coordination.commit_router import (
        _stage_artifacts_in_coord_worktree,
    )

    real_root = tmp_path / "real-repo"
    coord_worktree = real_root / ".worktrees" / "001-demo-coord"
    real_log = coord_worktree / "kitty-specs" / "001-demo" / "status.events.jsonl"
    real_log.parent.mkdir(parents=True)
    real_log.write_text('{"row": 1}\n', encoding="utf-8")
    linked_root = tmp_path / "linked-repo"
    linked_root.symlink_to(real_root, target_is_directory=True)
    linked_log = linked_root / real_log.relative_to(real_root)

    coord_files = _stage_artifacts_in_coord_worktree([linked_log], coord_worktree, linked_root)

    assert coord_files == [linked_log]


# ---------------------------------------------------------------------------
# #5353: the router commits a coord-resident status log under the SAME mission
# status lock (L1) the transactional status shell holds across emit -> commit.
# Without it a router commit sweeps a concurrent transition's appended-but-
# uncommitted row; the transition's own commit then finds an empty changeset
# (``SafeCommitStagedTreeUnchanged``) and its rollback truncates a row that
# already landed on the coordination branch.
# ---------------------------------------------------------------------------

_PENDING_TRANSITION_ROW = '{"simulated": "transition row"}\n'


def _coord_mission_with_clean_status_log(tmp_path: Path) -> tuple[CoordMission, Path, Path]:
    """A real coord mission whose coord-resident status log is committed; returns (mission, log, coord worktree)."""
    from specify_cli.coordination.surface_resolver import resolve_status_surface
    from specify_cli.coordination.workspace import CoordinationWorkspace
    from tests.terminus.conftest import build_coord_mission

    mission = build_coord_mission(tmp_path, target_branch="feature/router-status-lock")
    log = resolve_status_surface(mission.repo, mission.slug)
    coord = CoordinationWorkspace.worktree_path(mission.repo, mission.slug, mission.mid8)
    assert log.is_relative_to(coord), f"fixture must put the status log in the coord worktree: {log}"
    subprocess.run(["git", "add", "--", str(log.relative_to(coord))], cwd=coord, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=coord, check=False, capture_output=True)
    return mission, log, coord


def _coord_head(coord: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=coord, check=True, capture_output=True, text=True).stdout.strip()


def _commit_log_via_router(mission: CoordMission, log: Path) -> CommitRouterResult:
    from specify_cli.coordination.commit_router import commit_for_mission

    return commit_for_mission(
        mission.repo,
        mission.slug,
        (log,),
        "chore(retrospective): retrospect-like router commit",
        ProtectionPolicy.resolve(mission.repo),
        kind=MissionArtifactKind.RETROSPECTIVE,
    )


@pytest.mark.git_repo
def test_router_does_not_commit_a_status_row_while_a_transition_holds_the_status_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A transition holding L1 across emit -> commit keeps its row; the router refuses with an error result.

    The holder takes the lock exactly as ``_emit_on_coord_then_commit`` does:
    ``feature_status_lock(repo_root, <coord feature dir name>)``.
    """
    import threading

    from specify_cli.coordination import status_transition as st
    from specify_cli.status.locking import feature_status_lock

    from mission_runtime import MissionArtifactKind, placement_seam

    mission, log, coord = _coord_mission_with_clean_status_log(tmp_path)
    # WP07 re-pin (coord-artifact-single-home-01M3V4BE, T038): ``status_transition.
    # _coord_feature_dir`` is retired; the single write-location accessor is its
    # successor.
    coord_fd = placement_seam(mission.repo, mission.slug).write_dir(MissionArtifactKind.STATUS_STATE).path
    assert coord_fd == log.parent
    monkeypatch.setattr(st, "BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS", 0.2)
    head_before = _coord_head(coord)
    ready = threading.Event()
    release = threading.Event()
    outcome: dict[str, str] = {}

    def _transition() -> None:
        with feature_status_lock(mission.repo, coord_fd.name, timeout=5):
            with log.open("a", encoding="utf-8") as fh:
                fh.write(_PENDING_TRANSITION_ROW)
            ready.set()
            release.wait(timeout=10)
            try:
                st._commit_status_artifacts_to_coord(
                    repo_root=mission.repo,
                    mission_slug=mission.slug,
                    coord_worktree=coord,
                    coord_feature_dir=coord_fd,
                )
                outcome["transition"] = "committed"
            except Exception as exc:  # recorded, asserted below
                outcome["transition"] = type(exc).__name__

    holder = threading.Thread(target=_transition, name="status-transition-holder")
    holder.start()
    try:
        assert ready.wait(timeout=5), "the transition never took the status lock"
        result = _commit_log_via_router(mission, log)
        head_while_held = _coord_head(coord)
    finally:
        release.set()
        holder.join(timeout=10)

    assert not holder.is_alive()
    assert result.status == "error"
    assert ".status.lock" in (result.diagnostic or "")
    assert head_while_held == head_before, "the router committed the transition's row while it held the lock"
    assert outcome["transition"] == "committed"
    committed_log = subprocess.run(["git", "show", f"HEAD:{log.relative_to(coord).as_posix()}"], cwd=coord, check=True, capture_output=True, text=True).stdout
    assert committed_log.endswith(_PENDING_TRANSITION_ROW)


@pytest.mark.git_repo
def test_router_commits_a_status_row_when_its_own_thread_already_holds_the_status_lock(tmp_path: Path) -> None:
    """The lock is re-entrant: a caller that already holds L1 is not deadlocked by the router."""
    from specify_cli.status.locking import feature_status_lock

    mission, log, coord = _coord_mission_with_clean_status_log(tmp_path)
    head_before = _coord_head(coord)
    with feature_status_lock(mission.repo, log.parent.name, timeout=5):
        with log.open("a", encoding="utf-8") as fh:
            fh.write(_PENDING_TRANSITION_ROW)
        result = _commit_log_via_router(mission, log)

    from mission_runtime import MissionArtifactKind, placement_seam

    assert result.status == "committed"
    assert _coord_head(coord) != head_before
    # WP07 re-pin (coord-artifact-single-home-01M3V4BE, T038): successor accessor.
    assert placement_seam(mission.repo, mission.slug).write_dir(MissionArtifactKind.STATUS_STATE).path == log.parent


# ---------------------------------------------------------------------------
# R12 (#5440, FR-008): the router no longer fast-forwards the TARGET branch to
# the coordination tip after a coordination commit. After WP06, ``create``
# seeds the coordination branch from the target, so the target is an ancestor
# of the coordination tip -- the former best-effort ``_try_advance_ref`` would
# then silently carry every coordination (STATUS/bookkeeping) commit onto the
# target, re-mixing the two surfaces the partition exists to keep apart.
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
def test_no_target_advance_for_coordination_routed_mission(tmp_path: Path) -> None:
    """A coordination commit never advances the target branch, even when it is a clean ancestor.

    Non-vacuity precondition (post-tasks squad R-M8): first prove the fixture's
    target branch IS a clean ancestor of the coordination tip -- i.e. that a
    base-shaped fast-forward WOULD move it if the router still performed one --
    so the "target unchanged" assertion below cannot pass vacuously.
    """
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.coordination.surface_resolver import resolve_status_surface
    from specify_cli.coordination.workspace import CoordinationWorkspace
    from tests.terminus.conftest import build_coord_mission

    mission = build_coord_mission(tmp_path, target_branch="feature/router-r12")
    coord = CoordinationWorkspace.worktree_path(mission.repo, mission.slug, mission.mid8)
    coord_log = resolve_status_surface(mission.repo, mission.slug)
    target_sha_before = mission.rev(mission.target_branch)

    # Baseline: the coordination branch must genuinely DIVERGE ahead of the
    # target before this test's own commit, so the non-vacuity precondition
    # below is real rather than a same-SHA coincidence.
    coord_rel = coord_log.relative_to(coord)
    with coord_log.open("a", encoding="utf-8") as fh:
        fh.write('{"simulated": "R12 baseline advance row"}\n')
    subprocess.run(["git", "add", "--", str(coord_rel)], cwd=coord, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline coord advance"], cwd=coord, check=True, capture_output=True)
    coord_sha_before = _coord_head(coord)

    # Non-vacuity: the target IS a clean ancestor of the coordination tip, and
    # the two differ -- a base-shaped advance would genuinely move it.
    assert target_sha_before != coord_sha_before
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", target_sha_before, coord_sha_before],
        cwd=mission.repo,
        check=True,
    )

    with coord_log.open("a", encoding="utf-8") as fh:
        fh.write('{"simulated": "R12 coord-only row"}\n')

    result = commit_for_mission(
        mission.repo,
        mission.slug,
        (coord_log,),
        "chore(status): commit the mission status log (R12)",
        ProtectionPolicy.resolve(mission.repo),
        kind=MissionArtifactKind.STATUS_STATE,
        target_branch=mission.target_branch,
    )

    assert result.status == "committed"
    assert mission.rev(mission.target_branch) == target_sha_before, "the target branch must NOT advance on a coordination commit (FR-008)"
    assert _coord_head(coord) != coord_sha_before, "the coordination branch must still advance"


# ---------------------------------------------------------------------------
# Owned arm (owned-checkout-lifecycle-authority WP09, review cycle 1 issue 3b):
# ``_resolve_group_placement`` must use ``owned.topology`` directly when a fact
# is present, never calling ``resolve_topology`` (which walks
# ``get_main_repo_root(repo_root)`` back to R — the exact R-touching residue
# "the fact is the single representation" forbids).
# ---------------------------------------------------------------------------


def _mint_owned_for_commit_router(tmp_path: Path, *, mission_slug: str = "001-my-mission") -> object:
    from mission_runtime import MissionTopology, OwnedCheckout

    repo = tmp_path / "repo"
    owned_root = tmp_path / "owned"
    mission_dir = owned_root / "kitty-specs" / mission_slug
    repo.mkdir(parents=True, exist_ok=True)
    mission_dir.mkdir(parents=True, exist_ok=True)
    return OwnedCheckout._mint(
        repository_root=repo,
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=mission_slug,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch=_PRIMARY_BRANCH,
    )


def test_owned_arm_never_calls_resolve_topology(tmp_path: Path) -> None:
    """Owned arm: ``resolve_topology`` (an R-touching read) must never be
    reached. Pinned with a raising monkeypatch — the routing decision must
    come from ``owned.topology`` directly instead.
    """
    owned = _mint_owned_for_commit_router(tmp_path)
    # The owned arm folds protection through ProtectionPolicy.resolve_for_owned
    # (the fact's two roots' configs), not the injected policy: declare "nothing
    # protected" in both roots, which is what the unprotected policy stands for.
    for root in (owned.repository_root, owned.owned_root):
        (root / ".kittify").mkdir(parents=True, exist_ok=True)
        (root / ".kittify" / "config.yaml").write_text("protection:\n  protected_branches: []\n", encoding="utf-8")
    primary_target = _make_primary_target()
    policy = _make_policy(protected=False)
    artifact = owned.repository_root / "spec.md"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("# Spec\n", encoding="utf-8")

    def _raise_resolve_topology(*_a: object, **_kw: object) -> object:
        raise AssertionError("owned arm must never call resolve_topology")

    with (
        patch(
            "specify_cli.coordination.commit_router.resolve_topology",
            side_effect=_raise_resolve_topology,
        ),
        patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            return_value=primary_target,
        ),
        patch(
            "specify_cli.coordination.commit_router.safe_commit",
            return_value=_FakeCommitResult(),
        ),
    ):
        from specify_cli.coordination.commit_router import commit_for_mission

        result = commit_for_mission(
            repo_root=owned.repository_root,
            mission_slug=owned.mission_slug,
            files=(artifact,),
            message="Add spec",
            policy=policy,
            kind=MissionArtifactKind.SPEC,
            owned=owned,
        )

    assert result.status == "committed"


def test_coord_status_dirs_names_only_status_files_inside_the_commit_worktree(tmp_path: Path) -> None:
    """Only STATUS_STATE files in the commit worktree select a status lock; the dirs come back sorted."""
    from specify_cli.coordination.commit_router import _coord_status_dirs

    worktree = tmp_path / "coord"
    b_dir = worktree / "kitty-specs" / "002-b-01M5001B"
    a_dir = worktree / "kitty-specs" / "001-a-01M5001A"
    paths = (
        b_dir / "status.events.jsonl",
        a_dir / "status.json",
        a_dir / "status.events.jsonl",
        a_dir / "acceptance-matrix.json",
        tmp_path / "elsewhere" / "kitty-specs" / "003-c" / "status.events.jsonl",
    )

    assert _coord_status_dirs(worktree, paths) == [a_dir, b_dir]


# ---------------------------------------------------------------------------
# T005 (campsite-clean WP01): focused tests for the extracted per-path
# classifier and residue-cleanup helpers. The pre-existing
# ``test_coord_staging_*`` tests above already pin the end-to-end behaviour of
# ``_stage_artifacts_in_coord_worktree``; these tests pin the five-outcome
# classification decision directly, one outcome per test.
# ---------------------------------------------------------------------------


def test_classify_stage_path_copies_a_plain_primary_artifact(tmp_path: Path) -> None:
    """A path outside ``.worktrees/`` that is neither STATUS_STATE nor the
    re-homed analysis report classifies as COPY (a "trace file" style artifact)."""
    from specify_cli.coordination.commit_router import _StagePlan, _classify_stage_path

    repo_root = tmp_path / "repo"
    coord_worktree = tmp_path / "coord"
    src = repo_root / "kitty-specs" / "001-demo" / "traces" / "approach.md"

    assert _classify_stage_path(src, src.relative_to(repo_root), coord_worktree) is _StagePlan.COPY


def test_classify_stage_path_skips_status_state_files(tmp_path: Path) -> None:
    """A STATUS_STATE path outside ``.worktrees/`` classifies as SKIP_STATUS_LOG."""
    from specify_cli.coordination.commit_router import _StagePlan, _classify_stage_path

    repo_root = tmp_path / "repo"
    coord_worktree = tmp_path / "coord"
    src = repo_root / "kitty-specs" / "001-demo" / "status.events.jsonl"

    assert _classify_stage_path(src, src.relative_to(repo_root), coord_worktree) is _StagePlan.SKIP_STATUS_LOG


def test_classify_stage_path_skips_decision_log_files(tmp_path: Path) -> None:
    """A DECISION_LOG path outside ``.worktrees/`` classifies as SKIP_DECISION_LOG (WP05 T027)."""
    from specify_cli.coordination.commit_router import _StagePlan, _classify_stage_path

    repo_root = tmp_path / "repo"
    coord_worktree = tmp_path / "coord"
    src = repo_root / "kitty-specs" / "001-demo" / "decisions.events.jsonl"

    assert _classify_stage_path(src, src.relative_to(repo_root), coord_worktree) is _StagePlan.SKIP_DECISION_LOG


def test_classify_stage_path_skips_the_rehomed_analysis_report(tmp_path: Path) -> None:
    """``analysis-report.md`` outside ``.worktrees/`` classifies as SKIP_ANALYSIS_REPORT (FR-003)."""
    from specify_cli.coordination.commit_router import _StagePlan, _classify_stage_path

    repo_root = tmp_path / "repo"
    coord_worktree = tmp_path / "coord"
    src = repo_root / "kitty-specs" / "001-demo" / "analysis-report.md"

    assert _classify_stage_path(src, src.relative_to(repo_root), coord_worktree) is _StagePlan.SKIP_ANALYSIS_REPORT


def test_classify_stage_path_keeps_a_path_already_in_this_worktree(tmp_path: Path) -> None:
    """A path directly inside THIS coordination worktree classifies as IN_PLACE."""
    from specify_cli.coordination.commit_router import _StagePlan, _classify_stage_path

    repo_root = tmp_path / "repo"
    coord_worktree = repo_root / ".worktrees" / "001-demo-coord"
    src = coord_worktree / "kitty-specs" / "001-demo" / "status.events.jsonl"

    assert _classify_stage_path(src, src.relative_to(repo_root), coord_worktree) is _StagePlan.IN_PLACE


def test_classify_stage_path_drops_a_foreign_worktree_path(tmp_path: Path) -> None:
    """A path under ``.worktrees/`` but NOT directly in this coordination worktree
    (a sibling mission's coord worktree) classifies as DROP_FOREIGN_WORKTREE."""
    from specify_cli.coordination.commit_router import _StagePlan, _classify_stage_path

    repo_root = tmp_path / "repo"
    coord_worktree = repo_root / ".worktrees" / "001-demo-coord"
    src = repo_root / ".worktrees" / "002-other-coord" / "kitty-specs" / "002-other" / "status.events.jsonl"

    assert _classify_stage_path(src, src.relative_to(repo_root), coord_worktree) is _StagePlan.DROP_FOREIGN_WORKTREE


def test_classify_stage_path_drops_an_analysis_report_inside_this_worktree(tmp_path: Path) -> None:
    """An ``analysis-report.md`` under ``.worktrees/`` is dropped even when it
    lives directly in THIS coordination worktree — its only legitimate home is
    the non-worktrees-segment SKIP_ANALYSIS_REPORT arm (FR-003)."""
    from specify_cli.coordination.commit_router import _StagePlan, _classify_stage_path

    repo_root = tmp_path / "repo"
    coord_worktree = repo_root / ".worktrees" / "001-demo-coord"
    src = coord_worktree / "kitty-specs" / "001-demo" / "analysis-report.md"

    assert _classify_stage_path(src, src.relative_to(repo_root), coord_worktree) is _StagePlan.DROP_FOREIGN_WORKTREE


def test_cleanup_staging_residue_does_nothing_when_no_paths_created_this_invocation(tmp_path: Path) -> None:
    from specify_cli.coordination.commit_router import _cleanup_staging_residue

    repo_root = tmp_path / "repo"
    src = repo_root / "kitty-specs" / "001-demo" / "tasks.md"
    src.parent.mkdir(parents=True)
    src.write_text("x", encoding="utf-8")
    dst = tmp_path / "coord" / "tasks.md"
    dst.parent.mkdir(parents=True)
    dst.write_text("x", encoding="utf-8")

    _cleanup_staging_residue([(src, dst)], None, repo_root)

    assert src.exists(), "nothing should be unlinked when primary_paths_created_this_invocation is falsy"


def test_cleanup_staging_residue_unlinks_an_identical_created_source(tmp_path: Path) -> None:
    """A primary source this invocation created IS unlinked once the coord copy matches."""
    from specify_cli.coordination.commit_router import _cleanup_staging_residue

    repo_root = tmp_path / "repo"
    src = repo_root / "kitty-specs" / "001-demo" / "tasks.md"
    src.parent.mkdir(parents=True)
    src.write_text("same bytes", encoding="utf-8")
    dst = tmp_path / "coord" / "tasks.md"
    dst.parent.mkdir(parents=True)
    dst.write_text("same bytes", encoding="utf-8")

    _cleanup_staging_residue([(src, dst)], frozenset({src}), repo_root)

    assert not src.exists()


def test_cleanup_staging_residue_keeps_a_diverged_created_source(tmp_path: Path) -> None:
    """A primary source whose coord copy has DIVERGED is kept, not unlinked."""
    from specify_cli.coordination.commit_router import _cleanup_staging_residue

    repo_root = tmp_path / "repo"
    src = repo_root / "kitty-specs" / "001-demo" / "tasks.md"
    src.parent.mkdir(parents=True)
    src.write_text("primary bytes", encoding="utf-8")
    dst = tmp_path / "coord" / "tasks.md"
    dst.parent.mkdir(parents=True)
    dst.write_text("different bytes", encoding="utf-8")

    _cleanup_staging_residue([(src, dst)], frozenset({src}), repo_root)

    assert src.exists(), "a diverged primary copy must never be unlinked"


# ---------------------------------------------------------------------------
# WP05 T027 — owning-surface translation: logs (STATUS_STATE / DECISION_LOG)
# always translate; the other COORD kinds translate only when a coordination
# copy already exists; a root log is NEVER copied over the coordination one.
# ---------------------------------------------------------------------------


def test_mission_relative_subpath_returns_the_tail_after_the_mission_slug() -> None:
    from specify_cli.coordination.commit_router import _mission_relative_subpath

    rel = Path("kitty-specs") / "001-demo" / "tasks" / "WP01" / "review-cycle-1.md"

    assert _mission_relative_subpath(rel) == Path("tasks") / "WP01" / "review-cycle-1.md"


def test_mission_relative_subpath_none_when_no_kitty_specs_segment() -> None:
    from specify_cli.coordination.commit_router import _mission_relative_subpath

    assert _mission_relative_subpath(Path("spec.md")) is None


def test_mission_relative_subpath_none_when_nothing_after_the_slug() -> None:
    from specify_cli.coordination.commit_router import _mission_relative_subpath

    assert _mission_relative_subpath(Path("kitty-specs") / "001-demo") is None


def _fake_write_location(path: Path) -> object:
    from mission_runtime import Establishment, TopologySurface, WriteLocation

    return WriteLocation(
        path=path,
        surface_root=path.parent,
        surface=TopologySurface.COORD,
        coord_state_before=None,
        establishment=Establishment.NONE,
    )


def test_act_on_stage_plan_translates_a_log_without_mission_slug_preserves_legacy_skip(tmp_path: Path) -> None:
    """No ``mission_slug`` (a legacy 3-positional caller): a log plan is bare-skipped, never copied (byte-identical to pre-WP05)."""
    from specify_cli.coordination.commit_router import _StagePlan, _act_on_stage_plan

    repo_root = tmp_path / "repo"
    coord_worktree = tmp_path / "coord"
    src = repo_root / "kitty-specs" / "001-demo" / "status.events.jsonl"

    coord_file, staged_pair = _act_on_stage_plan(
        _StagePlan.SKIP_STATUS_LOG, src, src.relative_to(repo_root), coord_worktree, repo_root, mission_slug=None, owned=None, write_dirs={}
    )

    assert coord_file is None
    assert staged_pair is None


def test_act_on_stage_plan_translates_a_log_with_mission_slug_via_write_dir(tmp_path: Path) -> None:
    """A log plan WITH ``mission_slug`` resolves ``write_dir`` and translates, never copying."""
    from specify_cli.coordination.commit_router import _StagePlan, _act_on_stage_plan

    repo_root = tmp_path / "repo"
    coord_worktree = tmp_path / "coord"
    owning_dir = coord_worktree / "kitty-specs" / "001-demo"
    src = repo_root / "kitty-specs" / "001-demo" / "decisions.events.jsonl"
    src.parent.mkdir(parents=True)
    src.write_text("root copy (never used)\n", encoding="utf-8")

    with patch(
        "specify_cli.coordination.commit_router._resolve_owning_write_dir",
        return_value=_fake_write_location(owning_dir),
    ) as resolve_write_dir:
        coord_file, staged_pair = _act_on_stage_plan(
            _StagePlan.SKIP_DECISION_LOG,
            src,
            src.relative_to(repo_root),
            coord_worktree,
            repo_root,
            mission_slug="001-demo",
            owned=None,
            write_dirs={},
        )

    assert coord_file == owning_dir / "decisions.events.jsonl"
    assert staged_pair is None, "a log is translated, never copied"
    resolve_write_dir.assert_called_once()


def test_act_on_stage_plan_non_log_coord_kind_unconditionally_overwrites_the_owning_copy(tmp_path: Path) -> None:
    """Reviewer ruling B1 (WP05 cycle 1, DECISION plan.design.translate-if-present-kinds).

    An ``ISSUE_MATRIX`` root copy ALWAYS overwrites an existing coordination
    copy -- the legacy behaviour, unconditional, exactly pre-WP05. No writer
    for this kind has migrated to ``write_dir`` yet (WP10 does), so preferring
    the existing coordination copy would silently drop the writer's update;
    ``_resolve_owning_write_dir`` (``write_dir``) is never called for this plan.
    """
    from specify_cli.coordination.commit_router import _StagePlan, _act_on_stage_plan

    repo_root = tmp_path / "repo"
    coord_worktree = tmp_path / "coord"
    src = repo_root / "kitty-specs" / "001-demo" / "issue-matrix.md"
    src.parent.mkdir(parents=True)
    src.write_text("fresh root copy\n", encoding="utf-8")
    owning = coord_worktree / "kitty-specs" / "001-demo" / "issue-matrix.md"
    owning.parent.mkdir(parents=True)
    owning.write_text("stale coord copy\n", encoding="utf-8")

    with patch("specify_cli.coordination.commit_router._resolve_owning_write_dir") as resolve_write_dir:
        coord_file, staged_pair = _act_on_stage_plan(
            _StagePlan.COPY, src, src.relative_to(repo_root), coord_worktree, repo_root, mission_slug="001-demo", owned=None, write_dirs={}
        )

    assert coord_file == owning
    assert staged_pair == (src, owning)
    assert owning.read_text(encoding="utf-8") == "fresh root copy\n", "the legacy writer's root copy must overwrite the coordination copy (B1 revert)"
    resolve_write_dir.assert_not_called()


def test_act_on_stage_plan_non_log_coord_kind_copies_when_owning_is_absent(tmp_path: Path) -> None:
    """A ``TRACER_FILE`` whose owning copy is ABSENT is copied there (legacy ``shutil.copy2``, unchanged behaviour)."""
    from specify_cli.coordination.commit_router import _StagePlan, _act_on_stage_plan

    repo_root = tmp_path / "repo"
    coord_worktree = tmp_path / "coord"
    src = repo_root / "kitty-specs" / "001-demo" / "traces" / "approach.md"
    src.parent.mkdir(parents=True)
    src.write_text("a finding\n", encoding="utf-8")

    with patch("specify_cli.coordination.commit_router._resolve_owning_write_dir") as resolve_write_dir:
        coord_file, staged_pair = _act_on_stage_plan(
            _StagePlan.COPY, src, src.relative_to(repo_root), coord_worktree, repo_root, mission_slug="001-demo", owned=None, write_dirs={}
        )

    expected_dst = coord_worktree / "kitty-specs" / "001-demo" / "traces" / "approach.md"
    assert coord_file == expected_dst
    assert staged_pair == (src, expected_dst)
    assert expected_dst.read_text(encoding="utf-8") == "a finding\n"
    resolve_write_dir.assert_not_called()


# ---------------------------------------------------------------------------
# WP05 T029 — named refusals: write_dir failures translate to a refused
# surfaces[*] entry, never a bare/swallowed exception.
# ---------------------------------------------------------------------------


def test_resolve_owning_write_dir_translates_status_lock_timeout(tmp_path: Path) -> None:
    from specify_cli.coordination.commit_router import _OwningSurfaceRefused, _resolve_owning_write_dir
    from specify_cli.status.locking import FeatureStatusLockTimeoutError

    def _raise(*_a: object, **_kw: object) -> None:
        raise FeatureStatusLockTimeoutError("status lock contended", lock_path=tmp_path / ".status.lock", timeout=5.0, holder=None)

    with patch("mission_runtime.placement_seam") as fake_seam:
        fake_seam.return_value.write_dir.side_effect = _raise
        with pytest.raises(_OwningSurfaceRefused) as excinfo:
            _resolve_owning_write_dir(
                tmp_path, MissionArtifactKind.STATUS_STATE, mission_slug="001-demo", owned=None, rel=Path("kitty-specs/001-demo/status.events.jsonl")
            )

    assert excinfo.value.reason == "STATUS_LOCK_HELD"
    assert excinfo.value.path == "kitty-specs/001-demo/status.events.jsonl"


def test_resolve_owning_write_dir_translates_coordination_branch_deleted(tmp_path: Path) -> None:
    from specify_cli.coordination.commit_router import _OwningSurfaceRefused, _resolve_owning_write_dir
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    def _raise(*_a: object, **_kw: object) -> None:
        raise CoordinationBranchDeleted(
            repo_root=tmp_path,
            mission_slug="001-demo",
            mid8="01ABCDEF",
            coordination_branch="kitty/mission-001-demo-01ABCDEF",
            coord_candidate=tmp_path / "coord",
            primary_candidate=tmp_path / "primary",
        )

    with patch("mission_runtime.placement_seam") as fake_seam:
        fake_seam.return_value.write_dir.side_effect = _raise
        with pytest.raises(_OwningSurfaceRefused) as excinfo:
            _resolve_owning_write_dir(
                tmp_path, MissionArtifactKind.DECISION_LOG, mission_slug="001-demo", owned=None, rel=Path("kitty-specs/001-demo/decisions.events.jsonl")
            )

    assert excinfo.value.reason == "COORDINATION_BRANCH_DELETED"


def test_translate_to_owning_surface_refuses_an_unroutable_kind(tmp_path: Path) -> None:
    """A path whose kind cannot be classified is PATH_UNROUTABLE, never silently coerced."""
    from specify_cli.coordination.commit_router import _OwningSurfaceRefused, _translate_to_owning_surface

    with pytest.raises(_OwningSurfaceRefused) as excinfo:
        _translate_to_owning_surface(tmp_path, Path("kitty-specs") / "001-demo" / "some-unrecognised-file.xyz", mission_slug="001-demo", owned=None, write_dirs={})

    assert excinfo.value.reason == "PATH_UNROUTABLE"


def test_commit_partition_group_maps_owning_surface_refused_to_named_reason(tmp_path: Path) -> None:
    """A :class:`_OwningSurfaceRefused` raised during staging becomes a named ``refused`` surfaces[*] entry (T029)."""
    from specify_cli.coordination.commit_router import _OwningSurfaceRefused

    mission_slug = "001-my-mission"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    status_log = feature_dir / "status.events.jsonl"
    status_log.write_text('{"row": 1}\n', encoding="utf-8")

    def _raise_refused(*_a: object, **_kw: object) -> None:
        raise _OwningSurfaceRefused(
            path="kitty-specs/001-my-mission/status.events.jsonl", reason="STATUS_LOCK_HELD", diagnostic="status lock held by another writer"
        )

    with (
        _patch_topology(coord=True),
        _patch_primary_target(),
        patch("specify_cli.coordination.commit_router.resolve_placement_only", return_value=_make_coord_target()),
        patch("specify_cli.coordination.commit_router._materialise_coord_worktree", side_effect=_raise_refused),
    ):
        from specify_cli.coordination.commit_router import commit_for_mission

        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug=mission_slug,
            files=(status_log,),
            message="chore(status): commit",
            policy=_make_policy(protected=False),
            kind=MissionArtifactKind.STATUS_STATE,
        )

    assert result.status == "error"
    assert len(result.surfaces) == 1
    surface = result.surfaces[0]
    assert surface.surface == "coordination"
    assert surface.status == "refused"
    assert surface.refused == (PathFate(path="kitty-specs/001-my-mission/status.events.jsonl", reason="STATUS_LOCK_HELD"),)
    assert commit_outcome_exit_code(result) == 1


@pytest.mark.parametrize(
    "reason",
    [STATUS_LOCK_HELD, COORDINATION_BRANCH_DELETED, COORDINATION_WORKTREE_UNMATERIALIZED, COORD_SEED_FORK_REFUSED, PATH_UNROUTABLE],
)
def test_every_named_owning_surface_reason_is_refused_with_exit_code_1(tmp_path: Path, reason: str) -> None:
    """T029: one case per named ``write_dir``-sourced refusal reason, end-to-end through ``commit_for_mission``.

    Each reason reaches ``surfaces[*].refused[*].reason`` verbatim, and
    ``commit_outcome_exit_code`` is 1 for every one of them -- never a bare
    status with no named reason.
    """
    from specify_cli.coordination.commit_router import _OwningSurfaceRefused

    mission_slug = "001-my-mission"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    status_log = feature_dir / "status.events.jsonl"
    status_log.write_text('{"row": 1}\n', encoding="utf-8")

    def _raise_refused(*_a: object, **_kw: object) -> None:
        raise _OwningSurfaceRefused(path="kitty-specs/001-my-mission/status.events.jsonl", reason=reason, diagnostic=f"synthetic {reason} for T029 coverage")

    with (
        _patch_topology(coord=True),
        _patch_primary_target(),
        patch("specify_cli.coordination.commit_router.resolve_placement_only", return_value=_make_coord_target()),
        patch("specify_cli.coordination.commit_router._materialise_coord_worktree", side_effect=_raise_refused),
    ):
        from specify_cli.coordination.commit_router import commit_for_mission

        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug=mission_slug,
            files=(status_log,),
            message="chore(status): commit",
            policy=_make_policy(protected=False),
            kind=MissionArtifactKind.STATUS_STATE,
        )

    assert result.status == "error"
    assert len(result.surfaces) == 1
    surface = result.surfaces[0]
    assert surface.status == "refused"
    assert surface.refused[0].reason == reason
    assert commit_outcome_exit_code(result) == 1


def test_protected_branch_refused_reason_and_exit_code(tmp_path: Path) -> None:
    """T029: the protected-primary refusal arm of ``_commit_partition_group`` names ``PROTECTED_BRANCH_REFUSED`` with exit code 1."""
    mission_slug = "001-my-mission"
    artifact = tmp_path / "WP01.md"
    artifact.write_text("# WP01\n", encoding="utf-8")

    with (
        _patch_topology(coord=True),
        _patch_primary_target(),
        patch("specify_cli.coordination.commit_router.resolve_placement_only", return_value=_make_primary_target()),
    ):
        from specify_cli.coordination.commit_router import commit_for_mission

        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug=mission_slug,
            files=(artifact,),
            message="Add WP01",
            policy=_make_policy(protected=True),
            kind=MissionArtifactKind.WORK_PACKAGE_TASK,
        )

    assert result.status == "no_op_wrong_surface"
    assert len(result.surfaces) == 1
    surface = result.surfaces[0]
    assert surface.surface == "primary"
    assert surface.status == "refused"
    assert surface.refused[0].reason == PROTECTED_BRANCH_REFUSED
    assert commit_outcome_exit_code(result) == 1


def test_classify_no_commit_paths_wrong_surface_reason_and_exit_code(tmp_path: Path) -> None:
    """T029: the B16 wrong-surface arm of ``_classify_no_commit_paths`` names ``WRONG_SURFACE`` with exit code 1.

    A coord-routed group whose staging produced no ``commit_paths`` (simulated
    directly here) but whose caller-named file is STILL dirty in the PRIMARY
    checkout must refuse, named, never report a bare ``unchanged``.
    """
    from mission_runtime import CommitTarget
    from specify_cli.coordination.commit_router import _classify_no_commit_paths

    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    dirty_file = repo_root / "kitty-specs" / "001-demo" / "status.events.jsonl"
    dirty_file.parent.mkdir(parents=True)
    dirty_file.write_text("never staged to coord\n", encoding="utf-8")
    # Untracked counts as dirty per `git status --porcelain` (_paths_uncommitted_in_primary).

    result = _classify_no_commit_paths(repo_root, (dirty_file,), use_coord=True, placement=CommitTarget(ref="kitty/mission-001-demo-ABCDEF01"))

    assert result.status == "no_op_wrong_surface"
    assert len(result.surfaces) == 1
    surface = result.surfaces[0]
    assert surface.surface == "coordination"
    assert surface.status == "refused"
    assert surface.refused[0].reason == WRONG_SURFACE
    assert commit_outcome_exit_code(result) == 1


def test_resolve_owning_write_dir_translates_coordination_worktree_unmaterialized(tmp_path: Path) -> None:
    from specify_cli.coordination.commit_router import _OwningSurfaceRefused, _resolve_owning_write_dir
    from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized

    _init_repo(tmp_path)

    def _raise(*_a: object, **_kw: object) -> None:
        raise CoordinationWorktreeUnmaterialized(
            repo_root=tmp_path,
            mission_slug="001-demo",
            mid8="01ABCDEF",
            coordination_branch="kitty/mission-001-demo-01ABCDEF",
            coord_candidate=tmp_path / "coord",
            primary_candidate=tmp_path / "primary",
        )

    with patch("mission_runtime.placement_seam") as fake_seam:
        fake_seam.return_value.write_dir.side_effect = _raise
        with pytest.raises(_OwningSurfaceRefused) as excinfo:
            _resolve_owning_write_dir(
                tmp_path, MissionArtifactKind.STATUS_STATE, mission_slug="001-demo", owned=None, rel=Path("kitty-specs/001-demo/status.events.jsonl")
            )

    assert excinfo.value.reason == "COORDINATION_WORKTREE_UNMATERIALIZED"


def test_resolve_owning_write_dir_translates_coord_seed_fork_refused(tmp_path: Path) -> None:
    from specify_cli.coordination.commit_router import _OwningSurfaceRefused, _resolve_owning_write_dir
    from specify_cli.coordination.coord_seed import CoordSeedForkRefused

    def _raise(*_a: object, **_kw: object) -> None:
        raise CoordSeedForkRefused(
            root_path=tmp_path / "kitty-specs" / "001-demo" / "status.events.jsonl",
            coord_path="kitty-specs/001-demo/status.events.jsonl",
            coord_ref="kitty/mission-001-demo-01ABCDEF",
            first_divergence_root="01HXYZ0001",
            first_divergence_coord="01HXYZ0002",
            reconcile_steps=("inspect with `spec-kitty doctor decisions`",),
        )

    with patch("mission_runtime.placement_seam") as fake_seam:
        fake_seam.return_value.write_dir.side_effect = _raise
        with pytest.raises(_OwningSurfaceRefused) as excinfo:
            _resolve_owning_write_dir(
                tmp_path, MissionArtifactKind.STATUS_STATE, mission_slug="001-demo", owned=None, rel=Path("kitty-specs/001-demo/status.events.jsonl")
            )

    assert excinfo.value.reason == "COORD_SEED_FORK_REFUSED"


def test_translate_to_owning_surface_refuses_a_non_mission_relative_path(tmp_path: Path) -> None:
    """T029: the SECOND ``PATH_UNROUTABLE`` arm -- a classifiable kind whose path has no Mission-relative tail.

    Distinct from ``test_translate_to_owning_surface_refuses_an_unroutable_kind``
    (which hits the FIRST arm, ``kind_for_mission_file`` returning ``None``):
    this forces a real kind via a patched classifier for a path that does not
    contain a ``kitty-specs/<slug>/...`` shape at all, so
    ``_mission_relative_subpath`` -- not the kind lookup -- is what fails.
    """
    from specify_cli.coordination.commit_router import _OwningSurfaceRefused, _translate_to_owning_surface

    with (
        patch("specify_cli.coordination.commit_router.kind_for_mission_file", return_value=MissionArtifactKind.STATUS_STATE),
        pytest.raises(_OwningSurfaceRefused) as excinfo,
    ):
        _translate_to_owning_surface(tmp_path, Path("some") / "other" / "path.txt", mission_slug="001-demo", owned=None, write_dirs={})

    assert excinfo.value.reason == "PATH_UNROUTABLE"


def test_act_on_stage_plan_in_place_never_calls_write_dir(tmp_path: Path) -> None:
    """Binding "Recursion" (WP03 seed hazard): a path already IN_PLACE never resolves ``write_dir``.

    The WP03 seed commits through ``commit_for_mission`` with paths already
    inside the coordination worktree -- ``_classify_stage_path`` routes those
    to ``IN_PLACE`` BEFORE either log plan is even considered, so the seed's
    own commit can never recursively re-enter ``establish_coord_write_location``
    (the seed itself) via this module's staging path.
    """
    from specify_cli.coordination.commit_router import _StagePlan, _act_on_stage_plan

    repo_root = tmp_path / "repo"
    coord_worktree = repo_root / ".worktrees" / "001-demo-coord"
    src = coord_worktree / "kitty-specs" / "001-demo" / "status.events.jsonl"
    src.parent.mkdir(parents=True)
    src.write_text('{"seeded": true}\n', encoding="utf-8")

    with patch("specify_cli.coordination.commit_router._resolve_owning_write_dir") as resolve_write_dir:
        coord_file, staged_pair = _act_on_stage_plan(
            _StagePlan.IN_PLACE,
            src,
            src.relative_to(repo_root),
            coord_worktree,
            repo_root,
            mission_slug="001-demo",
            owned=None,
            write_dirs={},
        )

    assert coord_file == src
    assert staged_pair is None
    resolve_write_dir.assert_not_called()


# ---------------------------------------------------------------------------
# WP05 T028 — ``COORD_RECORD_IN_ROOT_CHECKOUT``: an owning-surface commit that
# is genuinely unchanged is re-classified when the caller's OWN root-checkout
# copy is also dirty (never silently masked as a bare no-op).
# ---------------------------------------------------------------------------


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)


def test_refine_unchanged_for_root_checkout_dirt_marks_dirty_root_copy(tmp_path: Path) -> None:
    from mission_runtime import CommitTarget
    from specify_cli.coordination.commit_router import (
        CommitRouterResult,
        PathFate,
        SurfaceOutcome,
        _refine_unchanged_for_root_checkout_dirt,
    )

    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    root_file = repo_root / "kitty-specs" / "001-demo" / "status.events.jsonl"
    root_file.parent.mkdir(parents=True)
    root_file.write_text('{"committed": true}\n', encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=repo_root, check=True)
    # Dirty the root copy AFTER the commit -- the owning (coordination) copy is
    # unrelated and reported clean by the (already-built) ``unchanged`` result.
    root_file.write_text('{"committed": true, "dirty_root_edit": true}\n', encoding="utf-8")

    base_result = CommitRouterResult(
        status="unchanged",
        placement_ref="kitty/mission-001-demo-ABCDEF01",
        reason="no_op_no_changes",
        surfaces=(
            SurfaceOutcome(
                surface="coordination",
                branch="kitty/mission-001-demo-ABCDEF01",
                status="unchanged",
                commit_hash=None,
                skipped=(PathFate(path="kitty-specs/001-demo/status.events.jsonl", reason="no_op_no_changes"),),
            ),
        ),
    )

    refined = _refine_unchanged_for_root_checkout_dirt(
        base_result,
        repo_root,
        (root_file,),
        use_coord=True,
        surface_name="coordination",
        placement=CommitTarget(ref="kitty/mission-001-demo-ABCDEF01"),
    )

    assert refined.status == "unchanged"
    assert len(refined.surfaces) == 1
    assert refined.surfaces[0].skipped == (PathFate(path="kitty-specs/001-demo/status.events.jsonl", reason=COORD_RECORD_IN_ROOT_CHECKOUT),)


def test_refine_unchanged_for_root_checkout_dirt_is_a_noop_when_root_is_clean(tmp_path: Path) -> None:
    from mission_runtime import CommitTarget
    from specify_cli.coordination.commit_router import (
        CommitRouterResult,
        PathFate,
        SurfaceOutcome,
        _refine_unchanged_for_root_checkout_dirt,
    )

    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    root_file = repo_root / "kitty-specs" / "001-demo" / "status.events.jsonl"
    root_file.parent.mkdir(parents=True)
    root_file.write_text('{"committed": true}\n', encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=repo_root, check=True)

    base_result = CommitRouterResult(
        status="unchanged",
        placement_ref="kitty/mission-001-demo-ABCDEF01",
        reason="no_op_no_changes",
        surfaces=(
            SurfaceOutcome(
                surface="coordination",
                branch="kitty/mission-001-demo-ABCDEF01",
                status="unchanged",
                commit_hash=None,
                skipped=(PathFate(path="kitty-specs/001-demo/status.events.jsonl", reason="no_op_no_changes"),),
            ),
        ),
    )

    refined = _refine_unchanged_for_root_checkout_dirt(
        base_result,
        repo_root,
        (root_file,),
        use_coord=True,
        surface_name="coordination",
        placement=CommitTarget(ref="kitty/mission-001-demo-ABCDEF01"),
    )

    assert refined is base_result


def test_refine_unchanged_for_root_checkout_dirt_skips_non_coord_groups(tmp_path: Path) -> None:
    from mission_runtime import CommitTarget
    from specify_cli.coordination.commit_router import CommitRouterResult, _refine_unchanged_for_root_checkout_dirt

    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    base_result = CommitRouterResult(status="unchanged", placement_ref="main", reason="no_op_no_changes")

    refined = _refine_unchanged_for_root_checkout_dirt(
        base_result, repo_root, (repo_root / "spec.md",), use_coord=False, surface_name="primary", placement=CommitTarget(ref="main")
    )

    assert refined is base_result


# ---------------------------------------------------------------------------
# WP05 T027 — end-to-end: a DECISION_LOG root-path input commits the
# coordination copy (real git fixture, mirrors R2's STATUS_STATE coverage).
# ---------------------------------------------------------------------------


def test_decision_log_root_path_input_commits_the_coordination_copy(tmp_path: Path) -> None:
    """A real coord mission: a DECISION_LOG file passed by its root-checkout path lands on the coordination copy."""
    from mission_runtime import placement_seam
    from specify_cli.coordination.commit_router import commit_for_mission
    from tests.terminus.conftest import build_coord_mission

    mission = build_coord_mission(tmp_path, target_branch="feature/router-decision-log")
    owning_dir = placement_seam(mission.repo, mission.slug).write_dir(MissionArtifactKind.DECISION_LOG).path
    owning_log = owning_dir / "decisions.events.jsonl"
    owning_log.parent.mkdir(parents=True, exist_ok=True)
    owning_log.write_text('{"simulated": "decision row"}\n', encoding="utf-8")

    root_log = mission.feature_dir / "decisions.events.jsonl"
    root_log.parent.mkdir(parents=True, exist_ok=True)
    root_log.write_text("", encoding="utf-8")

    result = commit_for_mission(
        mission.repo,
        mission.slug,
        (root_log,),
        "chore(decisions): commit the decision log",
        ProtectionPolicy.resolve(mission.repo),
        kind=MissionArtifactKind.DECISION_LOG,
    )

    assert result.status == "committed", result
    committed = subprocess.run(
        ["git", "show", f"{result.placement_ref}:kitty-specs/{mission.slug}/decisions.events.jsonl"],
        cwd=mission.repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "decision row" in committed
    # The root copy (empty) is NEVER copied over the owning (coordination) one.
    assert owning_log.read_text(encoding="utf-8") != root_log.read_text(encoding="utf-8")


def test_decision_log_clean_coord_with_dirty_root_reports_coord_record_in_root_checkout(tmp_path: Path) -> None:
    """T028: a clean owning DECISION_LOG copy, with the root copy dirty, is ``unchanged`` + named ``COORD_RECORD_IN_ROOT_CHECKOUT``; the target is unchanged."""
    from mission_runtime import placement_seam
    from specify_cli.coordination.commit_router import commit_for_mission
    from tests.terminus.conftest import build_coord_mission

    mission = build_coord_mission(tmp_path, target_branch="feature/router-decision-log-root-dirt")
    location = placement_seam(mission.repo, mission.slug).write_dir(MissionArtifactKind.DECISION_LOG)
    owning_log = location.path / "decisions.events.jsonl"
    owning_log.parent.mkdir(parents=True, exist_ok=True)
    owning_log.write_text('{"simulated": "decision row"}\n', encoding="utf-8")
    owning_rel = owning_log.relative_to(location.surface_root)
    subprocess.run(["git", "add", "--", str(owning_rel)], cwd=location.surface_root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline decision log"], cwd=location.surface_root, check=True, capture_output=True)

    root_log = mission.feature_dir / "decisions.events.jsonl"
    root_log.parent.mkdir(parents=True, exist_ok=True)
    root_log.write_text('{"operator edited root directly": true}\n', encoding="utf-8")
    target_sha_before = mission.rev(mission.target_branch)

    result = commit_for_mission(
        mission.repo,
        mission.slug,
        (root_log,),
        "chore(decisions): commit the decision log",
        ProtectionPolicy.resolve(mission.repo),
        kind=MissionArtifactKind.DECISION_LOG,
    )

    assert result.status == "unchanged", result
    assert len(result.surfaces) == 1
    surface = result.surfaces[0]
    assert surface.status == "unchanged"
    root_rel = root_log.relative_to(mission.repo).as_posix()
    assert any(fate.path == root_rel and fate.reason == COORD_RECORD_IN_ROOT_CHECKOUT for fate in surface.skipped), surface.skipped
    assert mission.rev(mission.target_branch) == target_sha_before, "the target branch must stay unchanged"


def test_decision_log_both_clean_reports_unchanged(tmp_path: Path) -> None:
    """T028 positive control: a DECISION_LOG clean on BOTH surfaces is a genuine no-op."""
    from mission_runtime import placement_seam
    from specify_cli.coordination.commit_router import commit_for_mission
    from tests.terminus.conftest import build_coord_mission

    mission = build_coord_mission(tmp_path, target_branch="feature/router-decision-log-clean")
    location = placement_seam(mission.repo, mission.slug).write_dir(MissionArtifactKind.DECISION_LOG)
    owning_log = location.path / "decisions.events.jsonl"
    owning_log.parent.mkdir(parents=True, exist_ok=True)
    owning_log.write_text('{"simulated": "decision row"}\n', encoding="utf-8")
    owning_rel = owning_log.relative_to(location.surface_root)
    subprocess.run(["git", "add", "--", str(owning_rel)], cwd=location.surface_root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline decision log"], cwd=location.surface_root, check=True, capture_output=True)

    root_log = mission.feature_dir / "decisions.events.jsonl"
    root_log.parent.mkdir(parents=True, exist_ok=True)
    root_log.write_text("", encoding="utf-8")
    target_sha_before = mission.rev(mission.target_branch)

    result = commit_for_mission(
        mission.repo,
        mission.slug,
        (root_log,),
        "chore(decisions): commit the decision log",
        ProtectionPolicy.resolve(mission.repo),
        kind=MissionArtifactKind.DECISION_LOG,
    )

    assert result.status == "unchanged", result
    assert mission.rev(mission.target_branch) == target_sha_before


# ---------------------------------------------------------------------------
# R2 / R2b (#5513) — folded in from the adopted standalone
# test_commit_router_coord_only_dirty_status_log.py (DoD, post-tasks squad
# R-M8/FR-016) once GREEN: a status log dirty only in the coordination
# worktree is committed there, never reported ``unchanged``; a genuinely
# clean coordination copy still reports ``unchanged`` (the positive control).
# Adopted originally via ``git cherry-pick -x 251bea520f``
# (``upstream/test/p0-repro-5513``, PR #5520).
# ---------------------------------------------------------------------------

_R2_STATUS_EVENTS = "status.events.jsonl"
_R2_COORD_ONLY_ROW = '{"simulated": "row appended only in the coordination worktree (#5513)"}\n'
#: T026 step 3: an outcome other than ``committed`` on the standard fixture
#: passes only if backed by one of these NAMED reasons (never a bare status).
_R2_NAMED_REFUSAL_REASONS = frozenset({PROTECTED_BRANCH_REFUSED, STATUS_LOCK_HELD, COORDINATION_BRANCH_DELETED, PATH_UNROUTABLE})


def _r2_porcelain(cwd: Path, rel: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", rel.as_posix()], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _build_coord_mission_with_baseline_status_log(tmp_path: Path) -> tuple[CoordMission, Path, Path, Path]:
    """A real coord mission whose status log is committed and CLEAN on both surfaces.

    Returns ``(mission, primary_log, coord_log, coord_worktree)``.
    """
    from specify_cli.coordination.surface_resolver import resolve_status_surface
    from specify_cli.coordination.workspace import CoordinationWorkspace
    from tests.terminus.conftest import build_coord_mission

    mission = build_coord_mission(tmp_path, target_branch="feature/router-5513")
    coord = CoordinationWorkspace.worktree_path(mission.repo, mission.slug, mission.mid8)
    coord_log = resolve_status_surface(mission.repo, mission.slug)
    primary_log = mission.feature_dir / _R2_STATUS_EVENTS
    assert coord_log.is_relative_to(coord), f"fixture must put the canonical status log in the coord worktree: {coord_log}"
    assert primary_log.is_file(), f"fixture must carry a committed primary copy of the status log: {primary_log}"

    coord_rel = coord_log.relative_to(coord)
    subprocess.run(["git", "add", "--", coord_rel.as_posix()], cwd=coord, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=coord, check=False, capture_output=True)
    assert _r2_porcelain(coord, coord_rel) == "", "precondition: coord status log starts committed"
    return mission, primary_log, coord_log, coord


def _coord_mission_with_coord_only_dirty_log(tmp_path: Path) -> tuple[CoordMission, Path, Path, Path]:
    """A real coord mission whose status log is dirty ONLY in the coordination worktree.

    Returns ``(mission, primary_log, coord_log, coord_worktree)``. Both copies of the
    log start committed and clean; then one row is appended to the coordination copy
    only, so the primary checkout stays clean.
    """
    mission, primary_log, coord_log, coord = _build_coord_mission_with_baseline_status_log(tmp_path)
    coord_rel = coord_log.relative_to(coord)

    with coord_log.open("a", encoding="utf-8") as fh:
        fh.write(_R2_COORD_ONLY_ROW)

    assert _r2_porcelain(coord, coord_rel) != "", "precondition: coord status log is dirty"
    primary_rel = primary_log.relative_to(mission.repo)
    assert _r2_porcelain(mission.repo, primary_rel) == "", "precondition: primary status log is clean (dirty ONLY on coord)"
    return mission, primary_log, coord_log, coord


def _r2_route_status_log(mission: CoordMission, primary_log: Path) -> CommitRouterResult:
    from specify_cli.coordination.commit_router import commit_for_mission

    return commit_for_mission(
        mission.repo,
        mission.slug,
        (primary_log,),
        "chore(status): commit the mission status log (#5513 reproduction)",
        ProtectionPolicy.resolve(mission.repo),
        kind=MissionArtifactKind.STATUS_STATE,
    )


@pytest.mark.git_repo
def test_router_never_reports_a_coord_only_dirty_status_log_as_unchanged(tmp_path: Path) -> None:
    """R2 (#5513): a status log dirty only in the coord worktree is committed there, never ``unchanged``.

    Tightened (WP05 T026, post-tasks squad R-M8/FR-016 R2 adoption): on this
    STANDARD fixture (healthy coordination worktree, no lock contention), the
    router must commit outright -- there is no legitimate reason to refuse
    here. A result other than ``committed`` would need a NAMED reason in
    ``surfaces[*].refused`` (never a bare status label) to be defensible at
    all; this fixture has none of those conditions, so anything but
    ``committed`` is a defect.
    """
    mission, primary_log, coord_log, coord = _coord_mission_with_coord_only_dirty_log(tmp_path)
    coord_rel = coord_log.relative_to(coord)
    coord_head_before = _coord_head(coord)

    result = _r2_route_status_log(mission, primary_log)

    coord_dirty_after = _r2_porcelain(coord, coord_rel)
    coord_head_after = _coord_head(coord)

    assert result.status != "unchanged", (
        f"commit_for_mission reported status={result.status!r} reason={result.reason!r} "
        f"placement_ref={result.placement_ref!r} for a status log that is dirty in the "
        f"coordination worktree ({coord_rel.as_posix()}: {coord_dirty_after!r}); nothing was "
        f"committed (coord HEAD unchanged: {coord_head_after == coord_head_before}) and no error "
        f"surfaced (#5513 silent skip)."
    )

    if result.status != "committed":
        named_reasons = {fate.reason for surface in result.surfaces for fate in surface.refused}
        assert named_reasons & _R2_NAMED_REFUSAL_REASONS, (
            f"a non-committed result must carry a NAMED refusal reason in surfaces[*].refused "
            f"(one of {sorted(_R2_NAMED_REFUSAL_REASONS)}); got status={result.status!r} "
            f"surfaces={result.surfaces!r}"
        )
        pytest.fail(
            f"the standard fixture (healthy worktree, no contention) must commit outright; "
            f"got status={result.status!r} with named reasons {named_reasons & _R2_NAMED_REFUSAL_REASONS!r} "
            f"-- investigate why this healthy fixture hit a refusal path at all."
        )

    assert coord_head_after != coord_head_before, "a 'committed' result must advance the coordination branch"
    assert coord_dirty_after == "", f"a 'committed' result must leave the coord status log clean: {coord_dirty_after!r}"
    committed = subprocess.run(["git", "show", f"HEAD:{coord_rel.as_posix()}"], cwd=coord, check=True, capture_output=True, text=True).stdout.strip()
    assert committed.endswith(_R2_COORD_ONLY_ROW.rstrip("\n")), "the coord-only row must be in the committed log"


@pytest.mark.git_repo
def test_clean_coordination_copy_reports_unchanged(tmp_path: Path) -> None:
    """R2b (positive control): a genuinely CLEAN coordination copy still reports ``unchanged``.

    Proves R2's tightened assertion did not over-correct into "always commit" --
    a status log that is clean on BOTH surfaces is a genuine no-op.
    """
    mission, primary_log, coord_log, coord = _build_coord_mission_with_baseline_status_log(tmp_path)
    coord_rel = coord_log.relative_to(coord)
    coord_head_before = _coord_head(coord)

    result = _r2_route_status_log(mission, primary_log)

    assert result.status == "unchanged", f"a clean coordination copy must report unchanged, got {result!r}"
    assert _coord_head(coord) == coord_head_before, "a genuine no-op must not advance the coordination branch"
    assert _r2_porcelain(coord, coord_rel) == "", "the coordination copy must stay clean"


def test_status_state_clean_coord_with_dirty_root_reports_coord_record_in_root_checkout(tmp_path: Path) -> None:
    """T028: a clean owning STATUS_STATE copy, with the root copy dirty, is ``unchanged`` + named ``COORD_RECORD_IN_ROOT_CHECKOUT``; the target is unchanged.

    Complements R2 (coord-dirty -> committed) and R2b (both-clean -> unchanged):
    this is the third T028 case for STATUS_STATE -- the operator edited the
    root checkout's copy directly (never the coordination one), so the
    coordination surface is a genuine no-op but the root edit is named, not
    silently swallowed as a bare ``no_op_no_changes``.
    """
    mission, primary_log, coord_log, coord = _build_coord_mission_with_baseline_status_log(tmp_path)
    with primary_log.open("a", encoding="utf-8") as fh:
        fh.write('{"operator edited root directly": true}\n')
    target_sha_before = mission.rev(mission.target_branch)
    coord_head_before = _coord_head(coord)

    result = _r2_route_status_log(mission, primary_log)

    assert result.status == "unchanged", result
    assert len(result.surfaces) == 1
    surface = result.surfaces[0]
    root_rel = primary_log.relative_to(mission.repo).as_posix()
    assert any(fate.path == root_rel and fate.reason == COORD_RECORD_IN_ROOT_CHECKOUT for fate in surface.skipped), surface.skipped
    assert mission.rev(mission.target_branch) == target_sha_before, "the target branch must stay unchanged"
    assert _coord_head(coord) == coord_head_before, "the coordination branch must stay unchanged (genuine no-op there)"
    assert _r2_porcelain(coord, coord_log.relative_to(coord)) == "", "the coordination copy must stay clean"


def test_acceptance_matrix_root_dirty_is_copied_and_committed_end_to_end(tmp_path: Path) -> None:
    """T028 (legacy, non-log, COORD kind): a dirty root ACCEPTANCE_MATRIX is copied over the coordination copy and committed.

    End-to-end through ``commit_for_mission`` (not just the ``_act_on_stage_plan``
    unit level): proves the B1-reverted unconditional legacy overwrite still
    lands a real commit on the coordination branch through the full pipeline.
    """
    from tests.terminus.conftest import build_coord_mission

    mission = build_coord_mission(tmp_path, target_branch="feature/router-acceptance-matrix")
    root_matrix = mission.feature_dir / "acceptance-matrix.json"
    root_matrix.parent.mkdir(parents=True, exist_ok=True)
    root_matrix.write_text('{"rows": {"T0001": "fixed"}}\n', encoding="utf-8")

    from specify_cli.coordination.commit_router import commit_for_mission

    result = commit_for_mission(
        mission.repo,
        mission.slug,
        (root_matrix,),
        "chore(accept): commit the acceptance matrix",
        ProtectionPolicy.resolve(mission.repo),
        kind=MissionArtifactKind.ACCEPTANCE_MATRIX,
    )

    assert result.status == "committed", result
    committed = subprocess.run(
        ["git", "show", f"{result.placement_ref}:kitty-specs/{mission.slug}/acceptance-matrix.json"],
        cwd=mission.repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "T0001" in committed


# ---------------------------------------------------------------------------
# WP05 T025 (P-M5) — the public per-path partition predicate agrees with
# _group_files_by_partition's own grouping (same function, not a copy).
# ---------------------------------------------------------------------------


def test_partition_for_mission_path_matches_group_files_by_partition(tmp_path: Path) -> None:
    """The public predicate names the SAME verdict ``_group_files_by_partition`` groups by (P-M5)."""
    from specify_cli.coordination.commit_router import (
        _group_files_by_partition,
        partition_for_mission_path,
    )

    mission_slug = "001-demo"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    tasks_file = feature_dir / "tasks.md"
    tasks_file.write_text("# Tasks\n", encoding="utf-8")
    matrix_file = feature_dir / "acceptance-matrix.json"
    matrix_file.write_text("{}", encoding="utf-8")

    assert partition_for_mission_path(tmp_path, mission_slug, tasks_file) == "primary"
    assert partition_for_mission_path(tmp_path, mission_slug, matrix_file) == "coordination"

    with patch(
        "specify_cli.coordination.commit_router.resolve_placement_only",
        side_effect=_fake_resolve_placement_only_by_partition,
    ):
        groups = _group_files_by_partition(tmp_path, (tasks_file, matrix_file), mission_slug, kind=MissionArtifactKind.TASKS_INDEX)

    # Exactly the two files, split into their own groups -- and each group's
    # own files agree with the public predicate's verdict for them.
    assert {file for _kind, files in groups for file in files} == {tasks_file, matrix_file}
    primary_group_files = next(files for kind, files in groups if is_primary_artifact_kind(kind))
    coord_group_files = next(files for kind, files in groups if not is_primary_artifact_kind(kind))
    for file in primary_group_files:
        assert partition_for_mission_path(tmp_path, mission_slug, file) == "primary"
    for file in coord_group_files:
        assert partition_for_mission_path(tmp_path, mission_slug, file) == "coordination"


# ---------------------------------------------------------------------------
# #5651 (nightly-suites-green WP02): a coordination Mission whose PRIMARY
# directory is the bare slug while its coordination directory is the composed
# ``<slug>-<mid8>`` name.  The seed commit passes the bare slug and the
# composed-directory status files; they must group to the COORD partition and
# commit on the coordination branch even though the primary branch is protected.
# ---------------------------------------------------------------------------

_BARE_SLUG_MID8 = "01M5651A"
_BARE_SLUG = "bare-slug-coord"


def _git_out(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _bare_slug_coord_mission(tmp_path: Path, mid8: str = _BARE_SLUG_MID8) -> tuple[Path, Path, tuple[Path, Path], str]:
    """A real coordination Mission: bare primary directory, composed coordination directory.

    Returns ``(repo, coordination worktree, (status log, status snapshot), coordination branch)``.
    The two status files exist only in the coordination worktree and are untracked, exactly
    what the consolidate-time seed leaves behind before its commit. ``mid8`` is the recorded
    identity verbatim: nothing normalises its case or shape before the composed names are built.
    """
    import json

    from specify_cli.coordination.workspace import CoordinationWorkspace
    from tests.terminus.conftest import _init_fixture_repo

    mission = _init_fixture_repo(tmp_path, mid8=_BARE_SLUG_MID8, slug=_BARE_SLUG, target_branch="main")
    repo = mission.repo
    coord_branch = CoordinationWorkspace.branch_name(_BARE_SLUG, mid8)
    meta = {
        "mission_slug": _BARE_SLUG,
        "mission_id": (mid8 + "0" * 26)[:26],
        "mid8": mid8,
        "target_branch": "main",
        "coordination_branch": coord_branch,
        "topology": "coord",
    }
    mission.feature_dir.mkdir(parents=True)
    (mission.feature_dir / "meta.json").write_text(json.dumps(meta, sort_keys=True) + "\n", encoding="utf-8")
    _git_out(repo, "add", "kitty-specs")
    _git_out(repo, "commit", "-qm", "bootstrap bare-slug coord mission")
    _git_out(repo, "branch", coord_branch)
    coord = CoordinationWorkspace.resolve(repo, _BARE_SLUG, mid8)

    composed_dir = coord / "kitty-specs" / f"{_BARE_SLUG}-{mid8}"
    composed_dir.mkdir(parents=True)
    log = composed_dir / "status.events.jsonl"
    snapshot = composed_dir / "status.json"
    log.write_text('{"event": 1}\n', encoding="utf-8")
    snapshot.write_text("{}\n", encoding="utf-8")
    return repo, coord, (log, snapshot), coord_branch


@pytest.mark.git_repo
def test_seed_style_commit_for_a_bare_slug_mission_lands_the_composed_status_files_on_the_coordination_branch(tmp_path: Path) -> None:
    """#5651 layer 1: the composed-directory status files are COORD for a bare-slug Mission.

    Same call shape as ``coord_seed._commit_seed``: the bare slug, the two composed-directory
    status files, ``kind=STATUS_STATE``, a policy that protects the primary branch.  Before the
    directory alias set the files grouped to the PRIMARY partition, the commit was refused on
    ``main`` (``no_op_wrong_surface``) and the files stayed untracked.
    """
    from specify_cli.coordination.commit_router import commit_for_mission

    repo, coord, files, coord_branch = _bare_slug_coord_mission(tmp_path)
    main_before = _git_out(repo, "rev-parse", "main")

    result = commit_for_mission(
        repo,
        _BARE_SLUG,
        files,
        f"chore({_BARE_SLUG}): seed coordination surface",
        _make_policy(protected=True),
        kind=MissionArtifactKind.STATUS_STATE,
    )

    assert result.status == "committed", result
    assert _git_out(repo, "rev-parse", "main") == main_before
    tracked = _git_out(repo, "ls-tree", "-r", "--name-only", coord_branch).splitlines()
    composed = f"kitty-specs/{_BARE_SLUG}-{_BARE_SLUG_MID8}"
    assert f"{composed}/status.events.jsonl" in tracked
    assert f"{composed}/status.json" in tracked
    assert _git_out(coord, "status", "--porcelain", "--untracked-files=all") == ""


@pytest.mark.git_repo
@pytest.mark.parametrize("mid8", ["01m5651a", "01COORD0"], ids=["lowercase", "non-crockford"])
def test_seed_style_commit_follows_a_recorded_mid8_verbatim_whatever_its_case_or_alphabet(tmp_path: Path, mid8: str) -> None:
    """The seed names the coordination directory from the recorded ``mid8`` as written (#5651).

    Nothing normalises the recorded identity before the composed directory is created, so the
    alias set must follow it byte for byte; otherwise the seed commit is misrouted again.
    """
    from specify_cli.coordination.commit_router import commit_for_mission

    repo, coord, files, coord_branch = _bare_slug_coord_mission(tmp_path, mid8)

    result = commit_for_mission(
        repo,
        _BARE_SLUG,
        files,
        f"chore({_BARE_SLUG}): seed coordination surface",
        _make_policy(protected=True),
        kind=MissionArtifactKind.STATUS_STATE,
    )

    assert result.status == "committed", result
    tracked = _git_out(repo, "ls-tree", "-r", "--name-only", coord_branch).splitlines()
    assert f"kitty-specs/{_BARE_SLUG}-{mid8}/status.events.jsonl" in tracked
    assert _git_out(coord, "status", "--porcelain", "--untracked-files=all") == ""


# ---------------------------------------------------------------------------
# Review cycle 1 N5: ``_dirty_paths_in_checkout`` must correctly match a
# porcelain entry whose path git C-quotes (a space, or a non-ASCII byte
# under the default ``core.quotePath=true``) and a rename entry (``old ->
# new``, either side independently quoted).
# ---------------------------------------------------------------------------


def test_dirty_paths_in_checkout_matches_a_quoted_path_with_a_space(tmp_path: Path) -> None:
    from specify_cli.coordination.commit_router import _dirty_paths_in_checkout

    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    quoted_file = repo_root / "kitty-specs" / "a file with space.txt"
    quoted_file.parent.mkdir(parents=True)
    quoted_file.write_text("x\n", encoding="utf-8")

    dirty = _dirty_paths_in_checkout(repo_root, (quoted_file,))

    assert dirty == (quoted_file,)


def test_dirty_paths_in_checkout_matches_a_quoted_non_ascii_path(tmp_path: Path) -> None:
    from specify_cli.coordination.commit_router import _dirty_paths_in_checkout

    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    non_ascii_file = repo_root / "kitty-specs" / "café.txt"
    non_ascii_file.parent.mkdir(parents=True)
    non_ascii_file.write_text("x\n", encoding="utf-8")

    dirty = _dirty_paths_in_checkout(repo_root, (non_ascii_file,))

    assert dirty == (non_ascii_file,)


def test_dirty_paths_in_checkout_matches_the_new_side_of_a_rename(tmp_path: Path) -> None:
    from specify_cli.coordination.commit_router import _dirty_paths_in_checkout

    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    old_file = repo_root / "kitty-specs" / "old name.txt"
    old_file.parent.mkdir(parents=True)
    old_file.write_text("identical content for a clean rename\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=repo_root, check=True)
    new_file = repo_root / "kitty-specs" / "new name.txt"
    subprocess.run(["git", "mv", str(old_file), str(new_file)], cwd=repo_root, check=True)

    dirty = _dirty_paths_in_checkout(repo_root, (new_file,))

    assert dirty == (new_file,)


# ---------------------------------------------------------------------------
# Review cycle 2 R2: a C-quoted path that ITSELF contains " (" (git quotes it
# for the space, same as any other space) was cut mid-quote by the cycle-1
# "split at the first ' ('" parsing, landing inside the quotes and leaving an
# unparseable, unclosed-quote remainder that matched nothing -- a false
# "clean" regression against base for this shape.
# ---------------------------------------------------------------------------


def test_dirty_paths_in_checkout_matches_an_untracked_path_containing_parenthesis(tmp_path: Path) -> None:
    from specify_cli.coordination.commit_router import _dirty_paths_in_checkout

    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    # Commit an unrelated sibling first so ``kitty-specs/`` is itself a
    # TRACKED directory -- otherwise the new file's own ``?? "Copy (1).md"``
    # entry collapses into a whole-directory ``?? kitty-specs/`` entry
    # instead, which matches via the directory-prefix path regardless of the
    # specific filename and would mask this regression.
    sibling = repo_root / "kitty-specs" / "sibling.txt"
    sibling.parent.mkdir(parents=True)
    sibling.write_text("sibling\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=repo_root, check=True)
    quoted_file = repo_root / "kitty-specs" / "Copy (1).md"
    quoted_file.write_text("x\n", encoding="utf-8")

    dirty = _dirty_paths_in_checkout(repo_root, (quoted_file,))

    assert dirty == (quoted_file,)


def test_dirty_paths_in_checkout_matches_a_tracked_modified_path_containing_parenthesis(tmp_path: Path) -> None:
    from specify_cli.coordination.commit_router import _dirty_paths_in_checkout

    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    quoted_file = repo_root / "kitty-specs" / "tracked (2).md"
    quoted_file.parent.mkdir(parents=True)
    quoted_file.write_text("committed content\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=repo_root, check=True)
    quoted_file.write_text("modified content\n", encoding="utf-8")

    dirty = _dirty_paths_in_checkout(repo_root, (quoted_file,))

    assert dirty == (quoted_file,)
