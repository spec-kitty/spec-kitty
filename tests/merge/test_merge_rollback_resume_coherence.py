"""Scope: #2745 — terminus half-termination + rollback/resume coherence (WP02).

Mission ``terminus-safety-invariant-01M2XFT7`` / WP02 (FR-007, FR-008, FR-010,
FR-012, T008/T009/T010/T021). Two facets:

1. **Direct-on-target refuse-before-advance (T009, US3-3, FOLD 3).** The
   direct-on-target completion path (no lane branch — a WP implemented
   directly on the target branch, the sanctioned fallback) must refuse a
   NOT-merge-ready mission BEFORE advancing the target ref. FOLD 3 (verified
   live during planning): ``require_lanes_json`` fires BEFORE
   ``_phase_gates_and_state`` — so, absent T021's skip-lanes tolerance, a
   no-lanes mission refuses via ``MissingLanesError`` (the WRONG reason — a
   missing manifest, never the terminal-lane invariant) and
   ``_assert_mission_terminal_ready`` never runs. This test drives the
   direct-on-target mission through the ``--skip-lanes`` path (T021) so the
   flow genuinely reaches the target-advance path, and asserts the refusal
   ORIGINATES from ``_assert_mission_terminal_ready`` (names the missing WP),
   is explicitly NOT a ``MissingLanesError``, and the target ref SHA is
   provably unchanged.

   RED before T007 (precondition) + T021 (skip-lanes plumbing) exist: today
   (no ``skip_lanes`` parameter on the executor at all) a no-lanes mission
   always hard-fails with ``MissingLanesError`` regardless of readiness.
   GREEN after: the skip-lanes path reaches the real precondition.

2. **Coord-topology rollback coherence (T008, US3-1).** Forcing a
   post-consolidation-and-bake failure on a coord-topology, merge-ready
   mission must reset the coordination ref/worktree to a coherent
   pre-mutation state — committed coordination ``done`` markers stay coherent
   with the coordination worktree bytes so a subsequent ``--resume`` reads a
   consistent state. This specific narrow scenario (failure strictly AFTER
   the pre-``done`` checkpoint) was already closed by #2711
   (``tests/merge/test_issue_2711_merge_rollback_resume_coherence.py``,
   permanent guard, not red-first here) — this module's contribution is
   pinning that the SAME coherence holds when the injected failure happens
   EARLIER, during/just-after lane consolidation itself (before the #2711
   pre-``done`` checkpoint is even captured), which only the NEW T008
   pre-mutation checkpoint covers.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from kernel.clock import now_utc_iso

import specify_cli.status  # noqa: F401  # import-order guard

from specify_cli.cli.commands.merge import _run_lane_based_merge
from specify_cli.coordination.status_service import (
    EventLogReadContract,
    read_event_log,
    wp_lane_actor_from_events,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import MissingLanesError, write_lanes_json
from specify_cli.merge.config import MergeStrategy
from specify_cli.status import Lane, StatusEvent

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _branch_tip(repo: Path, branch: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), "rev-parse", branch], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


# ---------------------------------------------------------------------------
# T009/T010 (FOLD 3): direct-on-target refuse via --skip-lanes, non-vacuous
# ---------------------------------------------------------------------------

DOT_MISSION_SLUG = "terminus-dot-4764-01M2DOT7"
DOT_WP_ID = "WP01"


def _dot_write_meta(feature_dir: Path) -> None:
    """A FLAT/direct-on-target mission: NO ``coordination_branch`` — the WP was
    implemented directly on the target branch, no lane branch, no lanes.json."""
    meta = {
        "mission_slug": DOT_MISSION_SLUG,
        "mission_id": "01M2DOT7000000000000004764",
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "purpose_tldr": "#2745 direct-on-target refuse-before-advance regression",
        "purpose_context": "a not-merge-ready direct-on-target mission must refuse before advancing target",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _dot_write_wp_file(feature_dir: Path) -> None:
    (feature_dir / "tasks" / f"{DOT_WP_ID}-work.md").write_text(
        f"---\nwork_package_id: {DOT_WP_ID}\ntitle: {DOT_WP_ID} work\nagent: implementer-bot\n---\n# {DOT_WP_ID}\n",
        encoding="utf-8",
    )


def _dot_in_progress_event() -> dict[str, object]:
    return {
        "actor": "implementer-bot",
        "at": now_utc_iso(),
        "event_id": "01HXYZDOT0000000000000001",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": DOT_MISSION_SLUG,
        "force": False,
        "from_lane": "claimed",
        "reason": None,
        "review_ref": None,
        "to_lane": "in_progress",
        "wp_id": DOT_WP_ID,
    }


def _bootstrap_direct_on_target_mission(repo: Path) -> Path:
    """A direct-on-target mission: WP code committed directly on ``main``
    (the target branch), no lane branch, no ``lanes.json``, no coordination
    branch — the sanctioned fallback topology this WP's affordance targets."""
    feature_dir = repo / "kitty-specs" / DOT_MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    _dot_write_meta(feature_dir)
    _dot_write_wp_file(feature_dir)
    (feature_dir / "status.events.jsonl").write_text(json.dumps(_dot_in_progress_event(), sort_keys=True) + "\n", encoding="utf-8")
    code_path = repo / "src" / "direct_on_target_feature.py"
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("def direct_on_target() -> int:\n    return 2745\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"feat({DOT_MISSION_SLUG}): {DOT_WP_ID} committed directly on target")
    return feature_dir


@contextlib.contextmanager
def _dot_external_mocks() -> Iterator[dict[str, MagicMock]]:
    patches = {
        "run_check": patch("specify_cli.merge.executor.run_check"),
        "sparse": patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        "preflight": patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        "review_consistency": patch("specify_cli.merge.executor._enforce_review_artifact_consistency"),
        "status_history": patch("specify_cli.merge.executor._enforce_canonical_status_history"),
        "hollow": patch("specify_cli.merge.executor._warn_or_confirm_hollow_reviews"),
        "gates": patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        "policy": patch("specify_cli.policy.config.load_policy_config"),
        "remote": patch("specify_cli.merge.executor.has_remote", return_value=False),
    }
    with contextlib.ExitStack() as stack:
        mocks = {name: stack.enter_context(p) for name, p in patches.items()}
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        mocks["gates"].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = MagicMock(mode="warn")
        mocks["policy"].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        mocks["run_check"].return_value = stale_report
        yield mocks


def test_direct_on_target_refuse_originates_from_precondition_not_missing_lanes(
    tmp_path: Path,
) -> None:
    """FOLD 3 / T009/T010 (US3-3): a NOT-merge-ready direct-on-target mission,
    driven through the ``--skip-lanes`` entry point (so it genuinely reaches
    the target-advance path instead of tripping ``require_lanes_json``
    first), must be refused by ``_assert_mission_terminal_ready`` — NOT a
    ``MissingLanesError`` — with the target ref SHA provably unchanged.

    Entry point: ``_run_lane_based_merge(..., skip_lanes=True)`` — the
    executor capability behind ``spec-kitty merge --skip-lanes``.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_direct_on_target_mission(repo)
    pre_target_tip = _branch_tip(repo, "main")

    with _dot_external_mocks(), patch("specify_cli.cli.console.console.print") as mock_print, pytest.raises(BaseException) as excinfo:  # noqa: PT011
        _run_lane_based_merge(
            repo_root=repo,
            mission_slug=DOT_MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            assume_yes=True,
            skip_lanes=True,
        )

    assert not isinstance(excinfo.value, MissingLanesError), (
        "the refusal must NOT be a MissingLanesError — --skip-lanes must reach the real merge-ready precondition, not trip the manifest requirement first"
    )
    exit_code = getattr(excinfo.value, "exit_code", None)
    assert exit_code not in (0, None), f"must exit non-zero, got {excinfo.value!r}"

    printed = " ".join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
    assert DOT_WP_ID in printed, f"refusal must name the missing WP: {printed!r}"
    assert "MissingLanesError" not in printed
    assert "lanes.json" not in printed.lower()

    assert _branch_tip(repo, "main") == pre_target_tip, "the target ref must be provably unchanged — refused before any advance"


def test_direct_on_target_skip_lanes_without_lanes_json_today_raises_missing_lanes_error(
    tmp_path: Path,
) -> None:
    """Characterization: WITHOUT ``skip_lanes=True``, a no-lanes direct-on-target
    mission still hard-fails with ``MissingLanesError`` — T021's tolerance is
    opt-in via the flag, never a blanket bypass of the manifest requirement."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_direct_on_target_mission(repo)

    with _dot_external_mocks(), pytest.raises(MissingLanesError):
        _run_lane_based_merge(
            repo_root=repo,
            mission_slug=DOT_MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            assume_yes=True,
            skip_lanes=False,
        )


# ---------------------------------------------------------------------------
# T008 (US3-1): coord-topology pre-mutation checkpoint rollback coherence
# ---------------------------------------------------------------------------

RB_MID8 = "01M2RBCK"
RB_MISSION_ID = "01M2RBCK000000000000004764"
RB_MISSION_SLUG = f"merge-rollback-t008-{RB_MID8}"
RB_COORD_BRANCH = f"kitty/mission-{RB_MISSION_SLUG}"
RB_WP_ID = "WP01"
RB_LANE_ID = "lane-a"
RB_LANE_CODE = "src/rollback_t008_feature.py"

_INJECTED_CONSOLIDATION_FAILURE = "injected T008 post-consolidation failure"


def _rb_write_meta(feature_dir: Path) -> None:
    meta = {
        "mission_slug": RB_MISSION_SLUG,
        "mission_id": RB_MISSION_ID,
        "mid8": RB_MID8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": RB_COORD_BRANCH,
        "purpose_tldr": "T008 pre-mutation checkpoint rollback coherence",
        "purpose_context": "a post-consolidation failure must reset the coord ref coherently",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _rb_write_manifest(feature_dir: Path) -> LanesManifest:
    # ``mission_id`` MUST be the ULID ``RB_MISSION_ID`` (never the slug -- see
    # ``LanesManifest.mission_id``'s docstring, "ULID or None; never a slug").
    # Epic #5001 landing remediation: passing the slug here made
    # ``lane_branch_name`` derive a lane branch that never matched the real
    # one this fixture creates, so the reconciliation claim builder silently
    # resolved empty authorship for every run -- invisible before FIX C's new
    # fail-closed squash-vacuous-authorship guard, which correctly surfaces it.
    manifest = LanesManifest(
        version=1,
        mission_slug=RB_MISSION_SLUG,
        mission_id=RB_MISSION_ID,
        mission_branch=RB_COORD_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=RB_LANE_ID,
                wp_ids=(RB_WP_ID,),
                write_scope=(RB_LANE_CODE,),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=now_utc_iso(),
        computed_from="test-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    return manifest


def _rb_write_wp_file(feature_dir: Path) -> None:
    (feature_dir / "tasks" / f"{RB_WP_ID}-work.md").write_text(
        f"---\nwork_package_id: {RB_WP_ID}\ntitle: {RB_WP_ID} work\nagent: implementer-bot\n"
        "review_status: approved\nreviewed_by: reviewer-renata\n---\n"
        f"# {RB_WP_ID}\n",
        encoding="utf-8",
    )


def _rb_approved_event() -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": now_utc_iso(),
        "event_id": "01HXYZRBCK0000000000000001",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": RB_MISSION_SLUG,
        "force": False,
        "from_lane": "in_review",
        "reason": None,
        "review_ref": f"review-{RB_WP_ID}",
        "to_lane": "approved",
        "wp_id": RB_WP_ID,
    }


def _rb_bootstrap_coord_mission(repo: Path) -> Path:
    feature_dir = repo / "kitty-specs" / RB_MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    _rb_write_meta(feature_dir)
    _rb_write_manifest(feature_dir)
    _rb_write_wp_file(feature_dir)
    (feature_dir / "status.events.jsonl").write_text(json.dumps(_rb_approved_event(), sort_keys=True) + "\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({RB_MISSION_SLUG}): bootstrap coord mission")
    _git(repo, "branch", RB_COORD_BRANCH)
    lane_branch = f"kitty/mission-{RB_MISSION_SLUG}-{RB_LANE_ID}"
    _git(repo, "branch", lane_branch, RB_COORD_BRANCH)
    _git(repo, "checkout", lane_branch)
    code_path = repo / RB_LANE_CODE
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("def rollback_t008() -> int:\n    return 4764\n", encoding="utf-8")
    _git(repo, "add", RB_LANE_CODE)
    _git(repo, "commit", "-m", f"feat({RB_MISSION_SLUG}): lane code for {RB_WP_ID}")
    _git(repo, "checkout", "main")
    CoordinationWorkspace.resolve(repo, RB_MISSION_SLUG, RB_MID8)
    return feature_dir


@contextlib.contextmanager
def _rb_external_mocks(*, include_bake_mock: bool = True) -> Iterator[dict[str, MagicMock]]:
    """Mock ONLY side effects outside git/status bookkeeping + the T008 seam.

    Deliberately LEFT REAL: lane consolidation (``consolidate_lane_into_mission``),
    the done-bookkeeping write, and the coordination-checkpoint capture/reset
    machinery under test.

    ``include_bake_mock=False`` (FOLD-F1, terminus-safety-invariant-01M2XFT7):
    leaves ``_bake_mission_number_into_mission_branch`` REAL too, so a
    coord-topology mission whose meta.json is absent on the mission-branch
    tree genuinely exercises the primary-tree bake fallback
    (``_bake_mission_number_on_primary_tree``) instead of masking it —
    the default (``True``) preserves every pre-existing caller's behavior
    unchanged.
    """
    patches = {
        "run_check": patch("specify_cli.merge.executor.run_check"),
        "sparse": patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        "preflight": patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        "review_consistency": patch("specify_cli.merge.executor._enforce_review_artifact_consistency"),
        "status_history": patch("specify_cli.merge.executor._enforce_canonical_status_history"),
        "hollow": patch("specify_cli.merge.executor._warn_or_confirm_hollow_reviews"),
        "gates": patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        "policy": patch("specify_cli.policy.config.load_policy_config"),
        "remote": patch("specify_cli.merge.executor.has_remote", return_value=False),
    }
    if include_bake_mock:
        patches["bake"] = patch("specify_cli.merge.executor._bake_mission_number_into_mission_branch", return_value=None)
    with contextlib.ExitStack() as stack:
        mocks = {name: stack.enter_context(p) for name, p in patches.items()}
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        mocks["gates"].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = MagicMock(mode="warn")
        mocks["policy"].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        mocks["run_check"].return_value = stale_report
        yield mocks


def _rb_committed_coord_events(repo: Path, feature_dir: Path) -> list[StatusEvent]:
    return cast(
        "list[StatusEvent]",
        read_event_log(
            EventLogReadContract.coordination_branch_ref(
                repo_root=repo,
                destination_ref=RB_COORD_BRANCH,
                feature_dir=feature_dir,
                parser_feature_dir=feature_dir,
            )
        ),
    )


def test_post_consolidation_failure_resets_coord_ref_and_stays_resume_coherent(
    tmp_path: Path,
) -> None:
    """T008 (FR-007/008, US3-1): force a failure right after lane consolidation
    + the pre-target ``done`` write (``integrate_mission_into_target`` — the
    mission→target step) on a merge-ready coord-topology mission. The
    coordination ref must reset to its pre-mutation checkpoint (consolidation
    + the done write undone), the WP must remain reviewable (its committed
    lane is back to ``approved``, not stranded at ``done``), and a subsequent
    ``--resume`` must read a coherent state (no split-brain)."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _rb_bootstrap_coord_mission(repo)
    _branch_tip(repo, RB_COORD_BRANCH)

    with (
        _rb_external_mocks(),
        patch(
            "specify_cli.lanes.merge.integrate_mission_into_target",
            side_effect=RuntimeError(_INJECTED_CONSOLIDATION_FAILURE),
        ),
        pytest.raises(RuntimeError, match=_INJECTED_CONSOLIDATION_FAILURE),
    ):
        _run_lane_based_merge(
            repo_root=repo,
            mission_slug=RB_MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            assume_yes=True,
        )

    # -- coherence: the committed coordination ref reads back a WP state that
    #    matches the (rolled-back) working tree — never a stranded ``done`` --
    events = _rb_committed_coord_events(repo, feature_dir)
    wp_state = wp_lane_actor_from_events(events, RB_WP_ID)
    assert wp_state.lane in (Lane.APPROVED,), f"the committed coordination reduction must not strand 'done' after rollback — got lane={wp_state.lane!r}"

    # -- resume: a second attempt (now merge-ready and un-obstructed) must
    #    complete cleanly, reading a coherent pre-mutation state, not raise on
    #    a stranded/duplicate 'done' or a split-brain coordination reduction --
    with _rb_external_mocks():
        _run_lane_based_merge(
            repo_root=repo,
            mission_slug=RB_MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            assume_yes=True,
        )
    resumed_events = _rb_committed_coord_events(repo, feature_dir)
    resumed_state = wp_lane_actor_from_events(resumed_events, RB_WP_ID)
    assert resumed_state.lane == Lane.DONE, "resume must complete the merge cleanly"


# ---------------------------------------------------------------------------
# Pre-PR adversarial-squad FINDING 1 (HIGH) — a REAL primary-tree bake commit
# defeats the T008 pre-target rollback baseline guard
# ---------------------------------------------------------------------------
#
# T008 above proves rollback coherence when the bake writes to the MISSION
# branch (the common case — meta.json present on that branch's tree, exactly
# what ``_rb_bootstrap_coord_mission`` sets up by branching COORD_BRANCH from
# the SAME commit that already carries meta.json). Finding 1 is the DEEPER,
# genuinely-083+ shape (mirrors ``test_issue_4474_topology_aware_bake.py``'s
# Case 1): the coordination branch is cut BEFORE meta.json exists, so its
# tree genuinely lacks it, forcing ``_write_mission_number_to_branch`` to
# fall through to ``_bake_mission_number_on_primary_tree`` — which commits
# directly on ``main_repo``'s own checkout (``main``, the target branch; the
# main repo's checkout never leaves it during a merge). Pre-fix, that commit
# silently advances ``main`` past ``run.target_baseline_sha`` (captured
# BEFORE the bake), so ``_target_branch_still_at_baseline`` sees `main` has
# "moved" and the ENTIRE ``_restore_pre_target_if_at_baseline`` rollback
# block is skipped: no coord ``done`` revert, no mission_number un-bake, an
# orphaned ``chore(...): assign mission_number=N (primary tree)`` commit
# stranded on ``main`` for a mission that never merged — the #4764/#4474
# split-brain this mission exists to close (US3-1, SC-003).

F1_MID8 = "01M2F1CK"
F1_MISSION_ID = "01M2F1CK00000000000004764"
F1_MISSION_SLUG = f"merge-primarybake-f1-{F1_MID8}"
F1_COORD_BRANCH = f"kitty/mission-{F1_MISSION_SLUG}"
F1_WP_ID = "WP01"
F1_LANE_ID = "lane-a"
F1_LANE_CODE = "src/primarybake_f1_feature.py"

_INJECTED_F1_FAILURE = "injected FOLD-F1 post-bake mission-to-target failure"


def _f1_write_meta(feature_dir: Path) -> None:
    meta = {
        "mission_slug": F1_MISSION_SLUG,
        "mission_id": F1_MISSION_ID,
        "mid8": F1_MID8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": F1_COORD_BRANCH,
        "purpose_tldr": "FOLD-F1 primary-tree bake defeats pre-target rollback guard",
        "purpose_context": ("a real primary-tree bake commit on target must not defeat the pre-target rollback baseline guard"),
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _f1_write_manifest(feature_dir: Path) -> LanesManifest:
    # ``mission_id`` MUST be the ULID ``F1_MISSION_ID`` (never the slug -- see
    # ``LanesManifest.mission_id``'s docstring, "ULID or None; never a slug").
    # Epic #5001 landing remediation: passing the slug here made
    # ``lane_branch_name`` derive a lane branch that never matched the real
    # one this fixture creates, so the reconciliation claim builder silently
    # resolved empty authorship for every run -- invisible before FIX C's new
    # fail-closed squash-vacuous-authorship guard, which correctly surfaces it.
    manifest = LanesManifest(
        version=1,
        mission_slug=F1_MISSION_SLUG,
        mission_id=F1_MISSION_ID,
        mission_branch=F1_COORD_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=F1_LANE_ID,
                wp_ids=(F1_WP_ID,),
                write_scope=(F1_LANE_CODE,),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=now_utc_iso(),
        computed_from="test-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    return manifest


def _f1_write_wp_file(feature_dir: Path) -> None:
    (feature_dir / "tasks" / f"{F1_WP_ID}-work.md").write_text(
        f"---\nwork_package_id: {F1_WP_ID}\ntitle: {F1_WP_ID} work\nagent: implementer-bot\n"
        "review_status: approved\nreviewed_by: reviewer-renata\n---\n"
        f"# {F1_WP_ID}\n",
        encoding="utf-8",
    )


def _f1_approved_event() -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": now_utc_iso(),
        "event_id": "01HXYZF1CK0000000000000001",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": F1_MISSION_SLUG,
        "force": False,
        "from_lane": "in_review",
        "reason": None,
        "review_ref": f"review-{F1_WP_ID}",
        "to_lane": "approved",
        "wp_id": F1_WP_ID,
    }


def _f1_bootstrap_primary_tree_bake_mission(repo: Path) -> Path:
    """#4764 FOLD-F1: a coord-topology mission whose meta.json/lanes.json/tasks
    live ONLY on the PRIMARY checkout (``main``) — the coordination branch is
    cut BEFORE they exist, so its tree genuinely lacks them (mirrors
    ``test_issue_4474_topology_aware_bake.py``'s Case-1 shape), forcing
    ``_write_mission_number_to_branch`` to fall through to the REAL
    ``_bake_mission_number_on_primary_tree`` fallback — never mocked out."""
    feature_dir = repo / "kitty-specs" / F1_MISSION_SLUG
    initial_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--max-parents=0", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    # Coordination branch cut BEFORE meta.json/lanes.json/tasks exist -- its
    # tree genuinely lacks the PRIMARY-partition artifacts (the real #4474
    # shape: coord = lifecycle surfaces only).
    _git(repo, "branch", F1_COORD_BRANCH, initial_sha)

    (feature_dir / "tasks").mkdir(parents=True)
    _f1_write_meta(feature_dir)
    _f1_write_manifest(feature_dir)
    _f1_write_wp_file(feature_dir)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({F1_MISSION_SLUG}): bootstrap primary-tree mission")

    lane_branch = f"kitty/mission-{F1_MISSION_SLUG}-{F1_LANE_ID}"
    _git(repo, "branch", lane_branch, F1_COORD_BRANCH)
    _git(repo, "checkout", lane_branch)
    code_path = repo / F1_LANE_CODE
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("def primarybake_f1() -> int:\n    return 4764\n", encoding="utf-8")
    _git(repo, "add", F1_LANE_CODE)
    _git(repo, "commit", "-m", f"feat({F1_MISSION_SLUG}): lane code for {F1_WP_ID}")
    _git(repo, "checkout", "main")

    # The coordination branch is lifecycle-only: status.events.jsonl lives
    # there, committed AFTER the primary-tree commit above so the coord
    # branch's tree never carries meta.json/lanes.json/tasks.
    _git(repo, "checkout", F1_COORD_BRANCH)
    coord_feature_dir = repo / "kitty-specs" / F1_MISSION_SLUG
    coord_feature_dir.mkdir(parents=True, exist_ok=True)
    (coord_feature_dir / "status.events.jsonl").write_text(json.dumps(_f1_approved_event(), sort_keys=True) + "\n", encoding="utf-8")
    _git(repo, "add", str(coord_feature_dir / "status.events.jsonl"))
    _git(repo, "commit", "-m", f"chore({F1_MISSION_SLUG}): coord status events")
    _git(repo, "checkout", "main")

    CoordinationWorkspace.resolve(repo, F1_MISSION_SLUG, F1_MID8)
    return feature_dir


def _f1_committed_coord_events(repo: Path, feature_dir: Path) -> list[StatusEvent]:
    return cast(
        "list[StatusEvent]",
        read_event_log(
            EventLogReadContract.coordination_branch_ref(
                repo_root=repo,
                destination_ref=F1_COORD_BRANCH,
                feature_dir=feature_dir,
                parser_feature_dir=feature_dir,
            )
        ),
    )


def test_post_bake_failure_on_real_primary_tree_bake_resets_target_and_stays_resume_coherent(
    tmp_path: Path,
) -> None:
    """FOLD-F1 (HIGH, C-ROLLBACK/US3-1): a REAL primary-tree mission_number
    bake (meta.json absent on the mission-branch tree, present only on the
    primary checkout) commits directly onto ``main``. Forcing a
    mission→target failure AFTER that bake must not defeat
    ``_restore_pre_target_if_at_baseline``'s baseline guard — the rollback
    must undo consolidation, the coordination ``done`` write, AND the orphan
    bake commit together, and a subsequent ``--resume`` must read a coherent
    state."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _f1_bootstrap_primary_tree_bake_mission(repo)
    pre_merge_main_tip = _branch_tip(repo, "main")

    with (
        _rb_external_mocks(include_bake_mock=False),
        patch(
            "specify_cli.lanes.merge.integrate_mission_into_target",
            side_effect=RuntimeError(_INJECTED_F1_FAILURE),
        ),
        pytest.raises(RuntimeError, match=_INJECTED_F1_FAILURE),
    ):
        _run_lane_based_merge(
            repo_root=repo,
            mission_slug=F1_MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            assume_yes=True,
        )

    # (a) the coord WP must not be stranded at 'done' -- rolled back to 'approved'.
    events = _f1_committed_coord_events(repo, feature_dir)
    wp_state = wp_lane_actor_from_events(events, F1_WP_ID)
    assert wp_state.lane in (Lane.APPROVED,), f"the committed coordination reduction must not strand 'done' after rollback -- got lane={wp_state.lane!r}"

    # (b)/(c) primary meta.json must show NO mission_number for the un-merged
    #     mission -- the orphan bake commit's effect must be undone, not just
    #     halted. (HEAD is on 'main' throughout, so reading off disk reads the
    #     post-rollback committed state.)
    persisted_meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert persisted_meta.get("mission_number") is None, "primary meta.json must not carry a mission_number for a mission that never merged"

    # (d) a subsequent --resume must read a coherent state and complete
    #     cleanly -- no split-brain between committed coordination 'done'
    #     markers and worktree bytes, and mission_number gets (re-)baked
    #     exactly once on the successful resume.
    with _rb_external_mocks(include_bake_mock=False):
        _run_lane_based_merge(
            repo_root=repo,
            mission_slug=F1_MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            assume_yes=True,
        )
    resumed_events = _f1_committed_coord_events(repo, feature_dir)
    resumed_state = wp_lane_actor_from_events(resumed_events, F1_WP_ID)
    assert resumed_state.lane == Lane.DONE, "resume must complete the merge cleanly"
    resumed_meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert resumed_meta.get("mission_number") == 1, "the resumed merge must (re-)bake mission_number exactly once"
    assert _branch_tip(repo, "main") != pre_merge_main_tip, "the resume must genuinely advance main past the ORIGINAL pre-merge baseline"
