"""``next`` bootstrap reads the status read door (WP05, #7310).

Mission ``runtime-status-read-door-01M73HHB`` (FR-001, FR-006).

FR-001: an advancing ``next`` on a non-owned coordination Mission reports the progress committed
on the coordination branch whether its worktree is materialized, empty or unmaterialized.

FR-006 characterisation (analysis finding I1): an advancing ``next`` on an **owned** coordination
Mission keeps today's dispatch outcome. Pinned on the WP04 owned matrix Mission (WP01
``in_progress`` committed on the coordination branch), for ``coord`` and ``lanes_with_coord``:

* **empty** coordination worktree (the Mission directory removed from it): the owned context
  build refuses, so bootstrap returns the typed ``blocked`` decision
  ``OWNED_COORDINATION_WORKSPACE_UNAVAILABLE``;
* **unmaterialized** coordination worktree (the worktree removed): the decision-log wrap
  materializes it, and dispatch proceeds (``kind == step``, no error code).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionTopology, OwnedRefusalCode
from runtime.next.runtime_bridge import decide_next_via_runtime
from tests.runtime._next_mission_scaffold import analysis_is_current
from tests.runtime.next.test_board_query_read_door_7507 import (
    _EXPECTED_PROGRESS,
    COORD_TOPOLOGIES,
    EMPTY,
    MATERIALIZED,
    UNMATERIALIZED,
    _coord_cell_mission,
    _owned_coordination_mission,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_owned_advance_on_an_empty_coordination_worktree_refuses(tmp_path: Path, topology: MissionTopology) -> None:
    repo, fact = _owned_coordination_mission(tmp_path, topology, EMPTY)

    decision = decide_next_via_runtime("pedro", fact.mission_slug, "success", repo, owned=fact)

    assert str(decision.kind) == "blocked"
    assert decision.error_code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value
    assert (decision.reason or "").startswith(f"Coordination worktree registry is unavailable for mission {fact.mission_slug!r}")


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_owned_advance_on_an_unmaterialized_coordination_worktree_proceeds(tmp_path: Path, topology: MissionTopology) -> None:
    repo, fact = _owned_coordination_mission(tmp_path, topology, UNMATERIALIZED)

    decision = decide_next_via_runtime("pedro", fact.mission_slug, "success", repo, owned=fact)

    # The wrap proceeds to the board. WP01 is in_progress, so the never-rewind gate answers with
    # the board's state instead of the DAG's ``discovery`` (#5929, #7565; FR-016).
    assert decision.error_code != OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value
    assert str(decision.kind) == "blocked", decision.reason
    assert decision.error_code == "BOARD_STEP_NOT_DISPATCHABLE", decision.reason
    assert decision.next_command == f"spec-kitty agent action implement WP01 --agent pedro --mission {fact.mission_slug}"


# ---------------------------------------------------------------------------
# T026 (FR-001, red first): advancing progress reads the door after the wrap
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cell", [MATERIALIZED, EMPTY, UNMATERIALIZED])
@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_advancing_progress_reports_the_committed_lanes(tmp_path: Path, topology: MissionTopology, cell: str) -> None:
    """The #7507 cells through an advancing decision: every cell reports the committed board.

    Before WP05 the progress came from bootstrap's status directory: the coordination worktree,
    which holds no ``tasks/`` (no progress at all when materialized), or the root checkout's
    primary copy (zero lanes and 0.0 when empty or unmaterialized).
    """
    repo, slug = _coord_cell_mission(tmp_path, topology, cell)

    decision = decide_next_via_runtime("pedro", slug, "success", repo, analysis_currency=analysis_is_current)

    assert decision.progress == _EXPECTED_PROGRESS, (decision.kind, decision.reason)


@pytest.mark.parametrize("error", ["registry", "ref"])
def test_owned_door_failure_after_the_wrap_is_the_typed_blocked_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: str) -> None:
    """The door's own failures map to the O8 typed ``blocked`` decision, never a traceback.

    The decision-log wrap materializes the worktree first; the door read that follows is the
    only thing that fails here (the hazard of code-grounding §3).
    """
    from specify_cli.coordination.status_service import StatusSurfaceRefUnreadable
    from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable
    import specify_cli.status as status_package
    from specify_cli.status import read_surface

    repo, fact = _owned_coordination_mission(tmp_path, MissionTopology.LANES_WITH_COORD, UNMATERIALIZED)
    real = read_surface.resolve_status_read

    def _failing(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("owned") is None:
            return real(*args, **kwargs)
        if error == "registry":
            raise WorktreeRegistryUnavailable(repo_root=repo, detail="injected worktree-list failure")
        raise StatusSurfaceRefUnreadable(repo_root=repo, ref="refs/heads/x", path="kitty-specs/m/status.events.jsonl", detail="bad object")

    monkeypatch.setattr(status_package, "resolve_status_read", _failing)

    decision = decide_next_via_runtime("pedro", fact.mission_slug, "success", repo, owned=fact)

    assert str(decision.kind) == "blocked"
    assert decision.error_code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value


@pytest.mark.parametrize("error", ["registry", "ref"])
def test_non_owned_door_failure_is_a_typed_blocked_decision_not_stale_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: str) -> None:
    """A non-owned bootstrap whose door read fails blocks with the cause's own code (as the board does)."""
    from specify_cli.coordination.status_service import StatusSurfaceRefUnreadable
    from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable
    import specify_cli.status as status_package

    repo, slug = _coord_cell_mission(tmp_path, MissionTopology.COORD, MATERIALIZED)

    def _failing(*args: Any, **kwargs: Any) -> Any:
        if error == "registry":
            raise WorktreeRegistryUnavailable(repo_root=repo, detail="injected worktree-list failure")
        raise StatusSurfaceRefUnreadable(repo_root=repo, ref="refs/heads/x", path="kitty-specs/m/status.events.jsonl", detail="bad object")

    monkeypatch.setattr(status_package, "resolve_status_read", _failing)

    decision = decide_next_via_runtime("pedro", slug, "success", repo, analysis_currency=analysis_is_current)

    assert str(decision.kind) == "blocked"
    assert decision.error_code == ("WORKTREE_REGISTRY_UNAVAILABLE" if error == "registry" else "STATUS_SURFACE_REF_UNREADABLE")
