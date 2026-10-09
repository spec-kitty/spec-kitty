"""Every Mission status writer locks the same file as ``status.emit`` (WP04 T020, plan A8 / A10).

Three writers keyed the lock on the Mission slug (``move-task``, ``mark-status``
and the lifecycle-event appenders), so on a Mission whose directory name
differs from its slug they took a different lock file than ``emit_status_transition``
and did not exclude it. The tracer appender (#5467) and the commit router's
``coord_status_lock`` must re-enter that same file: one lock path per Mission.

The fixture Mission has directory ``foo-01AAAAAA`` and slug ``foo``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

import specify_cli.cli.commands.agent.tasks as tasks_module
import specify_cli.cli.commands.agent.tasks_move_task_executor as move_task_module
import specify_cli.status.emit as emit_module
import specify_cli.status.lifecycle_events as lifecycle_module
from specify_cli.cli.commands.agent.tasks_mark_status import _ms_apply_updates
from specify_cli.coordination.status_transition import coord_status_lock
from specify_cli.missions._read_path_resolver import mission_write_lock_dir
from specify_cli.status import TransitionRequest, emit_status_transition, mission_write_lock
from specify_cli.status.locking import _get_thread_locks, feature_status_lock_path
from tests.status.conftest import seed_wp_to_planned

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

DIR_NAME = "foo-01AAAAAA"
SLUG = "foo"


@pytest.fixture
def mission(tmp_path: Path) -> tuple[Path, Path]:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    feature_dir = tmp_path / "kitty-specs" / DIR_NAME
    feature_dir.mkdir(parents=True)
    seed_wp_to_planned(feature_dir, "WP01", slug=SLUG)
    return tmp_path, feature_dir


class _Spy:
    """Records the lock file every ``feature_status_lock`` take resolves to."""

    def __init__(self, module: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        self.paths: list[Path] = []
        self._original = module.feature_status_lock
        monkeypatch.setattr(module, "feature_status_lock", self._record)

    @contextmanager
    def _record(self, root: Path, key: str, **kwargs: Any) -> Iterator[Path]:
        self.paths.append(feature_status_lock_path(root, key))
        with self._original(root, key, **kwargs) as held:
            yield held


def _emit_lock_path(repo: Path, feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    spy = _Spy(emit_module, monkeypatch)
    emit_status_transition(TransitionRequest(feature_dir=feature_dir, mission_slug=SLUG, wp_id="WP01", to_lane="claimed", actor="t"))
    assert len(set(spy.paths)) == 1
    assert spy.paths[0].name == f"{DIR_NAME}.status.lock"
    return spy.paths[0]


class _StopAfterLock(Exception):
    pass


@pytest.mark.parametrize("owned", [False, True], ids=["main-checkout", "owned-checkout"])
def test_move_task_locks_the_emit_lock_file(mission: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, owned: bool) -> None:
    repo, feature_dir = mission
    expected = _emit_lock_path(repo, feature_dir, monkeypatch)
    spy = _Spy(tasks_module, monkeypatch)

    def _stop(*_args: Any, **_kwargs: Any) -> None:
        raise _StopAfterLock

    monkeypatch.setattr(move_task_module, "_mt_emit_transitions", _stop)
    st: Any = SimpleNamespace(
        owned=SimpleNamespace(owned_root=repo) if owned else None,
        main_repo_root=repo,
        feature_dir=feature_dir,
        mission_slug=SLUG,
    )

    with pytest.raises(_StopAfterLock):
        move_task_module._mt_execute(st, SimpleNamespace())

    assert spy.paths == [expected]


@pytest.mark.parametrize("owned", [False, True], ids=["main-checkout", "owned-checkout"])
def test_mark_status_locks_the_emit_lock_file(mission: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, owned: bool) -> None:
    """The owned-checkout arm takes the lock too (it was a ``nullcontext``)."""
    repo, feature_dir = mission
    expected = _emit_lock_path(repo, feature_dir, monkeypatch)
    spy = _Spy(tasks_module, monkeypatch)
    monkeypatch.setattr(tasks_module, "_output_error", lambda *_a, **_k: None)
    st: Any = SimpleNamespace(
        owned=SimpleNamespace(owned_root=repo) if owned else None,
        main_repo_root=repo,
        feature_dir=feature_dir,
        mission_slug=SLUG,
        tasks_md=feature_dir / "tasks.md",  # absent: the phase exits right after taking the lock
        json_output=True,
    )

    with pytest.raises(typer.Exit):
        _ms_apply_updates(st, SimpleNamespace())

    assert spy.paths == [expected]


def test_lifecycle_appender_locks_the_emit_lock_file(mission: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir = mission
    expected = _emit_lock_path(repo, feature_dir, monkeypatch)
    spy = _Spy(lifecycle_module, monkeypatch)

    envelope = lifecycle_module.emit_wp_created_local(feature_dir, mission_slug=SLUG, wp_id="WP01", wp_title="t", repo_root=repo)

    assert envelope is not None
    assert spy.paths == [expected]


def test_tracer_lock_dir_is_the_mission_directory_name_and_reenters_coord_lock(mission: tuple[Path, Path]) -> None:
    """The tracer's key is the directory name, and the router's ``coord_status_lock`` re-enters it."""
    repo, feature_dir = mission
    (feature_dir / "meta.json").write_text('{"mission_slug": "foo", "mission_id": "01AAAAAAAAAAAAAAAAAAAAAAAA"}', encoding="utf-8")
    lock_dir = mission_write_lock_dir(repo, DIR_NAME)
    assert lock_dir == feature_dir

    with mission_write_lock(lock_dir, repo_root=repo) as held:
        before = set(_get_thread_locks())
        with coord_status_lock(repo, feature_dir) as inner:
            assert inner == held
            assert set(_get_thread_locks()) == before, "coord_status_lock took a second lock path"
        assert held == feature_status_lock_path(repo, DIR_NAME)


def test_tracer_lock_dir_for_a_slug_without_mid8(tmp_path: Path) -> None:
    """A Mission directory without a mid8 (legacy shape) keys on that directory name."""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    legacy = tmp_path / "kitty-specs" / "legacy-mission"
    legacy.mkdir(parents=True)
    (legacy / "meta.json").write_text('{"mission_slug": "legacy-mission"}', encoding="utf-8")

    assert mission_write_lock_dir(tmp_path, "legacy-mission").name == "legacy-mission"
    assert mission_write_lock_dir(tmp_path, "no-such-mission").name == "no-such-mission"


def test_tracer_lock_dir_on_a_real_coord_mission_is_the_coord_directory_name(tmp_path: Path) -> None:
    """The tracer key equals the directory name ``coord_status_lock`` takes on a coord Mission."""
    from tests.integration.coord_topology_fixture import _build_coord_topology

    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)

    lock_dir = mission_write_lock_dir(ctx.repo, ctx.slug)

    assert lock_dir.name == ctx.coord_feature_dir.name
    with mission_write_lock(lock_dir, repo_root=ctx.repo) as held:
        before = set(_get_thread_locks())
        with coord_status_lock(ctx.repo, ctx.coord_feature_dir) as inner:
            assert inner == held
            assert set(_get_thread_locks()) == before


# --- review-cycle allocation lock (WP05 review, rule-3 finding) -----------------


class _StopCycle(Exception):
    pass


def _record_lock_paths(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Record every lock file any ``feature_status_lock`` take resolves to."""
    import specify_cli.status.locking as locking_module

    paths: list[Path] = []
    original = locking_module.feature_status_lock_path

    def _record(root: Path, key: str) -> Path:
        paths.append(original(root, key))
        return paths[-1]

    monkeypatch.setattr(locking_module, "feature_status_lock_path", _record)
    return paths


def _cycle_lock_path(repo: Path, handle: str, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The lock file the review-cycle allocation takes for *handle* (stops right after the take)."""
    import specify_cli.review.cycle as cycle_module

    def _stop(**_kwargs: Any) -> None:
        raise _StopCycle

    monkeypatch.setattr(cycle_module, "_allocate_and_write_review_cycle_while_locked", _stop)
    paths = _record_lock_paths(monkeypatch)
    with pytest.raises(_StopCycle):
        cycle_module._allocate_and_write_review_cycle_locked(
            main_repo_root=repo,
            mission_slug=handle,
            wp_id="WP01",
            sub_artifact_dir=repo,
            reviewer_agent="r",
            affected_files=[],
            body="b",
        )
    assert len(set(paths)) == 1
    return paths[0]


@pytest.mark.parametrize("handle", [DIR_NAME, "01AAAAAA", SLUG], ids=["dir-name", "mid8", "slug"])
def test_review_cycle_locks_the_emit_lock_file(mission: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, handle: str) -> None:
    """On a Mission whose directory name differs from its slug the cycle take is ``emit``'s file."""
    repo, feature_dir = mission
    (feature_dir / "meta.json").write_text('{"mission_slug": "foo", "mission_id": "01AAAAAAAAAAAAAAAAAAAAAAAA"}', encoding="utf-8")
    expected = _emit_lock_path(repo, feature_dir, monkeypatch)

    assert _cycle_lock_path(repo, handle, monkeypatch) == expected


def test_review_cycle_lock_on_a_real_coord_mission_is_the_coord_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.integration.coord_topology_fixture import _build_coord_topology

    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)

    path = _cycle_lock_path(ctx.repo, ctx.slug, monkeypatch)

    assert path.name == f"{ctx.coord_feature_dir.name}.status.lock"
    with coord_status_lock(ctx.repo, ctx.coord_feature_dir) as held:
        assert held == path


# --- add-history (F6) -------------------------------------------------------------
#
# add-history no longer rewrites the WP-file markdown Activity Log under
# ``locked_rewrite_text``; it records the note as a plain (uncommitted)
# InnerStateChanged annotation via ``emit_inner_state_changed`` (#2334, end
# state (ii)), resolving its STATUS surface through the SAME ``write_dir``
# write-location accessor move-task's ``feature_write_dir`` uses. The retired
# markdown-write lock tests were removed with that code path; that add-history
# records on the authoritative coord surface (and so locks the coord Mission
# directory name) is covered by
# ``test_add_history_on_a_coord_mission_records_to_the_coord_surface`` in
# tests/specify_cli/cli/commands/agent/test_add_history_event_log.py.


# --- implement claim (#5819): one Mission, one lock across both claim paths -----------


def test_implement_claim_hold_locks_the_directory_agent_action_implement_locks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A coord Mission with a legacy primary directory name (``foo``) has a coord directory ``foo-<mid8>``.

    ``agent action implement`` locks the coord directory; ``implement`` must take the same file,
    or the two claim paths no longer exclude each other on that Mission.
    """
    import json
    from contextlib import ExitStack

    import specify_cli.status.mission_write as mission_write_module
    from specify_cli.cli.commands import implement_phases
    from specify_cli.cli.commands.agent import workflow_executor
    from specify_cli.coordination.workspace import CoordinationWorkspace
    from tests.integration.coord_topology_fixture import _git, _make_git_repo

    repo = _make_git_repo(tmp_path / "legacy-coord")
    mid8, branch = "01AAAAAA", "kitty/mission-foo-01AAAAAA"
    _git(repo, "branch", branch)
    primary = repo / "kitty-specs" / SLUG
    primary.mkdir(parents=True)
    meta = {"mission_id": "01AAAAAAAAAAAAAAAAAAAAAAAA", "mission_slug": SLUG, "topology": "coord", "coordination_branch": branch, "target_branch": "main"}
    (primary / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    coord_dir = CoordinationWorkspace.resolve(repo, SLUG, mid8) / "kitty-specs" / DIR_NAME
    coord_dir.mkdir(parents=True)
    assert workflow_executor.claim_status_dir(repo, SLUG) == coord_dir

    spy = _Spy(mission_write_module, monkeypatch)
    ctx: Any = SimpleNamespace(repo_root=repo, mission_slug=SLUG, mission_dir=primary)

    with ExitStack() as stack:
        implement_phases.hold_mission_write_lock(stack, ctx)

    assert spy.paths == [feature_status_lock_path(repo, DIR_NAME)]
