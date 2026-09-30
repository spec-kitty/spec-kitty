"""Focused tests for the WP16 task-command conversion onto the ``OwnedCheckout`` fact.

owned-checkout-lifecycle-authority WP16: ``move-task``, ``mark-status``,
``spec-commit`` and ``check-prerequisites`` validate ownership exactly once at
their Typer edge and read every owned root, branch, slug and mission directory
straight off the validated fact. These tests execute each new or converted
owned arm in isolation, and pin that no owned arm consults a resolver
(``get_main_repo_root``, the minter, the adoption probe) again.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import typer

from mission_runtime import ActionContextError, OwnedCheckout, OwnedRefusalCode
from specify_cli.cli.commands import _owned_checkout
from specify_cli.cli.commands.agent import tasks, tasks_finalize_validation, tasks_mark_status, tasks_move_task, tasks_shared, tasks_verdict_persistence
from specify_cli.cli.commands.agent import mission_check_prerequisites, tasks_parsing_validation
from specify_cli.cli.commands import spec_commit_cmd
from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES
from specify_cli.status import Lane
from tests.integration.conftest import OwnedCheckouts, make_owned_checkouts, owned_checkouts
from tests.integration.test_explicit_checkout_commands import checkouts, invoke

__all__ = ["checkouts", "make_owned_checkouts", "owned_checkouts"]
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


class _ResolverConsulted(AssertionError):
    """Raised by a poisoned resolver: an owned arm must never reach one."""


def _poison_resolvers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every resolver an owned arm could fall back to RAISE."""

    def _boom(*_args: object, **_kwargs: object) -> Any:
        raise _ResolverConsulted

    from specify_cli.core import owned_mission, paths

    monkeypatch.setattr(paths, "get_main_repo_root", _boom)
    monkeypatch.setattr(tasks, "get_main_repo_root", _boom)
    monkeypatch.setattr(tasks, "locate_project_root", _boom)
    monkeypatch.setattr(owned_mission, "resolve_owned_mission", _boom)
    monkeypatch.setattr(owned_mission, "adopt_owned_checkout", _boom)


@pytest.fixture
def fact(owned_checkouts: OwnedCheckouts) -> OwnedCheckout:
    """The validated fact for the standard R/P/S triple, minted through the shared helper."""
    minted = _owned_checkout.resolve_owned_or_adopt(
        owned_checkouts.repository_root,
        owned_checkouts.owned_root,
        owned_checkouts.mission_slug,
        cwd=owned_checkouts.owned_root,
        allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
    )
    assert minted is not None
    return minted


# ---------------------------------------------------------------------------
# _owned_checkout: the Typer-edge wrapper and the flat envelope
# ---------------------------------------------------------------------------


class TestResolveOwnedOrRefuse:
    def test_explicit_checkout_returns_the_fact(self, owned_checkouts: OwnedCheckouts) -> None:
        result = _owned_checkout.resolve_owned_or_refuse(
            owned_checkouts.repository_root,
            owned_checkouts.owned_root,
            owned_checkouts.mission_slug,
            cwd=owned_checkouts.sibling,
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
            json_output=True,
            envelope=_owned_checkout.flat_error_envelope,
        )
        assert result is not None
        assert result.owned_root == owned_checkouts.owned_root.resolve()

    def test_flagless_from_repository_root_returns_none(self, owned_checkouts: OwnedCheckouts) -> None:
        result = _owned_checkout.resolve_owned_or_refuse(
            owned_checkouts.repository_root,
            None,
            owned_checkouts.mission_slug,
            cwd=owned_checkouts.repository_root,
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
            json_output=True,
            envelope=_owned_checkout.flat_error_envelope,
        )
        assert result is None

    def test_refusal_prints_the_envelope_and_exits_one(self, owned_checkouts: OwnedCheckouts, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(typer.Exit) as excinfo:
            _owned_checkout.resolve_owned_or_refuse(
                owned_checkouts.repository_root,
                owned_checkouts.repository_root,
                owned_checkouts.mission_slug,
                cwd=owned_checkouts.repository_root,
                allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
                json_output=True,
                envelope=_owned_checkout.flat_error_envelope,
            )
        assert excinfo.value.exit_code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["error_code"] == OwnedRefusalCode.OWNED_CHECKOUT_IS_REPOSITORY_ROOT
        assert set(payload) == {"error", "error_code"}

    def test_target_override_is_forwarded_on_the_explicit_path(self, owned_checkouts: OwnedCheckouts, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(typer.Exit):
            _owned_checkout.resolve_owned_or_refuse(
                owned_checkouts.repository_root,
                owned_checkouts.owned_root,
                owned_checkouts.mission_slug,
                cwd=owned_checkouts.owned_root,
                allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
                json_output=True,
                envelope=_owned_checkout.flat_error_envelope,
                target_override="codex/not-the-checked-out-branch",
            )
        assert json.loads(capsys.readouterr().out)["error_code"] == OwnedRefusalCode.OWNED_BRANCH_REFUSED


def test_flat_error_envelope_shape() -> None:
    assert _owned_checkout.flat_error_envelope("CODE", "msg") == {"error": "msg", "error_code": "CODE"}


# ---------------------------------------------------------------------------
# tasks._resolve_task_owned: the move-task / mark-status Typer edge
# ---------------------------------------------------------------------------


class TestResolveTaskOwned:
    def test_no_project_root_leaves_the_body_to_report_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(tasks, "locate_project_root", lambda: None)
        assert tasks._resolve_task_owned(Path("/nowhere"), "m", json_output=True, envelope=_owned_checkout.flat_error_envelope) is None

    def test_explicit_checkout_is_validated_once(self, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(tasks, "locate_project_root", lambda: owned_checkouts.repository_root)
        monkeypatch.chdir(owned_checkouts.sibling)
        result = tasks._resolve_task_owned(
            owned_checkouts.owned_root,
            owned_checkouts.mission_slug,
            json_output=True,
            envelope=_owned_checkout.flat_error_envelope,
        )
        assert result is not None
        assert result.mission_slug == owned_checkouts.mission_slug
        assert result.write_branch == owned_checkouts.target_branch

    def test_refusal_exits_with_the_command_envelope(
        self, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(tasks, "locate_project_root", lambda: owned_checkouts.repository_root)
        with pytest.raises(typer.Exit):
            tasks._resolve_task_owned(
                owned_checkouts.repository_root,
                owned_checkouts.mission_slug,
                json_output=True,
                envelope=tasks_mark_status._ms_failure_payload,
            )
        payload = json.loads(capsys.readouterr().out)
        assert payload["result"] == "error"
        assert payload["error_code"] == OwnedRefusalCode.OWNED_CHECKOUT_IS_REPOSITORY_ROOT
        assert payload["state_applied"] is False


# ---------------------------------------------------------------------------
# move-task: the owned arm of target resolution, and the small value reads
# ---------------------------------------------------------------------------


def _move_state(**overrides: Any) -> Any:
    base: dict[str, Any] = {
        "resolved_auto_commit": True,
        "agent": "codex",
        "assignee": None,
        "note": None,
        "shell_pid": None,
        "tracker_ref": None,
        "mission_slug": "",
        "main_repo_root": Path(),
        "target_branch": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestMoveTaskOwnedTargets:
    def test_targets_come_off_the_fact_without_consulting_a_resolver(self, fact: OwnedCheckout, monkeypatch: pytest.MonkeyPatch) -> None:
        _poison_resolvers(monkeypatch)
        st = _move_state()

        tasks_move_task._mt_apply_owned_targets(st, fact)

        assert st.mission_slug == fact.mission_slug
        assert st.main_repo_root == fact.repository_root
        assert st.target_branch == fact.write_branch

    def test_owned_run_requires_auto_commit(self, fact: OwnedCheckout) -> None:
        with pytest.raises(ActionContextError) as excinfo:
            tasks_move_task._mt_apply_owned_targets(_move_state(resolved_auto_commit=False), fact)
        assert excinfo.value.code == OwnedRefusalCode.OWNED_OPTION_UNSUPPORTED

    def test_invalid_shell_pid_is_an_owned_input_refusal(self, fact: OwnedCheckout) -> None:
        with pytest.raises(ActionContextError) as excinfo:
            tasks_move_task._mt_apply_owned_targets(_move_state(shell_pid="not-a-number"), fact)
        assert excinfo.value.code == OwnedRefusalCode.OWNED_INPUT_INVALID

    def test_owned_workspace_is_the_fact_checkout(self, fact: OwnedCheckout, monkeypatch: pytest.MonkeyPatch) -> None:
        _poison_resolvers(monkeypatch)
        wp = SimpleNamespace(frontmatter="---\nexecution_mode: code_change\n---\n")
        st = _move_state(owned=fact, wp=wp, task_id="WP01", mission_slug=fact.mission_slug, target_branch=fact.write_branch)

        workspace = tasks_move_task._mt_owned_workspace(st)

        assert workspace.worktree_path == fact.owned_root
        assert workspace.workspace_name == fact.owned_root.name

    def test_owned_workspace_is_the_resolvers_single_owned_construction(self, fact: OwnedCheckout, monkeypatch: pytest.MonkeyPatch) -> None:
        """Architecture review item 5: move-task builds no second owned ``ResolvedWorkspace`` shape.

        The owned workspace is exactly what ``resolve_workspace_for_wp(..., owned=)``
        produces (one constructor), so move-task and every other owned consumer
        agree field for field (``lane_wp_ids``, ``mode_source``, ``branch_name``).
        """
        from specify_cli.workspace.context import resolve_workspace_for_wp

        _poison_resolvers(monkeypatch)
        wp = SimpleNamespace(frontmatter="---\nexecution_mode: code_change\n---\n")
        st = _move_state(owned=fact, wp=wp, task_id="WP01", mission_slug=fact.mission_slug, target_branch=fact.write_branch)

        assert tasks_move_task._mt_owned_workspace(st) == resolve_workspace_for_wp(fact.repository_root, fact.mission_slug, "WP01", owned=fact)


# ---------------------------------------------------------------------------
# tasks_shared / tasks_parsing_validation / tasks_finalize_validation
# ---------------------------------------------------------------------------


class TestSharedReadersTakeTheFact:
    def test_check_unchecked_subtasks_reads_the_fact_without_get_main_repo_root(self, fact: OwnedCheckout, monkeypatch: pytest.MonkeyPatch) -> None:
        _poison_resolvers(monkeypatch)

        result = tasks_shared._check_unchecked_subtasks(fact.owned_root, fact.mission_slug, "WP01", False, owned=fact)

        assert result == []

    def test_validate_ready_for_review_owned_arm_uses_the_fact_roots(self, fact: OwnedCheckout, monkeypatch: pytest.MonkeyPatch) -> None:
        _poison_resolvers(monkeypatch)

        def _resolver_boom(*_a: object, **_k: object) -> Any:
            raise _ResolverConsulted

        valid, guidance = tasks_parsing_validation._validate_ready_for_review(
            fact.owned_root,
            fact.mission_slug,
            "WP01",
            False,
            owned=fact,
            get_main_repo_root=_resolver_boom,
            get_mission_type=lambda _feature_dir: "documentation",
            get_feature_target_branch=_resolver_boom,
            resolve_workspace_for_wp=_resolver_boom,
            review_currency_check_branch=_resolver_boom,
            behind_commits_touch_only_planning_artifacts=_resolver_boom,
            filter_runtime_state_paths=_resolver_boom,
            list_wp_branch_specs_changes_for_guard=_resolver_boom,
            console=MagicMock(),
        )

        assert (valid, guidance) == (True, [])

    def test_wrapper_forwards_owned_not_effective_root(self, fact: OwnedCheckout, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        def _seam(*_args: object, **kwargs: Any) -> tuple[bool, list[str]]:
            captured.update(kwargs)
            return True, []

        monkeypatch.setattr(tasks_shared, "_seam_validate_ready_for_review", _seam)

        assert tasks_shared._validate_ready_for_review(fact.owned_root, fact.mission_slug, "WP01", False, owned=fact) == (True, [])
        assert captured["owned"] is fact
        assert "effective_root" not in captured

    def test_read_transactional_wp_lane_forwards_the_fact(self, fact: OwnedCheckout, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict[str, Any] = {}

        def _fake_read(**kwargs: Any) -> list[Any]:
            seen.update(kwargs)
            return []

        monkeypatch.setattr(tasks_finalize_validation, "read_events_transactional", _fake_read)
        monkeypatch.setattr(tasks_finalize_validation, "_wp_lane_from_status_events", lambda _events, _wp: Lane.PLANNED)

        lane = tasks_finalize_validation._read_transactional_wp_lane(
            feature_dir=fact.mission_dir,
            mission_slug=fact.mission_slug,
            wp_id="WP01",
            repo_root=fact.repository_root,
            owned=fact,
        )

        assert lane == Lane.PLANNED
        assert seen["owned"] is fact
        assert "effective_root" not in seen


# ---------------------------------------------------------------------------
# tasks_verdict_persistence: value reads off the fact
# ---------------------------------------------------------------------------


def test_revert_commit_worktree_is_the_owned_checkout(fact: OwnedCheckout) -> None:
    st: Any = SimpleNamespace(owned=fact)
    original = fact.mission_dir / "tasks" / "verdict.md"

    root, path = tasks_verdict_persistence._resolve_revert_commit_worktree(st, target_ref=fact.write_branch, original_path=original)

    assert (root, path) == (fact.owned_root, original)


# ---------------------------------------------------------------------------
# mark-status: the failure envelope and its reporter
# ---------------------------------------------------------------------------


class TestMarkStatusFailureEnvelope:
    def test_refusal_shape_has_nothing_applied(self) -> None:
        payload = tasks_mark_status._ms_failure_payload("CODE", "msg")
        assert payload == {
            "result": "error",
            "error_code": "CODE",
            "error": "msg",
            "state_applied": False,
            "event_ids": [],
            "applied_wps": [],
            "destination_ref": None,
            "status_events_path": None,
            "status_snapshot_path": None,
            "dirty": None,
        }

    def test_applied_state_is_reported(self, tmp_path: Path) -> None:
        payload = tasks_mark_status._ms_failure_payload(
            "CODE",
            "msg",
            event_ids=["E1"],
            applied_wps=["WP01"],
            destination_ref="codex/owned",
            status_events_path=tmp_path / "status.events.jsonl",
            status_snapshot_path=tmp_path / "status.json",
            dirty=False,
        )
        assert payload["state_applied"] is True
        assert payload["event_ids"] == ["E1"]
        assert payload["applied_wps"] == ["WP01"]
        assert payload["status_events_path"] == str(tmp_path / "status.events.jsonl")
        assert payload["status_snapshot_path"] == str(tmp_path / "status.json")
        assert payload["dirty"] is False

    @pytest.mark.parametrize("json_output", [True, False])
    def test_report_owned_failure_exits_one_with_the_owned_state(self, fact: OwnedCheckout, json_output: bool, capsys: pytest.CaptureFixture[str]) -> None:
        st: Any = SimpleNamespace(status_dir=Path(), applied_event_ids=["E1"], applied_wps=["WP01"], json_output=json_output)
        error = ActionContextError("TEST_CODE", "boom")

        with pytest.raises(typer.Exit) as excinfo:
            tasks_mark_status._ms_report_owned_failure(st, fact, error)

        assert excinfo.value.exit_code == 1
        captured = capsys.readouterr()
        if json_output:
            payload = json.loads(captured.out)
            assert payload["error_code"] == "TEST_CODE"
            assert payload["event_ids"] == ["E1"]
            assert payload["applied_wps"] == ["WP01"]
            assert payload["destination_ref"] == fact.write_branch
            assert payload["status_events_path"] == str(fact.mission_dir / "status.events.jsonl")
            assert payload["status_snapshot_path"] is None
            assert payload["dirty"] is False
            assert captured.err == ""
        else:
            # Unified owned-refusal output (#5445): human mode lands on
            # stderr as ``Error: [<CODE>] <message>``, not the old
            # ``[red]CODE: message[/red]`` on stdout.
            assert captured.err.strip() == "Error: [TEST_CODE] boom"
            assert captured.out == ""

    def test_report_owned_failure_defaults_the_error_code(self, fact: OwnedCheckout, capsys: pytest.CaptureFixture[str]) -> None:
        st: Any = SimpleNamespace(status_dir=fact.mission_dir, applied_event_ids=[], applied_wps=[], json_output=True)

        with pytest.raises(typer.Exit):
            tasks_mark_status._ms_report_owned_failure(st, fact, RuntimeError("plain"))

        payload = json.loads(capsys.readouterr().out)
        assert payload["error_code"] == "MARK_STATUS_FAILED"
        assert payload["status_snapshot_path"] == str(fact.mission_dir / "status.json")


# ---------------------------------------------------------------------------
# spec-commit
# ---------------------------------------------------------------------------


class TestSpecCommitConversion:
    def test_owned_batch_reads_slug_and_paths_off_the_fact(self, fact: OwnedCheckout, monkeypatch: pytest.MonkeyPatch) -> None:
        _poison_resolvers(monkeypatch)
        spec = Path("kitty-specs") / fact.mission_slug / "spec.md"

        slug, files = spec_commit_cmd._resolve_commit_inputs(fact.repository_root, [spec], "ignored-handle", fact)

        assert slug == fact.mission_slug
        assert files == [fact.owned_root / spec]

    def test_owned_batch_refuses_a_path_outside_the_mission(self, fact: OwnedCheckout) -> None:
        with pytest.raises(ActionContextError) as excinfo:
            spec_commit_cmd._resolve_commit_inputs(fact.repository_root, [Path("app.py")], None, fact)
        assert excinfo.value.code == OwnedRefusalCode.OWNED_MISSION_PATH_REFUSED

    def test_ordinary_batch_anchors_relative_paths_at_the_repository_root(self, tmp_path: Path) -> None:
        slug, files = spec_commit_cmd._resolve_commit_inputs(tmp_path, [Path("kitty-specs/m/spec.md")], "m", None)
        assert slug == "m"
        assert files == [(tmp_path / "kitty-specs/m/spec.md").resolve()]

    def test_slug_comes_from_the_option_else_the_first_path(self) -> None:
        assert spec_commit_cmd._mission_slug_from_args([Path("kitty-specs/from-path/spec.md")], None) == "from-path"
        assert spec_commit_cmd._mission_slug_from_args([Path("kitty-specs/from-path/spec.md")], " explicit ") == "explicit"
        assert spec_commit_cmd._mission_slug_from_args([], None) is None

    def test_refusal_envelope_keeps_the_command_shape_and_adds_the_code(self) -> None:
        payload = spec_commit_cmd._refusal_envelope("SOME_CODE", "why")
        assert payload["success"] is False
        assert payload["result"] == "error"
        assert payload["error"] == "why"
        assert payload["error_code"] == "SOME_CODE"


# ---------------------------------------------------------------------------
# check-prerequisites
# ---------------------------------------------------------------------------


class TestCheckPrerequisitesConversion:
    def test_refusal_envelope_carries_the_cli_version_like_every_json_payload(self) -> None:
        payload = mission_check_prerequisites._refusal_envelope("SOME_CODE", "why")
        assert payload["error"] == "why"
        assert payload["error_code"] == "SOME_CODE"
        assert "spec_kitty_version" in payload

    def test_resume_probe_with_a_validated_checkout_is_refused(self, fact: OwnedCheckout) -> None:
        with pytest.raises(ActionContextError) as excinfo:
            mission_check_prerequisites._refuse_resume_probe_with_owned(fact, resume_probe=True)
        assert excinfo.value.code == OwnedRefusalCode.OWNED_OPTION_UNSUPPORTED

    def test_resume_probe_without_a_fact_or_a_fact_without_the_probe_passes(self, fact: OwnedCheckout) -> None:
        mission_check_prerequisites._refuse_resume_probe_with_owned(None, resume_probe=True)
        mission_check_prerequisites._refuse_resume_probe_with_owned(fact, resume_probe=False)
        mission_check_prerequisites._refuse_resume_probe_with_owned(None, resume_probe=False)

    def test_invalid_checkout_with_resume_probe_reports_its_ownership_code(self, checkouts: tuple[Path, Path, Path]) -> None:
        _primary, owned, _sibling = checkouts

        result = invoke("check-prerequisites", owned / "kitty-specs", "--resume-probe")

        assert result.exit_code == 1, result.output
        assert json.loads(result.output)["error_code"] == OwnedRefusalCode.OWNERSHIP_NESTED

    def test_flagless_resume_probe_never_adopts_the_invoking_checkout(self, checkouts: tuple[Path, Path, Path]) -> None:
        _primary, owned, _sibling = checkouts

        result = invoke("check-prerequisites", owned, "--resume-probe", opt_in=False)

        assert OwnedRefusalCode.OWNED_OPTION_UNSUPPORTED not in result.output
