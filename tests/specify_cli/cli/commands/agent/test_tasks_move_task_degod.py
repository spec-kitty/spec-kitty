"""Characterization + focused-helper tests for the WP07 degod (#2649, folds #2604).

Pins BEFORE and AFTER the WP07 decomposition of ``tasks_move_task.py``:

- T033: ``_do_move_task``'s parameter count stays at or under the local ≤13
  gate now that the 21-parameter signature collapsed to a
  ``_MoveTaskArgs`` param object + ``ports``.

Re-scope (WP10 closeout, 2026-07-19): the ``_mt_uncheck_rollback_subtasks``
tasks.md-checkbox-uncheck handler (and its ``_mt_attempt_uncheck_write`` /
``_mt_commit_uncheck_tasks_md`` helpers) were **deleted** by WP04's subtask
eviction — the rollback-to-planned reset is now an event-sourced
``InnerStateChanged`` ``subtasks`` delta (``_mt_rollback_subtasks_reset``), not
a checkbox rewrite.

Re-scope (#2816/IC-06, WP07): the T032 degrade-never-crash pin and the T034
focused-helper pins were **deleted** with the surface they exercised — the
now production-dead WP-file write/commit closure (``_mt_commit_wp_file`` +
``_mt_write_and_commit_wp_file`` + ``_mt_wp_commit_message`` /
``_mt_report_commit_outcome`` / ``_mt_wp_commit_success_message``) that WP05
orphaned when it removed ``_mt_dual_write_wp_file`` (the closure's last caller).
Only the T033 param-object ceiling gate survives.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.status import Lane, ReviewOverride
from specify_cli.cli.commands.agent.tasks_move_task import (
    _MoveTaskArgs,
    _build_claim_review_override,
    _do_move_task,
    _mt_emit_runtime_state,
    _mt_rollback_subtasks_reset,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MODULE = "specify_cli.cli.commands.agent.tasks_move_task"


# --------------------------------------------------------------------------- #
# T033 — _do_move_task parameter-object ceiling (the ONE hard local gate)
# --------------------------------------------------------------------------- #


def test_do_move_task_param_count_at_or_under_ceiling() -> None:
    params = inspect.signature(_do_move_task).parameters
    assert len(params) <= 13, (
        f"_do_move_task has {len(params)} parameters — must stay <=13 "
        "(the parameter-object ceiling, T033/#2649)."
    )


def test_do_move_task_accepts_move_task_args_param_object() -> None:
    params = list(inspect.signature(_do_move_task).parameters)
    assert params[0] == "args"
    assert "ports" in params


def test_move_task_args_field_set_matches_pre_extraction_signature() -> None:
    """The param object groups every raw CLI-facing input the pre-extraction
    21-parameter signature carried (minus ``ports``, which stays a separate DI
    seam) — NFR-002 behavior preservation — plus ``summary``, the #4327
    inline gist option added alongside ``--note``."""
    expected = {
        "task_id",
        "to",
        "mission",
        "agent",
        "assignee",
        "shell_pid",
        "note",
        "review_feedback_file",
        "approval_ref",
        "summary",
        "reviewer",
        "self_review_fallback",
        "intended_reviewer",
        "reviewer_failure_reason",
        "done_override_reason",
        "force",
        "tracker_ref",
        "skip_review_artifact_check",
        "auto_commit",
        "json_output",
        "skip_pre_review_gate",
        "model",
        "profile",
        "invocation_id",
        "owned_checkout",
    }
    assert set(_MoveTaskArgs.__dataclass_fields__) == expected


def test_rollback_subtask_reset_uses_authored_frontmatter_roster(tmp_path: Path) -> None:
    """Rollback remains complete after legacy tasks.md checkboxes disappear."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "tasks.md").write_text("# Tasks\n\nNo checkbox rows.\n", encoding="utf-8")
    (feature_dir / "tasks" / "WP01-core.md").write_text(
        "---\nwork_package_id: WP01\ndependencies: []\nsubtasks:\n  - T001\n  - T002\n---\n",
        encoding="utf-8",
    )
    st = SimpleNamespace(main_repo_root=tmp_path, mission_slug="demo", task_id="WP01")
    ports = SimpleNamespace(
        fs=SimpleNamespace(planning_read_dir=lambda _handle, *, kind: feature_dir)
    )

    assert _mt_rollback_subtasks_reset(st, ports) == {
        "T001": Lane.PLANNED,
        "T002": Lane.PLANNED,
    }


# --------------------------------------------------------------------------- #
# T007 (WP02, verdict-seam-boundary-hardening-01KZG179) — cc=14->11 campsite
# extraction out of ``_mt_emit_runtime_state``. Exercises the helper's output
# DIRECTLY (NFR-004): a skipped extract would otherwise pass silently once
# the same-WP migration branch alone lands the parent at ~cc14, still under
# the 15 ceiling.
# --------------------------------------------------------------------------- #


def test_build_claim_review_override_defaults_release_and_resets_subtasks(
    tmp_path: Path,
) -> None:
    """No pre-existing claim fields: the release marker
    (``release_runtime_claim=True``) applies, the authored subtask roster
    resets to ``planned``, and the ``review`` slot is an all-empty release
    sentinel."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "tasks.md").write_text("# Tasks\n\nNo checkbox rows.\n", encoding="utf-8")
    (feature_dir / "tasks" / "WP01-core.md").write_text(
        "---\nwork_package_id: WP01\ndependencies: []\nsubtasks:\n  - T001\n---\n",
        encoding="utf-8",
    )
    st = SimpleNamespace(main_repo_root=tmp_path, mission_slug="demo", task_id="WP01")
    ports = SimpleNamespace(
        fs=SimpleNamespace(planning_read_dir=lambda _handle, *, kind: feature_dir)
    )

    additions = _build_claim_review_override(st, ports)

    assert additions["subtasks"] == {"T001": Lane.PLANNED}
    assert additions["release_runtime_claim"] is True
    assert additions["review"] == ReviewOverride(at="", actor="", wp_id="", reason="")
    assert additions["review"].complete is False


def test_build_claim_review_override_release_marker_independent_of_existing_fields(
    tmp_path: Path,
) -> None:
    """partition-authority-residuals (#2960 follow-up): the release marker is
    set UNCONDITIONALLY by this pure builder — it no longer inspects the
    caller's already-staged fields to decide whether to release. Precedence
    over a SAME-move fresh claim re-plant (an explicit ``--agent``/
    ``--shell-pid`` override) is the reducer's job: ``_apply_annotation_delta``
    applies the release clear BEFORE its replace-slot loop, so a concrete
    value present in the same delta wins (see
    ``test_rollback_with_explicit_agent_replants_claim`` for the end-to-end
    proof). An empty authored subtask roster resets nothing; the review
    sentinel still applies unconditionally."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "tasks.md").write_text("# Tasks\n\nNo checkbox rows.\n", encoding="utf-8")
    (feature_dir / "tasks" / "WP01-core.md").write_text(
        "---\nwork_package_id: WP01\ndependencies: []\nsubtasks: []\n---\n",
        encoding="utf-8",
    )
    st = SimpleNamespace(main_repo_root=tmp_path, mission_slug="demo", task_id="WP01")
    ports = SimpleNamespace(
        fs=SimpleNamespace(planning_read_dir=lambda _handle, *, kind: feature_dir)
    )

    additions = _build_claim_review_override(st, ports)

    assert additions["release_runtime_claim"] is True
    assert "subtasks" not in additions, "an empty authored roster resets nothing"
    assert additions["review"] == ReviewOverride(at="", actor="", wp_id="", reason="")


def test_runtime_state_persistence_error_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A move cannot report success when its authoritative annotation is lost."""
    import specify_cli.coordination.status_transition as status_transition_module

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    # FR-007 (#2939): ``_mt_emit_runtime_state`` now routes the post-transition
    # annotation through the commit-durable ``emit_inner_state_changed_transactional``
    # seam (which commits on a coord topology, delegates to the uncommitted
    # ``emit_inner_state_changed`` otherwise). The propagation contract is unchanged;
    # only the intercept point moves to the new seam.
    monkeypatch.setattr(
        status_transition_module, "emit_inner_state_changed_transactional", _fail
    )
    st = SimpleNamespace(
        claim_emitted=False,
        agent="codex",
        resolved_binding=None,
        shell_pid=None,
        assignee=None,
        note_text=None,
        tracker_ref_values=(),
        target_lane=Lane.IN_PROGRESS,
        feature_dir=tmp_path,
        task_id="WP01",
        final_hop_actor="codex",
        actor="codex",
        mission_slug="demo",
        main_repo_root=tmp_path,
        json_output=True,
        # #3460: ``_mt_emit_runtime_state`` now branches on ``resolved_auto_commit``
        # to pick the transactional vs. uncommitted emitter. This test exercises
        # the durable-commit leg (the patched ``emit_inner_state_changed_transactional``),
        # so it must be True here.
        resolved_auto_commit=True,
    )

    with pytest.raises(OSError, match="disk full"):
        _mt_emit_runtime_state(st, SimpleNamespace())
