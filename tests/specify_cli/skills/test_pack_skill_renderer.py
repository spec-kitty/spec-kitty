"""Pack-skill renderer (mission pack-skills-kind-01M43419, WP04 T016)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from charter.activation.skill_preparation import PreparedSkill
from charter.offering.pack_skills.models import PackSkill, SkillExpansion
from specify_cli.skills.command_installer import CANONICAL_COMMANDS
from specify_cli.skills.command_renderer import ensure_skill_frontmatter
from specify_cli.skills.pack_skill_renderer import PackSkillRenderError, _wrapper_instruction, render_pack_skill

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _prepared(
    *,
    form: str = "prompt",
    body: str | None = "Do the thing: $ARGUMENTS\n",
    target: str = "builtin:spec-kitty.review",
    args: str = "",
    requires: tuple[str, ...] = (),
    extra: dict[str, object] | None = None,
) -> PreparedSkill:
    record: dict[str, object] = {
        "schema_version": "1.0",
        "id": "deploy-helper",
        "title": "Deploy helper",
        "description": "Ships   the  release.",
        "form": form,
        **(extra or {}),
    }
    if form == "prompt":
        record["body_path"] = "deploy-helper.skill.md"
    else:
        record["expands_to"] = {"target": target, "args": args}
    skill = PackSkill.model_validate(record)
    return PreparedSkill(
        id="deploy-helper",
        tier="org",
        rendered_name="acme-deploy-helper",
        form=form,
        body=body if form == "prompt" else None,
        expansion=skill.expands_to,
        requires=requires,
        source_path=Path("/pack/skills/deploy-helper.skill.yaml"),
        source_hash="0" * 64,
        skill=skill,
    )


def _frontmatter(text: str) -> dict[str, object]:
    assert text.startswith("---\n")
    loaded = yaml.safe_load(text.split("---\n")[1])
    assert isinstance(loaded, dict)
    return loaded


def test_prompt_skill_renders_frontmatter_preamble_and_body() -> None:
    text = render_pack_skill(_prepared(requires=("procedure:release-proc", "directive:dir-d")))

    meta = _frontmatter(text)
    assert meta == {"name": "acme-deploy-helper", "description": "Ships the release.", "user-invocable": True}
    assert "- `spec-kitty charter context --include procedure:release-proc`" in text
    assert "- `spec-kitty charter context --include directive:dir-d`" in text
    assert "## Instructions\n\nDo the thing: $ARGUMENTS" in text
    assert text.index("Governing context") < text.index("## Instructions")
    assert text.endswith("\n") and not text.endswith("\n\n")


def test_rendered_frontmatter_is_already_complete_for_the_installer() -> None:
    text = render_pack_skill(_prepared())
    assert ensure_skill_frontmatter(text, "acme-deploy-helper") == text


def test_no_requires_means_no_preamble_section() -> None:
    assert "Governing context" not in render_pack_skill(_prepared())


def test_never_emits_allowed_tools_or_bindings() -> None:
    text = render_pack_skill(_prepared(requires=("procedure:p",), extra={"tools": ["Bash", "Edit"]}))
    assert "allowed-tools" not in text and "allowed_tools" not in text
    assert "Bash" not in text and "Edit" not in text


def test_substance_stays_in_the_procedure_not_in_the_skill() -> None:
    text = render_pack_skill(_prepared(requires=("procedure:release-proc",)))
    assert "Substance carried by a procedure." not in text


def test_invocation_flags_are_rendered() -> None:
    quiet = render_pack_skill(_prepared(extra={"invocation": {"user_invocable": False}}))
    assert _frontmatter(quiet)["user-invocable"] is False
    assert "disable-model-invocation" not in quiet

    side_effects = render_pack_skill(_prepared(extra={"invocation": {"side_effects": ["pushes"]}}))
    meta = _frontmatter(side_effects)
    assert meta["disable-model-invocation"] is True and meta["user-invocable"] is True


def test_triggers_extend_the_description_and_special_characters_stay_valid_yaml() -> None:
    text = render_pack_skill(_prepared(extra={"triggers": ["ship it", 'say "go"'], "description": "Colon: and # hash"}))
    meta = _frontmatter(text)
    assert meta["description"] == 'Colon: and # hash Triggers: ship it, say "go".'


def test_parameters_are_listed() -> None:
    text = render_pack_skill(
        _prepared(
            extra={
                "parameters": [
                    {"name": "env", "required": True, "description": "Target"},
                    {"name": "dry", "default": "yes"},
                ]
            }
        )
    )
    assert "- `env` (required): Target" in text
    assert "- `dry` (optional, default `yes`)" in text


def test_prompt_body_newlines_are_normalised_and_an_empty_body_is_refused() -> None:
    assert "line one\nline two" in render_pack_skill(_prepared(body="\r\nline one\r\nline two\r\n"))
    with pytest.raises(PackSkillRenderError, match="empty body"):
        render_pack_skill(_prepared(body="  \n"))
    with pytest.raises(PackSkillRenderError, match="empty body"):
        render_pack_skill(_prepared(body=None))


@pytest.mark.parametrize("command", CANONICAL_COMMANDS)
def test_wrapper_builtin_targets_every_canonical_command(command: str) -> None:
    text = render_pack_skill(_prepared(form="wrapper", target=f"builtin:spec-kitty.{command}", args="--flag"))
    assert f"Invoke the `spec-kitty.{command}` command skill. Pass these arguments: `--flag`." in text


def test_wrapper_without_args_has_no_argument_sentence() -> None:
    text = render_pack_skill(_prepared(form="wrapper"))
    assert "Invoke the `spec-kitty.review` command skill.\n" in text and "Pass these" not in text


@pytest.mark.parametrize("target", ["builtin:spec-kitty.nope", "builtin:review", "builtin:other.review", "builtin:spec-kitty."])
def test_wrapper_unknown_builtin_target_is_refused(target: str) -> None:
    with pytest.raises(PackSkillRenderError, match="unknown built-in command"):
        render_pack_skill(_prepared(form="wrapper", target=target))


def test_wrapper_cli_target_renders_the_argv() -> None:
    text = render_pack_skill(_prepared(form="wrapper", target="cli:spec-kitty status --json", args="--mission x"))
    assert "```bash\nspec-kitty status --json --mission x\n```" in text
    assert "```bash\nspec-kitty status\n```" in render_pack_skill(_prepared(form="wrapper", target="cli:spec-kitty status"))


def test_wrapper_without_expansion_and_unsupported_targets_are_refused() -> None:
    broken = _prepared(form="wrapper")
    with pytest.raises(PackSkillRenderError, match="no expansion"):
        render_pack_skill(PreparedSkill(**{**broken.__dict__, "expansion": None}))
    with pytest.raises(PackSkillRenderError, match="unsupported target"):
        _wrapper_instruction("x", "http:evil", "")
    # The model itself already refuses an unsupported scheme.
    with pytest.raises(ValueError, match="must start with"):
        SkillExpansion(target="http:evil")
