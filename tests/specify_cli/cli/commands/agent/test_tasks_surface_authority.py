"""WP03 characterization: the task commands consult ONE shared authoritative-surface rule.

Mission ``coord-commit-surface-authority-01M1M553`` (#2300). Proves that the
commit-bearing ``agent tasks`` commands DERIVE their commit-surface verdict from
the single ``resolve_surface_authority`` rule instead of hardcoding divergent
per-command logic:

* ``move-task`` (lifecycle-kind) — ``_skip_target_branch_commit`` returns the
  :class:`RouteToCoord` skip (exit 0) under coord + protected primary.
* ``map-requirements`` (planning-kind) — ``_protected_branch_status_commit_error``
  returns the :class:`Refuse` (exit 1) with the SHARED remedy constant under a
  protected primary.
* ``mark-status`` — frozen event-log-only: NO commit path (proven with a
  non-fakeable ``commit_for_mission`` spy AND a HEAD-unchanged assertion, while
  the event log IS written and the command exits 0).

The exit-code rows (genuine-no-op → 0, wrong-surface → 1 not collapsed) are
asserted through the canonical ``_exit_code_for`` / ``_classify_noncommit_outcome``
mapping — the same single source the CLI uses. (The WP01 golden harness that once
froze these rows was retired; its commit-router rows live in
``tests/coordination/test_commit_router*.py``.)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionArtifactKind, MissionTopology
from specify_cli.coordination.surface_authority import (
    REMEDY_PROTECTED_PRIMARY,
    Refuse,
    RouteToCoord,
    _classify_noncommit_outcome,
    _exit_code_for,
    resolve_surface_authority,
)
from specify_cli.git.protection_policy import ProtectionPolicy

from tests.git.protected_target_fixtures import (  # noqa: F401 — pytest fixture re-export
    ProtectedTargetRepo,
    protected_target_repo,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_TASKS = "specify_cli.cli.commands.agent.tasks"
_PRIMARY_BRANCH = "main"


def _policy(*, protected: bool) -> ProtectionPolicy:
    branches = frozenset({_PRIMARY_BRANCH}) if protected else frozenset()
    return ProtectionPolicy(protected_branches=branches, operator_hatch_active=False)


# ---------------------------------------------------------------------------
# move-task (lifecycle-kind): _skip_target_branch_commit derives RouteToCoord.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("coord_active", "protected", "expected_skip"),
    [
        (True, True, True),  # rule 1: coord + protected → RouteToCoord → skip (exit 0)
        (True, False, False),  # rule 2: coord + unprotected → committable → no skip
        (False, True, False),  # no coord route → not a RouteToCoord (short-circuit, no policy I/O)
        (False, False, False),
    ],
)
def test_skip_helper_derives_route_to_coord_via_shared_rule(tmp_path: Path, coord_active: bool, protected: bool, expected_skip: bool) -> None:
    """``_skip_target_branch_commit`` mirrors the shared rule's RouteToCoord verdict.

    The lifecycle-kind (STATUS_STATE) under a coord-routing topology with a
    protected primary is exactly ``resolve_surface_authority``'s rule-1
    RouteToCoord — and the helper's boolean tracks it. When no coord worktree
    exists the protection resolve is short-circuited entirely (contract: no policy
    I/O on flat missions).
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_shared import _skip_target_branch_commit

    with (
        patch.object(_tasks, "_coord_topology_active", return_value=coord_active) as coord_mock,
        patch.object(_tasks.ProtectionPolicy, "resolve", return_value=_policy(protected=protected)),
    ):
        skip = _skip_target_branch_commit(tmp_path, "001-my-mission", _PRIMARY_BRANCH)

    assert skip is expected_skip
    coord_mock.assert_called_once_with(tmp_path, "001-my-mission")

    # The helper's verdict is the SAME one the shared rule produces for the
    # lifecycle-kind under the equivalent {topology, protection}.
    topology = MissionTopology.COORD if coord_active else MissionTopology.SINGLE_BRANCH
    verdict = resolve_surface_authority(
        topology=topology,
        primary_target=_PRIMARY_BRANCH,
        primary_protected=protected,
        current_branch=_PRIMARY_BRANCH,
        artifact_kind=MissionArtifactKind.STATUS_STATE,
    )
    assert isinstance(verdict.non_committable, RouteToCoord) is expected_skip
    if expected_skip:
        # RouteToCoord is an exit-0 outcome (the coord commit is authoritative).
        assert _exit_code_for(verdict.non_committable) == 0


# ---------------------------------------------------------------------------
# map-requirements (planning-kind): _protected_branch_status_commit_error → Refuse.
# ---------------------------------------------------------------------------


def test_protected_error_derives_refuse_with_shared_remedy(tmp_path: Path) -> None:
    """Planning-kind on a protected primary → Refuse (exit 1), remedy = shared constant."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_shared import (
        _protected_branch_status_commit_error,
    )

    with patch.object(_tasks.ProtectionPolicy, "resolve", return_value=_policy(protected=True)):
        message = _protected_branch_status_commit_error(_PRIMARY_BRANCH, tmp_path, "spec-kitty agent tasks map-requirements")

    assert message is not None
    assert "map-requirements" in message
    assert f"'{_PRIMARY_BRANCH}'" in message
    # Remedy unified to the ONE shared constant (no per-command drift).
    assert REMEDY_PROTECTED_PRIMARY in message

    # The refuse verdict + its exit code come from the shared rule.
    verdict = resolve_surface_authority(
        topology=MissionTopology.SINGLE_BRANCH,
        primary_target=_PRIMARY_BRANCH,
        primary_protected=True,
        current_branch=_PRIMARY_BRANCH,
        artifact_kind=MissionArtifactKind.WORK_PACKAGE_TASK,
    )
    assert isinstance(verdict.non_committable, Refuse)
    assert _exit_code_for(verdict.non_committable) == 1


def test_protected_error_none_on_unprotected_primary(tmp_path: Path) -> None:
    """Unprotected primary → committable → no refusal (``None``)."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_shared import (
        _protected_branch_status_commit_error,
    )

    with patch.object(_tasks.ProtectionPolicy, "resolve", return_value=_policy(protected=False)):
        message = _protected_branch_status_commit_error(_PRIMARY_BRANCH, tmp_path, "spec-kitty agent tasks map-requirements")
    assert message is None


def test_map_requirements_cli_refuses_exit1_on_protected(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """CLI-level diff: ``map-requirements --auto-commit`` on protected main exits 1.

    The refuse comes through ``_protected_branch_status_commit_error`` (now
    shared-rule-derived) before any frontmatter write. Nothing lands on the
    protected ref.
    """
    from specify_cli.cli.commands.agent.tasks import app

    repo = protected_target_repo
    slug = "001-surface-authority"
    mission_dir = repo.repo_root / "kitty-specs" / slug
    (mission_dir / "tasks").mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_id": "01SURFACEAUTHORITYMISSION0"}), encoding="utf-8")
    (mission_dir / "spec.md").write_text("# Spec\n\n- FR-001: do a thing\n", encoding="utf-8")
    (mission_dir / "tasks" / "WP01-thing.md").write_text("---\nwork_package_id: WP01\n---\n# WP01\n", encoding="utf-8")

    head_before = _head_sha(repo.repo_root)
    runner = CliRunner()
    with (
        patch(f"{_TASKS}.locate_project_root", return_value=repo.repo_root),
        patch(f"{_TASKS}._find_mission_slug", return_value=slug),
        patch(
            f"{_TASKS}._ensure_target_branch_checked_out",
            return_value=(repo.repo_root, repo.target_branch),
        ),
        patch(f"{_TASKS}._emit_sparse_session_warning"),
    ):
        result = runner.invoke(
            app,
            [
                "map-requirements",
                "--wp",
                "WP01",
                "--refs",
                "FR-001",
                "--mission",
                slug,
                "--auto-commit",
                "--json",
            ],
        )

    assert result.exit_code == 1, result.output
    assert _head_sha(repo.repo_root) == head_before


# ---------------------------------------------------------------------------
# INV-4: same {kind, topology, protection} → same verdict via the shared rule;
# exit codes differ legitimately BY KIND, never by hardcoded per-command logic.
# ---------------------------------------------------------------------------


def test_same_inputs_same_rule_exit_codes_differ_by_kind() -> None:
    """Coord + protected primary: lifecycle → RouteToCoord/exit-0; planning → Refuse/exit-1."""
    lifecycle = resolve_surface_authority(
        topology=MissionTopology.COORD,
        primary_target=_PRIMARY_BRANCH,
        primary_protected=True,
        current_branch=_PRIMARY_BRANCH,
        artifact_kind=MissionArtifactKind.STATUS_STATE,
    )
    planning = resolve_surface_authority(
        topology=MissionTopology.COORD,
        primary_target=_PRIMARY_BRANCH,
        primary_protected=True,
        current_branch=_PRIMARY_BRANCH,
        artifact_kind=MissionArtifactKind.WORK_PACKAGE_TASK,
    )
    assert isinstance(lifecycle.non_committable, RouteToCoord)
    assert _exit_code_for(lifecycle.non_committable) == 0
    assert isinstance(planning.non_committable, Refuse)
    assert _exit_code_for(planning.non_committable) == 1


def test_no_op_exit0_and_wrong_surface_exit1_not_collapsed() -> None:
    """Genuine no-op → exit 0 (typed reason); wrong-surface → Refuse/exit 1 (never collapsed)."""
    no_op = _classify_noncommit_outcome("unchanged", "no_op_no_changes")
    assert _exit_code_for(no_op) == 0
    assert getattr(no_op, "reason", None) == "no_op_no_changes"

    wrong_surface = _classify_noncommit_outcome("no_op_wrong_surface")
    assert isinstance(wrong_surface, Refuse)
    assert _exit_code_for(wrong_surface) == 1, "wrong-surface must NOT collapse to exit 0"


# ---------------------------------------------------------------------------
# T012 — mark-status frozen no-commit (non-fakeable: commit_for_mission spy +
# HEAD unchanged, while the event log IS written and exit is 0).
# ---------------------------------------------------------------------------


def _head_sha(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.mark.git_repo
def test_mark_status_is_frozen_no_commit(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """``mark-status --auto-commit`` writes the event log but NEVER commits.

    Non-fakeable: exit-code-only would be forgeable, so this asserts BOTH that
    ``commit_for_mission`` (the seam ``_do_mark_status`` would route through) is
    never invoked AND that ``git rev-parse HEAD`` is unchanged across the call —
    while proving the event log WAS written (event-log-only) and the command
    exits 0.
    """
    repo = protected_target_repo
    slug = "001-frozen-no-commit"
    mission_dir = repo.repo_root / "kitty-specs" / slug
    (mission_dir / "tasks").mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_id": "01FROZENNOCOMMITMISSION000"}), encoding="utf-8")
    (mission_dir / "tasks.md").write_text("# Tasks\n\n## WP01\nSubtasks: T001\n", encoding="utf-8")
    (mission_dir / "tasks" / "WP01-thing.md").write_text("---\nwork_package_id: WP01\nsubtasks:\n- T001\n---\n# WP01\n", encoding="utf-8")

    from specify_cli.cli.commands.agent.tasks import app

    head_before = _head_sha(repo.repo_root)
    events_file = mission_dir / "status.events.jsonl"

    runner = CliRunner()
    # Spy on BOTH the canonical entry point and the tasks-namespace re-export seam
    # the coord router would route through; either being called is a #2816 revival.
    with (
        patch(f"{_TASKS}.locate_project_root", return_value=repo.repo_root),
        patch(f"{_TASKS}._find_mission_slug", return_value=slug),
        patch(
            f"{_TASKS}._ensure_target_branch_checked_out",
            return_value=(repo.repo_root, repo.target_branch),
        ),
        patch(f"{_TASKS}._emit_sparse_session_warning"),
        patch("specify_cli.coordination.commit_router.commit_for_mission") as router_commit_spy,
        patch(f"{_TASKS}.commit_for_mission") as seam_commit_spy,
    ):
        result = runner.invoke(
            app,
            [
                "mark-status",
                "T001",
                "--status",
                "done",
                "--mission",
                slug,
                "--auto-commit",
                "--json",
            ],
        )

    assert result.exit_code == 0, result.output
    # (a) The commit seam was never invoked (no-commit is structural, not incidental).
    router_commit_spy.assert_not_called()
    seam_commit_spy.assert_not_called()
    # (b) HEAD is byte-identical — no commit landed on the protected target.
    assert _head_sha(repo.repo_root) == head_before, "event-only mark-status landed a commit on the protected target"
    # (c) The event log WAS written — completion is event-sourced, not committed.
    assert events_file.exists(), "mark-status did not append the canonical status event"
    assert events_file.read_text(encoding="utf-8").strip(), "status event log is empty"
