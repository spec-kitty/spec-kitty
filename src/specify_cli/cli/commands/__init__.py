"""Command registration helpers for Spec Kitty CLI."""

from __future__ import annotations

import sys

import click
import typer
from typer.core import TyperGroup
from typer.models import DefaultPlaceholder, TyperInfo


class HelpOnEmptyTopLevelGroup(TyperGroup):
    """Render help with exit 0 for empty top-level command-group invocation."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if not args and self.no_args_is_help and not ctx.resilient_parsing:
            click.echo(ctx.get_help(), color=ctx.color)
            ctx.exit(0)
        return super().parse_args(ctx, args)


_HELP_ON_EMPTY_GROUP_CLASS_CACHE: dict[type[TyperGroup], type[TyperGroup]] = {}
HELP_OPTION_NAMES = ["--help", "-h"]

_TOP_LEVEL_GROUP_EMPTY_INVOCATION_EXCEPTIONS = frozenset(
    {
        # These groups intentionally run a default action when invoked without
        # a subcommand.
        "context",
        "migrate",
        # This surface is JSON-first; even usage failures must remain JSON
        # envelopes, not Rich/prose help.
        "orchestrator-api",
    }
)


def _is_explicit_typer_setting(value: object) -> bool:
    return not isinstance(value, DefaultPlaceholder)


def _with_short_help(context_settings: dict[str, object] | None | DefaultPlaceholder) -> dict[str, object]:
    settings = (
        {}
        if isinstance(context_settings, DefaultPlaceholder) or context_settings is None
        else dict(context_settings)
    )
    settings["help_option_names"] = HELP_OPTION_NAMES
    return settings


def _apply_short_help_options(app: typer.Typer) -> None:
    """Make ``-h`` an alias for ``--help`` across registered commands."""
    app.info.context_settings = _with_short_help(app.info.context_settings)

    for command_info in app.registered_commands:
        command_info.context_settings = _with_short_help(command_info.context_settings)

    for group_info in app.registered_groups:
        group_info.context_settings = _with_short_help(group_info.context_settings)
        _apply_short_help_options(group_info.typer_instance)


def _top_level_group_name(group_info: TyperInfo) -> str | None:
    if _is_explicit_typer_setting(group_info.name) and group_info.name is not None:
        return str(group_info.name)

    child_name = group_info.typer_instance.info.name
    if _is_explicit_typer_setting(child_name) and child_name is not None:
        return str(child_name)

    return None


def _command_name(command_info: object) -> str:
    name = getattr(command_info, "name", None)
    if _is_explicit_typer_setting(name) and name is not None:
        return str(name)

    callback = getattr(command_info, "callback", None)
    callback_name = getattr(callback, "__name__", "")
    return str(callback_name).replace("_", "-")


def _sort_root_command_metadata(app: typer.Typer) -> None:
    """Sort root commands and groups by their displayed names."""
    app.registered_commands.sort(key=_command_name)
    app.registered_groups.sort(key=lambda group_info: _top_level_group_name(group_info) or "")


def _top_level_group_invokes_without_command(group_info: TyperInfo) -> bool:
    values = (
        group_info.invoke_without_command,
        group_info.typer_instance.info.invoke_without_command,
    )
    return any(_is_explicit_typer_setting(value) and bool(value) for value in values)


def _top_level_group_base_class(group_info: TyperInfo) -> type[TyperGroup]:
    if _is_explicit_typer_setting(group_info.cls):
        return group_info.cls

    child_cls = group_info.typer_instance.info.cls
    if _is_explicit_typer_setting(child_cls):
        return child_cls

    return TyperGroup


def _help_on_empty_group_class(base_class: type[TyperGroup]) -> type[TyperGroup]:
    if issubclass(base_class, HelpOnEmptyTopLevelGroup):
        return base_class
    if base_class is TyperGroup:
        return HelpOnEmptyTopLevelGroup

    cached = _HELP_ON_EMPTY_GROUP_CLASS_CACHE.get(base_class)
    if cached is not None:
        return cached

    wrapped = type(
        f"HelpOnEmpty{base_class.__name__}",
        (HelpOnEmptyTopLevelGroup, base_class),
        {},
    )
    _HELP_ON_EMPTY_GROUP_CLASS_CACHE[base_class] = wrapped
    return wrapped


def _enforce_top_level_empty_group_help(app: typer.Typer) -> None:
    """Make empty top-level command groups render help by default.

    Typer defaults nested command groups to "Missing command" unless each group
    opts into no_args_is_help.  Enforcing that policy at root registration keeps
    future top-level groups consistent while preserving explicit default-action
    and machine-contract exceptions.
    """
    for group_info in app.registered_groups:
        group_name = _top_level_group_name(group_info)
        if group_name in _TOP_LEVEL_GROUP_EMPTY_INVOCATION_EXCEPTIONS:
            continue
        if _top_level_group_invokes_without_command(group_info):
            continue

        group_info.no_args_is_help = True
        group_info.cls = _help_on_empty_group_class(_top_level_group_base_class(group_info))
        group_info.typer_instance.info.no_args_is_help = True


def _is_next_fast_path(argv: list[str]) -> bool:
    """Return True when argv directly invokes the startup-sensitive next command."""
    for arg in argv[1:]:
        if arg in {"--help", "-h"}:
            return False
        if arg == "next":
            return True
        if not arg.startswith("-"):
            return False
    return False


def _is_live_work_hook_fast_path(argv: list[str]) -> bool:
    """Return True when argv directly invokes the per-tool-call live-work hook.

    ``spec-kitty live-work hook <harness>`` is registered on the harness's
    PreToolUse/PostToolUse events, which run synchronously around every tool
    call — so this path must not pay the full command-registry import
    (spec-kitty#4353 fix round: the hook was measured at ~12 s wall against
    its own 4 s budget, all of it registry imports). Only the live-work
    group is registered, the same posture as the ``next`` fast path.
    """
    args = [arg for arg in argv[1:] if not arg.startswith("-")]
    return len(args) >= 2 and args[0] == "live-work" and args[1] == "hook"


_LIVE_WORK_GROUP_HELP = (
    "Live Work harness capture: tools, files, tests and delegation as live relay frames (#4268)."
)


def register_commands(app: typer.Typer) -> None:
    """Attach all extracted commands to the root Typer application."""
    if _is_next_fast_path(sys.argv):
        from . import next_cmd as next_cmd_module

        app.command(name="next")(next_cmd_module.next_step)
        _apply_short_help_options(app)
        return

    if _is_live_work_hook_fast_path(sys.argv):
        from . import live_work as live_work_module

        app.add_typer(live_work_module.app, name="live-work", help=_LIVE_WORK_GROUP_HELP)
        _apply_short_help_options(app)
        return

    from . import accept as accept_module
    from . import agent as agent_module
    from . import archive as archive_module
    from . import auth as auth_module
    from . import plugin as plugin_module
    from . import charter as charter_module
    from . import commit_guard_hook_cmd as commit_guard_hook_cmd_module
    from . import config_cmd as config_cmd_module
    from . import context as context_module
    from . import cutover_guard as cutover_guard_module
    from . import dashboard as dashboard_module
    from . import dispatch as dispatch_module
    from . import docs as docs_module
    from . import doctor as doctor_module
    from . import doctrine as doctrine_module
    from . import events as events_module
    from . import glossary as glossary_module
    from . import implement as implement_module
    from . import intake as intake_module
    from . import invocations_cmd as invocations_cmd_module
    from specify_cli.tasks import issue_matrix_migration as issue_matrix_module
    from . import lifecycle as lifecycle_module
    from . import lint as lint_module
    from . import live_work as live_work_module
    from . import materialize as materialize_module
    from . import merge as merge_module
    from . import merge_driver as merge_driver_module
    from . import migrate_cmd as migrate_module
    from . import mission as mission_module
    from . import mission_type as mission_type_module
    from . import moments as moments_module
    from . import next_cmd as next_cmd_module
    from . import ops as ops_module
    from . import profiles_cmd as profiles_cmd_module
    from . import profile_invocation as profile_invocation_module
    from . import reconcile as reconcile_module
    from . import regen as regen_module
    from . import research as research_module
    from . import routes as routes_module
    from . import review as review_module
    from . import safe_commit_cmd as safe_commit_module
    from . import spec_commit_cmd as spec_commit_module
    from . import session_start as session_start_module
    from . import session_stop as session_stop_module
    from . import upgrade as upgrade_module
    from . import validate_encoding as validate_encoding_module
    from . import validate_tasks as validate_tasks_module
    from . import verify as verify_module
    from . import workflow as workflow_module
    from . import zeitgeist as zeitgeist_module
    from specify_cli import orchestrator_api as orchestrator_api_module
    from . import tracker as tracker_module

    app.command()(accept_module.accept)
    app.add_typer(agent_module.app, name="agent")
    app.add_typer(archive_module.app, name="archive", help="Archive a terminal mission (operator-invoked only).")
    app.command()(config_cmd_module.config)
    app.add_typer(auth_module.app, name="auth", help="Authentication commands")
    app.add_typer(charter_module.app, name="charter")
    app.add_typer(context_module.app, name="context")
    app.command(name="cutover-guard", help="Diff-scoped fail-closed cut-over gate (pre-merge required check).")(
        cutover_guard_module.cutover_guard
    )
    app.command()(dashboard_module.dashboard)
    app.add_typer(doctor_module.app, name="doctor", help="Project health diagnostics")
    # CR-02 (mission charter-code-topology-01M152G1 S4): the `doctrine`
    # group is a deprecated, hidden alias -- `spec-kitty doctrine <x>` still
    # runs (it delegates to the exact same implementation, unchanged), but
    # it no longer clutters `spec-kitty --help`'s top-level command list
    # (`hidden=True`) and typer marks it `deprecated=True` for the rare
    # caller who still finds it via `spec-kitty doctrine --help` directly.
    # The module's own `@app.callback()` adds the operator-facing stderr
    # notice every invocation prints.
    app.add_typer(
        doctrine_module.app,
        name="doctrine",
        help="[DEPRECATED — use `spec-kitty charter`] Manage org-layer doctrine packs",
        deprecated=True,
        hidden=True,
    )
    app.add_typer(docs_module.app, name="docs", help="Common Docs retrieval commands")
    app.add_typer(events_module.app, name="events", help="Event log tailing commands")
    app.add_typer(glossary_module.app, name="glossary", help="Glossary management commands")
    app.command()(implement_module.implement)
    app.command()(intake_module.intake)
    # write-side-seam-matrix-tracer-01KYP3MH WP05 / T022 (FR-013): bulk
    # issue-matrix migration command, out-of-map registration (owned_files
    # for WP05 does not list this file; a rationale-backed minimal edit is
    # the only way to make `spec-kitty issue-matrix migrate` reachable).
    app.add_typer(issue_matrix_module.app, name="issue-matrix", help="Issue-matrix commands (structured issue-matrix.json).")
    app.command()(lifecycle_module.specify)
    app.command()(lifecycle_module.plan)
    app.command()(lifecycle_module.tasks)
    app.command(name="lint")(lint_module.lint_command)
    app.command(name="materialize")(materialize_module.materialize)
    app.command(
        name="regen",
        help="Regenerate the committed generated agent-command + skill fixtures from source (#3447).",
    )(regen_module.regen)
    app.command()(merge_module.merge)
    app.command(name="commit-guard-hook", hidden=True)(
        commit_guard_hook_cmd_module.commit_guard_hook_cli
    )
    app.command(name="merge-driver-event-log", hidden=True)(merge_driver_module.merge_driver_event_log)
    app.command(name="merge-driver-meta", hidden=True)(merge_driver_module.merge_driver_meta)
    app.command(name="merge-driver-traces", hidden=True)(merge_driver_module.merge_driver_traces)
    app.command(name="merge-driver-acceptance-matrix", hidden=True)(
        merge_driver_module.merge_driver_acceptance_matrix
    )
    app.command(name="merge-driver-issue-matrix", hidden=True)(
        merge_driver_module.merge_driver_issue_matrix
    )
    app.command(name="merge-driver-review-cycle", hidden=True)(
        merge_driver_module.merge_driver_review_cycle
    )
    app.add_typer(migrate_module.app, name="migrate")
    app.add_typer(mission_module.app, name="mission")
    app.command(name="next")(next_cmd_module.next_step)
    app.add_typer(mission_type_module.app, name="mission-type")
    app.add_typer(
        moments_module.moments_app,
        name="moments",
        help="Control which Zeitgeist status moments reach agent context (off / mine / team), per developer and per repo.",
    )
    app.add_typer(ops_module.app, name="ops")
    app.add_typer(plugin_module.plugin_app, name="plugin", help="Plugin bundle commands")
    app.add_typer(orchestrator_api_module.app, name="orchestrator-api")
    app.command(name="reconcile", help="Reconcile a mission dossier against its recorded snapshot (exit 0=parity, non-zero=divergence).")(
        reconcile_module.reconcile
    )
    app.command()(research_module.research)
    app.command(
        name="routes", help="Show which team admits this checkout and which relay carries its moments."
    )(routes_module.routes)
    app.command(name="review")(review_module.review_mission)
    app.command(name="safe-commit")(safe_commit_module.safe_commit_command)
    app.command(name="spec-commit")(spec_commit_module.spec_commit_command)
    app.command(name="session-start", help="Emit spec-kitty orientation for the Claude Code SessionStart hook.")(session_start_module.session_start)
    app.command(name="session-stop", help="Emit the open-Ops reminder for the Claude Code Stop hook.")(session_stop_module.session_stop)
    app.add_typer(
        live_work_module.app,
        name="live-work",
        help=_LIVE_WORK_GROUP_HELP,
    )
    app.add_typer(tracker_module.app, name="tracker", help="Task tracker commands")
    app.command(name="issue-search", help="Search tracker issues via the hosted read path")(tracker_module.issue_search_command)
    app.command()(upgrade_module.upgrade)
    app.command(name="validate-encoding")(validate_encoding_module.validate_encoding)
    app.command(name="validate-tasks")(validate_tasks_module.validate_tasks)
    app.command()(verify_module.verify_setup)
    app.add_typer(workflow_module.app, name="workflow", help="Manage mission workflow definitions")
    app.add_typer(
        zeitgeist_module.app,
        name="zeitgeist",
        help=(
            "Access to one team's live Zeitgeist presence/focus stream and status-moment events, "
            "authored peer messaging (#4269), a local human-gated prose approval surface, and operability drills."
        ),
    )
    app.add_typer(profiles_cmd_module.app, name="profiles")
    app.command(name="dispatch", help="Dispatch a request to a governed Op (canonical surface).")(dispatch_module.dispatch)
    app.add_typer(profile_invocation_module.profile_invocation_app, name="profile-invocation")
    app.add_typer(invocations_cmd_module.app, name="invocations")

    from specify_cli.cli.commands.retrospect import app as retrospect_app  # WP05 (replaces WP09 single-command registration)

    app.add_typer(retrospect_app, name="retrospect", help="Retrospective authoring and summary (create / backfill / summary)")
    _sort_root_command_metadata(app)
    _enforce_top_level_empty_group_help(app)
    _apply_short_help_options(app)


__all__ = ["register_commands"]
