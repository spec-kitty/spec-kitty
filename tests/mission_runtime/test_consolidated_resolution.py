"""Unit tests for phase-aware CONSOLIDATED resolution (WP03, T009-T013).

Mission ``post-merge-write-authoring-finish-01KYRRM5`` (FR-001/002/003,
C-001/002/003/005, NFR-001/004). Covers:

* E1 (CONSOLIDATED) — PRIMARY-kind and coord-kind resolution is BYTE-IDENTICAL
  to #3076 (no behaviour change on this leg, per the ADR).
* E2 (PUBLISHED), content present — the in-scope kinds (PRIMARY +
  ISSUE_MATRIX/TRACER_FILE/ACCEPTANCE_MATRIX) resolve to the resolved Primary
  Branch NAME, never a SHA or ``HEAD`` (paula MINOR-2), and the coordination-
  surface probe is bypassed entirely (so a fully-retired E2 mission whose
  coordination branch has ALSO been deleted does not raise
  ``CoordinationBranchDeleted`` — the #3033 T007 shape).
* E2, content absent — refuses (``ActionContextError``), never a fabricated
  write.
* The squash case (D1, priti m3) — content-presence succeeds where an
  ancestry-based check (``git merge-base --is-ancestor``) would
  false-negative; this test PINS that rejection.
* SC-005 — ``STATUS_STATE`` / ``DECISION_LOG`` resolution via
  ``resolve_artifact_surface`` is UNCHANGED in PRE_CONSOLIDATION and E2 (not
  re-routed to CONSOLIDATED) — the shared-resolver non-regression guarantee.
* Renata M1 — both ``resolve_placement_only`` (probe) and
  ``resolve_artifact_surface`` (materializer) derive the SAME
  :class:`~mission_runtime.lifecycle_phase.LifecyclePhase` for one mission
  state (no split-brain, NFR-001).

Fixtures build REAL git repos through the actual merge-time bookkeeping entry
point (:func:`specify_cli.merge.baseline.record_baseline_merge_commit`),
mirroring ``tests/specify_cli/cli/commands/test_issue_3033_post_consolidation_write.py``
(WP02) and ``tests/mission_runtime/test_lifecycle_phase.py`` (WP03 T008).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import mission_runtime.resolution as resolution_module
from mission_runtime import (
    ActionContextError,
    CommitTarget,
    MissionArtifactKind,
    resolve_artifact_surface,
    resolve_placement_only,
)
from mission_runtime.lifecycle_phase import LifecyclePhase, resolve_lifecycle_phase
from specify_cli.merge.baseline import record_baseline_merge_commit
from specify_cli.mission_metadata import load_meta, write_meta

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Real-git plumbing helpers (mirrors tests/regression/test_issue_3033_*)
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args], cwd=repo)


def _init_git_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)], cwd=repo)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.json").write_text("{}\n", encoding="utf-8")
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _branch_exists(repo: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo,
        capture_output=True,
    )
    return result.returncode == 0


def _write_meta(
    feature_dir: Path,
    *,
    mission_slug: str,
    mission_id: str,
    mid8: str,
    target_branch: str,
    topology: str = "single_branch",
    coordination_branch: str | None = None,
) -> None:
    meta: dict[str, object] = {
        "mission_slug": mission_slug,
        "mission_id": mission_id,
        "mid8": mid8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": target_branch,
        "topology": topology,
        "friendly_name": "Consolidated resolution fixture",
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_wp_file(feature_dir: Path, wp_id: str) -> Path:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    wp_path = tasks_dir / f"{wp_id}-evidence.md"
    wp_path.write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\n---\n# {wp_id}\n",
        encoding="utf-8",
    )
    return wp_path


def _write_issue_matrix_file(feature_dir: Path) -> Path:
    matrix_path = feature_dir / "issue-matrix.json"
    matrix_path.write_text(
        json.dumps({"schema_version": 1, "rows": {}}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return matrix_path


def _done_event(mission_slug: str, wp_id: str) -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": "2026-07-30T12:00:00+00:00",
        "event_id": f"01HXYZCONSOLRES0000{wp_id}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": mission_slug,
        "force": False,
        "from_lane": "approved",
        "reason": None,
        "review_ref": None,
        "to_lane": "done",
        "wp_id": wp_id,
    }


def _consolidate_e1(
    repo: Path,
    feature_dir: Path,
    *,
    mission_slug: str,
    mission_id: str,
    baseline_commit: str,
    mission_number: int,
) -> None:
    record_baseline_merge_commit(feature_dir, baseline_commit, mission_id=mission_id)
    meta = load_meta(feature_dir)
    assert meta is not None
    meta["mission_number"] = mission_number
    write_meta(feature_dir, meta, validate=False)
    _git(repo, "add", ".")
    _git(
        repo,
        "commit",
        "-m",
        f"chore({mission_slug}): record baseline_merge_commit (E1 consolidation)",
    )


def _build_e1_mission_flat(repo: Path, *, mid8: str, mission_number: int) -> tuple[str, Path, str]:
    """A genuine E1 (CONSOLIDATED) mission — FLAT topology, Target Ref intact.

    Returns ``(mission_slug, feature_dir, target_branch)``.
    """
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"widget-catalog-{mid8}"
    target_branch = f"kitty/mission-{mission_slug}"
    wp_id = "WP01"

    _git(repo, "checkout", "-q", "-b", target_branch)
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch=target_branch,
    )
    _write_wp_file(feature_dir, wp_id)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold")
    # The scaffold commit — NOT the pre-mission ``init`` commit — is the
    # baseline: it exists ONLY on ``target_branch``'s lineage, so a squash
    # publish (which creates ONE new commit on main whose parent is main's
    # PRE-EXISTING tip, never ``target_branch``) makes it a genuine
    # NON-ancestor of the squashed tip — the exact D1 scenario the squash
    # test (below) pins. Using the shared pre-mission ``init`` commit instead
    # would be trivially an ancestor of every branch and prove nothing.
    scaffold_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    _consolidate_e1(
        repo,
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        baseline_commit=scaffold_sha,
        mission_number=mission_number,
    )
    return mission_slug, feature_dir, target_branch


def _build_e2_mission_flat(repo: Path, *, mid8: str, mission_number: int, squash: bool = False) -> tuple[str, Path, Path, str]:
    """A genuine E2 (PUBLISHED) mission — FLAT topology, Target Ref deleted.

    ``squash=True`` publishes via ``git merge --squash`` (D1's load-bearing
    case: the E1 baseline commit is NOT a commit-ancestor of the resulting
    Primary Branch tip) instead of a real merge commit.

    Returns ``(mission_slug, feature_dir, wp_path, target_branch)``.
    """
    mission_slug, feature_dir, target_branch = _build_e1_mission_flat(repo, mid8=mid8, mission_number=mission_number)
    wp_path = feature_dir / "tasks" / "WP01-evidence.md"

    _git(repo, "checkout", "-q", "main")
    if squash:
        _git(repo, "merge", "-q", "--squash", target_branch)
        _git(repo, "commit", "-m", f"Squash-merge {target_branch}")
    else:
        _git(repo, "merge", "-q", "--no-ff", target_branch, "-m", f"Merge {target_branch}")
    _git(repo, "branch", "-D", target_branch)
    return mission_slug, feature_dir, wp_path, target_branch


def _build_e2_mission_coord_fully_retired(repo: Path, *, mid8: str, mission_number: int) -> tuple[str, Path, str, str]:
    """A genuine E2 mission whose COORD coordination branch has ALSO been
    retired -- the #3033 T007 shape (the coord-probe-bypass pin).

    Returns ``(mission_slug, feature_dir, target_branch, coordination_branch)``.
    """
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"invoice-export-{mid8}"
    target_branch = f"kitty/mission-{mission_slug}"
    coordination_branch = f"kitty/mission-{mission_slug}-coord"
    wp_id = "WP01"

    init_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "checkout", "-q", "-b", target_branch)
    _git(repo, "branch", coordination_branch, target_branch)
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch=target_branch,
        topology="coord",
        coordination_branch=coordination_branch,
    )
    _write_wp_file(feature_dir, wp_id)
    _write_issue_matrix_file(feature_dir)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold")

    _consolidate_e1(
        repo,
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        baseline_commit=init_sha,
        mission_number=mission_number,
    )
    _git(repo, "branch", "-D", coordination_branch)

    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", target_branch, "-m", f"Merge {target_branch}")
    _git(repo, "branch", "-D", target_branch)
    return mission_slug, feature_dir, target_branch, coordination_branch


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    _init_git_repo(r)
    return r


# ---------------------------------------------------------------------------
# E1 (CONSOLIDATED): byte-identical to #3076 (T012 regression floor)
# ---------------------------------------------------------------------------


def test_e1_primary_kind_resolves_target_ref_tree_unchanged(repo: Path) -> None:
    """E1: a PRIMARY-kind write still resolves the Target Ref — no behaviour
    change on this leg (ADR Decision 1 §2)."""
    mission_slug, _feature_dir, target_branch = _build_e1_mission_flat(repo, mid8="01KYT1AA", mission_number=301)

    resolved = resolve_placement_only(repo, mission_slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK)

    assert resolved == CommitTarget(ref=target_branch)
    assert _branch_exists(repo, target_branch)


# ---------------------------------------------------------------------------
# E2 (PUBLISHED), content present: in-scope kinds route to CONSOLIDATED
# ---------------------------------------------------------------------------


def test_e2_primary_kind_resolves_primary_branch_name(repo: Path) -> None:
    """E2 / SC-001: a PRIMARY-kind write resolves the resolved Primary Branch
    NAME — an existing branch, never a SHA or HEAD (paula MINOR-2)."""
    mission_slug, _feature_dir, _wp_path, target_branch = _build_e2_mission_flat(repo, mid8="01KYT1BB", mission_number=302)

    resolved = resolve_placement_only(repo, mission_slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK)

    assert resolved == CommitTarget(ref="main")
    assert _branch_exists(repo, resolved.ref), f"resolved ref {resolved.ref!r} must be an EXISTING branch — never the deleted Target Ref {target_branch!r}"
    assert not _branch_exists(repo, target_branch)


@pytest.mark.parametrize(
    "kind",
    [
        MissionArtifactKind.ISSUE_MATRIX,
        MissionArtifactKind.TRACER_FILE,
        MissionArtifactKind.ACCEPTANCE_MATRIX,
    ],
)
def test_e2_coord_kind_bypasses_deleted_coordination_branch(repo: Path, kind: MissionArtifactKind) -> None:
    """E2 / SC-002 / #3033 T007 shape: a coord-partition in-scope kind on a
    mission whose coordination branch has ALSO been retired resolves the
    CONSOLIDATED target directly — the unconditional coordination-surface
    probe (which would raise ``CoordinationBranchDeleted``) must be BYPASSED
    for this phase+kind combination, not merely tolerated."""
    mission_slug, _feature_dir, _target, _coord = _build_e2_mission_coord_fully_retired(repo, mid8="01KYT1CC", mission_number=303)

    resolved = resolve_placement_only(repo, mission_slug, kind=kind)

    assert resolved == CommitTarget(ref="main")


@pytest.mark.parametrize("kind", [MissionArtifactKind.STATUS_STATE, MissionArtifactKind.DECISION_LOG])
def test_e2_status_state_still_probes_coordination_and_is_unaffected(repo: Path, kind: MissionArtifactKind) -> None:
    """SC-005 guard: ``STATUS_STATE`` and ``DECISION_LOG`` are NOT in
    the E2 in-scope set, so a fully-retired-coord E2 mission still raises
    ``CoordinationBranchDeleted`` (wrapped) for it — proving the E2
    short-circuit is genuinely kind-scoped, not blanket."""
    mission_slug, _feature_dir, _target, _coord = _build_e2_mission_coord_fully_retired(repo, mid8="01KYT1DD", mission_number=304)

    from specify_cli.coordination.surface_resolver import resolve_status_surface

    # Completed-mission reads stay anchored to the published primary tree, but
    # that read shortcut must not authorize an excluded kind's write placement.
    expected_read = _feature_dir / "status.events.jsonl"
    assert resolve_status_surface(repo, mission_slug) == expected_read
    with pytest.raises(ActionContextError):
        resolve_placement_only(repo, mission_slug, kind=kind)
    assert resolve_status_surface(repo, mission_slug) == expected_read


# ---------------------------------------------------------------------------
# E2, content absent: refuse, never fabricate
# ---------------------------------------------------------------------------


def test_e2_content_absent_refuses(repo: Path) -> None:
    """E2 but ``main`` (the resolved Primary Branch) does NOT carry the
    mission's consolidated content (a broken publish: the Target Ref was
    cleaned up WITHOUT ever landing on trunk) -> ``ActionContextError``,
    never a fabricated write to a ref that doesn't hold the content.

    The phase-derivation itself (``resolve_lifecycle_phase``) reads
    ``meta.json`` off the CURRENT WORKING TREE, so this fixture stays
    detached at the mission's own commit (files still on disk, exactly like
    a lane worktree that was never cleaned up) while deleting ONLY the
    branch ref — main's git-tree content (what
    ``content_present_at_primary_tip`` actually probes) never received the
    mission's commits at all.
    """
    mission_slug, feature_dir, target_branch = _build_e1_mission_flat(repo, mid8="01KYT1EE", mission_number=305)
    assert feature_dir.exists()
    # Detach HEAD at the mission's own commit (working tree — and therefore
    # meta.json on disk — is UNCHANGED) so the branch ref itself can be
    # deleted without losing filesystem access to meta.json.
    _git(repo, "checkout", "-q", "--detach", "HEAD")
    _git(repo, "branch", "-D", target_branch)
    assert not _branch_exists(repo, target_branch)
    # ``main`` was never touched by a merge — it still sits at the original
    # ``init`` commit, so it genuinely lacks the mission's kitty-specs/ tree.

    with pytest.raises(ActionContextError) as excinfo:
        resolve_placement_only(repo, mission_slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK)

    assert excinfo.value.code == "CONSOLIDATED_CONTENT_ABSENT"
    assert "main" in str(excinfo.value)


# ---------------------------------------------------------------------------
# The squash case (D1, priti m3): content-presence succeeds where
# commit-ancestry would false-negative — pins the rejected approach.
# ---------------------------------------------------------------------------


def test_squash_publish_resolves_via_content_presence_not_ancestry(repo: Path) -> None:
    """D1's load-bearing scenario: after a SQUASH publish-to-trunk, the E1
    consolidation commit is NOT a commit-ancestor of the Primary Branch tip.
    An ancestry-based check would false-negative here — this test PINS that
    rejection (priti m3) while proving the actual (content-presence)
    predicate succeeds."""
    mission_slug, feature_dir, wp_path, target_branch = _build_e2_mission_flat(repo, mid8="01KYT1FF", mission_number=306, squash=True)
    meta = load_meta(feature_dir)
    assert meta is not None
    baseline_commit = str(meta["baseline_merge_commit"])

    # Pin the REJECTED approach: ancestry-based resolution would false-negative
    # on this exact (realistic) squash-publish fixture.
    ancestry_check = subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline_commit, "HEAD"],
        cwd=repo,
        capture_output=True,
    )
    assert ancestry_check.returncode != 0, (
        "the squash fixture must make the E1 baseline commit a NON-ancestor "
        "of the Primary Branch tip -- otherwise this test is not exercising "
        "the squash-robustness the content-presence predicate exists for"
    )

    # The ACTUAL (content-presence) predicate succeeds despite the above.
    resolved = resolve_placement_only(repo, mission_slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK)

    assert resolved == CommitTarget(ref="main")
    assert wp_path.exists()


# ---------------------------------------------------------------------------
# SC-005: STATUS_STATE / DECISION_LOG resolution via resolve_artifact_surface
# is UNCHANGED (materializer / read side)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", [MissionArtifactKind.STATUS_STATE, MissionArtifactKind.DECISION_LOG])
def test_sc005_unchanged_pre_consolidation(repo: Path, kind: MissionArtifactKind) -> None:
    """PRE_CONSOLIDATION: resolve_artifact_surface's classification for
    STATUS_STATE/DECISION_LOG is untouched by the new phase call (fast path,
    zero subprocess — NFR-004)."""
    mid8 = "01KYT1GG"
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"widget-catalog-{mid8}"
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch="feat/never-materialized",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): scaffold")

    resolved = resolve_artifact_surface(repo, mission_slug, kind)

    assert resolved.path == feature_dir


@pytest.mark.parametrize("kind", [MissionArtifactKind.STATUS_STATE, MissionArtifactKind.DECISION_LOG])
def test_sc005_unchanged_in_e2(repo: Path, kind: MissionArtifactKind) -> None:
    """E2 (PUBLISHED): STATUS_STATE / DECISION_LOG are NOT re-routed to
    CONSOLIDATED — the resolved surface/path is identical to the
    PRE_CONSOLIDATION case above (C-005 non-regression, ADR Decision 1 §6)."""
    mission_slug, feature_dir, _wp_path, _target = _build_e2_mission_flat(repo, mid8="01KYT1HH", mission_number=307)

    resolved = resolve_artifact_surface(repo, mission_slug, kind)

    # Flat/single_branch topology: PRIMARY is the declared home for a
    # coord-partition kind regardless of phase (AH-2) — unaffected by E2.
    assert resolved.path == feature_dir
    # Sanity: this really is E2 (the phase this test exists to probe).
    assert resolve_lifecycle_phase(mission_slug, repo) is LifecyclePhase.PUBLISHED


# ---------------------------------------------------------------------------
# Renata M1: byte-identical phase from both entry points (no split-brain)
# ---------------------------------------------------------------------------


def test_probe_and_materializer_derive_identical_phase(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both ``resolve_placement_only`` (the probe) and
    ``resolve_artifact_surface`` (the materializer) call the SAME
    ``resolve_lifecycle_phase`` — this test intercepts both call sites and
    asserts they observe the identical phase for one mission state
    (NFR-001, no split-brain)."""
    mission_slug, _feature_dir, _wp_path, _target = _build_e2_mission_flat(repo, mid8="01KYT1II", mission_number=308)

    observed: list[LifecyclePhase] = []

    def _spy(*args: object, **kwargs: object) -> LifecyclePhase:
        phase = resolve_lifecycle_phase(*args, **kwargs)  # type: ignore[arg-type]
        observed.append(phase)
        return phase

    monkeypatch.setattr(resolution_module, "resolve_lifecycle_phase", _spy)

    resolve_placement_only(repo, mission_slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK)
    resolve_artifact_surface(repo, mission_slug, MissionArtifactKind.STATUS_STATE)

    assert len(observed) == 2, "both entry points must call the single phase authority"
    assert observed[0] is observed[1] is LifecyclePhase.PUBLISHED
