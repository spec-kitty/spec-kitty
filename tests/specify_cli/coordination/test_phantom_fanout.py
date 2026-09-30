"""FR-008 / SC-002: the coord fallback arm announces only committed events.

Mission ``fsm-write-path-integrity-01M1TZV6`` (WP06, T031/T032/T036/T039).

``_fallback_emit_single._coord`` and ``_fallback_emit_batch._coord``
(``coordination/status_transition.py``) write a coord-topology mission's
transition through the flat shell on the coord worktree and then commit it
with ``_commit_status_artifacts_to_coord``. Before this mission the flat
shell's step-7 SaaS fan-out fired *inside* that call -- BEFORE the commit --
so a commit failure truncated the event back (``_restore_coord_status_
artifacts``) after the outside world had already been told about it: a
phantom announcement of an event that no longer exists (spec US2 scenario 1).

The contract (``contracts/emit-pipeline.md`` §2, data-model §5 S-1) is that
external fan-out fires only after the durable write completes in every coord
arm: the transactional doors defer it behind ``BookkeepingTransaction.commit``
(``queue_saas_emission``), and the fallback coord arms now call the flat shell
with ``fan_out=False``, commit, and fan out the committed tail afterwards.

The fallback path is reached by forcing ``_transaction_topology_available``
to ``False`` on a stored-coord mission (the same predicate production consults;
its False arm is the ONLY way into ``_emit_via_non_transactional_fallback``).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from specify_cli.coordination import status_transition as st
from specify_cli.coordination.status_service import EventLogWriteContract, append_event_log
from specify_cli.coordination.transaction import BookkeepingTransaction
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.status.models import Lane, StatusEvent, TransitionRequest, WPInnerStateDelta
from tests.specify_cli.coordination.test_status_transition import (
    COORD_BRANCH,
    MID8,
    MISSION_DIRNAME,
    MISSION_ID,
    MISSION_SLUG,
    _git,
    _request,
    _seed_planned_on_coord,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_FAN_OUT_BOUNDARIES = (
    "specify_cli.status.adapters.fire_saas_fanout",
    "specify_cli.status.fire_saas_fanout",
    "specify_cli.status.emit.fire_saas_fanout",
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """The sibling module's coord-topology mission repo (same meta, same coord branch)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "t@example.invalid")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "config", "commit.gpgsign", "false")
    feature_dir = repo_root / "kitty-specs" / MISSION_DIRNAME
    feature_dir.mkdir(parents=True)
    meta = {"mission_slug": MISSION_SLUG, "mission_id": MISSION_ID, "mid8": MID8, "coordination_branch": COORD_BRANCH}
    (feature_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")
    _git(repo_root, "add", "kitty-specs")
    _git(repo_root, "commit", "-q", "-m", "seed mission")
    _git(repo_root, "branch", COORD_BRANCH)
    return repo_root


@pytest.fixture
def order(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Record the relative order of durable commits and SaaS fan-outs.

    Patches the same three ``fire_saas_fanout`` boundaries as
    ``tests.conftest_saas_sink.mock_saas_sink`` so every fan-out path (flat
    shell and deferred outbound) lands in one ordered log.
    """
    recorded: list[str] = []

    def _fan_out(*_args: Any, **_kwargs: Any) -> None:
        recorded.append("fan_out")

    for boundary in _FAN_OUT_BOUNDARIES:
        monkeypatch.setattr(boundary, _fan_out)
    yield recorded


def _force_fallback_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Take the ``_transaction_topology_available`` False arm (FR-004 row 7)."""
    monkeypatch.setattr(st, "_transaction_topology_available", lambda *_args, **_kwargs: False)


def _coord_events_path(repo_root: Path) -> Path:
    coord_worktree = CoordinationWorkspace.worktree_path(repo_root, MISSION_SLUG, MID8)
    return coord_worktree / "kitty-specs" / MISSION_DIRNAME / "status.events.jsonl"


def _batch(repo_root: Path) -> list[TransitionRequest]:
    claim = _request(repo_root)
    start = _request(repo_root)
    start.to_lane = "in_progress"
    # The forced fallback arm reaches the plain batch door, which fails closed
    # on an omitted workspace context for claimed -> in_progress (#946);
    # production callers (work_package_lifecycle) always supply one.
    start.workspace_context = "worktree:/nonexistent/wp01"
    start.annotation_delta = WPInnerStateDelta(note="batch binding")
    return [claim, start]


def _emit_single(repo_root: Path) -> None:
    st.emit_status_transition_transactional(_request(repo_root))


def _emit_batch(repo_root: Path) -> None:
    st.emit_status_transition_batch_transactional(_batch(repo_root))


def test_coord_fallback_announces_only_its_own_rows_when_writer_interleaves(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A writer finishing after this commit must not enter this call's fan-out."""
    _seed_planned_on_coord(repo)
    _force_fallback_path(monkeypatch)
    real_commit = st._commit_status_artifacts_to_coord
    injected = False
    seen: list[str] = []

    def interleaved_commit(**kwargs: Any) -> None:
        nonlocal injected
        real_commit(**kwargs)
        if not injected:
            injected = True
            other = _request(repo)
            other.to_lane = "in_progress"
            other.workspace_context = "worktree:/test/parallel"
            st.emit_status_transition_transactional(other)

    monkeypatch.setattr(st, "_commit_status_artifacts_to_coord", interleaved_commit)
    monkeypatch.setattr(st._emit, "_saas_fan_out", lambda event, *a, **k: seen.append(event.event_id))
    _emit_single(repo)
    assert len(seen) == len(set(seen)) == 2


@pytest.mark.parametrize("commit_fails", [False, True])
def test_coord_fallback_holds_lock_through_commit_and_restore_but_not_fanout(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    commit_fails: bool,
) -> None:
    from specify_cli.status.locking import _get_thread_locks, feature_status_lock_path

    _seed_planned_on_coord(repo)
    _force_fallback_path(monkeypatch)
    key = str(feature_status_lock_path(repo, MISSION_DIRNAME))
    real_commit = st._commit_status_artifacts_to_coord
    real_restore = st._restore_coord_status_artifacts
    restored: list[bool] = []
    announced: list[bool] = []

    def commit(**kwargs: Any) -> None:
        assert key in _get_thread_locks(), "commit escaped the mission status lock"
        if commit_fails:
            raise RuntimeError("injected commit failure")
        real_commit(**kwargs)

    def restore(*args: Any, **kwargs: Any) -> None:
        assert key in _get_thread_locks(), "rollback escaped the mission status lock"
        restored.append(True)
        real_restore(*args, **kwargs)

    def fanout(*args: Any, **kwargs: Any) -> None:
        assert key not in _get_thread_locks(), "outbound I/O holds the mission status lock"
        announced.append(True)

    monkeypatch.setattr(st, "_commit_status_artifacts_to_coord", commit)
    monkeypatch.setattr(st, "_restore_coord_status_artifacts", restore)
    monkeypatch.setattr(st._emit, "_saas_fan_out", fanout)
    if commit_fails:
        with pytest.raises(RuntimeError, match="injected commit failure"):
            _emit_single(repo)
        assert restored == [True] and announced == []
    else:
        _emit_single(repo)
        assert restored == [] and announced == [True]


@pytest.mark.parametrize("commit_fails", [False, True])
def test_coord_fallback_refreshes_projection_only_after_commit_never_on_failure(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    commit_fails: bool,
) -> None:
    """B1 (review cycle 1): the coord fallback's flat shell
    (``_fallback_emit_single._coord`` / ``_fallback_emit_batch._coord``) runs
    the flat shell INSIDE ``_emit_on_coord_then_commit``'s bounded L1, BEFORE
    the coord commit. Before this fix, WP05's F-3 projection-refresh hook
    fired unconditionally from that pre-commit call (it did not key on
    ``fan_out=False``), producing:

    * a double refresh on success (once pre-commit under L1, once more from
      the post-commit ``_fan_out_committed_coord_tail`` hook), and
    * a phantom projection on a commit failure -- ``.kittify/derived/<slug>/
      status.json`` would show the rolled-back event, the same hazard SC-002
      forbids for SaaS fan-out.

    The fix threads a separate ``refresh_projection=False`` through the flat
    shell (independent of ``fan_out``), so the ONLY refresh is the one
    ``_fan_out_committed_coord_tail`` runs after commit, outside L1.
    """
    from specify_cli.status.locking import _get_thread_locks, feature_status_lock_path
    from specify_cli.status.views import refresh_execution_projection as real_refresh

    _seed_planned_on_coord(repo)
    _force_fallback_path(monkeypatch)
    key = str(feature_status_lock_path(repo, MISSION_DIRNAME))
    real_commit = st._commit_status_artifacts_to_coord
    refreshed: list[bool] = []

    def commit(**kwargs: Any) -> None:
        if commit_fails:
            raise RuntimeError("injected commit failure")
        real_commit(**kwargs)

    def counting_refresh(feature_dir: Path, repo_root: Path) -> bool:
        assert key not in _get_thread_locks(), "projection refresh must run outside the mission status lock"
        refreshed.append(True)
        return real_refresh(feature_dir, repo_root)

    monkeypatch.setattr(st, "_commit_status_artifacts_to_coord", commit)
    # Patch BOTH call sites the flat shell and the coord-tail hook reach
    # through their own module-local bindings of refresh_execution_projection
    # (`status/emit.py`'s `_refresh_projection_if_ledger_on` and this
    # module's `_fan_out_committed_coord_tail`) -- patching only one would
    # hide a double refresh: on the pre-fix code the flat shell's own
    # (buggy) refresh routes through `_emit`'s binding, not this module's.
    monkeypatch.setattr(st._emit, "refresh_execution_projection", counting_refresh)
    monkeypatch.setattr(st, "_refresh_execution_projection", counting_refresh)
    monkeypatch.setattr(st._emit, "_saas_fan_out", lambda *a, **k: None)

    derived_status = repo / ".kittify" / "derived" / MISSION_SLUG / "status.json"

    if commit_fails:
        with pytest.raises(RuntimeError, match="injected commit failure"):
            _emit_single(repo)
        assert refreshed == [], "no refresh may happen when the commit fails (no phantom projection)"
        assert not derived_status.exists(), "no derived file may be written when the commit fails"
    else:
        _emit_single(repo)
        assert refreshed == [True], "exactly one refresh must happen, after commit, outside the lock"
        assert derived_status.exists()


@pytest.mark.parametrize("commit_fails", [False, True])
def test_coord_fallback_batch_refreshes_projection_only_after_commit_never_on_failure(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    commit_fails: bool,
) -> None:
    """Batch sibling of
    ``test_coord_fallback_refreshes_projection_only_after_commit_never_on_failure``:
    ``_fallback_emit_batch``'s ``_flat_shell`` must thread the SAME
    ``refresh_projection=False`` through ``emit_status_transition_batch`` as
    the single door threads through ``emit_status_transition`` -- without it,
    the batch coord arm would double-refresh on success and leave a phantom
    projection behind a rolled-back commit failure, exactly like the single
    door's pre-fix B1 defect.
    """
    from specify_cli.status.locking import _get_thread_locks, feature_status_lock_path
    from specify_cli.status.views import refresh_execution_projection as real_refresh

    _seed_planned_on_coord(repo)
    _force_fallback_path(monkeypatch)
    key = str(feature_status_lock_path(repo, MISSION_DIRNAME))
    real_commit = st._commit_status_artifacts_to_coord
    refreshed: list[bool] = []

    def commit(**kwargs: Any) -> None:
        if commit_fails:
            raise RuntimeError("injected commit failure")
        real_commit(**kwargs)

    def counting_refresh(feature_dir: Path, repo_root: Path) -> bool:
        assert key not in _get_thread_locks(), "projection refresh must run outside the mission status lock"
        refreshed.append(True)
        return real_refresh(feature_dir, repo_root)

    monkeypatch.setattr(st, "_commit_status_artifacts_to_coord", commit)
    # Same double-boundary patch as the single-door test: the flat shell and
    # the coord-tail hook reach refresh through their own module-local
    # bindings (`status/emit.py`'s `_refresh_projection_if_ledger_on` and this
    # module's `_fan_out_committed_coord_tail`).
    monkeypatch.setattr(st._emit, "refresh_execution_projection", counting_refresh)
    monkeypatch.setattr(st, "_refresh_execution_projection", counting_refresh)
    monkeypatch.setattr(st._emit, "_saas_fan_out", lambda *a, **k: None)

    derived_status = repo / ".kittify" / "derived" / MISSION_SLUG / "status.json"

    if commit_fails:
        with pytest.raises(RuntimeError, match="injected commit failure"):
            _emit_batch(repo)
        assert refreshed == [], "no refresh may happen when the commit fails (no phantom projection)"
        assert not derived_status.exists(), "no derived file may be written when the commit fails"
    else:
        _emit_batch(repo)
        assert refreshed == [True], "exactly one refresh must happen, after commit, outside the lock"
        assert derived_status.exists()


@pytest.mark.parametrize("commit_landed", [False, True])
def test_coord_recovery_failure_preserves_only_landed_status(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    commit_landed: bool,
) -> None:
    from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed

    _seed_planned_on_coord(repo)
    _force_fallback_path(monkeypatch)
    CoordinationWorkspace.resolve(repo, MISSION_SLUG, MID8)
    events = _coord_events_path(repo)
    status = events.with_name("status.json")

    def snapshot() -> tuple[bytes, bytes | None]:
        return events.read_bytes(), status.read_bytes() if status.exists() else None

    before = snapshot()
    emitted: list[tuple[bytes, bytes]] = []
    announced: list[bool] = []
    real_commit = st._commit_status_artifacts_to_coord

    def recovery_failure(**kwargs: Any) -> None:
        emitted.append((events.read_bytes(), status.read_bytes()))
        sha = None
        if commit_landed:
            real_commit(**kwargs)
            sha = _git(repo, "rev-parse", COORD_BRANCH).stdout.strip()
        raise SafeCommitRecoveryFailed("injected staging recovery failure", commit_sha=sha)

    monkeypatch.setattr(st, "_commit_status_artifacts_to_coord", recovery_failure)
    monkeypatch.setattr(st._emit, "_saas_fan_out", lambda *a, **k: announced.append(True))
    with pytest.raises(SafeCommitRecoveryFailed, match="injected staging recovery failure"):
        _emit_single(repo)
    assert snapshot() == (emitted[0] if commit_landed else before)
    assert announced == []


# ---------------------------------------------------------------------------
# SC-002: commit failure => truncated back AND zero fan-out (single + batch).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("emit", "expected_lanes"),
    [
        pytest.param(_emit_single, ("claimed",), id="single"),
        pytest.param(_emit_batch, ("claimed", "in_progress"), id="batch"),
    ],
)
def test_coord_fallback_commit_failure_announces_nothing(
    repo: Path,
    order: list[str],
    monkeypatch: pytest.MonkeyPatch,
    emit: Any,
    expected_lanes: tuple[str, ...],
) -> None:
    """A truncated event is never announced (FR-008 / SC-002, US2 scenario 1).

    The commit is forced to fail after the flat shell has written the coord
    log. The arm's failure policy is preserved verbatim: the commit error
    propagates, the coord log is truncated back to the seed, and -- the fix --
    NO SaaS fan-out fired for the event that no longer exists.
    """
    _seed_planned_on_coord(repo)
    _force_fallback_path(monkeypatch)

    def _commit_boom(**_kwargs: object) -> None:
        order.append("commit")
        raise RuntimeError("simulated: coord commit refused")

    monkeypatch.setattr(st, "_commit_status_artifacts_to_coord", _commit_boom)

    with pytest.raises(RuntimeError, match="coord commit refused"):
        emit(repo)

    coord_log = _coord_events_path(repo).read_text(encoding="utf-8")
    assert '"to_lane": "planned"' in coord_log
    for lane in expected_lanes:
        assert f'"to_lane": "{lane}"' not in coord_log, "the event must be truncated back"
    assert order == ["commit"], f"fan-out fired for a truncated event: {order}"


# ---------------------------------------------------------------------------
# Ordering equivalence: fan-out follows the durable write on every coord arm.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("emit", "expected"),
    [
        pytest.param(_emit_single, ["commit", "fan_out"], id="single"),
        pytest.param(_emit_batch, ["commit", "fan_out", "fan_out"], id="batch"),
    ],
)
def test_coord_fallback_fans_out_only_after_commit(
    repo: Path,
    order: list[str],
    monkeypatch: pytest.MonkeyPatch,
    emit: Any,
    expected: list[str],
) -> None:
    """The fallback coord arm commits first, then fans out the committed tail.

    Mirrors ``test_transactional_door_fans_out_only_after_commit`` below so
    the two shell kinds agree on the observable ordering (contract §2 step 7).
    The batch member carrying an ``annotation_delta`` proves the committed
    resolved-binding annotation also survives the deferral: it is read back
    from the committed tail and handed to the resolved-binding fan-out (which
    is a no-op for a plain note, but is invoked after the commit only).
    """
    _seed_planned_on_coord(repo)
    _force_fallback_path(monkeypatch)
    real_commit = st._commit_status_artifacts_to_coord

    def _recording_commit(**kwargs: Any) -> None:
        order.append("commit")
        real_commit(**kwargs)

    monkeypatch.setattr(st, "_commit_status_artifacts_to_coord", _recording_commit)

    emit(repo)

    assert order == expected
    committed = _git(repo, "show", f"{COORD_BRANCH}:kitty-specs/{MISSION_DIRNAME}/status.events.jsonl")
    assert '"to_lane": "claimed"' in committed.stdout


@pytest.mark.parametrize(
    ("emit", "expected"),
    [
        pytest.param(_emit_single, ["commit", "fan_out"], id="single"),
        pytest.param(_emit_batch, ["commit", "fan_out", "fan_out"], id="batch"),
    ],
)
def test_transactional_door_fans_out_only_after_commit(
    repo: Path,
    order: list[str],
    monkeypatch: pytest.MonkeyPatch,
    emit: Any,
    expected: list[str],
) -> None:
    """The transactional doors defer fan-out behind ``BookkeepingTransaction.commit``."""
    _seed_planned_on_coord(repo)
    real_commit = BookkeepingTransaction.commit

    def _recording_commit(self: BookkeepingTransaction, *args: Any, **kwargs: Any) -> Any:
        order.append("commit")
        return real_commit(self, *args, **kwargs)

    monkeypatch.setattr(BookkeepingTransaction, "commit", _recording_commit)

    emit(repo)

    assert order == expected


def test_coord_fallback_collapse_arm_commits_and_announces_nothing(
    repo: Path,
    order: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The alias-collapse no-op arm appends nothing, so nothing is fanned out.

    Requesting the WP's current lane through a legacy alias persists no event
    (C-007, the fourth failure policy); the committed tail is empty and the
    post-commit fan-out therefore has nothing to announce -- the same zero
    fan-out the flat shell's collapse arm has always had.
    """
    _seed_in_progress_on_coord(repo)
    _force_fallback_path(monkeypatch)
    monkeypatch.setattr(st, "_commit_status_artifacts_to_coord", lambda **_kwargs: order.append("commit"))
    request = _request(repo)
    request.to_lane = "doing"  # the one legacy alias; resolves to the current lane

    event = st.emit_status_transition_transactional(request)

    assert event.to_lane == Lane.IN_PROGRESS
    assert order == ["commit"]
    coord_log = _coord_events_path(repo).read_text(encoding="utf-8")
    assert coord_log.count('"to_lane": "in_progress"') == 1, "the collapse arm appends nothing"


def _seed_in_progress_on_coord(repo_root: Path) -> None:
    """Seed WP01 to ``in_progress`` on the coordination branch (committed)."""
    seeds = []
    for index, (from_lane, to_lane) in enumerate(((Lane.GENESIS, Lane.PLANNED), (Lane.PLANNED, Lane.CLAIMED), (Lane.CLAIMED, Lane.IN_PROGRESS))):
        seeds.append(
            StatusEvent(
                event_id=f"01SEEDINPROGRESS00000000{index:02d}",
                mission_slug=MISSION_SLUG,
                mission_id=MISSION_ID,
                wp_id="WP01",
                from_lane=from_lane,
                to_lane=to_lane,
                at=f"2026-05-31T00:00:0{index}+00:00",
                actor="seed",
                force=False,
                reason="seed",
                execution_mode="worktree",
            )
        )
    worktree = repo_root / ".worktrees" / "seed-in-progress"
    _git(repo_root, "worktree", "add", "-q", str(worktree), COORD_BRANCH)
    coord_feature_dir = worktree / "kitty-specs" / MISSION_DIRNAME
    for seed in seeds:
        append_event_log(EventLogWriteContract.coordination_transaction_append(coord_feature_dir), seed)
    _git(worktree, "add", "kitty-specs")
    _git(worktree, "commit", "-q", "-m", "seed genesis->in_progress")
    _git(repo_root, "worktree", "remove", "-f", str(worktree))


@pytest.mark.parametrize("emit", [_emit_single, _emit_batch], ids=["single", "batch"])
@pytest.mark.parametrize("fallback", [False, True], ids=["transaction", "fallback"])
def test_coord_claim_reads_dependencies_from_primary(repo: Path, monkeypatch: pytest.MonkeyPatch, emit: Any, fallback: bool) -> None:
    """Coord status is current, but PRIMARY owns the WP's declared dependencies."""
    from specify_cli.status.emit import TransitionError

    _seed_planned_on_coord(repo)
    primary_tasks = repo / "kitty-specs" / MISSION_DIRNAME / "tasks"
    primary_tasks.mkdir()
    (primary_tasks / "WP01-test.md").write_text("---\nwork_package_id: WP01\ntitle: Test\ndependencies: [WP02]\n---\n", encoding="utf-8")
    if fallback:
        _force_fallback_path(monkeypatch)
    with pytest.raises(TransitionError, match="unsatisfied dependencies"):
        emit(repo)
    assert '"to_lane": "claimed"' not in _coord_events_path(repo).read_text(encoding="utf-8")
