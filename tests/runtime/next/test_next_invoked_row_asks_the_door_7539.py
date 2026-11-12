"""The ``MissionNextInvoked`` row's landed routing asks the status read door (#7539 item 3).

Pre-PR squad row 11: ``next_invocation_lifecycle`` decided "landed" with its own
``mission_has_landed`` beside the door's ``CONSOLIDATED_TARGET`` decision. The row now follows the
door: a ``CONSOLIDATED_TARGET`` surface names the directory, anything else goes through the status
write seam. Only a terminal or blocked decision asks the door (squad fold 1): a landed Mission answers
with one of them. The end-to-end cells (landed, in flight, owned) stay pinned in
``test_materialization_report``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import specify_cli.status as status_package
from mission_runtime import MissionTopology
from runtime.next import next_invocation_lifecycle as lifecycle
from specify_cli.status import StatusReadSource, StatusReadSurface

pytestmark = pytest.mark.fast

SLUG = "row-door-7539"


def _surface(source: StatusReadSource, path: Path) -> StatusReadSurface:
    return StatusReadSurface(
        topology=MissionTopology.COORD,
        source=source,
        mission_dir_name=SLUG,
        path=path,
        repo_root=path.parent,
        ref=None,
    )


def _stub_write_seam(monkeypatch: pytest.MonkeyPatch, write_dir: Path) -> list[object]:
    writes: list[object] = []

    def _write_dir(kind: object) -> SimpleNamespace:
        writes.append(kind)
        return SimpleNamespace(path=write_dir, surface_root=write_dir.parent, surface=None)

    seam = SimpleNamespace(write_dir=_write_dir, read_dir=lambda _kind: pytest.fail("the row reads no PRIMARY dir"))
    monkeypatch.setattr(lifecycle, "placement_seam", lambda *_args, **_kwargs: seam)
    return writes


def test_a_consolidated_target_surface_names_the_rows_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target_dir = tmp_path / "target" / SLUG
    target_dir.mkdir(parents=True)
    writes = _stub_write_seam(monkeypatch, tmp_path / "coord")
    monkeypatch.setattr(status_package, "resolve_status_read", lambda *_a, **_k: _surface(StatusReadSource.CONSOLIDATED_TARGET, target_dir))

    assert lifecycle._mission_next_invoked_dir(tmp_path, SLUG, None, may_be_landed=True)[0] == target_dir
    assert writes == []


def test_any_other_surface_goes_through_the_write_seam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    coord_dir = tmp_path / "coord" / SLUG
    coord_dir.mkdir(parents=True)
    write_dir = tmp_path / "written"
    writes = _stub_write_seam(monkeypatch, write_dir)
    monkeypatch.setattr(status_package, "resolve_status_read", lambda *_a, **_k: _surface(StatusReadSource.COORD_WORKTREE, coord_dir))

    assert lifecycle._mission_next_invoked_dir(tmp_path, SLUG, None, may_be_landed=True)[0] == write_dir
    assert len(writes) == 1


def test_a_door_that_cannot_answer_goes_through_the_write_seam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The write seam keeps its own outcome (and its own error) for a Mission the door cannot read."""

    def _not_found(*_args: Any, **_kwargs: Any) -> Any:
        raise FileNotFoundError("meta.json not found")

    write_dir = tmp_path / "written"
    writes = _stub_write_seam(monkeypatch, write_dir)
    monkeypatch.setattr(status_package, "resolve_status_read", _not_found)

    assert lifecycle._mission_next_invoked_dir(tmp_path, SLUG, None, may_be_landed=True)[0] == write_dir
    assert len(writes) == 1


def test_a_non_terminal_decision_never_asks_the_door(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_dir = tmp_path / "written"
    writes = _stub_write_seam(monkeypatch, write_dir)
    monkeypatch.setattr(status_package, "resolve_status_read", lambda *_a, **_k: pytest.fail("a non-terminal row reads no door"))

    assert lifecycle._mission_next_invoked_dir(tmp_path, SLUG, None, may_be_landed=False)[0] == write_dir
    assert len(writes) == 1


def test_a_blocked_decision_on_a_landed_mission_names_the_target_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An owned call whose coordination checkout is torn down answers ``blocked``, not ``terminal``."""
    target_dir = tmp_path / "target" / SLUG
    target_dir.mkdir(parents=True)
    writes = _stub_write_seam(monkeypatch, tmp_path / "coord")
    monkeypatch.setattr(status_package, "resolve_status_read", lambda *_a, **_k: _surface(StatusReadSource.CONSOLIDATED_TARGET, target_dir))
    appended: list[Path | None] = []
    monkeypatch.setattr("specify_cli.mission_v1.events.emit_event", lambda *_a, feature_dir=None, **_k: appended.append(feature_dir))
    decision = SimpleNamespace(kind="blocked", action=None, wp_id=None, mission_state="x", mission=SLUG)

    lifecycle.emit_mission_next_invoked("pedro", "success", SLUG, tmp_path, decision)

    assert appended == [target_dir]
    assert writes == []
