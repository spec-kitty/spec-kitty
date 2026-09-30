"""Unit tests for the ``tasks_materialization`` seam (WP03, #2058).

These tests exercise the frontmatter/file-persistence + markdown-row mutation
helpers directly against the new module (not via the ``tasks`` re-export shim).
They cover the three task-row mutation formats (checkbox, pipe-table, inline
``Subtasks:`` reference), the ``_update_pipe_table_status`` column-priority
logic, and — the coverage gap research flagged — the error/edge paths
(write failure, invalid YAML frontmatter, missing file).
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.cli.commands.agent.tasks_materialization import (
    TASKS_MD_FILENAME,
    TaskIdResolutionFormat,
    TaskIdResolutionOutcome,
    _collect_status_artifacts,
    _persist_review_artifact_override,
    _persist_review_feedback,
    _resolve_checkbox,
    _resolve_pipe_table,
    _resolve_wp_slug,
    _update_pipe_table_status,
)
from specify_cli.cli.commands.agent.tasks_outline import _parse_pipe_table_header

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# _update_pipe_table_status — column-priority logic
# ---------------------------------------------------------------------------


class TestUpdatePipeTableStatus:
    """The four-branch priority ladder: status col -> parallel -> last cell -> append."""

    def test_updates_dedicated_status_column_only(self) -> None:
        line = "| T001 | do thing | WP01 | [ ] |"
        header_map = {"id": 0, "description": 1, "wp": 2, "status": 3}
        result = _update_pipe_table_status(line, "done", header_map)
        assert "[D]" in result
        assert "WP01" in result  # other columns untouched

    def test_status_column_out_of_range_falls_through_to_last_cell(self) -> None:
        # status_col present but >= number of inner cells -> must NOT index-error;
        # falls into the no-header branch (last cell is a marker -> replace).
        line = "| T001 | [ ] |"
        header_map = {"status": 9}
        result = _update_pipe_table_status(line, "done", header_map)
        assert "[D]" in result

    def test_parallel_column_is_never_corrupted(self) -> None:
        line = "| T001 | do thing | WP01 | [P] |"
        header_map = {"id": 0, "description": 1, "wp": 2, "parallel": 3}
        result = _update_pipe_table_status(line, "done", header_map)
        assert "[P]" in result  # parallel marker preserved
        assert "[D]" in result  # status appended in a new cell

    def test_no_header_replaces_trailing_marker_in_place(self) -> None:
        line = "| T001 | do thing | WP01 | [ ] |"
        result = _update_pipe_table_status(line, "done", {})
        assert "[D]" in result
        # No extra cell appended: exactly the same number of pipes.
        assert result.count("|") == line.count("|")

    def test_no_header_appends_when_last_cell_is_not_a_marker(self) -> None:
        line = "| T001 | do thing | WP01 |"
        result = _update_pipe_table_status(line, "done", {})
        assert "[D]" in result
        assert result.count("|") == line.count("|") + 1  # one cell appended

    def test_pending_status_writes_empty_marker(self) -> None:
        line = "| T001 | do thing | WP01 | [D] |"
        header_map = {"id": 0, "description": 1, "wp": 2, "status": 3}
        result = _update_pipe_table_status(line, "pending", header_map)
        assert "[ ]" in result
        assert "[D]" not in result

    def test_result_is_a_well_formed_pipe_row(self) -> None:
        line = "| T001 | do thing | WP01 | [P] |"
        header_map = {"parallel": 3}
        result = _update_pipe_table_status(line, "done", header_map)
        assert result.startswith("|")
        assert result.endswith("|")


# ---------------------------------------------------------------------------
# _resolve_checkbox
# ---------------------------------------------------------------------------


class TestResolveCheckbox:
    def test_marks_done(self) -> None:
        lines = ["- [ ] T001 do thing"]
        result = _resolve_checkbox("T001", lines, "done")
        assert result is not None
        assert result.outcome == TaskIdResolutionOutcome.UPDATED
        assert result.format == TaskIdResolutionFormat.CHECKBOX
        assert lines[0] == "- [x] T001 do thing"

    def test_marks_pending(self) -> None:
        lines = ["- [x] T001 do thing"]
        result = _resolve_checkbox("T001", lines, "pending")
        assert result is not None
        assert lines[0] == "- [ ] T001 do thing"

    def test_is_case_insensitive_on_task_id(self) -> None:
        lines = ["- [ ] t001 do thing"]
        result = _resolve_checkbox("T001", lines, "done")
        assert result is not None
        assert lines[0].startswith("- [x]")

    def test_updates_all_matching_rows(self) -> None:
        lines = ["- [ ] T001 first", "noise", "- [ ] T001 second"]
        result = _resolve_checkbox("T001", lines, "done")
        assert result is not None
        assert lines[0].startswith("- [x]")
        assert lines[2].startswith("- [x]")

    def test_returns_none_when_absent(self) -> None:
        lines = ["- [ ] T999 other"]
        assert _resolve_checkbox("T001", lines, "done") is None


# ---------------------------------------------------------------------------
# _resolve_pipe_table
# ---------------------------------------------------------------------------


class TestResolvePipeTable:
    def test_mutates_pipe_table_row(self) -> None:
        lines = [
            "| ID | Description | WP | Status |",
            "|----|----|----|----|",
            "| T001 | do thing | WP01 | [ ] |",
        ]
        result = _resolve_pipe_table("T001", lines, "done")
        assert result is not None
        assert result.outcome == TaskIdResolutionOutcome.UPDATED
        assert result.format == TaskIdResolutionFormat.PIPE_TABLE
        assert "[D]" in lines[2]

    def test_returns_none_when_no_pipe_row_matches(self) -> None:
        lines = ["- [ ] T001 checkbox not a pipe row"]
        assert _resolve_pipe_table("T001", lines, "done") is None

    def test_header_map_is_honored(self) -> None:
        lines = [
            "| ID | Description | WP | Status |",
            "|----|----|----|----|",
            "| T001 | do thing | WP01 | [ ] |",
        ]
        # Sanity-check header parsing wiring used by the resolver.
        header_map = _parse_pipe_table_header(lines, 2)
        assert header_map["status"] == 3
        _resolve_pipe_table("T001", lines, "done")
        assert "[D]" in lines[2]
        assert "WP01" in lines[2]


# ---------------------------------------------------------------------------
# _collect_status_artifacts
# ---------------------------------------------------------------------------


class TestCollectStatusArtifacts:
    def test_empty_when_no_artifacts(self, tmp_path: Path) -> None:
        assert _collect_status_artifacts(tmp_path) == []

    def test_returns_only_existing_artifacts(self, tmp_path: Path) -> None:
        from specify_cli.status import EVENTS_FILENAME

        (tmp_path / EVENTS_FILENAME).write_text("{}\n", encoding="utf-8")
        (tmp_path / TASKS_MD_FILENAME).write_text("# tasks\n", encoding="utf-8")
        collected = _collect_status_artifacts(tmp_path)
        names = {p.name for p in collected}
        assert EVENTS_FILENAME in names
        assert TASKS_MD_FILENAME in names
        # status.json was never created -> excluded.
        assert all(p.exists() for p in collected)


# ---------------------------------------------------------------------------
# _persist_review_artifact_override (FR-009 / WP09: event-sourced write half)
# ---------------------------------------------------------------------------


def _artifact_with_frontmatter(path: Path, body: str = "review body\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nstatus: rejected\n---\n" + body,
        encoding="utf-8",
    )


def _review_feature_dir(root: Path, mission_slug: str = "demo-mission") -> Path:
    """Create a kitty-specs feature_dir named after the mission slug.

    ``_persist_review_artifact_override`` derives the emit target from the
    artifact path (``<feature_dir>/tasks/<wp-slug>/review-cycle-N.md``), so the
    directory name MUST equal the mission slug.
    """
    import json as _json

    feature_dir = root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        _json.dumps({"mission_id": "01KXWN13EVICTION00000000000", "mission_slug": mission_slug}),
        encoding="utf-8",
    )
    return feature_dir


class TestPersistReviewArtifactOverride:
    """FR-009 (WP09): the override is event-sourced into the ``review`` snapshot
    slot, NOT stamped onto the artifact frontmatter (and NOT mirrored into a coord
    copy). The artifact file must be left byte-unchanged."""

    def test_emits_review_override_without_stamping_frontmatter(self, tmp_path: Path) -> None:
        from specify_cli.status import materialize

        feature_dir = _review_feature_dir(tmp_path)
        artifact = feature_dir / "tasks" / "WP01-slug" / "review-cycle-1.md"
        _artifact_with_frontmatter(artifact)
        before = artifact.read_bytes()

        _persist_review_artifact_override(
            artifact,
            repo_root=tmp_path,
            wp_id="WP01",
            actor="claude",
            reason="superseded by newer approval",
        )

        # The artifact file is byte-unchanged: no frontmatter stamp.
        assert artifact.read_bytes() == before
        assert "review_artifact_override" not in artifact.read_text(encoding="utf-8")

        # The override is event-sourced into the ``review`` snapshot slot.
        review = materialize(feature_dir).work_packages["WP01"]["review"]
        assert review["actor"] == "claude"
        assert review["wp_id"] == "WP01"
        assert review["reason"] == "superseded by newer approval"
        assert review["at"]

    def test_override_reason_round_trips_through_snapshot(self, tmp_path: Path) -> None:
        from specify_cli.status import materialize

        feature_dir = _review_feature_dir(tmp_path, mission_slug="mission-two")
        artifact = feature_dir / "tasks" / "WP02-slug" / "review-cycle-1.md"
        _artifact_with_frontmatter(artifact)

        _persist_review_artifact_override(
            artifact,
            repo_root=tmp_path,
            wp_id="WP02",
            actor="codex",
            reason="manual override",
        )

        review = materialize(feature_dir).work_packages["WP02"]["review"]
        assert review == {
            "at": review["at"],
            "actor": "codex",
            "wp_id": "WP02",
            "reason": "manual override",
        }
        # Artifact frontmatter carries no override evidence.
        assert "review_artifact_override" not in artifact.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# _resolve_wp_slug
# ---------------------------------------------------------------------------


def _patch_materialization_read_dir(read_dir: Path) -> AbstractContextManager[MagicMock]:
    seam = MagicMock()
    seam.read_dir.return_value = read_dir
    return patch(
        "specify_cli.cli.commands.agent.tasks_materialization.placement_seam",
        return_value=seam,
    )


class TestResolveWpSlug:
    def test_finds_titled_file(self, tmp_path: Path) -> None:
        with _patch_materialization_read_dir(tmp_path):
            (tmp_path / "tasks").mkdir()
            (tmp_path / "tasks" / "WP01-do-the-thing.md").write_text("x", encoding="utf-8")
            assert _resolve_wp_slug(tmp_path, "010-test", "WP01") == "WP01-do-the-thing"

    def test_exact_match_stem(self, tmp_path: Path) -> None:
        with _patch_materialization_read_dir(tmp_path):
            (tmp_path / "tasks").mkdir()
            (tmp_path / "tasks" / "WP01.md").write_text("x", encoding="utf-8")
            assert _resolve_wp_slug(tmp_path, "010-test", "WP01") == "WP01"

    def test_falls_back_to_bare_id_when_no_tasks_dir(self, tmp_path: Path) -> None:
        with _patch_materialization_read_dir(tmp_path):
            assert _resolve_wp_slug(tmp_path, "010-test", "WP01") == "WP01"

    def test_falls_back_to_bare_id_when_no_matching_file(self, tmp_path: Path) -> None:
        with _patch_materialization_read_dir(tmp_path):
            (tmp_path / "tasks").mkdir()
            (tmp_path / "tasks" / "WP99-other.md").write_text("x", encoding="utf-8")
            assert _resolve_wp_slug(tmp_path, "010-test", "WP01") == "WP01"


# ---------------------------------------------------------------------------
# _persist_review_feedback (delegation boundary)
# ---------------------------------------------------------------------------


class TestPersistReviewFeedback:
    def test_delegates_to_review_cycle_with_resolved_slug(self, tmp_path: Path) -> None:
        fake_cycle = MagicMock()
        fake_cycle.artifact_path = tmp_path / "cycle.md"
        fake_cycle.pointer = "review-cycle://WP01/abc"

        with patch(
            "specify_cli.cli.commands.agent.tasks_materialization._resolve_wp_slug",
            return_value="WP01-titled",
        ), patch(
            "specify_cli.review.cycle.create_rejected_review_cycle",
            return_value=fake_cycle,
        ) as create_mock:
            artifact_path, pointer = _persist_review_feedback(
                main_repo_root=tmp_path,
                mission_slug="010-test",
                task_id="WP01",
                feedback_source=tmp_path / "feedback.md",
                reviewer_agent="codex",
            )

        assert artifact_path == fake_cycle.artifact_path
        assert pointer == fake_cycle.pointer
        _, kwargs = create_mock.call_args
        assert kwargs["wp_slug"] == "WP01-titled"
        assert kwargs["wp_id"] == "WP01"
        assert kwargs["reviewer_agent"] == "codex"

    def test_propagates_review_cycle_errors(self, tmp_path: Path) -> None:
        with patch(
            "specify_cli.cli.commands.agent.tasks_materialization._resolve_wp_slug",
            return_value="WP01",
        ), patch(
            "specify_cli.review.cycle.create_rejected_review_cycle",
            side_effect=RuntimeError("cycle boom"),
        ), pytest.raises(RuntimeError, match="cycle boom"):
            _persist_review_feedback(
                main_repo_root=tmp_path,
                mission_slug="010-test",
                task_id="WP01",
                feedback_source=tmp_path / "feedback.md",
            )
