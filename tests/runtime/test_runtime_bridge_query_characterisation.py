"""Characterisation of the runtime_bridge read path and decision mapping (#2560).

Mission ``runtime-bridge-query-seam-01M490EQ`` moves these functions out of
``runtime_bridge.py`` verbatim. Baseline coverage over the runtime_bridge test
surface left the branches below unexercised, so they are pinned here before
the move and must stay green after it.

Two rules keep these tests honest across the move:

* every function under test is reached through :func:`_owner`, one lookup
  table that names the module currently defining it (each extraction WP
  repoints its rows), never by patching an attribute of ``runtime_bridge``;
* collaborators are faked only on modules BELOW the moved code
  (``mission_runtime``, ``runtime.next.prompt_builder``,
  ``runtime_bridge_identity``, ``runtime_bridge_engine``) and through the
  deferred imports the moved code performs at call time, so a fake keeps
  intercepting wherever the function lives. Each fake records that it ran.

Not repeated here because an existing test already pins it without patching
the bridge: the ephemeral query run store is removed after a query
(``tests/next/test_query_mode_unit.py::test_fresh_run_query_omits_ephemeral_run_id``,
which fakes ``runtime_bridge_io``). ``_map_wp_step_decision``'s blocked-reason
branch needs a full WP-iteration fixture and is covered by the mapping's
blocked-path tests once they are repointed; it is left out on purpose.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from mission_runtime import ActionContextError
from runtime.next._internal_runtime.schema import MissionRuntimeError, NextDecision
from specify_cli.coordination.workspace import CoordinationWorkspaceUnavailable
from specify_cli.status import Lane
from specify_cli.status.models import StatusEvent
from specify_cli.status.store import append_event
from tests._owned_fixtures import mint_test_fact
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION = "char-mission"

#: Function name -> the ``runtime.next`` module that defines it today.
_OWNERS: dict[str, str] = {
    "_build_decision_required_prompt_file": "runtime_bridge_decision_mapping",
    "_reduced_wp_lane": "runtime_bridge_decision_mapping",
    "_count_wp_endings": "runtime_bridge_decision_mapping",
    "_resolve_wp_board_action": "runtime_bridge_decision_mapping",
    "_resolve_wp_board_review_action": "runtime_bridge_decision_mapping",
    "_WP_BOARD_DECLINE": "runtime_bridge_decision_mapping",
    "_finalized_task_board_override_step": "runtime_bridge_decision_mapping",
    "_wrap_with_decision_git_log": "runtime_bridge_decision_log",
    "DecisionGitLogUnavailable": "runtime_bridge_decision_log",
    "answer_decision_via_runtime": "runtime_bridge_query",
    "_query_read_runtime_plan": "runtime_bridge_query",
    "QueryModeValidationError": "runtime_bridge_query",
}


def _owner(name: str) -> Any:
    return getattr(importlib.import_module(f"runtime.next.{_OWNERS[name]}"), name)


def _decision_required(question: str | None) -> NextDecision:
    return NextDecision(
        kind="decision_required",
        run_id="run-1",
        mission_key="software-dev",
        decision_id="dec-1",
        question=question,
        options=["yes", "no"],
    )


# ---------------------------------------------------------------------------
# Decision mapping
# ---------------------------------------------------------------------------


class TestDecisionRequiredPromptFile:
    def test_no_question_returns_none_without_building(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr("runtime.next.prompt_builder.build_decision_prompt", lambda **kw: calls.append(kw))

        result = _owner("_build_decision_required_prompt_file")(_decision_required(None), _MISSION, tmp_path, "claude")

        assert result is None
        assert calls == []

    def test_built_prompt_path_is_returned_as_string(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        calls: list[dict[str, Any]] = []
        prompt = tmp_path / "decision-prompt.md"

        def _fake_build(**kwargs: Any) -> tuple[str, Path]:
            calls.append(kwargs)
            return "body", prompt

        monkeypatch.setattr("runtime.next.prompt_builder.build_decision_prompt", _fake_build)

        result = _owner("_build_decision_required_prompt_file")(_decision_required("Proceed?"), _MISSION, tmp_path, "claude")

        assert result == str(prompt)
        assert calls == [
            {
                "question": "Proceed?",
                "options": ["yes", "no"],
                "decision_id": "dec-1",
                "mission_slug": _MISSION,
                "repo_root": tmp_path,
                "agent": "claude",
            }
        ]

    def test_builder_failure_degrades_to_none(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        calls: list[str] = []

        def _boom(**kwargs: Any) -> tuple[str, Path]:
            calls.append(kwargs["question"])
            raise OSError("disk full")

        monkeypatch.setattr("runtime.next.prompt_builder.build_decision_prompt", _boom)

        assert _owner("_build_decision_required_prompt_file")(_decision_required("Proceed?"), _MISSION, tmp_path, "claude") is None
        assert calls == ["Proceed?"]


def test_reduced_wp_lane_without_snapshot_is_uninitialized() -> None:
    assert _owner("_reduced_wp_lane")(None) == str(Lane.UNINITIALIZED)


def test_reduced_wp_lane_without_lane_key_is_genesis() -> None:
    assert _owner("_reduced_wp_lane")({}) == str(Lane.GENESIS)


def test_count_wp_endings_without_tasks_dir_is_zero(tmp_path: Path) -> None:
    assert _owner("_count_wp_endings")(tmp_path) == (0, 0)


def test_wp_board_action_declines_when_mission_context_is_unresolvable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    probes: list[str] = []

    class _UnresolvableSeam:
        def read_dir(self, kind: object) -> Path:
            probes.append(str(kind))
            raise ActionContextError("FEATURE_CONTEXT_UNRESOLVED", "no such mission")

    monkeypatch.setattr("mission_runtime.placement_seam", lambda *args, **kwargs: _UnresolvableSeam())

    action = _owner("_resolve_wp_board_action")(mission_slug=_MISSION, repo_root=tmp_path)

    assert action == _owner("_WP_BOARD_DECLINE")
    assert len(probes) == 1


def _all_done_board(feature_dir: Path) -> None:
    tasks = feature_dir / "tasks"
    tasks.mkdir(parents=True)
    (feature_dir / "meta.json").write_text('{"mission_type": "software-dev"}', encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))
    (tasks / "WP01.md").write_text("---\nwork_package_id: WP01\ndependencies: []\ntitle: WP01\n---\n# WP01\n", encoding="utf-8")
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-WP01-done",
            mission_slug=_MISSION,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.DONE,
            at="2026-01-01T00:00:00+00:00",
            actor="fixture",
            force=True,
            execution_mode="worktree",
        ),
    )


def test_wp_board_action_declines_a_finished_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A board whose override step is ``accept``/``done`` declines (no WP iteration)."""
    from runtime.next.decision import _compute_wp_progress

    feature_dir = tmp_path / "kitty-specs" / _MISSION
    _all_done_board(feature_dir)
    assert _owner("_finalized_task_board_override_step")(feature_dir, _compute_wp_progress(feature_dir), status_dir=feature_dir) == "done"
    contexts: list[str] = []

    class _Seam:
        def read_dir(self, kind: object) -> Path:
            return feature_dir

    def _context(repo_root: Path, mission_slug: str, **kwargs: Any) -> SimpleNamespace:
        contexts.append(mission_slug)
        return SimpleNamespace(artifact=lambda kind: SimpleNamespace(read_dir=feature_dir))

    monkeypatch.setattr("mission_runtime.placement_seam", lambda *args, **kwargs: _Seam())
    monkeypatch.setattr("mission_runtime.mission_context_for", _context)

    action = _owner("_resolve_wp_board_action")(mission_slug=_MISSION, repo_root=tmp_path)

    assert action == _owner("_WP_BOARD_DECLINE")
    assert contexts == [_MISSION]


def test_wp_board_review_action_blocks_when_reviewable_wp_vanished_on_reread(tmp_path: Path) -> None:
    board = tmp_path / "tasks"
    board.mkdir()

    action = _owner("_resolve_wp_board_review_action")(_MISSION, tmp_path, board, tmp_path)

    assert action.board_step == "review"
    assert action.wp_id is None
    assert action.blocked_reason is not None
    assert action.blocked_reason.startswith("Board reported a reviewable work package but none was found on re-read.")
    assert _MISSION in action.blocked_reason


# ---------------------------------------------------------------------------
# Decision-log wrapper
# ---------------------------------------------------------------------------


def test_unowned_coordination_workspace_failure_becomes_decision_git_log_unavailable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A non-owned caller gets the generic fail-closed refusal, with the cause suppressed."""
    seam_reads: list[str] = []

    class _PrimarySeam:
        def read_dir(self, kind: object) -> Path:
            seam_reads.append(str(kind))
            return tmp_path / "no-meta-here"  # read_topology raises -> non-coord topology

    def _unavailable(*args: Any, **kwargs: Any) -> str:
        raise CoordinationWorkspaceUnavailable(128, ["git", "worktree", "list"], stderr="fatal")

    monkeypatch.setattr("mission_runtime.placement_seam", lambda *args, **kwargs: _PrimarySeam())
    monkeypatch.setattr("runtime.next.runtime_bridge_identity._resolve_coordination_branch", _unavailable)

    with pytest.raises(_owner("DecisionGitLogUnavailable")) as excinfo:
        _owner("_wrap_with_decision_git_log")(object(), _MISSION, tmp_path)

    assert "DecisionGitLog construction failed for declared coordination topology mission" in str(excinfo.value)
    assert excinfo.value.__suppress_context__ is True
    assert excinfo.value.__cause__ is None
    assert seam_reads  # the stored-topology probe ran


def test_owned_coordination_workspace_failure_propagates_unwrapped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An owned caller gets the typed refusal itself, never DecisionGitLogUnavailable (#4867).

    This pins the outcome, not the arm: the refusal carries the owned
    ``error_code``, so the generic ``except Exception`` arm would re-raise it
    too (``_is_owned_coordination_unavailable``) if the dedicated
    ``except CoordinationWorkspaceUnavailable`` arm were ever removed.
    """
    refusal = CoordinationWorkspaceUnavailable(128, ["git", "worktree", "add"], stderr="fatal")
    resolves: list[str] = []

    def _unavailable(repo_root: Path, mission_slug: str, **kwargs: Any) -> object:
        resolves.append(mission_slug)
        raise refusal

    monkeypatch.setattr("mission_runtime.mission_context_for", _unavailable)
    owned_root = tmp_path / "owned-checkout"
    owned = mint_test_fact(
        repository_root=tmp_path,
        owned_root=owned_root,
        mission_dir=owned_root / "kitty-specs" / _MISSION,
        mission_slug=_MISSION,
        write_branch="codex/owned",
    )

    with pytest.raises(CoordinationWorkspaceUnavailable) as excinfo:
        _owner("_wrap_with_decision_git_log")(object(), _MISSION, tmp_path, owned=owned)

    assert excinfo.value is refusal
    assert resolves == [_MISSION]


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------


class TestAnswerDecisionPreconditions:
    def test_missing_feature_dir_refuses_with_exact_text(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        missing = tmp_path / "kitty-specs" / _MISSION
        resolved: list[str] = []

        def _resolve(repo_root: Path, *, action: str, feature: str, owned: object = None) -> SimpleNamespace:
            resolved.append(action)
            return SimpleNamespace(feature_dir=str(missing))

        monkeypatch.setattr("mission_runtime.resolve_action_context", _resolve)

        with pytest.raises(MissionRuntimeError) as excinfo:
            _owner("answer_decision_via_runtime")(_MISSION, "dec-1", "yes", "claude", tmp_path)

        assert str(excinfo.value) == f"Mission {_MISSION!r} not found; cannot answer decision 'dec-1'"
        assert resolved == ["tasks"]

    def test_typed_read_path_error_propagates_unchanged(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        error = ActionContextError("COORDINATION_BRANCH_DELETED", "coordination branch is gone")

        def _resolve(*args: Any, **kwargs: Any) -> SimpleNamespace:
            raise error

        monkeypatch.setattr("mission_runtime.resolve_action_context", _resolve)

        with pytest.raises(ActionContextError) as excinfo:
            _owner("answer_decision_via_runtime")(_MISSION, "dec-1", "yes", "claude", tmp_path)

        assert excinfo.value is error
        assert excinfo.value.code == "COORDINATION_BRANCH_DELETED"


class TestQueryReadRuntimePlan:
    def test_query_validation_error_is_reraised_unwrapped(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        validation_error = _owner("QueryModeValidationError")("template drifted")
        reads: list[Path] = []

        def _read_snapshot(run_dir: Path) -> object:
            reads.append(run_dir)
            raise validation_error

        monkeypatch.setattr("runtime.next.runtime_bridge_engine._read_snapshot", _read_snapshot)

        with pytest.raises(_owner("QueryModeValidationError")) as excinfo:
            _owner("_query_read_runtime_plan")(SimpleNamespace(run_dir=str(tmp_path)), _MISSION, "software-dev", tmp_path)

        assert excinfo.value is validation_error
        assert reads == [tmp_path]

    def test_other_failure_is_wrapped_with_the_mission_slug(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        cause = RuntimeError("snapshot unreadable")

        def _read_snapshot(run_dir: Path) -> object:
            raise cause

        monkeypatch.setattr("runtime.next.runtime_bridge_engine._read_snapshot", _read_snapshot)

        with pytest.raises(_owner("QueryModeValidationError")) as excinfo:
            _owner("_query_read_runtime_plan")(SimpleNamespace(run_dir=str(tmp_path)), _MISSION, "software-dev", tmp_path)

        assert str(excinfo.value) == f"Could not read query state for mission '{_MISSION}': snapshot unreadable"
        assert excinfo.value.__cause__ is cause
