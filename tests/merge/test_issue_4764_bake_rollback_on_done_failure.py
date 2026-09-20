"""Scope: #4764 FOLD-A — orphan primary-tree bake survives a done-bookkeeping
failure (rollback-completeness gap, sibling of FOLD-F1).

Mission ``terminus-safety-invariant-01M2XFT7`` closed FOLD-F1
(``tests/merge/test_merge_rollback_resume_coherence.py::
test_post_bake_failure_on_real_primary_tree_bake_resets_target_and_stays_resume_coherent``)
for the case where a mission→target failure (``integrate_mission_into_target``)
happens AFTER a real primary-tree ``mission_number`` bake has landed directly
on ``target_branch``. This module closes the SAME defect class one call
earlier: when ``_record_merged_wps_done_for_merge`` (still inside
``_phase_bake_and_pre_target_done``, strictly BEFORE the mission→target step
even begins) raises, the ``except Exception as exc:`` handler in
``executor._phase_bake_and_pre_target_done`` called only
``_restore_and_guard_coord_coherence(run, ..., error=exc)`` and re-raised —
never checking whether a primary-tree bake had just committed directly on
``target_branch``. That orphan bake commit was left permanently stranded on
an unmerged mission's target branch.

The fix threads the SAME still-at-baseline guard
(``_target_branch_still_at_baseline``) that
``_restore_pre_target_if_at_baseline`` uses into this earlier handler, and
calls ``_revert_orphan_target_bake_commit`` when it fires.

RED before the fix: ``target_branch`` tip has advanced past the pre-merge
baseline (the orphan bake commit is still there) and the persisted
``mission_number_baked`` flag is still ``True``. GREEN after: the bake commit
is reverted (target tip == pre-merge baseline) and the flag is cleared so a
subsequent ``--resume`` re-attempts the bake.

This module duplicates the F1 primary-tree-bake fixture from
``tests/merge/test_merge_rollback_resume_coherence.py`` rather than importing
its private helpers, per that module's own "shared harness files are never
edited in place" convention (also followed by
``tests/merge/test_issue_4764_terminus_safety.py``).
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

# Import the status package before any coordination submodule (production import
# order) to avoid the known ``coordination -> transaction -> status`` cycle when a
# test module imports ``merge`` first under ``PYTHONPATH=src``.
import specify_cli.status  # noqa: F401  # import-order guard (see comment above)

from specify_cli.cli.commands.merge import _run_lane_based_merge
from specify_cli.coordination.status_service import (
    EventLogReadContract,
    read_event_log,
    wp_lane_actor_from_events,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.merge.config import MergeStrategy
from specify_cli.merge.state import load_state
from specify_cli.status import Lane, StatusEvent

pytestmark = [
    pytest.mark.integration,
    pytest.mark.git_repo,
    pytest.mark.non_sandbox,
    pytest.mark.regression,
]


MID8 = "01M4764A"
MISSION_ID = f"{MID8}000000000000004764"
MISSION_SLUG = f"foldabake-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"
WP_ID = "WP01"
LANE_ID = "lane-a"
LANE_CODE = "src/folda_bake_feature.py"

_INJECTED_DONE_FAILURE = "injected FOLD-A post-bake done-bookkeeping failure"


# ---------------------------------------------------------------------------
# Git helpers (duplicated from sibling merge test harnesses; see docstring)
# ---------------------------------------------------------------------------


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
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", branch],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _branch_tree(repo: Path, branch: str) -> str:
    """Resolve a branch's TREE object hash (content, not commit identity).

    The revert path corrects the orphan bake commit forward with ``git
    revert`` (never a hard reset — AC-B3), so a reverted tip is a NEW commit
    whose TREE matches the pre-bake tree, not the pre-bake commit SHA itself.
    """
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", f"{branch}^{{tree}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


# ---------------------------------------------------------------------------
# Primary-tree-bake fixture (mirrors the F1 shape: coordination branch cut
# BEFORE meta.json exists, so the mission-branch tree genuinely lacks it and
# ``_bake_mission_number_into_mission_branch`` falls through to the REAL
# ``_bake_mission_number_on_primary_tree`` fallback, committing on ``main``).
# ---------------------------------------------------------------------------


def _write_meta(feature_dir: Path) -> None:
    meta = {
        "mission_slug": MISSION_SLUG,
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": COORD_BRANCH,
        "purpose_tldr": "#4764 FOLD-A orphan primary-tree bake on done-bookkeeping failure",
        "purpose_context": ("a real primary-tree bake commit on target must be reverted when the LATER pre-target done-bookkeeping step fails"),
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_manifest(feature_dir: Path) -> LanesManifest:
    manifest = LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_SLUG,
        mission_branch=COORD_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=LANE_ID,
                wp_ids=(WP_ID,),
                write_scope=(LANE_CODE,),
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


def _write_wp_file(feature_dir: Path) -> None:
    (feature_dir / "tasks" / f"{WP_ID}-work.md").write_text(
        f"---\nwork_package_id: {WP_ID}\ntitle: {WP_ID} work\nagent: implementer-bot\nreview_status: approved\nreviewed_by: reviewer-renata\n---\n# {WP_ID}\n",
        encoding="utf-8",
    )


def _approved_event() -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": now_utc_iso(),
        "event_id": "01HXYZA4764000000000000001",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": MISSION_SLUG,
        "force": False,
        "from_lane": "in_review",
        "reason": None,
        "review_ref": f"review-{WP_ID}",
        "to_lane": "approved",
        "wp_id": WP_ID,
    }


def _bootstrap_primary_tree_bake_mission(repo: Path) -> Path:
    """Coord-topology mission whose meta.json/lanes.json/tasks live ONLY on
    the PRIMARY checkout (``main``) — the coordination branch is cut BEFORE
    they exist, so its tree genuinely lacks them, forcing
    ``_write_mission_number_to_branch`` to fall through to the REAL
    ``_bake_mission_number_on_primary_tree`` fallback (never mocked)."""
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    initial_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--max-parents=0", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    _git(repo, "branch", COORD_BRANCH, initial_sha)

    (feature_dir / "tasks").mkdir(parents=True)
    _write_meta(feature_dir)
    _write_manifest(feature_dir)
    _write_wp_file(feature_dir)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({MISSION_SLUG}): bootstrap primary-tree mission")

    lane_branch = f"kitty/mission-{MISSION_SLUG}-{LANE_ID}"
    _git(repo, "branch", lane_branch, COORD_BRANCH)
    _git(repo, "checkout", lane_branch)
    code_path = repo / LANE_CODE
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("def folda_bake() -> int:\n    return 4764\n", encoding="utf-8")
    _git(repo, "add", LANE_CODE)
    _git(repo, "commit", "-m", f"feat({MISSION_SLUG}): lane code for {WP_ID}")
    _git(repo, "checkout", "main")

    # Coordination branch is lifecycle-only: status.events.jsonl lives there,
    # committed AFTER the primary-tree commit above so the coord branch's
    # tree never carries meta.json/lanes.json/tasks.
    _git(repo, "checkout", COORD_BRANCH)
    coord_feature_dir = repo / "kitty-specs" / MISSION_SLUG
    coord_feature_dir.mkdir(parents=True, exist_ok=True)
    (coord_feature_dir / "status.events.jsonl").write_text(json.dumps(_approved_event(), sort_keys=True) + "\n", encoding="utf-8")
    _git(repo, "add", str(coord_feature_dir / "status.events.jsonl"))
    _git(repo, "commit", "-m", f"chore({MISSION_SLUG}): coord status events")
    _git(repo, "checkout", "main")

    CoordinationWorkspace.resolve(repo, MISSION_SLUG, MID8)
    return feature_dir


@contextlib.contextmanager
def _external_mocks() -> Iterator[dict[str, MagicMock]]:
    """Mock ONLY side effects outside git/status bookkeeping + the bake seam.

    Deliberately LEFT REAL: lane consolidation, the primary-tree bake
    (``_bake_mission_number_into_mission_branch``), and the done-bookkeeping
    call under test (``_record_merged_wps_done_for_merge`` is patched
    per-test with a ``side_effect``, never here).
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


def _committed_coord_events(repo: Path, feature_dir: Path) -> list[StatusEvent]:
    return cast(
        "list[StatusEvent]",
        read_event_log(
            EventLogReadContract.coordination_branch_ref(
                repo_root=repo,
                destination_ref=COORD_BRANCH,
                feature_dir=feature_dir,
                parser_feature_dir=feature_dir,
            )
        ),
    )


def test_done_bookkeeping_failure_after_primary_tree_bake_reverts_orphan_commit(
    tmp_path: Path,
) -> None:
    """#4764 FOLD-A: a REAL primary-tree ``mission_number`` bake lands directly
    on ``main`` (target_branch) BEFORE ``_record_merged_wps_done_for_merge``
    is even attempted. Forcing that call to raise must revert the orphan bake
    commit (target tip back at the pre-merge baseline) and clear the
    persisted ``mission_number_baked`` flag — not merely restore coordination
    coherence and re-raise, leaving the bake stranded."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _bootstrap_primary_tree_bake_mission(repo)
    pre_merge_main_tree = _branch_tree(repo, "main")

    with (
        _external_mocks(),
        patch(
            "specify_cli.merge.executor._record_merged_wps_done_for_merge",
            side_effect=RuntimeError(_INJECTED_DONE_FAILURE),
        ),
        pytest.raises(RuntimeError, match=_INJECTED_DONE_FAILURE),
    ):
        _run_lane_based_merge(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            assume_yes=True,
        )

    # (a) target_branch TREE must be back at the pre-merge baseline content --
    #     the orphan primary-tree bake commit must be reverted (its net effect
    #     undone), not stranded. Tree equality, not commit-SHA equality: the
    #     revert path corrects forward with ``git revert`` (AC-B3), so the
    #     reverted tip is a NEW commit whose tree matches the pre-bake tree.
    assert _branch_tree(repo, "main") == pre_merge_main_tree, (
        "the orphan primary-tree mission_number bake commit must be reverted when the later done-bookkeeping step fails"
    )

    # (b) primary meta.json must show NO mission_number for the un-merged
    #     mission (HEAD stays on 'main' throughout).
    persisted_meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert persisted_meta.get("mission_number") is None, "primary meta.json must not carry a mission_number for a mission that never merged"

    # (c) the persisted mission_number_baked flag must be cleared so a
    #     subsequent --resume re-attempts the bake instead of short-circuiting
    #     on a flag that no longer matches the reverted git state.
    state = load_state(repo, mission_id=MISSION_ID)
    assert state is not None, "merge state must have been created for this run"
    assert state.mission_number_baked is False, "mission_number_baked must be cleared once the orphan bake commit is reverted"

    # (d) the coordination WP must remain reviewable/resumable -- no 'done'
    #     was ever recorded on this failure path (it failed BEFORE the done
    #     write), so it must still read 'approved'.
    events = _committed_coord_events(repo, feature_dir)
    wp_state = wp_lane_actor_from_events(events, WP_ID)
    assert wp_state.lane == Lane.APPROVED, f"WP{WP_ID} must remain at 'approved' (done was never recorded) -- got lane={wp_state.lane!r}"
