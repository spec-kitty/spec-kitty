"""Layer-4 seam interception tests for the WP06 map_requirements-family relocation.

Mission ``tasks-py-degod-wave2-01KWH9EQ`` — parity-contract Layer 4 (NFR-002):
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/contracts/parity-contract.md``.

**Interception battery only** (dev-assist-retire-path-hardening-01KXAVR0
WP05a / #2565): each test patches ``...agent.tasks.<symbol>`` with a sentinel
and drives a relocated ``_mr_*`` phase helper (or
``_default_map_requirements_ports`` construction) THROUGH the moved body,
asserting the sentinel is hit — proving the lazy ``_tasks.<attr>`` seam
bridge preserves patch interception, not merely import resolution. The
C-001 divergence wiring (REFUSE-exit-1 through
``_protected_branch_status_commit_error`` with NO
``_skip_target_branch_commit`` pre-gate) is pinned explicitly.

The identity re-export battery
(``test_tasks_binding_is_tasks_map_requirements_object``) and its exact-set
completeness pin (``test_move_set_matches_tasks_map_requirements_defs``)
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

from mission_runtime import CommitTarget
from specify_cli.cli.commands.agent import tasks, tasks_map_requirements
from specify_cli.cli.commands.agent.tasks_map_requirements import _MapReqState

pytestmark = pytest.mark.fast

_TASKS = "specify_cli.cli.commands.agent.tasks"


class _SentinelHit(Exception):
    """Raised by sentinel patches to prove the patched attribute was called."""


def _make_state(**overrides: Any) -> _MapReqState:
    """A minimal ``_MapReqState`` (raw command inputs only) with overrides."""
    kwargs: dict[str, Any] = {
        "wp": "WP01",
        "refs": "FR-001",
        "batch": None,
        "replace": False,
        "tracker_ref": None,
        "mission": "034-feature",
        "json_output": True,
        "auto_commit": None,
    }
    field_overrides = {k: v for k, v in overrides.items() if k in kwargs}
    kwargs.update(field_overrides)
    st = _MapReqState(**kwargs)
    for key, value in overrides.items():
        if key not in field_overrides:
            setattr(st, key, value)
    return st


# ---------------------------------------------------------------------------
# Interception battery — patch tasks.<symbol>, drive the relocated body,
# assert the sentinel bites. All patches target the ``tasks`` namespace; the
# bodies live in ``tasks_map_requirements`` (research.md D1 seam bridge).
# ---------------------------------------------------------------------------


def test_c001_refuse_arm_intercepts_through_tasks_namespace(tmp_path: Path) -> None:
    """C-001 REFUSE arm: with auto-commit resolved on, ``_mr_resolve_context``
    resolves the placement, consults ``_protected_branch_status_commit_error``
    via ``_tasks.<attr>`` and refuses exit-1 — and the ``move_task``-only
    ``_skip_target_branch_commit`` skip pre-gate is NEVER consulted (the
    divergence the coord-harness refuse-arm case T005 pins end-to-end)."""
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
            "specify_cli.coordination.commit_router._resolve_planning_placement",
            return_value=CommitTarget(ref="main"),
        ) as placement_mock,
        patch(
            f"{_TASKS}._protected_branch_status_commit_error",
            return_value="protected: refuse",
        ) as protected_mock,
        patch(f"{_TASKS}._skip_target_branch_commit") as skip_mock,
        patch(f"{_TASKS}._output_error") as error_mock,
        pytest.raises(typer.Exit) as exc_info,
    ):
        tasks_map_requirements._mr_resolve_context(st)
    assert exc_info.value.exit_code == 1
    locate_mock.assert_called_once()
    sparse_mock.assert_called_once_with(
        tmp_path, command="spec-kitty agent tasks map-requirements"
    )
    slug_mock.assert_called_once()
    branch_mock.assert_called_once_with(tmp_path, "034-feature", True)
    placement_mock.assert_called_once()
    protected_mock.assert_called_once_with(
        "main", tmp_path, "spec-kitty agent tasks map-requirements", "034-feature"
    )
    skip_mock.assert_not_called()
    error_mock.assert_called_once_with(True, "protected: refuse")


def test_c001_protected_gate_not_consulted_when_auto_commit_resolves_false(
    tmp_path: Path,
) -> None:
    """C-001 wiring: with auto-commit resolved False (via the patched
    ``tasks.get_auto_commit_default`` D7 seam) the placement resolution and the
    protected-branch refusal are NOT consulted; ``commit_target`` keeps the
    resolved target branch."""
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
        patch(
            f"{_TASKS}._protected_branch_status_commit_error"
        ) as protected_mock,
    ):
        tasks_map_requirements._mr_resolve_context(st)
    auto_mock.assert_called_once_with(tmp_path)
    protected_mock.assert_not_called()
    assert st.auto_commit_on is False
    assert st.commit_target.ref == "main"


def test_patched_output_error_intercepts_validate_modes() -> None:
    """``tasks._output_error`` bites through ``_mr_validate_modes``' operator
    mode gate (batch + wp is a refused combination)."""
    st = _make_state(batch='{"WP01": ["FR-001"]}')
    with (
        patch(f"{_TASKS}._output_error", side_effect=_SentinelHit) as error_mock,
        pytest.raises(_SentinelHit),
    ):
        tasks_map_requirements._mr_validate_modes(st)
    error_mock.assert_called_once()


def test_patched_output_error_intercepts_build_new_mappings_bad_json() -> None:
    """``tasks._output_error`` bites through ``_mr_build_new_mappings``'
    malformed ``--batch`` JSON leg."""
    st = _make_state(wp=None, refs=None, batch="{not json")
    with (
        patch(f"{_TASKS}._output_error", side_effect=_SentinelHit) as error_mock,
        pytest.raises(_SentinelHit),
    ):
        tasks_map_requirements._mr_build_new_mappings(st)
    error_mock.assert_called_once()


def test_patched_console_intercepts_unknown_wp_gate_human_leg(tmp_path: Path) -> None:
    """``tasks.console`` bites through ``_mr_unknown_wp_gate``'s human error
    leg (the moved body prints via ``_tasks.console``)."""
    (tmp_path / "WP01-x.md").write_text("body", encoding="utf-8")
    st = _make_state(json_output=False)
    st.tasks_dir = tmp_path
    st.new_mappings = {"WP99": ["FR-001"]}
    with (
        patch(f"{_TASKS}.console") as console_mock,
        pytest.raises(typer.Exit) as exc_info,
    ):
        tasks_map_requirements._mr_unknown_wp_gate(st)
    assert exc_info.value.exit_code == 1
    assert console_mock.print.call_count == 2
    assert "Unknown WP IDs" in console_mock.print.call_args_list[0].args[0]


def test_patched_render_intercepts_unknown_wp_gate_json_leg(tmp_path: Path) -> None:
    """``tasks.RealRender`` bites through ``_mr_unknown_wp_gate``'s ``--json``
    error leg (envelope construction via ``_tasks.RealRender()``)."""
    st = _make_state(json_output=True)
    st.tasks_dir = tmp_path
    st.new_mappings = {"WP99": ["FR-001"]}
    with (
        patch(f"{_TASKS}.RealRender") as render_cls,
        pytest.raises(typer.Exit),
    ):
        tasks_map_requirements._mr_unknown_wp_gate(st)
    render_cls.assert_called_once_with()
    payload = render_cls.return_value.json_envelope.call_args.args[0]
    assert payload["unknown_wps"] == ["WP99"]


def test_patched_map_requirements_feature_dir_intercepts_resolve_read_dirs(
    tmp_path: Path,
) -> None:
    """``tasks._map_requirements_feature_dir`` (the pre30-guard-wiring patch
    seam, tests/upgrade/test_pre30_guard_wiring.py) bites through
    ``_mr_resolve_read_dirs``'s ``_tasks.<attr>`` route."""
    st = _make_state()
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    with (
        patch(
            f"{_TASKS}._map_requirements_feature_dir", side_effect=_SentinelHit
        ) as dir_mock,
        pytest.raises(_SentinelHit),
    ):
        tasks_map_requirements._mr_resolve_read_dirs(st, ports=MagicMock())
    dir_mock.assert_called_once_with(tmp_path, "034-feature")


def test_patched_plan_mapping_intercepts_mr_plan(tmp_path: Path) -> None:
    """``tasks.plan_mapping`` (sentinel-monkeypatch seam,
    test_tasks_mapping_core.py) bites through ``_mr_plan``'s ``_tasks.<attr>``
    route."""
    st = _make_state()
    st.tasks_dir = tmp_path
    st.feature_dir = tmp_path
    st.all_spec_ids = {"FR-001"}
    st.functional_ids = {"FR-001"}
    st.new_mappings = {"WP01": ["FR-001"]}
    with (
        patch(f"{_TASKS}.plan_mapping", side_effect=_SentinelHit) as plan_mock,
        pytest.raises(_SentinelHit),
    ):
        tasks_map_requirements._mr_plan(st)
    request = plan_mock.call_args.args[0]
    assert request.mode == "wp_refs"
    assert request.new_mappings == {"WP01": ["FR-001"]}


def test_patched_render_intercepts_stale_gate_json_leg(tmp_path: Path) -> None:
    """``tasks.RealRender`` bites through ``_mr_stale_gate``'s post-write
    refusal ``--json`` leg (stale refs found on disk)."""
    (tmp_path / "WP01-x.md").write_text(
        "---\nwork_package_id: WP01\nrequirement_refs:\n- FR-999\n---\nbody",
        encoding="utf-8",
    )
    st = _make_state(json_output=True)
    st.tasks_dir = tmp_path
    st.all_spec_ids = {"FR-001"}
    with (
        patch(f"{_TASKS}.RealRender") as render_cls,
        pytest.raises(typer.Exit) as exc_info,
    ):
        tasks_map_requirements._mr_stale_gate(st)
    assert exc_info.value.exit_code == 1
    payload = render_cls.return_value.json_envelope.call_args.args[0]
    assert payload["stale_refs"] == {"WP01": ["FR-999"]}


def test_patched_protection_policy_intercepts_auto_commit(tmp_path: Path) -> None:
    """``tasks.ProtectionPolicy`` bites through ``_mr_auto_commit``'s
    ``_tasks.<attr>`` route and the resolved policy reaches the ports
    ``commit_artifact`` capability."""
    wp_file = tmp_path / "WP01-x.md"
    wp_file.write_text("body", encoding="utf-8")
    st = _make_state()
    st.auto_commit_on = True
    st.tasks_dir = tmp_path
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.new_mappings = {"WP01": ["FR-001"]}
    ports = MagicMock()
    ports.coord.commit_artifact.return_value = SimpleNamespace(
        status="committed", commit_hash="abc123", placement_ref="main"
    )
    with patch(f"{_TASKS}.ProtectionPolicy") as policy_cls:
        tasks_map_requirements._mr_auto_commit(st, ports)
    policy_cls.resolve.assert_called_once_with(tmp_path)
    assert (
        ports.coord.commit_artifact.call_args.kwargs["policy"]
        is policy_cls.resolve.return_value
    )
    assert st.committed is True
    assert st.commit_sha == "abc123"
    assert st.commit_result_payload == {
        "sha": "abc123",
        "destination_ref": "main",
        "worktree_root": str(tmp_path),
    }


def test_patched_console_intercepts_auto_commit_warning(tmp_path: Path) -> None:
    """``tasks.console`` bites through ``_mr_auto_commit``'s defensive
    warning leg (commit failure on the human output path)."""
    wp_file = tmp_path / "WP01-x.md"
    wp_file.write_text("body", encoding="utf-8")
    st = _make_state(json_output=False)
    st.auto_commit_on = True
    st.tasks_dir = tmp_path
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.new_mappings = {"WP01": ["FR-001"]}
    ports = MagicMock()
    ports.coord.commit_artifact.side_effect = RuntimeError("boom")
    with (
        patch(f"{_TASKS}.ProtectionPolicy"),
        patch(f"{_TASKS}.console") as console_mock,
    ):
        tasks_map_requirements._mr_auto_commit(st, ports)
    assert console_mock.print.call_count == 1
    assert "Auto-commit skipped" in console_mock.print.call_args.args[0]


def test_patched_identity_payload_intercepts_emit_output(tmp_path: Path) -> None:
    """``tasks._mission_identity_payload`` / ``tasks.RealRender`` bite through
    ``_mr_emit_output``'s success-envelope reconstruction (``--json`` leg)."""
    st = _make_state(json_output=True)
    st.tasks_dir = tmp_path
    st.primary_dir = tmp_path
    st.functional_ids = {"FR-001"}
    st.new_mappings = {"WP01": ["FR-001"]}
    st.mapping_plan = cast(Any, SimpleNamespace(unmapped_fr=[], bare_prose_requirement_ids=[]))
    with (
        patch(
            f"{_TASKS}._mission_identity_payload",
            return_value={"mission_id": "01SENTINEL"},
        ) as identity_mock,
        patch(f"{_TASKS}.RealRender") as render_cls,
    ):
        tasks_map_requirements._mr_emit_output(st)
    identity_mock.assert_called_once_with(tmp_path)
    payload = render_cls.return_value.json_envelope.call_args.args[0]
    assert payload["mission_id"] == "01SENTINEL"
    assert payload["result"] == "success"
    assert payload["coverage"]["mapped_functional"] == 1


def test_patched_output_error_intercepts_do_map_requirements_exception_arm() -> None:
    """``tasks._output_error`` bites through ``_do_map_requirements``' generic
    exception arm (exit-1 translation). The failure is injected through the
    routed ``tasks.locate_project_root`` D7 seam — the orchestrator reaches its
    ``_mr_*`` phase siblings by bare same-module name (the ratchet-closure
    invariant), so the phases themselves are deliberately NOT patch targets."""
    with (
        patch(
            f"{_TASKS}.locate_project_root", side_effect=RuntimeError("boom")
        ),
        patch(f"{_TASKS}._output_error") as error_mock,
        pytest.raises(typer.Exit) as exc_info,
    ):
        tasks_map_requirements._do_map_requirements(
            wp="WP01",
            refs="FR-001",
            batch=None,
            replace=False,
            tracker_ref=None,
            mission="034-feature",
            json_output=True,
            auto_commit=None,
        )
    assert exc_info.value.exit_code == 1
    error_mock.assert_called_once_with(True, "boom")


# ---------------------------------------------------------------------------
# WP06 (#3396) T032a: _mr_plan threads spec_content -> the fail-loud
# bare-prose detector -> MappingRequest.
# ---------------------------------------------------------------------------


def test_mr_plan_threads_spec_content_into_bare_prose_request_field(
    tmp_path: Path,
) -> None:
    """``_mr_plan`` computes ``bare_prose_requirement_ids`` from
    ``st.spec_content`` (populated by ``_mr_resolve_read_dirs``, Phase C) and
    passes it into ``MappingRequest`` -- proving the plumbing fix threads the
    raw text all the way from the Phase C read to the Phase D request, not
    merely a dead field."""
    st = _make_state()
    st.tasks_dir = tmp_path
    st.feature_dir = tmp_path
    st.all_spec_ids = {"NFR-001"}
    st.functional_ids = set()
    st.new_mappings = {"WP01": ["NFR-001"]}
    st.spec_content = (
        "### Functional Requirements\n\n"
        "FR-001 the loader must reject an unknown pack.\n"
        "FR-002 the error must name the offending path.\n\n"
        "| ID | Requirement |\n"
        "|----|-------------|\n"
        "| NFR-001 | Resolution completes within 200ms |\n"
    )
    with patch(f"{_TASKS}.plan_mapping") as plan_mock:
        tasks_map_requirements._mr_plan(st)
    request = plan_mock.call_args.args[0]
    assert request.bare_prose_requirement_ids == frozenset({"FR-001", "FR-002"})


def test_mr_detect_bare_prose_requirement_ids_finds_repro_ids() -> None:
    """The wrapper's happy path returns the exact FR-001/FR-002 repro ids."""
    spec_content = (
        "### Functional Requirements\n\n"
        "FR-001 the loader must reject an unknown pack.\n"
        "FR-002 the error must name the offending path.\n\n"
        "| ID | Requirement |\n"
        "|----|-------------|\n"
        "| NFR-001 | Resolution completes within 200ms |\n"
    )
    result = tasks_map_requirements._mr_detect_bare_prose_requirement_ids(spec_content)
    assert result == frozenset({"FR-001", "FR-002"})


def test_mr_detect_bare_prose_requirement_ids_is_fail_loud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WP06 (#3396) IC-04 fault injection: a detector exception is caught
    ONCE and converted into an explicit, non-empty result -- never a
    swallowed "0 uncounted" (NFR-002) -- mirroring WP05/T023's
    ``classification_error`` contract."""
    import specify_cli.requirement_mapping as req_mapping_module

    def _boom(_spec_content: str) -> list[object]:
        raise RuntimeError("boom")

    monkeypatch.setattr(req_mapping_module, "find_bare_prose_requirement_ids", _boom)
    result = tasks_map_requirements._mr_detect_bare_prose_requirement_ids("irrelevant")
    assert result, "expected a non-empty failure entry"
    assert "boom" in next(iter(result))


def test_default_ports_constructs_through_tasks_bindings() -> None:
    """The moved ``_default_map_requirements_ports`` constructs its adapters
    via the ``tasks`` bindings, so ``@patch("...tasks.<Adapter>")`` intercepts
    construction (the WP03 checklist invariant, preserved across the move) —
    and the coord router carries the resolved ``target_branch``."""
    with (
        patch(f"{_TASKS}.seam_coord_router") as router_factory,
        patch(f"{_TASKS}.RealFsReader") as fs_cls,
        patch(f"{_TASKS}.RealGitOps") as git_cls,
        patch(f"{_TASKS}.RealRender") as render_cls,
    ):
        ports = tasks._default_map_requirements_ports("main")
    # map_requirements threads the resolved target_branch (ff-advance parity).
    router_factory.assert_called_once_with(thread_target_branch=True, target_branch="main")
    assert ports.coord is router_factory.return_value
    assert ports.fs is fs_cls.return_value
    assert ports.git is git_cls.return_value
    assert ports.render is render_cls.return_value
