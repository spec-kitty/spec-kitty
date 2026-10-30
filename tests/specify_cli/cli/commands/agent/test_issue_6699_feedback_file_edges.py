"""#6699: ``--review-feedback-file`` is never validated and then silently dropped.

Landing fold verdict (development-assist-test-cleanup): KEPT as a permanent
issue-named guard — the repo's established convention (see
test_issue_2684_subtask_completion_event_sourced.py and siblings); the fix has
landed, so this is no longer a red-first pin but the standing guard for the
feedback-file edge contract recorded in
kitty-specs/honest-feedback-file-drop-01M66FMD/contracts/.

``move-task`` resolves the file on every edge, but only the rejection writer
and the approval writer consume it. On edges that write no review cycle the
file used to be validated and then dropped without a word. These tests drive
the production Typer app through the shared rework-loop harness:

* ``in_progress -> for_review`` and ``for_review -> in_review`` with the flag
  must REFUSE (exit 1) naming the edge, writing nothing (RED on the pre-fix
  tree: today they exit 0 in silence).
* The same moves without the flag must still succeed (positive controls, so
  the refusal probe is non-vacuous).
* An arbiter override into ``approved`` with the flag keeps the #6652 stderr
  warning and records only the ``--note`` (ratchet: passes pre-fix; pinned here
  end-to-end because it was only pinned at writer level).
* Unit matrix on the pure guard: the refusal arms exactly on non-recordable
  edges and leaves the recordable-edge messages byte-stable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from specify_cli.cli.commands.agent.tasks_transition_core import (
    RefuseExit1,
    _guard_feedback_file,
    decide_transition,
    Emit,
)
from tests.specify_cli.cli.commands.agent._rework_loop_harness import (
    IMPLEMENTER,
    REVIEWER,
    WP,
    build_mission,
    drive_to_for_review,
    events,
    move,
    override_probes,
    reject,
    review_cycle_files,
)
from tests.specify_cli.cli.commands.agent.test_tasks_transition_core import _base_request
from specify_cli.review.arbiter import get_arbiter_overrides_for_wp

pytestmark = pytest.mark.slow


def _feedback(m: Any, name: str = "feedback.md") -> Path:
    path = m.repo / name
    path.write_text("## Review feedback\n\nPlease fix the thing.\n", encoding="utf-8")
    return path


def _lane_events(m: Any) -> list[dict[str, Any]]:
    return [e for e in events(m) if "to_lane" in e and "from_lane" in e]


# ---------------------------------------------------------------------------
# RED on the pre-fix tree: non-review edges must refuse the flag.
# ---------------------------------------------------------------------------


def test_feedback_file_on_in_progress_to_for_review_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = build_mission(tmp_path, monkeypatch)
    assert move(m, WP, "claimed", IMPLEMENTER).exit_code == 0
    assert move(m, WP, "in_progress", IMPLEMENTER).exit_code == 0
    hops_before = len(_lane_events(m))

    result = move(m, WP, "for_review", IMPLEMENTER, "--review-feedback-file", str(_feedback(m)))

    assert result.exit_code == 1, result.output
    assert "--review-feedback-file" in result.output
    assert "from 'in_progress' to 'for_review'" in result.output
    assert "no review cycle" in result.output
    # NFR-001: nothing durable — no lane hop, no review cycle.
    assert len(_lane_events(m)) == hops_before
    assert _lane_events(m)[-1]["to_lane"] == "in_progress"
    assert review_cycle_files(m) == []


def test_feedback_file_on_for_review_to_in_review_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = build_mission(tmp_path, monkeypatch)
    drive_to_for_review(m)
    hops_before = len(_lane_events(m))

    result = move(m, WP, "in_review", REVIEWER, "--review-feedback-file", str(_feedback(m)))

    assert result.exit_code == 1, result.output
    assert "from 'for_review' to 'in_review'" in result.output
    assert len(_lane_events(m)) == hops_before
    assert _lane_events(m)[-1]["to_lane"] == "for_review"
    assert review_cycle_files(m) == []


# ---------------------------------------------------------------------------
# Positive controls on the same fixtures: the moves succeed without the flag.
# ---------------------------------------------------------------------------


def test_in_progress_to_for_review_without_the_flag_still_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = build_mission(tmp_path, monkeypatch)
    assert move(m, WP, "claimed", IMPLEMENTER).exit_code == 0
    assert move(m, WP, "in_progress", IMPLEMENTER).exit_code == 0

    result = move(m, WP, "for_review", IMPLEMENTER)

    assert result.exit_code == 0, result.output
    assert _lane_events(m)[-1]["to_lane"] == "for_review"


def test_for_review_to_in_review_without_the_flag_still_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = build_mission(tmp_path, monkeypatch)
    drive_to_for_review(m)

    result = move(m, WP, "in_review", REVIEWER)

    assert result.exit_code == 0, result.output
    assert _lane_events(m)[-1]["to_lane"] == "in_review"


def test_rejection_edge_still_requires_the_feedback_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = build_mission(tmp_path, monkeypatch)
    drive_to_for_review(m)

    missing = move(m, WP, "planned", REVIEWER)

    assert missing.exit_code == 1, missing.output
    assert _lane_events(m)[-1]["to_lane"] == "for_review"


# ---------------------------------------------------------------------------
# Ratchet (passes pre-fix): the arbiter-override drop stays announced.
# ---------------------------------------------------------------------------


def test_arbiter_override_with_feedback_file_warns_and_records_only_the_note(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = build_mission(tmp_path, monkeypatch)
    drive_to_for_review(m)
    reject(m, "for_review_to_planned")
    rejection_cycles = review_cycle_files(m)

    result = move(
        m,
        WP,
        "approved",
        REVIEWER,
        "--force",
        "--note",
        "rejection superseded by design decision",
        "--review-feedback-file",
        str(_feedback(m, "arbiter-feedback.md")),
    )

    assert result.exit_code == 0, result.output
    # The drop is announced (#6652 warning), not silent.
    assert "was not recorded" in result.output
    assert "arbiter override" in result.output
    # The arbiter decision durably carries the note, not the file.
    probes = override_probes(m, WP, result.output)
    assert probes["raw_log_review_override"] is True
    assert probes["reduced_overrides"] is True
    # ... and the recorded reason is the note-derived shape, not a generic one
    # (T004: pin `[custom] <note>` per arbiter.py's four-field ReviewOverride).
    overrides = get_arbiter_overrides_for_wp(m.feature_dir, WP)
    assert len(overrides) == 1
    assert overrides[0]["explanation"] == "rejection superseded by design decision"
    assert overrides[0]["category"] == "custom"
    # I-4: no approval review cycle is fabricated for the file.
    assert review_cycle_files(m) == rejection_cycles


def test_arbiter_override_without_feedback_file_is_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = build_mission(tmp_path, monkeypatch)
    drive_to_for_review(m)
    reject(m, "for_review_to_planned")

    result = move(m, WP, "approved", REVIEWER, "--force", "--note", "rejection superseded by design decision")

    assert result.exit_code == 0, result.output
    assert "was not recorded" not in result.output


# ---------------------------------------------------------------------------
# Unit matrix on the pure guard (#6699): the refusal arms exactly on the
# non-recordable edges; recordable-edge messages stay byte-stable.
# ---------------------------------------------------------------------------


@pytest.mark.fast
@pytest.mark.parametrize(
    ("old_lane", "target_lane"),
    [
        ("planned", "claimed"),
        ("claimed", "in_progress"),
        ("in_progress", "for_review"),
        ("for_review", "in_review"),
        ("for_review", "in_progress"),  # forced rework edge: writes no review cycle either (#6699)
        ("in_progress", "blocked"),
        ("planned", "canceled"),
    ],
)
def test_guard_refuses_feedback_file_on_non_recordable_edges(old_lane: str, target_lane: str, tmp_path: Path) -> None:
    refusal = _guard_feedback_file(
        _base_request(
            old_lane=old_lane,
            target_lane=target_lane,
            feedback_provided=True,
            feedback_source=str(tmp_path / "fb.md"),
            feedback_exists=True,
            feedback_is_file=True,
            feedback_content=None,
        )
    )
    assert isinstance(refusal, RefuseExit1), f"{old_lane} -> {target_lane} must refuse the flag"
    assert f"from '{old_lane}' to '{target_lane}'" in refusal.error
    assert "--review-feedback-file" in refusal.error
    assert "no review cycle" in refusal.error


@pytest.mark.fast
def test_guard_refusal_message_names_the_recordable_families_and_the_note_escape(tmp_path: Path) -> None:
    """NFR-002 wording pins (reviewer nit 2): families + --note suggestion drift-visible."""
    refusal = _guard_feedback_file(
        _base_request(
            old_lane="in_progress",
            target_lane="for_review",
            feedback_provided=True,
            feedback_source=str(tmp_path / "fb.md"),
            feedback_exists=True,
            feedback_is_file=True,
            feedback_content=None,
        )
    )
    assert isinstance(refusal, RefuseExit1)
    assert "review-rejection edges" in refusal.error
    assert "--to planned" in refusal.error
    assert "in_review -> in_progress" in refusal.error
    assert "approval edges" in refusal.error
    assert "approved / --to done" in refusal.error
    assert "--note" in refusal.error


@pytest.mark.fast
@pytest.mark.parametrize(
    ("old_lane", "target_lane"),
    [
        ("for_review", "planned"),  # review-rejection edge (any * -> planned)
        ("in_review", "planned"),  # review-rejection edge
        ("in_review", "in_progress"),  # re-implement edge (#4899)
        ("in_review", "approved"),  # approval edge
        ("planned", "done"),  # approval edge
    ],
)
def test_guard_leaves_recordable_edges_alone(old_lane: str, target_lane: str, tmp_path: Path) -> None:
    req = _base_request(
        old_lane=old_lane,
        target_lane=target_lane,
        feedback_provided=True,
        feedback_source=str(tmp_path / "fb.md"),
        feedback_exists=True,
        feedback_is_file=True,
        feedback_content="feedback\n",
    )
    assert _guard_feedback_file(req) is None, f"{old_lane} -> {target_lane} must not refuse a usable file"
    # And the full decision still emits on these edges (no new guard slot bites).
    outcome = decide_transition(req)
    assert isinstance(outcome, Emit), f"{old_lane} -> {target_lane}: {outcome!r}"


@pytest.mark.fast
def test_guard_missing_file_message_is_byte_stable_on_recordable_edges(tmp_path: Path) -> None:
    missing = str(tmp_path / "missing.md")
    refusal = _guard_feedback_file(
        _base_request(
            old_lane="for_review",
            target_lane="planned",
            feedback_provided=True,
            feedback_source=missing,
            feedback_exists=False,
            feedback_is_file=False,
        )
    )
    assert isinstance(refusal, RefuseExit1)
    assert refusal.error == f"Review feedback file not found: {missing}"


@pytest.mark.fast
def test_guard_no_flag_is_silent_on_every_edge() -> None:
    assert _guard_feedback_file(_base_request(old_lane="in_progress", target_lane="for_review")) is None


@pytest.mark.fast
def test_guard_edge_arm_precedes_the_path_checks(tmp_path: Path) -> None:
    """A bogus path on a non-recordable edge gets the edge message, not 'not found'."""
    refusal = _guard_feedback_file(
        _base_request(
            old_lane="in_progress",
            target_lane="for_review",
            feedback_provided=True,
            feedback_source=str(tmp_path / "does-not-exist.md"),
            feedback_exists=False,
            feedback_is_file=False,
        )
    )
    assert isinstance(refusal, RefuseExit1)
    assert "no review cycle" in refusal.error
    assert "not found" not in refusal.error
