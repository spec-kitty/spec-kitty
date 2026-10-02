"""C-008: topology-less callers' verdict for decision-ledger paths (WP12, #5023).

Six call sites classify a path's coordination-residue status WITHOUT passing
an explicit ``topology`` to :func:`~specify_cli.coordination.coherence.
is_coord_residue_churn` / :func:`~specify_cli.coordination.coherence.
is_toolchain_generated_churn` -- its ``topology=None`` default is an EXPLICIT,
documented backward-compatible ``MissionTopology.COORD`` projection (see its
own docstring). Four of the six pass NEITHER a ``topology`` NOR a
``mission_slug`` at all (the truly "blind" shape):

- ``cli/commands/agent/tasks_move_task.py::_drop_lane_coord_residue``
- ``cli/commands/agent/tasks_shared.py::_list_wp_branch_mission_specs_changes``
- ``cli/commands/implement.py::_partition_files_for_commit`` /
  ``_guard_planning_commit_partition`` (two call sites, same file)
- ``lanes/auto_rebase.py::_is_coordination_owned_artifact``

Two pass ``mission_slug`` but not ``topology``:

- ``coordination/commit_router.py::partition_for_mission_path`` (deliberately
  topology-blind by its own docstring, to agree with
  ``_group_files_by_partition``'s grouping);
- ``consolidation/executor.py``'s post-merge invariant gate (via
  ``is_toolchain_generated_churn(path_part, mission_slug=run.mission_slug)``).

This file drives the FIRST FOUR plus ``commit_router`` through their own real
entry points (DIRECTIVE_041: assert the reader's observable decision, never
the shared predicate directly) on REAL Missions built through WP02's
production-create-path factory (``COORD``) and direct ``create_mission_core``
(``LANES`` / ``SINGLE_BRANCH``, which the factory does not produce).
``consolidation/executor``'s shape is covered in
``tests/mission_runtime/test_decision_ledger_reader_flips.py::
test_injected_residue_predicate_treats_ledger_as_real_work``.

**C-008 RULING (Decision Moment ``plan.design.ledger-topology-less-verdict``,
recorded in the ``design-decisions`` tracer; WP22 carries it into the ADR):**
an uncommitted ``decisions/*`` ledger file is REAL WORK, never residue, under
EVERY topology -- ``lanes`` and ``single_branch`` included, at every
topology-less caller. This is an accepted C-008 EXCEPTION: no compatibility
set, no ``coherence.py`` logic change. Every test below is therefore
parametrized over ``COORD`` / ``LANES`` / ``SINGLE_BRANCH`` and asserts the
SAME "real work" verdict for all three -- the ruling explicitly rejects
differentiating by topology at these call sites.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import create_mission_core
from tests._factories import provision_test_charter
from tests._factories.coord_mission import make_coord_mission
from tests._support.git_template import clone_template

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_TOPIC_BRANCH = "topic"
_NON_COORD_TOPOLOGIES = (MissionTopology.LANES, MissionTopology.SINGLE_BRANCH)
_ALL_TOPOLOGIES = (MissionTopology.COORD, *_NON_COORD_TOPOLOGIES)


def _mission_for(tmp_path: Path, topology: MissionTopology) -> tuple[Path, str]:
    """Build a real Mission under *topology*; return ``(repo_root, mission_dir_name)``.

    ``COORD`` uses WP02's :func:`make_coord_mission` factory (production create
    path). ``LANES`` / ``SINGLE_BRANCH`` (no coordination branch at all) are
    built directly via ``create_mission_core`` since the factory requires a
    coordination branch for every shape it produces.
    """
    if topology is MissionTopology.COORD:
        coord = make_coord_mission(tmp_path, topology)
        return coord.repo_root, coord.mission_dir_name
    repo = clone_template(tmp_path / "repo")
    provision_test_charter(repo)
    subprocess.run(["git", "-C", str(repo), "add", ".kittify"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "chore(fixture): provision charter"],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "-C", str(repo), "checkout", "-b", _TOPIC_BRANCH], check=True, capture_output=True)
    result = create_mission_core(repo, "topology-less", topology=topology, target_branch=_TOPIC_BRANCH, allow_worktree_context=True)
    mission_dir_name = result.meta["mission_slug"]
    assert isinstance(mission_dir_name, str)
    return repo, mission_dir_name


def _ledger_path(repo_root: Path, mission_dir_name: str) -> Path:
    path = repo_root / "kitty-specs" / mission_dir_name / "decisions" / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"entries": []}\n', encoding="utf-8")
    return path


@pytest.mark.parametrize("topology", _ALL_TOPOLOGIES)
def test_tasks_move_task_keeps_ledger_as_real_work(tmp_path: Path, topology: MissionTopology) -> None:
    """``tasks_move_task.py::_drop_lane_coord_residue`` (~L824), the truly blind
    shape (no mission_slug, no topology): a dirty ``decisions/index.json`` must
    be KEPT in the lane deliverable set, not dropped as coordination residue --
    for EVERY topology (C-008 ruling: ``plan.design.ledger-topology-less-verdict``).
    """
    from specify_cli.cli.commands.agent.tasks_move_task import _drop_lane_coord_residue

    repo_root, mission_dir_name = _mission_for(tmp_path, topology)
    index_path = _ledger_path(repo_root, mission_dir_name)

    kept = _drop_lane_coord_residue(repo_root, (index_path,))

    assert index_path in kept, (
        f"[{topology.value}] decisions/index.json was dropped as coordination "
        "residue by _drop_lane_coord_residue -- the PRIMARY-partition ledger is "
        "real lane work and must survive the Seam-A filter under every topology "
        "(FR-009, #5023, C-008 ruling)"
    )


@pytest.mark.parametrize("topology", _ALL_TOPOLOGIES)
def test_implement_partition_files_for_commit_classifies_ledger_primary(tmp_path: Path, topology: MissionTopology) -> None:
    """``implement.py::_partition_files_for_commit`` (~L905), the truly blind
    shape (bare path string, no mission_slug, no topology): the ledger joins
    the PRIMARY group, not the COORD-residue group -- for EVERY topology.
    """
    from specify_cli.cli.commands.implement import _partition_files_for_commit

    repo_root, mission_dir_name = _mission_for(tmp_path, topology)
    rel = f"kitty-specs/{mission_dir_name}/decisions/index.json"

    primary_files, coord_files = _partition_files_for_commit([rel])

    assert primary_files == [rel], (topology.value, primary_files, coord_files)
    assert coord_files == []


@pytest.mark.parametrize("topology", _ALL_TOPOLOGIES)
def test_implement_guard_refuses_ledger_reaching_coord_seam(tmp_path: Path, topology: MissionTopology) -> None:
    """``implement.py::_guard_planning_commit_partition`` (~L947), the truly
    blind shape: a PRIMARY-kind ledger path reaching a COORD-destination
    commit seam is now the FORBIDDEN PRIMARY→coord route (it was the
    permitted same-partition route pre-WP12); reaching a PRIMARY destination
    is the permitted route. Topology-independent by construction (the guard
    takes no Mission context at all), pinned for every topology regardless.
    """
    from specify_cli.cli.commands.implement import _guard_planning_commit_partition
    from specify_cli.coordination.commit_router import PrimaryKindReachedCoordStagingError

    repo_root, mission_dir_name = _mission_for(tmp_path, topology)
    rel = f"kitty-specs/{mission_dir_name}/decisions/index.json"

    with pytest.raises(PrimaryKindReachedCoordStagingError):
        _guard_planning_commit_partition([rel], destination_is_coord=True)

    # The mirror route (PRIMARY destination) is permitted -- no raise.
    _guard_planning_commit_partition([rel], destination_is_coord=False)


@pytest.mark.parametrize("topology", _ALL_TOPOLOGIES)
def test_auto_rebase_does_not_treat_ledger_as_coordination_owned(tmp_path: Path, topology: MissionTopology) -> None:
    """``lanes/auto_rebase.py::_is_coordination_owned_artifact`` (~L225), the
    truly blind shape (bare rel path): the ledger is neither surface residue
    nor managed PRIMARY layout, so auto-rebase does NOT take-theirs resolve a
    conflict on it -- it surfaces as a real (Manual-halt-eligible) conflict,
    matching "an uncommitted ledger file is real work, not residue" under
    every topology.
    """
    from specify_cli.lanes.auto_rebase import _is_coordination_owned_artifact

    repo_root, mission_dir_name = _mission_for(tmp_path, topology)
    rel = f"kitty-specs/{mission_dir_name}/decisions/index.json"

    assert _is_coordination_owned_artifact(rel) is False, topology.value


@pytest.mark.parametrize("topology", _ALL_TOPOLOGIES)
def test_commit_router_partition_for_mission_path_classifies_ledger_primary(tmp_path: Path, topology: MissionTopology) -> None:
    """``commit_router.py::partition_for_mission_path`` (~L768/937): passes
    ``mission_slug`` but deliberately never ``topology`` (its own docstring:
    topology-blind on purpose, to agree with ``_group_files_by_partition``'s
    grouping). The ledger now classifies "primary" for every topology.
    """
    from specify_cli.coordination.commit_router import partition_for_mission_path

    repo_root, mission_dir_name = _mission_for(tmp_path, topology)
    index_path = _ledger_path(repo_root, mission_dir_name)

    assert partition_for_mission_path(repo_root, mission_dir_name, index_path) == "primary", topology.value
