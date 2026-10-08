"""Concurrent claims through ``spec-kitty implement`` and ``orchestrator-api start-implementation``.

concurrent-mission-writers WP03 (#5468, #5796; plan amendments A6, A7).

* **#5468** -- ``implement`` made its claim commit (``chore: WPxx claimed for
  implementation``) *outside* the Mission lock. A concurrent ``move-task`` that had
  already appended its rows but not yet committed them had them swept into the
  claim commit; its own commit then found nothing to commit, failed, and rolled
  its rows off the disk although HEAD held them.
* **#5796** -- on a single_branch Mission the write-checkout occupancy scan
  (``WRITE_CHECKOUT_OCCUPIED``) ran with no lock shared with the claim emit, so two
  overlapping claims both passed it and two WPs were ``in_progress`` in one checkout.

Determinism: the interleavings are produced with ``threading.Event`` hooks at named
seams, never ``sleep``; every wait carries a timeout so a regression fails instead of
hanging. The hook decides from the lock state whether the interleaving is
*permitted* (the first writer holds no lock, so the second runs to its seam) or
*queued* (the first holds the lock, so the second must wait): the SAME test is RED on
the unlocked code and GREEN once the lock spans the window.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import typer
import typer.main

import specify_cli.cli.commands.agent.tasks_move_task_executor as move_task_executor
import specify_cli.lanes.implement_support as implement_support
import specify_cli.orchestrator_api.wp_lifecycle as wp_lifecycle
import specify_cli.status.locking as locking
from specify_cli.status import mission_write_lock
from specify_cli import app as root_app
from specify_cli.cli.commands import implement_claim
from specify_cli.lanes.persistence import write_lanes_json
from tests.specify_cli.cli.commands.test_single_branch_implement_refusals import (
    _build_mission,
    _git,
    _init_repo,
    _repo_root_manifest_multi,
    _write_code_wp,
)
from tests.specify_cli.cli.commands.agent.test_issue_4905_coord_staging import _build_flat_two_lane_mission
from tests.utils import _seed_canonical_wp_state

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: Upper bound for every cross-thread wait; a regression fails with a message instead of hanging.
WAIT_SECONDS = 120.0
EVENTS = "status.events.jsonl"
NOTE = "descoped"
_POLICY = json.dumps(
    {
        "orchestrator_id": "test-orch",
        "orchestrator_version": "0.1.0",
        "agent_family": "claude",
        "approval_mode": "supervised",
        "sandbox_mode": "sandbox",
        "network_mode": "restricted",
        "dangerous_flags": [],
    }
)
_IMPLEMENT = "implement"
_ORCHESTRATOR = "orchestrator"


def _invoke(*args: str) -> int:
    """Run the root CLI in-process without ``CliRunner`` (which swaps ``sys.stdout`` process-wide)."""
    command = typer.main.get_command(root_app)
    try:
        result = command.main(args=list(args), prog_name="spec-kitty", standalone_mode=False)
    except typer.Exit as exc:
        return int(exc.exit_code)
    return int(result or 0)


def _rows(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _disk_rows(feature_dir: Path) -> list[dict[str, Any]]:
    return _rows((feature_dir / EVENTS).read_text(encoding="utf-8"))


def _lane_of(rows: list[dict[str, Any]], wp_id: str) -> str | None:
    lane = None
    for row in rows:
        if row.get("wp_id") == wp_id and row.get("to_lane"):
            lane = row["to_lane"]
    return lane


# ---------------------------------------------------------------------------
# #5468 -- the claim commit runs under the Mission lock
# ---------------------------------------------------------------------------


def test_claim_commit_never_commits_half_of_a_concurrent_writers_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """#5468: ``implement``'s claim commit is a consistent snapshot of the Mission's status files.

    Writer B (``move-task``) appends its transition rows and, still holding the Mission
    lock, is about to append its note annotation. If writer A's claim commit runs in that
    window it commits the transition rows without the annotation: the committed log holds
    half of B's operation, and B's own rows sit in a commit named after A's claim.
    """
    repo, mission = _build_flat_two_lane_mission(tmp_path, monkeypatch, mission_slug="five-four-six-eight")
    feature_dir = repo / "kitty-specs" / mission
    relative = f"kitty-specs/{mission}/{EVENTS}"
    a_thread = threading.current_thread()
    b_mid_operation = threading.Event()
    a_commit_done = threading.Event()
    b_rc: list[int] = []
    a_held_lock: list[bool] = []
    b_thread: list[threading.Thread] = []
    hook_errors: list[str] = []  # an assertion inside a hook may be swallowed by the command's soft-warning arm

    def _writer_b() -> None:
        b_rc.append(_invoke("agent", "tasks", "move-task", "WP02", "--to", "in_progress", "--agent", "system", "--note", NOTE, "--mission", mission))

    original_claim_commit = implement_claim._commit_wp_claim_status

    def _hooked_claim_commit(**kwargs: Any) -> Any:
        if threading.current_thread() is a_thread:
            holds = str(locking.feature_status_lock_path(repo, mission)) in locking._get_thread_locks()
            a_held_lock.append(holds)
            b_thread.append(threading.Thread(target=_writer_b, name="writer-b", daemon=True))
            b_thread[0].start()
            if not holds and not b_mid_operation.wait(WAIT_SECONDS):
                hook_errors.append("writer B never reached the middle of its operation")
        try:
            return original_claim_commit(**kwargs)
        finally:
            a_commit_done.set()

    original_persist = move_task_executor._mt_persist_wp_file

    def _hooked_persist(st: Any, ports: Any) -> Any:
        if threading.current_thread() is not a_thread:
            b_mid_operation.set()  # B's transition rows are on disk, its annotation is not
            if not a_commit_done.wait(WAIT_SECONDS):
                hook_errors.append("writer A's claim commit never finished")
        return original_persist(st, ports)

    monkeypatch.setattr(implement_claim, "_commit_wp_claim_status", _hooked_claim_commit)
    monkeypatch.setattr(move_task_executor, "_mt_persist_wp_file", _hooked_persist)

    a_rc = _invoke("implement", "WP01", "--mission", mission, "--actor", "alice")
    assert b_thread, "writer A never reached its claim commit"
    b_thread[0].join(WAIT_SECONDS)
    out = capsys.readouterr().out

    assert not hook_errors, hook_errors
    assert a_rc == 0, out
    assert not b_thread[0].is_alive(), "writer B never finished"
    assert b_rc == [0], f"writer B (move-task) exited {b_rc}\n{out}"
    disk = _disk_rows(feature_dir)
    assert _lane_of(disk, "WP02") == "in_progress"
    assert _lane_of(disk, "WP01") == "in_progress"
    head = _rows(_git(repo, "show", f"HEAD:{relative}"))
    assert _lane_of(head, "WP01") == "in_progress", "writer A's own claim is not committed"
    b_head_transition = _lane_of(head, "WP02") is not None and _lane_of(head, "WP02") != "planned"
    b_head_note = bool(_notes(head, "WP02", NOTE))
    assert b_head_transition == b_head_note, "the claim commit committed half of writer B's operation (#5468)"
    assert a_held_lock == [True], "writer A committed without holding the Mission lock (#5468)"


def _notes(rows: list[dict[str, Any]], wp_id: str, note: str) -> list[str]:
    return [row["event_id"] for row in rows if row.get("wp_id") == wp_id and (row.get("delta") or {}).get("note") == note]


# ---------------------------------------------------------------------------
# #5796 -- the write-checkout occupancy scan and the claim share one lock
# ---------------------------------------------------------------------------


def _single_branch_repo(root: Path) -> Path:
    _init_repo(root)
    return root


def _add_second_wp(repo: Path, slug: str, mission_id: str, wp_id: str) -> None:
    """Give a single_branch Mission a second WP in the same repository-root lane."""
    feature_dir = repo / "kitty-specs" / slug
    _write_code_wp(feature_dir, wp_id)
    write_lanes_json(feature_dir, _repo_root_manifest_multi(slug, mission_id, ("WP01", wp_id)))
    _seed_canonical_wp_state(repo, slug, wp_id, "planned", actor="system", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T00:31:00Z")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"planning: {slug} {wp_id}")


def _claim_via(kind: str, mission: str, wp_id: str, actor: str) -> int:
    if kind == _IMPLEMENT:
        return _invoke("implement", wp_id, "--mission", mission, "--json", "--actor", actor)
    try:
        wp_lifecycle.start_implementation(mission=mission, wp=wp_id, actor=actor, policy=_POLICY)
    except typer.Exit as exc:
        return int(exc.exit_code)
    return 0


@contextmanager
def _paused_after_scan(
    monkeypatch: pytest.MonkeyPatch, repo: Path, a_kind: str, run_b: Callable[[], None]
) -> Iterator[tuple[threading.Event, list[threading.Thread], list[bool]]]:
    """Run ``run_b`` on a second thread right after writer A's occupancy scan returns."""
    a_thread = threading.current_thread()
    b_done = threading.Event()
    b_queued = threading.Event()
    threads: list[threading.Thread] = []
    held: list[bool] = []

    def _body() -> None:
        try:
            run_b()
        finally:
            b_done.set()

    def _after_scan() -> None:
        if threading.current_thread() is not a_thread or threads:
            return
        held.append(str(locking._checkout_claim_lock_path(repo)) in locking._get_thread_locks())
        threads.append(threading.Thread(target=_body, name="writer-b", daemon=True))
        threads[0].start()
        if held[0]:
            assert b_queued.wait(WAIT_SECONDS), "writer B neither queued on the checkout lock nor finished"
        else:
            assert b_done.wait(WAIT_SECONDS), "writer B did not finish while writer A sat after its scan"

    if a_kind == _IMPLEMENT:
        original_scan = implement_support.refuse_repo_root_checkout_if_unavailable

        def _scan(*args: Any, **kwargs: Any) -> bool:
            result = original_scan(*args, **kwargs)
            _after_scan()
            return result

        monkeypatch.setattr(implement_support, "refuse_repo_root_checkout_if_unavailable", _scan)
    else:
        original_check = wp_lifecycle._ensure_repo_root_checkout_or_fail

        def _check(*args: Any, **kwargs: Any) -> None:
            original_check(*args, **kwargs)
            _after_scan()

        monkeypatch.setattr(wp_lifecycle, "_ensure_repo_root_checkout_or_fail", _check)

    original_lock = locking._named_status_lock

    @contextmanager
    def _watched_lock(lock_path: Path, *, timeout: float) -> Iterator[Path]:
        if threading.current_thread().name == "writer-b" and Path(lock_path).name.startswith("__checkout-"):
            b_queued.set()
        with original_lock(lock_path, timeout=timeout) as held_path:
            yield held_path

    monkeypatch.setattr(locking, "_named_status_lock", _watched_lock)
    yield b_done, threads, held


@pytest.mark.parametrize(
    ("a_kind", "b_kind", "cross_mission"),
    [
        (_IMPLEMENT, _IMPLEMENT, False),
        (_IMPLEMENT, _IMPLEMENT, True),
        (_IMPLEMENT, _ORCHESTRATOR, True),
        (_ORCHESTRATOR, _IMPLEMENT, False),
    ],
    ids=["implement-implement-same-mission", "implement-implement-cross-mission", "implement-orchestrator-cross-mission", "orchestrator-implement-same-mission"],
)
def test_overlapping_single_branch_claims_leave_exactly_one_wp_in_progress(
    a_kind: str,
    b_kind: str,
    cross_mission: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """#5796: the second claimant waits on the checkout lock, then is refused; one WP is in_progress."""
    repo = _single_branch_repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    mission_a, id_a = "occ-race-alpha", "01OCCRACEALPHA00000000001"
    _build_mission(repo, mission_a, id_a)
    if cross_mission:
        mission_b, id_b = "occ-race-beta", "01OCCRACEBETA000000000001"
        _build_mission(repo, mission_b, id_b)
        wp_b = "WP01"
    else:
        mission_b, wp_b = mission_a, "WP03"
        _add_second_wp(repo, mission_a, id_a, wp_b)
    b_rc: list[int] = []

    def _run_b() -> None:
        b_rc.append(_claim_via(b_kind, mission_b, wp_b, "bob"))

    with _paused_after_scan(monkeypatch, repo, a_kind, _run_b) as (_b_done, threads, held):
        a_rc = _claim_via(a_kind, mission_a, "WP01", "alice")
        assert threads, "writer A never reached its occupancy scan"
        threads[0].join(WAIT_SECONDS)
    out = capsys.readouterr().out

    assert not threads[0].is_alive(), "writer B never finished"
    in_progress = [
        (mission, wp)
        for mission, wps in {mission_a: ("WP01", "WP03"), mission_b: ("WP01", "WP03")}.items()
        for wp in wps
        if _lane_of(_disk_rows(repo / "kitty-specs" / mission), wp) == "in_progress"
    ]
    assert a_rc == 0, out
    assert in_progress == [(mission_a, "WP01")], f"both claimants passed the occupancy scan (#5796): {in_progress}\n{out}"
    assert b_rc != [0], out
    assert "WRITE_CHECKOUT_OCCUPIED" in out or "already in_progress in the shared write checkout" in out
    assert held == [True], "writer A did not hold the checkout lock between its scan and its claim (#5796)"


def test_start_implementation_lets_a_lock_order_violation_propagate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Taking the checkout lock under a Mission lock is a programming error, not a retryable STATUS_LOCK_HELD."""
    repo = _single_branch_repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    mission, mission_id = "lock-order-alpha", "01LOCKORDERALPHA00000001"
    _build_mission(repo, mission, mission_id)

    with mission_write_lock(repo / "kitty-specs" / mission, repo_root=repo), pytest.raises(RuntimeError, match="checkout claim lock must be taken before"):
        _claim_via(_ORCHESTRATOR, mission, "WP01", "alice")


@pytest.mark.parametrize("kind", [_ORCHESTRATOR, _IMPLEMENT])
def test_a_checkout_lock_held_past_its_bound_names_status_lock_held_on_the_envelope_and_implement_paths(
    kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """F5/F7: a checkout claim lock that stays held past its bound is STATUS_LOCK_HELD, never a generic or create failure."""
    import specify_cli.status as status_pkg

    repo = _single_branch_repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    mission, mission_id = "lock-held-alpha", "01LOCKHELDALPHA000000001"
    _build_mission(repo, mission, mission_id)
    monkeypatch.setattr(wp_lifecycle, "CHECKOUT_CLAIM_LOCK_TIMEOUT_SECONDS", 0.2)
    real_lock = status_pkg.write_checkout_claim_lock
    monkeypatch.setattr(status_pkg, "write_checkout_claim_lock", lambda root, **_kw: real_lock(root, timeout=0.2))
    holding, release = threading.Event(), threading.Event()

    def _hold() -> None:
        with locking.write_checkout_claim_lock(repo):
            holding.set()
            release.wait(WAIT_SECONDS)

    holder = threading.Thread(target=_hold, name="checkout-holder", daemon=True)
    holder.start()
    assert holding.wait(WAIT_SECONDS), "the holder never took the checkout claim lock"
    try:
        rc = _claim_via(kind, mission, "WP01", "alice")
    finally:
        release.set()
        holder.join(WAIT_SECONDS)

    out = capsys.readouterr().out
    assert rc == 1
    assert "STATUS_LOCK_HELD" in out
    assert "Timed out acquiring status lock" in out
    if kind == _ORCHESTRATOR:
        envelope = json.loads(out.strip().splitlines()[-1])
        assert envelope["success"] is False
        assert envelope["error_code"] == "STATUS_LOCK_HELD"
        assert envelope["data"]["wp_id"] == "WP01"
    else:
        assert "allocation failed" not in out
