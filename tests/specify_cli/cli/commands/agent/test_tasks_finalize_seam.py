"""Layer-4 seam interception tests for the WP08 finalize-family relocation.

Mission ``tasks-py-degod-wave2-01KWH9EQ`` — parity-contract Layer 4 (NFR-002):
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/contracts/parity-contract.md``.

**Interception battery only** (dev-assist-retire-path-hardening-01KXAVR0
WP05a / #2565): each test patches ``...agent.tasks.<symbol>`` with a sentinel
and drives a relocated ``_ft_*`` phase helper (or ``_default_finalize_ports``
construction) THROUGH the moved body, asserting the sentinel is hit —
proving the lazy ``_tasks.<attr>`` seam bridge preserves patch interception,
not merely import resolution. The heavy ``bootstrap_canonical_state`` (×7)
and ``resolve_feature_dir_for_mission`` (pre30-guard-wiring) seams are pinned
explicitly. ``finalize_tasks`` has ZERO direct emission sites (research.md
D3), so there is no byte-case leg here — output routes through
``_output_result`` only.

The identity re-export battery (``test_tasks_binding_is_tasks_finalize_object``)
and its exact-set completeness pin (``test_move_set_matches_tasks_finalize_defs``)
were retired here — folded into the consolidated
``tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py`` guard,
which covers this seam's full symbol surface alongside the other 5
``tasks_*`` seams in one place.

Seam checklist (per-symbol evidence):
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/seam-checklist.md``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
import typer

from mission_runtime import MissionArtifactKind
from specify_cli.cli.commands.agent import tasks, tasks_finalize
from specify_cli.cli.commands.agent.tasks_finalize import _FinalizeState

pytestmark = pytest.mark.fast

_TASKS = "specify_cli.cli.commands.agent.tasks"


class _SentinelHit(Exception):
    """Raised by sentinel patches to prove the patched attribute was called."""


def _make_state(**overrides: Any) -> _FinalizeState:
    """A minimal ``_FinalizeState`` (raw command inputs only) with overrides."""
    kwargs: dict[str, Any] = {
        "mission": "034-feature",
        "json_output": True,
        "validate_only": False,
    }
    field_overrides = {k: v for k, v in overrides.items() if k in kwargs}
    kwargs.update(field_overrides)
    st = _FinalizeState(**kwargs)
    for key, value in overrides.items():
        if key not in field_overrides:
            setattr(st, key, value)
    return st


# ---------------------------------------------------------------------------
# Interception battery — patch tasks.<symbol>, drive the relocated body,
# assert the sentinel bites. All patches target the ``tasks`` namespace; the
# bodies live in ``tasks_finalize`` (research.md D1 seam bridge).
# ---------------------------------------------------------------------------


def test_resolve_context_routes_resolution_seams_through_tasks(tmp_path: Path) -> None:
    """``tasks.locate_project_root`` / ``_emit_sparse_session_warning`` /
    ``_find_mission_slug`` / ``_ensure_target_branch_checked_out`` bite through
    ``_ft_resolve_context``, the FsReader port carries the WORK_PACKAGE_TASK
    kind (FR-010 guard-only read migration), and the tasks.md-missing error
    leg routes ``tasks._output_error``."""
    st = _make_state()
    ports = MagicMock()
    ports.fs.planning_read_dir.return_value = tmp_path  # no tasks.md inside
    with (
        patch(f"{_TASKS}.locate_project_root", return_value=tmp_path) as locate_mock,
        patch(f"{_TASKS}._emit_sparse_session_warning") as sparse_mock,
        patch(f"{_TASKS}._find_mission_slug", return_value="034-feature") as slug_mock,
        patch(
            f"{_TASKS}._ensure_target_branch_checked_out",
            return_value=(tmp_path, "main"),
        ) as branch_mock,
        patch(f"{_TASKS}._output_error") as error_mock,
        pytest.raises(typer.Exit) as exc_info,
    ):
        tasks_finalize._ft_resolve_context(st, ports)
    assert exc_info.value.exit_code == 1
    locate_mock.assert_called_once()
    sparse_mock.assert_called_once_with(tmp_path, command="spec-kitty agent tasks finalize-tasks")
    slug_mock.assert_called_once()
    branch_mock.assert_called_once_with(tmp_path, "034-feature", True)
    assert ports.fs.planning_read_dir.call_args.kwargs["kind"] is MissionArtifactKind.WORK_PACKAGE_TASK
    error_mock.assert_called_once_with(True, f"tasks.md not found: {tmp_path / 'tasks.md'}")


def test_patched_output_error_intercepts_resolve_context_no_root() -> None:
    """``tasks._output_error`` bites through ``_ft_resolve_context``'s
    no-project-root refusal."""
    st = _make_state()
    with (
        patch(f"{_TASKS}.locate_project_root", return_value=None),
        patch(f"{_TASKS}._output_error", side_effect=_SentinelHit) as error_mock,
        pytest.raises(_SentinelHit),
    ):
        tasks_finalize._ft_resolve_context(st, ports=MagicMock())
    error_mock.assert_called_once_with(True, "Could not locate project root")


def test_patched_output_error_intercepts_validate_coverage_gate(tmp_path: Path) -> None:
    """``tasks._output_error`` bites through ``_ft_validate``'s WP-coverage
    pre-write refusal (a WP file on disk with no parsed tasks.md section)."""
    tasks_md = tmp_path / "tasks.md"
    tasks_md.write_text("# Tasks\n\nno work package sections here\n", encoding="utf-8")
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01-build-the-thing.md").write_text("---\nwork_package_id: WP01\n---\nbody\n", encoding="utf-8")
    st = _make_state()
    st.tasks_md = tasks_md
    st.tasks_dir = tasks_dir
    with (
        patch(f"{_TASKS}._output_error", side_effect=_SentinelHit) as error_mock,
        pytest.raises(_SentinelHit),
    ):
        tasks_finalize._ft_validate(st)
    error_mock.assert_called_once()
    assert "coverage is incomplete" in error_mock.call_args.args[1]


def test_patched_bootstrap_seams_intercept_apply_writes(tmp_path: Path) -> None:
    """``tasks_finalize.placement_seam`` (the read-surface-ssot-closeout WP08
    routed seam, replacing the retired ``tasks.resolve_feature_dir_for_mission``
    pre30-guard-wiring patch) and ``tasks.bootstrap_canonical_state`` (×7 patch
    seam) bite through ``_ft_apply_writes`` — the bootstrap read stays on the
    topology-aware STATUS-partition resolver (``STATUS_STATE`` kind).

    ``placement_seam`` is a MODULE-SCOPE import in ``tasks_finalize`` (not a
    lazy in-function import like the ``_tasks.<attr>`` seam-bridge symbols
    above), so the patch target is ``tasks_finalize.placement_seam`` — not
    ``mission_runtime.placement_seam`` — matching the module-scope import
    convention already used for ``MissionArtifactKind`` in this module.
    """
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    st = _make_state(validate_only=True)
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.tasks_dir = tasks_dir
    st.dependencies_map = {}
    # #4890: the plan is now computed (and its effective graph validated) in
    # ``_ft_validate`` — ``_ft_apply_writes`` only consumes ``st.update_plan``.
    st.update_plan = tasks_finalize.compute_wp_frontmatter_updates(st.dependencies_map, tasks_dir)
    feature_dir = tmp_path / "kitty-specs" / "034-feature"
    bootstrap_result = SimpleNamespace(total_wps=0, already_initialized=0, newly_seeded=0, skipped=0, wp_details=[])
    mock_seam = MagicMock()
    mock_seam.read_dir.return_value = feature_dir
    with (
        patch(
            "specify_cli.cli.commands.agent.tasks_finalize.placement_seam",
            return_value=mock_seam,
        ) as seam_mock,
        patch(f"{_TASKS}.bootstrap_canonical_state", return_value=bootstrap_result) as bootstrap_mock,
        patch(f"{_TASKS}.console") as console_mock,
    ):
        tasks_finalize._ft_apply_writes(st)
    seam_mock.assert_called_once_with(tmp_path, "034-feature")
    mock_seam.read_dir.assert_called_once_with(MissionArtifactKind.STATUS_STATE)
    bootstrap_mock.assert_called_once_with(feature_dir, "034-feature", dry_run=True)
    assert st.feature_dir == feature_dir
    assert st.bootstrap_result is bootstrap_result
    console_mock.print.assert_not_called()


def test_patched_console_intercepts_apply_writes_warning_leg(tmp_path: Path) -> None:
    """``tasks.console`` bites through ``_ft_apply_writes``' update-plan
    warning leg."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    # A WP file whose frontmatter disagrees shape-wise triggers a plan warning;
    # simplest deterministic route: a WP file with unparseable frontmatter.
    (tasks_dir / "WP01-build-the-thing.md").write_text("no frontmatter\n", encoding="utf-8")
    st = _make_state(validate_only=True)
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.tasks_dir = tasks_dir
    st.dependencies_map = {"WP01": []}
    # #4890: the plan (and its unreadable-frontmatter warning) is now computed
    # in ``_ft_validate`` — ``_ft_apply_writes`` only consumes ``st.update_plan``.
    st.update_plan = tasks_finalize.compute_wp_frontmatter_updates(st.dependencies_map, tasks_dir)
    mock_seam = MagicMock()
    mock_seam.read_dir.return_value = tmp_path
    with (
        patch(
            "specify_cli.cli.commands.agent.tasks_finalize.placement_seam",
            return_value=mock_seam,
        ),
        patch(
            f"{_TASKS}.bootstrap_canonical_state",
            return_value=SimpleNamespace(total_wps=0, already_initialized=0, newly_seeded=0, skipped=0, wp_details=[]),
        ),
        patch(f"{_TASKS}.console") as console_mock,
    ):
        tasks_finalize._ft_apply_writes(st)
    assert console_mock.print.call_count >= 1
    assert "Warning:" in console_mock.print.call_args_list[0].args[0]


def test_patched_output_result_intercepts_ft_output_success_leg(tmp_path: Path) -> None:
    """``tasks._mission_identity_payload`` / ``tasks._output_result`` bite
    through ``_ft_output``'s success envelope."""
    st = _make_state(validate_only=False)
    st.feature_dir = tmp_path
    st.dependencies_map = {"WP02": ["WP01"]}
    st.update_plan = cast(
        Any,
        SimpleNamespace(
            updated_count=1,
            modified_wps=["WP02"],
            unchanged_wps=["WP01"],
            preserved_wps=[],
            warnings=[],
            writes=[],
            effective_dependencies={"WP02": ["WP01"]},
        ),
    )
    st.bootstrap_result = cast(
        Any,
        SimpleNamespace(total_wps=2, already_initialized=1, newly_seeded=1, skipped=0, wp_details=[]),
    )
    with (
        patch(
            f"{_TASKS}._mission_identity_payload",
            return_value={"mission_id": "01SENTINEL"},
        ) as identity_mock,
        patch(f"{_TASKS}._output_result") as result_mock,
    ):
        tasks_finalize._ft_output(st)
    identity_mock.assert_called_once_with(tmp_path)
    payload = result_mock.call_args.args[1]
    assert payload["result"] == "success"
    assert payload["mission_id"] == "01SENTINEL"
    assert payload["updated_wp_count"] == 1
    assert payload["dependencies"] == {"WP02": ["WP01"]}
    assert payload["bootstrap"]["newly_seeded"] == 1
    assert "would_modify" not in payload


def test_patched_output_result_intercepts_ft_output_validate_only_leg(
    tmp_path: Path,
) -> None:
    """``_ft_output``'s validate-only envelope keeps its distinct shape
    (``validation_passed`` + ``would_modify``) through the routed seams."""
    st = _make_state(validate_only=True)
    st.feature_dir = tmp_path
    st.would_modify = [{"wp_id": "WP02", "changes": {"dependencies": ["WP01"]}}]
    st.update_plan = cast(
        Any,
        SimpleNamespace(
            updated_count=1,
            modified_wps=["WP02"],
            unchanged_wps=[],
            preserved_wps=[],
            warnings=[],
            writes=[],
            effective_dependencies={"WP02": ["WP01"]},
        ),
    )
    st.bootstrap_result = cast(
        Any,
        SimpleNamespace(total_wps=2, already_initialized=2, newly_seeded=0, skipped=0, wp_details=[]),
    )
    with (
        patch(f"{_TASKS}._mission_identity_payload", return_value={}),
        patch(f"{_TASKS}._output_result") as result_mock,
    ):
        tasks_finalize._ft_output(st)
    payload = result_mock.call_args.args[1]
    assert payload["result"] == "validation_passed"
    assert payload["validate_only"] is True
    assert payload["would_modify"] == st.would_modify


def test_patched_output_error_intercepts_do_finalize_tasks_exception_arm() -> None:
    """``tasks._output_error`` bites through ``_do_finalize_tasks``' generic
    exception arm (exit-1 translation). The
    failure is injected through the routed ``tasks.locate_project_root`` D7
    seam — the orchestrator reaches its ``_ft_*`` phase siblings by bare
    same-module name, so the phases themselves are deliberately NOT patch
    targets."""
    with (
        patch(f"{_TASKS}.locate_project_root", side_effect=RuntimeError("boom")),
        patch(f"{_TASKS}._output_error") as error_mock,
        pytest.raises(typer.Exit) as exc_info,
    ):
        tasks_finalize._do_finalize_tasks(
            mission="034-feature",
            json_output=True,
            validate_only=False,
        )
    assert exc_info.value.exit_code == 1
    error_mock.assert_called_once_with(True, "boom")


def test_default_ports_constructs_through_tasks_bindings() -> None:
    """The moved ``_default_finalize_ports`` constructs its adapters via the
    ``tasks`` bindings, so ``@patch("...tasks.<Adapter>")`` intercepts
    construction (the WP03 checklist invariant, preserved across the move) —
    incl. the plain ``RealCoordCommitRouter`` (finalize commits nothing
    itself; the router is the bundle's inert WRITE authority)."""
    with (
        patch(f"{_TASKS}.RealCoordCommitRouter") as router_cls,
        patch(f"{_TASKS}.RealFsReader") as fs_cls,
        patch(f"{_TASKS}.RealGitOps") as git_cls,
        patch(f"{_TASKS}.RealRender") as render_cls,
    ):
        ports = tasks._default_finalize_ports()
    router_cls.assert_called_once_with()
    assert ports.coord is router_cls.return_value
    assert ports.fs is fs_cls.return_value
    assert ports.git is git_cls.return_value
    assert ports.render is render_cls.return_value
