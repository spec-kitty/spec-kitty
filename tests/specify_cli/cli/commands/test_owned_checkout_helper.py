"""Unit and integration tests for the shared CLI owned-checkout surface (WP08).

Covers:

* ``TestContextHelpers`` -- the ``agent/context.py`` campsite extraction
  (T042): each helper pulled out of ``resolve_context`` gets a focused test
  so the diff-cover gate is satisfied and a later change to one helper is
  caught in isolation.
* the public surface of ``specify_cli.cli.commands._owned_checkout`` (T039,
  landing in a later commit in this same file): option declaration, the
  single validation entry point, the typed refusal emitter and its registry
  validation, the envelope builders, and the stale-repository-root-copy
  reporter.
* the re-homed ``operation_context.py`` behaviours (T043, also landing
  later), mapped explicitly onto their WP08 replacement below.

T043 disposition table (moved here from an inline comment per review cycle 1
finding 10 -- the table belongs in the module docstring):

* ``test_prefers_caller_owned_mission_surface`` (caller surface chosen,
  mocked probe) -> ``TestResolveOwnedOrAdopt::test_flagless_adopts_validated_owned_checkout``:
  returns the validated fact.
* ``test_falls_back_to_primary_when_caller_has_no_mission`` (a VALID,
  registered caller checkout with no copy of M; R chosen) ->
  ``TestResolveOwnedOrAdopt::test_no_adoption_when_checkout_lacks_mission``:
  ``None``; the command resolves R. Distinct from cwd being R itself
  (``test_flagless_from_repository_root_returns_none``), which the old
  disposition conflated this row with.
* ``test_rejects_conflicting_primary_and_caller_identities``
  (``MissionSurfaceConflictError``) ->
  ``TestResolveOwnedOrAdopt::test_flagless_conflicting_identity_propagates_mission_context_conflict``:
  ``ActionContextError("MISSION_CONTEXT_CONFLICT")``.
* ``test_real_resolver_prefers_caller_worktree_mission`` (adopted WITHOUT
  validation) ->
  ``TestUnvalidatedPointerNotAdopted::test_unvalidated_pointer_checkout_is_not_adopted``:
  ``None`` -- the pointer is not a registered worktree on the target branch,
  so the validator refuses (this IS O10).
* ``test_real_resolver_falls_back_when_caller_has_no_kitty_specs`` (R chosen)
  -> ``TestUnvalidatedPointerNotAdopted::test_no_adoption_without_kitty_specs``:
  ``None``.
* ``test_real_resolver_rejects_conflicting_identities`` (conflict raised,
  hand-made pointer) ->
  ``TestUnvalidatedPointerNotAdopted::test_conflicting_id_via_unregistered_pointer_raises_mission_context_conflict``:
  ``ActionContextError("MISSION_CONTEXT_CONFLICT")`` -- the name states what
  it actually asserts (a conflict refusal), not "not adopted": WP02's
  ``adopt_owned_checkout`` resolves and compares both sides' identities
  BEFORE the worktree-registration check, so a conflicting id still surfaces
  here even for an unregistered pointer, unchanged from the old behaviour for
  this specific case.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import typer

from mission_runtime import ActionContextError, OwnedRefusalCode
from tests._owned_fixtures import mint_test_fact
from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable
from specify_cli.core.owned_mission import (
    FEATURE_CONTEXT_UNRESOLVED,
    LIFECYCLE_OWNED_TOPOLOGIES,
    MISSION_CONTEXT_CONFLICT,
)

# Re-exported (T039 step 1) so this file's real-git cases use the ONE
# canonical R/P/S fixture set instead of a hand-rolled equivalent.
# ``make_owned_checkouts`` is pulled in too: the ``owned_checkouts`` fixture
# depends on it BY NAME, and pytest resolves fixture dependencies only
# within the requesting module's own visible fixture set -- a plain
# re-export of ``owned_checkouts`` alone leaves that dependency unresolved
# outside ``tests/integration/``.
from tests.integration.conftest import (  # noqa: F401
    OwnedCheckouts,
    make_owned_checkouts,
    owned_checkouts,
    stale_root_copy,
)

__all__ = ["make_owned_checkouts", "owned_checkouts", "stale_root_copy"]


# ---------------------------------------------------------------------------
# TestContextHelpers (T042): the campsite extraction, behaviour-preserving.
# ---------------------------------------------------------------------------


class TestContextHelpers:
    pytestmark = [pytest.mark.unit, pytest.mark.fast]

    def test_validate_resolve_inputs_returns_root_and_handle(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.cli.commands.agent.context import _validate_resolve_inputs

        monkeypatch.setattr("specify_cli.cli.commands.agent.context.locate_project_root", lambda: tmp_path)
        repo_root, handle = _validate_resolve_inputs("implement", " demo-mission ")
        assert repo_root == tmp_path
        assert handle == "demo-mission"

    def test_validate_resolve_inputs_missing_project_root(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.cli.commands.agent.context import _validate_resolve_inputs

        monkeypatch.setattr("specify_cli.cli.commands.agent.context.locate_project_root", lambda: None)
        with pytest.raises(ActionContextError) as excinfo:
            _validate_resolve_inputs("implement", "demo-mission")
        assert excinfo.value.code == "PROJECT_ROOT_UNRESOLVED"

    def test_validate_resolve_inputs_invalid_action(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.cli.commands.agent.context import _validate_resolve_inputs

        monkeypatch.setattr("specify_cli.cli.commands.agent.context.locate_project_root", lambda: tmp_path)
        with pytest.raises(ActionContextError) as excinfo:
            _validate_resolve_inputs("not-a-real-action", "demo-mission")
        assert excinfo.value.code == "INVALID_ACTION"

    def test_validate_resolve_inputs_missing_mission(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.cli.commands.agent.context import _validate_resolve_inputs

        monkeypatch.setattr("specify_cli.cli.commands.agent.context.locate_project_root", lambda: tmp_path)
        with pytest.raises(ActionContextError) as excinfo:
            _validate_resolve_inputs("implement", None)
        assert excinfo.value.code == "MISSING_MISSION"

    def test_reanchor_planning_feature_dir_skips_non_planning_action(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent.context import _reanchor_planning_feature_dir

        payload: dict[str, object] = {"feature_dir": "/original"}
        _reanchor_planning_feature_dir(payload, "implement", tmp_path, "demo-mission")
        assert payload["feature_dir"] == "/original"

    def test_reanchor_planning_feature_dir_uses_primary_anchor(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.cli.commands.agent import context as context_module

        payload: dict[str, object] = {"feature_dir": "/original"}
        monkeypatch.setattr(
            "specify_cli.cli.commands.agent.mission_feature_resolution._primary_anchored_feature_dir",
            lambda repo_root, slug: tmp_path / "anchored",
        )
        context_module._reanchor_planning_feature_dir(payload, "tasks_outline", tmp_path, "demo-mission")
        assert payload["feature_dir"] == str(tmp_path / "anchored")

    def test_reanchor_planning_feature_dir_keeps_original_when_primary_anchor_is_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.cli.commands.agent import context as context_module

        payload: dict[str, object] = {"feature_dir": "/original"}
        monkeypatch.setattr(
            "specify_cli.cli.commands.agent.mission_feature_resolution._primary_anchored_feature_dir",
            lambda repo_root, slug: None,
        )
        context_module._reanchor_planning_feature_dir(payload, "plan", tmp_path, "demo-mission")
        assert payload["feature_dir"] == "/original"

    def test_render_context_human_prints_expected_lines(self, capsys: pytest.CaptureFixture[str]) -> None:
        from mission_runtime import MissionExecutionContext

        from specify_cli.cli.commands.agent.context import _render_context_human

        context = MissionExecutionContext(
            action="implement",
            mission_slug="demo-mission",
            feature_dir="/repo/kitty-specs/demo-mission",
            target_branch="main",
            detection_method="explicit",
            wp_id="WP01",
            lane="in_progress",
            workspace_path="/repo/.worktrees/demo-mission-lane-a",
            commands={"workflow": "spec-kitty agent action implement WP01"},
        )
        payload = context.to_dict()
        _render_context_human(context, payload)
        out = capsys.readouterr().out
        assert "Resolved implement context" in out
        assert "demo-mission" in out
        assert "WP01" in out
        assert "workflow" in out

    def test_emit_context_error_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands.agent.context import _emit_context_error

        with pytest.raises(typer.Exit) as excinfo:
            _emit_context_error(ActionContextError("MISSION_NOT_FOUND", "nope"), True)
        assert excinfo.value.exit_code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload == {"success": False, "error_code": "MISSION_NOT_FOUND", "error": "nope"}

    def test_emit_context_error_human(self, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands.agent.context import _emit_context_error

        with pytest.raises(typer.Exit) as excinfo:
            _emit_context_error(ActionContextError("MISSION_NOT_FOUND", "nope"), False)
        assert excinfo.value.exit_code == 1
        assert "nope" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _owned_checkout.py public surface (T039).
# ---------------------------------------------------------------------------


class TestOwnedCheckoutOption:
    pytestmark = [pytest.mark.unit, pytest.mark.fast]

    def test_owned_checkout_help_text_is_stable(self) -> None:
        from specify_cli.cli.commands._owned_checkout import OWNED_CHECKOUT_HELP

        assert "owned checkout" in OWNED_CHECKOUT_HELP
        assert "repository root checkout" in OWNED_CHECKOUT_HELP

    def test_owned_checkout_option_preserves_custom_help(self) -> None:
        from specify_cli.cli.commands._owned_checkout import owned_checkout_option

        option = owned_checkout_option(help="custom text")
        assert option.help == "custom text"
        # typer's pre-Annotated-style positional arg to `typer.Option(...)`
        # lands on `.default`, not `.param_decls`, when constructed this way
        # -- the SAME shape every existing `--owned-checkout` flag in this
        # codebase already uses (`accept.py`, `mission_finalize.py`, ...).
        assert option.default == "--owned-checkout"


# ---------------------------------------------------------------------------
# Real-git cases below (integration + git_repo, per T043 edge case 3: the old
# operation_context real-resolver rows were mislabelled unit/fast -- these
# build real worktrees through the canonical validator, so they belong in
# the integration lane).
# ---------------------------------------------------------------------------


class TestResolveOwnedOrAdopt:
    pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

    def test_explicit_valid_checkout_returns_fact(self, owned_checkouts: OwnedCheckouts, tmp_path: Path) -> None:
        from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt

        result = resolve_owned_or_adopt(
            owned_checkouts.repository_root,
            owned_checkouts.owned_root,
            owned_checkouts.mission_slug,
            cwd=tmp_path,
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
        )
        assert result is not None
        assert result.owned_root == owned_checkouts.owned_root.resolve()
        assert result.mission_dir == owned_checkouts.mission_dir.resolve()
        assert result.mission_slug == owned_checkouts.mission_slug

    def test_explicit_relative_checkout_resolved_against_cwd(self, owned_checkouts: OwnedCheckouts) -> None:
        from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt

        relative = Path(owned_checkouts.owned_root.name)
        result = resolve_owned_or_adopt(
            owned_checkouts.repository_root,
            relative,
            owned_checkouts.mission_slug,
            cwd=owned_checkouts.owned_root.parent,
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
        )
        assert result is not None
        assert result.owned_root == owned_checkouts.owned_root.resolve()

    def test_explicit_repository_root_raises_typed_refusal(self, owned_checkouts: OwnedCheckouts) -> None:
        from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt

        with pytest.raises(ActionContextError) as excinfo:
            resolve_owned_or_adopt(
                owned_checkouts.repository_root,
                owned_checkouts.repository_root,
                owned_checkouts.mission_slug,
                cwd=owned_checkouts.repository_root,
                allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
            )
        assert excinfo.value.code == OwnedRefusalCode.OWNED_CHECKOUT_IS_REPOSITORY_ROOT

    def test_flagless_adopts_validated_owned_checkout(self, owned_checkouts: OwnedCheckouts) -> None:
        from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt

        result = resolve_owned_or_adopt(
            owned_checkouts.repository_root,
            None,
            owned_checkouts.mission_slug,
            cwd=owned_checkouts.owned_root,
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
        )
        assert result is not None
        assert result.owned_root == owned_checkouts.owned_root.resolve()

    def test_flagless_from_repository_root_returns_none(self, owned_checkouts: OwnedCheckouts) -> None:
        from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt

        result = resolve_owned_or_adopt(
            owned_checkouts.repository_root,
            None,
            owned_checkouts.mission_slug,
            cwd=owned_checkouts.repository_root,
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
        )
        assert result is None

    def test_no_adoption_when_checkout_lacks_mission(self, owned_checkouts: OwnedCheckouts) -> None:
        """A VALID, registered linked checkout with no copy of M: adoption declines, falls back to R.

        T043 disposition row 2 (re-homed from operation_context's
        ``test_falls_back_to_primary_when_caller_has_no_mission``). Distinct
        from cwd being R itself: this uses a real registered worktree
        (``owned_checkouts.sibling``) that simply never received a copy of
        the mission, not the repository root checkout.
        """
        from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt

        result = resolve_owned_or_adopt(
            owned_checkouts.repository_root,
            None,
            owned_checkouts.mission_slug,
            cwd=owned_checkouts.sibling,
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
        )
        assert result is None

    def test_flagless_no_handle_returns_none(self, owned_checkouts: OwnedCheckouts) -> None:
        from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt

        result = resolve_owned_or_adopt(
            owned_checkouts.repository_root,
            None,
            None,
            cwd=owned_checkouts.owned_root,
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
        )
        assert result is None

    def test_flagless_conflicting_identity_propagates_mission_context_conflict(
        self,
        owned_checkouts: OwnedCheckouts,
        stale_root_copy: Any,
    ) -> None:
        from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt

        stale_root_copy(different_id=True)
        with pytest.raises(ActionContextError) as excinfo:
            resolve_owned_or_adopt(
                owned_checkouts.repository_root,
                None,
                owned_checkouts.mission_slug,
                cwd=owned_checkouts.owned_root,
                allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
            )
        assert excinfo.value.code == MISSION_CONTEXT_CONFLICT

    def test_explicit_path_fails_closed_on_worktree_registry_unavailable(
        self,
        owned_checkouts: OwnedCheckouts,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """WP02 review follow-up 1: the explicit ``--owned-checkout`` route fails closed.

        ``resolve_owned_mission`` -> ``_require_not_mission_worktree`` ->
        ``_is_coordination_worktree`` reading an unreadable git worktree
        registry must surface as a typed ``WORKTREE_REGISTRY_UNAVAILABLE``
        refusal, not swallow it or crash -- unlike the flagless adoption
        path, which is allowed to degrade that same exception to ``None``.
        """
        from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt
        from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable

        def _raise(*_args: Any, **_kwargs: Any) -> bool:
            raise WorktreeRegistryUnavailable(repo_root=owned_checkouts.repository_root, detail="synthetic registry read failure")

        monkeypatch.setattr("specify_cli.core.owned_mission._is_coordination_worktree", _raise)

        with pytest.raises(ActionContextError) as excinfo:
            resolve_owned_or_adopt(
                owned_checkouts.repository_root,
                owned_checkouts.owned_root,
                owned_checkouts.mission_slug,
                cwd=tmp_path,
                allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
            )
        assert excinfo.value.code == WorktreeRegistryUnavailable.error_code

    def test_explicit_path_forwards_target_override_matching_succeeds(self, owned_checkouts: OwnedCheckouts, tmp_path: Path) -> None:
        """Review cycle 1 finding 7: ``target_override`` reaches ``resolve_owned_mission`` on the explicit path."""
        from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt

        result = resolve_owned_or_adopt(
            owned_checkouts.repository_root,
            owned_checkouts.owned_root,
            owned_checkouts.mission_slug,
            cwd=tmp_path,
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
            target_override=owned_checkouts.target_branch,
        )
        assert result is not None
        assert result.write_branch == owned_checkouts.target_branch

    def test_explicit_path_forwards_target_override_mismatch_refuses(self, owned_checkouts: OwnedCheckouts, tmp_path: Path) -> None:
        """A mismatching ``target_override`` proves it reached the minter, not just accepted silently."""
        from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt

        with pytest.raises(ActionContextError) as excinfo:
            resolve_owned_or_adopt(
                owned_checkouts.repository_root,
                owned_checkouts.owned_root,
                owned_checkouts.mission_slug,
                cwd=tmp_path,
                allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
                target_override="codex/some-other-branch",
            )
        assert excinfo.value.code == OwnedRefusalCode.OWNED_BRANCH_REFUSED


class TestRefuseOwnedAction:
    pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

    def test_refuses_with_handle_after_validating_checkout(self, owned_checkouts: OwnedCheckouts) -> None:
        from specify_cli.cli.commands._owned_checkout import refuse_owned_action

        with pytest.raises(ActionContextError) as excinfo:
            refuse_owned_action(
                owned_checkouts.repository_root,
                owned_checkouts.owned_root,
                owned_checkouts.mission_slug,
                action="implement",
            )
        assert excinfo.value.code == OwnedRefusalCode.OWNED_ACTION_UNSUPPORTED
        assert "implement" in str(excinfo.value)
        assert "--owned-checkout" in str(excinfo.value)

    def test_refuses_invalid_checkout_before_the_action_refusal(self, owned_checkouts: OwnedCheckouts) -> None:
        from specify_cli.cli.commands._owned_checkout import refuse_owned_action

        with pytest.raises(ActionContextError) as excinfo:
            refuse_owned_action(
                owned_checkouts.repository_root,
                owned_checkouts.repository_root,
                owned_checkouts.mission_slug,
                action="implement",
            )
        assert excinfo.value.code == OwnedRefusalCode.OWNED_CHECKOUT_IS_REPOSITORY_ROOT

    def test_refuses_without_handle_via_create_root(self, owned_checkouts: OwnedCheckouts) -> None:
        from specify_cli.cli.commands._owned_checkout import refuse_owned_action

        with pytest.raises(ActionContextError) as excinfo:
            refuse_owned_action(
                owned_checkouts.repository_root,
                owned_checkouts.owned_root,
                None,
                action="review",
            )
        assert excinfo.value.code == OwnedRefusalCode.OWNED_ACTION_UNSUPPORTED

    def test_refuses_repository_root_without_handle(self, owned_checkouts: OwnedCheckouts) -> None:
        from specify_cli.cli.commands._owned_checkout import refuse_owned_action

        with pytest.raises(ActionContextError) as excinfo:
            refuse_owned_action(
                owned_checkouts.repository_root,
                owned_checkouts.repository_root,
                None,
                action="review",
            )
        assert excinfo.value.code == OwnedRefusalCode.OWNED_CHECKOUT_IS_REPOSITORY_ROOT


class TestEmitOwnedRefusal:
    pytestmark = [pytest.mark.unit, pytest.mark.fast]

    def test_json_mode_prints_envelope_and_exits(self, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands._owned_checkout import emit_owned_refusal, success_false_envelope

        with pytest.raises(typer.Exit) as excinfo:
            emit_owned_refusal(
                ActionContextError(OwnedRefusalCode.OWNED_BRANCH_REFUSED, "bad branch"),
                json_output=True,
                envelope=success_false_envelope,
            )
        assert excinfo.value.exit_code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload == {"success": False, "error_code": OwnedRefusalCode.OWNED_BRANCH_REFUSED, "error": "bad branch"}

    def test_human_mode_prints_on_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands._owned_checkout import emit_owned_refusal, success_false_envelope

        with pytest.raises(typer.Exit):
            emit_owned_refusal(
                ActionContextError(OwnedRefusalCode.OWNED_BRANCH_REFUSED, "bad branch"),
                json_output=False,
                envelope=success_false_envelope,
            )
        captured = capsys.readouterr()
        assert captured.out == ""
        assert OwnedRefusalCode.OWNED_BRANCH_REFUSED in captured.err

    def test_envelope_without_error_code_key_gets_one_added(self, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands._owned_checkout import emit_owned_refusal

        def _bare_envelope(code: str, message: str) -> dict[str, object]:
            return {"ok": False, "message": message}

        with pytest.raises(typer.Exit):
            emit_owned_refusal(
                ActionContextError(OwnedRefusalCode.OWNED_INDEX_REFUSED, "staged"),
                json_output=True,
                envelope=_bare_envelope,
            )
        payload = json.loads(capsys.readouterr().out)
        assert payload["error_code"] == OwnedRefusalCode.OWNED_INDEX_REFUSED

    @pytest.mark.parametrize(
        "code",
        [
            OwnedRefusalCode.WORKTREE_INVOCATION_REFUSED,
            OwnedRefusalCode.OWNERSHIP_NESTED,
            OwnedRefusalCode.OWNERSHIP_FOREIGN,
            OwnedRefusalCode.OWNERSHIP_BROKEN_POINTER,
            OwnedRefusalCode.OWNED_MISSION_PATH_REFUSED,
            OwnedRefusalCode.OWNED_TOPOLOGY_UNSUPPORTED,
            OwnedRefusalCode.OWNED_BRANCH_REFUSED,
            OwnedRefusalCode.OWNED_INDEX_REFUSED,
            OwnedRefusalCode.OWNED_CHECKOUT_IS_REPOSITORY_ROOT,
            OwnedRefusalCode.OWNED_CHECKOUT_IS_MISSION_WORKTREE,
            OwnedRefusalCode.OWNED_ACTION_UNSUPPORTED,
            OwnedRefusalCode.OWNED_REVIEW_BASE_UNAVAILABLE,
            OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE,
            OwnedRefusalCode.WORK_PACKAGE_UNRESOLVED,
            OwnedRefusalCode.OWNED_OPTION_UNSUPPORTED,
            OwnedRefusalCode.OWNED_INPUT_INVALID,
            WorktreeRegistryUnavailable.error_code,
            FEATURE_CONTEXT_UNRESOLVED,
            MISSION_CONTEXT_CONFLICT,
        ],
    )
    def test_every_registered_code_is_accepted(self, code: str, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands._owned_checkout import emit_owned_refusal, success_false_envelope

        with pytest.raises(typer.Exit):
            emit_owned_refusal(ActionContextError(code, "refused"), json_output=True, envelope=success_false_envelope)
        payload = json.loads(capsys.readouterr().out)
        assert payload["error_code"] == code

    def test_unregistered_code_raises_typed_error(self) -> None:
        """Review cycle 1 finding 11: an explicit typed raise, not an ``assert`` (stripped under ``python -O``)."""
        from specify_cli.cli.commands._owned_checkout import (
            UnregisteredOwnedRefusalCode,
            emit_owned_refusal,
            success_false_envelope,
        )

        with pytest.raises(UnregisteredOwnedRefusalCode):
            emit_owned_refusal(
                ActionContextError("SOME_UNRELATED_CODE", "not an owned refusal"),
                json_output=True,
                envelope=success_false_envelope,
            )


class TestEnvelopeBuilders:
    pytestmark = [pytest.mark.unit, pytest.mark.fast]

    def test_success_false_envelope(self) -> None:
        from specify_cli.cli.commands._owned_checkout import success_false_envelope

        assert success_false_envelope("CODE", "msg") == {"success": False, "error_code": "CODE", "error": "msg"}

    def test_json_error_envelope(self) -> None:
        from specify_cli.cli.commands._owned_checkout import json_error_envelope

        payload = json_error_envelope("CODE", "msg")
        assert payload["error_code"] == "CODE"
        assert payload["ok"] is False
        assert payload["error"] == {"code": "CODE", "message": "msg"}

    def test_result_error_envelope(self) -> None:
        from specify_cli.cli.commands._owned_checkout import result_error_envelope

        assert result_error_envelope("CODE", "msg") == {
            "result": "error",
            "phase_complete": False,
            "error_code": "CODE",
            "error": "msg",
        }


class TestStaleRepositoryRootCopy:
    pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

    def test_no_copy_returns_none(self, owned_checkouts: OwnedCheckouts) -> None:
        from specify_cli.cli.commands._owned_checkout import stale_repository_root_copy

        owned = mint_test_fact(
            repository_root=owned_checkouts.repository_root,
            owned_root=owned_checkouts.owned_root,
            mission_dir=owned_checkouts.mission_dir,
            mission_slug=owned_checkouts.mission_slug,
            write_branch=owned_checkouts.target_branch,
        )
        assert stale_repository_root_copy(owned) is None

    def test_same_id_copy_is_reported(self, owned_checkouts: OwnedCheckouts, stale_root_copy: Any) -> None:
        from specify_cli.cli.commands._owned_checkout import stale_repository_root_copy

        r_copy_dir = stale_root_copy()
        owned = mint_test_fact(
            repository_root=owned_checkouts.repository_root,
            owned_root=owned_checkouts.owned_root,
            mission_dir=owned_checkouts.mission_dir,
            mission_slug=owned_checkouts.mission_slug,
            write_branch=owned_checkouts.target_branch,
        )
        value = stale_repository_root_copy(owned)
        assert value == {"path": str(r_copy_dir), "mission_id": owned_checkouts.mission_id}

    def test_different_id_copy_returns_none(self, owned_checkouts: OwnedCheckouts, stale_root_copy: Any) -> None:
        from specify_cli.cli.commands._owned_checkout import stale_repository_root_copy

        stale_root_copy(different_id=True)
        owned = mint_test_fact(
            repository_root=owned_checkouts.repository_root,
            owned_root=owned_checkouts.owned_root,
            mission_dir=owned_checkouts.mission_dir,
            mission_slug=owned_checkouts.mission_slug,
            write_branch=owned_checkouts.target_branch,
        )
        assert stale_repository_root_copy(owned) is None

    def test_no_git_subprocess_calls(self, owned_checkouts: OwnedCheckouts, stale_root_copy: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        import subprocess

        from specify_cli.cli.commands._owned_checkout import stale_repository_root_copy

        stale_root_copy()
        owned = mint_test_fact(
            repository_root=owned_checkouts.repository_root,
            owned_root=owned_checkouts.owned_root,
            mission_dir=owned_checkouts.mission_dir,
            mission_slug=owned_checkouts.mission_slug,
            write_branch=owned_checkouts.target_branch,
        )

        def _forbidden(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("subprocess.run called")

        monkeypatch.setattr(subprocess, "run", _forbidden)
        stale_repository_root_copy(owned)  # must not raise

    def test_stale_copy_payload_appends_warning(self, owned_checkouts: OwnedCheckouts, stale_root_copy: Any) -> None:
        from specify_cli.cli.commands._owned_checkout import STALE_COPY_WARNING, stale_copy_payload

        r_copy_dir = stale_root_copy()
        owned = mint_test_fact(
            repository_root=owned_checkouts.repository_root,
            owned_root=owned_checkouts.owned_root,
            mission_dir=owned_checkouts.mission_dir,
            mission_slug=owned_checkouts.mission_slug,
            write_branch=owned_checkouts.target_branch,
        )
        warnings: list[str] = []
        payload = stale_copy_payload(owned, warnings=warnings)
        assert payload["stale_repository_root_copy"] == {"path": str(r_copy_dir), "mission_id": owned_checkouts.mission_id}
        assert len(warnings) == 1
        assert str(r_copy_dir) in warnings[0]
        assert warnings[0] == STALE_COPY_WARNING.format(slug=owned.mission_slug, path=str(r_copy_dir), owned_path=str(owned.owned_root))

    def test_stale_copy_payload_without_warnings_list(self, owned_checkouts: OwnedCheckouts) -> None:
        from specify_cli.cli.commands._owned_checkout import stale_copy_payload

        owned = mint_test_fact(
            repository_root=owned_checkouts.repository_root,
            owned_root=owned_checkouts.owned_root,
            mission_dir=owned_checkouts.mission_dir,
            mission_slug=owned_checkouts.mission_slug,
            write_branch=owned_checkouts.target_branch,
        )
        assert stale_copy_payload(owned) == {"stale_repository_root_copy": None}

    def test_echo_stale_copy_warning_prints_on_stderr_when_present(
        self,
        owned_checkouts: OwnedCheckouts,
        stale_root_copy: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from specify_cli.cli.commands._owned_checkout import echo_stale_copy_warning

        stale_root_copy()
        owned = mint_test_fact(
            repository_root=owned_checkouts.repository_root,
            owned_root=owned_checkouts.owned_root,
            mission_dir=owned_checkouts.mission_dir,
            mission_slug=owned_checkouts.mission_slug,
            write_branch=owned_checkouts.target_branch,
        )
        echo_stale_copy_warning(owned)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert owned_checkouts.mission_slug in captured.err

    def test_echo_stale_copy_warning_silent_when_absent(self, owned_checkouts: OwnedCheckouts, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands._owned_checkout import echo_stale_copy_warning

        owned = mint_test_fact(
            repository_root=owned_checkouts.repository_root,
            owned_root=owned_checkouts.owned_root,
            mission_dir=owned_checkouts.mission_dir,
            mission_slug=owned_checkouts.mission_slug,
            write_branch=owned_checkouts.target_branch,
        )
        echo_stale_copy_warning(owned)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


# ---------------------------------------------------------------------------
# T043: re-homed ``operation_context.py`` tests (disposition table in the
# module docstring above).
# ---------------------------------------------------------------------------


def _link_worktree(primary: Path, caller: Path) -> None:
    """Give ``caller`` a real linked-worktree ``.git`` pointer back to ``primary``.

    The precise shape of O10 (T043 edge case 1a): the pointer *looks* linked
    but is NOT a worktree registered to ``primary`` on any real branch, so
    the canonical validator (git worktree registry read) refuses it -- unlike
    the deleted ``operation_context._probe``, which trusted path shape alone.
    """
    gitdir = primary / ".git" / "worktrees" / "demo"
    gitdir.mkdir(parents=True)
    gitdir.joinpath("HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    caller.joinpath(".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")


class TestUnvalidatedPointerNotAdopted:
    pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

    def test_unvalidated_pointer_checkout_is_not_adopted(self, owned_checkouts: OwnedCheckouts, tmp_path: Path) -> None:
        import shutil

        from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt

        caller = tmp_path / "pointer_checkout"
        caller.mkdir()
        _link_worktree(owned_checkouts.repository_root, caller)
        shutil.copytree(owned_checkouts.mission_dir, caller / "kitty-specs" / owned_checkouts.mission_slug)

        result = resolve_owned_or_adopt(
            owned_checkouts.repository_root,
            None,
            owned_checkouts.mission_slug,
            cwd=caller,
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
        )
        assert result is None

    def test_no_adoption_without_kitty_specs(self, owned_checkouts: OwnedCheckouts, tmp_path: Path) -> None:
        from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt

        caller = tmp_path / "pointer_no_specs"
        caller.mkdir()
        _link_worktree(owned_checkouts.repository_root, caller)

        result = resolve_owned_or_adopt(
            owned_checkouts.repository_root,
            None,
            owned_checkouts.mission_slug,
            cwd=caller,
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
        )
        assert result is None

    def test_conflicting_id_via_unregistered_pointer_raises_mission_context_conflict(
        self, owned_checkouts: OwnedCheckouts, stale_root_copy: Any, tmp_path: Path
    ) -> None:
        """WP02's identity-conflict check runs BEFORE the worktree-registration check.

        Confirmed empirically (T043 edge case): ``adopt_owned_checkout``
        resolves both sides' identities and compares them first, so a
        conflicting id still raises ``MISSION_CONTEXT_CONFLICT`` even for an
        otherwise-unregistered pointer checkout; it never silently degrades
        to ``None`` for this case.
        """
        import shutil

        from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt

        stale_root_copy(different_id=True)
        caller = tmp_path / "pointer_conflicting"
        caller.mkdir()
        _link_worktree(owned_checkouts.repository_root, caller)
        shutil.copytree(owned_checkouts.mission_dir, caller / "kitty-specs" / owned_checkouts.mission_slug)

        with pytest.raises(ActionContextError) as excinfo:
            resolve_owned_or_adopt(
                owned_checkouts.repository_root,
                None,
                owned_checkouts.mission_slug,
                cwd=caller,
                allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
            )
        assert excinfo.value.code == MISSION_CONTEXT_CONFLICT
