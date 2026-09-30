"""Layer-4 seam interception tests for the WP07 status-family relocation.

Mission ``tasks-py-degod-wave2-01KWH9EQ`` — parity-contract Layer 4 (NFR-002):
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/contracts/parity-contract.md``.

This file now carries ONE battery (the WP06 / dev-assist-retire-path-hardening
ruling, mission ``dev-assist-retire-path-hardening-01KXAVR0``, #2565):

1. **Interception** — each test patches ``...agent.tasks.<symbol>`` with a
   sentinel and drives a relocated ``_st_*`` phase helper (or
   ``_default_status_ports`` construction) THROUGH the moved body, asserting
   the sentinel is hit — proving the lazy ``_tasks.<attr>`` seam bridge
   preserves patch interception, not merely import resolution. The
   ``build_status_view`` sentinel seam (test_tasks_status_view.py's
   ``monkeypatch.setattr(tasks_module, "build_status_view", …)``) and the
   ``_default_status_ports`` indent=2 render construction (the WP01 status
   byte case's production seam) are pinned explicitly. This coverage is
   UNIQUE — no observable-contract test proves a call-site is still routed
   through the patchable ``tasks.<attr>`` seam (a same-object identity check
   cannot observe that either), so KEEP is the default per the WP05 review
   ruling; see the module docstring conclusion at the bottom of this file's
   change history for the WP06 per-proof reconcile.

The **identity** battery (``test_tasks_binding_is_tasks_status_cmd_object``,
parametrized over the 21-symbol move-set) and the exact-set completeness pin
(``test_move_set_matches_tasks_status_cmd_defs``) were RETIRED at WP06: both
are mechanically subsumed by WP05's consolidated re-export guard —
``tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py``
(``test_tasks_binding_is_seam_object`` for identity,
``test_guard_symbol_is_genuinely_native_to_its_seam`` +
``test_guard_keyset_is_superset_of_all_six_seams_native_defs`` for the
exact-set/completeness claim over the same 21 ``tasks_status_cmd`` symbols).

Seam checklist (per-symbol evidence):
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/seam-checklist.md``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer

from mission_runtime import MissionTopology, OwnedCheckout
from specify_cli.cli.commands.agent import tasks, tasks_status_cmd
from specify_cli.cli.commands.agent.tasks_status_cmd import _StatusState
from specify_cli.cli.commands.agent.tasks_status_view import StatusView
from specify_cli.status import NON_DISPLAY_LANES, Lane

pytestmark = pytest.mark.fast

_TASKS = "specify_cli.cli.commands.agent.tasks"


class _SentinelHit(Exception):
    """Raised by sentinel patches to prove the patched attribute was called."""


def _make_state(**overrides: Any) -> _StatusState:
    """A minimal ``_StatusState`` (raw command inputs only) with overrides."""
    kwargs: dict[str, Any] = {
        "mission": "034-feature",
        "json_output": True,
        "stale_threshold": 10,
    }
    field_overrides = {k: v for k, v in overrides.items() if k in kwargs}
    kwargs.update(field_overrides)
    st = _StatusState(**kwargs)
    for key, value in overrides.items():
        if key not in field_overrides:
            setattr(st, key, value)
    return st


def _mint_owned(tmp_path: Path, *, slug: str = "034-feature") -> OwnedCheckout:
    """Mint a real ``OwnedCheckout`` fact over ``tmp_path`` (owned-checkout-lifecycle-authority WP09).

    Mirrors ``tests/status/test_transition_request_owned.py::_mint``:
    ``OwnedCheckout._mint`` is the one test-visible construction door (bare
    construction raises ``TypeError``), and its invariants only check path
    relationships, so no real git repo is needed for these pure unit tests.
    """
    repo = tmp_path / "repo"
    owned_root = tmp_path / "owned"
    mission_dir = owned_root / "kitty-specs" / slug
    repo.mkdir(parents=True, exist_ok=True)
    mission_dir.mkdir(parents=True, exist_ok=True)
    return OwnedCheckout._mint(
        repository_root=repo,
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=slug,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch="codex/owned",
    )


def _empty_lanes() -> dict[Lane | str, list[dict[str, object]]]:
    return {lane: [] for lane in Lane if lane not in NON_DISPLAY_LANES}


def _view(**overrides: Any) -> StatusView:
    """A ``StatusView`` with empty lanes and overridable aggregates."""
    kwargs: dict[str, Any] = {
        "lanes": _empty_lanes(),
        "lane_counts": {},
        "total_wps": 0,
        "done_count": 0,
        "in_progress_count": 0,
        "planned_count": 0,
        "stale_count": 0,
        "done_percentage": 0.0,
        "progress_percentage": 0.0,
        "dependency_readiness": {},
    }
    kwargs.update(overrides)
    return StatusView(**kwargs)


# ---------------------------------------------------------------------------
# Interception battery — patch tasks.<symbol>, drive the relocated body,
# assert the sentinel bites. All patches target the ``tasks`` namespace; the
# bodies live in ``tasks_status_cmd`` (research.md D1 seam bridge).
# ---------------------------------------------------------------------------


def test_patched_resolution_seams_intercept_resolve_dirs(tmp_path: Path) -> None:
    """The routed D7 resolution seams (``locate_project_root`` ×67,
    ``_find_mission_slug`` ×66, ``_ensure_target_branch_checked_out`` ×50,
    ``get_status_read_root`` ×3) and ``tasks.console`` all bite through
    ``_st_resolve_dirs``' mission-dir-not-found error leg."""
    st = _make_state()
    missing_root = tmp_path / "elsewhere"
    with (
        patch(f"{_TASKS}.locate_project_root", return_value=tmp_path) as locate_mock,
        patch(f"{_TASKS}._find_mission_slug", return_value="034-feature") as slug_mock,
        patch(
            f"{_TASKS}._ensure_target_branch_checked_out",
            return_value=(tmp_path, "main"),
        ) as branch_mock,
        patch(f"{_TASKS}.get_status_read_root", return_value=missing_root) as read_root_mock,
        patch(f"{_TASKS}.console") as console_mock,
        pytest.raises(typer.Exit) as exc_info,
    ):
        tasks_status_cmd._st_resolve_dirs(st)
    assert exc_info.value.exit_code == 1
    locate_mock.assert_called_once()
    slug_mock.assert_called_once_with(explicit_mission="034-feature", json_output=True, repo_root=tmp_path, error_handler=tasks_status_cmd._status_selector_error)
    branch_mock.assert_called_once_with(tmp_path, "034-feature", True)
    read_root_mock.assert_called_once_with(st.cwd)
    payload = console_mock.emit_json.call_args.args[0]
    assert payload["ok"] is False
    assert "Mission directory not found" in payload["error"]["message"]


def test_patched_workspace_resolver_intercepts_resolve_execution_mode(
    tmp_path: Path,
) -> None:
    """``tasks.resolve_workspace_for_wp`` (D7 ×3, the mocked-env fixture seam)
    bites through ``_st_resolve_execution_mode``'s primary arm."""
    workspace = SimpleNamespace(execution_mode="worktree", resolution_kind="lane_workspace")
    with patch(f"{_TASKS}.resolve_workspace_for_wp", return_value=workspace) as resolver_mock:
        result = tasks_status_cmd._st_resolve_execution_mode("execution_mode: ignored", tmp_path, "034-feature", "WP01")
    # owned-checkout-lifecycle-authority WP09: the caller now forwards
    # ``owned=`` (``None`` for every non-owned call, as here) so an owned
    # mission's staleness/workspace resolution reads the owned checkout.
    resolver_mock.assert_called_once_with(tmp_path, "034-feature", "WP01", owned=None)
    assert result == ("worktree", "lane_workspace")


def test_patched_workspace_resolver_forwards_owned_fact(tmp_path: Path) -> None:
    """Owned counterpart (review cycle 1 issue 2): a real ``OwnedCheckout``
    fact is forwarded verbatim to ``resolve_workspace_for_wp``, proving an
    owned mission's workspace/staleness resolution reads the owned checkout,
    never a repository-root-side lane worktree."""
    fact = _mint_owned(tmp_path)
    workspace = SimpleNamespace(execution_mode="code_change", resolution_kind="owned_checkout")
    with patch(f"{_TASKS}.resolve_workspace_for_wp", return_value=workspace) as resolver_mock:
        result = tasks_status_cmd._st_resolve_execution_mode("execution_mode: ignored", tmp_path, "034-feature", "WP01", owned=fact)
    resolver_mock.assert_called_once_with(tmp_path, "034-feature", "WP01", owned=fact)
    assert result == ("code_change", "owned_checkout")


def test_st_status_read_dir_owned_arm_never_calls_committed_status_dir(tmp_path: Path) -> None:
    """``_st_status_read_dir``'s owned arm (review cycle 1 issue 2): returns
    ``owned.mission_dir`` and never calls ``committed_status_dir`` -- pinned
    with a raising monkeypatch so a regression that re-introduces the R-side
    committed-authority read for an owned run fails loudly."""
    fact = _mint_owned(tmp_path)
    st = _make_state()
    st.owned = fact
    st.feature_dir = tmp_path / "unrelated-coord-dir"

    def _raise(*args: object, **kwargs: object) -> None:
        raise AssertionError("owned arm must not call committed_status_dir")

    with patch("runtime.next.committed_authority.committed_status_dir", side_effect=_raise):
        result = tasks_status_cmd._st_status_read_dir(st)
    assert result == fact.mission_dir
    assert result is not st.feature_dir


def test_st_status_read_dir_non_owned_arm_still_calls_committed_status_dir(tmp_path: Path) -> None:
    """Non-owned arm: unchanged behaviour -- ``committed_status_dir`` still
    governs the committed-vs-coordination read-dir decision."""
    st = _make_state()
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.feature_dir = tmp_path / "coord-dir"
    committed_dir = tmp_path / "primary-committed-dir"
    with patch(
        "runtime.next.committed_authority.committed_status_dir",
        return_value=committed_dir,
    ) as committed_mock:
        result = tasks_status_cmd._st_status_read_dir(st)
    committed_mock.assert_called_once_with(tmp_path, "034-feature")
    assert result == committed_dir


def test_st_resolve_dirs_owned_arm_never_calls_non_owned_resolution_seams(tmp_path: Path) -> None:
    """Owned arm (review cycle 1 issue 3): once ``_st_resolve_owned`` resolves
    a fact, ``_st_resolve_dirs`` returns immediately and never reaches the
    non-owned resolution seams -- ``_find_mission_slug``,
    ``_ensure_target_branch_checked_out``, ``resolve_handle_to_read_path``,
    ``candidate_feature_dir_for_mission`` and ``get_status_read_root`` --
    pinned with raising monkeypatches so a regression that lets an owned run
    fall through to R-side resolution fails loudly.
    """
    fact = _mint_owned(tmp_path)
    st = _make_state()

    def _raise(name: str) -> Any:
        def _inner(*args: object, **kwargs: object) -> None:
            raise AssertionError(f"owned arm must not call {name}")

        return _inner

    with (
        patch(f"{_TASKS}.locate_project_root", return_value=tmp_path),
        patch(
            "specify_cli.cli.commands._owned_checkout.resolve_owned_or_adopt",
            return_value=fact,
        ),
        patch(f"{_TASKS}._find_mission_slug", side_effect=_raise("_find_mission_slug")),
        patch(
            f"{_TASKS}._ensure_target_branch_checked_out",
            side_effect=_raise("_ensure_target_branch_checked_out"),
        ),
        patch(
            "specify_cli.missions._read_path_resolver.resolve_handle_to_read_path",
            side_effect=_raise("resolve_handle_to_read_path"),
        ),
        patch(
            "specify_cli.missions._read_path_resolver.candidate_feature_dir_for_mission",
            side_effect=_raise("candidate_feature_dir_for_mission"),
        ),
        patch(f"{_TASKS}.get_status_read_root", side_effect=_raise("get_status_read_root")),
    ):
        tasks_status_cmd._st_resolve_dirs(st)

    assert st.owned is fact
    assert st.mission_slug == fact.mission_slug
    assert st.main_repo_root == fact.repository_root
    assert st.feature_dir == fact.mission_dir


def test_patched_console_intercepts_load_work_packages_empty_leg(
    tmp_path: Path,
) -> None:
    """The data-loading phase permits empty status without rendering or exiting."""
    st = _make_state()
    st.feature_dir = tmp_path
    st.tasks_dir = tmp_path
    with patch(f"{_TASKS}.console") as console_mock:
        tasks_status_cmd._st_load_work_packages(st)
    assert st.work_packages == []
    console_mock.print.assert_not_called()


def test_patched_stall_threshold_intercepts_apply_review_flags(
    tmp_path: Path,
) -> None:
    """``tasks._review_stall_threshold_minutes`` (the tasks.py-resident
    single-family helper, T007 partition) bites through
    ``_st_apply_review_flags``' ``_tasks.<attr>`` route."""
    st = _make_state()
    st.main_repo_root = tmp_path
    st.tasks_dir = tmp_path
    st.work_packages = []
    with patch(f"{_TASKS}._review_stall_threshold_minutes", return_value=77) as threshold_mock:
        tasks_status_cmd._st_apply_review_flags(st)
    threshold_mock.assert_called_once_with(tmp_path)
    assert st.review_stall_threshold == 77
    assert st.stale_verdicts == []
    assert st.stalled_wps == []


def test_patched_sentinel_view_and_identity_drive_emit_json(tmp_path: Path) -> None:
    """The ``tasks.build_status_view`` sentinel seam
    (test_tasks_status_view.py's monkeypatch contract), the
    ``tasks.get_auto_commit_default`` D7 seam and
    ``tasks._mission_identity_payload`` all bite through ``_st_emit_json``,
    and the envelope routes through the injected Render port."""
    st = _make_state()
    st.main_repo_root = tmp_path
    st.feature_dir = tmp_path
    st.work_packages = [{"id": "WP01", "lane": Lane.PLANNED}]
    sentinel = _view(total_wps=999, done_count=7, stale_count=5)
    ports = MagicMock()
    ports.render.json_envelope.return_value = "{}"
    with (
        patch(f"{_TASKS}.build_status_view", return_value=sentinel) as view_mock,
        patch(f"{_TASKS}.get_auto_commit_default", return_value=True) as auto_mock,
        patch(
            f"{_TASKS}._mission_identity_payload",
            return_value={"mission_id": "01SENTINEL"},
        ) as identity_mock,
    ):
        tasks_status_cmd._st_emit_json(st, ports)
    view_mock.assert_called_once()
    auto_mock.assert_called_once_with(tmp_path)
    identity_mock.assert_called_once_with(tmp_path)
    payload = ports.render.json_envelope.call_args.args[0]
    assert payload["mission_id"] == "01SENTINEL"
    assert payload["total_wps"] == 999
    assert payload["done_count"] == 7
    assert payload["stale_wps"] == 5
    assert payload["auto_commit"] is True


def test_patched_hic_marker_intercepts_board_cell(tmp_path: Path) -> None:
    """``tasks._get_hic_marker`` (tasks.py-resident, ×8 family call sites)
    bites through ``_st_board_cell``'s ``_tasks.<attr>`` route."""
    wp = {"id": "WP01", "title": "Latency audit", "agent_profile": "human-in-charge"}
    with patch(f"{_TASKS}._get_hic_marker", return_value="👤 ") as marker_mock:
        cell = tasks_status_cmd._st_board_cell(wp, Lane.PLANNED, tmp_path, None)
    marker_mock.assert_called_once_with("human-in-charge", tmp_path, repo=None)
    assert cell.startswith("👤 WP01")


def test_patched_stale_label_intercepts_render_active(tmp_path: Path) -> None:
    """``tasks._render_stale_status`` and ``tasks._get_hic_marker`` bite
    through ``_st_render_active``'s in-progress section, emitting via the
    injected Render port."""
    st = _make_state()
    st.main_repo_root = tmp_path
    wp = {"id": "WP01", "title": "Latency audit", "agent": "claude", "agent_profile": ""}
    view = _view(lanes={**_empty_lanes(), Lane.IN_PROGRESS: [wp]})
    ports = MagicMock()
    with (
        patch(f"{_TASKS}._get_hic_marker", return_value="") as marker_mock,
        patch(f"{_TASKS}._render_stale_status", return_value="stale: 42m") as label_mock,
    ):
        tasks_status_cmd._st_render_active(ports, st, view, {}, None)
    marker_mock.assert_called_once()
    label_mock.assert_called_once_with(None)
    rendered = [call.args[0] for call in ports.render.human.call_args_list if isinstance(call.args[0], str)]
    assert any("stale: 42m" in line for line in rendered)


def test_patched_auto_commit_intercepts_render_summary(tmp_path: Path) -> None:
    """``tasks.get_auto_commit_default`` (D7 ×9) bites through
    ``_st_render_summary``'s ``_tasks.<attr>`` route."""
    st = _make_state()
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    ports = MagicMock()
    with patch(f"{_TASKS}.get_auto_commit_default", return_value=False) as auto_mock:
        tasks_status_cmd._st_render_summary(ports, st, _view())
    auto_mock.assert_called_once_with(tmp_path)
    assert ports.render.human.call_count >= 4


def test_patched_sentinel_view_drives_render_human(tmp_path: Path) -> None:
    """``tasks.build_status_view`` bites through ``_st_render_human``'s
    ``_tasks.<attr>`` route (the human-leg twin of the sentinel-seam contract)
    and ``tasks._apply_stale_status_fields`` is NOT consulted when staleness
    reports nothing."""
    st = _make_state(json_output=False)
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    ports = MagicMock()
    sentinel = _view(total_wps=999)
    with (
        patch(f"{_TASKS}.build_status_view", return_value=sentinel) as view_mock,
        patch(
            "specify_cli.core.stale_detection.check_doing_wps_for_staleness",
            return_value={},
        ),
        patch(f"{_TASKS}._apply_stale_status_fields") as stale_fields_mock,
        patch(f"{_TASKS}.get_auto_commit_default", return_value=False),
    ):
        tasks_status_cmd._st_render_human(st, ports)
    view_mock.assert_called_once()
    stale_fields_mock.assert_not_called()
    assert ports.render.human.call_count > 5


def test_patched_staleness_forwards_owned_fact_in_render_human(tmp_path: Path) -> None:
    """Owned counterpart (review cycle 1 issue 2): ``_st_render_human``
    forwards ``owned=st.owned`` (a real fact) to
    ``check_doing_wps_for_staleness``."""
    fact = _mint_owned(tmp_path)
    st = _make_state(json_output=False)
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.owned = fact
    ports = MagicMock()
    with (
        patch(f"{_TASKS}.build_status_view", return_value=_view()),
        patch(
            "specify_cli.core.stale_detection.check_doing_wps_for_staleness",
            return_value={},
        ) as staleness_mock,
        patch(f"{_TASKS}.get_auto_commit_default", return_value=False),
    ):
        tasks_status_cmd._st_render_human(st, ports)
    staleness_mock.assert_called_once_with(
        main_repo_root=tmp_path,
        mission_slug="034-feature",
        doing_wps=[],
        threshold_minutes=st.stale_threshold,
        owned=fact,
    )


def test_patched_staleness_forwards_owned_fact_in_emit_json(tmp_path: Path) -> None:
    """Owned counterpart (review cycle 1 issue 2): ``_st_emit_json``
    forwards ``owned=st.owned`` (a real fact) to
    ``check_doing_wps_for_staleness``, and merges ``stale_repository_root_copy``
    into the payload."""
    fact = _mint_owned(tmp_path)
    st = _make_state(json_output=True)
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.feature_dir = tmp_path
    st.owned = fact
    ports = MagicMock()
    with (
        patch(f"{_TASKS}.build_status_view", return_value=_view()),
        patch(
            "specify_cli.core.stale_detection.check_doing_wps_for_staleness",
            return_value={},
        ) as staleness_mock,
        patch(f"{_TASKS}.get_auto_commit_default", return_value=False),
        patch(f"{_TASKS}._mission_identity_payload", return_value={}),
    ):
        tasks_status_cmd._st_emit_json(st, ports)
    staleness_mock.assert_called_once_with(
        main_repo_root=tmp_path,
        mission_slug="034-feature",
        doing_wps=[],
        threshold_minutes=st.stale_threshold,
        owned=fact,
    )
    payload = ports.render.json_envelope.call_args.args[0]
    assert "stale_repository_root_copy" in payload


def test_patched_output_error_intercepts_do_status_exception_arm() -> None:
    """The shared JSON envelope renders ``_do_status``' generic exception
    arm (exit-1 translation). The failure is injected through the routed
    ``tasks.locate_project_root`` D7 seam — the orchestrator reaches its
    ``_st_*`` phase siblings by bare same-module name (the ratchet-closure
    invariant), so the phases themselves are deliberately NOT patch targets."""
    with (
        patch(f"{_TASKS}.locate_project_root", side_effect=RuntimeError("boom")),
        patch(f"{_TASKS}.console.emit_json") as error_mock,
        pytest.raises(typer.Exit) as exc_info,
    ):
        tasks_status_cmd._do_status(
            mission="034-feature",
            json_output=True,
            stale_threshold=10,
            ports=MagicMock(),
        )
    assert exc_info.value.exit_code == 1
    error_mock.assert_called_once_with({"ok": False, "error": {"code": "status_failed", "message": "boom"}})


def test_default_ports_constructs_through_tasks_bindings() -> None:
    """The moved ``_default_status_ports`` constructs its adapters via the
    ``tasks`` bindings, so ``@patch("...tasks.<Adapter>")`` intercepts
    construction (the WP03 checklist invariant, preserved across the move) —
    and the Render adapter is built with the module ``console`` and the ONE
    ``indent=2`` envelope (the WP01 status byte case's production seam)."""
    with (
        patch(f"{_TASKS}.RealFsReader") as fs_cls,
        patch(f"{_TASKS}.RealCoordCommitRouter") as coord_cls,
        patch(f"{_TASKS}.RealGitOps") as git_cls,
        patch(f"{_TASKS}.RealRender") as render_cls,
    ):
        ports = tasks._default_status_ports()
    render_cls.assert_called_once_with(console=tasks.console, indent=2)
    assert ports.fs is fs_cls.return_value
    assert ports.coord is coord_cls.return_value
    assert ports.git is git_cls.return_value
    assert ports.render is render_cls.return_value


# NOTE (WP06 / #2565): the identity battery
# (``test_tasks_binding_is_tasks_status_cmd_object``, 21 symbols) and the
# exact-set completeness pin (``test_move_set_matches_tasks_status_cmd_defs``)
# formerly lived here. Both are RETIRED — mechanically subsumed by WP05's
# consolidated guard, ``test_tasks_compat_surface.py``
# (``test_tasks_binding_is_seam_object`` for identity;
# ``test_guard_symbol_is_genuinely_native_to_its_seam`` +
# ``test_guard_keyset_is_superset_of_all_six_seams_native_defs`` for the
# exact-set claim), which covers the same 21-symbol ``tasks_status_cmd``
# surface. See the module docstring above for the reconcile ruling on the
# interception battery kept in this file.
