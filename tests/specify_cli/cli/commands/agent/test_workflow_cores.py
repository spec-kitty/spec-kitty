"""Direct unit tests for ``workflow_cores.py`` (WP02, T014).

coord-authority-trio-degod-01KX7094: focused branch-coverage tests for the
pure(ish) helpers extracted from ``workflow.py`` during the ``implement``
(CC78)/``review`` (CC72)/``_resolve_review_context`` (CC37) decomposition —
in particular the genuinely NEW pure helpers that did not exist as
named functions before this split (``event_is_review_claim`` and, since
#7578, ``wp_owned_files``), plus light direct coverage of the moved
renderers/classifiers/request dataclasses. The retired review-base helpers'
cases are re-pinned to their successors: the review range fills the review
context (``workflow_executor._fill_review_range``) and is the one pathspec
authority (``WpReviewRange.owned_pathspecs``).

Marker: unit only -- no subprocess, no git (per the ``unit`` marker's
contract in ``pytest.ini``); every function under test here takes plain
values in and returns a plain value/string out, save two exceptions:
``TestWpOwnedFiles`` reads a WP file it writes to ``tmp_path`` (the canonical
frontmatter reader takes a path), and ``TestWpReviewRangeOwnedPathspecs``
(marked ``git_repo``) reads the pathspecs off a range resolved in an empty
temporary directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.cli.commands.agent import workflow_cores as cores
from specify_cli.cli.commands.agent import workflow_executor as executor
from specify_cli.review.wp_range import RangeCommit, RangeSource, RangeStatus, WpReviewRange, resolve_wp_review_range
from specify_cli.status import AgentAssignment, Lane, StatusEvent

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# The review base (re-pinned, #7578): the WP review range fills the review
# context; the pure scored base-branch pick (``pick_best_base_branch``) is
# retired with the candidate search that fed it.
# ---------------------------------------------------------------------------


def _range(*, base: str | None, commits: int = 0) -> WpReviewRange:
    if base is None:
        return WpReviewRange.unavailable("WP01", "not_recorded")
    return WpReviewRange(
        wp_id="WP01",
        base=base,
        tip="f" * 40,
        base_source=RangeSource.RECORDED_WINDOW,
        tip_source=RangeSource.RECORDED_SUBMISSION,
        gap=None,
        status=RangeStatus.RECORDED,
        commits=tuple(RangeCommit(sha=f"{index:040d}", subject=f"c{index}") for index in range(commits)),
    )


def _unknown_ctx() -> dict[str, object]:
    return {"branch_name": "unknown", "base_branch": "unknown", "lane_branch": "unknown", "base_ref": "unknown", "commit_count": 0}


class TestFillReviewRange:
    """Re-pinned: ``_fill_review_range`` takes the base from the review range, never a scored branch pick."""

    def test_unavailable_range_keeps_unknown_base_and_zero_count(self) -> None:
        ctx = executor._fill_review_range(_unknown_ctx(), _range(base=None), None)
        assert ctx["base_branch"] == "unknown" and ctx["base_ref"] == "unknown"
        assert ctx["commit_count"] == 0

    def test_recorded_range_fills_base_and_commit_count(self) -> None:
        ctx = executor._fill_review_range(_unknown_ctx(), _range(base="a" * 40, commits=5), "main")
        assert ctx["base_branch"] == "a" * 40 and ctx["base_ref"] == "a" * 40
        assert ctx["commit_count"] == 5

    def test_commit_count_is_the_listed_implementation_commits(self) -> None:
        """The count is the range's listed implementation commits, not a branch's unique-commit score."""
        review_range = _range(base="b" * 40, commits=3)
        ctx = executor._fill_review_range(_unknown_ctx(), review_range, "kitty/mission-x-lane-a")
        assert ctx["commit_count"] == len(review_range.commits) == 3
        assert ctx["review_range"] is review_range

    def test_missing_branch_keeps_unknown_branch_labels(self) -> None:
        """The branch is display only: a missing branch keeps ``unknown`` while the base still comes from the range."""
        ctx = executor._fill_review_range(_unknown_ctx(), _range(base="c" * 40, commits=4), None)
        assert ctx["branch_name"] == "unknown" and ctx["lane_branch"] == "unknown"
        assert ctx["base_branch"] == "c" * 40

    def test_empty_commit_list_keeps_the_base_with_zero_count(self) -> None:
        ctx = executor._fill_review_range(_unknown_ctx(), _range(base="d" * 40, commits=0), "main")
        assert ctx["base_branch"] == "d" * 40
        assert ctx["commit_count"] == 0


# ---------------------------------------------------------------------------
# wp_owned_files (re-pinned, #7578): the review range reads the WP's
# ``owned_files`` through the canonical authored-frontmatter reader
# (``read_authored_wp_frontmatter``); ``parse_dependency_wp_ids`` is retired
# with the dependency-branch candidate search it fed.
# ---------------------------------------------------------------------------

_WP_HEAD = "---\nwork_package_id: WP01\ntitle: Some WP\n"


def _wp_file(tmp_path: Path, frontmatter: str) -> Path:
    path = tmp_path / "WP01-some-wp.md"
    path.write_text(f"{_WP_HEAD}{frontmatter}---\n# WP01\n", encoding="utf-8")
    return path


class TestWpOwnedFiles:
    def test_no_owned_files_key_returns_empty(self, tmp_path: Path) -> None:
        assert cores.wp_owned_files(_wp_file(tmp_path, "")) == []

    def test_empty_owned_files_list_returns_empty(self, tmp_path: Path) -> None:
        assert cores.wp_owned_files(_wp_file(tmp_path, "owned_files: []\n")) == []

    def test_single_owned_file_quoted(self, tmp_path: Path) -> None:
        assert cores.wp_owned_files(_wp_file(tmp_path, 'owned_files: ["src/a.py"]\n')) == ["src/a.py"]

    def test_multiple_owned_files_quoted(self, tmp_path: Path) -> None:
        assert cores.wp_owned_files(_wp_file(tmp_path, 'owned_files: ["src/a.py", "src/b/**"]\n')) == ["src/a.py", "src/b/**"]

    def test_multiple_owned_files_block_list(self, tmp_path: Path) -> None:
        assert cores.wp_owned_files(_wp_file(tmp_path, "owned_files:\n- src/a.py\n- src/b/**\n")) == ["src/a.py", "src/b/**"]

    def test_ignores_unrelated_frontmatter(self, tmp_path: Path) -> None:
        assert cores.wp_owned_files(_wp_file(tmp_path, 'agent: "claude"\nowned_files: [src/a.py]\n')) == ["src/a.py"]

    def test_declaration_the_canonical_reader_rejects_declares_nothing(self, tmp_path: Path) -> None:
        """Bad YAML, a scalar where the schema wants a list, and an unknown key are the canonical reader's refusals."""
        assert cores.wp_owned_files(_wp_file(tmp_path, "owned_files: [unclosed\n")) == []
        assert cores.wp_owned_files(_wp_file(tmp_path, "owned_files: src/only.py\n")) == []
        assert cores.wp_owned_files(_wp_file(tmp_path, "bogus_field: 1\nowned_files: [src/a.py]\n")) == []

    def test_missing_file_declares_nothing(self, tmp_path: Path) -> None:
        assert cores.wp_owned_files(tmp_path / "WP09-absent.md") == []


# ---------------------------------------------------------------------------
# WpReviewRange.owned_pathspecs (re-pinned, #7578): the one pathspec authority;
# ``build_owned_files_review_pathspecs`` is retired. A directory with no
# Mission resolves an UNAVAILABLE range that still carries the pathspecs.
# ---------------------------------------------------------------------------


def _mission(tmp_path: Path) -> Path:
    """A minimal readable Mission, so the range resolves its bookkeeping surface (an unreadable one builds no excludes)."""
    mission_dir = tmp_path / "kitty-specs" / "my-mission"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_slug": "my-mission", "mission_id": "01KABCDEFGHJKMNPQRSTVWXYZ0", "target_branch": "main"}),
        encoding="utf-8",
    )
    (mission_dir / "status.events.jsonl").write_text("", encoding="utf-8")
    return tmp_path


def _pathspecs(owned: list[str], tmp_path: Path) -> list[str]:
    return list(resolve_wp_review_range(_mission(tmp_path), "my-mission", "WP01", owned_files=owned).owned_pathspecs)


@pytest.mark.git_repo
class TestWpReviewRangeOwnedPathspecs:
    def test_empty_owned_files_returns_empty(self, tmp_path: Path) -> None:
        assert _pathspecs([], tmp_path) == []

    def test_files_outside_mission_root_pass_through_unmodified(self, tmp_path: Path) -> None:
        owned = ["src/specify_cli/foo.py", "tests/test_foo.py"]
        assert _pathspecs(owned, tmp_path) == owned

    def test_mission_root_files_that_reach_no_bookkeeping_get_no_excludes(self, tmp_path: Path) -> None:
        """Re-pin (#7578, DIRECTIVE_041): an exclude is added only for a bookkeeping prefix an owned glob can reach."""
        owned = ["kitty-specs/my-mission/spec.md", "src/foo.py"]
        assert _pathspecs(owned, tmp_path) == owned

    def test_mission_dir_glob_gets_every_mission_bookkeeping_exclude(self, tmp_path: Path) -> None:
        result = _pathspecs(["kitty-specs/my-mission/**", "src/foo.py"], tmp_path)
        assert result[:2] == ["kitty-specs/my-mission/**", "src/foo.py"]
        assert ":(exclude)kitty-specs/my-mission/tasks/*" in result
        assert ":(exclude)kitty-specs/my-mission/tasks.md" in result  # the task index is one exact path (#7578 L1)
        assert ":(exclude)kitty-specs/my-mission/status.*" in result
        assert ":(exclude)kitty-specs/my-mission/meta.json*" in result
        assert ":(exclude).kittify/*" not in result

    def test_excludes_only_added_once_even_with_multiple_mission_root_globs(self, tmp_path: Path) -> None:
        owned = ["kitty-specs/my-mission/**", "kitty-specs/my-mission/research/**", "kitty-specs/*/tasks/**"]
        result = _pathspecs(owned, tmp_path)
        assert result.count(":(exclude)kitty-specs/my-mission/tasks/*") == 1

    def test_unreadable_status_builds_no_excludes_from_the_callers_handle(self, tmp_path: Path) -> None:
        """Landing fold: with no readable Mission the handle may be a mid8 or ULID, so only the owned globs are returned."""
        owned = ["kitty-specs/my-mission/**", "src/foo.py"]
        result = resolve_wp_review_range(tmp_path, "my-mission", "WP01", owned_files=owned).owned_pathspecs
        assert list(result) == owned


# ---------------------------------------------------------------------------
# event_is_review_claim (new, dedupes the shared predicate from
# _find_first_for_review_wp / review())
# ---------------------------------------------------------------------------


def _event(*, to_lane: Lane, review_ref: str | None) -> StatusEvent:
    return StatusEvent(
        event_id="01TESTEVENT00000000000001",
        mission_slug="trio-mission",
        wp_id="WP01",
        from_lane=Lane.FOR_REVIEW,
        to_lane=to_lane,
        at="2026-01-01T00:00:00+00:00",
        actor="reviewer-renata",
        force=False,
        execution_mode="worktree",
        review_ref=review_ref,
    )


class TestEventIsReviewClaim:
    def test_new_canonical_shape_in_review_is_claimed(self) -> None:
        assert cores.event_is_review_claim(_event(to_lane=Lane.IN_REVIEW, review_ref=None)) is True

    def test_legacy_shape_in_progress_with_sentinel_is_claimed(self) -> None:
        event = _event(to_lane=Lane.IN_PROGRESS, review_ref="action-review-claim")
        assert cores.event_is_review_claim(event) is True

    def test_in_progress_without_sentinel_is_not_claimed(self) -> None:
        event = _event(to_lane=Lane.IN_PROGRESS, review_ref=None)
        assert cores.event_is_review_claim(event) is False

    def test_for_review_lane_is_not_claimed(self) -> None:
        event = _event(to_lane=Lane.FOR_REVIEW, review_ref=None)
        assert cores.event_is_review_claim(event) is False

    def test_approved_lane_is_not_claimed(self) -> None:
        event = _event(to_lane=Lane.APPROVED, review_ref=None)
        assert cores.event_is_review_claim(event) is False


# ---------------------------------------------------------------------------
# Request dataclasses (T009/T010)
# ---------------------------------------------------------------------------


class TestRequestDataclasses:
    def test_implement_request_is_frozen(self) -> None:
        request = cores.ImplementRequest(
            wp_id="WP01",
            mission="my-mission",
            agent="claude",
            allow_sparse_checkout=False,
            acknowledge_not_bulk_edit=False,
        )
        assert request.wp_id == "WP01"
        with pytest.raises(AttributeError):
            request.wp_id = "WP02"

    def test_review_request_is_frozen(self) -> None:
        request = cores.ReviewRequest(wp_id="WP01", mission="my-mission", agent="reviewer-renata")
        assert request.agent == "reviewer-renata"
        with pytest.raises(AttributeError):
            request.agent = "someone-else"


# ---------------------------------------------------------------------------
# Light direct coverage of the moved renderers/classifiers (behaviour
# preservation for the T007 move, not new logic)
# ---------------------------------------------------------------------------


class TestMovedRenderersAndClassifiers:
    def test_normalize_wp_id_variants(self) -> None:
        assert cores.normalize_wp_id("wp01") == "WP01"
        assert cores.normalize_wp_id("WP01-some-slug") == "WP01"
        assert cores.normalize_wp_id("3") == "WP3"

    def test_render_isolation_banner_implement_mentions_subtasks(self) -> None:
        lines = cores.render_isolation_banner("WP01", "implement")
        text = "\n".join(lines)
        assert "YOU ARE ASSIGNED TO: WP01" in text
        assert "subtasks belonging to WP01" in text

    def test_render_isolation_banner_review_mentions_review_ownership(self) -> None:
        lines = cores.render_isolation_banner("WP01", "review")
        text = "\n".join(lines)
        assert "YOU ARE REVIEWING: WP01" in text
        assert "Review or approve any WP other than WP01" in text

    def test_render_wp_prompt_wrapper_wraps_content(self) -> None:
        lines = cores.render_wp_prompt_wrapper("WP BODY TEXT")
        text = "\n".join(lines)
        assert "WORK PACKAGE PROMPT BEGINS" in text
        assert "WP BODY TEXT" in text
        assert "WORK PACKAGE PROMPT ENDS" in text

    def test_render_resolved_agent_identity_defaults(self) -> None:
        assignment = AgentAssignment(tool="claude", model="sonnet", profile_id=None, role=None)
        lines = cores.render_resolved_agent_identity(assignment)
        text = "\n".join(lines)
        assert "tool       : claude" in text
        assert "profile_id : (default)" in text
        assert "role       : (default)" in text

    def test_is_missing_canonical_status_error_true_for_typed_exception(self) -> None:
        from specify_cli.status import CanonicalStatusNotFoundError

        assert cores.is_missing_canonical_status_error(CanonicalStatusNotFoundError("boom")) is True

    def test_is_missing_canonical_status_error_false_for_other_exception(self) -> None:
        assert cores.is_missing_canonical_status_error(RuntimeError("boom")) is False

    def test_missing_canonical_status_message_without_feature_dir(self) -> None:
        message = cores.missing_canonical_status_message("WP01", "my-mission")
        assert "WP01" in message
        assert "finalize-tasks" in message
        assert "my-mission" in message

    def test_auto_claim_failure_message_dependency_reason(self) -> None:
        class _Preview:
            selection_reason = "dependencies_not_satisfied"

        message = cores.auto_claim_failure_message(_Preview())
        assert "dependencies_not_satisfied" in message

    def test_auto_claim_failure_message_default(self) -> None:
        message = cores.auto_claim_failure_message(None)
        assert "No planned work packages found" in message


# ---------------------------------------------------------------------------
# review_feedback_root (structural navigation, no filesystem touch)
# ---------------------------------------------------------------------------


class TestReviewFeedbackRoot:
    def test_navigates_two_levels_up_from_feature_dir(self) -> None:
        feature_dir = Path("/repo/kitty-specs/my-mission")
        assert cores.review_feedback_root(feature_dir) == Path("/repo")
