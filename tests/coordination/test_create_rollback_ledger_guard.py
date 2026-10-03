"""A create-time rollback is not blocked by the coordination-ledger teardown guard.

``teardown_coordination_topology`` refuses (``COORDINATION_LEDGER_UNREPAIRED``)
while the decisions ledger exists only on the coordination branch. The two
create-time rollback callers discard a coordination surface that the create
itself owns, so they pass ``check_ledger=False`` and must still remove the
coordination worktree in that state. A normal teardown of the very same state
(``mission close --discard`` / ``consolidate --abort`` keep the default) still
refuses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionTopology
from specify_cli.coordination.teardown import (
    ProjectionTeardownAbort,
    teardown_coordination_topology,
)
from tests._factories.coord_mission import ForkFixture, make_fork_fixture

pytestmark = pytest.mark.fast


def _ledger_only_fixture(tmp_path: Path) -> ForkFixture:
    return make_fork_fixture(tmp_path, "ledger_only_on_coordination", MissionTopology.COORD)


def test_normal_teardown_of_a_coordination_only_ledger_still_refuses(tmp_path: Path) -> None:
    fixture = _ledger_only_fixture(tmp_path)

    with pytest.raises(ProjectionTeardownAbort) as excinfo:
        teardown_coordination_topology(fixture.repo_root, fixture.mission_dir_name, fixture.mid8, persist=False)

    assert excinfo.value.error_code == "COORDINATION_LEDGER_UNREPAIRED"
    assert fixture.coord_worktree_path.exists(), "a refused teardown must leave the worktree"


def test_create_rollback_is_not_refused_by_a_coordination_only_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``_rollback_coordination_surface`` skips the ledger guard.

    The rollback clears the coordination Mission dir before tearing down, so a
    *committed* ledger shows up as tracked deletions and the destroy leg itself
    (a separate, swallowed dirty-worktree refusal) cannot remove the worktree
    in this fixture. What this fold changes is only the ledger guard, so the
    test asserts exactly that: the real seam is invoked with
    ``check_ledger=False`` and raises no ``COORDINATION_LEDGER_UNREPAIRED``.
    """
    import specify_cli.coordination.teardown as teardown_module
    from specify_cli.core.mission_creation import (
        _CoordCreateRollbackContext,
        _rollback_coordination_surface,
    )

    fixture = _ledger_only_fixture(tmp_path)
    real_teardown = teardown_module.teardown_coordination_topology
    calls: list[dict[str, object]] = []
    aborts: list[ProjectionTeardownAbort] = []

    def _spy(repo_root: Path, mission_slug: str, mid8: str, **kwargs: Any) -> bool:
        calls.append(dict(kwargs))
        try:
            result: bool = real_teardown(repo_root, mission_slug, mid8, **kwargs)
            return result
        except ProjectionTeardownAbort as exc:
            aborts.append(exc)
            raise

    monkeypatch.setattr(teardown_module, "teardown_coordination_topology", _spy)

    _rollback_coordination_surface(
        _CoordCreateRollbackContext(
            repo_root=fixture.repo_root,
            mission_slug_formatted=fixture.mission_dir_name,
            mid8=fixture.mid8,
            coordination_branch=fixture.coordination_branch,
            coordination_branch_created=True,
        )
    )

    assert len(calls) == 1
    assert calls[0]["check_ledger"] is False
    assert aborts == []


def test_force_recreate_teardown_removes_the_coordination_worktree_despite_a_coordination_only_ledger(
    tmp_path: Path,
) -> None:
    from specify_cli.missions._create import _teardown_coordination_worktree_if_present

    fixture = _ledger_only_fixture(tmp_path)
    meta = json.loads((fixture.root_mission_dir / "meta.json").read_text(encoding="utf-8"))
    assert fixture.coord_worktree_path.exists()

    _teardown_coordination_worktree_if_present(fixture.repo_root, fixture.mission_dir_name, meta["mission_id"])

    assert not fixture.coord_worktree_path.exists()
