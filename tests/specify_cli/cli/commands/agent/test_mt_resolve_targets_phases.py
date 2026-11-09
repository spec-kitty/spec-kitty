"""Characterisation pins for ``_mt_resolve_targets`` (#7410).

Written against the unsplit function and kept green across its split into
resolve, validate and write steps. Every collaborator is replaced by a
recorder (the ``tasks``-namespace seams on ``tasks``, the rest on
``tasks_move_task``), so the tests pin the orchestration: the order of every
call and refusal, the state fields the function fills, and each refusal's
rendered message and exit code (or its ``ActionContextError`` code).
``test_tasks_move_task_seam.py`` keeps pinning the ``tasks``-namespace patch
interception of the first half.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from mission_runtime import ActionContextError
from specify_cli.cli.commands.agent import tasks, tasks_move_task, workflow
from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState
from specify_cli.status import Lane
from specify_cli.upgrade.pre30_guard import Pre30LayoutError

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "probe-mission-01KZZZZZ"
_PROTECTED = "protected branch: refusing the status commit"
_SELF_REVIEW = "--self-review-fallback needs --intended-reviewer"


@dataclass
class Harness:
    """Recorder state shared by the fakes."""

    tmp: Path
    calls: list[str] = field(default_factory=list)
    kwargs: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    project_root: Path | None = None
    auto_commit_default: bool = True
    skip_commit: bool = False
    protected_error: str | None = None
    self_review_error: str | None = None
    pre30: bool = False
    old_lane: Lane = Lane.PLANNED

    @property
    def main_root(self) -> Path:
        return self.tmp / "main"

    @property
    def coord_dir(self) -> Path:
        return self.tmp / "coord" / "kitty-specs" / _SLUG

    def record(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append(name)
        self.kwargs[name] = {"args": args, **kwargs}


def _install(monkeypatch: pytest.MonkeyPatch, h: Harness) -> None:
    def fake(name: str, result: Any = None) -> Any:
        def _fn(*args: Any, **kwargs: Any) -> Any:
            h.record(name, *args, **kwargs)
            return result() if callable(result) else result

        return _fn

    def output_error(json_output: bool, message: str) -> None:
        h.record("_output_error", json_output, message)
        h.errors.append(message)

    def pre30(feature_dir: Path) -> None:
        h.record("check_pre30_layout", feature_dir)
        if h.pre30:
            raise Pre30LayoutError(feature_dir, ["planned"])

    def placement(root: Path, slug: str, *, owned: Any = None) -> Any:
        h.record("placement_seam", root, slug, owned=owned)
        return SimpleNamespace(read_dir=lambda kind: h.tmp / "primary" / str(kind))

    ports = SimpleNamespace(coord=SimpleNamespace(feature_write_dir=fake("feature_write_dir", lambda: h.coord_dir)))
    h.kwargs["ports"] = {"ports": ports}

    monkeypatch.setattr(tasks, "_refuse_unparseable_agent", fake("_refuse_unparseable_agent"))
    monkeypatch.setattr(tasks, "locate_project_root", fake("locate_project_root", lambda: h.project_root))
    monkeypatch.setattr(tasks, "_output_error", output_error)
    monkeypatch.setattr(tasks, "_emit_sparse_session_warning", fake("_emit_sparse_session_warning"))
    monkeypatch.setattr(tasks, "get_auto_commit_default", fake("get_auto_commit_default", lambda: h.auto_commit_default))
    monkeypatch.setattr(tasks, "_find_mission_slug", fake("_find_mission_slug", _SLUG))
    monkeypatch.setattr(tasks, "_ensure_target_branch_checked_out", fake("_ensure_target_branch_checked_out", lambda: (h.main_root, "main")))
    monkeypatch.setattr(tasks, "_skip_target_branch_commit", fake("_skip_target_branch_commit", lambda: h.skip_commit))
    monkeypatch.setattr(tasks, "_protected_branch_status_commit_error", fake("_protected_branch_status_commit_error", lambda: h.protected_error))
    monkeypatch.setattr(tasks, "locate_work_package", fake("locate_work_package", "wp-object"))
    monkeypatch.setattr(workflow, "_resolve_dispatch_binding", fake("_resolve_dispatch_binding", "binding"))
    monkeypatch.setattr(tasks_move_task, "placement_seam", placement)
    monkeypatch.setattr(tasks_move_task, "resolve_mission_identity", fake("resolve_mission_identity", SimpleNamespace(mission_id="01KZZZZZMISSIONID000000000")))
    monkeypatch.setattr(tasks_move_task, "_self_review_fallback_option_error", fake("_self_review_fallback_option_error", lambda: h.self_review_error))
    monkeypatch.setattr(tasks_move_task, "_mt_warn_worktree_kitty_specs", fake("_mt_warn_worktree_kitty_specs"))
    monkeypatch.setattr(tasks_move_task, "check_pre30_layout", pre30)
    monkeypatch.setattr(tasks_move_task, "_read_transactional_wp_lane", fake("_read_transactional_wp_lane", lambda: h.old_lane))
    monkeypatch.setattr(tasks_move_task, "_mt_guard_planned_boundary_lanes", fake("_mt_guard_planned_boundary_lanes"))
    monkeypatch.setattr(tasks_move_task, "_mt_resolve_owned_review_base", fake("_mt_resolve_owned_review_base", "base-sha"))
    monkeypatch.setattr(tasks_move_task, "_mt_resolve_current_agent", fake("_mt_resolve_current_agent", "prior-agent"))
    monkeypatch.setattr(tasks_move_task, "_mt_preflight_owned_request", fake("_mt_preflight_owned_request"))

    def apply_owned(st: _MoveTaskState, owned: Any) -> None:
        h.record("_mt_apply_owned_targets", st, owned)
        st.mission_slug = owned.mission_slug
        st.main_repo_root, st.target_branch = owned.repository_root, owned.write_branch

    monkeypatch.setattr(tasks_move_task, "_mt_apply_owned_targets", apply_owned)


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Harness:
    h = Harness(tmp=tmp_path, project_root=tmp_path / "checkout")
    _install(monkeypatch, h)
    return h


def _state(**overrides: Any) -> _MoveTaskState:
    kwargs: dict[str, Any] = {
        "task_id": "WP01",
        "to": "doing",
        "mission": _SLUG,
        "agent": "claude",
        "assignee": None,
        "shell_pid": None,
        "note": None,
        "review_feedback_file": None,
        "approval_ref": None,
        "reviewer": None,
        "self_review_fallback": False,
        "intended_reviewer": None,
        "reviewer_failure_reason": None,
        "done_override_reason": None,
        "force": False,
        "tracker_ref": None,
        "skip_review_artifact_check": False,
        "auto_commit": None,
        "json_output": True,
    }
    kwargs.update(overrides)
    return _MoveTaskState(**kwargs)


def _resolve(h: Harness, st: _MoveTaskState) -> None:
    tasks_move_task._mt_resolve_targets(st, h.kwargs["ports"]["ports"])


def _resolved_fields(st: _MoveTaskState) -> dict[str, Any]:
    return {
        "target_lane": st.target_lane,
        "repo_root": st.repo_root,
        "resolved_auto_commit": st.resolved_auto_commit,
        "mission_slug": st.mission_slug,
        "main_repo_root": st.main_repo_root,
        "target_branch": st.target_branch,
        "resolved_binding": st.resolved_binding,
        "skip_target_branch_commit": st.skip_target_branch_commit,
        "tracker_ref_values": st.tracker_ref_values,
        "mt_feature_dir": st.mt_feature_dir,
        "feature_dir": st.feature_dir,
        "wp": st.wp,
        "old_lane": st.old_lane,
        "review_base_ref": st.review_base_ref,
        "current_agent": st.current_agent,
    }


_PLAIN_ORDER = [
    "_refuse_unparseable_agent",
    "locate_project_root",
    "_emit_sparse_session_warning",
    "get_auto_commit_default",
    "_find_mission_slug",
    "_ensure_target_branch_checked_out",
    "_resolve_dispatch_binding",
    "_skip_target_branch_commit",
    "_protected_branch_status_commit_error",
    "_mt_warn_worktree_kitty_specs",
    "feature_write_dir",
    "check_pre30_layout",
    "locate_work_package",
    "_read_transactional_wp_lane",
    "_mt_guard_planned_boundary_lanes",
    "_mt_resolve_current_agent",
]


# ---------------------------------------------------------------------------
# Resolution: order and the fields it fills
# ---------------------------------------------------------------------------


def test_plain_resolution_order_and_fields(harness: Harness) -> None:
    st = _state(tracker_ref=[" ISSUE-1 ", "", "  ", "ISSUE-2"])
    _resolve(harness, st)

    assert harness.calls == _PLAIN_ORDER
    assert harness.errors == []
    assert _resolved_fields(st) == {
        "target_lane": Lane.IN_PROGRESS,
        "repo_root": harness.tmp / "checkout",
        "resolved_auto_commit": True,
        "mission_slug": _SLUG,
        "main_repo_root": harness.main_root,
        "target_branch": "main",
        "resolved_binding": "binding",
        "skip_target_branch_commit": False,
        "tracker_ref_values": ("ISSUE-1", "ISSUE-2"),
        "mt_feature_dir": harness.coord_dir,
        "feature_dir": harness.coord_dir,
        "wp": "wp-object",
        "old_lane": Lane.PLANNED,
        "review_base_ref": None,
        "current_agent": "prior-agent",
    }
    binding = harness.kwargs["_resolve_dispatch_binding"]
    assert binding["action"] == "implement"
    assert binding["mission_id"] is None
    assert binding["repo_root"] == harness.main_root
    assert harness.kwargs["_find_mission_slug"]["repo_root"] == harness.tmp / "checkout"
    assert harness.kwargs["locate_work_package"]["args"] == (harness.tmp / "checkout", _SLUG, "WP01")
    assert harness.kwargs["_protected_branch_status_commit_error"]["args"] == ("main", harness.main_root, "spec-kitty agent tasks move-task", _SLUG)


def test_explicit_auto_commit_skips_the_project_default(harness: Harness) -> None:
    st = _state(auto_commit=False)
    _resolve(harness, st)

    assert "get_auto_commit_default" not in harness.calls
    assert "_skip_target_branch_commit" not in harness.calls
    assert "_protected_branch_status_commit_error" not in harness.calls
    assert st.resolved_auto_commit is False


def test_skipped_target_branch_commit_bypasses_the_protected_check(harness: Harness) -> None:
    harness.skip_commit = True
    harness.protected_error = _PROTECTED
    st = _state()
    _resolve(harness, st)

    assert st.skip_target_branch_commit is True
    assert "_protected_branch_status_commit_error" not in harness.calls
    assert harness.errors == []


def test_invocation_id_reads_the_mission_id_for_the_binding(harness: Harness) -> None:
    st = _state(invocation_id="01KZZZZZINVOCATION00000000", to="approved")
    _resolve(harness, st)

    assert harness.calls.index("placement_seam") < harness.calls.index("_resolve_dispatch_binding")
    assert harness.kwargs["placement_seam"]["args"] == (harness.main_root, _SLUG)
    binding = harness.kwargs["_resolve_dispatch_binding"]
    assert binding["mission_id"] == "01KZZZZZMISSIONID000000000"
    assert binding["action"] == "review"


# ---------------------------------------------------------------------------
# Refusals: message, exit code and how far the function got
# ---------------------------------------------------------------------------


def test_missing_project_root_refuses_first(harness: Harness) -> None:
    harness.project_root = None
    st = _state()

    with pytest.raises(typer.Exit) as exit_info:
        _resolve(harness, st)

    assert exit_info.value.exit_code == 1
    assert harness.errors == ["Could not locate project root"]
    assert harness.calls == ["_refuse_unparseable_agent", "locate_project_root", "_output_error"]


def test_protected_branch_refuses_before_the_event_log_read(harness: Harness) -> None:
    harness.protected_error = _PROTECTED
    st = _state()

    with pytest.raises(typer.Exit) as exit_info:
        _resolve(harness, st)

    assert exit_info.value.exit_code == 1
    assert harness.errors == [_PROTECTED]
    assert harness.calls[-3:] == ["_protected_branch_status_commit_error", "_self_review_fallback_option_error", "_output_error"]
    assert "feature_write_dir" not in harness.calls


def test_protected_branch_reports_a_self_review_option_error_instead(harness: Harness) -> None:
    harness.protected_error = _PROTECTED
    harness.self_review_error = _SELF_REVIEW
    st = _state(self_review_fallback=True, to="approved", force=True)

    with pytest.raises(typer.Exit) as exit_info:
        _resolve(harness, st)

    assert exit_info.value.exit_code == 1
    assert harness.errors == [_SELF_REVIEW]
    option_check = harness.kwargs["_self_review_fallback_option_error"]
    assert option_check == {
        "args": (),
        "enabled": True,
        "target_lane": "approved",
        "force": True,
        "intended_reviewer": None,
        "failure_reason": None,
    }


def test_pre30_layout_refuses_before_locating_the_work_package(harness: Harness) -> None:
    harness.pre30 = True
    st = _state()

    with pytest.raises(typer.Exit) as exit_info:
        _resolve(harness, st)

    assert exit_info.value.exit_code == 1
    assert harness.errors == [
        "Pre-3.0 layout detected (tasks/planned/ directories or frontmatter lane state).\nRun `spec-kitty upgrade` to migrate before continuing."
    ]
    assert harness.calls[-2:] == ["check_pre30_layout", "_output_error"]
    assert st.mt_feature_dir == harness.coord_dir


# ---------------------------------------------------------------------------
# Owned checkout arm
# ---------------------------------------------------------------------------


def _owned(h: Harness) -> SimpleNamespace:
    return SimpleNamespace(owned_root=h.tmp / "owned", repository_root=h.tmp / "repo", write_branch="kitty/mission-probe", mission_slug=_SLUG)


def test_owned_resolution_uses_the_validated_checkout(harness: Harness) -> None:
    owned = _owned(harness)
    st = _state(owned=owned, to="for_review")
    harness.old_lane = Lane.IN_PROGRESS
    _resolve(harness, st)

    assert harness.calls == [
        "_refuse_unparseable_agent",
        "_mt_preflight_owned_request",
        "_emit_sparse_session_warning",
        "get_auto_commit_default",
        "_mt_apply_owned_targets",
        "_resolve_dispatch_binding",
        "_protected_branch_status_commit_error",
        "_mt_warn_worktree_kitty_specs",
        "feature_write_dir",
        "check_pre30_layout",
        "locate_work_package",
        "_read_transactional_wp_lane",
        "_mt_guard_planned_boundary_lanes",
        "_mt_resolve_owned_review_base",
        "_mt_resolve_current_agent",
    ]
    assert st.repo_root == harness.tmp / "owned"
    assert st.main_repo_root == harness.tmp / "repo"
    assert st.target_branch == "kitty/mission-probe"
    assert st.skip_target_branch_commit is False
    assert st.review_base_ref == "base-sha"
    assert harness.kwargs["_resolve_dispatch_binding"]["repo_root"] == harness.tmp / "owned"
    assert harness.kwargs["locate_work_package"]["owned"] is owned


def test_owned_checkout_refuses_an_unsupported_source_lane(harness: Harness) -> None:
    st = _state(owned=_owned(harness), to="in_progress")
    harness.old_lane = Lane.DONE

    with pytest.raises(ActionContextError) as error:
        _resolve(harness, st)

    assert error.value.code == "OWNED_TRANSITION_UNSUPPORTED"
    assert str(error.value) == "Owned checkout does not support transitions from this lane."
    assert harness.calls[-1] == "_read_transactional_wp_lane"
