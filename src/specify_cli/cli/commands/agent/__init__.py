"""Agent command namespace for AI agents to execute spec-kitty mission actions programmatically."""

import typer
from typing_extensions import Annotated

from specify_cli.cli.commands import profiles_cmd
from specify_cli.cli.commands.agent_retrospect import app as retrospect_app
from specify_cli.cli.commands.decision import decision_app

from . import config, context, mission, release, status, tasks, tests, workflow
from .acceptance_verdict import acceptance_verdict
from .issue_verdict import issue_verdict_command
from .tracer_append import tracer_append

app = typer.Typer(
    name="agent",
    help="Commands for AI agents to execute spec-kitty mission actions programmatically",
    no_args_is_help=True
)

# Register sub-apps for each command module.
# `mission` and `action` are the canonical command namespaces.
app.add_typer(config.app, name="config")
app.add_typer(mission.app, name="mission", help="Mission lifecycle commands for AI agents")
app.add_typer(tasks.app, name="tasks")
app.add_typer(context.app, name="context")
app.add_typer(release.app, name="release")
app.add_typer(workflow.app, name="action", help="Mission action commands that display prompts and instructions for agents")
app.add_typer(status.app, name="status")
app.add_typer(tests.app, name="tests")
app.add_typer(decision_app, name="decision")
app.add_typer(retrospect_app, name="retrospect", help="Retrospective synthesis commands")
app.command(name="tracer-append")(tracer_append)
app.add_typer(
    profiles_cmd.app,
    name="profile",
    help="Compatibility alias for listing agent profiles",
    hidden=True,
)
app.command(name="issue-verdict")(issue_verdict_command)
# #3951 (F-58): both verdict commands live at the ``agent`` level.  Before
# this, ``issue-verdict`` was reachable at ``agent issue-verdict`` while
# ``acceptance-verdict`` lived only under ``agent mission`` — an operator
# following the one-level pattern hit "No such command".  The
# ``agent mission acceptance-verdict`` registration stays: mission-step
# prompts and the docs name it.
app.command(name="acceptance-verdict")(acceptance_verdict)


@app.command(name="check-prerequisites", hidden=True)
def check_prerequisites_alias(
    mission_slug: Annotated[
        str | None,
        typer.Option("--mission", help="Mission slug")
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON format")] = False,
    paths_only: Annotated[bool, typer.Option("--paths-only", help="Only output path variables")] = False,
    include_tasks: Annotated[bool, typer.Option("--include-tasks", help="Include tasks.md in validation")] = False,
    require_tasks: Annotated[
        bool,
        typer.Option("--require-tasks", hidden=True, help="Deprecated alias for --include-tasks"),
    ] = False,
) -> None:
    """Deprecated compatibility alias forwarding to agent mission check-prerequisites."""
    mission.check_prerequisites(
        feature=mission_slug,
        json_output=json_output,
        paths_only=paths_only,
        include_tasks=include_tasks,
        require_tasks=require_tasks,
    )


__all__ = ["app"]
