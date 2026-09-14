"""Behavioral two-ref write-surface placement guard (write-surface-coherence WP07 / T027).

The mission's headline invariant, asserted BEHAVIORALLY (not structurally) against a
REAL coordination-topology fixture, across EVERY converged write path. The bifurcation:

* PRIMARY-partition kinds (``SPEC`` / ``DATA_MODEL`` / ``RESEARCH`` / ``CHECKLIST`` /
  ``FINALIZED_EXECUTION_PLAN`` / ``TASKS_INDEX`` / ``WORK_PACKAGE_TASK`` /
  ``LANE_STATE`` / ``PRIMARY_METADATA`` / ``RETROSPECTIVE`` / ``ANALYSIS_REPORT``)
  resolve to the primary ``target_branch`` for EVERY topology and NEVER transit
  coordination. (``ANALYSIS_REPORT`` was re-homed COORD→PRIMARY by FR-003 /
  coord-commit-integrity.)
* COORD-partition kinds (``STATUS_STATE`` / ``ISSUE_MATRIX`` / ``ACCEPTANCE_MATRIX``)
  keep the topology-routed coordination ref under coord topology.

Non-vacuity (research D-7 / NFR-002):

* The guard drives the **REAL resolver** (``resolve_placement_only`` /
  ``resolve_topology``) against the real coord-topology fixture — it does NOT stub
  either, unlike ``tests/coordination/test_commit_router.py`` (which stubs both and
  proves nothing about the partition). It exercises the assertion across THREE
  converged write paths: ``commit_for_mission``, the ``safe-commit`` bypass writer
  (``_resolve_commit_target``), and ``_planning_commit_worktree``.
* A MANDATORY anti-mutant negative test forces the PRE-fix partition (puts ``SPEC``
  back into ``_PLACEMENT_ARTIFACT_KINDS``) and asserts the planning-ref assertion
  goes RED — killing the "always-coord-for-coord-topology" mutant. Without it the
  two-ref guard could pass vacuously.

Fixture realism (mandatory): a real 26-char ULID ``mission_id``, real 8-char
``mid8``, a real ``<slug>-<mid8>`` mission dir, a real ``coordination_branch``, and
a NON-protected feature ``target_branch``.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
import pytest
from ulid import ULID

import mission_runtime.artifacts as artifacts_mod
import mission_runtime.resolution as resolution_mod
from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    kind_for_mission_file,
    resolve_placement_only,
    resolve_topology,
    routes_through_coordination,
)

pytestmark = [pytest.mark.architectural, pytest.mark.git_repo]

# Production-shaped identity: a real 26-char ULID + its derived 8-char mid8. The
# on-disk slug carries the mid8 tail (post-WP03 grammar), and ``target_branch`` is
# a NON-protected feature branch so a PRIMARY-kind commit lands cleanly there.
_TARGET_BRANCH = "feat/write-surface-coherence"


@dataclass(frozen=True)
class _CoordMission:
    """A real on-disk coordination-topology mission fixture."""

    repo_root: Path
    mission_slug: str
    feature_dir: Path
    coordination_branch: str
    target_branch: str


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _build_coord_mission(tmp_path: Path) -> _CoordMission:
    """Build a real coord-topology mission whose ``target_branch`` is non-protected.

    The mission stores ``coordination_branch`` + ``topology: coord`` so the REAL
    resolver classifies it COORD (``routes_through_coordination`` is True), and a
    non-protected ``target_branch`` that is HEAD so PRIMARY-kind commits land there.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET_BRANCH)
    _git(repo, "config", "user.email", "guard@example.com")
    _git(repo, "config", "user.name", "Guard Suite")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("project: guard-suite\n", encoding="utf-8")

    mission_id = str(ULID())
    # NOT lowercased: mission_runtime.identity.resolve_mid8 returns
    # ``mission_id[:8]`` VERBATIM (uppercase Crockford, matching
    # ``mid8_from_slug``'s ``[0-9A-HJKMNP-TV-Z]{8}`` regex) -- a lowercased
    # embedded tail here would make ``_resolve_mid8`` (used by
    # ``commit_router.py``'s coord-worktree materialisation) derive an
    # UPPERCASE mid8 that disagrees with this fixture's own LOWERCASE
    # branch/worktree naming, so a genuine coord commit (T015's
    # ``result.status == "committed"`` checks, not merely a resolved-ref
    # check) fails with a worktree/branch HEAD mismatch.
    mid8 = mission_id[:8]
    slug = f"write-surface-guard-{mid8}"
    coordination_branch = f"kitty/mission-{slug}"

    feature_dir = repo / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mid8": mid8,
                "mission_slug": slug,
                "target_branch": _TARGET_BRANCH,
                "coordination_branch": coordination_branch,
                "topology": "coord",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    # A PRIMARY-kind artifact (spec.md) and a COORD-kind artifact (status log).
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (feature_dir / "status.events.jsonl").write_text("{}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed coord mission")
    _git(repo, "branch", coordination_branch)

    return _CoordMission(
        repo_root=repo.resolve(),
        mission_slug=slug,
        feature_dir=feature_dir,
        coordination_branch=coordination_branch,
        target_branch=_TARGET_BRANCH,
    )


@pytest.fixture
def coord_mission(tmp_path: Path) -> _CoordMission:
    mission = _build_coord_mission(tmp_path)
    # Precondition: the REAL resolver classifies this fixture as coord-routing.
    # Without this the two-ref guard is exercising the wrong topology cell.
    assert routes_through_coordination(
        resolve_topology(mission.repo_root, mission.mission_slug)
    ), "fixture precondition violated: mission must route through coordination"
    return mission


# ---------------------------------------------------------------------------
# The two-ref behavioral assertion, parametrized across three write paths.
# ---------------------------------------------------------------------------

# A representative PRIMARY-partition kind and COORD-partition kind. The full
# partition is asserted in ``test_full_partition_resolves_per_membership`` below.
_PRIMARY_KIND = MissionArtifactKind.SPEC
_COORD_KIND = MissionArtifactKind.STATUS_STATE


def _path_commit_for_mission(mission: _CoordMission) -> tuple[str, str]:
    """Write path 1: ``commit_for_mission`` — drives the real resolver internally.

    Returns the (primary_ref, coord_ref) the router lands/resolves each kind on.
    The PRIMARY-kind commit is exercised end-to-end (it must really land on the
    target branch); the COORD-kind commit's resolved placement ref is the
    discriminating signal that it routes to coordination, not the primary.
    """
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy

    policy = ProtectionPolicy(
        protected_branches=frozenset({"main", "master"}), operator_hatch_active=False
    )

    # PRIMARY kind: actually mutate + commit; assert it lands on the target branch.
    spec_path = mission.feature_dir / "spec.md"
    spec_path.write_text("# Spec edited by guard\n", encoding="utf-8")
    primary_result = commit_for_mission(
        mission.repo_root,
        mission.mission_slug,
        (spec_path,),
        "guard: primary kind",
        policy,
        kind=_PRIMARY_KIND,
    )
    assert primary_result.status == "committed", primary_result.diagnostic

    # COORD kind: the resolved placement ref is the routing signal (coord worktree
    # materialisation plumbing is covered by tests/coordination/test_commit_router).
    status_path = mission.feature_dir / "status.events.jsonl"
    status_path.write_text('{"edited": true}\n', encoding="utf-8")
    coord_result = commit_for_mission(
        mission.repo_root,
        mission.mission_slug,
        (status_path,),
        "guard: coord kind",
        policy,
        kind=_COORD_KIND,
    )
    return primary_result.placement_ref, coord_result.placement_ref


def _path_safe_commit_bypass(mission: _CoordMission) -> tuple[str, str]:
    """Write path 2: the ``safe-commit`` bypass writer (``_resolve_commit_target``).

    A planning artifact path (``spec.md``) resolves to the primary target branch;
    a status file path (``status.events.jsonl``) resolves to the coordination ref.
    Drives the real ``resolve_placement_only`` through the CLI's single destination
    resolver — no stub.
    """
    from specify_cli.cli.commands.safe_commit_cmd import _resolve_commit_target

    primary = _resolve_commit_target(
        explicit_to_branch=None,
        repo_root=mission.repo_root,
        files=[mission.feature_dir / "spec.md"],
    )
    coord = _resolve_commit_target(
        explicit_to_branch=None,
        repo_root=mission.repo_root,
        files=[mission.feature_dir / "status.events.jsonl"],
    )
    return primary.ref, coord.ref


def _path_planning_commit_worktree(mission: _CoordMission) -> tuple[str, str]:
    """Write path 3: ``_planning_commit_worktree`` — drives the real resolver.

    A PRIMARY kind returns ``(repo_root, paths)`` (no coord transit). A COORD kind
    routes through coordination — its resolved placement ref (read from the same
    real resolver) is the discriminating signal. We report each path's resolved
    ref by composing the worktree behaviour with the real resolver.
    """
    from specify_cli.cli.commands.agent.mission import _planning_commit_worktree

    spec_path = mission.feature_dir / "spec.md"
    primary_wt, primary_paths = _planning_commit_worktree(
        mission.repo_root, mission.mission_slug, (spec_path,), kind=_PRIMARY_KIND
    )
    # PRIMARY kind never transits coordination: it commits directly from the
    # primary checkout, so the resolved ref is the primary target branch.
    assert primary_wt == mission.repo_root, (
        "PRIMARY kind transited a non-primary worktree (planning→coord route "
        "was not removed)"
    )
    assert primary_paths == (spec_path,)
    primary_ref = resolve_placement_only(
        mission.repo_root, mission.mission_slug, kind=_PRIMARY_KIND
    ).ref

    # COORD kind routes through coordination — its placement ref is the coord ref.
    coord_ref = resolve_placement_only(
        mission.repo_root, mission.mission_slug, kind=_COORD_KIND
    ).ref
    return primary_ref, coord_ref


def _path_workflow_placement_wrapper(mission: _CoordMission) -> tuple[str, str]:
    """Write path 4 (coord-primary-partition-lock WP07 / T033 / T035):
    workflow.py's ``_resolve_workflow_placement`` thin wrapper.

    T033's new checkout-grammar ratchet (``test_no_write_side_rederivation.py``)
    trusts ``_resolve_workflow_placement`` as a sanctioned seam-fold callee
    (a caller assigning from it is treated as seam-derived, not a checkout
    read) WITHOUT re-deriving the placement inline at each of workflow.py's
    write sites. This drives the REAL wrapper (not a stub) against the real
    coord fixture for a representative PRIMARY kind (``WORK_PACKAGE_TASK`` --
    the kind workflow.py actually calls it with for baseline-test capture) and
    the COORD kind (``STATUS_STATE``), proving T033's static "this callee is
    seam-derived" assumption holds behaviorally, not just by AST inspection.
    """
    from specify_cli.cli.commands.agent.workflow import _resolve_workflow_placement

    primary = _resolve_workflow_placement(
        repo_root=mission.repo_root,
        mission_slug=mission.mission_slug,
        kind=MissionArtifactKind.WORK_PACKAGE_TASK,
    )
    coord = _resolve_workflow_placement(
        repo_root=mission.repo_root,
        mission_slug=mission.mission_slug,
        kind=_COORD_KIND,
    )
    return primary.ref, coord.ref


_WRITE_PATHS = {
    "commit_for_mission": _path_commit_for_mission,
    "safe_commit_bypass": _path_safe_commit_bypass,
    "planning_commit_worktree": _path_planning_commit_worktree,
    "workflow_placement_wrapper": _path_workflow_placement_wrapper,
}


@pytest.mark.parametrize("path_name", sorted(_WRITE_PATHS))
def test_two_ref_partition_per_write_path(
    coord_mission: _CoordMission, path_name: str
) -> None:
    """NFR-002 two-ref guard: each converged write path lands the PRIMARY kind on
    the primary ``target_branch`` AND the COORD kind on the ``coordination_branch``.

    A single regression on ANY of the three paths fails its parametrization. The
    real resolver is driven against the real coord fixture — no
    ``resolve_topology`` / ``resolve_placement_only`` stub (D-7).
    """
    resolve_path = _WRITE_PATHS[path_name]
    primary_ref, coord_ref = resolve_path(coord_mission)

    assert primary_ref == coord_mission.target_branch, (
        f"[{path_name}] PRIMARY kind {_PRIMARY_KIND.name} did NOT resolve to the "
        f"primary target branch {coord_mission.target_branch!r}; got {primary_ref!r}"
    )
    assert coord_ref == coord_mission.coordination_branch, (
        f"[{path_name}] COORD kind {_COORD_KIND.name} did NOT resolve to the "
        f"coordination branch {coord_mission.coordination_branch!r}; got {coord_ref!r}"
    )
    # The two refs must DIFFER — a configuration where they collapse to one ref
    # would let a vacuous guard pass.
    assert primary_ref != coord_ref


def test_full_partition_resolves_per_membership(coord_mission: _CoordMission) -> None:
    """Every PRIMARY-partition kind → target_branch; every COORD-partition kind → coord.

    Drives the REAL resolver for the whole partition so a single mis-classified
    kind fails. ``PRIMARY_METADATA`` resolves to the primary surface too (its
    placement is the never-committed-through-a-ref metadata home, asserted via
    ``is_primary_artifact_kind`` rather than a ref equality).
    """
    from mission_runtime import is_primary_artifact_kind

    primary_kinds = {
        MissionArtifactKind.SPEC,
        MissionArtifactKind.DATA_MODEL,
        MissionArtifactKind.RESEARCH,
        MissionArtifactKind.CHECKLIST,
        MissionArtifactKind.FINALIZED_EXECUTION_PLAN,
        MissionArtifactKind.TASKS_INDEX,
        MissionArtifactKind.WORK_PACKAGE_TASK,
        MissionArtifactKind.LANE_STATE,
        MissionArtifactKind.PRIMARY_METADATA,
        MissionArtifactKind.RETROSPECTIVE,
        # FR-003 (coord-commit-integrity): ANALYSIS_REPORT re-homed COORD→PRIMARY.
        MissionArtifactKind.ANALYSIS_REPORT,
    }
    coord_kinds = {
        MissionArtifactKind.STATUS_STATE,
        MissionArtifactKind.ISSUE_MATRIX,
        MissionArtifactKind.ACCEPTANCE_MATRIX,
        # coord-write-placement-closure-01KYCF83 WP02 (FR-003, FR-006): newly
        # classified COORD-partition kinds.
        MissionArtifactKind.DECISION_LOG,
        MissionArtifactKind.TRACER_FILE,
        # review-cycle-verdict-seam-rebuild-01KZ2W7W WP04 (FR-023, ADR
        # 2026-08-03-1): review-cycle artifacts are per-WP lifecycle
        # bookkeeping -- COORD-partition.
        MissionArtifactKind.REVIEW_CYCLE,
        # #3928: the Decision Moment ledger (``decisions/index.json`` +
        # ``decisions/DM-<ulid>.md``) -- coord-authority-owned state, matching
        # the write side's own ``read_dir(STATUS_STATE)`` placement.
        MissionArtifactKind.DECISION_LEDGER,
    }
    # Sanity: the two sets partition the whole enum exactly once.
    assert primary_kinds | coord_kinds == set(MissionArtifactKind)
    assert primary_kinds.isdisjoint(coord_kinds)

    for kind in primary_kinds:
        assert is_primary_artifact_kind(kind), kind
        ref = resolve_placement_only(
            coord_mission.repo_root, coord_mission.mission_slug, kind=kind
        ).ref
        assert ref == coord_mission.target_branch, (
            f"PRIMARY kind {kind.name} resolved to {ref!r}, not the target branch"
        )

    for kind in coord_kinds:
        assert not is_primary_artifact_kind(kind), kind
        ref = resolve_placement_only(
            coord_mission.repo_root, coord_mission.mission_slug, kind=kind
        ).ref
        assert ref == coord_mission.coordination_branch, (
            f"COORD kind {kind.name} resolved to {ref!r}, not the coordination branch"
        )


# ---------------------------------------------------------------------------
# MANDATORY anti-mutant negative test (D-7 / DECISION 7).
# ---------------------------------------------------------------------------


def _patch_partition(
    monkeypatch: pytest.MonkeyPatch,
    *,
    primary: frozenset[MissionArtifactKind],
    placement: frozenset[MissionArtifactKind],
) -> None:
    """Patch the live partition frozensets to ``(primary, placement)``.

    ``resolution.py`` imports ``_PRIMARY_ARTIFACT_KINDS`` by reference, so the
    ``artifacts`` AND ``resolution`` module-level bindings are patched together
    (via ``monkeypatch`` so they auto-restore) to keep the write-side projection
    (``resolve_placement_only``) consistent with the mutated partition. The single
    seam every partition-mutation test drives — so the all-kinds anti-mutant
    reuses this machinery rather than re-implementing the three-binding patch.
    """
    monkeypatch.setattr(artifacts_mod, "_PRIMARY_ARTIFACT_KINDS", primary)
    monkeypatch.setattr(artifacts_mod, "_PLACEMENT_ARTIFACT_KINDS", placement)
    monkeypatch.setattr(resolution_mod, "_PRIMARY_ARTIFACT_KINDS", primary)


@pytest.fixture
def _forced_pre_fix_partition(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the PRE-fix partition: move ``SPEC`` into ``_PLACEMENT_ARTIFACT_KINDS``."""
    orig_primary = artifacts_mod._PRIMARY_ARTIFACT_KINDS
    orig_placement = artifacts_mod._PLACEMENT_ARTIFACT_KINDS
    _patch_partition(
        monkeypatch,
        primary=orig_primary - {MissionArtifactKind.SPEC},
        placement=orig_placement | {MissionArtifactKind.SPEC},
    )


def test_anti_mutant_pre_fix_partition_makes_planning_ref_go_red(
    coord_mission: _CoordMission, _forced_pre_fix_partition: None
) -> None:
    """Anti-mutant: with SPEC forced back into the COORD partition, the planning-ref
    assertion the two-ref guard makes goes RED — proving the guard KILLS the
    "always-coord-for-coord-topology" mutant and is not vacuous (DECISION 7).

    The positive guard (``test_two_ref_partition_per_write_path``) asserts
    ``SPEC → target_branch``. Under the mutant SPEC resolves to the coordination
    branch instead, so that assertion would fail. We assert the mutant's effect
    directly (SPEC now resolves to coord) so this test is the explicit
    mutant-catcher paired with the positive guard.
    """
    spec_ref = resolve_placement_only(
        coord_mission.repo_root, coord_mission.mission_slug, kind=MissionArtifactKind.SPEC
    ).ref
    # Under the pre-fix mutant the planning artifact resolves to coordination —
    # exactly the regression the positive guard forbids.
    assert spec_ref == coord_mission.coordination_branch
    assert spec_ref != coord_mission.target_branch, (
        "Anti-mutant test is vacuous: forcing SPEC into the placement partition "
        "did not change its resolved ref — the two-ref guard could pass vacuously."
    )

# ---------------------------------------------------------------------------
# T014 — the filename-anchored REVIEW_CYCLE classifier leg.
#
# review-cycle-verdict-seam-rebuild-01KZ2W7W WP04 (FR-023): focused unit tests
# directly against ``kind_for_mission_file`` / ``_artifact_kind_for_path`` (not
# only the higher-level guard tests above), per the WP's own explicit
# requirement. The four required cases (one positive, two negative, plus the
# ADR's permissive-glob boundary case) and the anchoring edge case.
# ---------------------------------------------------------------------------

_CLASSIFIER_MISSION_SLUG = "some-mission"


def test_review_cycle_pattern_classifies_to_review_cycle_kind() -> None:
    """Positive case: tasks/WP01/review-cycle-1.md -> REVIEW_CYCLE (T014)."""
    path = f"kitty-specs/{_CLASSIFIER_MISSION_SLUG}/tasks/WP01/review-cycle-1.md"
    assert kind_for_mission_file(path) is MissionArtifactKind.REVIEW_CYCLE


def test_baseline_tests_json_under_wp_dir_stays_work_package_task() -> None:
    """Negative case: tasks/WP01/baseline-tests.json must NOT be reclassified —
    this is the regression the filename-anchoring constraint exists to prevent
    (a directory-anchored rule would silently re-partition it)."""
    path = f"kitty-specs/{_CLASSIFIER_MISSION_SLUG}/tasks/WP01/baseline-tests.json"
    assert kind_for_mission_file(path) is MissionArtifactKind.WORK_PACKAGE_TASK


def test_single_part_wp_task_file_stays_work_package_task() -> None:
    """Negative case: tasks/WP01-foo.md (single relative part) must keep
    classifying WORK_PACKAGE_TASK via the basename-lookup branch, not be
    accidentally caught by the new nested-pattern leg (which only applies to
    the multi-part / nested case)."""
    path = f"kitty-specs/{_CLASSIFIER_MISSION_SLUG}/tasks/WP01-foo.md"
    assert kind_for_mission_file(path) is MissionArtifactKind.WORK_PACKAGE_TASK


def test_review_cycle_pattern_classifies_non_numeric_suffix() -> None:
    """Fourth case (the ADR's permissive-glob boundary, T014 step 3's explicit
    call-out): ``review-cycle-notes.md`` does not match the numeric
    ``review-cycle-<N>.md`` shape ``review/cycle.py``'s OWN writer validates
    (``_REVIEW_CYCLE_FILE_RE``), but the ADR's decision text names the glob
    ``review-cycle-*.md`` verbatim -- a permissive glob, not the writer's
    stricter numeric one. This test makes that boundary EXPLICIT rather than
    accidental: the classifier intentionally accepts it."""
    path = f"kitty-specs/{_CLASSIFIER_MISSION_SLUG}/tasks/WP01/review-cycle-notes.md"
    assert kind_for_mission_file(path) is MissionArtifactKind.REVIEW_CYCLE


def test_review_cycle_pattern_anchors_on_final_component_only() -> None:
    """Edge case: a WP slug that itself contains the substring ``review-cycle``
    must not trigger the classifier via a whole-path substring test -- only the
    FINAL path component (the actual filename) may match the glob. A WP-shaped
    directory segment spelled ``review-cycle-thing`` holding an ordinary WP
    task file must still classify WORK_PACKAGE_TASK."""
    path = (
        f"kitty-specs/{_CLASSIFIER_MISSION_SLUG}/tasks/review-cycle-thing/"
        "baseline-tests.json"
    )
    assert kind_for_mission_file(path) is MissionArtifactKind.WORK_PACKAGE_TASK


def test_review_cycle_pattern_matches_regardless_of_wp_slug_separator() -> None:
    """T014 step 2: the classifier keys purely on the FILENAME pattern, never on
    directory depth or the parent WP-slug spelling — so every accepted WP-slug
    separator shape (spec.md US3: ``-``, ``_``, ``.``, or none) classifies
    identically."""
    for wp_slug in ("WP01", "WP-01", "WP_01", "WP.01", "wp01"):
        path = f"kitty-specs/{_CLASSIFIER_MISSION_SLUG}/tasks/{wp_slug}/review-cycle-2.md"
        assert kind_for_mission_file(path) is MissionArtifactKind.REVIEW_CYCLE, wp_slug


# ---------------------------------------------------------------------------
# T015 — the commit router honours REVIEW_CYCLE for review-cycle paths.
#
# review-cycle-verdict-seam-rebuild-01KZ2W7W WP04 (FR-023): traced call chain
# is ``commit_for_mission`` -> ``_group_files_by_partition`` ->
# ``is_coord_residue_churn`` -> ``kind_for_mission_file`` (now returns
# REVIEW_CYCLE post-T014) -> ``kind_is_coordination_residue`` (now True post-
# T013, since REVIEW_CYCLE is in ``_PLACEMENT_ARTIFACT_KINDS``). This traces
# and CONFIRMS (see the module-level statement below) that
# ``commit_router.py`` needed NO production change: ``is_coord_residue_churn``
# is the sole delegated authority, and T014's classifier fix alone is
# sufficient. These tests exercise that composed chain end-to-end, driving
# the REAL ``commit_for_mission`` against the REAL coord/coordless fixtures --
# no stub, matching this file's existing non-vacuity discipline.
# ---------------------------------------------------------------------------

_SINGLE_BRANCH_TARGET = "feat/single-branch-guard"


def _build_single_branch_mission(tmp_path: Path) -> _CoordMission:
    """Build a real SINGLE_BRANCH (coordless) mission fixture.

    No ``coordination_branch``, ``topology: single_branch`` -- the REAL
    resolver classifies this coordless, so EVERY kind (PRIMARY or COORD-
    partition) resolves to the SAME ``target_branch`` (the coordless-topology
    collapse ``_group_files_by_partition`` documents).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _SINGLE_BRANCH_TARGET)
    _git(repo, "config", "user.email", "guard@example.com")
    _git(repo, "config", "user.name", "Guard Suite")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("project: guard-suite\n", encoding="utf-8")

    mission_id = str(ULID())
    # NOT lowercased: mission_runtime.identity.resolve_mid8 returns
    # ``mission_id[:8]`` VERBATIM (uppercase Crockford, matching
    # ``mid8_from_slug``'s ``[0-9A-HJKMNP-TV-Z]{8}`` regex) -- a lowercased
    # embedded tail here would make ``_resolve_mid8`` (used by
    # ``commit_router.py``'s coord-worktree materialisation) derive an
    # UPPERCASE mid8 that disagrees with this fixture's own LOWERCASE
    # branch/worktree naming, so a genuine coord commit (T015's
    # ``result.status == "committed"`` checks, not merely a resolved-ref
    # check) fails with a worktree/branch HEAD mismatch.
    mid8 = mission_id[:8]
    slug = f"write-surface-guard-single-{mid8}"

    feature_dir = repo / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mid8": mid8,
                "mission_slug": slug,
                "target_branch": _SINGLE_BRANCH_TARGET,
                "topology": "single_branch",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed single-branch mission")

    return _CoordMission(
        repo_root=repo.resolve(),
        mission_slug=slug,
        feature_dir=feature_dir,
        coordination_branch=_SINGLE_BRANCH_TARGET,  # no coord ref; same as target
        target_branch=_SINGLE_BRANCH_TARGET,
    )


@pytest.fixture
def single_branch_mission(tmp_path: Path) -> _CoordMission:
    mission = _build_single_branch_mission(tmp_path)
    assert not routes_through_coordination(
        resolve_topology(mission.repo_root, mission.mission_slug)
    ), "fixture precondition violated: mission must be coordless (SINGLE_BRANCH)"
    return mission


def _write_review_cycle_file(mission: _CoordMission, wp_slug: str, cycle: int) -> Path:
    wp_dir = mission.feature_dir / "tasks" / wp_slug
    wp_dir.mkdir(parents=True, exist_ok=True)
    path = wp_dir / f"review-cycle-{cycle}.md"
    path.write_text(f"# Review cycle {cycle}\n\nverdict: rejected\n", encoding="utf-8")
    return path


def test_review_cycle_write_lands_on_coord_ref_under_coord_topology(
    coord_mission: _CoordMission,
) -> None:
    """T015 (a): a ``kind=REVIEW_CYCLE`` write lands on the coordination ref
    under coord topology -- no production change in ``commit_router.py``, only
    this test coverage (the classifier fix, T014, is the entire mechanism)."""
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy

    policy = ProtectionPolicy(
        protected_branches=frozenset({"main", "master"}), operator_hatch_active=False
    )
    artifact_path = _write_review_cycle_file(coord_mission, "WP01", 1)

    result = commit_for_mission(
        coord_mission.repo_root,
        coord_mission.mission_slug,
        (artifact_path,),
        "chore: Record review-cycle-1 (rejected) for WP01",
        policy,
        kind=MissionArtifactKind.REVIEW_CYCLE,
    )

    assert result.status == "committed", result.diagnostic
    assert result.placement_ref == coord_mission.coordination_branch


def test_review_cycle_write_lands_on_target_branch_under_single_branch_topology(
    single_branch_mission: _CoordMission,
) -> None:
    """T015 (b): the same write under SINGLE_BRANCH lands on ``target_branch``
    (the coordless collapse -- every kind resolves to the same ref there)."""
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy

    policy = ProtectionPolicy(
        protected_branches=frozenset({"main", "master"}), operator_hatch_active=False
    )
    artifact_path = _write_review_cycle_file(single_branch_mission, "WP01", 1)

    result = commit_for_mission(
        single_branch_mission.repo_root,
        single_branch_mission.mission_slug,
        (artifact_path,),
        "chore: Record review-cycle-1 (rejected) for WP01",
        policy,
        kind=MissionArtifactKind.REVIEW_CYCLE,
    )

    assert result.status == "committed", result.diagnostic
    assert result.placement_ref == single_branch_mission.target_branch


def test_mixed_review_cycle_and_work_package_task_batch_splits_under_coord(
    coord_mission: _CoordMission,
) -> None:
    """T015 edge case: a batch mixing a REVIEW_CYCLE file with a
    WORK_PACKAGE_TASK file (e.g. a WP task-file edit landing in the same
    commit as a new review cycle) under coord topology must split into TWO
    commits against TWO different refs -- the one case
    ``_group_files_by_partition``'s genuinely-mixed-AND-refs-diverge branch
    actually exercises new code paths for."""
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy

    policy = ProtectionPolicy(
        protected_branches=frozenset({"main", "master"}), operator_hatch_active=False
    )
    review_cycle_path = _write_review_cycle_file(coord_mission, "WP01", 1)
    wp_task_path = coord_mission.feature_dir / "tasks" / "WP01" / "WP01-foo.md"
    wp_task_path.write_text("# WP01\n", encoding="utf-8")

    result = commit_for_mission(
        coord_mission.repo_root,
        coord_mission.mission_slug,
        (review_cycle_path, wp_task_path),
        "chore: mixed batch (review-cycle-1 + WP01 task edit)",
        policy,
        # Caller's own kind here is WORK_PACKAGE_TASK -- the per-file residue
        # classification (not the caller's kind) decides each file's bucket.
        kind=MissionArtifactKind.WORK_PACKAGE_TASK,
    )

    assert result.status == "committed", result.diagnostic
    # #2549 facet B: commit_hashes carries the UNION of every committed
    # group's hashes -- a genuinely split (mixed-partition) batch reports
    # BOTH, proving two distinct commits against two distinct refs landed.
    refs_committed = {ref for ref, _sha in result.commit_hashes}
    assert refs_committed == {
        coord_mission.target_branch,
        coord_mission.coordination_branch,
    }, (
        "a mixed REVIEW_CYCLE + WORK_PACKAGE_TASK batch under coord topology "
        f"must split into two commits against two distinct refs; got {refs_committed!r}"
    )


# ---------------------------------------------------------------------------
# T016 — REVIEW_CYCLE's E2 (PUBLISHED) eligibility ruling: INCLUDED.
#
# Mirrors the fixture shape of ``tests/mission_runtime/test_consolidated_
# resolution.py``'s ``_build_e2_mission_coord_fully_retired`` (that file is
# NOT owned by this WP) so the PUBLISHED + fully-retired-coordination-branch
# case (the ADR's measured "45 of 45" reality) is exercised for REVIEW_CYCLE
# specifically, inside this WP's own owned test file.
# ---------------------------------------------------------------------------


def _e2_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _build_e2_review_cycle_mission(tmp_path: Path) -> tuple[Path, str]:
    """A genuine PUBLISHED (E2) coord-topology mission whose coordination
    branch has ALSO been retired (0-of-45 shape, ADR 2026-08-03-1) -- returns
    ``(repo_root, mission_slug)``. ``main`` is the resolved Primary Branch.
    """
    from specify_cli.merge.baseline import record_baseline_merge_commit
    from specify_cli.mission_metadata import load_meta, write_meta

    repo = tmp_path / "repo"
    repo.mkdir()
    _e2_git(repo, "init", "-q", "-b", "main")
    _e2_git(repo, "config", "user.email", "guard@example.com")
    _e2_git(repo, "config", "user.name", "Guard Suite")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("project: guard-suite\n", encoding="utf-8")
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    _e2_git(repo, "add", "-A")
    _e2_git(repo, "commit", "-q", "-m", "init")
    init_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    mission_id = str(ULID())
    mid8 = mission_id[:8]
    slug = f"review-cycle-e2-guard-{mid8}"
    target_branch = f"kitty/mission-{slug}"
    coordination_branch = f"kitty/mission-{slug}-coord"

    _e2_git(repo, "checkout", "-q", "-b", target_branch)
    _e2_git(repo, "branch", coordination_branch, target_branch)
    feature_dir = repo / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": slug,
                "mission_id": mission_id,
                "mid8": mid8,
                "mission_number": None,
                "mission_type": "software-dev",
                "target_branch": target_branch,
                "topology": "coord",
                "coordination_branch": coordination_branch,
                "friendly_name": "T016 E2 review-cycle guard fixture",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks" / "WP01").mkdir(parents=True)
    (feature_dir / "tasks" / "WP01" / "review-cycle-1.md").write_text(
        "# Review cycle 1\n\nverdict: rejected\n", encoding="utf-8"
    )
    _e2_git(repo, "add", "-A")
    _e2_git(repo, "commit", "-q", "-m", f"chore({slug}): mission scaffold")

    # E1 consolidation bookkeeping (baseline_merge_commit + mission_number).
    record_baseline_merge_commit(feature_dir, init_sha, mission_id=mission_id)
    meta = load_meta(feature_dir)
    assert meta is not None
    meta["mission_number"] = 999
    write_meta(feature_dir, meta, validate=False)
    _e2_git(repo, "add", "-A")
    _e2_git(repo, "commit", "-q", "-m", f"chore({slug}): record baseline (E1)")

    # Publish (E2): merge to main, delete BOTH the target and coordination
    # branches -- the 0-of-45 shape.
    _e2_git(repo, "branch", "-D", coordination_branch)
    _e2_git(repo, "checkout", "-q", "main")
    _e2_git(repo, "merge", "-q", "--no-ff", target_branch, "-m", f"Merge {target_branch}")
    _e2_git(repo, "branch", "-D", target_branch)

    return repo.resolve(), slug


def test_review_cycle_e2_published_resolves_consolidated_surface(tmp_path: Path) -> None:
    """T016 (INCLUDED): a PUBLISHED mission's REVIEW_CYCLE write resolves the
    CONSOLIDATED target (the resolved Primary Branch NAME) directly -- the
    unconditional coordination-surface probe (which would raise
    ``CoordinationBranchDeleted`` for every one of the ADR's measured 45
    already-retired-coord missions) is BYPASSED for this phase+kind
    combination, exactly like ISSUE_MATRIX/TRACER_FILE/ACCEPTANCE_MATRIX."""
    repo, mission_slug = _build_e2_review_cycle_mission(tmp_path)

    resolved = resolve_placement_only(repo, mission_slug, kind=MissionArtifactKind.REVIEW_CYCLE)

    assert resolved == CommitTarget(ref="main")


def test_review_cycle_e2_ruling_does_not_affect_status_state_exclusion(
    tmp_path: Path,
) -> None:
    """T016 non-regression: STATUS_STATE / DECISION_LOG's existing exclusion
    from the E2-eligible set is unaffected by REVIEW_CYCLE's inclusion --
    STATUS_STATE still probes coordination (and raises) for the SAME
    fully-retired-coord E2 fixture."""
    from mission_runtime import ActionContextError

    repo, mission_slug = _build_e2_review_cycle_mission(tmp_path)

    with pytest.raises(ActionContextError):
        resolve_placement_only(repo, mission_slug, kind=MissionArtifactKind.STATUS_STATE)
