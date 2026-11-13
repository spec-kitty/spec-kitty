"""#7560: a Mission whose base the target branch lacks (the fork shapes).

Every reconciliation window is ``window_base..ref``, where ``window_base`` is the target
branch's pre-run tip. On a fork the local target need not reach the commit the Mission
branch was cut from, so history that predates the Mission reads as Mission work: the
declaration guard (#6771) refuses ``DEPENDENCY_REF_COVERS_MISSION_WORK`` naming an upstream
commit, and the closed world reports pre-Mission commits as un-attributable content.

Red-first through ``spec-kitty consolidate`` (Charter Standing Order 4):

* the acceptance tests for both reported shapes were strict xfails until the fix (WP04
  flipped them); each first proves, through :func:`_assert_refusal_is_7560`, that a refusal
  it sees carries the bug's own token, and raises :class:`UnrelatedRefusalError` when it does
  not, so a regression names its cause;
* the soundness ratchets on the same fork fixture stay green: genuine post-base Mission
  work keeps refusing, named by its own SHA;
* the non-fork control keeps its verdict (NFR-001).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.terminus.conftest import (
    CoordMission,
    _commit_planning_artifacts,
    _commit_status_events,
    _cut_coord_branch,
    _cut_lane_branch,
    _finish_coord_mission,
    _init_fixture_repo,
    _stamped_approve_events,
    _write_manifest,
    _write_meta,
    _write_wp_file,
    build_coord_mission,
    patch_id,
    reached_reconciliation_verdict,
    restamp_approvals_at_lane_tips,
    run_terminus,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

UPSTREAM = "upstream"
PIN_TAG = "PIN"
DEP_BRANCH = "dep-branch"
COVERS_MISSION_WORK = "Error code: DEPENDENCY_REF_COVERS_MISSION_WORK."
UNATTRIBUTABLE = "un-attributable"
_BUG_TOKENS = (COVERS_MISSION_WORK, UNATTRIBUTABLE)
_WPS = ("WP01", "WP02")


class UnrelatedRefusalError(Exception):
    """A refusal that does not carry #7560's token: the fixture or another gate broke, not the bug."""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _is_ancestor(repo: Path, ancestor: str, ref: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", ancestor, ref], cwd=repo, capture_output=True, check=False).returncode == 0


def _flat(result: subprocess.CompletedProcess[str]) -> str:
    return " ".join((result.stdout + "\n" + result.stderr).split())


def _assert_refusal_is_7560(result: subprocess.CompletedProcess[str], fork: ForkMission) -> None:
    """Always-run proof that a refusal is #7560, so a failure here always names its cause.

    A run that exits 0 passes through (the fixed product). A run that refuses must carry
    one of the bug's tokens AND name pre-Mission history: a commit of ``R..B`` by SHA or
    by patch-id (the real run's lane consolidation re-letters them), or a path only that
    history wrote (the squash axis names files). That is the shape of the defect. Anything
    else raises :class:`UnrelatedRefusalError`.
    """
    if result.returncode == 0:
        return
    flat = _flat(result)
    if not any(token in flat for token in _BUG_TOKENS):
        raise UnrelatedRefusalError(f"refused without a #7560 token (exit {result.returncode}):\n{flat[-3000:]}")
    evidence = [sha[:10] for sha in fork.pre_base_shas] + [pid[:12] for pid in fork.pre_base_patch_ids] + [f"'{path}'" for path in fork.pre_base_paths]
    if not any(item in flat for item in evidence):
        raise UnrelatedRefusalError(f"refused with a #7560 token but named no pre-base history:\n{flat[-3000:]}")


def _assert_clean_forecast(result: subprocess.CompletedProcess[str]) -> None:
    flat = _flat(result)
    assert result.returncode == 0, f"exit {result.returncode}:\n{flat[-3000:]}"
    assert "would FAIL" not in flat and "would REFUSE" not in flat, flat[-3000:]


# ---------------------------------------------------------------------------
# Fixture: the fork shapes
# ---------------------------------------------------------------------------


@dataclass
class ForkMission:
    """A coord-topology Mission cut from ``B`` (upstream ``PIN`` + one overlay), on a target at ``R``."""

    mission: CoordMission
    root: str  # R: the target's only commit, and the tip it is rewound to
    pin: str  # PIN: the upstream pin, B's first parent
    base: str  # B: the Mission base (the overlay commit)
    deleted_path: str  # a path upstream added and deleted before the base
    pre_base_shas: tuple[str, ...]  # every commit in R..B, base included
    pre_base_patch_ids: tuple[str, ...]  # their patch-ids
    pre_base_paths: tuple[str, ...]  # every path R..B wrote


def _require(condition: bool, message: str) -> None:
    """A fixture invariant: a broken fixture raises :class:`RuntimeError`, never an ``AssertionError``."""
    if not condition:
        raise RuntimeError(f"fixture invariant broken: {message}")


def _commit_file(repo: Path, rel: str, content: str, message: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _plant_upstream(repo: Path) -> str:
    """Upstream history from R that adds files and later deletes one (a pre-base deletion)."""
    _git(repo, "checkout", "-qb", UPSTREAM)
    _commit_file(repo, "up/a.py", "A = 1\n", "feat(upstream): a")
    _commit_file(repo, "up/b.py", "B = 1\n", "feat(upstream): b")
    _commit_file(repo, "up/c.py", "C = 1\n", "feat(upstream): c")
    _git(repo, "rm", "-q", "up/b.py")
    _git(repo, "commit", "-qm", "chore(upstream): drop b")
    _git(repo, "tag", PIN_TAG)
    return _git(repo, "rev-parse", "HEAD")


def build_fork_mission(tmp_path: Path, *, mid8: str) -> ForkMission:
    """Report 2: the Mission base is ``PIN`` + one overlay commit, and the target never received either.

    Built like :func:`tests.terminus.conftest.build_coord_mission` (planning scaffold on
    ``B``, coordination branch, one lane per WP with real code, stamped approvals, status
    committed on the target and the coordination branch fast-forwarded to it), then the
    target is rewound to ``R`` so it lacks ``B``. The coordination worktree holds the
    coordination branch and the status log, so the rewind leaves both in place.

    Fixture adjustment (T001 note): a bare rewind to ``R`` leaves no ``kitty-specs/<slug>/``
    in the repository root checkout and ``consolidate`` stops at "Mission not found". So the
    target gets one commit above ``R`` that carries only the Mission directory (bookkeeping
    paths), copied from the coordination branch; it carries none of ``B``'s history.
    """
    slug = f"terminus-{mid8.upper()}"
    mission = _init_fixture_repo(tmp_path, mid8=mid8, slug=slug, target_branch="main")
    repo = mission.repo
    root = _git(repo, "rev-parse", "HEAD")
    pin = _plant_upstream(repo)
    _git(repo, "checkout", "-q", mission.target_branch)
    _git(repo, "reset", "-q", "--hard", pin)
    base = _commit_file(repo, "overlay/cfg.txt", "fork = true\n", "chore(fork): overlay on the upstream pin")

    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)
    _write_manifest(mission, _WPS)
    for wp_id in _WPS:
        _write_wp_file(mission, wp_id)
    _commit_planning_artifacts(mission, f"chore({slug}): bootstrap coord mission")
    _cut_coord_branch(mission)

    events: list[dict[str, object]] = []
    for idx, wp_id in enumerate(_WPS):

        def _plant_code(repo: Path, wp_id: str = wp_id, idx: int = idx) -> None:
            _commit_file(repo, f"src/pkg/{wp_id.lower()}.py", f"def {wp_id.lower()}() -> int:\n    return {idx}\n", f"feat({slug}): {wp_id} approved code")

        claim_head = mission.rev(mission.coord_branch)
        mission.lane_branches[wp_id] = _cut_lane_branch(mission, f"lane-{chr(ord('a') + idx)}", [_plant_code])
        events.extend(_stamped_approve_events(mission, wp_id, claim_head=claim_head, approved_head=mission.rev(mission.lane_branches[wp_id])))
    _commit_status_events(mission, events, f"chore({slug}): approve coord mission WPs")
    _finish_coord_mission(mission)

    _git(repo, "checkout", "-q", mission.target_branch)
    _git(repo, "reset", "-q", "--hard", root)
    # The repository root checkout must still carry the Mission directory, or ``consolidate``
    # stops at "Mission not found". One bookkeeping-only commit above R carries it, without
    # any of B's history (the shape of a fork target that received the planning artifacts).
    _copy_mission_dir_to_target(mission, "planning artifacts on the fork target")

    # Fixture invariants: a broken fixture errors here (a RuntimeError, never a test assertion).
    _require(not _is_ancestor(repo, base, mission.target_branch), "the target must lack the Mission base")
    _require(_git(repo, "rev-parse", f"{base}^") == pin, "PIN must be B's first parent")
    _require(_is_ancestor(repo, base, mission.coord_branch), "the Mission branch must descend from B")
    _require(not _is_ancestor(repo, pin, mission.target_branch), "the target must lack PIN")
    pre_base = tuple(_git(repo, "rev-list", f"{root}..{base}").split())
    _require(len(pre_base) == 5, f"R..B must hold five commits: {pre_base}")
    patch_ids = tuple(patch_id(repo, sha) for sha in pre_base)
    _require(all(patch_ids), f"every pre-base commit must have a patch-id: {patch_ids}")
    paths = tuple(_git(repo, "log", "--format=", "--name-only", f"{root}..{base}").split())
    _require("up/b.py" in paths and "overlay/cfg.txt" in paths, f"R..B must write up/b.py and overlay/cfg.txt: {paths}")
    return ForkMission(
        mission=mission,
        root=root,
        pin=pin,
        base=base,
        deleted_path="up/b.py",
        pre_base_shas=pre_base,
        pre_base_patch_ids=patch_ids,
        pre_base_paths=tuple(sorted(set(paths))),
    )


def _copy_mission_dir_to_target(mission: CoordMission, subject: str) -> None:
    """Commit the coordination branch's Mission directory onto the target (repository root checkout), bookkeeping only."""
    rel_feature_dir = mission.feature_dir.relative_to(mission.repo).as_posix()
    _git(mission.repo, "checkout", mission.coord_branch, "--", rel_feature_dir)
    _git(mission.repo, "commit", "-qm", f"chore({mission.slug}): {subject}")


def _merge_into_lane(mission: CoordMission, tmp_path: Path, branch: str, wp_id: str) -> None:
    """Merge *branch* ``--no-ff`` into *wp_id*'s lane, then record that review approved the merged tip."""
    lane_wt = tmp_path / f"lane-wt-{wp_id.lower()}"
    _git(mission.repo, "worktree", "add", "-q", lane_wt.as_posix(), mission.lane_branch(wp_id))
    _git(lane_wt, "merge", "-q", "--no-ff", "--no-edit", branch)
    _git(mission.repo, "worktree", "remove", lane_wt.as_posix())
    restamp_approvals_at_lane_tips(mission)


def _commit_on_new_branch(repo: Path, tmp_path: Path, branch: str, start: str, files: dict[str, str]) -> str:
    """Create *branch* at *start* and commit each file in its own commit (in a scratch worktree)."""
    _git(repo, "branch", branch, start)
    wt = tmp_path / f"wt-{branch.replace('/', '-')}"
    _git(repo, "worktree", "add", "-q", wt.as_posix(), branch)
    for rel, content in files.items():
        _commit_file(wt, rel, content, f"feat({branch}): {rel}")
    _git(repo, "worktree", "remove", wt.as_posix())
    return _git(repo, "rev-parse", branch)


def build_fork_mission_with_upstream_merge(tmp_path: Path, *, mid8: str) -> tuple[ForkMission, str]:
    """Report 1: report 2's fork, plus ``upstream`` advanced and merged ``--no-ff`` into WP02's lane.

    ``U``'s history carries the pre-base upstream commits the target lacks. Returns the
    fork and ``U``.
    """
    fork = build_fork_mission(tmp_path, mid8=mid8)
    repo = fork.mission.repo
    wt = tmp_path / "upstream-wt"
    _git(repo, "worktree", "add", "-q", wt.as_posix(), UPSTREAM)
    _commit_file(wt, "up/d.py", "D = 1\n", "feat(upstream): d")
    _commit_file(wt, "up/e.py", "E = 1\n", "feat(upstream): e")
    _git(repo, "worktree", "remove", wt.as_posix())
    upstream_tip = _git(repo, "rev-parse", UPSTREAM)
    _merge_into_lane(fork.mission, tmp_path, UPSTREAM, "WP02")
    # The restamp rewrote the approval events in place (same event ids) on the coordination
    # branch; the fork target's copy of the Mission directory must carry the same log, or the
    # real run's landing stops at the status merge driver ("Conflicting payloads"), not at #7560.
    _copy_mission_dir_to_target(fork.mission, "refresh the planning artifacts on the fork target")
    _require(not _is_ancestor(repo, fork.pin, fork.mission.target_branch), "the target must lack PIN")
    return fork, upstream_tip


def _consolidate(mission: CoordMission, *extra: str, strategy: str | None = "merge") -> subprocess.CompletedProcess[str]:
    args = ["consolidate", "--mission", mission.slug]
    if strategy is not None:
        args += ["--strategy", strategy]
    return run_terminus(mission, [*args, *extra])


# ---------------------------------------------------------------------------
# T003: acceptance (both reported shapes; strict xfails until WP04)
# ---------------------------------------------------------------------------


def test_report2_declared_pin_forecast_passes(tmp_path: Path) -> None:
    """Declaring the upstream pin must not be refused for covering the pin's own history."""
    fork = build_fork_mission(tmp_path, mid8="01M7560A")

    result = _consolidate(fork.mission, "--dry-run", "--dependency-ref", fork.pin)

    _assert_refusal_is_7560(result, fork)
    _assert_clean_forecast(result)


def test_report2_plain_forecast_passes(tmp_path: Path) -> None:
    """Undeclared, the pre-base upstream commits must not read as un-attributable Mission content."""
    fork = build_fork_mission(tmp_path, mid8="01M7560B")

    result = _consolidate(fork.mission, "--dry-run")

    _assert_refusal_is_7560(result, fork)
    _assert_clean_forecast(result)


def test_report2_real_merge_run_lands(tmp_path: Path) -> None:
    fork = build_fork_mission(tmp_path, mid8="01M7560C")

    result = _consolidate(fork.mission, "--yes")

    _assert_refusal_is_7560(result, fork)
    assert result.returncode == 0, _flat(result)[-3000:]
    assert reached_reconciliation_verdict(result) and "reconciliation verified" in _flat(result).lower(), _flat(result)[-3000:]


def test_report1_declared_upstream_forecast_and_real_run_land(tmp_path: Path) -> None:
    fork, _upstream_tip = build_fork_mission_with_upstream_merge(tmp_path, mid8="01M7560D")

    forecast = _consolidate(fork.mission, "--dry-run", "--dependency-ref", UPSTREAM)
    _assert_refusal_is_7560(forecast, fork)
    _assert_clean_forecast(forecast)

    real = _consolidate(fork.mission, "--yes", "--dependency-ref", UPSTREAM)
    _assert_refusal_is_7560(real, fork)
    assert real.returncode == 0, _flat(real)[-3000:]


def test_report2_default_squash_forecast_passes(tmp_path: Path) -> None:
    """The squash axes must not flag the pre-base deletion and blobs as un-attributable."""
    fork = build_fork_mission(tmp_path, mid8="01M7560E")

    result = _consolidate(fork.mission, "--dry-run", strategy=None)

    _assert_refusal_is_7560(result, fork)
    _assert_clean_forecast(result)


# ---------------------------------------------------------------------------
# T004: soundness ratchets on the fork (green now, green after)
# ---------------------------------------------------------------------------


def test_ratchet_declaring_a_post_base_mission_commit_refuses(tmp_path: Path) -> None:
    """A content commit made directly on the Mission branch after the base is Mission work."""
    from specify_cli.coordination.workspace import CoordinationWorkspace

    fork = build_fork_mission(tmp_path, mid8="01M7560F")
    mission = fork.mission
    coord_wt = CoordinationWorkspace.worktree_path(mission.repo, mission.slug, mission.mid8)
    post_base = _commit_file(coord_wt, "src/pkg/direct.py", "DIRECT = 1\n", "feat: direct commit on the Mission branch")
    _git(mission.repo, "branch", "side", post_base)
    assert _is_ancestor(mission.repo, fork.base, post_base) and post_base != fork.base

    result = _consolidate(mission, "--dry-run", "--dependency-ref", "side")

    flat = _flat(result)
    assert result.returncode != 0, flat[-3000:]
    assert COVERS_MISSION_WORK in flat, flat[-3000:]
    assert post_base[:10] in flat, f"the refusal must name the post-base Mission commit {post_base[:10]}:\n{flat[-3000:]}"


def test_ratchet_smuggled_removed_wp_commit_is_unattributable(tmp_path: Path) -> None:
    """A removed WP's post-base commit riding a lane through a second-parent merge is never attributed."""
    fork = build_fork_mission(tmp_path, mid8="01M7560G")
    mission = fork.mission
    smuggled = _commit_on_new_branch(mission.repo, tmp_path, "removed-wp", mission.coord_branch, {"src/pkg/removed.py": "REMOVED = 1\n"})
    assert _is_ancestor(mission.repo, fork.base, smuggled)
    _merge_into_lane(mission, tmp_path, "removed-wp", "WP01")
    _git(mission.repo, "branch", "-D", "removed-wp")

    result = _consolidate(mission, "--dry-run")

    flat = _flat(result)
    assert result.returncode != 0, flat[-3000:]
    assert UNATTRIBUTABLE in flat, flat[-3000:]
    assert smuggled[:10] in flat, f"the refusal must name the smuggled commit {smuggled[:10]}:\n{flat[-3000:]}"


def test_ratchet_declaring_a_lane_branch_refuses(tmp_path: Path) -> None:
    fork = build_fork_mission(tmp_path, mid8="01M7560H")
    lane = fork.mission.lane_branch("WP01")

    result = _consolidate(fork.mission, "--dry-run", "--dependency-ref", lane)

    flat = _flat(result)
    assert result.returncode != 0, flat[-3000:]
    assert COVERS_MISSION_WORK in flat and "branch namespace" in flat, flat[-3000:]


# ---------------------------------------------------------------------------
# T005: non-fork control (NFR-001)
# ---------------------------------------------------------------------------


def test_control_non_fork_declared_passes_and_undeclared_refuses(tmp_path: Path) -> None:
    """The target reaches the base: the #6771 verdicts are unchanged."""
    mission = build_coord_mission(tmp_path, wps=_WPS, mid8="01M7560J")
    root = _git(mission.repo, "rev-list", "--max-parents=0", "HEAD")
    dep_tip = _commit_on_new_branch(mission.repo, tmp_path, DEP_BRANCH, root, {"src/dep/mod0.py": "DEP = 0\n", "src/dep/mod1.py": "DEP = 1\n"})
    _merge_into_lane(mission, tmp_path, DEP_BRANCH, "WP02")

    declared = _consolidate(mission, "--dry-run", "--dependency-ref", DEP_BRANCH)
    undeclared = _consolidate(mission, "--dry-run")

    _assert_clean_forecast(declared)
    assert undeclared.returncode != 0, _flat(undeclared)[-3000:]
    assert UNATTRIBUTABLE in _flat(undeclared) and dep_tip[:10] in _flat(undeclared)
