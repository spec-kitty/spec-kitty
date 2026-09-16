"""Mission-agnostic leaf commands accept-and-ignore ``--mission`` (#3953).

The shipped mission-step skill text (``packs/built-in/missions/mission-steps/
**/prompt.md``) instructs agents to pass ``--mission <handle>`` to *every*
spec-kitty command in multi-mission repos. Mission-scoped commands declare a
real ``--mission`` option; mission-agnostic ones (``agent profile list`` is
the observed case) rejected it with ``No such option: --mission``, so the
instruction was contradicted by the CLI once per session.

``MissionAgnosticCommand`` (``specify_cli.cli.helpers``) appends a hidden,
non-exposed ``--mission`` option to every leaf command that does not declare
its own, and ``_build_app`` applies it to the whole registered tree. These
tests pin the mechanism at three levels: the observed command path, the
whole-tree invariant the skill text implies, and the option semantics
themselves — mirroring the contract/CLI drift seam of
``tests/doctrine/mission_step_contracts/test_declared_commands_parse.py``
(#4031), which found the identical drift class for step-contract commands.
"""

from __future__ import annotations

from typing import Any

import click
import pytest
import typer
from typer.core import TyperCommand, TyperGroup
from typer.main import get_command
from typer.testing import CliRunner

from specify_cli.cli.helpers import (
    MissionAgnosticCommand,
    MissionAgnosticGroup,
    make_leaf_commands_mission_agnostic,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _resolve(argv: list[str]) -> click.Command:
    """Walk the Click group tree along ``argv``'s command names to the leaf command."""
    from specify_cli import app

    node: click.Command = get_command(app)
    rest = list(argv)
    while rest:
        sub = getattr(node, "commands", None)
        if not sub or rest[0] not in sub:
            break
        node = sub[rest.pop(0)]
    return node


def test_observed_command_accepts_and_ignores_mission() -> None:
    """``agent profile list --mission <handle>`` parses instead of exiting 2 (#3953)."""
    leaf = _resolve(["agent", "profile", "list"])
    ctx = leaf.make_context(leaf.name, ["--mission", "057-some-mission"])
    ctx.close()


def test_observed_command_accepts_equals_form() -> None:
    """``--mission=<handle>`` parses identically on a mission-agnostic command."""
    leaf = _resolve(["agent", "profile", "list"])
    ctx = leaf.make_context(leaf.name, ["--mission=057-some-mission"])
    ctx.close()


def test_sub_app_used_as_leaf_command_accepts_mission() -> None:
    """A sub-app whose callback owns the options (``charter list``) accepts ``--mission``.

    That shape is a leaf *group* at click level — found by the tree-wide guard
    below on the first run of this suite — so it is covered by
    ``MissionAgnosticGroup``, not ``MissionAgnosticCommand``.
    """
    leaf = _resolve(["charter", "list"])
    assert isinstance(leaf, MissionAgnosticGroup)
    ctx = leaf.make_context(leaf.name, ["--mission", "057-some-mission"])
    ctx.close()


def test_every_leaf_command_accepts_mission() -> None:
    """The skill text's "pass ``--mission`` to every command" invariant holds tree-wide.

    Every leaf command in the assembled app either declares a real ``--mission``
    or carries the ignored one via ``MissionAgnosticCommand`` — so no command a
    step prompt can name exits 2 on ``--mission`` alone. This is the guard for
    the drift class: a future command registered without ``--mission`` and
    without the walker applied fails here by name.
    """
    from specify_cli import app

    root = get_command(app)

    def leaves(node: click.Command) -> list[tuple[str, click.Command]]:
        sub = getattr(node, "commands", None)
        if not sub:
            return [("", node)]
        found: list[tuple[str, click.Command]] = []
        for name, cmd in sub.items():
            found.extend((f"{prefix} {name}".strip(), leaf) for prefix, leaf in leaves(cmd))
        return found

    all_leaves = leaves(root)
    assert len(all_leaves) > 100, "guard the guard: the tree walk found implausibly few commands"
    ctx = click.Context(root)
    offenders = [path for path, leaf in all_leaves if not any("--mission" in param.opts for param in leaf.get_params(ctx))]
    assert offenders == [], f"commands that reject --mission: {offenders}"


def test_mission_scoped_command_keeps_its_real_option() -> None:
    """A command that declares ``--mission`` (even behind a ``feature`` param) is untouched.

    ``agent mission check-prerequisites`` declares ``--mission`` through a
    ``mission_slug`` parameter — matched by option name, the real value must
    still reach the callback, not be silently dropped.
    """
    received: dict[str, Any] = {}
    sub = typer.Typer()

    @sub.command("scoped")
    def scoped(
        feature: str | None = typer.Option(None, "--mission", help="Mission slug"),
    ) -> None:
        received["feature"] = feature

    @sub.command("agnostic")
    def agnostic(json_output: bool = typer.Option(False, "--json")) -> None:
        received["ran"] = True

    root = typer.Typer()
    root.add_typer(sub, name="group")
    assert make_leaf_commands_mission_agnostic(root) == 2

    runner = CliRunner()
    result = runner.invoke(root, ["group", "scoped", "--mission", "real-handle"])
    assert result.exit_code == 0, result.output
    assert received["feature"] == "real-handle"

    result = runner.invoke(root, ["group", "agnostic", "--mission", "ignored-handle"])
    assert result.exit_code == 0, result.output
    assert received["ran"] is True


def test_ignored_mission_value_never_reaches_the_callback() -> None:
    """The ignored option is parsed and discarded; the callback signature is unchanged."""
    seen_kwargs: list[dict[str, Any]] = []
    sub = typer.Typer()

    @sub.command("list")
    def list_cmd(json_output: bool = typer.Option(False, "--json")) -> None:
        seen_kwargs.append({"json_output": json_output})

    root = typer.Typer()
    root.add_typer(sub, name="profile")
    make_leaf_commands_mission_agnostic(root)

    runner = CliRunner()
    for extra in (["--mission", "some-handle"], ["--mission=some-handle"]):
        result = runner.invoke(root, ["profile", "list", *extra])
        assert result.exit_code == 0, result.output
    assert seen_kwargs == [{"json_output": False}, {"json_output": False}]


def test_ignored_mission_is_not_advertised_in_help() -> None:
    """The compatibility option is hidden: ``--help`` output is unchanged."""
    sub = typer.Typer()

    @sub.command("list")
    def list_cmd() -> None:
        """List things."""

    root = typer.Typer()
    root.add_typer(sub, name="profile")
    make_leaf_commands_mission_agnostic(root)

    result = CliRunner().invoke(root, ["profile", "list", "--help"])
    assert result.exit_code == 0
    assert "--mission" not in result.output


def test_bare_mission_without_value_still_fails_loudly() -> None:
    """``--mission`` still requires a value — it is never a boolean flag."""
    sub = typer.Typer()

    @sub.command("list")
    def list_cmd() -> None:
        """List things."""

    root = typer.Typer()
    root.add_typer(sub, name="profile")
    make_leaf_commands_mission_agnostic(root)

    result = CliRunner().invoke(root, ["profile", "list", "--mission"])
    assert result.exit_code == 2
    assert "requires an argument" in result.output


def test_walker_recurses_into_nested_sub_apps() -> None:
    """Commands two group levels deep are retargeted."""
    inner = typer.Typer()

    @inner.command("leaf")
    def leaf_cmd() -> None:
        """Leaf."""

    middle = typer.Typer()
    middle.add_typer(inner, name="inner")
    root = typer.Typer()
    root.add_typer(middle, name="middle")

    assert make_leaf_commands_mission_agnostic(root) == 1
    assert inner.registered_commands[0].cls is MissionAgnosticCommand


def test_walker_targets_sub_app_leaf_commands_as_groups() -> None:
    """A callback-only sub-app (the ``charter list`` shape) gets ``MissionAgnosticGroup``."""
    calls: list[bool] = []
    leaf_app = typer.Typer(name="list", invoke_without_command=True)

    @leaf_app.callback()
    def list_callback(json_output: bool = typer.Option(False, "--json")) -> None:
        calls.append(json_output)

    root = typer.Typer()
    root.add_typer(leaf_app, name="list")
    assert make_leaf_commands_mission_agnostic(root) == 1

    result = CliRunner().invoke(root, ["list", "--mission", "ignored-handle"])
    assert result.exit_code == 0, result.output
    assert calls == [False]

    result = CliRunner().invoke(root, ["list", "--help"])
    assert result.exit_code == 0
    assert "--mission" not in result.output


def test_walker_leaves_custom_command_classes_alone() -> None:
    """A command already carrying a deliberate click class keeps it."""

    class CustomCommand(TyperCommand):
        pass

    class UnrelatedGroup(TyperGroup):
        pass

    app = typer.Typer()
    sub = typer.Typer(cls=UnrelatedGroup)

    @sub.command("plain")
    def plain() -> None:
        """Plain."""

    @sub.command("custom", cls=CustomCommand)
    def custom() -> None:
        """Custom."""

    app.add_typer(sub, name="sub")
    retargeted = make_leaf_commands_mission_agnostic(app)

    assert retargeted == 1
    assert sub.registered_commands[0].cls is MissionAgnosticCommand
    assert sub.registered_commands[1].cls is CustomCommand
