"""Command-skill naming authority (#6475, FR-001/FR-002/FR-003)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from specify_cli.skills import command_skill_names as names
from specify_cli.skills.command_installer import CANONICAL_COMMANDS
from specify_cli.skills.command_skill_names import (
    CommandSkillNameCollisionError,
    assert_unique_command_skill_names,
    command_skill_name,
    command_skill_rel_path,
    legacy_command_skill_name,
    legacy_command_skill_names,
    legacy_command_skill_rel_path,
    parse_command_skill_rel_path,
    parse_legacy_command_skill_rel_path,
    rewrite_command_invocations,
    skill_invocation_token,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: The Agent Skills ``name`` grammar (lowercase alphanumerics and single hyphens, ≤64).
_SPEC_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def test_names_and_paths() -> None:
    assert command_skill_name("plan") == "spec-kitty-plan"
    assert legacy_command_skill_name("plan") == "spec-kitty.plan"
    assert command_skill_rel_path("tasks-outline") == ".agents/skills/spec-kitty-tasks-outline/SKILL.md"
    assert legacy_command_skill_rel_path("plan") == ".agents/skills/spec-kitty.plan/SKILL.md"
    assert legacy_command_skill_names(("plan", "review")) == frozenset({"spec-kitty.plan", "spec-kitty.review"})


@pytest.mark.parametrize("command", CANONICAL_COMMANDS)
def test_every_canonical_name_satisfies_the_agent_skills_grammar(command: str) -> None:
    name = command_skill_name(command)
    assert _SPEC_NAME.match(name) and len(name) <= 64
    assert command_skill_rel_path(command).split("/")[-2] == name


def test_parse_canonical_path_is_exact_against_the_explicit_set() -> None:
    commands = ("implement", "review", "tasks", "tasks-outline")
    assert parse_command_skill_rel_path(".agents/skills/spec-kitty-implement/SKILL.md", commands) == "implement"
    assert parse_command_skill_rel_path(".agents/skills/spec-kitty-tasks-outline/SKILL.md", commands) == "tasks-outline"
    # A shipped charter skill shares the prefix but is not a command.
    assert parse_command_skill_rel_path(".agents/skills/spec-kitty-implement-review/SKILL.md", commands) is None
    # The legacy form is only accepted by the legacy parser.
    assert parse_command_skill_rel_path(".agents/skills/spec-kitty.implement/SKILL.md", commands) is None
    assert parse_command_skill_rel_path(".agents/skills/spec-kitty-implement/other.md", commands) is None
    assert parse_command_skill_rel_path(".claude/skills/spec-kitty-implement/SKILL.md", commands) is None


def test_parse_legacy_path() -> None:
    commands = ("plan",)
    assert parse_legacy_command_skill_rel_path(".agents/skills/spec-kitty.plan/SKILL.md", commands) == "plan"
    assert parse_legacy_command_skill_rel_path(".agents/skills/spec-kitty-plan/SKILL.md", commands) is None
    assert parse_legacy_command_skill_rel_path(".agents/skills/spec-kitty.advise/SKILL.md", commands) is None


def test_uniqueness_passes_for_distinct_unreserved_names() -> None:
    assert_unique_command_skill_names(("plan", "review"), reserved={"spec-kitty-implement-review"})


def test_uniqueness_refuses_a_reserved_collision() -> None:
    with pytest.raises(CommandSkillNameCollisionError, match="spec-kitty-implement-review"):
        assert_unique_command_skill_names(("plan", "implement-review"), reserved={"spec-kitty-implement-review"})


def test_uniqueness_refuses_two_commands_on_one_name() -> None:
    with pytest.raises(CommandSkillNameCollisionError, match="both map"):
        assert_unique_command_skill_names(("plan", "plan"), reserved=())


def _reserved_skill_names() -> set[str]:
    """Shipped charter skills + built-in pack skills + retired names (plan A-m1)."""
    from charter.offering.pack_skills.validation import BUILT_IN, rendered_name
    from specify_cli.skills.catalog import resolve_builtin_skill_catalog
    from specify_cli.skills.retired import RETIRED_CANONICAL_SKILL_NAMES, RETIRED_STANDALONE_SKILL_NAMES

    registry = resolve_builtin_skill_catalog(local_repo=Path(__file__).resolve().parents[3])
    assert registry is not None, "shipped skill catalog must resolve in a source checkout"
    shipped = {skill.name for skill in registry.discover_skills()}
    assert "spec-kitty-implement-review" in shipped, "catalog resolution lost the shipped charter skills"
    built_in_pack_root = Path(__file__).resolve().parents[3] / "packs" / "built-in" / "skills"
    built_in_pack = {rendered_name(path.name.removesuffix(".skill.yaml"), None) for path in built_in_pack_root.glob("*.skill.yaml")}
    assert BUILT_IN  # the tier exists; built-in pack skills render under their bare id
    return shipped | built_in_pack | set(RETIRED_CANONICAL_SKILL_NAMES) | set(RETIRED_STANDALONE_SKILL_NAMES)


def test_canonical_command_skill_names_are_unique_against_every_reserved_name() -> None:
    """FR-003: build-time gate over the real shipped set."""
    assert_unique_command_skill_names(CANONICAL_COMMANDS, _reserved_skill_names())


def test_uniqueness_gate_detects_a_real_collision() -> None:
    """Self-mutation: a fake ``implement-review`` command collides with the shipped charter skill."""
    with pytest.raises(CommandSkillNameCollisionError):
        assert_unique_command_skill_names((*CANONICAL_COMMANDS, "implement-review"), _reserved_skill_names())


def test_legacy_names_are_not_in_the_retired_sets() -> None:
    """Plan A-M6: dotted names live here, never in ``skills/retired.py`` (would re-arm retire paths)."""
    from specify_cli.skills.retired import RETIRED_CANONICAL_SKILL_NAMES

    assert not legacy_command_skill_names(CANONICAL_COMMANDS) & RETIRED_CANONICAL_SKILL_NAMES


_COMMANDS = ("tasks", "tasks-outline", "plan", "review", "analyze", "implement")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Run /spec-kitty.plan now", "Run /spec-kitty-plan now"),
        ("Run `$spec-kitty.plan`", "Run `$spec-kitty-plan`"),
        ("Run /skill:spec-kitty.plan", "Run /skill:spec-kitty-plan"),
        ("/spec-kitty.tasks-outline then /spec-kitty.tasks", "/spec-kitty-tasks-outline then /spec-kitty-tasks"),
        ("end of sentence /spec-kitty.plan.", "end of sentence /spec-kitty-plan."),
        ("(/spec-kitty.review)", "(/spec-kitty-review)"),
        ("`/spec-kitty.implement WP01`", "`/spec-kitty-implement WP01`"),
        ("/spec-kitty.analyze,", "/spec-kitty-analyze,"),
        ("line\n/spec-kitty.plan", "line\n/spec-kitty-plan"),
    ],
)
def test_rewrite_rewrites_invocation_tokens(text: str, expected: str) -> None:
    assert rewrite_command_invocations(text, _COMMANDS) == expected


@pytest.mark.parametrize(
    "text",
    [
        "https://spec-kitty.ai",
        "see spec-kitty.analysis-report",
        "/spec-kitty.analysis-report",
        ".claude/commands/spec-kitty.plan.md",
        "commands/spec-kitty.plan.md",
        "/spec-kitty.plan.md",
        "https://example.com/spec-kitty.plan",
        "/spec-kitty.tasksx",
        "/spec-kitty.tasks_outline",
        "/spec-kitty.advise",
        "/spec-kitty.<command>",
        "spec-kitty.plan",
        "foo$spec-kitty.plan",
        "//spec-kitty.plan",
        "/spec-kitty-plan",
    ],
)
def test_rewrite_leaves_non_tokens_alone(text: str) -> None:
    assert rewrite_command_invocations(text, _COMMANDS) == text


def test_rewrite_with_no_commands_is_identity() -> None:
    assert rewrite_command_invocations("/spec-kitty.plan", ()) == "/spec-kitty.plan"


@pytest.mark.parametrize(
    ("agent", "is_skill_agent", "expected"),
    [
        ("codex", True, "$spec-kitty-plan"),
        ("pi", True, "/skill:spec-kitty-plan"),
        ("letta", True, "/spec-kitty-plan"),
        ("vibe", True, "/spec-kitty-plan"),
        ("claude", False, "/spec-kitty.plan"),
    ],
)
def test_skill_invocation_token(agent: str, is_skill_agent: bool, expected: str) -> None:
    assert skill_invocation_token(agent, "plan", is_skill_agent=is_skill_agent) == expected


def test_module_is_a_dependency_free_leaf() -> None:
    """The authority imports nothing from the package (import-cycle safety)."""
    tree = ast.parse(Path(names.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert imported == {"__future__", "re", "collections.abc"}
    assert set(names.__all__) <= set(dir(names))
