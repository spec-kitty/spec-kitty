"""Surface presence/absence tests for the Feedback Survey Check block.

Exercises production render paths (skills installer, shims, runtime prompt
builder, slash-command asset generator) with positive and negative controls.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from specify_cli.cli.commands.dispatch import render_open_hint_task_execution
from specify_cli.core.config import AGENT_COMMAND_CONFIG
from specify_cli.feedback.agent_block import op_close_guidance_line
from specify_cli.invocation.executor import InvocationPayload
from specify_cli.skills.command_installer import _render_command_skill
from specify_cli.skills.render_versions import FIXTURE_COMMAND_RENDER_VERSION
from specify_cli.shims.generator import generate_shim_content_for_agent
from specify_cli.template.asset_generator import render_command_template

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TEMPLATES_DIR = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev"
_BLOCK = "## Feedback Survey Check"
_TRIGGER_PLANNING = "--trigger planning_complete"
_TRIGGER_MISSION = "--trigger mission_end"


def _skill_body(command: str) -> str:
    return _render_command_skill(_REPO_ROOT, command, "codex", FIXTURE_COMMAND_RENDER_VERSION).decode("utf-8")


@pytest.mark.parametrize(
    ("command", "trigger_flag"),
    [
        ("tasks", _TRIGGER_PLANNING),
        ("tasks-finalize", _TRIGGER_PLANNING),
        ("consolidate", _TRIGGER_MISSION),
    ],
)
def test_skills_installer_includes_block_for_triggers(command: str, trigger_flag: str) -> None:
    body = _skill_body(command)
    assert _BLOCK in body
    assert trigger_flag in body


@pytest.mark.parametrize("command", ["status", "implement", "review"])
def test_skills_installer_omits_block_for_non_triggers(command: str) -> None:
    body = _skill_body(command)
    assert _BLOCK not in body


@pytest.mark.parametrize(
    ("command", "agent", "trigger_flag"),
    [
        ("consolidate", "claude", _TRIGGER_MISSION),
        ("tasks-finalize", "claude", _TRIGGER_PLANNING),
        ("consolidate", "gemini", _TRIGGER_MISSION),
        ("tasks-finalize", "gemini", _TRIGGER_PLANNING),
    ],
)
def test_shims_include_block_for_triggers(command: str, agent: str, trigger_flag: str) -> None:
    content = generate_shim_content_for_agent(command, agent)
    assert _BLOCK in content
    assert trigger_flag in content
    assert "SPEC_KITTY_NON_INTERACTIVE=1" in content


@pytest.mark.parametrize("agent", ["gemini", "qwen"])
def test_toml_shims_round_trip_the_block_byte_exact(agent: str) -> None:
    """The block's ``'\\''`` quoting rule must survive TOML escaping unchanged."""
    import tomllib

    from specify_cli.feedback.agent_block import render_feedback_survey_block
    from specify_cli.feedback.models import SurveyTrigger

    parsed = tomllib.loads(generate_shim_content_for_agent("tasks-finalize", agent))
    expected = render_feedback_survey_block(SurveyTrigger.PLANNING_COMPLETE, cli_driven=True)
    assert expected.rstrip("\n") in parsed["prompt"]
    assert "`'\\''`" in parsed["prompt"]


def test_shims_omit_block_for_status() -> None:
    assert _BLOCK not in generate_shim_content_for_agent("status", "claude")
    assert _BLOCK not in generate_shim_content_for_agent("status", "gemini")


def test_runtime_build_prompt_includes_block_for_tasks(tmp_path: Path) -> None:
    from runtime.next.prompt_builder import build_prompt

    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# demo\n", encoding="utf-8")

    text, _ = build_prompt(
        "tasks",
        feature_dir,
        "demo-mission",
        None,
        "claude",
        _REPO_ROOT,
        "software-dev",
    )
    assert _BLOCK in text
    assert _TRIGGER_PLANNING in text

    plan_text, _ = build_prompt(
        "plan",
        feature_dir,
        "demo-mission",
        None,
        "claude",
        _REPO_ROOT,
        "software-dev",
    )
    assert _BLOCK not in plan_text


def test_asset_generator_includes_block_for_tasks_finalize() -> None:
    template_path = _TEMPLATES_DIR / "tasks-finalize" / "prompt.md"
    assert template_path.is_file()
    config = AGENT_COMMAND_CONFIG["claude"]
    with patch(
        "specify_cli.template.asset_generator._get_cli_version",
        return_value=FIXTURE_COMMAND_RENDER_VERSION,
    ):
        rendered = render_command_template(
            template_path=template_path,
            script_type="sh",
            agent_key="claude",
            arg_format=config["arg_format"],
            extension=config["ext"],
        )
    assert _BLOCK in rendered
    assert _TRIGGER_PLANNING in rendered


def _open_op_payload() -> InvocationPayload:
    return InvocationPayload(
        invocation_id="01TESTINVOCATIONID00000001",
        profile_id="implementer-ivan",
        profile_friendly_name="Implementer Ivan",
        action="implement",
        governance_context_text="ctx",
        governance_context_hash="abc",
        governance_context_available=True,
        router_confidence="high",
        glossary_observations=None,
        mode_of_work="task_execution",
        recommendation=None,
        empty_charter_fallback=False,
        alternatives=[],
    )


def test_dispatch_json_payload_keys_unchanged() -> None:
    """Human-only op_close guidance must not alter the JSON contract."""
    payload = _open_op_payload()
    keys = set(payload.to_dict())
    assert "feedback" not in keys
    assert "op_close" not in keys
    assert "close_contract" in keys
    assert "status" in keys
    assert "invocation_id" in keys


def test_op_close_guidance_line_usable_by_dispatch() -> None:
    line = op_close_guidance_line()
    assert "op_close" in line
    assert "feedback --agent-check" in line


def test_dispatch_capsule_prints_op_close_guidance_after_close_hint() -> None:
    """The real capsule renderer emits the op_close line right after the close hint."""
    capture = Console(record=True, width=400, force_terminal=False)
    with patch("specify_cli.cli.commands.dispatch.console", capture):
        render_open_hint_task_execution(_open_op_payload())
    lines = [line.strip() for line in capture.export_text().splitlines() if line.strip()]
    hint_idx = next(i for i, line in enumerate(lines) if "Unclosed Ops are reported" in line)
    assert lines[hint_idx + 1] == op_close_guidance_line()
    assert "--trigger op_close" in lines[hint_idx + 1]
    assert hint_idx + 1 == len(lines) - 1, "op_close guidance must be the final capsule line"
