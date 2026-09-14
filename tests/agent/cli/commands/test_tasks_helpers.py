"""Unit tests for agent/tasks.py helper functions.

Covers uncovered lines in the pure-logic and lightly-mocked helpers
without requiring a running git repo or full CLI invocation.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import specify_cli.cli.commands.agent.tasks as tasks_module
from specify_cli.cli.commands.agent.tasks import (
    _behind_commits_touch_only_planning_artifacts,
    _check_unchecked_subtasks,
    _collect_status_artifacts,
    _detect_reviewer_name,
    _issue_matrix_approval_blocker,
    _is_pipe_table_task_row,
    _output_error,
    _output_result,
    _parse_pipe_table_header,
    _resolve_git_common_dir,
    _resolve_wp_slug,
)
from specify_cli.cli.commands.agent.tasks_parsing_validation import (
    _self_review_fallback_option_error,
)

pytestmark = pytest.mark.fast


def _write_issue_matrix(
    feature_dir: Path,
    verdict: str,
    evidence_ref: str = "tests/test_demo.py",
    issue: str = "#1582",
) -> None:
    (feature_dir / "issue-matrix.md").write_text(
        "\n".join(
            [
                "| issue | verdict | evidence_ref |",
                "| --- | --- | --- |",
                f"| {issue} | {verdict} | {evidence_ref} |",
            ]
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# review-independence / issue-matrix approval guards
# ---------------------------------------------------------------------------


def test_self_review_fallback_requires_explicit_force_and_metadata() -> None:
    assert _self_review_fallback_option_error(
        enabled=False,
        target_lane="approved",
        force=False,
        intended_reviewer="codex",
        failure_reason=None,
    ) == "--intended-reviewer/--reviewer-failure-reason require --self-review-fallback."

    assert _self_review_fallback_option_error(
        enabled=True,
        target_lane="for_review",
        force=True,
        intended_reviewer="codex",
        failure_reason="exit 1",
    ) == "--self-review-fallback is only valid when approving or marking done."

    assert _self_review_fallback_option_error(
        enabled=True,
        target_lane="approved",
        force=False,
        intended_reviewer="codex",
        failure_reason="exit 1",
    ) == "--self-review-fallback requires --force so force_count records the independence override."

    assert _self_review_fallback_option_error(
        enabled=True,
        target_lane="approved",
        force=True,
        intended_reviewer="codex",
        failure_reason="exit 1",
    ) is None


def test_issue_matrix_read_is_coord_authoritative_no_primary_fallback(
    tmp_path: Path,
) -> None:
    """coord-commit-integrity SURFACE A #1c: coord matrix is authoritative.

    Flipped from ``..._uses_primary_verdicts_when_coord_copy_stale`` which pinned
    the deleted ``_primary_issue_matrix_satisfies`` fallback: a filled PRIMARY copy
    must NOT rescue a stale COORD copy (a PRIMARY fallback for a COORD kind is the
    split-brain anti-pattern). ``primary_feature_dir`` is used only for ``spec.md``.
    """
    coord_dir = tmp_path / "coord" / "kitty-specs" / "demo"
    primary_dir = tmp_path / "primary" / "kitty-specs" / "demo"
    coord_dir.mkdir(parents=True)
    primary_dir.mkdir(parents=True)
    spec_text = "Fix Priivacy-ai/spec-kitty issue #1582.\n"
    (coord_dir / "spec.md").write_text(spec_text, encoding="utf-8")
    (primary_dir / "spec.md").write_text(spec_text, encoding="utf-8")
    _write_issue_matrix(coord_dir, "unknown")  # stale coord copy — authoritative
    _write_issue_matrix(primary_dir, "fixed")  # filled primary copy — MUST be ignored

    blocker = _issue_matrix_approval_blocker(
        coord_dir,
        primary_feature_dir=primary_dir,
    )
    # The filled primary copy MUST NOT rescue the stale coord matrix.
    assert blocker is not None
    # #4330: the unknown-verdict row is surfaced with its concrete rule, not
    # reduced to a bare "Unknown: #1582" id list.
    assert "Row for issue '#1582'" in blocker
    assert "verdict 'unknown' is not in the allowed set" in blocker

    stale_blocker = _issue_matrix_approval_blocker(coord_dir)
    assert stale_blocker is not None
    assert "Row for issue '#1582'" in stale_blocker
    assert "verdict 'unknown' is not in the allowed set" in stale_blocker


def test_issue_matrix_in_mission_passes_approved_blocks_done(tmp_path: Path) -> None:
    from specify_cli.status.models import Lane

    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(
        "Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8"
    )
    _write_issue_matrix(feature_dir, "in-mission", evidence_ref="WP14 (this mission)")

    # Accepted at per-WP approval: a later WP in this mission closes #1582.
    assert _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.APPROVED) is None
    # Default (unspecified) target behaves like approval.
    assert _issue_matrix_approval_blocker(feature_dir) is None

    # Rejected at mission done: must reach a terminal verdict first.
    blocker = _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.DONE)
    assert blocker is not None
    assert "in-mission" in blocker
    assert "#1582" in blocker

    # Resolving to a terminal verdict clears the done-time block.
    _write_issue_matrix(feature_dir, "fixed", evidence_ref="commit abc123")
    assert _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.DONE) is None


def test_issue_matrix_approval_blocker_fails_closed_on_evaluation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")

    def _boom(_path: Path):
        raise RuntimeError("parser unavailable")

    monkeypatch.setattr("specify_cli.tasks.issue_matrix.detect_issue_references", _boom)

    blocker = _issue_matrix_approval_blocker(feature_dir)

    assert blocker is not None
    assert "could not be evaluated" in blocker
    assert "parser unavailable" in blocker


# ---------------------------------------------------------------------------
# _collect_status_artifacts
# ---------------------------------------------------------------------------


def test_collect_status_artifacts_empty(tmp_path: Path) -> None:
    """Returns empty list when none of the status files exist."""
    result = _collect_status_artifacts(tmp_path)
    assert result == []


def test_collect_status_artifacts_partial(tmp_path: Path) -> None:
    """Returns only files that actually exist."""
    (tmp_path / "status.events.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "tasks.md").write_text("# Tasks\n", encoding="utf-8")

    result = _collect_status_artifacts(tmp_path)
    names = {p.name for p in result}
    assert "status.events.jsonl" in names
    assert "tasks.md" in names
    assert "status.json" not in names


def test_collect_status_artifacts_all_present(tmp_path: Path) -> None:
    """Returns all three files when they all exist."""
    (tmp_path / "status.events.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "status.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tasks.md").write_text("# Tasks\n", encoding="utf-8")

    result = _collect_status_artifacts(tmp_path)
    assert len(result) == 3


# ---------------------------------------------------------------------------
# _output_result
# ---------------------------------------------------------------------------


def test_output_result_json_mode(capsys) -> None:
    """In JSON mode, prints JSON to stdout."""
    _output_result(True, {"result": "ok", "count": 3})
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data == {"result": "ok", "count": 3}


def test_output_result_human_with_message(capsys) -> None:
    """In human mode with a message, prints the message (not JSON)."""
    _output_result(False, {"result": "ok"}, success_message="Done!")
    captured = capsys.readouterr()
    assert "Done!" in captured.out
    # Verify it's not raw JSON
    assert "{" not in captured.out


def test_output_result_human_no_message(capsys) -> None:
    """In human mode with no message, produces no output."""
    _output_result(False, {"result": "ok"}, success_message=None)
    captured = capsys.readouterr()
    assert captured.out == ""


# ---------------------------------------------------------------------------
# _output_error
# ---------------------------------------------------------------------------


def test_output_error_json_mode(capsys) -> None:
    """In JSON mode, prints JSON error object."""
    _output_error(True, "something broke")
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data == {"error": "something broke"}


def test_output_error_human_mode(capsys) -> None:
    """In human mode, prints Rich error text."""
    _output_error(False, "something broke")
    captured = capsys.readouterr()
    assert "something broke" in captured.out


# ---------------------------------------------------------------------------
# _detect_reviewer_name
# ---------------------------------------------------------------------------


def test_detect_reviewer_name_success() -> None:
    """Returns name from git config when successful."""
    mock_result = MagicMock()
    mock_result.stdout = "Alice Dev\n"
    with patch("subprocess.run", return_value=mock_result):
        name = _detect_reviewer_name()
    assert name == "Alice Dev"


def test_detect_reviewer_name_empty_output() -> None:
    """Returns 'unknown' when git config returns empty string."""
    mock_result = MagicMock()
    mock_result.stdout = "   \n"
    with patch("subprocess.run", return_value=mock_result):
        name = _detect_reviewer_name()
    assert name == "unknown"


def test_detect_reviewer_name_subprocess_error() -> None:
    """Returns 'unknown' when git command fails."""
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")):
        name = _detect_reviewer_name()
    assert name == "unknown"


def test_detect_reviewer_name_file_not_found() -> None:
    """Returns 'unknown' when git is not installed."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        name = _detect_reviewer_name()
    assert name == "unknown"


# ---------------------------------------------------------------------------
# _resolve_git_common_dir
# ---------------------------------------------------------------------------


def test_resolve_git_common_dir_relative(tmp_path: Path) -> None:
    """Resolves a relative path against main_repo_root."""
    mock_result = MagicMock()
    mock_result.stdout = ".git\n"
    with patch("subprocess.run", return_value=mock_result):
        result = _resolve_git_common_dir(tmp_path)
    assert result == (tmp_path / ".git").resolve()
    assert result.is_absolute()


def test_resolve_git_common_dir_absolute(tmp_path: Path) -> None:
    """Returns absolute path unchanged."""
    abs_path = str(tmp_path / ".git")
    mock_result = MagicMock()
    mock_result.stdout = abs_path + "\n"
    with patch("subprocess.run", return_value=mock_result):
        result = _resolve_git_common_dir(tmp_path)
    assert result == Path(abs_path)
    assert result.is_absolute()


def test_resolve_git_common_dir_empty_output(tmp_path: Path) -> None:
    """Raises RuntimeError when git returns empty string."""
    mock_result = MagicMock()
    mock_result.stdout = "  \n"
    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="Unable to resolve git common directory"):
            _resolve_git_common_dir(tmp_path)


# ---------------------------------------------------------------------------
# _resolve_wp_slug
# ---------------------------------------------------------------------------


def test_resolve_wp_slug_finds_titled_file(tmp_path: Path) -> None:
    """Returns stem of matching WP file."""
    tasks_dir = tmp_path / "kitty-specs" / "010-test" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-agent-config-cleanup.md").write_text("", encoding="utf-8")

    result = _resolve_wp_slug(tmp_path, "010-test", "WP01")
    assert result == "WP01-agent-config-cleanup"


def test_resolve_wp_slug_exact_match(tmp_path: Path) -> None:
    """Returns stem when file stem exactly equals task_id."""
    tasks_dir = tmp_path / "kitty-specs" / "010-test" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01.md").write_text("", encoding="utf-8")

    result = _resolve_wp_slug(tmp_path, "010-test", "WP01")
    assert result == "WP01"


def test_resolve_wp_slug_no_tasks_dir(tmp_path: Path) -> None:
    """Falls back to bare task_id when tasks/ dir doesn't exist."""
    result = _resolve_wp_slug(tmp_path, "010-test", "WP01")
    assert result == "WP01"


def test_resolve_wp_slug_no_matching_file(tmp_path: Path) -> None:
    """Falls back to bare task_id when no matching file exists."""
    tasks_dir = tmp_path / "kitty-specs" / "010-test" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP02-something.md").write_text("", encoding="utf-8")

    result = _resolve_wp_slug(tmp_path, "010-test", "WP01")
    assert result == "WP01"


# ---------------------------------------------------------------------------
# _check_unchecked_subtasks
# ---------------------------------------------------------------------------

def _write_wp_frontmatter(feature_dir: Path, wp_id: str, roster: list[str]) -> None:
    """Author a WP file whose frontmatter ``subtasks:`` list is the guard roster."""
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    lines = ["---", f"work_package_id: {wp_id}", "subtasks:"]
    lines += [f"- {tid}" for tid in roster]
    lines += ["---", "", f"# {wp_id}", ""]
    (feature_dir / "tasks" / f"{wp_id}.md").write_text("\n".join(lines), encoding="utf-8")


def _seed_subtask_snapshot(feature_dir: Path, wp_id: str, subtasks: dict[str, object]) -> None:
    """Record subtask completion in the event log — the guard's sole authority."""
    from specify_cli.status.models import InnerStateChanged, WPInnerStateDelta
    from specify_cli.status.store import append_annotations_atomic_verified

    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id=("01KXANN" + wp_id).ljust(26, "0")[:26],
                wp_id=wp_id,
                at="2026-01-01T00:01:00+00:00",
                actor="test",
                delta=WPInnerStateDelta(subtasks=subtasks),  # type: ignore[arg-type]
            )
        ],
    )


def test_check_unchecked_subtasks_no_wp_file(tmp_path: Path) -> None:
    """Returns empty list when the WP has no authored frontmatter roster."""
    with patch(
        "specify_cli.cli.commands.agent.tasks.get_main_repo_root", return_value=tmp_path
    ):
        result = _check_unchecked_subtasks(tmp_path, "010-test", "WP01", False)
    assert result == []


def test_check_unchecked_subtasks_finds_unchecked(tmp_path: Path) -> None:
    """Returns the roster ids the snapshot marks incomplete (not tasks.md bytes)."""
    from specify_cli.status.models import Lane

    feature_dir = tmp_path / "kitty-specs" / "010-test"
    _write_wp_frontmatter(feature_dir, "WP01", ["T001", "T002", "T003"])
    _seed_subtask_snapshot(
        feature_dir, "WP01", {"T001": Lane.DONE, "T002": Lane.IN_PROGRESS, "T003": Lane.PLANNED}
    )

    with patch(
        "specify_cli.cli.commands.agent.tasks.get_main_repo_root", return_value=tmp_path
    ):
        result = _check_unchecked_subtasks(tmp_path, "010-test", "WP01", False)

    assert "T002" in result
    assert "T003" in result
    assert "T001" not in result  # done in the snapshot


def test_check_unchecked_subtasks_all_done(tmp_path: Path) -> None:
    """Returns empty list when every roster id is done in the snapshot."""
    from specify_cli.status.models import Lane

    feature_dir = tmp_path / "kitty-specs" / "010-test"
    _write_wp_frontmatter(feature_dir, "WP01", ["T001", "T002"])
    _seed_subtask_snapshot(feature_dir, "WP01", {"T001": Lane.DONE, "T002": Lane.DONE})

    with patch(
        "specify_cli.cli.commands.agent.tasks.get_main_repo_root", return_value=tmp_path
    ):
        result = _check_unchecked_subtasks(tmp_path, "010-test", "WP01", False)
    assert result == []


def test_check_unchecked_subtasks_only_target_wp(tmp_path: Path) -> None:
    """Each WP's roster + completion resolve independently (per-WP frontmatter)."""
    from specify_cli.status.models import Lane

    feature_dir = tmp_path / "kitty-specs" / "010-test"
    _write_wp_frontmatter(feature_dir, "WP01", ["T001", "T002", "T003"])
    _write_wp_frontmatter(feature_dir, "WP02", ["T004", "T005"])
    _seed_subtask_snapshot(feature_dir, "WP01", {"T002": Lane.IN_PROGRESS})
    _seed_subtask_snapshot(feature_dir, "WP02", {"T004": Lane.PLANNED, "T005": Lane.DONE})

    with patch(
        "specify_cli.cli.commands.agent.tasks.get_main_repo_root", return_value=tmp_path
    ):
        result = _check_unchecked_subtasks(tmp_path, "010-test", "WP02", False)

    # WP02 has T004 not-done and T005 done.
    assert "T004" in result
    assert "T005" not in result
    # WP01 tasks must not bleed in.
    assert "T002" not in result


def test_check_unchecked_subtasks_rosters_do_not_cross_contaminate(
    tmp_path: Path,
) -> None:
    """#2346 / #2324 lineage: WP rosters come from per-WP frontmatter, so a
    dependent WP's ids can never be misattributed to another WP. WP02 (all done)
    reports nothing; WP03 reports its OWN incomplete ids."""
    from specify_cli.status.models import Lane

    feature_dir = tmp_path / "kitty-specs" / "010-test"
    _write_wp_frontmatter(feature_dir, "WP02", ["T004", "T005"])
    _write_wp_frontmatter(feature_dir, "WP03", ["T006", "T007"])
    _seed_subtask_snapshot(feature_dir, "WP02", {"T004": Lane.DONE, "T005": Lane.DONE})
    _seed_subtask_snapshot(feature_dir, "WP03", {"T006": Lane.PLANNED, "T007": Lane.PLANNED})

    with patch(
        "specify_cli.cli.commands.agent.tasks.get_main_repo_root", return_value=tmp_path
    ):
        wp02 = _check_unchecked_subtasks(tmp_path, "010-test", "WP02", False)
        wp03 = _check_unchecked_subtasks(tmp_path, "010-test", "WP03", False)

    assert wp02 == [], f"WP02's subtasks are all done; got {wp02!r}"
    assert wp03 == ["T006", "T007"]


# ---------------------------------------------------------------------------
# _behind_commits_touch_only_planning_artifacts
# ---------------------------------------------------------------------------


def _make_subproc(returncode: int = 0, stdout: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    return m


def test_behind_commits_merge_base_failure(tmp_path: Path) -> None:
    """Returns False when merge-base subprocess fails."""
    with patch("subprocess.run", return_value=_make_subproc(returncode=1)):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", "010-test")
    assert result is False


def test_behind_commits_empty_merge_base(tmp_path: Path) -> None:
    """Returns False when merge-base output is empty."""
    with patch("subprocess.run", return_value=_make_subproc(returncode=0, stdout="")):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", "010-test")
    assert result is False


def test_behind_commits_no_changed_files(tmp_path: Path) -> None:
    """Returns True when diff reports no changed files (fully up-to-date)."""
    responses = [
        _make_subproc(returncode=0, stdout="abc123\n"),  # merge-base
        _make_subproc(returncode=0, stdout=""),          # diff --name-only
    ]
    with patch("subprocess.run", side_effect=responses):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", "010-test")
    assert result is True


def test_behind_commits_only_planning_files(tmp_path: Path) -> None:
    """Returns True when all changed files are in kitty-specs/MISSION/."""
    responses = [
        _make_subproc(returncode=0, stdout="abc123\n"),
        _make_subproc(returncode=0, stdout="kitty-specs/010-test/tasks.md\nkitty-specs/010-test/status.json\n"),
    ]
    with patch("subprocess.run", side_effect=responses):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", "010-test")
    assert result is True


def test_behind_commits_mixed_files(tmp_path: Path) -> None:
    """Returns False when any changed file is outside allowed paths."""
    responses = [
        _make_subproc(returncode=0, stdout="abc123\n"),
        _make_subproc(returncode=0, stdout="kitty-specs/010-test/tasks.md\nsrc/foo.py\n"),
    ]
    with patch("subprocess.run", side_effect=responses):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", "010-test")
    assert result is False


def test_behind_commits_kittify_config_allowed(tmp_path: Path) -> None:
    """Allows .kittify/config.yaml as an exact-path exception."""
    responses = [
        _make_subproc(returncode=0, stdout="abc123\n"),
        _make_subproc(returncode=0, stdout=".kittify/config.yaml\n"),
    ]
    with patch("subprocess.run", side_effect=responses):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", "010-test")
    assert result is True


def test_behind_commits_diff_failure(tmp_path: Path) -> None:
    """Returns False when the diff subprocess fails."""
    responses = [
        _make_subproc(returncode=0, stdout="abc123\n"),
        _make_subproc(returncode=128, stdout=""),
    ]
    with patch("subprocess.run", side_effect=responses):
        result = _behind_commits_touch_only_planning_artifacts(tmp_path, "main", "010-test")
    assert result is False


# ---------------------------------------------------------------------------
# _is_pipe_table_task_row
# ---------------------------------------------------------------------------


def test_is_pipe_table_task_row_separator() -> None:
    assert _is_pipe_table_task_row("|------|------|", "T001") is False


# ---------------------------------------------------------------------------
# _parse_pipe_table_header
# ---------------------------------------------------------------------------


def test_parse_pipe_table_header_found() -> None:
    lines = [
        "| ID | Description | WP | Parallel |",
        "|-----|-------------|----|----|",
        "| T001 | Do thing | WP01 | No |",
    ]
    result = _parse_pipe_table_header(lines, 2)
    assert result == {"id": 0, "description": 1, "wp": 2, "parallel": 3}


def test_parse_pipe_table_header_skips_separator() -> None:
    lines = [
        "| ID | Description |",
        "|---|---|",
        "| T001 | something |",
    ]
    result = _parse_pipe_table_header(lines, 2)
    assert "id" in result
    assert "description" in result


def test_parse_pipe_table_header_no_header() -> None:
    """Returns empty dict when there is no header row above the task row."""
    lines = ["Some prose line", "| T001 | desc |"]
    result = _parse_pipe_table_header(lines, 1)
    assert result == {}
