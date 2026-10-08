"""Every per-Mission lock caller takes the canonical key (mission-writer-followups WP13, plan A1, A4, A6, A7).

The fixture is a legacy bare-directory coordination Mission: a primary directory ``060-test`` whose
``meta.json`` records a coordination branch and mid8 ``01COORD0``, beside the coordination directory
``060-test-01COORD0``. ``BookkeepingTransaction`` and the core doors lock ``060-test-01COORD0``; a caller
that keys on ``feature_dir.name`` locks ``060-test`` and can invert lock order against them.
"""

from __future__ import annotations

import ast
import json
import subprocess
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import specify_cli.status.locking as locking_module
from specify_cli.coordination.legacy_resolution import _mission_specs_dir_name
from specify_cli.coordination.transaction import _transaction_hold
from specify_cli.mission_metadata import flatten_coordination_metadata
from specify_cli.status import FeatureStatusLockTimeoutError, mission_lock_key
from specify_cli.status.locking import feature_status_lock_path
from specify_cli.status.mission_write import mission_write_lock

pytestmark = [pytest.mark.unit]

SLUG = "060-test"
MID8 = "01COORD0"
COORD_NAME = f"{SLUG}-{MID8}"
WAIT_SECONDS = 1.0
TIMEOUT_SECONDS = 0.5

Mission = tuple[Path, Path, Path]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def mission(tmp_path: Path) -> Mission:
    """``(repo, primary_dir, coord_dir)`` for a legacy bare-directory coordination Mission."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    primary = repo / "kitty-specs" / SLUG
    primary.mkdir(parents=True)
    (primary / "meta.json").write_text(
        json.dumps(
            {"mission_slug": SLUG, "mission_id": f"{MID8}XXXXXXXXXXXXXXXXXX", "mid8": MID8, "coordination_branch": f"kitty/mission-{COORD_NAME}"}
        ),
        encoding="utf-8",
    )
    coord = repo / ".worktrees" / f"{COORD_NAME}-coord" / "kitty-specs" / COORD_NAME
    coord.mkdir(parents=True)
    return repo, primary, coord


@pytest.fixture
def lock_files(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Names of every lock file the code under test asks the shared lock primitive for."""
    taken: list[str] = []
    real = locking_module._named_status_lock

    @contextmanager
    def _recording(lock_path: Path, *, timeout: float) -> Iterator[Path]:
        taken.append(lock_path.name)
        with real(lock_path, timeout=timeout) as held:
            yield held

    monkeypatch.setattr(locking_module, "_named_status_lock", _recording)
    return taken


class _Stop(Exception):
    """Raised by a stand-in so a caller stops right after it took its lock."""


def _stop(*_args: Any, **_kwargs: Any) -> Any:
    raise _Stop


# ---------------------------------------------------------------------------
# T005 / T053 -- each direct caller locks the transaction's file
# ---------------------------------------------------------------------------

Driver = Callable[[Path, Path, Path, pytest.MonkeyPatch], None]


def _drive_emit_inner_state(repo: Path, primary: Path, coord: Path, _mp: pytest.MonkeyPatch) -> None:
    from specify_cli.status.emit import emit_inner_state_changed
    from specify_cli.status.wp_state import WPInnerStateDelta

    emit_inner_state_changed(primary, "WP01", WPInnerStateDelta(shell_pid="1"), actor="t", mission_slug=SLUG, repo_root=repo)


def _drive_retro_lock(repo: Path, primary: Path, coord: Path, _mp: pytest.MonkeyPatch) -> None:
    from specify_cli.retrospective.lifecycle_events import retro_status_lock

    with retro_status_lock(primary):
        pass


def _drive_decision_append(repo: Path, primary: Path, coord: Path, _mp: pytest.MonkeyPatch) -> None:
    from specify_cli.decisions.emit import _append_raw_event

    _append_raw_event(primary / "status.events.jsonl", {"event_id": "01TESTEVENT00000000000000"})


def _drive_lifecycle_append(repo: Path, primary: Path, coord: Path, _mp: pytest.MonkeyPatch) -> None:
    from specify_cli.status.lifecycle_events import persist_lifecycle_event_local

    persist_lifecycle_event_local(
        primary / "status.events.jsonl",
        "NoSuchEvent",
        {},
        aggregate_id="a",
        aggregate_type="Mission",
        mission_slug=SLUG,
        repo_root=repo,
    )


def _drive_rebuild(repo: Path, primary: Path, coord: Path, mp: pytest.MonkeyPatch) -> None:
    import specify_cli.migration.rebuild_state as module

    mp.setattr(module, "_rebuild_event_log_locked", lambda *a, **k: None)
    module.rebuild_event_log(primary, SLUG, {})


def _drive_verdict_backfill(repo: Path, primary: Path, coord: Path, mp: pytest.MonkeyPatch) -> None:
    import specify_cli.migration.verdict_provenance_backfill as module

    mp.setattr(module, "_resolve_mission_id", lambda *_a, **_k: "m")
    mp.setattr(module, "_collect_backfill_events", lambda *_a, **_k: ([], []))
    module.backfill_verdict_provenance(primary)


def _drive_runtime_backfill(repo: Path, primary: Path, coord: Path, mp: pytest.MonkeyPatch) -> None:
    import specify_cli.migration.backfill_runtime_state as module

    (primary / "tasks").mkdir()
    mp.setattr(module, "_backfill_runtime_state_locked", lambda *_a, **_k: None)
    module.backfill_runtime_state(primary)


def _drive_lifecycle_start(repo: Path, primary: Path, coord: Path, mp: pytest.MonkeyPatch) -> None:
    import specify_cli.coordination.status_transition as transition
    from specify_cli.status.work_package_lifecycle import start_implementation_status

    mp.setattr(transition, "read_current_wp_state_transactional", _stop)
    with pytest.raises(_Stop):
        start_implementation_status(
            feature_dir=primary, mission_slug=SLUG, wp_id="WP01", actor="t", workspace_context="w", execution_mode="worktree", repo_root=repo
        )


def _drive_review_start(repo: Path, primary: Path, coord: Path, mp: pytest.MonkeyPatch) -> None:
    import specify_cli.coordination.status_transition as transition
    from specify_cli.status.work_package_lifecycle import start_review_status

    mp.setattr(transition, "read_current_wp_state_transactional", _stop)
    with pytest.raises(_Stop):
        start_review_status(
            feature_dir=primary, mission_slug=SLUG, wp_id="WP01", actor="t", workspace_context="w", execution_mode="worktree", repo_root=repo
        )


def _drive_coord_seed(repo: Path, primary: Path, coord: Path, mp: pytest.MonkeyPatch) -> None:
    import specify_cli.coordination.coord_seed as module

    mp.setattr(module, "_seed_coord_surface_locked", lambda *_a, **_k: None)
    request = SimpleNamespace(owned=None, repo_root=repo, mission_dir_name=COORD_NAME, root_mission_dir=primary, mission_slug=SLUG)
    module._seed_coord_surface(request)  # type: ignore[arg-type]


_DRIVERS: dict[str, Driver] = {
    "emit_inner_state_changed": _drive_emit_inner_state,
    "retro_status_lock": _drive_retro_lock,
    "decisions append": _drive_decision_append,
    "lifecycle append": _drive_lifecycle_append,
    "rebuild_event_log": _drive_rebuild,
    "verdict provenance backfill": _drive_verdict_backfill,
    "runtime state backfill": _drive_runtime_backfill,
    "start_implementation_status": _drive_lifecycle_start,
    "start_review_status": _drive_review_start,
    "coord seed": _drive_coord_seed,
}


@pytest.mark.parametrize("driver", list(_DRIVERS.values()), ids=list(_DRIVERS))
def test_direct_caller_takes_the_lock_file_the_bookkeeping_transaction_takes(
    driver: Driver, mission: Mission, lock_files: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, primary, coord = mission
    driver(repo, primary, coord, monkeypatch)
    assert lock_files, "the caller took no Mission lock"
    expected = feature_status_lock_path(repo, _mission_specs_dir_name(SLUG, MID8)).name
    assert set(lock_files) == {expected}


# ---------------------------------------------------------------------------
# T053 -- source sweep: no caller keys a per-Mission lock on a directory name
# ---------------------------------------------------------------------------

_SRC = Path(__file__).resolve().parents[2] / "src" / "specify_cli"
#: Files whose ``feature_status_lock`` key is not a Mission directory's: the matrix writers (WP04)
#: and the issue-matrix verdict (not a per-Mission status lock), plus the key's own definition sites.
_SWEEP_EXEMPT = frozenset(
    {
        "acceptance/matrix.py",
        "cli/commands/agent/issue_verdict.py",
        "status/mission_write.py",
        "status/locking.py",
        "coordination/transaction.py",
    }
)


def _key_argument(call: ast.Call) -> ast.expr | None:
    if len(call.args) >= 2:
        return call.args[1]
    return next((kw.value for kw in call.keywords if kw.arg == "lock_key"), None)


def _is_lock_call(call: ast.Call) -> bool:
    func = call.func
    return (isinstance(func, ast.Name) and func.id == "feature_status_lock") or (isinstance(func, ast.Attribute) and func.attr == "feature_status_lock")


def _is_key_call(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name | ast.Attribute) and getattr(node.func, "id", getattr(node.func, "attr", "")) in {
        "mission_lock_key",
        "transaction_lock_key",
    }


def _unconverted_callers() -> list[str]:
    found: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        rel = path.relative_to(_SRC).as_posix()
        if rel in _SWEEP_EXEMPT:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and _is_lock_call(node) and not _is_key_call(_key_argument(node)):
                found.append(f"{rel}:{node.lineno}")
    return found


def test_every_per_mission_lock_caller_passes_the_canonical_key() -> None:
    assert _unconverted_callers() == []


_SWEEP_SOURCES = {
    "directory name": ("feature_status_lock(root, feature_dir.name)", False),
    "attribute directory name": ("_t.feature_status_lock(root, st.feature_dir.name)", False),
    "canonical key": ("feature_status_lock(root, mission_lock_key(d, repo_root=root))", True),
    "keyword canonical key": ("feature_status_lock(root, lock_key=mission_lock_key(d))", True),
}


@pytest.mark.parametrize(("source", "converted"), list(_SWEEP_SOURCES.values()), ids=list(_SWEEP_SOURCES))
def test_the_sweep_distinguishes_converted_from_unconverted_callers(source: str, converted: bool) -> None:
    call = ast.parse(source).body[0].value  # type: ignore[attr-defined]
    assert _is_lock_call(call)
    assert _is_key_call(_key_argument(call)) is converted


# ---------------------------------------------------------------------------
# T054 -- lock order across threads
# ---------------------------------------------------------------------------


def test_a_direct_caller_serializes_with_the_core_door_on_the_other_directory(mission: Mission) -> None:
    """While the lifecycle path holds the Mission lock through the primary dir, the core door on the coord dir waits."""
    from specify_cli.retrospective.lifecycle_events import retro_status_lock

    repo, primary, coord = mission
    holder_in, release = threading.Event(), threading.Event()
    outcome: list[BaseException | None] = []

    def _hold() -> None:
        with retro_status_lock(primary):
            holder_in.set()
            release.wait(WAIT_SECONDS * 4)

    holder = threading.Thread(target=_hold)
    holder.start()
    try:
        assert holder_in.wait(WAIT_SECONDS * 4)
        try:
            with mission_write_lock(coord, repo_root=repo, timeout=TIMEOUT_SECONDS):
                outcome.append(None)
        except FeatureStatusLockTimeoutError as exc:
            outcome.append(exc)
    finally:
        release.set()
        holder.join(WAIT_SECONDS * 4)
    assert len(outcome) == 1
    assert isinstance(outcome[0], FeatureStatusLockTimeoutError)


def test_lifecycle_path_and_implement_claim_path_do_not_deadlock(mission: Mission) -> None:
    """Thread A takes the lifecycle lock then the claim lock; thread B takes them in the opposite order.

    With two lock files this deadlocks (each waits for the other, both time out). With one lock file the
    threads serialize: neither times out and their outer sections never overlap.
    """
    from specify_cli.retrospective.lifecycle_events import retro_status_lock

    repo, primary, coord = mission
    a_in, b_in = threading.Event(), threading.Event()
    errors: dict[str, BaseException] = {}
    inside: list[int] = []
    overlapped: list[str] = []
    guard = threading.Lock()

    @contextmanager
    def _outer(name: str) -> Iterator[None]:
        with guard:
            overlapped.extend([name] if inside else [])
            inside.append(1)
        try:
            yield
        finally:
            with guard:
                inside.pop()

    def _lifecycle_then_claim() -> None:
        try:
            with retro_status_lock(primary), _outer("A"):
                a_in.set()
                b_in.wait(WAIT_SECONDS)
                with mission_write_lock(coord, repo_root=repo, timeout=TIMEOUT_SECONDS * 4):
                    pass
        except FeatureStatusLockTimeoutError as exc:
            errors["A"] = exc

    def _claim_then_lifecycle() -> None:
        try:
            a_in.wait(WAIT_SECONDS * 4)
            with mission_write_lock(coord, repo_root=repo, timeout=TIMEOUT_SECONDS * 4), _outer("B"):
                b_in.set()
                with retro_status_lock(primary, lock_timeout=TIMEOUT_SECONDS * 4):
                    pass
        except FeatureStatusLockTimeoutError as exc:
            errors["B"] = exc

    threads = [threading.Thread(target=_lifecycle_then_claim), threading.Thread(target=_claim_then_lifecycle)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(WAIT_SECONDS * 20)
    assert not any(thread.is_alive() for thread in threads)
    assert errors == {}
    assert overlapped == []


# ---------------------------------------------------------------------------
# Handoffs from the WP01 review
# ---------------------------------------------------------------------------


def test_a_coord_seed_hold_is_registered_for_held_key_reuse(mission: Mission, monkeypatch: pytest.MonkeyPatch) -> None:
    """A nested ``mission_lock_key`` inside the seed's hold keeps the held key when the Mission's meta changes (A4)."""
    import specify_cli.coordination.coord_seed as module

    repo, primary, _coord = mission
    meta_path = primary / "meta.json"
    seen: list[str] = []

    def _locked(_request: object) -> None:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta.pop("coordination_branch")
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        seen.append(mission_lock_key(primary, repo_root=repo))

    monkeypatch.setattr(module, "_seed_coord_surface_locked", _locked)
    request = SimpleNamespace(owned=None, repo_root=repo, mission_dir_name=COORD_NAME, root_mission_dir=primary, mission_slug=SLUG)
    module._seed_coord_surface(request)  # type: ignore[arg-type]
    assert seen == [COORD_NAME]


def test_an_owned_checkout_transaction_hold_is_found_from_the_main_repo_root(mission: Mission, tmp_path: Path) -> None:
    """The hold registered under the owned root is also registered under the main repo root (A4)."""
    repo, primary, _coord = mission
    owned_root = tmp_path / "owned"
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--allow-empty", "-q", "-m", "init")
    _git(repo, "worktree", "add", "-q", str(owned_root), "-b", "owned")
    with _transaction_hold(owned_root, COORD_NAME, SLUG, 5.0, main_root=repo):
        flatten_coordination_metadata(primary)
        assert mission_lock_key(primary, repo_root=repo) == COORD_NAME
