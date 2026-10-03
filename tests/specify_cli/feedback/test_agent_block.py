"""Unit + drift tests for ``specify_cli.feedback.agent_block``."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.feedback.agent_block import (
    PACK_BLOCK_BEGIN,
    PACK_BLOCK_END,
    TRIGGER_BY_COMMAND,
    append_feedback_survey_check,
    op_close_guidance_line,
    render_feedback_survey_block,
)
from specify_cli.feedback.models import SurveyTrigger

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PACK_PROMPTS = (
    _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev" / "tasks" / "prompt.md",
    _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev" / "tasks-finalize" / "prompt.md",
)

_CLI_PREFIX = "Run the command above with `SPEC_KITTY_NON_INTERACTIVE=1` so it never waits for terminal input."
_BLOCK_HEADING = "## Feedback Survey Check"


def _extract_pack_block(text: str) -> str:
    begin = text.find(PACK_BLOCK_BEGIN)
    end = text.find(PACK_BLOCK_END)
    assert begin != -1, f"missing {PACK_BLOCK_BEGIN}"
    assert end != -1, f"missing {PACK_BLOCK_END}"
    assert begin < end, "pack block markers out of order"
    inner = text[begin + len(PACK_BLOCK_BEGIN) : end]
    return inner.strip("\n")


def test_trigger_by_command_maps_planning_and_mission_end() -> None:
    assert TRIGGER_BY_COMMAND["tasks"] is SurveyTrigger.PLANNING_COMPLETE
    assert TRIGGER_BY_COMMAND["tasks-finalize"] is SurveyTrigger.PLANNING_COMPLETE
    assert TRIGGER_BY_COMMAND["consolidate"] is SurveyTrigger.MISSION_END
    assert "status" not in TRIGGER_BY_COMMAND
    assert "implement" not in TRIGGER_BY_COMMAND


def test_render_substitutes_trigger_value() -> None:
    block = render_feedback_survey_block(SurveyTrigger.PLANNING_COMPLETE, cli_driven=False)
    assert _BLOCK_HEADING in block
    assert "--trigger planning_complete" in block
    assert "<TRIGGER>" not in block
    assert "Send feedback?" in block
    assert _CLI_PREFIX not in block


def test_render_cli_driven_prefix() -> None:
    block = render_feedback_survey_block(SurveyTrigger.MISSION_END, cli_driven=True)
    assert block.startswith(_BLOCK_HEADING) or _CLI_PREFIX in block
    assert _CLI_PREFIX in block
    assert "--trigger mission_end" in block


def test_append_passthrough_for_non_trigger() -> None:
    body = "hello world"
    assert append_feedback_survey_check(body, "status", cli_driven=True) == body
    assert append_feedback_survey_check(body, "dashboard", cli_driven=True) == body


def test_append_adds_block_for_trigger() -> None:
    body = "Run the CLI.\n"
    out = append_feedback_survey_check(body, "consolidate", cli_driven=True)
    assert out.startswith(body.rstrip("\n"))
    assert _BLOCK_HEADING in out
    assert "--trigger mission_end" in out
    assert _CLI_PREFIX in out


def test_append_empty_body_returns_block_alone() -> None:
    out = append_feedback_survey_check("", "consolidate", cli_driven=True)
    assert out.startswith(_BLOCK_HEADING)
    assert "--trigger mission_end" in out


def test_append_is_idempotent() -> None:
    body = "Run the CLI.\n"
    once = append_feedback_survey_check(body, "tasks-finalize", cli_driven=True)
    twice = append_feedback_survey_check(once, "tasks-finalize", cli_driven=True)
    assert once == twice
    assert once.count(_BLOCK_HEADING) == 1


def test_op_close_guidance_line_points_at_agent_check() -> None:
    line = op_close_guidance_line()
    assert "spec-kitty feedback --agent-check" in line
    assert "--trigger op_close" in line
    assert "human" in line.lower()


def test_op_close_guidance_line_is_limited_to_done_or_failed() -> None:
    """FR-006 / R-09: the survey is never offered after an ``abandoned`` close."""
    line = op_close_guidance_line()
    assert "outcome `done` or `failed`" in line
    assert "never `abandoned`" in line


def test_op_close_guidance_line_names_the_consent_step() -> None:
    line = op_close_guidance_line()
    assert "Send feedback?" in line
    assert "--consent yes" in line
    assert "[" not in line, "square brackets would be eaten as rich markup by the capsule"


_SKILL_PATH = _REPO_ROOT / "src" / "charter" / "offering" / "skills" / "spec-kitty" / "SKILL.md"


def _skill_after_closing_section() -> str:
    text = _SKILL_PATH.read_text(encoding="utf-8")
    start = text.index("### After closing")
    end = text.index("\n### ", start + 1)
    return " ".join(text[start:end].split())


def test_skill_after_closing_is_limited_to_done_or_failed() -> None:
    section = _skill_after_closing_section()
    assert "outcome `done` or `failed`" in section
    assert "never `abandoned`" in section
    assert "--trigger op_close" in section


def test_skill_after_closing_names_the_consent_step() -> None:
    section = _skill_after_closing_section()
    assert "Send feedback?" in section
    assert "--consent yes" in section


@pytest.mark.parametrize("prompt_path", _PACK_PROMPTS, ids=["tasks", "tasks-finalize"])
def test_pack_prompt_block_matches_canonical_render(prompt_path: Path) -> None:
    text = prompt_path.read_text(encoding="utf-8")
    extracted = _extract_pack_block(text)
    assert extracted, "pack block markers present but content empty"
    expected = render_feedback_survey_block(SurveyTrigger.PLANNING_COMPLETE, cli_driven=False)
    assert extracted == expected.rstrip("\n")


def test_block_limits_itself_to_one_ask_per_session() -> None:
    block = render_feedback_survey_block(SurveyTrigger.PLANNING_COMPLETE, cli_driven=False)
    assert "once per session" in block


def test_block_never_exposes_an_endpoint_url() -> None:
    for trigger in SurveyTrigger:
        for cli_driven in (False, True):
            block = render_feedback_survey_block(trigger, cli_driven=cli_driven)
            assert "://" not in block
            assert "http" not in block.lower()
            assert "endpoint" not in block.lower()
    assert op_close_guidance_line().count("://") == 0


def test_block_flags_are_real_feedback_options() -> None:
    """Every ``--flag`` the block tells agents to run exists on ``spec-kitty feedback``."""
    import re

    import typer
    import typer.main

    from specify_cli.cli.commands.feedback import feedback

    app = typer.Typer()
    app.command(name="feedback")(feedback)
    known = {opt for param in typer.main.get_command(app).params for opt in (*param.opts, *param.secondary_opts)}
    block = render_feedback_survey_block(SurveyTrigger.MISSION_END, cli_driven=True)
    used = set(re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", block))
    expected = {"--agent-check", "--agent-submit", "--agent-choice", "--trigger", "--agent", "--rating", "--comment", "--email", "--consent", "--json"}
    assert expected <= used
    assert used <= known, f"block names flags missing from the CLI: {sorted(used - known)}"


_ALL_RENDERS = [
    pytest.param(trigger, cli_driven, id=f"{trigger.value}-{'cli' if cli_driven else 'prompt'}") for trigger in SurveyTrigger for cli_driven in (False, True)
]
_SINGLE_QUOTE_RULE = (
    "Pass `<text>` and `<address>` as single-quoted shell arguments, writing each `'` inside them as "
    "`'\\''`, and collapse newlines to spaces; never put the human's words in double quotes "
    "(`$(...)` and backticks would run)."
)


@pytest.mark.parametrize(("trigger", "cli_driven"), _ALL_RENDERS)
def test_block_never_shows_double_quoted_free_text_arguments(trigger: SurveyTrigger, cli_driven: bool) -> None:
    """B2: the human's words must never be shown inside a double-quoted shell string."""
    block = render_feedback_survey_block(trigger, cli_driven=cli_driven)
    assert '--comment "' not in block
    assert '--email "' not in block
    assert "--comment '<text>'" in block
    assert "--email '<address>'" in block
    assert _SINGLE_QUOTE_RULE in block


def test_tasks_prompt_places_survey_before_the_handoff_question() -> None:
    """N1: the survey must not compete with the Step 10 'Do NOT skip the question' handoff."""
    text = _PACK_PROMPTS[0].read_text(encoding="utf-8")
    assert text.index(PACK_BLOCK_END) < text.index("### Step 10: Implementation Handoff Offer")
    step_10 = text[text.index("### Step 10: Implementation Handoff Offer") :]
    assert "after the Feedback Survey Check above is finished or skipped" in step_10
