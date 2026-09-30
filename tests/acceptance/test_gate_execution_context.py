"""Behavioural contract for the Gate Execution Context (WP03).

Discharges ``contracts/gate-execution-context.md`` C1–C7 and data-model
``GateExecutionContext`` GEC-1..GEC-5 / ``LifecyclePhase`` PH-1. Every assertion is
behavioural on realistic fixtures (NFR-008) — there is **no** single-construction-site
source scan and **no** code-shape assertion. The integration cases drive the REAL WP02
resolver (:func:`mission_runtime.resolve_artifact_surface`) on un-patched git fixtures;
the pure cases exercise the value object's outcomes directly.

Prior art reused rather than reinvented (contract C1): the decoy-marker idiom in
``tests/integration/coord_topology_fixture.py`` (a distinct answer seeded on the primary
copy so a wrong-leg read returns a wrong *value*, not merely a wrong path), and the
cwd-independence discipline of
``test_placement_partition_golden_path.py::test_cwd_independence_resolves_identical_authority``
(run the gate from a directory sharing no ancestry with the repo).

C-006 gate-coverage registration: this new file shells out to git (the integration
cases), so it carries the ``integration`` + ``git_repo`` markers deliberately.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionArtifactKind, TopologySurface
from specify_cli.acceptance import _resolve_git_context, _status_read_feature_dir, collect_feature_summary, normalize_feature_encoding
from specify_cli import app as cli_app
from specify_cli.acceptance.execution_context import (
    _DETACHED_HEAD_SENTINEL,
    CannotEvaluate,
    CannotEvaluateReason,
    GateExecutionContext,
    GateSurfaceRefMismatch,
    LifecyclePhase,
    _git_head_of,
    build_gate_execution_context,
    declared_home_surface,
)
from specify_cli.acceptance.gates_core import (
    AcceptanceCheckDiagnostic,
    _acceptance_gate_context,
    _check_lane_gates,
    _evaluate_acceptance_matrix,
)
from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    scaffold_acceptance_matrix,
    write_acceptance_matrix,
)
from specify_cli.coordination.write_seam import WriteSeamResult
from specify_cli.core.owned_mission import resolve_owned_mission
from tests.integration import coord_topology_fixture as ctf

# The WP02 owned-checkout fixtures live in ``tests/integration/conftest.py``, which
# pytest applies only under ``tests/integration/``; import them explicitly and
# re-export for pytest discovery (same pattern as
# ``tests/specify_cli/coordination/test_owned_status_read_contract.py``).
from tests.integration.conftest import make_owned_checkouts, make_r_snapshot, owned_checkouts, r_snapshot, stale_root_copy

if TYPE_CHECKING:
    from collections.abc import Callable

    from mission_runtime import OwnedCheckout
    from tests._owned_fixtures import RSnapshotter
    from tests.integration.conftest import OwnedCheckouts

# The ``coord_topology_mission`` / ``flat_topology_mission`` fixtures are injected
# by name via ``tests/acceptance/conftest.py`` (re-exported there to avoid the
# import-shadows-parameter F811), so they are NOT imported into this module.

__all__ = ["make_owned_checkouts", "make_r_snapshot", "owned_checkouts", "r_snapshot", "stale_root_copy"]
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ===========================================================================
# Helpers — realistic acceptance matrices + the create-window fixtures
# ===========================================================================


def _seed_matrix(feature_dir: Path, *, verdict: str, marker: str) -> None:
    """Write a realistic acceptance-matrix.json whose overall_verdict is ``verdict``.

    ``marker`` becomes the single criterion's id so a wrong-leg read returns a
    distinguishable *value* (the decoy-marker idiom), not merely a wrong path.
    """
    pass_fail = "fail" if verdict == "fail" else "pass"
    matrix = AcceptanceMatrix(
        mission_slug=feature_dir.name,
        criteria=[
            AcceptanceCriterion(
                criterion_id=marker,
                description=f"seeded {verdict} criterion",
                proof_type="code_review",
                evidence="seeded",
                pass_fail=pass_fail,
                verified_by="pedro",
                verified_at="2026-07-24T00:00:00+00:00",
            )
        ],
    )
    write_acceptance_matrix(feature_dir, matrix)


def _run_public_accept_diagnosis(mission_slug: str) -> dict[str, Any]:
    """Invoke ``spec-kitty accept`` and return its read-only JSON result."""
    result = CliRunner().invoke(
        cli_app,
        ["accept", "--mission", mission_slug, "--diagnose", "--json", "--lenient"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    return cast(dict[str, Any], json.loads(result.output))


def _plain_context(
    *,
    surface: Path,
    surface_kind: TopologySurface,
    phase: LifecyclePhase = LifecyclePhase.ACCEPT,
    ref: str = "main",
) -> GateExecutionContext:
    return GateExecutionContext(
        surface=surface,
        surface_kind=surface_kind,
        ref=ref,
        phase=phase,
        mission_slug="mission-under-test",
    )


def _build_create_window_coord(tmp_path: Path, *, coord_branch_exists: bool) -> tuple[Path, str, Path]:
    """Materialise a coord-routing mission whose coord worktree is NOT created.

    ``coord_branch_exists=True`` → UNMATERIALIZED (branch present, no worktree — the
    #1718 create window). ``coord_branch_exists=False`` → DELETED (branch absent).
    No ``.worktrees/<slug>-coord`` is ever created, so ``probe_coord_state`` sees the
    coord root absent and splits the two states on the branch's git existence. No
    resolver is patched. Returns ``(repo_root, slug, primary_feature_dir)``.
    """
    subdir = "unmat" if coord_branch_exists else "deleted"
    repo = ctf._make_git_repo(tmp_path / subdir)
    mission_id = "01KY72GQ0000000000000000A1"
    mid8 = mission_id[:8]
    slug = f"create-window-{mid8}"
    coord_branch = f"kitty/mission-{slug}"
    if coord_branch_exists:
        ctf._git(repo, "branch", coord_branch)

    feature_dir = repo / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    ctf._write_meta(
        feature_dir,
        slug=slug,
        mission_id=mission_id,
        topology="coord",
        coordination_branch=coord_branch,
    )
    ctf._write_lanes_json(feature_dir, slug=slug, mission_id=mission_id)
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    ctf._write_wp_task(tasks_dir, "WP01")
    ctf._git(repo, "add", ".")
    ctf._git(repo, "commit", "-m", "feat: primary planning, coord worktree not materialised")
    return repo, slug, feature_dir


# ===========================================================================
# LifecyclePhase + PH-1 (T015)
# ===========================================================================


def test_lifecycle_phase_is_ordered() -> None:
    """PH-1 ordering: REVIEW < ACCEPT < POST_CONSOLIDATION."""
    assert LifecyclePhase.REVIEW < LifecyclePhase.ACCEPT < LifecyclePhase.POST_CONSOLIDATION


def test_implement_is_not_a_lifecycle_phase() -> None:
    """IC-01 finding: IMPLEMENT is not represented (no gate declares that floor)."""
    assert "IMPLEMENT" not in LifecyclePhase.__members__


def test_below_minimum_phase_returns_not_applicable() -> None:
    """PH-1: a gate invoked below its declared floor returns NOT_APPLICABLE_IN_PHASE.

    Not a pass and not a fail — a distinguishable cannot-evaluate naming its surface.
    """
    ctx = _plain_context(surface=Path("/x"), surface_kind=TopologySurface.PRIMARY, phase=LifecyclePhase.REVIEW)
    outcome = ctx.not_applicable_below(LifecyclePhase.ACCEPT)
    assert isinstance(outcome, CannotEvaluate)
    assert outcome.reason is CannotEvaluateReason.BELOW_MINIMUM_PHASE
    assert outcome.reason.value == "NOT_APPLICABLE_IN_PHASE"
    assert outcome.surface_kind is TopologySurface.PRIMARY and outcome.ref == "main"


@pytest.mark.parametrize("phase", [LifecyclePhase.ACCEPT, LifecyclePhase.POST_CONSOLIDATION])
def test_at_or_above_minimum_phase_is_evaluable(phase: LifecyclePhase) -> None:
    """A gate at or above its declared floor is not short-circuited (returns None)."""
    ctx = _plain_context(surface=Path("/x"), surface_kind=TopologySurface.COORD, phase=phase)
    assert ctx.not_applicable_below(LifecyclePhase.ACCEPT) is None


# ===========================================================================
# Cannot-evaluate + GEC-5 (T016) — a stamp is not permission
# ===========================================================================


def test_gec5_coord_home_on_primary_stamp_cannot_evaluate() -> None:
    """GEC-5 / C2: a COORD-homed kind judged on a PRIMARY-stamped surface refuses.

    This is the create-window substitution: the outcome is cannot-evaluate (naming
    the reason + surface + ref), NOT a verdict — the #2885 pass-by-default fix.
    """
    ctx = _plain_context(surface=Path("/primary"), surface_kind=TopologySurface.PRIMARY)
    outcome = ctx.surface_cannot_hold(TopologySurface.COORD)
    assert isinstance(outcome, CannotEvaluate)
    assert outcome.reason is CannotEvaluateReason.SURFACE_CANNOT_HOLD_FACT
    # C6: the refusal names a resolvable surface + ref.
    assert outcome.surface_kind is TopologySurface.PRIMARY and outcome.ref == "main"


def test_gec5_flat_primary_home_can_hold() -> None:
    """C7 neutrality: a PRIMARY-homed kind on a PRIMARY surface is judgeable (None).

    Flat / SINGLE_BRANCH / LANES resolve primary as their DECLARED home (AH-2) — the
    stamp is genuine, not a substitution, so the gate proceeds to a verdict.
    """
    ctx = _plain_context(surface=Path("/primary"), surface_kind=TopologySurface.PRIMARY)
    assert ctx.surface_cannot_hold(TopologySurface.PRIMARY) is None


def test_gec5_materialized_coord_home_can_hold() -> None:
    """A COORD-homed kind on a materialised COORD surface is judgeable (None)."""
    ctx = _plain_context(surface=Path("/coord"), surface_kind=TopologySurface.COORD)
    assert ctx.surface_cannot_hold(TopologySurface.COORD) is None


def test_cannot_evaluate_is_a_distinct_outcome_type() -> None:
    """C2: cannot-evaluate is a distinguishable type, not a pass/fail string."""
    outcome = _plain_context(surface=Path("/p"), surface_kind=TopologySurface.PRIMARY).surface_cannot_hold(TopologySurface.COORD)
    assert isinstance(outcome, CannotEvaluate)
    assert outcome.reason.value not in {"pass", "fail", "pending"}


def test_gate_execution_context_is_immutable() -> None:
    """GEC-1 shape: the value object a gate is handed is frozen — no in-place patch."""
    ctx = _plain_context(surface=Path("/p"), surface_kind=TopologySurface.PRIMARY)
    with pytest.raises((AttributeError, TypeError)):
        ctx.surface = Path("/elsewhere")


# ===========================================================================
# GEC-2 / C5 — ref agreement (injected head resolver, no real git needed)
# ===========================================================================


def test_assert_at_ref_raises_when_surface_drifted() -> None:
    """C5: a surface not at its ref makes the gate refuse rather than judge."""
    ctx = _plain_context(surface=Path("/p"), surface_kind=TopologySurface.COORD, ref="expected-sha")
    with pytest.raises(GateSurfaceRefMismatch) as excinfo:
        ctx.assert_at_ref(head_of=lambda _s: "different-sha")
    assert excinfo.value.error_code == "GATE_SURFACE_REF_MISMATCH"
    assert excinfo.value.expected_ref == "expected-sha"
    assert excinfo.value.actual_ref == "different-sha"


def test_assert_at_ref_passes_on_agreement() -> None:
    """C5: when the surface is at its ref, the gate proceeds (no raise)."""
    ctx = _plain_context(surface=Path("/p"), surface_kind=TopologySurface.COORD, ref="sha-abc")
    ctx.assert_at_ref(head_of=lambda _s: "sha-abc")  # must not raise


def test_git_head_of_detached_checkout_returns_sentinel(tmp_path: Path) -> None:
    """A detached checkout resolves to the ``"HEAD"`` sentinel (#2909 item 1).

    ``git symbolic-ref --short HEAD`` fails on a detached checkout; the caller's own
    no-branch fallback in ``gates_core._acceptance_gate_context`` is the same literal
    ``"HEAD"``, so this is the value that makes "no expectation" compare equal on
    both sides of :meth:`GateExecutionContext.assert_at_ref`.
    """
    repo = ctf._make_git_repo(tmp_path)
    commit_sha = ctf._git(repo, "rev-parse", "HEAD")
    ctf._git(repo, "checkout", "--detach", commit_sha)

    assert _git_head_of(repo) == _DETACHED_HEAD_SENTINEL


def test_git_head_of_attached_checkout_returns_branch_name(tmp_path: Path) -> None:
    """Companion sanity check: an attached checkout resolves the real branch, not the sentinel."""
    repo = ctf._make_git_repo(tmp_path)

    assert _git_head_of(repo) == "main"


def test_git_head_of_detached_checkout_returns_head_sentinel(
    flat_topology_mission: ctf.FlatTopologyContext,
) -> None:
    """C5: a real detached checkout resolves to the no-branch ``HEAD`` sentinel."""
    ctx = flat_topology_mission
    ctf._git(ctx.repo, "checkout", "--detach", "HEAD")
    assert ctf._git(ctx.repo, "branch", "--show-current") == ""

    assert _git_head_of(ctx.repo) == "HEAD"


def test_accept_command_normalizes_detached_head_before_matrix_gate(
    flat_topology_mission: ctf.FlatTopologyContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public command normalizes detached HEAD and refuses at its branch gate.

    On the current operator path, a detached invocation becomes ``branch=None``
    and is rejected before an acceptance-matrix ``GateExecutionContext`` can be
    built. The observable contract is therefore the JSON branch value, blocker,
    and skipped matrix checks rather than a private HEAD-resolver return value.
    """
    ctx = flat_topology_mission
    ctf._git(ctx.repo, "checkout", "--detach", "HEAD")
    _seed_matrix(
        ctx.primary_feature_dir,
        verdict="fail",
        marker="DETACHED-HEAD-MUST-NOT-REACH-MATRIX",
    )
    assert ctf._git(ctx.repo, "branch", "--show-current") == ""
    monkeypatch.chdir(ctx.repo)

    payload = _run_public_accept_diagnosis(ctx.slug)

    assert payload["branch"] is None
    assert any("detached HEAD" in issue for issue in payload["activity_issues"])
    assert any(item["check"] == "mission_branch" for item in payload["blocked_checks"])
    assert any(item["check"] == "acceptance_matrix_presence" for item in payload["skipped_checks"])
    assert not any("verdict is" in issue for issue in payload["activity_issues"])


# ===========================================================================
# Total resolution over the four CoordState answers (T017 / C3) — real resolver
# ===========================================================================


def test_build_context_materialized_coord_stamps_coord(
    coord_topology_mission: ctf.CoordTopologyContext,
) -> None:
    """C3 MATERIALIZED: a materialised coord worktree resolves + stamps COORD."""
    ctx = build_gate_execution_context(
        coord_topology_mission.repo,
        coord_topology_mission.slug,
        MissionArtifactKind.ACCEPTANCE_MATRIX,
        phase=LifecyclePhase.ACCEPT,
        ref="main",
    )
    assert ctx.surface_kind is TopologySurface.COORD
    assert ctx.surface == coord_topology_mission.coord_feature_dir


def test_build_context_flat_stamps_primary(
    flat_topology_mission: ctf.FlatTopologyContext,
) -> None:
    """C3 / AH-2: a flat mission resolves primary AFFIRMATIVELY, stamped PRIMARY."""
    ctx = build_gate_execution_context(
        flat_topology_mission.repo,
        flat_topology_mission.slug,
        MissionArtifactKind.ACCEPTANCE_MATRIX,
        phase=LifecyclePhase.ACCEPT,
        ref="main",
    )
    assert ctx.surface_kind is TopologySurface.PRIMARY
    assert ctx.surface == flat_topology_mission.primary_feature_dir


def test_build_context_unmaterialized_coord_worktree_raises(tmp_path: Path) -> None:
    """C3 UNMATERIALIZED: the create window raises, it does NOT read primary.

    #4959 (coord-read-fail-closed): a declared coord branch that exists in git but
    has no worktree yet is refused with ``CoordinationWorktreeUnmaterialized``
    rather than substituting an empty PRIMARY surface. The branch is not lost
    (unlike DELETED), so the payload names the coord candidate to materialize.
    The acceptance gate turns this raise into cannot-evaluate (#5399, see
    :func:`test_gec5_create_window_gate_refuses_instead_of_passing`).
    """
    from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized

    repo, slug, _primary = _build_create_window_coord(tmp_path, coord_branch_exists=True)
    with pytest.raises(CoordinationWorktreeUnmaterialized) as excinfo:
        build_gate_execution_context(
            repo,
            slug,
            MissionArtifactKind.ACCEPTANCE_MATRIX,
            phase=LifecyclePhase.ACCEPT,
            ref="main",
        )
    assert excinfo.value.error_code == "COORDINATION_WORKTREE_UNMATERIALIZED"


def test_build_context_deleted_coord_branch_raises(tmp_path: Path) -> None:
    """C3 DELETED: a declared coord branch absent from git raises, does NOT read primary."""
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    repo, slug, _primary = _build_create_window_coord(tmp_path, coord_branch_exists=False)
    with pytest.raises(CoordinationBranchDeleted) as excinfo:
        build_gate_execution_context(
            repo,
            slug,
            MissionArtifactKind.ACCEPTANCE_MATRIX,
            phase=LifecyclePhase.ACCEPT,
            ref="main",
        )
    assert excinfo.value.error_code == "COORDINATION_BRANCH_DELETED"


def test_declared_home_surface_coord_vs_flat(
    coord_topology_mission: ctf.CoordTopologyContext,
    flat_topology_mission: ctf.FlatTopologyContext,
) -> None:
    """The kind's declared home is COORD under coord topology, PRIMARY under flat."""
    assert (
        declared_home_surface(
            coord_topology_mission.repo,
            coord_topology_mission.slug,
            MissionArtifactKind.ACCEPTANCE_MATRIX,
        )
        is TopologySurface.COORD
    )
    assert (
        declared_home_surface(
            flat_topology_mission.repo,
            flat_topology_mission.slug,
            MissionArtifactKind.ACCEPTANCE_MATRIX,
        )
        is TopologySurface.PRIMARY
    )


# ===========================================================================
# C1 — a gate judges the surface it was handed, not an ambient one (behavioural)
# ===========================================================================


def test_c1_gate_judges_handed_surface_not_ambient(
    coord_topology_mission: ctf.CoordTopologyContext,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1: the acceptance-matrix verdict reflects the answer at ``context.surface``.

    The surface (the materialised COORD dir) is distinct from BOTH ``repo_root``
    (the primary checkout) and the process cwd (an unrelated dir sharing no
    ancestry). All three hold DIFFERENT seeded answers: COORD carries a FAIL
    matrix, the primary decoy carries a PASS matrix (silent if read), the cwd carries
    a third decoy. The gate reads coord → the verdict is FAIL. Reverting the read to
    the ambient primary/cwd surface would flip it to a silent pass — the mutant dies
    on a wrong *value*, not merely a wrong path.
    """
    ctx = coord_topology_mission
    # Seed three DIFFERENT answers at the three locations.
    _seed_matrix(ctx.coord_feature_dir, verdict="fail", marker="COORD-AUTHORITY")
    _seed_matrix(ctx.primary_feature_dir, verdict="pass", marker="PRIMARY-DECOY")
    unrelated_cwd = tmp_path_factory.mktemp("unrelated-cwd")
    assert not str(unrelated_cwd).startswith(str(ctx.repo))
    _seed_matrix(unrelated_cwd, verdict="pass", marker="CWD-DECOY")

    # Pre-flight: the gate is genuinely handed the COORD surface (non-vacuity).
    handed = _acceptance_gate_context(ctx.repo, ctx.primary_feature_dir)
    assert handed.surface_kind is TopologySurface.COORD
    assert handed.surface == ctx.coord_feature_dir

    monkeypatch.chdir(unrelated_cwd)
    activity_issues: list[str] = []
    skipped: list[AcceptanceCheckDiagnostic] = []
    blocked: list[AcceptanceCheckDiagnostic] = []
    _evaluate_acceptance_matrix(
        ctx.repo,
        ctx.primary_feature_dir,
        activity_issues,
        skipped,
        blocked,
        mutate_matrix=False,
    )

    # The verdict follows context.surface (COORD → fail), not the ambient decoys.
    assert any("verdict is 'fail'" in issue for issue in activity_issues), activity_issues
    assert not any(c.check == "acceptance_matrix_cannot_evaluate" for c in blocked)


# ===========================================================================
# GEC-5 through the real gate — create-window refuses instead of passing (#2885)
# ===========================================================================


def test_gec5_create_window_gate_refuses_instead_of_passing(tmp_path: Path) -> None:
    """GEC-5 end to end: the create window records cannot-evaluate, not a pass.

    On the UNMATERIALIZED coord create window the context build raises
    ``CoordinationWorktreeUnmaterialized`` (#4959). A PASS matrix is seeded on the
    primary surface — a gate that fell back to it would pass by default (#2885),
    and a gate that let the raise escape would crash instead of refusing (#5399).
    The gate refuses: a distinguishable cannot-evaluate naming its reason, the
    unmaterialized COORD surface and the error code, and NO silent pass.
    """
    repo, slug, primary_feature_dir = _build_create_window_coord(tmp_path, coord_branch_exists=True)
    _seed_matrix(primary_feature_dir, verdict="pass", marker="PRIMARY-EMPTY-STAND-IN")

    activity_issues: list[str] = []
    skipped: list[AcceptanceCheckDiagnostic] = []
    blocked: list[AcceptanceCheckDiagnostic] = []
    _evaluate_acceptance_matrix(
        repo,
        primary_feature_dir,
        activity_issues,
        skipped,
        blocked,
        mutate_matrix=False,
    )

    assert any(c.check == "acceptance_matrix_cannot_evaluate" for c in blocked), blocked
    assert any(CannotEvaluateReason.SURFACE_CANNOT_HOLD_FACT.value in issue for issue in activity_issues), activity_issues
    assert any("COORDINATION_WORKTREE_UNMATERIALIZED" in issue and "surface=coord" in issue for issue in activity_issues), activity_issues
    # It is NOT a verdict — no pass/fail verdict issue was recorded.
    assert not any("verdict is" in issue for issue in activity_issues)


def test_gec2_primary_ref_drift_gate_refuses_instead_of_passing(
    flat_topology_mission: ctf.FlatTopologyContext,
) -> None:
    """GEC-2 / C5 end to end: a drifted PRIMARY surface refuses, not judges.

    The real gate resolves ``ref`` from the caller-observed currently-checked-out
    ``branch`` (:func:`_acceptance_gate_context`). A PASS matrix is seeded on the
    genuine primary surface, but the caller asserts a ``branch`` that does NOT match
    what is actually checked out (simulating drift between when ``branch`` was
    captured and when this gate runs — WITHOUT GEC-2 the gate would read the seeded
    PASS matrix and judge it, silently ignoring the drift). GEC-2 refuses: a
    ``GATE_SURFACE_REF_MISMATCH`` cannot-evaluate naming the surface + expected/actual
    ref, and NO pass/fail verdict.
    """
    ctx = flat_topology_mission
    _seed_matrix(ctx.primary_feature_dir, verdict="pass", marker="DRIFTED-REF-PASS")

    activity_issues: list[str] = []
    skipped: list[AcceptanceCheckDiagnostic] = []
    blocked: list[AcceptanceCheckDiagnostic] = []
    _evaluate_acceptance_matrix(
        ctx.repo,
        ctx.primary_feature_dir,
        activity_issues,
        skipped,
        blocked,
        mutate_matrix=False,
        branch="stale-observed-branch",
    )

    assert any(c.check == "acceptance_matrix_cannot_evaluate" for c in blocked), blocked
    assert any("GATE_SURFACE_REF_MISMATCH" in issue for issue in activity_issues), activity_issues
    # It is NOT a verdict — no pass/fail verdict issue was recorded.
    assert not any("verdict is" in issue for issue in activity_issues)


def test_gec2_real_cross_checkout_branch_drift_gate_refuses(flat_topology_mission: ctf.FlatTopologyContext, tmp_path: Path) -> None:
    """GEC-2 / C5, the REAL production trigger: two genuinely divergent checkouts.

    ``test_gec2_primary_ref_drift_gate_refuses_instead_of_passing`` proves the
    wiring with a *synthetic* ``branch="stale-observed-branch"`` — a value
    ``_evaluate_branch_gate`` would itself reject before the matrix is ever
    reached, the inverse of the real production drift. This test drives the
    trigger production actually reaches: ``branch`` is resolved by the caller
    (``_resolve_git_context`` in ``specify_cli.acceptance``) as the HEAD checked
    out at the *invocation* ``repo_root`` — but ``resolve_artifact_surface``
    finds the PRIMARY surface via ``get_main_repo_root``, which is
    CWD-invariant and does NOT depend on which checkout invoked it (C-CTX-2). So
    an accept run invoked from a linked git *worktree* genuinely checked out on
    the mission branch, while the canonical main checkout sits on a different
    branch, makes ``context.ref`` (the mission branch) and the surface's real
    HEAD (the main checkout's actual branch, ``main``) disagree for real — no
    synthetic string, no monkeypatch, no direct construction of the mismatch.

    ``branch`` here is the mission branch, a genuine member of
    ``{target_branch, mission_branch}`` — exactly the set
    ``_evaluate_branch_gate`` allows — so this path does NOT bypass that gate
    with an invalid value; the branch gate would legitimately let it through.
    """
    ctx = flat_topology_mission
    mission_branch = f"kitty/mission-{ctx.slug}"
    # A real branch, not yet checked out anywhere, cut from the SAME commit the
    # main checkout (still on "main") sits at.
    ctf._git(ctx.repo, "branch", mission_branch)
    # A genuine linked worktree — a second, real checkout of the SAME repo,
    # actually checked out on the mission branch. The main checkout is
    # untouched: still on "main".
    linked_worktree = tmp_path / "linked-worktree"
    ctf._git(ctx.repo, "worktree", "add", str(linked_worktree), mission_branch)

    # A PASS matrix on the genuine primary surface: WITHOUT GEC-2 this is read
    # and judged, silently ignoring the real cross-checkout drift.
    _seed_matrix(ctx.primary_feature_dir, verdict="pass", marker="CROSS-CHECKOUT-DRIFT-PASS")

    activity_issues: list[str] = []
    skipped: list[AcceptanceCheckDiagnostic] = []
    blocked: list[AcceptanceCheckDiagnostic] = []
    _evaluate_acceptance_matrix(
        linked_worktree,
        ctx.primary_feature_dir,
        activity_issues,
        skipped,
        blocked,
        mutate_matrix=False,
        branch=mission_branch,
    )

    assert any(c.check == "acceptance_matrix_cannot_evaluate" for c in blocked), blocked
    assert any("GATE_SURFACE_REF_MISMATCH" in issue for issue in activity_issues), activity_issues
    # Names both real sides of the drift: expected the mission branch, found "main".
    assert any(mission_branch in issue for issue in activity_issues), activity_issues
    assert any("'main'" in issue for issue in activity_issues), activity_issues
    # It is NOT a verdict — no pass/fail verdict issue was recorded.
    assert not any("verdict is" in issue for issue in activity_issues)


def test_resolve_git_context_branch_forwards_through_check_lane_gates(flat_topology_mission: ctf.FlatTopologyContext, tmp_path: Path) -> None:
    """#2909 item 2: the invocation-checkout ``branch`` is not dropped mid-chain.

    ``test_gec2_real_cross_checkout_branch_drift_gate_refuses`` proves GEC-2/C5 at
    the ``_evaluate_acceptance_matrix(branch=...)`` entry point directly, while
    ``test_trio_pure_cores.py`` stubs ``_check_lane_gates`` entirely and does not
    assert which ``branch`` reaches it. Neither proves, with REAL git, that a
    ``branch`` genuinely resolved off a real invocation checkout's HEAD
    (``_resolve_git_context``) survives the ``_check_lane_gates(branch=branch)``
    hop on its way to the acceptance-matrix gate. This test covers that hop: if
    ``_check_lane_gates`` (or ``_evaluate_branch_gate`` inside it) dropped the
    ``branch`` kwarg mid-chain, this gate would silently judge the drifted
    surface instead of refusing — the exact regression #2909 asks to be closed
    against.

    (``collect_feature_summary`` itself is not used as the entry point here: it
    also drives WP-metadata collection, which — separately from anything #2909
    asks for — does not support being invoked from a linked worktree
    (``summary_core.py`` ``wp.path.relative_to(repo_root)`` raises ``ValueError``).
    So the top-level ``collect_feature_summary -> _check_lane_gates(branch)`` hop
    remains uncovered pending that defect; #2909 item 2 is therefore only
    partially covered by this test.)
    """
    ctx = flat_topology_mission
    mission_branch = f"kitty/mission-{ctx.slug}"
    # A real branch, not yet checked out anywhere, cut from the SAME commit the
    # main checkout (still on "main") sits at — a genuine member of
    # {target_branch, mission_branch}, so `_evaluate_branch_gate` legitimately
    # lets this invocation through to the acceptance-matrix gate.
    ctf._git(ctx.repo, "branch", mission_branch)
    # A genuine linked worktree, actually checked out on the mission branch —
    # this is the invocation checkout `_resolve_git_context` reads HEAD from.
    # The main checkout is untouched: still on "main".
    linked_worktree = tmp_path / "linked-worktree"
    ctf._git(ctx.repo, "worktree", "add", str(linked_worktree), mission_branch)

    # A PASS matrix on the genuine primary surface: if `branch` were dropped
    # anywhere in the chain, this would be read and judged, silently ignoring
    # the real cross-checkout drift.
    _seed_matrix(ctx.primary_feature_dir, verdict="pass", marker="E2E-CROSS-CHECKOUT-PASS")

    branch, _worktree_root, _primary_repo_root, _git_dirty = _resolve_git_context(linked_worktree)
    # `_resolve_git_context` read the invocation checkout's real HEAD.
    assert branch == mission_branch

    activity_issues: list[str] = []
    skipped: list[AcceptanceCheckDiagnostic] = []
    blocked: list[AcceptanceCheckDiagnostic] = []
    _check_lane_gates(
        linked_worktree,
        ctx.primary_feature_dir,
        branch,
        activity_issues,
        skipped,
        blocked,
        mutate_matrix=False,
    )

    # The branch reached the acceptance-matrix gate: it refused the drift
    # instead of judging the seeded PASS matrix.
    assert any(c.check == "acceptance_matrix_cannot_evaluate" for c in blocked), blocked
    assert any("GATE_SURFACE_REF_MISMATCH" in issue for issue in activity_issues), activity_issues
    assert any(mission_branch in issue for issue in activity_issues), activity_issues
    assert any("'main'" in issue for issue in activity_issues), activity_issues
    # It is NOT a verdict — no pass/fail verdict issue was recorded.
    assert not any("verdict is" in issue for issue in activity_issues)


def test_gec2_primary_ref_agreement_still_judges(
    flat_topology_mission: ctf.FlatTopologyContext,
) -> None:
    """GEC-2 happy path: a PRIMARY surface genuinely at its ref still judges (C5).

    The caller-observed ``branch`` matches what is actually checked out (the
    ordinary, undrifted case) — ref-agreement holds, so the gate proceeds to a real
    verdict instead of refusing.
    """
    ctx = flat_topology_mission
    _seed_matrix(ctx.primary_feature_dir, verdict="fail", marker="AT-REF-FAIL")

    activity_issues: list[str] = []
    skipped: list[AcceptanceCheckDiagnostic] = []
    blocked: list[AcceptanceCheckDiagnostic] = []
    _evaluate_acceptance_matrix(
        ctx.repo,
        ctx.primary_feature_dir,
        activity_issues,
        skipped,
        blocked,
        mutate_matrix=False,
        branch="main",
    )

    assert not any(c.check == "acceptance_matrix_cannot_evaluate" for c in blocked), blocked
    assert any("verdict is 'fail'" in issue for issue in activity_issues), activity_issues


def test_accept_command_forwards_normal_branch_to_matrix_gate(
    flat_topology_mission: ctf.FlatTopologyContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public accept path preserves the invocation branch through matrix judgement.

    The mission branch deliberately differs from target ``main``. The seeded FAIL
    verdict remains observable only when every production forwarding hop preserves
    that branch: dropping it either trips the branch gate or yields a surface-ref
    mismatch before the matrix can be judged.
    """
    ctx = flat_topology_mission
    mission_branch = f"kitty/mission-{ctx.slug}"
    ctf._git(ctx.repo, "switch", "-c", mission_branch)
    _seed_matrix(
        ctx.primary_feature_dir,
        verdict="fail",
        marker="INVOCATION-BRANCH-FLOW-THROUGH",
    )
    monkeypatch.chdir(ctx.repo)

    payload = _run_public_accept_diagnosis(ctx.slug)

    assert payload["branch"] == mission_branch
    assert any("verdict is 'fail'" in issue for issue in payload["activity_issues"])
    assert not any(item["check"] in {"mission_branch", "acceptance_matrix_cannot_evaluate"} for item in payload["blocked_checks"])
    assert not any("GATE_SURFACE_REF_MISMATCH" in issue for issue in payload["activity_issues"])


# ===========================================================================
# C7 — topology neutrality: identical defect → identical outcome (coord and flat)
# ===========================================================================


def test_c7_identical_defect_identical_outcome_coord_and_flat(
    coord_topology_mission: ctf.CoordTopologyContext,
    flat_topology_mission: ctf.FlatTopologyContext,
) -> None:
    """C7 / C-004: the same FAIL defect on coord and flat yields the same outcome.

    The gate is neither named nor shaped around coordination topology and reads no
    ``flattened`` flag: a FAIL matrix seeded at each mission's GENUINE home (coord's
    materialised worktree, flat's primary dir) produces the identical
    ``verdict is 'fail'`` outcome. A decoy PASS matrix on the coord mission's primary
    leg proves the coord case really read coord, not its own primary.
    """
    # Coord: defect at the materialised coord home; decoy pass on the primary leg.
    _seed_matrix(coord_topology_mission.coord_feature_dir, verdict="fail", marker="COORD-DEFECT")
    _seed_matrix(coord_topology_mission.primary_feature_dir, verdict="pass", marker="COORD-PRIMARY-DECOY")
    # Flat: defect at its declared (primary) home.
    _seed_matrix(flat_topology_mission.primary_feature_dir, verdict="fail", marker="FLAT-DEFECT")

    coord_issues: list[str] = []
    flat_issues: list[str] = []
    _evaluate_acceptance_matrix(
        coord_topology_mission.repo,
        coord_topology_mission.primary_feature_dir,
        coord_issues,
        [],
        [],
        mutate_matrix=False,
    )
    _evaluate_acceptance_matrix(
        flat_topology_mission.repo,
        flat_topology_mission.primary_feature_dir,
        flat_issues,
        [],
        [],
        mutate_matrix=False,
    )

    coord_fail = any("verdict is 'fail'" in i for i in coord_issues)
    flat_fail = any("verdict is 'fail'" in i for i in flat_issues)
    assert coord_fail and flat_fail, (coord_issues, flat_issues)
    assert coord_fail == flat_fail  # identical outcome, identical defect


# ===========================================================================
# C6 — every recorded judgement names its surface + ref
# ===========================================================================


def test_c6_recorded_judgement_names_surface_and_ref(
    coord_topology_mission: ctf.CoordTopologyContext,
) -> None:
    """C6 / NFR-003: the cannot-evaluate outcome carries a resolvable surface + ref.

    Built through the real gate-context door so the ``ref`` is the mission's own
    target branch (a resolvable identifier), not a synthetic literal.
    """
    ctx = _acceptance_gate_context(coord_topology_mission.repo, coord_topology_mission.primary_feature_dir)
    # The context (and thus any verdict/refusal derived from it) names its surface+ref.
    assert ctx.surface_kind is TopologySurface.COORD
    assert ctx.ref == "main"  # the mission's recorded target_branch
    outcome = ctx.not_applicable_below(LifecyclePhase.POST_CONSOLIDATION)
    assert isinstance(outcome, CannotEvaluate)
    assert outcome.surface_kind is TopologySurface.COORD and outcome.ref == "main"


def test_fixture_smoke_no_resolver_patched(
    coord_topology_mission: ctf.CoordTopologyContext,
) -> None:
    """Non-vacuity: the coord fixture is real git state (a coord worktree exists)."""
    assert coord_topology_mission.coord_feature_dir.exists()
    assert (coord_topology_mission.repo / ".worktrees").exists()
    # meta.json on primary declares coord topology (drives the real resolver).
    meta = json.loads((coord_topology_mission.primary_feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["topology"] == "coord"


# --- owned checkout (WP15) ---------------------------------------------------
#
# The acceptance package takes the validated ``OwnedCheckout`` fact directly. Each
# case mints a REAL fact through the sanctioned minter (``resolve_owned_mission``,
# never ``OwnedCheckout._mint``), seeds a decoy copy in the repository root checkout
# where it matters, and asserts the repository root checkout is untouched (NFR-001).


@pytest.fixture
def owned_fact(owned_checkouts: OwnedCheckouts) -> OwnedCheckout:
    return resolve_owned_mission(owned_checkouts.repository_root, owned_checkouts.owned_root, owned_checkouts.mission_slug)


@pytest.fixture
def no_root_or_handle_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    """The owned arm makes no ``get_main_repo_root`` call and no handle walk."""

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("owned arm must not consult get_main_repo_root / the handle walk")

    monkeypatch.setattr("specify_cli.core.paths.get_main_repo_root", _boom)
    monkeypatch.setattr("specify_cli.missions._read_path_resolver.resolve_handle_to_read_path", _boom)


def test_owned_build_context_stamps_owned_checkout_not_repository_root(
    owned_checkouts: OwnedCheckouts,
    owned_fact: OwnedCheckout,
    stale_root_copy: Callable[..., Path],
    r_snapshot: RSnapshotter,
    no_root_or_handle_walk: None,
) -> None:
    """GEC-1: the gate judges the owned checkout it was handed, never a stale R copy."""
    stale_root_copy()
    before = r_snapshot.take()
    ctx = build_gate_execution_context(
        owned_checkouts.repository_root,
        owned_checkouts.mission_slug,
        MissionArtifactKind.ACCEPTANCE_MATRIX,
        phase=LifecyclePhase.ACCEPT,
        ref="main",
        owned=owned_fact,
    )
    assert ctx.surface_kind is TopologySurface.PRIMARY
    assert ctx.surface == owned_fact.mission_dir
    assert owned_checkouts.repository_root not in ctx.surface.parents
    r_snapshot.assert_unchanged(before, r_snapshot.take())


def test_owned_declared_home_surface_single_branch_is_primary(
    owned_checkouts: OwnedCheckouts,
    owned_fact: OwnedCheckout,
    no_root_or_handle_walk: None,
) -> None:
    surface = declared_home_surface(
        owned_checkouts.repository_root,
        owned_checkouts.mission_slug,
        MissionArtifactKind.ACCEPTANCE_MATRIX,
        owned=owned_fact,
    )
    assert surface is TopologySurface.PRIMARY


def test_owned_status_read_feature_dir_returns_owned_status_dir_without_fallback(
    owned_checkouts: OwnedCheckouts,
    owned_fact: OwnedCheckout,
    no_root_or_handle_walk: None,
) -> None:
    """The owned arm returns the seam dir unconditionally, even when it does not exist yet."""
    fallback = owned_checkouts.mission_dir / "fallback-feature-dir"
    result = _status_read_feature_dir(
        owned_checkouts.repository_root,
        owned_checkouts.mission_slug,
        fallback,
        owned=owned_fact,
    )
    assert result != fallback
    assert owned_fact.mission_dir in (result, *result.parents)


def test_owned_collect_feature_summary_reads_work_packages_from_owned_mission_dir(
    owned_checkouts: OwnedCheckouts,
    owned_fact: OwnedCheckout,
    stale_root_copy: Callable[..., Path],
    r_snapshot: RSnapshotter,
) -> None:
    """The owned accept read sees P's two WPs, not R's stale five-WP copy."""
    stale_root_copy()
    before = r_snapshot.take()
    # The accept CLI hands the owned checkout root as ``repo_root`` alongside the fact.
    summary = collect_feature_summary(
        owned_fact.owned_root,
        owned_checkouts.mission_slug,
        strict_metadata=False,
        mutate_matrix=False,
        owned=owned_fact,
    )
    assert summary.feature_dir == owned_fact.mission_dir
    assert sorted(wp.work_package_id for wp in summary.work_packages) == ["WP01", "WP02"]
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=owned_checkouts.mission_slug)


def test_owned_scaffold_acceptance_matrix_raises_when_write_seam_refuses(
    owned_checkouts: OwnedCheckouts,
    owned_fact: OwnedCheckout,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owned writes are fatal on failure: no silent fallback to a bare write."""
    import specify_cli.acceptance.matrix as matrix_module

    seen: dict[str, object] = {}

    def _refuse(*_args: object, **kwargs: object) -> WriteSeamResult:
        seen.update(kwargs)
        return WriteSeamResult(status="refused", entry_id="finalize-scaffold", destination_surface=None, diagnostic=None)

    monkeypatch.setattr(matrix_module, "write_and_commit_acceptance_matrix", _refuse)
    with pytest.raises(RuntimeError, match="Owned acceptance matrix write failed."):
        scaffold_acceptance_matrix(
            owned_fact.mission_dir,
            owned_checkouts.mission_slug,
            repo_root=owned_checkouts.repository_root,
            owned=owned_fact,
        )
    assert seen["owned"] is owned_fact


def test_owned_scaffold_acceptance_matrix_committed_returns_matrix_path(
    owned_checkouts: OwnedCheckouts,
    owned_fact: OwnedCheckout,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import specify_cli.acceptance.matrix as matrix_module

    def _committed(*_args: object, **_kwargs: object) -> WriteSeamResult:
        return WriteSeamResult(status="unchanged", entry_id="finalize-scaffold", destination_surface="primary")

    monkeypatch.setattr(matrix_module, "write_and_commit_acceptance_matrix", _committed)
    path = scaffold_acceptance_matrix(
        owned_fact.mission_dir,
        owned_checkouts.mission_slug,
        repo_root=owned_checkouts.repository_root,
        owned=owned_fact,
    )
    assert path == owned_fact.mission_dir / "acceptance-matrix.json"


def test_owned_normalize_feature_encoding_touches_only_owned_mission_dir(
    owned_checkouts: OwnedCheckouts,
    owned_fact: OwnedCheckout,
    stale_root_copy: Callable[..., Path],
    r_snapshot: RSnapshotter,
    no_root_or_handle_walk: None,
) -> None:
    legacy = "Caf\u00e9 \u201cquoted\u201d na\u00efve r\u00e9sum\u00e9 \u2014 owned checkout notes.\n".encode("cp1252")
    stale_copy = stale_root_copy()
    (stale_copy / "plan.md").write_bytes(legacy)
    owned_plan = owned_fact.mission_dir / "plan.md"
    owned_plan.write_bytes(legacy)
    before = r_snapshot.take()
    rewritten = normalize_feature_encoding(owned_checkouts.repository_root, owned_checkouts.mission_slug, owned=owned_fact)
    assert owned_plan in rewritten
    assert all(owned_fact.mission_dir in path.parents for path in rewritten)
    assert (stale_copy / "plan.md").read_bytes() == legacy
    r_snapshot.assert_unchanged(before, r_snapshot.take())


def test_owned_check_lane_gates_forwards_the_fact_to_every_gate_seam(
    owned_checkouts: OwnedCheckouts,
    owned_fact: OwnedCheckout,
    stale_root_copy: Callable[..., Path],
    r_snapshot: RSnapshotter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1 / GEC-1: the fact reaches every gates_core seam, so the matrix is judged on P.

    R holds a stale copy of the mission with a DIFFERENT (failing) matrix; P holds the
    passing one. Dropping ``owned=owned`` at any of the four forwards
    (``_check_lane_gates`` -> ``_evaluate_acceptance_matrix``, ``_evaluate_acceptance_matrix``
    -> ``_acceptance_gate_context`` / ``_matrix_surface_cannot_hold``,
    ``_matrix_surface_cannot_hold`` -> ``declared_home_surface``) either hands a spy
    ``owned=None`` or judges the stale R matrix, and this test goes red.
    """
    import specify_cli.acceptance.execution_context as ec

    stale_dir = stale_root_copy()
    _seed_matrix(stale_dir, verdict="fail", marker="STALE-ROOT-MATRIX")
    _seed_matrix(owned_fact.mission_dir, verdict="pass", marker="OWNED-MATRIX")
    before = r_snapshot.take()

    seen_build: list[object] = []
    seen_home: list[object] = []
    real_build = ec.build_gate_execution_context
    real_home = ec.declared_home_surface

    def _spy_build(*args: Any, **kwargs: Any) -> Any:
        seen_build.append(kwargs.get("owned"))
        return real_build(*args, **kwargs)

    def _spy_home(*args: Any, **kwargs: Any) -> Any:
        seen_home.append(kwargs.get("owned"))
        return real_home(*args, **kwargs)

    monkeypatch.setattr(ec, "build_gate_execution_context", _spy_build)
    monkeypatch.setattr(ec, "declared_home_surface", _spy_home)

    activity_issues: list[str] = []
    skipped: list[AcceptanceCheckDiagnostic] = []
    blocked: list[AcceptanceCheckDiagnostic] = []
    outcome = _check_lane_gates(
        owned_checkouts.repository_root,
        owned_fact.mission_dir,
        owned_checkouts.target_branch,
        activity_issues,
        skipped,
        blocked,
        mutate_matrix=False,
        owned=owned_fact,
    )

    assert seen_build == [owned_fact]
    assert seen_home == [owned_fact]
    assert outcome.matrix_dir == owned_fact.mission_dir
    assert not any("STALE-ROOT-MATRIX" in issue for issue in activity_issues), activity_issues
    assert not any("verdict is 'fail'" in issue for issue in activity_issues), activity_issues
    r_snapshot.assert_unchanged(before, r_snapshot.take())
