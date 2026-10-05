"""Command-surface tests for the on-demand ``/spec-kitty.feedback`` command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from kernel.clock import UTC, datetime, timedelta
from specify_cli.distribution.profile import stock_distribution_profile
from specify_cli.feedback.endpoint import ENV_FEEDBACK_URL
from specify_cli.core.config import AGENT_COMMAND_CONFIG
from specify_cli.feedback.agent_protocol import agent_check
from specify_cli.feedback.models import SurveyTrigger
from specify_cli.feedback.preferences import load_preferences
from specify_cli.shims.registry import (
    CLI_DRIVEN_COMMANDS,
    CONSUMER_SKILLS,
    PROMPT_DRIVEN_COMMANDS,
)
from specify_cli.skills.command_installer import (
    CANONICAL_COMMANDS,
    PROMPT_BACKED_COMMANDS,
    _render_command_skill,
)
from specify_cli.skills._agent_roster import SUPPORTED_AGENTS as SKILL_AGENTS
from specify_cli.skills.render_versions import FIXTURE_COMMAND_RENDER_VERSION
from specify_cli.template.asset_generator import render_command_template

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
_TEMPLATE = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev" / "feedback" / "prompt.md"


@pytest.fixture
def endpoint_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        stock_distribution_profile,
    )
    return {ENV_FEEDBACK_URL: "https://feedback.example.test/v1"}


def _skill_body(agent: str) -> str:
    rendered: bytes = _render_command_skill(_REPO_ROOT, "feedback", agent, FIXTURE_COMMAND_RENDER_VERSION)
    return rendered.decode("utf-8")


def _slash_body(agent: str) -> str:
    config = AGENT_COMMAND_CONFIG[agent]
    with patch("specify_cli.template.asset_generator._get_cli_version", return_value=FIXTURE_COMMAND_RENDER_VERSION):
        rendered: str = render_command_template(
            template_path=_TEMPLATE,
            script_type="sh",
            agent_key=agent,
            arg_format=config["arg_format"],
            extension=config["ext"],
        )
    return rendered


def test_feedback_is_a_consumer_skill_in_exactly_one_classification() -> None:
    assert "feedback" in CONSUMER_SKILLS
    assert ("feedback" in PROMPT_DRIVEN_COMMANDS) != ("feedback" in CLI_DRIVEN_COMMANDS)
    assert "feedback" in PROMPT_BACKED_COMMANDS
    assert "feedback" in CANONICAL_COMMANDS


@pytest.mark.parametrize("agent", SKILL_AGENTS)
def test_feedback_skill_renders_for_every_skills_agent(agent: str) -> None:
    assert "name: spec-kitty.feedback" in _skill_body(agent)


@pytest.mark.parametrize("agent", sorted(AGENT_COMMAND_CONFIG))
def test_feedback_slash_command_renders_for_every_slash_agent(agent: str) -> None:
    assert "--agent-check --trigger on_demand" in _slash_body(agent)


def test_feedback_prompt_carries_the_on_demand_handshake() -> None:
    body = _skill_body("codex")
    assert "--agent-check --trigger on_demand" in body
    assert "--agent-submit --trigger on_demand" in body
    assert "--agent-choice skip" not in body
    assert "--agent-choice never" not in body
    assert "2000" not in body
    assert "Send feedback" in body
    for code in ("rating_out_of_range", "email_malformed", "comment_truncated", "no_endpoint", "not_sent"):
        assert code in body


def test_feedback_prompt_has_no_end_of_command_survey_block() -> None:
    assert "## Feedback Survey Check" not in _skill_body("codex")


def test_on_demand_check_prompts_even_after_weekly_offer_is_claimed(endpoint_env: dict[str, str]) -> None:
    first = agent_check(SurveyTrigger.PLANNING_COMPLETE, "cursor", now=_NOW, env=endpoint_env)
    assert first["action"] == "prompt"
    before = load_preferences()

    second = agent_check(SurveyTrigger.ON_DEMAND, "cursor", now=_NOW + timedelta(hours=1), env=endpoint_env)
    third = agent_check(SurveyTrigger.ON_DEMAND, "cursor", now=_NOW + timedelta(hours=2), env=endpoint_env)

    assert second["action"] == "prompt"
    assert third["action"] == "prompt"
    assert load_preferences() == before
