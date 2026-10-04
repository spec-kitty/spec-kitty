"""Unit coverage for ``specify_cli.lanes.claim_base`` (WP02/T007).

The claim-base ref (``refs/spec-kitty/wp-base/<mission_slug>/<wp_id>``) is a
repo-root lane's ``for_review`` starting point -- see
``contracts/single-branch-execution.md``, "Claim base and for_review".
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.claim_base import (
    _claim_base_ref,
    _clear_claim_base,
    on_wp_terminal,
    read_claim_base,
    record_claim_base,
)

pytestmark = [pytest.mark.fast, pytest.mark.git_repo]

_MISSION_SLUG = "claim-base-01KZZTEST"
_WP_ID = "WP01"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")


def test_claim_base_ref_name_is_the_documented_contract() -> None:
    assert _claim_base_ref("my-mission", "WP07") == "refs/spec-kitty/wp-base/my-mission/WP07"


def test_read_claim_base_returns_none_when_absent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    assert read_claim_base(repo, _MISSION_SLUG, _WP_ID) is None


def test_record_then_read_round_trips_the_head_sha(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    head = _git(repo, "rev-parse", "HEAD")

    recorded = record_claim_base(repo, repo, _MISSION_SLUG, _WP_ID)

    assert recorded == head
    assert read_claim_base(repo, _MISSION_SLUG, _WP_ID) == head
    # The ref is a real, independently resolvable git ref.
    assert _git(repo, "rev-parse", "--verify", _claim_base_ref(_MISSION_SLUG, _WP_ID)) == head


def test_record_is_idempotent_by_absence_a_second_record_does_not_move_the_ref(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    first_sha = record_claim_base(repo, repo, _MISSION_SLUG, _WP_ID)

    # Advance HEAD -- a naive re-record would move the ref forward, which
    # would silently shrink the for_review gate's `base..HEAD` window on a
    # resumed claim.
    (repo / "more.txt").write_text("more\n", encoding="utf-8")
    _git(repo, "add", "more.txt")
    _git(repo, "commit", "-q", "-m", "second commit")

    second_sha = record_claim_base(repo, repo, _MISSION_SLUG, _WP_ID)

    assert second_sha == first_sha
    assert read_claim_base(repo, _MISSION_SLUG, _WP_ID) == first_sha


def test_record_reads_head_from_write_checkout_not_repo_root(tmp_path: Path) -> None:
    """``record_claim_base`` records *write_checkout*'s HEAD -- distinct from
    *repo_root* when the two differ (a lane worktree, for example).

    ``other_checkout`` is a REAL linked worktree of ``repo`` (review-feedback-
    2.md Issue 1) -- not a second, independent repository. Two independent
    ``_init_repo`` calls only diverge when their seed commits land in
    different wall-clock seconds (same tree/author/message otherwise
    produces the identical SHA), which made the prior shape of this test
    pass or fail on wall-clock timing: ``update-ref`` in *repo* rejected a
    SHA from a foreign object database it had never seen, exit 128. A linked
    worktree shares ``repo``'s object database and ref store (refs live in
    the common dir -- the same reason ``record_claim_base`` targets
    *write_checkout*'s HEAD in the first place, mirroring the real lane-
    worktree production shape), and the extra commit below makes the two
    HEADs differ deterministically, with no timing dependency.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    repo_head = _git(repo, "rev-parse", "HEAD")

    other_checkout = tmp_path / "other"
    _git(repo, "worktree", "add", "-q", "-b", "other-branch", str(other_checkout))
    (other_checkout / "extra.txt").write_text("extra\n", encoding="utf-8")
    _git(other_checkout, "add", "extra.txt")
    _git(other_checkout, "commit", "-q", "-m", "extra commit that exists only in the worktree")
    other_head = _git(other_checkout, "rev-parse", "HEAD")
    assert other_head != repo_head

    recorded = record_claim_base(repo, other_checkout, _MISSION_SLUG, _WP_ID)

    assert recorded == other_head
    assert read_claim_base(repo, _MISSION_SLUG, _WP_ID) == other_head


def test_clear_removes_the_ref(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    record_claim_base(repo, repo, _MISSION_SLUG, _WP_ID)
    assert read_claim_base(repo, _MISSION_SLUG, _WP_ID) is not None

    _clear_claim_base(repo, _MISSION_SLUG, _WP_ID)

    assert read_claim_base(repo, _MISSION_SLUG, _WP_ID) is None


def test_clear_is_a_no_op_when_the_ref_was_never_recorded(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    _clear_claim_base(repo, _MISSION_SLUG, _WP_ID)  # must not raise

    assert read_claim_base(repo, _MISSION_SLUG, _WP_ID) is None


def test_on_wp_terminal_clears_the_claim_base_ref(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    record_claim_base(repo, repo, _MISSION_SLUG, _WP_ID)
    assert read_claim_base(repo, _MISSION_SLUG, _WP_ID) is not None

    on_wp_terminal(repo, _MISSION_SLUG, _WP_ID)

    assert read_claim_base(repo, _MISSION_SLUG, _WP_ID) is None


def test_ref_is_scoped_per_mission_and_wp(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    record_claim_base(repo, repo, "mission-a", "WP01")

    assert read_claim_base(repo, "mission-a", "WP02") is None
    assert read_claim_base(repo, "mission-b", "WP01") is None


# ---------------------------------------------------------------------------
# Production wiring (WP02 review cycle 1, Issue 1): drive the REAL seams --
# implement_support.create_lane_workspace, orchestrator_api._resolve_start_
# workspace / _resolve_existing_workspace, coordination.status_transition's
# terminal hook (both the primary-fallback and transactional arms) -- so
# deleting any of those production call sites fails one of these tests
# (mutation-checked; see the fix commit for the delete/restore evidence).
# ---------------------------------------------------------------------------


def _planning_lane_legacy_repo(tmp_path: Path) -> Path:
    """A legacy (no coordination_branch) mission whose WP02 is the planning
    lane -- reuses the established test_claim_ancestry_gate.py fixture
    shape, converting lane-b (WP02) to PLANNING_LANE_ID."""
    import json

    from tests.specify_cli.cli.commands.agent.test_claim_ancestry_gate import (
        _MISSION_SLUG as _ANCESTRY_MISSION_SLUG,
        _WP_DEP,
        _WP_SELF,
        _feature_dir,
        _init_repo as _init_ancestry_repo,
        _write_meta_and_lanes,
    )
    from specify_cli.lanes.compute import PLANNING_LANE_ID
    from tests.utils import write_wp

    repo = tmp_path / "repo"
    _init_ancestry_repo(repo)
    _write_meta_and_lanes(repo)
    lanes_path = _feature_dir(repo) / "lanes.json"
    payload = json.loads(lanes_path.read_text(encoding="utf-8"))
    payload["lanes"][1]["lane_id"] = PLANNING_LANE_ID
    lanes_path.write_text(json.dumps(payload), encoding="utf-8")
    write_wp(repo, _ANCESTRY_MISSION_SLUG, "planned", _WP_DEP, seed_canonical=False)
    write_wp(repo, _ANCESTRY_MISSION_SLUG, "planned", _WP_SELF, seed_canonical=False)
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "convert WP02 to the planning lane")
    return repo


def test_create_lane_workspace_records_claim_base_for_planning_wp(tmp_path: Path) -> None:
    """(a) implement_support.create_lane_workspace's planning arm records
    the claim base at write-checkout HEAD; a resumed call does not move it."""
    from tests.specify_cli.cli.commands.agent.test_claim_ancestry_gate import (
        _MISSION_SLUG as _ANCESTRY_MISSION_SLUG,
        _WP_SELF,
        _feature_dir,
    )
    from specify_cli.lanes.compute import PLANNING_LANE_ID
    from specify_cli.lanes.implement_support import create_lane_workspace
    from specify_cli.lanes.persistence import read_lanes_json
    from specify_cli.workspace.context import ResolvedWorkspace

    repo = _planning_lane_legacy_repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    manifest = read_lanes_json(_feature_dir(repo))
    workspace = ResolvedWorkspace(
        mission_slug=_ANCESTRY_MISSION_SLUG,
        wp_id=_WP_SELF,
        execution_mode="planning_artifact",
        mode_source="explicit",
        resolution_kind="repo_root",
        workspace_name=f"{_ANCESTRY_MISSION_SLUG}-{PLANNING_LANE_ID}",
        worktree_path=repo,
        branch_name=None,
        lane_id=PLANNING_LANE_ID,
        lane_wp_ids=[_WP_SELF],
        context=None,
    )
    wp_file = _feature_dir(repo) / "tasks" / f"{_WP_SELF}.md"

    result = create_lane_workspace(repo, _ANCESTRY_MISSION_SLUG, _WP_SELF, wp_file, workspace, manifest, [], "git")

    assert result.workspace_path == repo
    assert read_claim_base(repo, _ANCESTRY_MISSION_SLUG, _WP_SELF) == head

    # Resumed call (a re-invoked implement on an in_progress WP): HEAD moves,
    # the recorded claim base must NOT.
    (repo / "resume.txt").write_text("resume\n", encoding="utf-8")
    _git(repo, "add", "resume.txt")
    _git(repo, "commit", "-q", "-m", "advance HEAD before the resumed call")

    create_lane_workspace(repo, _ANCESTRY_MISSION_SLUG, _WP_SELF, wp_file, workspace, manifest, [], "git")

    assert read_claim_base(repo, _ANCESTRY_MISSION_SLUG, _WP_SELF) == head


def test_orchestrator_resolve_start_workspace_records_claim_base_for_planning_lane(tmp_path: Path) -> None:
    """(b) orchestrator_api._resolve_start_workspace's repo-root arm returns
    workspace_path == repo_root and records the claim base."""
    from tests.specify_cli.cli.commands.agent.test_claim_ancestry_gate import (
        _MISSION_SLUG as _ANCESTRY_MISSION_SLUG,
        _WP_SELF,
        _feature_dir,
    )
    from specify_cli.orchestrator_api.wp_lifecycle import _resolve_start_workspace

    repo = _planning_lane_legacy_repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")

    start_ws = _resolve_start_workspace("start-implementation", repo, _ANCESTRY_MISSION_SLUG, _feature_dir(repo), _WP_SELF)

    assert start_ws.workspace_path == str(repo)
    assert read_claim_base(repo, _ANCESTRY_MISSION_SLUG, _WP_SELF) == head


def test_orchestrator_resolve_existing_workspace_does_not_record_claim_base(tmp_path: Path) -> None:
    """(b) the read-only companion never writes the claim-base ref."""
    from tests.specify_cli.cli.commands.agent.test_claim_ancestry_gate import (
        _MISSION_SLUG as _ANCESTRY_MISSION_SLUG,
        _WP_SELF,
    )
    from specify_cli.orchestrator_api.wp_lifecycle import _resolve_existing_workspace

    repo = _planning_lane_legacy_repo(tmp_path)

    existing_ws = _resolve_existing_workspace(repo, _ANCESTRY_MISSION_SLUG, _WP_SELF)

    assert existing_ws.workspace_path == str(repo)
    assert read_claim_base(repo, _ANCESTRY_MISSION_SLUG, _WP_SELF) is None


# --- (c) terminal transitions clear the ref; non-terminal ones leave it ---

_TXN_MISSION_SLUG = "claim-base-txn"
_TXN_MID8 = "01KZZCTXN"
_TXN_MISSION_ID = "01KZZCTXN00000000000000000"
_TXN_MISSION_DIRNAME = f"{_TXN_MISSION_SLUG}-{_TXN_MID8}"
_TXN_COORD_BRANCH = f"kitty/mission-{_TXN_MISSION_DIRNAME}"
_TXN_WP_ID = "WP01"


def _coord_repo_for_transaction(tmp_path: Path) -> Path:
    """A coord-topology mission -- ``coordination_branch`` is set, so
    ``emit_status_transition_transactional`` takes the TRANSACTIONAL arm
    (``_transaction_topology_available`` returns True)."""
    import json

    from tests.utils import write_wp

    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / _TXN_MISSION_DIRNAME
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _TXN_MISSION_SLUG,
                "mission_id": _TXN_MISSION_ID,
                "mid8": _TXN_MID8,
                "coordination_branch": _TXN_COORD_BRANCH,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    write_wp(repo, _TXN_MISSION_DIRNAME, "planned", _TXN_WP_ID, seed_canonical=False)
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed mission")
    _git(repo, "branch", _TXN_COORD_BRANCH)
    return repo


def _seed_genesis_to_planned_on_coord(repo: Path) -> None:
    from specify_cli.coordination.status_service import EventLogWriteContract, append_event_log
    from specify_cli.status.models import Lane, StatusEvent

    seed_event = StatusEvent(
        event_id="01SEEDGENESIS0000000000001",
        mission_slug=_TXN_MISSION_SLUG,
        mission_id=_TXN_MISSION_ID,
        wp_id=_TXN_WP_ID,
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-05-31T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )
    worktree = repo / ".worktrees" / "seed-genesis"
    _git(repo, "worktree", "add", "-q", str(worktree), _TXN_COORD_BRANCH)
    coord_feature_dir = worktree / "kitty-specs" / _TXN_MISSION_DIRNAME
    append_event_log(
        EventLogWriteContract.coordination_transaction_append(coord_feature_dir),
        seed_event,
    )
    _git(worktree, "add", "kitty-specs")
    _git(worktree, "commit", "-q", "-m", "seed genesis->planned")
    _git(repo, "worktree", "remove", "-f", str(worktree))


def _approval_evidence() -> dict[str, dict[str, str]]:
    """The raw-dict evidence shape ``_build_done_evidence`` requires for an
    approved/done transition (``review.reviewer`` / ``.verdict`` / ``.reference``)."""
    return {"review": {"reviewer": "claim-base-wiring-reviewer", "verdict": "approved", "reference": "claim-base-wiring-test"}}


def _txn_transition(repo: Path, to_lane: str, *, force: bool = False) -> None:
    from specify_cli.coordination.status_transition import emit_status_transition_transactional
    from specify_cli.status.models import TransitionRequest

    emit_status_transition_transactional(
        TransitionRequest(
            feature_dir=repo / "kitty-specs" / _TXN_MISSION_DIRNAME,
            mission_slug=_TXN_MISSION_SLUG,
            wp_id=_TXN_WP_ID,
            to_lane=to_lane,
            actor="claim-base-wiring-test",
            repo_root=repo,
            force=force,
            reason="claim-base wiring test" if force else None,
            evidence=_approval_evidence() if to_lane in ("approved", "done") else None,
        ),
    )


def test_transactional_arm_done_transition_clears_claim_base(tmp_path: Path) -> None:
    """(c) the transactional arm's terminal hook clears the ref on ``done``;
    a non-terminal transition (``blocked``) along the way leaves it."""
    repo = _coord_repo_for_transaction(tmp_path)
    _seed_genesis_to_planned_on_coord(repo)
    record_claim_base(repo, repo, _TXN_MISSION_SLUG, _TXN_WP_ID)
    assert read_claim_base(repo, _TXN_MISSION_SLUG, _TXN_WP_ID) is not None

    _txn_transition(repo, "claimed")
    _txn_transition(repo, "in_progress")
    assert read_claim_base(repo, _TXN_MISSION_SLUG, _TXN_WP_ID) is not None

    _txn_transition(repo, "blocked")
    assert read_claim_base(repo, _TXN_MISSION_SLUG, _TXN_WP_ID) is not None, "a non-terminal transition must not clear the claim base"

    _txn_transition(repo, "in_progress")
    _txn_transition(repo, "approved")
    _txn_transition(repo, "done")

    assert read_claim_base(repo, _TXN_MISSION_SLUG, _TXN_WP_ID) is None


def test_transactional_arm_canceled_transition_clears_claim_base(tmp_path: Path) -> None:
    """(c) the transactional arm's terminal hook also clears the ref on
    ``canceled``."""
    repo = _coord_repo_for_transaction(tmp_path)
    _seed_genesis_to_planned_on_coord(repo)
    record_claim_base(repo, repo, _TXN_MISSION_SLUG, _TXN_WP_ID)

    _txn_transition(repo, "claimed")
    _txn_transition(repo, "in_progress")
    _txn_transition(repo, "canceled")

    assert read_claim_base(repo, _TXN_MISSION_SLUG, _TXN_WP_ID) is None


def _primary_fallback_transition(repo: Path, feature_dir: Path, mission_slug: str, wp_id: str, to_lane: str, *, force: bool = False) -> None:
    from specify_cli.coordination.status_transition import emit_status_transition_transactional
    from specify_cli.status.models import TransitionRequest

    emit_status_transition_transactional(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane=to_lane,
            actor="claim-base-wiring-test",
            repo_root=repo,
            force=force,
            reason="claim-base wiring test" if force else None,
            evidence=_approval_evidence() if to_lane in ("approved", "done") else None,
        ),
    )


def test_primary_fallback_arm_done_transition_clears_claim_base(tmp_path: Path) -> None:
    """(c) a legacy (no coordination_branch) mission's transition takes the
    PRIMARY-FALLBACK arm (_transaction_topology_available is False there);
    its terminal hook must clear the ref too."""
    from tests.specify_cli.cli.commands.agent.test_claim_ancestry_gate import (
        _MISSION_SLUG as _ANCESTRY_MISSION_SLUG,
        _WP_DEP,
        _feature_dir,
        _write_meta_and_lanes,
    )
    from tests.utils import write_wp

    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_meta_and_lanes(repo)
    write_wp(repo, _ANCESTRY_MISSION_SLUG, "planned", _WP_DEP, seed_canonical=False)
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed WP01 task file")
    feature_dir = _feature_dir(repo)

    record_claim_base(repo, repo, _ANCESTRY_MISSION_SLUG, _WP_DEP)

    _primary_fallback_transition(repo, feature_dir, _ANCESTRY_MISSION_SLUG, _WP_DEP, "planned")
    _primary_fallback_transition(repo, feature_dir, _ANCESTRY_MISSION_SLUG, _WP_DEP, "claimed")
    _primary_fallback_transition(repo, feature_dir, _ANCESTRY_MISSION_SLUG, _WP_DEP, "in_progress")
    assert read_claim_base(repo, _ANCESTRY_MISSION_SLUG, _WP_DEP) is not None

    _primary_fallback_transition(repo, feature_dir, _ANCESTRY_MISSION_SLUG, _WP_DEP, "blocked")
    assert read_claim_base(repo, _ANCESTRY_MISSION_SLUG, _WP_DEP) is not None, "a non-terminal transition must not clear the claim base"

    _primary_fallback_transition(repo, feature_dir, _ANCESTRY_MISSION_SLUG, _WP_DEP, "in_progress")
    _primary_fallback_transition(repo, feature_dir, _ANCESTRY_MISSION_SLUG, _WP_DEP, "approved")
    _primary_fallback_transition(repo, feature_dir, _ANCESTRY_MISSION_SLUG, _WP_DEP, "done")

    assert read_claim_base(repo, _ANCESTRY_MISSION_SLUG, _WP_DEP) is None


def test_primary_fallback_arm_canceled_transition_clears_claim_base(tmp_path: Path) -> None:
    """(c) review-feedback-2.md Nit 2: the primary-fallback arm's terminal
    hook also clears the ref on ``canceled``, not just ``done``."""
    from tests.specify_cli.cli.commands.agent.test_claim_ancestry_gate import (
        _MISSION_SLUG as _ANCESTRY_MISSION_SLUG,
        _WP_DEP,
        _feature_dir,
        _write_meta_and_lanes,
    )
    from tests.utils import write_wp

    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_meta_and_lanes(repo)
    write_wp(repo, _ANCESTRY_MISSION_SLUG, "planned", _WP_DEP, seed_canonical=False)
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed WP01 task file")
    feature_dir = _feature_dir(repo)

    record_claim_base(repo, repo, _ANCESTRY_MISSION_SLUG, _WP_DEP)

    _primary_fallback_transition(repo, feature_dir, _ANCESTRY_MISSION_SLUG, _WP_DEP, "planned")
    _primary_fallback_transition(repo, feature_dir, _ANCESTRY_MISSION_SLUG, _WP_DEP, "claimed")
    _primary_fallback_transition(repo, feature_dir, _ANCESTRY_MISSION_SLUG, _WP_DEP, "in_progress")
    assert read_claim_base(repo, _ANCESTRY_MISSION_SLUG, _WP_DEP) is not None

    _primary_fallback_transition(repo, feature_dir, _ANCESTRY_MISSION_SLUG, _WP_DEP, "canceled")

    assert read_claim_base(repo, _ANCESTRY_MISSION_SLUG, _WP_DEP) is None


# --- (c continued) coord-fallback arm (status_transition.py ~577, inside
# _fallback_emit_single._coord) -- review-feedback-2.md Nit 2 ---
#
# This arm is UNREACHABLE from any self-consistent production meta.json via
# emit_status_transition_transactional's own routing:
# _transaction_topology_available returns True unconditionally the instant
# `coordination_branch` is set (a real git repo always satisfies its OTHER
# guard, `_repo_supports_transactions`), so the transactional arm is always
# taken once a mission is coord-shaped in the ONLY way status_transition.py's
# own identity resolution reads it. Two routing decisions are therefore
# patched to reach this arm at all, each independently confirmed necessary
# by reproducing its failure first:
#
# 1. `_transaction_topology_available` -> forced False, so
#    `emit_status_transition_transactional` takes `_fallback_emit_single`
#    instead of the transactional door.
# 2. `mission_runtime.resolve_placement_only` -> forced to the coord branch
#    for the STATUS_STATE kind. This test's minimal ad-hoc git fixture (no
#    `.kittify/config.yaml` mission registry entry) is NOT a gap in claim-
#    base wiring: `resolve_placement_only`'s full `mission_context_for`
#    authority resolves `coordination_branch` through its OWN
#    `_resolve_coordination_branch` lookup (mission_runtime/resolution.py),
#    which -- unlike `status_transition.py`'s own identity resolution --
#    does not recognize this fixture's `<slug>-<mid8>` feature-dir naming
#    without a full resolver/registry, so it falls back to the primary
#    target branch and `safe_commit`'s HEAD-mismatch guard then refuses the
#    commit before this arm's terminal hook ever runs (reproduced verbatim
#    while building this fixture: `SafeCommitHeadMismatch: ... HEAD is
#    'kitty/mission-...', expected 'main'`). That mismatch is orthogonal to
#    the claim-base hook under test, so the SAME coord ref
#    `_transaction_topology_available`'s own resolution already agrees on
#    (`CoordinationWorkspace.branch_name`) is threaded straight through.
#
# Every downstream git operation this test actually verifies -- the coord
# worktree materialization, the real `safe_commit`, and the terminal-hook ref
# clear -- runs unpatched, real production code.


def _coord_fallback_transition(repo: Path, to_lane: str, *, force: bool = False) -> None:
    from unittest.mock import patch

    from specify_cli.coordination.status_transition import emit_status_transition_transactional
    from specify_cli.coordination.workspace import CoordinationWorkspace
    from specify_cli.status.models import TransitionRequest
    from mission_runtime.context import CommitTarget

    coord_target = CommitTarget(ref=CoordinationWorkspace.branch_name(_TXN_MISSION_SLUG, _TXN_MID8))
    with (
        patch(
            "specify_cli.coordination.status_transition._transaction_topology_available",
            return_value=False,
        ),
        patch("mission_runtime.resolve_placement_only", return_value=coord_target),
    ):
        emit_status_transition_transactional(
            TransitionRequest(
                feature_dir=repo / "kitty-specs" / _TXN_MISSION_DIRNAME,
                mission_slug=_TXN_MISSION_SLUG,
                wp_id=_TXN_WP_ID,
                to_lane=to_lane,
                actor="claim-base-wiring-test",
                repo_root=repo,
                force=force,
                reason="claim-base wiring test" if force else None,
                evidence=_approval_evidence() if to_lane in ("approved", "done") else None,
            ),
        )


def test_coord_fallback_arm_done_transition_clears_claim_base(tmp_path: Path) -> None:
    """(c) review-feedback-2.md Nit 2: the non-transactional coord-fallback
    arm's terminal hook (``_fallback_emit_single._coord``, ~577) also clears
    the ref on ``done``."""
    repo = _coord_repo_for_transaction(tmp_path)
    _seed_genesis_to_planned_on_coord(repo)
    record_claim_base(repo, repo, _TXN_MISSION_SLUG, _TXN_WP_ID)

    _coord_fallback_transition(repo, "claimed")
    _coord_fallback_transition(repo, "in_progress")
    assert read_claim_base(repo, _TXN_MISSION_SLUG, _TXN_WP_ID) is not None

    _coord_fallback_transition(repo, "approved")
    _coord_fallback_transition(repo, "done")

    assert read_claim_base(repo, _TXN_MISSION_SLUG, _TXN_WP_ID) is None


def test_coord_fallback_arm_canceled_transition_clears_claim_base(tmp_path: Path) -> None:
    """(c) review-feedback-2.md Nit 2: the coord-fallback arm's terminal
    hook also clears the ref on ``canceled``."""
    repo = _coord_repo_for_transaction(tmp_path)
    _seed_genesis_to_planned_on_coord(repo)
    record_claim_base(repo, repo, _TXN_MISSION_SLUG, _TXN_WP_ID)

    _coord_fallback_transition(repo, "claimed")
    _coord_fallback_transition(repo, "in_progress")
    _coord_fallback_transition(repo, "canceled")

    assert read_claim_base(repo, _TXN_MISSION_SLUG, _TXN_WP_ID) is None


# --- (d) evaluate_for_review_gate refuses vacuously-absent claim base ---


def test_for_review_gate_refuses_when_claim_base_ref_missing_even_with_qualifying_commit(tmp_path: Path) -> None:
    """(d) a WP claimed before the claim-base ref existed (or any other
    reason the ref is missing) must NOT pass the gate just because HEAD
    happens to carry a qualifying implementation commit -- the gate falls
    back to its ordinary refusal (for_review_gate.py's missing-ref branch)."""
    from tests.specify_cli.cli.commands.agent.test_claim_ancestry_gate import (
        _MISSION_SLUG as _ANCESTRY_MISSION_SLUG,
        _WP_SELF,
    )
    from specify_cli.lanes.for_review_gate import evaluate_for_review_gate

    repo = _planning_lane_legacy_repo(tmp_path)
    src_dir = repo / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", "src")
    _git(repo, "commit", "-q", "-m", "feat: a qualifying implementation commit")

    assert read_claim_base(repo, _ANCESTRY_MISSION_SLUG, _WP_SELF) is None

    decision = evaluate_for_review_gate(repo, _ANCESTRY_MISSION_SLUG, _WP_SELF)

    assert decision.passed is False, decision.reason


# --- (e) the allocator and predictor refuse the planning lane ---


def test_predict_lane_worktree_refuses_planning_lane(tmp_path: Path) -> None:
    from specify_cli.lanes.compute import PLANNING_LANE_ID
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    with pytest.raises(ValueError, match="repo-root lane has no worktree"):
        predict_lane_worktree(tmp_path, "any-mission", PLANNING_LANE_ID)


def test_allocate_lane_worktree_refuses_planning_lane(tmp_path: Path) -> None:
    from specify_cli.lanes.compute import PLANNING_LANE_ID
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.worktree_allocator import allocate_lane_worktree

    manifest = LanesManifest(
        version=1,
        mission_slug="demo",
        mission_id="demo",
        mission_branch="kitty/mission-demo",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=PLANNING_LANE_ID,
                wp_ids=("WP01",),
                write_scope=(),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-01-01T00:00:00Z",
        computed_from="test",
    )

    with pytest.raises(ValueError, match="repo-root lane has no worktree"):
        allocate_lane_worktree(repo_root=tmp_path, mission_slug="demo", wp_id="WP01", lanes_manifest=manifest)


# ---------------------------------------------------------------------------
# #5115/WP07: on_wp_terminal ALSO clears the lane-tip ref, once every WP
# sharing that lane is terminal (out-of-map edit -- "the terminal-transition
# clear site" -- justified in the WP07 Activity Log: extends this module's
# existing single terminal hook rather than adding a second one, per
# plan.md post-tasks fold M-3).
# ---------------------------------------------------------------------------


def _build_lanes_fixture_for_tip_clear(repo: Path, mission_slug: str, wp_ids: tuple[str, ...]) -> None:
    """A minimal, no-coord ``lanes``-topology fixture: one lane sharing *wp_ids*."""
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json

    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        f'{{"mission_id": "{mission_slug}", "mission_slug": "{mission_slug}", "topology": "lanes", "target_branch": "main"}}\n',
        encoding="utf-8",
    )
    manifest = LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=mission_slug,
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=wp_ids,
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-01-01T00:00:00Z",
        computed_from="test",
    )
    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "planning: lanes.json + meta.json")


def _seed_wp_lane(repo: Path, mission_slug: str, wp_id: str, to_lane: str) -> None:
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    feature_dir = repo / "kitty-specs" / mission_slug
    chain = {
        "in_progress": [("genesis", "planned"), ("planned", "claimed"), ("claimed", "in_progress")],
        "done": [
            ("genesis", "planned"),
            ("planned", "claimed"),
            ("claimed", "in_progress"),
            ("in_progress", "for_review"),
            ("for_review", "in_review"),
            ("in_review", "approved"),
            ("approved", "done"),
        ],
    }[to_lane]
    digest = hashlib.sha1(f"{wp_id}-{to_lane}".encode()).hexdigest()[:6].upper()
    for index, (from_lane, dest_lane) in enumerate(chain):
        event = StatusEvent(
            event_id=f"01{digest}{index:018d}",
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane(from_lane),
            to_lane=Lane(dest_lane),
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=False,
            execution_mode="worktree",
        )
        append_event(feature_dir, event)


def test_on_wp_terminal_clears_lane_tip_when_the_whole_lane_is_terminal(tmp_path: Path) -> None:
    from specify_cli.lanes.lane_tip import read_tip, record_tip

    mission_slug = "tip-clear-solo-01KZZTES"
    repo = tmp_path / "repo"
    _build_lanes_fixture_for_tip_clear(repo, mission_slug, ("WP01",))
    branch = f"kitty/mission-{mission_slug}-lane-a"
    _git(repo, "checkout", "-q", "-b", branch)
    sha = _git(repo, "rev-parse", "HEAD")
    record_tip(repo, branch, sha=sha)
    assert read_tip(repo, branch) == sha
    _seed_wp_lane(repo, mission_slug, "WP01", "done")

    on_wp_terminal(repo, mission_slug, "WP01")

    assert read_tip(repo, branch) is None


def test_on_wp_terminal_preserves_lane_tip_when_a_sibling_wp_is_still_in_flight(tmp_path: Path) -> None:
    """A shared lane must not lose its tip while a sibling WP is non-terminal."""
    from specify_cli.lanes.lane_tip import read_tip, record_tip

    mission_slug = "tip-clear-shared-01KZZTES"
    repo = tmp_path / "repo"
    _build_lanes_fixture_for_tip_clear(repo, mission_slug, ("WP01", "WP02"))
    branch = f"kitty/mission-{mission_slug}-lane-a"
    _git(repo, "checkout", "-q", "-b", branch)
    sha = _git(repo, "rev-parse", "HEAD")
    record_tip(repo, branch, sha=sha)
    _seed_wp_lane(repo, mission_slug, "WP01", "done")
    _seed_wp_lane(repo, mission_slug, "WP02", "in_progress")

    on_wp_terminal(repo, mission_slug, "WP01")

    assert read_tip(repo, branch) == sha


# --- (f) bookkeeping under the mission dir is never qualifying work (A2) ---


def _commit_file(repo: Path, rel: str, body: str) -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", f"touch {rel}")


def test_meta_json_lock_commit_is_not_qualifying_work(tmp_path: Path) -> None:
    """The first claim commits ``meta.json`` (VCS lock) AFTER the claim base is
    recorded; that bookkeeping commit must not satisfy the for_review gate."""
    from specify_cli.lanes.for_review_gate import _has_qualifying_commit_since_claim_base

    repo = tmp_path / "repo"
    _init_repo(repo)
    base = _git(repo, "rev-parse", "HEAD")
    _commit_file(repo, f"kitty-specs/{_MISSION_SLUG}/meta.json", "{}\n")

    assert _has_qualifying_commit_since_claim_base(repo, base, _MISSION_SLUG) is False


def test_planning_artifact_work_under_mission_dir_still_qualifies(tmp_path: Path) -> None:
    """Control: a planning_artifact WP's real work IS under ``kitty-specs/<slug>/``."""
    from specify_cli.lanes.for_review_gate import _has_qualifying_commit_since_claim_base

    repo = tmp_path / "repo"
    _init_repo(repo)
    base = _git(repo, "rev-parse", "HEAD")
    _commit_file(repo, f"kitty-specs/{_MISSION_SLUG}/meta.json", "{}\n")
    _commit_file(repo, f"kitty-specs/{_MISSION_SLUG}/research.md", "# findings\n")

    assert _has_qualifying_commit_since_claim_base(repo, base, _MISSION_SLUG) is True


def test_non_ascii_bookkeeping_path_is_not_qualifying_work(tmp_path: Path) -> None:
    """A ``core.quotePath``-quoted bookkeeping path must still read as bookkeeping.

    With git's default ``core.quotePath=true`` a non-ASCII path comes back from
    ``git log --name-only`` as ``".kittify/caf\\303\\251.yaml"`` -- a quoted string
    that no longer starts with ``.kittify/``, so it counted as qualifying
    implementation work and let a bookkeeping-only window pass the gate.
    """
    from specify_cli.lanes.for_review_gate import _has_qualifying_commit_since_claim_base

    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "config", "core.quotePath", "true")
    base = _git(repo, "rev-parse", "HEAD")
    _commit_file(repo, ".kittify/café.yaml", "k: v\n")

    assert _has_qualifying_commit_since_claim_base(repo, base, _MISSION_SLUG) is False


def test_non_ascii_implementation_path_still_qualifies(tmp_path: Path) -> None:
    """Control: real work at a non-ASCII path outside the exclusion set qualifies."""
    from specify_cli.lanes.for_review_gate import _has_qualifying_commit_since_claim_base

    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "config", "core.quotePath", "true")
    base = _git(repo, "rev-parse", "HEAD")
    _commit_file(repo, ".kittify/café.yaml", "k: v\n")
    _commit_file(repo, "src/café.py", "VALUE = 1\n")

    assert _has_qualifying_commit_since_claim_base(repo, base, _MISSION_SLUG) is True
