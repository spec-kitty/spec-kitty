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

import pytest

from mission_runtime import MissionArtifactKind
from specify_cli.git.protection_policy import ProtectionPolicy

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


def test_protected_primary_refusal_names_mission_create_for_pre_tasks_kind(tmp_path: Path) -> None:
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
            kind=MissionArtifactKind.SPEC,
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
