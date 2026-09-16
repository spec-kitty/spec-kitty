"""Readiness-gating coverage for the ``tasks_dependency_graph`` seam (WP05, #2058).

Fills the research-flagged readiness coverage gap (FR-003, FR-004):

- A WP whose dependent is still ``in_progress`` is surfaced as incomplete, so a
  for_review transition cannot silently proceed without the dependency alert.
- ``get_dependents`` surfaces direct dependents correctly through the seam.
- The planning-artifact-only behind-commit path returns True when upstream
  commits only touch planning/status files (so lane transitions are not blocked
  by metadata churn), and False when any source file changed.

These exercise the moved helpers directly, without driving the full
``move_task`` command flow.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.cli.commands.agent.tasks_dependency_graph import (
    _behind_commits_touch_only_planning_artifacts,
    _check_dependent_warnings,
    _count_behind_commits_outside_planning_artifacts,
    compute_incomplete_dependents,
)
from specify_cli.core.dependency_graph import get_dependents
from specify_cli.status import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_SLUG = "010-readiness-mission"


def _event(wp_id: str, from_lane: str, to_lane: str, event_id: str) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=MISSION_SLUG,
        wp_id=wp_id,
        from_lane=Lane(from_lane),
        to_lane=Lane(to_lane),
        at="2026-01-01T12:00:00+00:00",
        actor="test-agent",
        force=False,
        execution_mode="worktree",
    )


def _seed(feature_dir: Path, *events: StatusEvent) -> None:
    for ev in events:
        append_event(feature_dir, ev)


# ---------------------------------------------------------------------------
# compute_incomplete_dependents — readiness gating (FR-003 / FR-004)
# ---------------------------------------------------------------------------


def test_dependent_in_progress_is_incomplete(tmp_path: Path) -> None:
    """WP02 depends on WP01; WP02 is in_progress → surfaced as incomplete.

    This is the readiness gate: moving WP01 to for_review must report that a
    dependent is still mid-flight rather than treat it as complete.
    """
    graph = {"WP01": [], "WP02": ["WP01"]}
    _seed(
        tmp_path,
        _event("WP02", "planned", "claimed", "01HZCLAIM00000000000000001"),
        _event("WP02", "claimed", "in_progress", "01HZPROG000000000000000001"),
    )

    incomplete = compute_incomplete_dependents("WP01", tmp_path, graph)

    assert incomplete == ["WP02"]


def test_dependent_done_is_not_incomplete(tmp_path: Path) -> None:
    """A dependent that reached an advanced lane is not flagged as incomplete."""
    graph = {"WP01": [], "WP02": ["WP01"]}
    _seed(
        tmp_path,
        _event("WP02", "planned", "claimed", "01HZCLAIM00000000000000002"),
        _event("WP02", "claimed", "in_progress", "01HZPROG000000000000000002"),
        _event("WP02", "in_progress", "for_review", "01HZREVIEW0000000000000002"),
        _event("WP02", "for_review", "approved", "01HZAPPRV00000000000000002"),
    )

    incomplete = compute_incomplete_dependents("WP01", tmp_path, graph)

    assert incomplete == []


def test_no_dependents_returns_empty(tmp_path: Path) -> None:
    """A WP nobody depends on yields no incomplete dependents (and no event read)."""
    graph = {"WP01": [], "WP02": ["WP01"]}

    assert compute_incomplete_dependents("WP02", tmp_path, graph) == []


def test_missing_event_log_treats_dependents_as_planned(tmp_path: Path) -> None:
    """With no event log, dependents default to PLANNED → incomplete.

    Exercises the graceful-fallback branch where ``read_events`` finds nothing,
    so the lane map is empty and every dependent is treated as not-yet-done.
    """
    graph = {"WP01": [], "WP02": ["WP01"], "WP03": ["WP01"]}

    incomplete = compute_incomplete_dependents("WP01", tmp_path, graph)

    assert sorted(incomplete) == ["WP02", "WP03"]


def test_get_dependents_surfaces_direct_dependents() -> None:
    """``get_dependents`` (re-imported by the seam) returns direct dependents."""
    graph = {"WP01": [], "WP02": ["WP01"], "WP03": ["WP01"], "WP04": ["WP02"]}

    assert sorted(get_dependents("WP01", graph)) == ["WP02", "WP03"]
    assert get_dependents("WP02", graph) == ["WP04"]
    assert get_dependents("WP04", graph) == []


# ---------------------------------------------------------------------------
# _check_dependent_warnings — composition over the pure core
# ---------------------------------------------------------------------------


def test_check_dependent_warnings_skips_non_for_review() -> None:
    """No graph build, no resolution when the target lane is not for_review."""
    with patch(
        "specify_cli.cli.commands.agent.tasks_dependency_graph.build_dependency_graph"
    ) as build_mock:
        _check_dependent_warnings(Path("/repo"), MISSION_SLUG, "WP01", Lane.IN_PROGRESS, json_mode=False)
    build_mock.assert_not_called()


def test_check_dependent_warnings_skips_json_mode() -> None:
    """JSON mode suppresses the warning path entirely."""
    with patch(
        "specify_cli.cli.commands.agent.tasks_dependency_graph.build_dependency_graph"
    ) as build_mock:
        _check_dependent_warnings(Path("/repo"), MISSION_SLUG, "WP01", Lane.FOR_REVIEW, json_mode=True)
    build_mock.assert_not_called()


def test_check_dependent_warnings_emits_alert_for_incomplete_dependent(tmp_path: Path) -> None:
    """for_review with an in_progress dependent prints the dependency alert."""
    feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _seed(
        feature_dir,
        _event("WP02", "planned", "claimed", "01HZCLAIM00000000000000003"),
        _event("WP02", "claimed", "in_progress", "01HZPROG000000000000000003"),
    )

    dep_ws = MagicMock()
    dep_ws.branch_name = None  # planning-lane workspace branch
    seam = "specify_cli.cli.commands.agent.tasks_dependency_graph"
    # read-surface-ssot-closeout WP08 / FR-001: the STATUS leg now routes
    # through the late-imported ``mission_runtime.placement_seam(...)
    # .read_dir(STATUS_STATE)`` seam — stub the seam, not the retired
    # ``resolve_feature_dir_for_mission`` name.
    mock_seam = MagicMock()
    mock_seam.read_dir.return_value = feature_dir
    with (
        patch(f"{seam}.get_main_repo_root", return_value=tmp_path),
        patch("mission_runtime.placement_seam", return_value=mock_seam),
        patch(f"{seam}.build_dependency_graph", return_value={"WP01": [], "WP02": ["WP01"]}),
        patch(f"{seam}.resolve_workspace_for_wp", return_value=dep_ws),
        patch(f"{seam}.console") as console_mock,
    ):
        _check_dependent_warnings(tmp_path, MISSION_SLUG, "WP01", Lane.FOR_REVIEW, json_mode=False)

    printed = " ".join(str(call.args[0]) for call in console_mock.print.call_args_list if call.args)
    assert "Dependency Alert" in printed
    assert "WP02" in printed


def test_check_dependent_warnings_emits_rebase_commands_per_lane(tmp_path: Path) -> None:
    """Same-lane dependents get a 'shares branch' note; others get a rebase cmd."""
    feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _seed(
        feature_dir,
        _event("WP02", "planned", "in_progress", "01HZPROG000000000000000004"),
        _event("WP03", "planned", "in_progress", "01HZPROG000000000000000005"),
    )

    current_ws = MagicMock()
    current_ws.branch_name = "lane-current"
    same_lane_ws = MagicMock()
    same_lane_ws.branch_name = "lane-current"  # shares the WP01 branch
    other_lane_ws = MagicMock()
    other_lane_ws.branch_name = "lane-other"
    other_lane_ws.worktree_path = "/wt/other"

    def _resolve(_root: Path, _slug: str, wp: str) -> MagicMock:
        return {"WP01": current_ws, "WP02": same_lane_ws, "WP03": other_lane_ws}[wp]

    seam = "specify_cli.cli.commands.agent.tasks_dependency_graph"
    mock_seam = MagicMock()
    mock_seam.read_dir.return_value = feature_dir
    with (
        patch(f"{seam}.get_main_repo_root", return_value=tmp_path),
        patch("mission_runtime.placement_seam", return_value=mock_seam),
        patch(f"{seam}.build_dependency_graph", return_value={"WP01": [], "WP02": ["WP01"], "WP03": ["WP01"]}),
        patch(f"{seam}.resolve_workspace_for_wp", side_effect=_resolve),
        patch(f"{seam}.console") as console_mock,
    ):
        _check_dependent_warnings(tmp_path, MISSION_SLUG, "WP01", Lane.FOR_REVIEW, json_mode=False)

    printed = " ".join(str(call.args[0]) for call in console_mock.print.call_args_list if call.args)
    assert "WP02: shares lane-current" in printed
    assert "cd /wt/other && git rebase lane-current" in printed


def test_check_dependent_warnings_silent_on_graph_build_failure(tmp_path: Path) -> None:
    """A graph-build failure is swallowed and produces no alert (graceful)."""
    seam = "specify_cli.cli.commands.agent.tasks_dependency_graph"
    mock_seam = MagicMock()
    mock_seam.read_dir.return_value = tmp_path
    with (
        patch(f"{seam}.get_main_repo_root", return_value=tmp_path),
        patch("mission_runtime.placement_seam", return_value=mock_seam),
        patch(f"{seam}.build_dependency_graph", side_effect=RuntimeError("boom")),
        patch(f"{seam}.console") as console_mock,
    ):
        _check_dependent_warnings(tmp_path, MISSION_SLUG, "WP01", Lane.FOR_REVIEW, json_mode=False)

    console_mock.print.assert_not_called()


# ---------------------------------------------------------------------------
# _behind_commits_touch_only_planning_artifacts — planning-only fast path
# ---------------------------------------------------------------------------


def _subproc(returncode: int = 0, stdout: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    return m


def test_behind_commits_planning_only_returns_true(tmp_path: Path) -> None:
    """Upstream commits touching only kitty-specs/<mission>/ are non-blocking."""
    responses = [
        _subproc(returncode=0, stdout="abc123\n"),  # merge-base
        _subproc(
            returncode=0,
            stdout=f"kitty-specs/{MISSION_SLUG}/tasks.md\nkitty-specs/{MISSION_SLUG}/status.events.jsonl\n",
        ),
    ]
    with patch("subprocess.run", side_effect=responses):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", MISSION_SLUG)
    assert result is True


def test_behind_commits_source_change_returns_false(tmp_path: Path) -> None:
    """Any non-planning file in the behind set blocks the transition."""
    responses = [
        _subproc(returncode=0, stdout="abc123\n"),
        _subproc(returncode=0, stdout=f"kitty-specs/{MISSION_SLUG}/tasks.md\nsrc/specify_cli/foo.py\n"),
    ]
    with patch("subprocess.run", side_effect=responses):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", MISSION_SLUG)
    assert result is False


def test_behind_commits_detached_head_merge_base_failure(tmp_path: Path) -> None:
    """Detached HEAD / missing ref → merge-base fails → graceful False."""
    with patch("subprocess.run", return_value=_subproc(returncode=128, stdout="")):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "missing-ref", MISSION_SLUG)
    assert result is False


def test_behind_commits_empty_merge_base_returns_false(tmp_path: Path) -> None:
    """Empty merge-base output (no common ancestor) → graceful False."""
    with patch("subprocess.run", return_value=_subproc(returncode=0, stdout="\n")):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", MISSION_SLUG)
    assert result is False


def test_behind_commits_diff_subprocess_failure_returns_false(tmp_path: Path) -> None:
    """A failing diff subprocess → graceful False."""
    responses = [
        _subproc(returncode=0, stdout="abc123\n"),  # merge-base ok
        _subproc(returncode=129, stdout=""),  # diff fails
    ]
    with patch("subprocess.run", side_effect=responses):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", MISSION_SLUG)
    assert result is False


def test_behind_commits_no_changed_files_returns_true(tmp_path: Path) -> None:
    """Empty diff (already up to date) → True (non-blocking)."""
    responses = [
        _subproc(returncode=0, stdout="abc123\n"),
        _subproc(returncode=0, stdout="\n"),
    ]
    with patch("subprocess.run", side_effect=responses):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", MISSION_SLUG)
    assert result is True


def test_behind_commits_diffs_check_branch_not_head(tmp_path: Path) -> None:
    """Regression (F1, mission merge-base-diff-ssot-01KX44SD): the diff TARGET
    is ``check_branch``, not HEAD.

    ``_behind_commits_touch_only_planning_artifacts`` must compute its
    merge-base via the canonical two-ref ``git_merge_base`` primitive — never
    the HEAD-relative ``merge_base_changed_files`` convenience — and must diff
    ``merge_base..check_branch``, never ``merge_base..HEAD``, which would
    silently invert which commits are inspected.
    """
    recorded_cmds: list[list[str]] = []

    def _record(cmd: list[str], **_kwargs: object) -> MagicMock:
        recorded_cmds.append(list(cmd))
        if cmd[:2] == ["git", "merge-base"]:
            return _subproc(returncode=0, stdout="abc123\n")
        return _subproc(returncode=0, stdout="")

    with patch("subprocess.run", side_effect=_record):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "release/upstream", MISSION_SLUG)

    assert result is True  # empty diff → non-blocking

    diff_cmds = [cmd for cmd in recorded_cmds if cmd[:2] == ["git", "diff"]]
    assert len(diff_cmds) == 1, f"expected exactly one diff invocation, got {recorded_cmds!r}"
    # The consolidated site now routes through core.vcs.git.git_diff_names_checked,
    # which uses the two-arg <base> <head> form (equivalent to base..head for
    # --name-only). The diff TARGET must still be check_branch, never HEAD (F1).
    diff_base, diff_head = diff_cmds[0][-2], diff_cmds[0][-1]
    assert (diff_base, diff_head) == ("abc123", "release/upstream"), (
        f"diff must target merge_base..check_branch, not merge_base..HEAD (F1 regression): {diff_cmds[0]!r}"
    )
    assert "HEAD" not in diff_cmds[0], f"diff must not reference HEAD (F1): {diff_cmds[0]!r}"


# ---------------------------------------------------------------------------
# _behind_commits_touch_only_planning_artifacts — #3940 whole-tree ledger roots
# ---------------------------------------------------------------------------


def test_behind_commits_other_mission_ledger_is_non_blocking(tmp_path: Path) -> None:
    """#3940: ledger commits for OTHER missions on the target branch are
    planning-only — a missions-family branch carries the orchestrator's
    ledger for every mission on it, and none of it is source divergence."""
    responses = [
        _subproc(returncode=0, stdout="abc123\n"),  # merge-base
        _subproc(
            returncode=0,
            stdout=(
                f"kitty-specs/{MISSION_SLUG}/tasks.md\n"
                "kitty-specs/some-other-mission/status.events.jsonl\n"
                "kitty-specs/third-mission/plan.md\n"
            ),
        ),
    ]
    with patch("subprocess.run", side_effect=responses):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", MISSION_SLUG)
    assert result is True


def test_behind_commits_kittify_subtree_is_non_blocking(tmp_path: Path) -> None:
    """#3940: the whole ``.kittify/`` tree is ledger state, not just the
    previously-allowed ``workspaces/``/config subset."""
    responses = [
        _subproc(returncode=0, stdout="abc123\n"),  # merge-base
        _subproc(
            returncode=0,
            stdout=".kittify/workspaces/wp01.json\n.kittify/missions/state.json\n.kittify/config.yml\n",
        ),
    ]
    with patch("subprocess.run", side_effect=responses):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", MISSION_SLUG)
    assert result is True


def test_behind_commits_mixed_ledger_and_source_still_blocks(tmp_path: Path) -> None:
    """#3940 guard: broadening the ledger roots must not let real source
    divergence through."""
    responses = [
        _subproc(returncode=0, stdout="abc123\n"),  # merge-base
        _subproc(
            returncode=0,
            stdout="kitty-specs/other-mission/tasks.md\nsrc/specify_cli/foo.py\n",
        ),
    ]
    with patch("subprocess.run", side_effect=responses):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", MISSION_SLUG)
    assert result is False


# ---------------------------------------------------------------------------
# _count_behind_commits_outside_planning_artifacts — #3940 source-divergence count
# ---------------------------------------------------------------------------


def test_count_behind_commits_outside_ledger(tmp_path: Path) -> None:
    """Reports the pathspec-excluded count when it can be determined."""
    with patch("subprocess.run", return_value=_subproc(returncode=0, stdout="2\n")):
        result = _count_behind_commits_outside_planning_artifacts(tmp_path, "main", 88)
    assert result == 2


def test_count_behind_commits_failure_falls_back_to_raw_count(tmp_path: Path) -> None:
    """Fail-open fallback: an undeterminable count keeps the conservative raw
    behind count (the transition already blocks in that state)."""
    with patch("subprocess.run", return_value=_subproc(returncode=128, stdout="")):
        result = _count_behind_commits_outside_planning_artifacts(tmp_path, "main", 88)
    assert result == 88


def test_count_behind_commits_uses_ledger_excludes(tmp_path: Path) -> None:
    """The count pathspec excludes exactly the ledger roots, so the two
    #3940 helpers can never drift apart on what a ledger path is."""
    with patch("subprocess.run", return_value=_subproc(returncode=0, stdout="0\n")) as mock_run:
        _count_behind_commits_outside_planning_artifacts(tmp_path, "release/upstream", 7)
    cmd = mock_run.call_args.args[0]
    assert cmd[:3] == ["git", "rev-list", "--count"]
    assert "HEAD..release/upstream" in cmd
    assert cmd[-4:] == ["--", ".", ":(exclude)kitty-specs", ":(exclude).kittify"]
