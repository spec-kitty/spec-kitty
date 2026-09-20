"""Scope: #4764 — WP04 (terminus-safety-invariant-01M2XFT7), FR-008.

Coherence pin (NOT red-first — see module docstring below for why): the
post-merge backstop's durable-done reader
(``done_bookkeeping._durable_done_wps_on_coordination_ref``) must observe
the coordination ref AFTER WP02's pre-mutation rollback
(``executor._rollback_to_pre_mutation_checkpoint`` /
``_reset_coord_to_checkpoint``) has reset it — so a subsequent
``spec-kitty merge --resume`` reads committed coordination ``done`` markers
that agree with the (rolled-back) worktree bytes, never a stranded/split
``done`` marker.

**Why this module adds a pin rather than a red-first defect fix.**
``_durable_done_wps_on_coordination_ref`` (``done_bookkeeping.py:595``) holds
no cache: every call re-resolves ``resolve_placement_only(...).ref`` and
shells out ``git show <ref>:kitty-specs/<slug>/status.events.jsonl`` fresh
(``coordination/status_service.py::read_event_log`` /
``EventLogReadContract.COORDINATION_BRANCH_REF``). WP02's
``_reset_coord_to_checkpoint`` performs a **forward-reversing** ``git
revert`` directly in the coordination worktree — which, by how ``git
revert`` works, updates the coordination branch ref AND the coordination
worktree's checked-out bytes in the SAME commit/lockstep. Because the
durable-done reader has no independent cache and always re-resolves the
live ref, it structurally CANNOT observe stale post-rollback state: the very
next call after the reset reads whatever the reset left behind. There is no
seam in ``done_bookkeeping.py`` where a second, independent read/reset path
could diverge from WP02's (C-001) — so no product change was required here.
This test proves that claim empirically rather than asserting it from
static reading alone, and stands as the durable regression guard for FR-008
at the ``done_bookkeeping`` seam (WP02's own
``tests/merge/test_merge_rollback_resume_coherence.py`` proves the same
coherence one level up, through the full ``_run_lane_based_merge`` entry
point and ``wp_lane_actor_from_events`` — this module pins it specifically
at the ``_durable_done_wps_on_coordination_ref`` function WP04 owns).
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
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
from specify_cli.coordination.surface_resolver import resolve_status_surface
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.merge.config import MergeStrategy
from specify_cli.merge.done_bookkeeping import _durable_done_wps_on_coordination_ref
from specify_cli.status import Lane, StatusEvent, get_wp_lane, resolve_lane_alias

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


MID8 = "01M2WP04"
MISSION_ID = "01M2WP04000000000000004764"
MISSION_SLUG = f"done-bookkeeping-coherence-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"
WP_ID = "WP01"
LANE_ID = "lane-a"
LANE_CODE = "src/done_bookkeeping_coherence_feature.py"

_INJECTED_INTEGRATE_FAILURE = "injected WP04 post-bake integrate failure"


def _write_meta(feature_dir: Path) -> None:
    meta = {
        "mission_slug": MISSION_SLUG,
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": COORD_BRANCH,
        "purpose_tldr": "WP04 durable-done reader resume-coherence pin",
        "purpose_context": "the durable-done reader must observe WP02's rollback with no split-brain",
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
        "event_id": "01HXYZWP040000000000000001",
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


def _bootstrap_coord_mission(repo: Path) -> Path:
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    _write_meta(feature_dir)
    _write_manifest(feature_dir)
    _write_wp_file(feature_dir)
    (feature_dir / "status.events.jsonl").write_text(json.dumps(_approved_event(), sort_keys=True) + "\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({MISSION_SLUG}): bootstrap coord mission")
    _git(repo, "branch", COORD_BRANCH)
    lane_branch = f"kitty/mission-{MISSION_SLUG}-{LANE_ID}"
    _git(repo, "branch", lane_branch, COORD_BRANCH)
    _git(repo, "checkout", lane_branch)
    code_path = repo / LANE_CODE
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("def done_bookkeeping_coherence() -> int:\n    return 4764\n", encoding="utf-8")
    _git(repo, "add", LANE_CODE)
    _git(repo, "commit", "-m", f"feat({MISSION_SLUG}): lane code for {WP_ID}")
    _git(repo, "checkout", "main")
    CoordinationWorkspace.resolve(repo, MISSION_SLUG, MID8)
    return feature_dir


@contextlib.contextmanager
def _external_mocks() -> Iterator[dict[str, MagicMock]]:
    """Mock ONLY side effects outside git/status bookkeeping + the T008 seam.

    Mirrors ``test_merge_rollback_resume_coherence.py``'s ``_rb_external_mocks``
    exactly: lane consolidation, the done-bookkeeping write, and the
    coordination-checkpoint capture/reset machinery under test are left REAL.
    """
    patches = {
        "run_check": patch("specify_cli.merge.executor.run_check"),
        "sparse": patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        "preflight": patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        "review_consistency": patch("specify_cli.merge.executor._enforce_review_artifact_consistency"),
        "status_history": patch("specify_cli.merge.executor._enforce_canonical_status_history"),
        "hollow": patch("specify_cli.merge.executor._warn_or_confirm_hollow_reviews"),
        "bake": patch("specify_cli.merge.executor._bake_mission_number_into_mission_branch", return_value=None),
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
    from typing import cast

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


def _worktree_side_lane(repo: Path, mission_slug: str, wp_id: str) -> Lane:
    """Read the WP's lane off the canonical on-disk (worktree) status surface.

    Uses the exact same resolver ``_assert_merged_wps_reached_done`` uses —
    the "worktree bytes" side of the FR-008 coherence check.
    """
    surface_path = resolve_status_surface(repo, mission_slug)
    feature_dir = surface_path.parent
    raw = get_wp_lane(feature_dir, wp_id)
    return Lane(resolve_lane_alias(raw))


def _run_merge(repo: Path) -> None:
    _run_lane_based_merge(
        repo_root=repo,
        mission_slug=MISSION_SLUG,
        push=False,
        delete_branch=False,
        remove_worktree=False,
        strategy=MergeStrategy.SQUASH,
        assume_yes=True,
    )


@pytest.mark.regression
def test_durable_done_reader_matches_worktree_bytes_after_wp02_rollback(
    tmp_path: Path,
) -> None:
    """FR-008 / T013 (US3-1): after WP02's pre-mutation checkpoint reset fires
    on a post-bake integrate failure, ``_durable_done_wps_on_coordination_ref``
    (the post-merge backstop's durable read, ``done_bookkeeping.py:595``) must
    NOT report the WP as durably ``done`` — it must agree with the (rolled
    back) worktree-side canonical surface, which reports ``approved``. Neither
    side may report ``done`` while the other does not (no split-brain). A
    subsequent, unobstructed resume must then bring BOTH sides to ``done`` in
    lockstep.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _bootstrap_coord_mission(repo)

    with (
        _external_mocks(),
        patch(
            "specify_cli.lanes.merge.integrate_mission_into_target",
            side_effect=RuntimeError(_INJECTED_INTEGRATE_FAILURE),
        ),
        pytest.raises(RuntimeError, match=_INJECTED_INTEGRATE_FAILURE),
    ):
        _run_merge(repo)

    # -- post-rollback: the durable-done reader must NOT strand the WP as done --
    durable_done = _durable_done_wps_on_coordination_ref(repo_root=repo, mission_slug=MISSION_SLUG, candidate_wps=[WP_ID])
    assert WP_ID not in durable_done, (
        f"split-brain: durable-done reader reports {WP_ID} done after WP02's rollback, "
        "but the coord ref was reset — the committed marker must not outlive the reset"
    )

    # -- and it must agree with the worktree-side canonical surface (no
    #    split-brain: a 'done' marker with no corresponding worktree content,
    #    or vice versa, is exactly what FR-008 forbids) --
    worktree_lane = _worktree_side_lane(repo, MISSION_SLUG, WP_ID)
    assert worktree_lane == Lane.APPROVED, f"expected the rolled-back worktree surface to read 'approved', got {worktree_lane.value!r}"

    # -- cross-check against the raw committed coordination ref content too --
    committed_events = _committed_coord_events(repo, feature_dir)
    committed_state = wp_lane_actor_from_events(committed_events, WP_ID)
    assert committed_state.lane == Lane.APPROVED, (
        f"the committed coordination ref itself must not carry a stranded 'done' marker after rollback — got lane={committed_state.lane!r}"
    )

    # -- resume: a second, unobstructed attempt must complete, and the durable
    #    reader must now agree with BOTH the worktree surface and the raw
    #    committed ref that the WP is done --
    with _external_mocks():
        _run_merge(repo)

    resumed_durable_done = _durable_done_wps_on_coordination_ref(repo_root=repo, mission_slug=MISSION_SLUG, candidate_wps=[WP_ID])
    assert WP_ID in resumed_durable_done, "resume must reach a durably-done coordination state"

    resumed_worktree_lane = _worktree_side_lane(repo, MISSION_SLUG, WP_ID)
    assert resumed_worktree_lane == Lane.DONE, "resume must reach 'done' on the worktree-side surface too"
