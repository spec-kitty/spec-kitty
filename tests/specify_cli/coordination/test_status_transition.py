"""Transactional status-transition integration tests for issue #1356."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from specify_cli.coordination.status_transition import (
    emit_inner_state_changed_transactional,
    emit_status_transition_batch_transactional,
    emit_status_transition_transactional,
    read_current_wp_state_transactional,
    read_event_stream_transactional,
    read_events_transactional,
)
from specify_cli.coordination.status_service import (
    EventLogReadContract,
    EventLogWriteContract,
    StatusContractError,
    append_event_log,
    append_event_stream_log,
    merge_append_preserving_coordination_event_log_bytes,
    read_event_log,
)
from specify_cli.coordination.transaction import BookkeepingCommitFailed, BookkeepingWorktreeMissing
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.core.paths import MissionMetaReadError
from specify_cli.status.models import (
    InnerStateChanged,
    Lane,
    ReviewOverride,
    Status,
    StatusEvent,
    TransitionRequest,
    WPInnerStateDelta,
)

pytest_plugins = ("tests.conftest_saas_sink",)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

MISSION_SLUG = "status-transaction"
MID8 = "01KT1356"
MISSION_ID = "01KT1356000000000000000000"
MISSION_DIRNAME = f"{MISSION_SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_DIRNAME}"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    feature_dir = r / "kitty-specs" / MISSION_DIRNAME
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": MISSION_SLUG,
                "mission_id": MISSION_ID,
                "mid8": MID8,
                "coordination_branch": COORD_BRANCH,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _git(r, "add", "kitty-specs")
    _git(r, "commit", "-q", "-m", "seed mission")
    _git(r, "branch", COORD_BRANCH)
    return r


def _request(repo: Path) -> TransitionRequest:
    return TransitionRequest(
        feature_dir=repo / "kitty-specs" / MISSION_DIRNAME,
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        to_lane="claimed",
        actor="issue-1356-test",
        repo_root=repo,
    )


def _status_event(event_id: str, *, to_lane: str = "claimed") -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane(to_lane),
        at="2026-06-01T00:00:00+00:00",
        actor="contract-test",
        force=False,
        execution_mode="worktree",
    )


def _seed_planned_on_coord(repo: Path) -> StatusEvent:
    """Seed WP01 out of the non-display 'genesis' state into 'planned'.

    A fresh WP derives from_lane 'genesis', so the first lane transition must
    be genesis -> planned (as finalize-tasks does). The seed is written and
    committed directly on the coordination branch via a throwaway worktree, so
    it does not fan out — only the transition under test does.
    """
    seed_event = StatusEvent(
        event_id="01SEEDGENESIS0000000000001",
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-05-31T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )
    worktree = repo / ".worktrees" / "seed-genesis"
    _git(repo, "worktree", "add", "-q", str(worktree), COORD_BRANCH)
    coord_feature_dir = worktree / "kitty-specs" / MISSION_DIRNAME
    append_event_log(
        EventLogWriteContract.coordination_transaction_append(coord_feature_dir),
        seed_event,
    )
    _git(worktree, "add", "kitty-specs")
    _git(worktree, "commit", "-q", "-m", "seed genesis->planned")
    _git(repo, "worktree", "remove", "-f", str(worktree))
    return seed_event


def test_transactional_emit_fans_out_only_after_commit(
    repo: Path,
    mock_saas_sink: Any,
) -> None:
    _seed_planned_on_coord(repo)
    event = emit_status_transition_transactional(_request(repo))

    assert mock_saas_sink.call_count == 1
    assert mock_saas_sink.last_kwargs["metadata"].causation_id == event.event_id

    show = _git(repo, "show", f"{COORD_BRANCH}:kitty-specs/{MISSION_DIRNAME}/status.events.jsonl")
    assert event.event_id in show.stdout


def test_transactional_claim_and_binding_use_one_atomic_stream_append(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A coord claim and its resolved binding are one crash-atomic file replace."""
    from specify_cli.status import store as status_store

    _seed_planned_on_coord(repo)
    request = _request(repo)
    request.annotation_delta = WPInnerStateDelta(
        role="implementer",
        agent_profile="python-pedro",
        model="claude-opus-4-6",
    )
    original_append = status_store._append_serialized_atomic
    appended_units: list[list[dict[str, object]]] = []

    def _capture(feature_dir: Path, payloads: list[dict[str, object]]) -> None:
        appended_units.append(payloads)
        original_append(feature_dir, payloads)

    monkeypatch.setattr(status_store, "_append_serialized_atomic", _capture)

    emit_status_transition_transactional(request)

    assert len(appended_units) == 1
    assert [payload.get("kind", "transition") for payload in appended_units[0]] == [
        "transition",
        "annotation",
    ]


def test_production_implement_lifecycle_persists_two_hops_and_binding_atomically(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real planned implementation start is one crash-atomic durability unit."""
    from specify_cli.status import start_implementation_status
    from specify_cli.status import store as status_store

    _seed_planned_on_coord(repo)
    original_append = status_store._append_serialized_atomic
    appended_units: list[list[dict[str, object]]] = []

    def _capture(feature_dir: Path, payloads: list[dict[str, object]]) -> None:
        appended_units.append(payloads)
        original_append(feature_dir, payloads)

    monkeypatch.setattr(status_store, "_append_serialized_atomic", _capture)

    start_implementation_status(
        feature_dir=repo / "kitty-specs" / MISSION_DIRNAME,
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        actor={
            "role": "implementer",
            "profile": "python-pedro",
            "tool": "claude",
            "model": "claude-opus-4-6",
        },
        workspace_context="worktree:/var/empty/wp01",
        execution_mode="worktree",
        repo_root=repo,
        annotation_delta=WPInnerStateDelta(
            role="implementer",
            agent_profile="python-pedro",
            model="claude-opus-4-6",
        ),
    )

    assert len(appended_units) == 1
    assert [payload.get("kind", "transition") for payload in appended_units[0]] == [
        "transition",
        "transition",
        "annotation",
    ]


def test_transactional_read_targets_coordination_branch(repo: Path) -> None:
    seed = _seed_planned_on_coord(repo)
    request = _request(repo)
    request.annotation_delta = WPInnerStateDelta(
        agent="claude",
        assignee="implementer",
    )
    event = emit_status_transition_transactional(request)

    events = read_events_transactional(
        feature_dir=repo / "kitty-specs" / MISSION_DIRNAME,
        mission_slug=MISSION_SLUG,
        repo_root=repo,
    )

    # The coordination branch carries the genesis->planned seed plus the
    # planned->claimed transition under test.
    assert [e.event_id for e in events] == [seed.event_id, event.event_id]
    stream = read_event_stream_transactional(
        feature_dir=repo / "kitty-specs" / MISSION_DIRNAME,
        mission_slug=MISSION_SLUG,
        repo_root=repo,
    )
    assert [item.event_id for item in stream.transitions] == [seed.event_id, event.event_id]
    assert len(stream.annotations) == 1
    assert stream.annotations[0].delta.agent == "claude"
    assert not (repo / "kitty-specs" / MISSION_DIRNAME / "status.events.jsonl").exists()


def test_review_gate_reads_subtask_annotations_from_unmaterialized_coord_branch(
    repo: Path,
) -> None:
    """The review gate must not fall back to stale primary runtime state.

    WP06 (``fsm-write-path-integrity-01M1TZV6``): the aggregate no longer
    infers the review gates itself; the status-owned pipeline infers them
    inside the transaction from ``txn.feature_dir`` -- the coordination
    surface that carries the committed subtask annotation. The primary
    checkout has NO event log at all, so a gate reading the primary would
    report every roster id incomplete and refuse the hand-off.
    """
    feature_dir = repo / "kitty-specs" / MISSION_DIRNAME
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01-test.md").write_text(
        "---\nwork_package_id: WP01\ndependencies: []\nsubtasks: [T001]\n---\n# WP01\n",
        encoding="utf-8",
    )
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "add authored subtask roster")

    _seed_planned_on_coord(repo)
    request = _request(repo)
    request.annotation_delta = WPInnerStateDelta(subtasks={"T001": Status.DONE})
    emit_status_transition_transactional(request)
    start = _request(repo)
    start.to_lane = "in_progress"
    emit_status_transition_transactional(start)

    from specify_cli.status import TransitionRequest
    from specify_cli.status.aggregate import MissionStatus

    aggregate = MissionStatus(
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        mid8=MID8,
        topology="coordination",
        read_dir=feature_dir,
        repo_root=repo,
        coordination_branch=COORD_BRANCH,
    )
    event = aggregate.transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=MISSION_SLUG,
            wp_id="WP01",
            to_lane=Lane.FOR_REVIEW,
            actor="review-gate",
            repo_root=repo,
        )
    )

    assert event.to_lane == Lane.FOR_REVIEW
    assert not (feature_dir / "status.events.jsonl").exists()
    committed = _git(repo, "show", f"{COORD_BRANCH}:kitty-specs/{MISSION_DIRNAME}/status.events.jsonl")
    assert event.event_id in committed.stdout


def test_merge_done_evidence_reads_unmaterialized_coord_branch(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Merge evidence and runtime agent come from the committed coord stream."""
    feature_dir = repo / "kitty-specs" / MISSION_DIRNAME
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01-test.md").write_text(
        "---\nwork_package_id: WP01\ndependencies: []\nsubtasks: []\n---\n# WP01\n",
        encoding="utf-8",
    )
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "add merge planning artifact")

    _seed_planned_on_coord(repo)
    review = ReviewOverride(
        at="2026-07-21T00:00:00+00:00",
        actor="reviewer-renata",
        wp_id="WP01",
        reason="approved",
    )
    approved = StatusEvent(
        event_id="01MERGEAPPROVED00000000000",
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.APPROVED,
        at=review.at,
        actor="reviewer-renata",
        force=True,
        execution_mode="worktree",
    )
    annotation = InnerStateChanged(
        event_id="01H22222222222222222222222",
        wp_id="WP01",
        at=review.at,
        actor="reviewer-renata",
        delta=WPInnerStateDelta(agent="claude", review=review),
    )
    worktree = repo / ".worktrees" / "seed-merge-state"
    _git(repo, "worktree", "add", "-q", str(worktree), COORD_BRANCH)
    coord_feature_dir = worktree / "kitty-specs" / MISSION_DIRNAME
    append_event_stream_log(
        EventLogWriteContract.coordination_transaction_append(coord_feature_dir),
        [approved, annotation],
    )
    _git(worktree, "add", "kitty-specs")
    _git(worktree, "commit", "-q", "-m", "seed approved merge state")
    _git(repo, "worktree", "remove", "-f", str(worktree))

    emit_mock = Mock()
    monkeypatch.setattr(
        "specify_cli.coordination.status_transition.emit_status_transition_transactional",
        emit_mock,
    )
    from specify_cli.merge.done_bookkeeping import _mark_wp_merged_done

    _mark_wp_merged_done(repo, MISSION_SLUG, "WP01", "main")

    emit_mock.assert_called_once()
    done_request = emit_mock.call_args.args[0]
    assert done_request.to_lane == Lane.DONE
    assert done_request.evidence["review"]["reviewer"] == "reviewer-renata"
    assert not (feature_dir / "status.events.jsonl").exists()
    assert not any((repo / ".worktrees").iterdir())


def test_primary_checkout_event_log_read_remains_explicit(repo: Path) -> None:
    feature_dir = repo / "kitty-specs" / MISSION_DIRNAME
    event = _status_event("01PRIMARY00000000000000000")

    append_event_log(EventLogWriteContract.primary_checkout_append(feature_dir), event)
    events = read_event_log(EventLogReadContract.primary_checkout(feature_dir))

    assert [e.event_id for e in events] == [event.event_id]
    assert (feature_dir / "status.events.jsonl").exists()


def test_coordination_branch_ref_read_ignores_stale_primary_checkout(repo: Path) -> None:
    feature_dir = repo / "kitty-specs" / MISSION_DIRNAME
    primary_event = _status_event("01PRIMARYSTALE00000000000", to_lane="planned")
    coord_event = _status_event("01COORDCURRENT00000000000", to_lane="claimed")
    append_event_log(EventLogWriteContract.primary_checkout_append(feature_dir), primary_event)

    worktree = repo / ".worktrees" / "seed-coord"
    _git(repo, "worktree", "add", "-q", str(worktree), COORD_BRANCH)
    coord_feature_dir = worktree / "kitty-specs" / MISSION_DIRNAME
    append_event_log(
        EventLogWriteContract.coordination_transaction_append(coord_feature_dir),
        coord_event,
    )
    _git(worktree, "add", "kitty-specs")
    _git(worktree, "commit", "-q", "-m", "seed coord event")
    _git(repo, "worktree", "remove", "-f", str(worktree))

    events = read_event_log(
        EventLogReadContract.coordination_branch_ref(
            repo_root=repo,
            destination_ref=COORD_BRANCH,
            feature_dir=coord_feature_dir,
            parser_feature_dir=feature_dir,
        )
    )

    assert [e.event_id for e in events] == [coord_event.event_id]
    assert read_event_log(EventLogReadContract.primary_checkout(feature_dir))[0].event_id == primary_event.event_id


def test_read_contract_cannot_be_used_as_write_contract(repo: Path) -> None:
    event = _status_event("01CONTRACTFAIL000000000000")

    with pytest.raises(StatusContractError):
        append_event_log(  # type: ignore[arg-type]
            EventLogReadContract.primary_checkout(repo / "kitty-specs" / MISSION_DIRNAME),
            event,
        )


def test_wrong_write_target_fails_loudly(repo: Path) -> None:
    event = _status_event("01WRONGTARGET000000000000")
    primary_feature_dir = repo / "kitty-specs" / MISSION_DIRNAME
    coordination_feature_dir = repo / ".worktrees" / "coord" / "kitty-specs" / MISSION_DIRNAME

    with pytest.raises(StatusContractError, match="primary_checkout_append"):
        append_event_log(
            EventLogWriteContract.primary_checkout_append(coordination_feature_dir),
            event,
        )

    with pytest.raises(StatusContractError, match="coordination_transaction_append"):
        append_event_log(
            EventLogWriteContract.coordination_transaction_append(primary_feature_dir),
            event,
        )


def test_wrong_read_source_fails_loudly(repo: Path) -> None:
    primary_feature_dir = repo / "kitty-specs" / MISSION_DIRNAME
    coordination_feature_dir = repo / ".worktrees" / "coord" / "kitty-specs" / MISSION_DIRNAME

    with pytest.raises(StatusContractError, match="primary_checkout"):
        read_event_log(EventLogReadContract.primary_checkout(coordination_feature_dir))

    with pytest.raises(StatusContractError, match="coordination_worktree"):
        read_event_log(EventLogReadContract.coordination_worktree(primary_feature_dir))


def test_append_preserving_coordination_merge_keeps_existing_history() -> None:
    coord = b'{"event_id":"existing"}\n'
    incoming = b'{"event_id":"existing"}\n{"event_id":"new"}\n'

    merged = merge_append_preserving_coordination_event_log_bytes(coord, incoming)

    assert merged == b'{"event_id":"existing"}\n{"event_id":"new"}\n'


def test_transactional_read_does_not_create_coordination_worktree(repo: Path) -> None:
    assert not (repo / ".worktrees").exists()

    events = read_events_transactional(
        feature_dir=repo / "kitty-specs" / MISSION_DIRNAME,
        mission_slug=MISSION_SLUG,
        repo_root=repo,
    )

    assert events == []
    assert not (repo / ".worktrees").exists()
    assert _git(repo, "status", "--short").stdout == ""


def test_transactional_emit_skips_fanout_when_commit_rolls_back(
    repo: Path,
    mock_saas_sink: Any,
) -> None:
    # Seed planned before installing the rejecting hook so the transition
    # under test is genesis-free (claimed is reachable from planned).
    _seed_planned_on_coord(repo)

    hooks_dir = repo / ".git" / "hooks-reject"
    hooks_dir.mkdir()
    hook = hooks_dir / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    _git(repo, "config", "core.hooksPath", str(hooks_dir))

    with pytest.raises(BookkeepingCommitFailed):
        emit_status_transition_transactional(_request(repo))

    assert mock_saas_sink.call_count == 0
    # The coord branch still carries only the seed (genesis->planned); the
    # rolled-back claimed transition must NOT have been committed.
    committed = _git(
        repo,
        "show",
        f"{COORD_BRANCH}:kitty-specs/{MISSION_DIRNAME}/status.events.jsonl",
        check=False,
    )
    assert committed.returncode == 0
    assert '"to_lane": "planned"' in committed.stdout
    assert '"to_lane": "claimed"' not in committed.stdout


def test_transactional_emit_fails_closed_when_coordination_branch_missing(
    repo: Path,
    mock_saas_sink: Any,
) -> None:
    _git(repo, "branch", "-D", COORD_BRANCH)

    with pytest.raises(BookkeepingWorktreeMissing):
        emit_status_transition_transactional(_request(repo))

    assert mock_saas_sink.call_count == 0
    assert not (repo / "kitty-specs" / MISSION_DIRNAME / "status.events.jsonl").exists()


def test_transactional_batch_fails_closed_when_coordination_branch_missing(
    repo: Path,
    mock_saas_sink: Any,
) -> None:
    """C-007: the batch door keeps the single door's fail-closed policy.

    An unresolvable coord worktree propagates ``BookkeepingWorktreeMissing``
    from the batch door exactly as from the single door (#1848 / SC-001);
    the #3460 degrade is the inner-state door's alone.
    """
    _git(repo, "branch", "-D", COORD_BRANCH)

    with pytest.raises(BookkeepingWorktreeMissing):
        emit_status_transition_batch_transactional([_request(repo)])

    assert mock_saas_sink.call_count == 0
    assert not (repo / "kitty-specs" / MISSION_DIRNAME / "status.events.jsonl").exists()


def test_inner_state_annotation_degrades_when_coordination_branch_missing(
    repo: Path,
    mock_saas_sink: Any,
) -> None:
    """#3460: an off-axis annotation emit must NEVER hard-fail on an
    unresolvable coord worktree the way the authoritative lane-hop transition
    correctly does (see ``test_transactional_emit_fails_closed_when_
    coordination_branch_missing`` immediately above — same fixture setup,
    deliberately opposite outcome).

    Before the fix, ``emit_inner_state_changed_transactional`` routed straight
    into ``BookkeepingTransaction.acquire`` whenever meta *declared* a
    ``coordination_branch`` regardless of whether that branch still existed,
    so a mission whose coord branch was deleted (or never materialized) raised
    ``BookkeepingWorktreeMissing`` out of an otherwise-uncommitted, best-effort
    annotation write -- the same defect class that made move-task's
    ``_mt_emit_runtime_state`` crash (#2939 WP03 regression). The fix catches
    ``BookkeepingWorktreeMissing`` and degrades to the uncommitted
    ``emit_inner_state_changed`` primary write instead of propagating.
    """
    _git(repo, "branch", "-D", COORD_BRANCH)
    events_path = repo / "kitty-specs" / MISSION_DIRNAME / "status.events.jsonl"

    annotation = emit_inner_state_changed_transactional(
        repo / "kitty-specs" / MISSION_DIRNAME,
        "WP01",
        WPInnerStateDelta(note="degrade-on-missing-coord-branch"),
        actor="issue-3460-test",
        mission_slug=MISSION_SLUG,
        repo_root=repo,
    )

    assert isinstance(annotation, InnerStateChanged)
    assert mock_saas_sink.call_count == 0
    # Degraded to the PRIMARY, uncommitted write: the annotation lands on
    # the primary checkout's event log rather than a coord ref that could
    # never be committed to (the coord branch no longer exists).
    assert events_path.exists()
    assert "degrade-on-missing-coord-branch" in events_path.read_text(encoding="utf-8")
    assert _git(repo, "status", "--short").stdout.strip() != ""


def test_transactional_emit_fails_closed_on_malformed_meta(
    repo: Path,
    mock_saas_sink: Any,
) -> None:
    (repo / "kitty-specs" / MISSION_DIRNAME / "meta.json").write_text(
        "{bad json",
        encoding="utf-8",
    )

    with pytest.raises(MissionMetaReadError, match="Malformed JSON"):
        emit_status_transition_transactional(_request(repo))

    assert mock_saas_sink.call_count == 0
    assert not (repo / "kitty-specs" / MISSION_DIRNAME / "status.events.jsonl").exists()


def _seed_coord_branch_without_meta(repo: Path) -> StatusEvent:
    """Set up the coordination branch the way a real mission has it.

    On the coordination branch the mission folder holds the status log but no
    ``meta.json`` — ``meta.json`` only lives in the normal checkout. We also
    record WP01 as ``planned`` so the work-start batch has a valid starting
    point. This is done in a temporary worktree that we delete before adding the
    real one, because git won't let the same branch be checked out twice at once.
    """
    seed_event = StatusEvent(
        event_id="01SEEDGENESIS0000000000001",
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-05-31T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )
    worktree = repo / ".worktrees" / "seed-coord-nometa"
    _git(repo, "worktree", "add", "-q", str(worktree), COORD_BRANCH)
    coord_feature_dir = worktree / "kitty-specs" / MISSION_DIRNAME
    (coord_feature_dir / "meta.json").unlink()
    append_event_log(
        EventLogWriteContract.coordination_transaction_append(coord_feature_dir),
        seed_event,
    )
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "-q", "-m", "coord: status surface without meta")
    _git(repo, "worktree", "remove", "-f", str(worktree))
    return seed_event


def test_transactional_batch_rejects_request_without_any_feature_dir(repo: Path) -> None:
    """A batch whose first request carries neither feature_dir nor mission_dir fails fast.

    The transactional batch needs a folder to anchor identity + the same-WP
    consistency check on. If the first request supplies neither ``feature_dir``
    nor ``mission_dir`` (both default to ``None``) it must raise ``TypeError``
    before touching git — alongside the existing missing-slug / missing-wp guard
    — rather than crashing deeper in identity resolution.
    """
    request = TransitionRequest(
        feature_dir=None,
        mission_dir=None,
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        to_lane="claimed",
        actor="no-feature-dir-test",
        repo_root=repo,
    )

    with pytest.raises(
        TypeError, match="requires feature_dir/mission_dir, mission_slug, and wp_id"
    ):
        emit_status_transition_batch_transactional([request])


def test_transactional_batch_same_wp_under_coord_topology_does_not_misfire(
    repo: Path,
    mock_saas_sink: Any,
) -> None:
    """Starting a work package on a coordination-mode mission used to crash here.

    Such a mission lives in two folders: the normal checkout and a separate
    coordination worktree. The batch that starts a work package points at the
    coordination folder, but the guard compared it against the normal-checkout
    folder and rejected the batch as "more than one work package" — crashing
    start-implementation. This builds that two-folder setup and checks the batch
    now succeeds.
    """
    seed = _seed_coord_branch_without_meta(repo)

    # Register the coordination worktree (in real life it already exists by the
    # time work starts) and pass the full mission-folder name, the way the
    # orchestrator does. This makes the requests point at the coordination folder
    # while the mission's identity still resolves to the normal checkout — the
    # mismatch that used to trip the guard.
    coord_worktree = CoordinationWorkspace.worktree_path(repo, MISSION_DIRNAME, MID8)
    _git(repo, "worktree", "add", "-q", str(coord_worktree), COORD_BRANCH)
    coord_feature_dir = coord_worktree / "kitty-specs" / MISSION_DIRNAME

    def _coord_request(to_lane: str) -> TransitionRequest:
        return TransitionRequest(
            feature_dir=coord_feature_dir,
            mission_slug=MISSION_DIRNAME,
            wp_id="WP01",
            to_lane=to_lane,
            actor="coord-batch-test",
            repo_root=repo,
        )

    events = emit_status_transition_batch_transactional(
        [_coord_request("claimed"), _coord_request("in_progress")],
    )

    assert [e.to_lane for e in events] == [Lane.CLAIMED, Lane.IN_PROGRESS]
    assert events[0].from_lane == seed.to_lane  # planned -> claimed


def _seed_planned_on_primary(repo: Path) -> StatusEvent:
    """Append a genesis->planned seed directly to the primary checkout log."""
    seed_event = StatusEvent(
        event_id="01SEEDPRIMARY000000000001",
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-05-31T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )
    append_event_log(
        EventLogWriteContract.primary_checkout_append(repo / "kitty-specs" / MISSION_DIRNAME),
        seed_event,
    )
    return seed_event


def test_transactional_read_falls_back_to_primary_when_coord_branch_deleted(repo: Path) -> None:
    """A deleted coordination branch must not mis-read WPs as genesis (#1847).

    Post-merge cleanup deletes the coordination branch while meta.json still
    declares it. The read path must then report lanes from the primary
    checkout event log instead of reading the dangling ref as empty.
    """
    from specify_cli.coordination.status_transition import read_current_wp_state_transactional

    seed = _seed_planned_on_primary(repo)
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "merge mission artifacts to main")
    _git(repo, "branch", "-D", COORD_BRANCH)

    _state = read_current_wp_state_transactional(
        feature_dir=repo / "kitty-specs" / MISSION_DIRNAME,
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        repo_root=repo,
    )
    lane, actor = _state.lane, _state.actor
    assert lane == Lane.PLANNED
    assert actor == "seed"

    events = read_events_transactional(
        feature_dir=repo / "kitty-specs" / MISSION_DIRNAME,
        mission_slug=MISSION_SLUG,
        repo_root=repo,
    )
    assert [e.event_id for e in events] == [seed.event_id]


# ---------------------------------------------------------------------------
# M6 error contract (PR #1850): the fail-closed surface refusal
# (StatusReadPathNotFound — coord worktree root materialized, mission dir
# absent) must never escape the transactional paths as a raw traceback. The
# transaction identity anchors on the canonical primary dir the structured
# refusal already carries; failures stay structured (Bookkeeping* errors).
# ---------------------------------------------------------------------------


def _materialize_coord_root_without_mission_dir(repo: Path) -> Path:
    """The fail-closed window: coord worktree root exists, mission dir absent."""
    coord_root = repo / ".worktrees" / f"{MISSION_DIRNAME}-coord"
    coord_root.mkdir(parents=True)
    return coord_root


def _canonical_slug_request(repo: Path) -> TransitionRequest:
    """Request carrying the canonical mission-dir name (what resolvers hand over)."""
    return TransitionRequest(
        feature_dir=repo / "kitty-specs" / MISSION_DIRNAME,
        mission_slug=MISSION_DIRNAME,
        wp_id="WP01",
        to_lane="planned",
        actor="m6-error-contract-test",
        repo_root=repo,
    )


def test_transactional_read_survives_fail_closed_surface_refusal(repo: Path) -> None:
    _materialize_coord_root_without_mission_dir(repo)

    events = read_events_transactional(
        feature_dir=repo / "kitty-specs" / MISSION_DIRNAME,
        mission_slug=MISSION_DIRNAME,
        repo_root=repo,
    )

    assert events == []


def test_transactional_wp_state_read_survives_fail_closed_surface_refusal(
    repo: Path,
) -> None:
    _materialize_coord_root_without_mission_dir(repo)

    _state = read_current_wp_state_transactional(
        feature_dir=repo / "kitty-specs" / MISSION_DIRNAME,
        mission_slug=MISSION_DIRNAME,
        wp_id="WP01",
        repo_root=repo,
    )
    lane, actor = _state.lane, _state.actor

    assert lane == Lane.GENESIS
    assert actor is None


def test_transactional_emit_fail_closed_surface_refusal_stays_structured(
    repo: Path,
) -> None:
    """The emit path refuses with a structured Bookkeeping error, not a raw leak.

    The mkdir'd coord root is not a valid git worktree, so after identity
    resolution succeeds the transaction refuses with its own structured
    BOOKKEEPING_WORKTREE_MISSING error — never a raw StatusReadPathNotFound.
    """
    _materialize_coord_root_without_mission_dir(repo)

    with pytest.raises(BookkeepingWorktreeMissing):
        emit_status_transition_transactional(_canonical_slug_request(repo))


# ---------------------------------------------------------------------------
# #154 regression: the coordination-topology probe must not demand mission
# metadata a meta-less mission never had. ``resolve_transaction_mid8`` returns
# "" for exactly those missions — its documented bare-slug surface ("there is
# no coord target to mis-route") — so probing branch existence by COMPOSING a
# ``CoordinationWorkspace`` handle from that empty mid8 raised
# CoordinationWorkspaceIdentityUnresolved out of every transactional read and
# write whenever the feature dir sat inside a git work tree (e.g. any ambient
# ancestor checkout above basetemp on the host running the suite), instead of
# reporting "no coordination topology available".
# ---------------------------------------------------------------------------


def _meta_less_legacy_repo(tmp_path: Path) -> Path:
    """A real repo whose only mission dir carries no meta.json (legacy slug)."""
    r = tmp_path / "meta-less-repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "kitty-specs" / "099-lifecycle-test").mkdir(parents=True)
    return r


def test_topology_probe_reports_unavailable_for_meta_less_mission(
    tmp_path: Path,
) -> None:
    """Empty mid8 ⇒ topology NOT available; never a malformed-ref composition."""
    from specify_cli.coordination.status_transition import (
        _identity_for_request,
        _transaction_topology_available,
    )

    repo = _meta_less_legacy_repo(tmp_path)
    identity = _identity_for_request(
        TransitionRequest(
            feature_dir=repo / "kitty-specs" / "099-lifecycle-test",
            mission_slug="099-lifecycle-test",
            wp_id="WP01",
            to_lane=Lane.PLANNED,
            actor="topology-probe",
            repo_root=repo,
        )
    )

    assert identity.mid8 == ""
    assert _transaction_topology_available(identity, "099-lifecycle-test") is False


def test_meta_less_mission_read_does_not_raise_identity_unresolved(
    tmp_path: Path,
) -> None:
    """An unseeded WP in a meta-less mission inside a real repo reads GENESIS."""
    repo = _meta_less_legacy_repo(tmp_path)

    _state = read_current_wp_state_transactional(
        feature_dir=repo / "kitty-specs" / "099-lifecycle-test",
        mission_slug="099-lifecycle-test",
        wp_id="WP01",
        repo_root=repo,
    )

    assert _state.lane == Lane.GENESIS


# ---------------------------------------------------------------------------
# FR-007 / SC-003 (WP06 T032 -> T039): batch/single owned-mission parity.
# The two transactional doors share ONE identity/acquire preamble, so the
# owned-mission refusal and the ``effective_root`` acquisition can no longer
# diverge field by field (decision Q5: parity; data-model §5 S-2).
# ---------------------------------------------------------------------------


def _owned_identity(repo: Path, *, primary_root: Path) -> Any:
    from specify_cli.coordination.status_transition import _TransactionIdentity

    return _TransactionIdentity(
        repo_root=repo,
        feature_dir=repo / "kitty-specs" / MISSION_DIRNAME,
        mission_id=MISSION_ID,
        mid8=MID8,
        destination_ref=COORD_BRANCH,
        meta_exists=True,
        coordination_branch=COORD_BRANCH,
        transaction_meta_exists=True,
        primary_root=primary_root,
    )


def _owned_request(repo: Path, *, effective_root: Path) -> TransitionRequest:
    request = _request(repo)
    request.effective_root = effective_root
    return request


class _AcquireHalted(Exception):
    """Sentinel: the acquire shape was recorded; nothing beyond it runs."""


def test_batch_door_refuses_owned_mission_without_transaction_like_single(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both doors raise the same ``OWNED_TRANSACTION_UNAVAILABLE`` refusal.

    An owned-mission (``effective_root``) request must never degrade to the
    non-transactional fallback: the single door has refused it since #1737;
    the batch door used to fall back silently (the SC-003 divergence).
    """
    from mission_runtime import ActionContextError
    from specify_cli.coordination import status_transition as st

    owned_checkout = tmp_path / "owned"
    monkeypatch.setattr(st, "_identity_for_request", lambda _r: _owned_identity(repo, primary_root=repo))
    monkeypatch.setattr(st, "_transaction_topology_available", lambda *_a, **_k: False)
    request = _owned_request(repo, effective_root=owned_checkout)

    with pytest.raises(ActionContextError) as single:
        emit_status_transition_transactional(request)
    with pytest.raises(ActionContextError) as batch:
        emit_status_transition_batch_transactional([request])

    assert single.value.code == "OWNED_TRANSACTION_UNAVAILABLE"
    assert batch.value.code == single.value.code
    assert not (repo / "kitty-specs" / MISSION_DIRNAME / "status.events.jsonl").exists()


def test_batch_door_acquires_transaction_with_the_single_door_shape(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``BookkeepingTransaction.acquire`` receives identical identity fields.

    For an owned mission the lock/worktree anchor is ``identity.primary_root``
    and ``effective_root`` is the owned checkout (``identity.repo_root``); for
    an ordinary mission both doors pass ``identity.repo_root`` and no
    ``effective_root``. The recorded kwargs must agree door-for-door.
    """
    from specify_cli.coordination import status_transition as st
    from specify_cli.coordination.transaction import BookkeepingTransaction

    owned_checkout = tmp_path / "owned"
    owned_checkout.mkdir()
    identity = _owned_identity(owned_checkout, primary_root=repo)
    monkeypatch.setattr(st, "_identity_for_request", lambda _r: identity)
    monkeypatch.setattr(st, "_transaction_topology_available", lambda *_a, **_k: True)
    recorded: list[dict[str, Any]] = []

    def _record_acquire(**kwargs: Any) -> None:
        recorded.append(kwargs)
        raise _AcquireHalted

    monkeypatch.setattr(BookkeepingTransaction, "acquire", _record_acquire)
    request = _owned_request(repo, effective_root=owned_checkout)

    with pytest.raises(_AcquireHalted):
        emit_status_transition_transactional(request)
    with pytest.raises(_AcquireHalted):
        emit_status_transition_batch_transactional([request])

    single, batch = recorded
    assert single["repo_root"] == repo, "the transaction anchors on the primary root"
    assert single["effective_root"] == owned_checkout
    for field in ("repo_root", "effective_root", "mission_id", "mission_slug", "mid8", "destination_ref", "capability"):
        assert batch[field] == single[field], field


# ---------------------------------------------------------------------------
# FR-006 / C-009 (WP06 T039): delegation equivalence across the three doors.
# The same TransitionRequest yields the same StatusEvent (modulo event_id/at)
# through the plain door, the single transactional door and the batch
# transactional door, and ``prepare_transition`` is the only validator any
# of them invokes.
# ---------------------------------------------------------------------------

_EVENT_IDENTITY_FIELDS = (
    "mission_slug",
    "mission_id",
    "wp_id",
    "from_lane",
    "to_lane",
    "actor",
    "force",
    "execution_mode",
    "reason",
    "reason_source",
    "review_ref",
    "evidence",
    "review_result",
    "policy_metadata",
)


def _event_identity(event: StatusEvent) -> dict[str, Any]:
    return {field: getattr(event, field) for field in _EVENT_IDENTITY_FIELDS}


def _flat_mission(tmp_path: Path) -> Path:
    """The same mission as ``repo`` but coord-less and outside git: the plain door's home."""
    feature_dir = tmp_path / "flat" / "kitty-specs" / MISSION_DIRNAME
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": MISSION_SLUG, "mission_id": MISSION_ID, "mid8": MID8}) + "\n",
        encoding="utf-8",
    )
    append_event_log(
        EventLogWriteContract.primary_checkout_append(feature_dir),
        _seed_planned_event(),
    )
    return feature_dir


def _seed_planned_event() -> StatusEvent:
    return StatusEvent(
        event_id="01SEEDGENESIS0000000000001",
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-05-31T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )


def _claim_with_policy(feature_dir: Path, repo_root: Path) -> TransitionRequest:
    return TransitionRequest(
        feature_dir=feature_dir,
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        to_lane="claimed",
        actor="equivalence-test",
        reason="delegation equivalence",
        reason_source="operator",
        repo_root=repo_root,
        policy_metadata={"claim": "policy"},
    )


def test_three_doors_build_the_same_event_and_validate_once_each(
    repo: Path, tmp_path: Path, mock_saas_sink: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specify_cli.coordination import status_transition as st
    from specify_cli.status import emit as status_emit
    from specify_cli.status import transition_pipeline

    calls: list[tuple[object, ...]] = []
    real = transition_pipeline.validate_transition

    def _counting(*args: object, **kwargs: object) -> object:
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(transition_pipeline, "validate_transition", _counting)
    _seed_planned_on_coord(repo)
    coord_feature_dir = repo / "kitty-specs" / MISSION_DIRNAME
    flat_feature_dir = _flat_mission(tmp_path)

    plain = status_emit.emit_status_transition(_claim_with_policy(flat_feature_dir, None), ensure_sync_daemon=False)
    assert len(calls) == 1
    single = emit_status_transition_transactional(_claim_with_policy(coord_feature_dir, repo), ensure_sync_daemon=False)
    assert len(calls) == 2
    # Roll the coord WP back to planned so the batch door sees the same from_lane
    # (the worktree holding the branch must go before the ref can move).
    _git(repo, "worktree", "remove", "-f", str(CoordinationWorkspace.worktree_path(repo, MISSION_SLUG, MID8)))
    _git(repo, "branch", "-f", COORD_BRANCH, f"{COORD_BRANCH}~1")
    (batch,) = emit_status_transition_batch_transactional(
        [_claim_with_policy(coord_feature_dir, repo)], ensure_sync_daemon=False
    )
    assert len(calls) == 3

    assert _event_identity(plain) == _event_identity(single) == _event_identity(batch)
    assert {(args[0], args[1]) for args in calls} == {(Lane.PLANNED, Lane.CLAIMED)}
    assert not hasattr(st, "validate_transition"), "the transactional shell must not validate itself (P-2)"
    assert not hasattr(st, "_prepare_event"), "the pre-promotion duplicate is gone (FR-005/FR-006)"
