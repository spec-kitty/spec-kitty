"""#3578 — the rollback-to-``planned`` operator signal (fail-loud sweep, M4).

A rollback to ``planned`` silently applied three deltas: it reset every roster
subtask, released the runtime claim, and cleared the review-override slot. These
pins assert the fail-loud discipline (epics #3410/#3549) is now honored:

* SC-002 — the reset count reaches the operator as BOTH a ``--json`` field and a
  human line, and the two sibling actions are named.
* SC-003 — the roster distinguishes a subtask completed in an earlier cycle from
  one never started; the flat reset no longer conflates work-state with
  review-state.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.cli.commands.agent.tasks_move_task import (
    _RollbackResetSummary,
    _build_claim_review_override,
    _mt_apply_rollback_signal,
    _mt_build_rollback_summary,
    _mt_rollback_signal_lines,
    _mt_rollback_subtasks_reset,
)
from specify_cli.cli.commands.agent.tasks_move_task_executor import _mt_prepare_rollback_reset, _mt_rollback_reason
from specify_cli.status import emit_inner_state_changed
from specify_cli.status.models import Lane, SubtaskStatus, WPInnerStateDelta

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "rollback-signal-demo"


def _seed_feature(tmp_path: Path, roster: list[str]) -> Path:
    feature_dir = tmp_path / "kitty-specs" / _SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(f'{{"mission_slug":"{_SLUG}","topology":"single_branch"}}\n', encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n\nNo checkbox rows.\n", encoding="utf-8")
    lines = ["---", "work_package_id: WP01", "dependencies: []"]
    if roster:
        lines.append("subtasks:")
        lines += [f"  - {tid}" for tid in roster]
    else:
        lines.append("subtasks: []")
    lines += ["---", "", "# WP01", ""]
    (feature_dir / "tasks" / "WP01-core.md").write_text("\n".join(lines), encoding="utf-8")
    return feature_dir


def _ports(feature_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(fs=SimpleNamespace(planning_read_dir=lambda _handle, *, kind: feature_dir))


def _st(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(main_repo_root=tmp_path, mission_slug=_SLUG, task_id="WP01")


# --------------------------------------------------------------------------- #
# SC-003 — work-state / review-state split is not conflated
# --------------------------------------------------------------------------- #


def test_rollback_summary_splits_completed_from_never_started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A subtask DONE in an earlier cycle is distinguishable from a never-started one."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    feature_dir = _seed_feature(tmp_path, ["T001", "T002", "T003", "T004"])
    # T001 was completed in an earlier cycle; T002 was in progress; T003 never
    # started; T004 was deliberately skipped — the pre-reset snapshot carries that
    # work-state. A skip is an operator decision, so the rollback must not revoke it.
    emit_inner_state_changed(
        feature_dir,
        "WP01",
        WPInnerStateDelta(subtasks={"T001": Lane.DONE, "T002": Lane.IN_PROGRESS, "T004": SubtaskStatus.SKIPPED}),
        actor="test",
        mission_slug=_SLUG,
        repo_root=tmp_path,
    )
    reset = _mt_rollback_subtasks_reset(_st(tmp_path), _ports(feature_dir))
    assert "T004" not in reset  # the deliberate skip survives the rollback

    summary = _mt_build_rollback_summary(_st(tmp_path), _ports(feature_dir), reset)

    assert summary.previously_completed == ("T001",)
    assert set(summary.never_completed) == {"T002", "T003"}
    # The two buckets are disjoint — a completed subtask is never reported as
    # never-completed (the conflation #3578 SC-003 forbids).
    assert set(summary.previously_completed).isdisjoint(summary.never_completed)
    assert set(summary.reset_ids) == {"T001", "T002", "T003"}
    assert summary.reset_count == 3


def test_rollback_summary_all_never_started_when_no_snapshot(tmp_path: Path) -> None:
    """Fail-closed: with no snapshot, every roster id reads as never-completed."""
    feature_dir = _seed_feature(tmp_path, ["T001", "T002"])
    reset = _mt_rollback_subtasks_reset(_st(tmp_path), _ports(feature_dir))

    summary = _mt_build_rollback_summary(_st(tmp_path), _ports(feature_dir), reset)

    assert summary.previously_completed == ()
    assert set(summary.never_completed) == {"T001", "T002"}


# --------------------------------------------------------------------------- #
# SC-002 — siblings surfaced + set on the state by the override builder
# --------------------------------------------------------------------------- #


def test_build_claim_review_override_sets_rollback_summary(tmp_path: Path) -> None:
    """The override builder records the summary so ``_mt_output`` can emit it."""
    feature_dir = _seed_feature(tmp_path, ["T001"])
    st = _st(tmp_path)

    _build_claim_review_override(st, _ports(feature_dir))

    summary = st.rollback_reset_summary
    assert isinstance(summary, _RollbackResetSummary)
    assert summary.reset_ids == ("T001",)
    assert summary.claim_released is True
    assert summary.review_override_cleared is True
    # #7582: computed once onto the state, with the full scope and a derived reason.
    assert st.rollback_reset_map == {"T001": Lane.PLANNED}
    assert summary.scope == "full"
    assert summary.reason.startswith("rollback to planned: ")


def test_build_claim_review_override_summary_survives_empty_roster(tmp_path: Path) -> None:
    """Even an empty roster still records the two sibling actions (FR-002)."""
    feature_dir = _seed_feature(tmp_path, [])
    st = _st(tmp_path)

    _build_claim_review_override(st, _ports(feature_dir))

    summary = st.rollback_reset_summary
    assert summary.reset_ids == ()
    assert summary.reset_count == 0
    assert summary.previously_completed == ()
    assert summary.never_completed == ()
    assert summary.claim_released is True
    assert summary.review_override_cleared is True


# --------------------------------------------------------------------------- #
# SC-002 — the operator signal reaches both the JSON envelope and the human line
# --------------------------------------------------------------------------- #


def _summary() -> _RollbackResetSummary:
    return _RollbackResetSummary(
        reset_ids=("T001", "T002"),
        previously_completed=("T001",),
        never_completed=("T002",),
        claim_released=True,
        review_override_cleared=True,
    )


def test_rollback_signal_json_fields() -> None:
    """The count + split + siblings land as machine-readable ``--json`` fields."""
    result: dict[str, object] = {}
    _mt_apply_rollback_signal(result, _summary())

    assert result["subtasks_reset_count"] == 2
    assert result["subtasks_reset_ids"] == ["T001", "T002"]
    assert result["subtasks_previously_completed"] == ["T001"]
    assert result["subtasks_never_completed"] == ["T002"]
    assert result["runtime_claim_released"] is True
    assert result["review_override_cleared"] is True
    # #7582 FR-015: the scope and reason ride beside the unchanged #3578 keys.
    assert result["subtasks_reset_scope"] == "full"
    assert result["subtasks_reset_reason"] == ""


def test_rollback_signal_human_line_names_count_and_siblings() -> None:
    """The human line states the reset count, the split, and both sibling actions."""
    line = _mt_rollback_signal_lines(_summary())

    assert "2 subtask" in line
    assert "planned" in line
    assert "T001" in line
    assert "earlier cycle" in line
    assert "runtime claim released" in line
    assert "review-override cleared" in line


# --------------------------------------------------------------------------- #
# #7582 — narrowing, the single reset authority, and the scope/reason line
# --------------------------------------------------------------------------- #


def test_rollback_subtasks_reset_narrows_to_only_and_never_resets_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``only`` keeps just the named roster ids; a skipped id stays out even when named."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    feature_dir = _seed_feature(tmp_path, ["T001", "T002", "T003"])
    emit_inner_state_changed(
        feature_dir,
        "WP01",
        WPInnerStateDelta(subtasks={"T003": SubtaskStatus.SKIPPED}),
        actor="test",
        mission_slug=_SLUG,
        repo_root=tmp_path,
    )

    reset = _mt_rollback_subtasks_reset(_st(tmp_path), _ports(feature_dir), only=frozenset({"T002", "T003"}))

    assert reset == {"T002": Lane.PLANNED}


def test_build_claim_review_override_reads_the_stored_map(tmp_path: Path) -> None:
    """The override reads the map computed before the PLANNED hop; it never recomputes it."""
    feature_dir = _seed_feature(tmp_path, ["T001", "T002"])
    st = _st(tmp_path)
    st.rollback_reset_map = {"T002": Lane.PLANNED}

    additions = _build_claim_review_override(st, _ports(feature_dir))

    assert additions["subtasks"] == {"T002": Lane.PLANNED}


def test_prepare_rollback_reset_records_narrowed_scope_and_operator_reason(tmp_path: Path) -> None:
    feature_dir = _seed_feature(tmp_path, ["T001", "T002"])
    st = _st(tmp_path)
    st.reset_subtasks_only = frozenset({"T002"})
    st.note = "  T002 regressed  "

    reset = _mt_prepare_rollback_reset(st, _ports(feature_dir))

    assert reset == {"T002": Lane.PLANNED}
    assert st.rollback_reset_map is reset
    summary = st.rollback_reset_summary
    assert summary.scope == "narrowed"
    assert summary.reason == "T002 regressed"
    assert summary.eligible_count == 2
    assert summary.record() == {"scope": "narrowed", "reset": ["T002"], "previously_completed": [], "reason": "T002 regressed"}


def test_rollback_reason_derived_from_edge_and_review_pointer(tmp_path: Path) -> None:
    st = _st(tmp_path)
    st.note = "   "
    st.old_lane = Lane.FOR_REVIEW
    st.review_feedback_pointer = "review-cycle://m/WP01/review-cycle-1.md"

    assert _mt_rollback_reason(st) == "rollback to planned: for_review -> planned (review-cycle://m/WP01/review-cycle-1.md)"
    st.review_feedback_pointer = None
    assert _mt_rollback_reason(st) == "rollback to planned: for_review -> planned"


def test_rollback_signal_human_line_names_narrowed_scope_and_reason() -> None:
    summary = replace(_summary(), reset_ids=("T002",), previously_completed=(), scope="narrowed", reason="T002 [regressed]", eligible_count=2)

    line = _mt_rollback_signal_lines(summary)

    # The reason is Rich-escaped so a bracketed reason is printed, not read as markup.
    assert "↺ Reset 1 of 2 subtask(s) to planned (narrowed: T002 \\[regressed])" in line


def test_rollback_signal_human_line_names_full_scope_and_reason() -> None:
    line = _mt_rollback_signal_lines(replace(_summary(), reason="rollback to planned: in_review -> planned"))

    assert "↺ Reset 2 subtask(s) to planned (full reset: rollback to planned: in_review -> planned)" in line
