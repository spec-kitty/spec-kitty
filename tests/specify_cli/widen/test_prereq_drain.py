"""Drain gates the decision-widen prerequisite probe (FR-004/G2).

``check_prereqs`` is an automatic hosted call run at interview startup; under
drain-off it must return an all-``False`` :class:`PrereqState` and make no
call against the injected ``SaasClient`` at all.

Also covers the three interview call sites (``cli/commands/charter/
interview.py``, ``missions/plan/specify_interview.py``,
``missions/plan/plan_interview.py``): drain must gate the widen-prereq probe
at interview startup BEFORE any credential-store read or OAuth refresh, not
just before ``check_prereqs`` itself. Each of those call sites calls
``SaasClient.from_env(repo_root)`` and (best-effort)
``load_auth_context(repo_root)`` before ``check_prereqs`` -- both of those
calls read the credential store and ``load_auth_context`` may refresh an
expired OAuth session over the network. Under drain-off none of that may
happen; ``[w]`` stays silently suppressed, exactly like the all-prereqs-
absent UX (no error banner, no misleading message).

Drain-on baseline (unchanged behaviour) is already covered by the existing
``test_charter_prereq_suppression.py`` / ``test_specify_widen.py`` /
``test_plan_widen.py`` suites, which patch and assert ``SaasClient.from_env``
IS called under the (drain-on, root-fixture) default posture -- those keep
passing unmodified.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from charter.activation.interview import MINIMAL_QUESTION_ORDER
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app as charter_app
from specify_cli.cli.commands.lifecycle import PLAN_WIDEN_QUESTIONS, SPECIFY_WIDEN_QUESTIONS, plan, specify
from specify_cli.widen.models import PrereqState
from specify_cli.widen.prereq import check_prereqs

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


def _make_client(token: str = "tok", integrations: list[str] | None = None, health: bool = True) -> MagicMock:
    client = MagicMock()
    client.has_token = bool(token)
    client.get_team_integrations.return_value = integrations if integrations is not None else []
    client.health_probe.return_value = health
    return client


class TestCheckPrereqsDrainGate:
    def test_returns_all_false_and_makes_no_call_under_drain_off(self, drain_off: None) -> None:
        client = _make_client(token="valid-token", integrations=["slack"], health=True)

        state = check_prereqs(client, "my-team")

        assert state == PrereqState(teamspace_ok=False, slack_ok=False, saas_reachable=False)
        client.get_team_integrations.assert_not_called()
        client.health_probe.assert_not_called()
        # has_token is a property read, not a method call; confirming zero
        # SaasClient *calls* is the meaningful assertion here (C-007's
        # never-raises contract also stays honest under drain-off).

    def test_unaffected_under_drain_on(self) -> None:
        """Baseline regression guard: without drain_off, behaviour is
        exactly what test_prereq.py already pins."""
        client = _make_client(token="valid-token", integrations=["slack"], health=True)

        state = check_prereqs(client, "my-team")

        assert state.all_satisfied is True


# ---------------------------------------------------------------------------
# charter interview
# ---------------------------------------------------------------------------

_CHARTER_MISSION_SLUG = "test-prereq-drain-charter"
_CHARTER_MISSION_ID = "01KWP03PREREQDRAINCHARTER01"
_CHARTER_N_QUESTIONS = len(MINIMAL_QUESTION_ORDER)
_CHARTER_META_PROMPTS = 3


def _setup_charter_repo(tmp_path: Path) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "charter" / "interview").mkdir(parents=True, exist_ok=True)
    mission_dir = tmp_path / "kitty-specs" / _CHARTER_MISSION_SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": _CHARTER_MISSION_ID, "mission_slug": _CHARTER_MISSION_SLUG}),
        encoding="utf-8",
    )
    return tmp_path


def _charter_inputs() -> str:
    return "\n".join([""] * _CHARTER_N_QUESTIONS + [""] * _CHARTER_META_PROMPTS) + "\n"


class TestCharterInterviewPrereqDrainGate:
    def test_drain_off_never_touches_credentials_or_auth(self, tmp_path: Path, drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
        _setup_charter_repo(tmp_path)
        old_cwd = os.getcwd()
        from_env = MagicMock(name="SaasClient.from_env")
        load_auth_context = MagicMock(name="load_auth_context")
        check_prereqs_mock = MagicMock(name="check_prereqs")
        try:
            os.chdir(tmp_path)
            with (
                patch("specify_cli.saas_client.client.SaasClient.from_env", from_env),
                patch("specify_cli.saas_client.auth.load_auth_context", load_auth_context),
                patch("specify_cli.widen.check_prereqs", check_prereqs_mock),
            ):
                result = runner.invoke(
                    charter_app,
                    ["interview", "--profile", "minimal", "--mission-slug", _CHARTER_MISSION_SLUG],
                    input=_charter_inputs(),
                    catch_exceptions=False,
                )
        finally:
            os.chdir(old_cwd)
        assert result.exit_code == 0, result.output
        assert "[w]iden" not in result.output
        from_env.assert_not_called()
        load_auth_context.assert_not_called()
        check_prereqs_mock.assert_not_called()


# ---------------------------------------------------------------------------
# specify interview (missions/plan/specify_interview.py)
# ---------------------------------------------------------------------------

_SPECIFY_MISSION_SLUG = "test-prereq-drain-specify"
_SPECIFY_MISSION_ID = "01KWP03PREREQDRAINSPECIFY01"
_SPECIFY_N_QUESTIONS = len(SPECIFY_WIDEN_QUESTIONS)

_specify_app = typer.Typer()
_specify_app.command()(specify)


def _setup_specify_repo(tmp_path: Path) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    (kittify / "config.yaml").write_text(
        "version: 1\nproject:\n  uuid: 00000000-0000-0000-0000-000000000003\n",
        encoding="utf-8",
    )
    (tmp_path / "kitty-specs").mkdir(parents=True, exist_ok=True)
    mission_dir = tmp_path / "kitty-specs" / _SPECIFY_MISSION_SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": _SPECIFY_MISSION_ID, "mission_slug": _SPECIFY_MISSION_SLUG}),
        encoding="utf-8",
    )
    return tmp_path


class TestSpecifyInterviewPrereqDrainGate:
    def test_drain_off_never_touches_credentials_or_auth(self, tmp_path: Path, drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPEC_KITTY_FORCE_INTERACTIVE", "1")
        _setup_specify_repo(tmp_path)
        inputs = "\n".join([""] * _SPECIFY_N_QUESTIONS) + "\n"
        old_cwd = os.getcwd()
        from_env = MagicMock(name="SaasClient.from_env")
        load_auth_context = MagicMock(name="load_auth_context")
        check_prereqs_mock = MagicMock(name="check_prereqs")
        try:
            os.chdir(tmp_path)
            with (
                patch("specify_cli.cli.commands.lifecycle.agent_feature.create_mission", return_value=None),
                patch("specify_cli.cli.commands.lifecycle.locate_project_root", return_value=tmp_path),
                patch("specify_cli.saas_client.client.SaasClient.from_env", from_env),
                patch("specify_cli.saas_client.auth.load_auth_context", load_auth_context),
                patch("specify_cli.widen.check_prereqs", check_prereqs_mock),
            ):
                result = runner.invoke(
                    _specify_app,
                    [_SPECIFY_MISSION_SLUG],
                    input=inputs,
                    catch_exceptions=False,
                )
        finally:
            os.chdir(old_cwd)
        assert result.exit_code == 0, result.output
        assert "[w]iden" not in result.output
        from_env.assert_not_called()
        load_auth_context.assert_not_called()
        check_prereqs_mock.assert_not_called()


# ---------------------------------------------------------------------------
# plan interview (missions/plan/plan_interview.py)
# ---------------------------------------------------------------------------

_PLAN_MISSION_SLUG = "test-prereq-drain-plan"
_PLAN_MISSION_ID = "01KWP03PREREQDRAINPLAN00001"
_PLAN_N_QUESTIONS = len(PLAN_WIDEN_QUESTIONS)

_plan_app = typer.Typer()
_plan_app.command()(plan)


def _setup_plan_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text("agents:\n  available: [claude]\n", encoding="utf-8")
    mission_dir = tmp_path / "kitty-specs" / _PLAN_MISSION_SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": _PLAN_MISSION_ID, "mission_slug": _PLAN_MISSION_SLUG}),
        encoding="utf-8",
    )
    return tmp_path


class TestPlanInterviewPrereqDrainGate:
    def test_drain_off_never_touches_credentials_or_auth(self, tmp_path: Path, drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPEC_KITTY_FORCE_INTERACTIVE", "1")
        _setup_plan_repo(tmp_path)
        inputs = "\n".join([""] * _PLAN_N_QUESTIONS) + "\n"
        old_cwd = os.getcwd()
        from_env = MagicMock(name="SaasClient.from_env")
        load_auth_context = MagicMock(name="load_auth_context")
        check_prereqs_mock = MagicMock(name="check_prereqs")
        try:
            os.chdir(tmp_path)
            with (
                patch("specify_cli.cli.commands.lifecycle.agent_feature.setup_plan", return_value=None),
                patch("specify_cli.cli.commands.lifecycle.locate_project_root", return_value=tmp_path),
                patch("specify_cli.saas_client.client.SaasClient.from_env", from_env),
                patch("specify_cli.saas_client.auth.load_auth_context", load_auth_context),
                patch("specify_cli.widen.check_prereqs", check_prereqs_mock),
            ):
                result = runner.invoke(
                    _plan_app,
                    ["--mission", _PLAN_MISSION_SLUG],
                    input=inputs,
                    catch_exceptions=False,
                )
        finally:
            os.chdir(old_cwd)
        assert result.exit_code == 0, result.output
        assert "[w]iden" not in result.output
        from_env.assert_not_called()
        load_auth_context.assert_not_called()
        check_prereqs_mock.assert_not_called()
