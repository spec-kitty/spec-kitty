"""Layer-4 seam interception tests for the WP08 mark_status-family relocation.

Mission ``tasks-py-degod-wave2-01KWH9EQ`` — parity-contract Layer 4 (NFR-002):
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/contracts/parity-contract.md``.

This file now carries ONE battery (the WP06 / dev-assist-retire-path-hardening
ruling, mission ``dev-assist-retire-path-hardening-01KXAVR0``, #2565):

1. **Interception** — each test patches ``...agent.tasks.<symbol>`` with a
   sentinel and drives a relocated ``_ms_*`` phase helper (or
   ``_default_mark_status_ports`` construction) THROUGH the moved body,
   asserting the sentinel is hit — proving the lazy ``_tasks.<attr>`` seam
   bridge preserves patch interception, not merely import resolution. The
   C-001 divergence wiring (REFUSE-exit-1 through
   ``_protected_branch_status_commit_error`` with NO
   ``_skip_target_branch_commit`` pre-gate) is pinned explicitly and
   positionally (``skip_mock.assert_not_called()``). This coverage is
   UNIQUE — no observable-contract test (including the coreless
   ``test_tasks_coreless_orchestration.py`` T033 projections) proves a
   call-site is still routed through the patchable ``tasks.<attr>`` seam,
   since those tests never patch ``tasks.<attr>`` to assert phase-helper
   routing; they drive ``_do_mark_status`` with injected Fake ports instead
   (coreless's two seam-patches merely suppress/pin ``emit_history_added`` /
   ``commit_for_mission``, neither of which this file carries a proof for). A same-object
   identity check cannot observe patchability either. KEEP is the default
   per the WP05 review ruling.

The **identity** battery (``test_tasks_binding_is_tasks_mark_status_object``,
parametrized over the 13-symbol move-set) and the exact-set completeness pin
(``test_move_set_matches_tasks_mark_status_defs``) were RETIRED at WP06:
both are mechanically subsumed by WP05's consolidated re-export guard —
``tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py``
(``test_tasks_binding_is_seam_object`` for identity;
``test_guard_symbol_is_genuinely_native_to_its_seam`` +
``test_guard_keyset_is_superset_of_all_six_seams_native_defs`` for the
exact-set/completeness claim over the same 13 ``tasks_mark_status`` symbols).

Seam checklist (per-symbol evidence):
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/seam-checklist.md``.
"""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer

from mission_runtime import MissionArtifactKind
from specify_cli.cli.commands.agent import tasks, tasks_mark_status
from specify_cli.cli.commands.agent.tasks_mark_status import _MarkStatusState
from specify_cli.cli.commands.agent.tasks_outline import (
    TaskIdResolutionFormat,
    TaskIdResolutionOutcome,
    TaskIdResult,
)

pytestmark = pytest.mark.fast

_TASKS = "specify_cli.cli.commands.agent.tasks"


class _SentinelHit(Exception):
    """Raised by sentinel patches to prove the patched attribute was called."""


def _make_state(**overrides: Any) -> _MarkStatusState:
    """A minimal ``_MarkStatusState`` (raw command inputs only) with overrides."""
    kwargs: dict[str, Any] = {
        "task_ids": ["T001"],
        "status": "done",
        "mission": "034-feature",
        "auto_commit": None,
        "json_output": True,
    }
    field_overrides = {k: v for k, v in overrides.items() if k in kwargs}
    kwargs.update(field_overrides)
    st = _MarkStatusState(**kwargs)
    for key, value in overrides.items():
        if key not in field_overrides:
            setattr(st, key, value)
    return st


def _not_found(task_id: str, fmt: TaskIdResolutionFormat | None = None) -> TaskIdResult:
    return TaskIdResult(
        id=task_id,
        outcome=TaskIdResolutionOutcome.NOT_FOUND,
        format=fmt,
        message=f"{task_id} was not found in any supported task format.",
    )


# ---------------------------------------------------------------------------
# Interception battery — patch tasks.<symbol>, drive the relocated body,
# assert the sentinel bites. All patches target the ``tasks`` namespace; the
# bodies live in ``tasks_mark_status`` (research.md D1 seam bridge).
# ---------------------------------------------------------------------------


def test_c001_auto_commit_input_no_longer_consults_protected_branch(
    tmp_path: Path,
) -> None:
    """Event-only mark-status never commits the primary tasks artifact."""
    st = _make_state(auto_commit=True)
    with (
        patch(f"{_TASKS}.locate_project_root", return_value=tmp_path) as locate_mock,
        patch(f"{_TASKS}._emit_sparse_session_warning") as sparse_mock,
        patch(f"{_TASKS}._find_mission_slug", return_value="034-feature") as slug_mock,
        patch(
            f"{_TASKS}._ensure_target_branch_checked_out",
            return_value=(tmp_path, "main"),
        ) as branch_mock,
        patch(
            f"{_TASKS}._protected_branch_status_commit_error",
            return_value="protected: refuse",
        ) as protected_mock,
        patch(f"{_TASKS}._skip_target_branch_commit") as skip_mock,
        patch(f"{_TASKS}._output_error") as error_mock,
    ):
        tasks_mark_status._ms_resolve_context(st)
    locate_mock.assert_called_once()
    sparse_mock.assert_called_once_with(
        tmp_path, command="spec-kitty agent tasks mark-status"
    )
    slug_mock.assert_called_once()
    branch_mock.assert_called_once_with(tmp_path, "034-feature", True)
    protected_mock.assert_not_called()
    skip_mock.assert_not_called()
    error_mock.assert_not_called()


def test_c001_protected_gate_not_consulted_when_auto_commit_resolves_false(
    tmp_path: Path,
) -> None:
    """C-001 wiring: with auto-commit resolved False (via the patched
    ``tasks.get_auto_commit_default`` D7 seam) the protected-branch refusal is
    NOT consulted and resolution completes."""
    st = _make_state(auto_commit=None)
    with (
        patch(f"{_TASKS}.locate_project_root", return_value=tmp_path),
        patch(f"{_TASKS}._emit_sparse_session_warning"),
        patch(f"{_TASKS}._find_mission_slug", return_value="034-feature"),
        patch(
            f"{_TASKS}._ensure_target_branch_checked_out",
            return_value=(tmp_path, "main"),
        ),
        patch(f"{_TASKS}.get_auto_commit_default", return_value=False) as auto_mock,
        patch(f"{_TASKS}._protected_branch_status_commit_error") as protected_mock,
        patch(f"{_TASKS}._skip_target_branch_commit") as skip_mock,
    ):
        tasks_mark_status._ms_resolve_context(st)
    auto_mock.assert_called_once_with(tmp_path)
    protected_mock.assert_not_called()
    skip_mock.assert_not_called()
    assert st.resolved_auto_commit is False
    assert st.target_branch == "main"


def test_patched_output_error_intercepts_validate_inputs_bad_status() -> None:
    """``tasks._output_error`` bites through ``_ms_validate_inputs``' invalid
    ``--status`` gate."""
    st = _make_state(status="approved")
    with (
        patch(f"{_TASKS}._output_error", side_effect=_SentinelHit) as error_mock,
        pytest.raises(_SentinelHit),
    ):
        tasks_mark_status._ms_validate_inputs(st)
    error_mock.assert_called_once_with(
        True, "Invalid status 'approved'. Must be 'done', 'pending', 'skipped', or 'not_applicable'."
    )


def test_patched_output_error_intercepts_validate_inputs_empty_ids() -> None:
    """``tasks._output_error`` bites through ``_ms_validate_inputs``' empty
    task-ID gate."""
    st = _make_state(task_ids=[])
    with (
        patch(f"{_TASKS}._output_error", side_effect=_SentinelHit) as error_mock,
        pytest.raises(_SentinelHit),
    ):
        tasks_mark_status._ms_validate_inputs(st)
    error_mock.assert_called_once_with(True, "At least one task ID is required")


def test_resolve_read_dir_routes_tasks_index_kind_through_fs_port(tmp_path: Path) -> None:
    """``_ms_resolve_read_dir`` resolves the TASKS_INDEX surface through the
    injected ``FsReader`` port (#2154 kind-aware WRITE-leg authority) and the
    pre30 error leg routes ``tasks._output_error``."""
    st = _make_state()
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    ports = MagicMock()
    ports.fs.planning_read_dir.return_value = tmp_path
    with patch(
        "specify_cli.coordination.resolve_status_surface",
        return_value=tmp_path / "status.events.jsonl",
    ):
        tasks_mark_status._ms_resolve_read_dir(st, ports)
    assert ports.fs.planning_read_dir.call_args.kwargs["kind"] is MissionArtifactKind.TASKS_INDEX
    assert st.feature_dir == tmp_path
    assert st.tasks_md == tmp_path / "tasks.md"


def test_patched_render_intercepts_report_none_resolved_json_leg() -> None:
    """``tasks.RealRender`` + ``tasks._mark_status_json_payload`` bite through
    ``_ms_report_none_resolved``'s ``--json`` leg (the family-owned no-IDs
    error byte case, research.md D3)."""
    st = _make_state(json_output=True)
    st.results = [_not_found("T404")]
    st.not_found_tasks = ["T404"]
    with (
        patch(f"{_TASKS}.RealRender") as render_cls,
        patch(
            f"{_TASKS}._mark_status_json_payload",
            return_value={"result": "error"},
        ) as payload_mock,
        pytest.raises(typer.Exit) as exc_info,
    ):
        tasks_mark_status._ms_report_none_resolved(st)
    assert exc_info.value.exit_code == 1
    render_cls.assert_called_once_with()
    payload_mock.assert_called_once_with(st.results)
    render_cls.return_value.json_envelope.assert_called_once_with({"result": "error"})


def test_patched_output_error_intercepts_report_none_resolved_wp_id_leg() -> None:
    """``tasks._output_error`` bites through ``_ms_report_none_resolved``'s
    WP_ID-detail leg (human output)."""
    st = _make_state(json_output=False)
    st.results = [_not_found("WP01", fmt=TaskIdResolutionFormat.WP_ID)]
    st.not_found_tasks = ["WP01"]
    with (
        patch(f"{_TASKS}._output_error") as error_mock,
        pytest.raises(typer.Exit) as exc_info,
    ):
        tasks_mark_status._ms_report_none_resolved(st)
    assert exc_info.value.exit_code == 1
    error_mock.assert_called_once_with(
        False, "WP01 was not found in any supported task format."
    )


def test_patched_output_error_intercepts_report_none_resolved_default_leg() -> None:
    """``tasks._output_error`` bites through ``_ms_report_none_resolved``'s
    contracted 'No task IDs found' leg."""
    st = _make_state(json_output=False)
    st.results = [_not_found("T404")]
    st.not_found_tasks = ["T404"]
    with (
        patch(f"{_TASKS}._output_error") as error_mock,
        pytest.raises(typer.Exit),
    ):
        tasks_mark_status._ms_report_none_resolved(st)
    error_mock.assert_called_once_with(False, "No task IDs found in tasks.md: T404")


def test_patched_protection_policy_intercepts_ms_commit(tmp_path: Path) -> None:
    """``tasks.ProtectionPolicy`` bites through ``_ms_commit``'s
    ``_tasks.<attr>`` route, the resolved policy reaches the ports
    ``commit_artifact`` capability, and the committed leg prints via
    ``tasks.console``."""
    tasks_md = tmp_path / "tasks.md"
    tasks_md.write_text("- [x] T001 build the thing\n", encoding="utf-8")
    st = _make_state(json_output=False)
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.target_branch = "main"
    st.tasks_md = tasks_md
    st.updated_tasks = ["T001"]
    ports = MagicMock()
    ports.coord.commit_artifact.return_value = SimpleNamespace(status="committed")
    with (
        patch(f"{_TASKS}.ProtectionPolicy") as policy_cls,
        patch(f"{_TASKS}.console") as console_mock,
    ):
        tasks_mark_status._ms_commit(st, ports)
    policy_cls.resolve.assert_called_once_with(tmp_path)
    call = ports.coord.commit_artifact.call_args
    assert call.kwargs["policy"] is policy_cls.resolve.return_value
    assert call.kwargs["kind"] is MissionArtifactKind.TASKS_INDEX
    assert call.args[2] == "chore: Mark T001 as done on spec 034"
    console_mock.print.assert_called_once_with(
        "[cyan]→ Committed subtask changes to main branch[/cyan]"
    )


def test_patched_console_intercepts_ms_commit_exception_leg(tmp_path: Path) -> None:
    """``tasks.console`` bites through ``_ms_commit``'s defensive auto-commit
    exception leg (human output path)."""
    tasks_md = tmp_path / "tasks.md"
    tasks_md.write_text("- [x] T001 build the thing\n", encoding="utf-8")
    st = _make_state(json_output=False)
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.tasks_md = tasks_md
    st.updated_tasks = ["T001", "T002"]
    ports = MagicMock()
    ports.coord.commit_artifact.side_effect = RuntimeError("boom")
    with (
        patch(f"{_TASKS}.ProtectionPolicy"),
        patch(f"{_TASKS}.console") as console_mock,
    ):
        tasks_mark_status._ms_commit(st, ports)
    assert console_mock.print.call_count == 1
    assert "Auto-commit exception: boom" in console_mock.print.call_args.args[0]


def test_patched_feature_status_lock_intercepts_apply_updates(tmp_path: Path) -> None:
    """``tasks.feature_status_lock`` (the heavy D7 seam) bites through
    ``_ms_apply_updates`` — the lock spans the read → resolve → write span
    exactly as the pre-move body did, and the tasks.md-missing error leg
    routes ``tasks._output_error`` INSIDE the held lock."""
    st = _make_state()
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.feature_dir = tmp_path / "kitty-specs" / "034-feature-01ABCDEF"
    st.tasks_md = tmp_path / "tasks.md"  # deliberately absent
    lock_mock = MagicMock(return_value=nullcontext())
    with (
        patch(f"{_TASKS}.feature_status_lock", lock_mock),
        patch(f"{_TASKS}._output_error", side_effect=_SentinelHit) as error_mock,
        pytest.raises(_SentinelHit),
    ):
        tasks_mark_status._ms_apply_updates(st, ports=MagicMock())
    # The lock is keyed on the Mission directory name, never the slug (#5819 A8).
    lock_mock.assert_called_once_with(tmp_path, "034-feature-01ABCDEF")
    error_mock.assert_called_once_with(True, f"tasks.md not found: {st.tasks_md}")


def test_patched_resolve_inline_subtasks_intercepts_apply_updates(tmp_path: Path) -> None:
    """``tasks._resolve_inline_subtasks`` (which stays ``tasks.py``-resident
    per the T007 partition record) bites through ``_ms_apply_updates``'
    resolver chain via the ``_tasks.<attr>`` route."""
    tasks_md = tmp_path / "tasks.md"
    tasks_md.write_text(
        "## WP01: Build\n\nSubtasks: T001, T002\n", encoding="utf-8"
    )
    st = _make_state(task_ids=["T001"])
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.feature_dir = tmp_path
    st.tasks_md = tasks_md
    lock_mock = MagicMock(return_value=nullcontext())
    with (
        patch(f"{_TASKS}.feature_status_lock", lock_mock),
        patch(
            f"{_TASKS}._resolve_inline_subtasks", side_effect=_SentinelHit
        ) as inline_mock,
        pytest.raises(_SentinelHit),
    ):
        tasks_mark_status._ms_apply_updates(st, ports=MagicMock())
    inline_mock.assert_called_once()
    assert inline_mock.call_args.args[0] == "T001"


def test_patched_output_result_intercepts_ms_output() -> None:
    """``tasks._mark_status_json_payload`` / ``tasks._output_result`` /
    ``tasks.console`` bite through ``_ms_output``'s success envelope + the
    not-found warning leg."""
    st = _make_state(json_output=False)
    st.results = [_not_found("T404")]
    st.updated_tasks = ["T001"]
    st.not_found_tasks = ["T404"]
    st.resolved_tasks = ["T001"]
    with (
        patch(
            f"{_TASKS}._mark_status_json_payload",
            return_value={"result": "ok"},
        ) as payload_mock,
        patch(f"{_TASKS}.console") as console_mock,
        patch(f"{_TASKS}._output_result") as result_mock,
    ):
        tasks_mark_status._ms_output(st)
    payload_mock.assert_called_once_with(st.results)
    assert "Not found: T404" in console_mock.print.call_args.args[0]
    result_mock.assert_called_once_with(
        False, {"result": "ok"}, "[green]✓[/green] Marked T001 as done"
    )


def test_patched_output_error_intercepts_do_mark_status_exception_arm() -> None:
    """``tasks._output_error`` bites through
    ``_do_mark_status``'s generic exception arm (exit-1 translation). The
    failure is injected through the routed ``tasks.locate_project_root`` D7
    seam — the orchestrator reaches its ``_ms_*`` phase siblings by bare
    same-module name, so the phases themselves are deliberately NOT patch
    targets."""
    with (
        patch(f"{_TASKS}.locate_project_root", side_effect=RuntimeError("boom")),
        patch(f"{_TASKS}._output_error") as error_mock,
        pytest.raises(typer.Exit) as exc_info,
    ):
        tasks_mark_status._do_mark_status(
            task_ids=["T001"],
            status="done",
            mission="034-feature",
            auto_commit=None,
            json_output=True,
        )
    assert exc_info.value.exit_code == 1
    error_mock.assert_called_once_with(True, "boom")


def test_default_ports_constructs_through_tasks_bindings() -> None:
    """The moved ``_default_mark_status_ports`` constructs its adapters via
    the ``tasks`` bindings, so ``@patch("...tasks.<Adapter>")`` intercepts
    construction (the WP03 checklist invariant, preserved across the move) —
    the coord router built by ``seam_coord_router()`` routes ``commit_for_mission``
    through ``_tasks.<attr>`` and commits target-branch-less."""
    with (
        patch(f"{_TASKS}.seam_coord_router") as router_factory,
        patch(f"{_TASKS}.RealFsReader") as fs_cls,
        patch(f"{_TASKS}.RealGitOps") as git_cls,
        patch(f"{_TASKS}.RealRender") as render_cls,
    ):
        ports = tasks._default_mark_status_ports()
    # mark_status: commit-seam-only routing, no target_branch, base emitter binding.
    router_factory.assert_called_once_with()
    assert ports.coord is router_factory.return_value
    assert ports.fs is fs_cls.return_value
    assert ports.git is git_cls.return_value
    assert ports.render is render_cls.return_value


# NOTE (WP06 / #2565): the identity battery
# (``test_tasks_binding_is_tasks_mark_status_object``, 13 symbols) and the
# exact-set completeness pin
# (``test_move_set_matches_tasks_mark_status_defs``) formerly lived here.
# Both are RETIRED — mechanically subsumed by WP05's consolidated guard,
# ``test_tasks_compat_surface.py``
# (``test_tasks_binding_is_seam_object`` for identity;
# ``test_guard_symbol_is_genuinely_native_to_its_seam`` +
# ``test_guard_keyset_is_superset_of_all_six_seams_native_defs`` for the
# exact-set claim), which covers the same 13-symbol ``tasks_mark_status``
# surface. See the module docstring above for the reconcile ruling on the
# interception battery kept in this file.
