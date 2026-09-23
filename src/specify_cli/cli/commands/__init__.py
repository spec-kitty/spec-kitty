"""Command registration helpers for Spec Kitty CLI."""

from __future__ import annotations

import inspect
import sys
from collections.abc import Callable

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
    settings = {} if isinstance(context_settings, DefaultPlaceholder) or context_settings is None else dict(context_settings)
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


_LIVE_WORK_GROUP_HELP = "Live Work harness capture: tools, files, tests and delegation as live relay frames (#4268)."


_CommandRegistrar = Callable[[typer.Typer], None]


def _register_accept(app: typer.Typer) -> None:
    from . import accept as accept_module

    app.command()(accept_module.accept)


def _register_agent(app: typer.Typer) -> None:
    from . import agent as agent_module

    app.add_typer(agent_module.app, name="agent")


def _register_archive(app: typer.Typer) -> None:
    from . import archive as archive_module

    app.add_typer(archive_module.app, name="archive", help="Archive a terminal mission (operator-invoked only).")


def _register_config(app: typer.Typer) -> None:
    from . import config_cmd as config_cmd_module

    app.command()(config_cmd_module.config)


def _register_auth(app: typer.Typer) -> None:
    from . import auth as auth_module

    app.add_typer(auth_module.app, name="auth", help="Authentication commands")


def _register_charter(app: typer.Typer) -> None:
    from . import charter as charter_module

    app.add_typer(charter_module.app, name="charter")


def _register_context(app: typer.Typer) -> None:
    from . import context as context_module

    app.add_typer(context_module.app, name="context")


def _register_cutover_guard(app: typer.Typer) -> None:
    from . import cutover_guard as cutover_guard_module

    app.command(name="cutover-guard", help="Diff-scoped fail-closed cut-over gate (pre-merge required check).")(cutover_guard_module.cutover_guard)


def _register_dashboard(app: typer.Typer) -> None:
    from . import dashboard as dashboard_module

    app.command()(dashboard_module.dashboard)


def _register_doctor(app: typer.Typer) -> None:
    from . import doctor as doctor_module

    app.add_typer(doctor_module.app, name="doctor", help="Project health diagnostics")


def _register_doctrine(app: typer.Typer) -> None:
    # CR-02 (mission charter-code-topology-01M152G1 S4): the `doctrine`
    # group is a deprecated, hidden alias -- `spec-kitty doctrine <x>` still
    # runs (it delegates to the exact same implementation, unchanged), but
    # it no longer clutters `spec-kitty --help`'s top-level command list
    # (`hidden=True`) and typer marks it `deprecated=True` for the rare
    # caller who still finds it via `spec-kitty doctrine --help` directly.
    # The module's own `@app.callback()` adds the operator-facing stderr
    # notice every invocation prints.
    from . import doctrine as doctrine_module

    app.add_typer(
        doctrine_module.app,
        name="doctrine",
        help="[DEPRECATED — use `spec-kitty charter`] Manage org-layer doctrine packs",
        deprecated=True,
        hidden=True,
    )


def _register_docs(app: typer.Typer) -> None:
    from . import docs as docs_module

    app.add_typer(docs_module.app, name="docs", help="Common Docs retrieval commands")


def _register_events(app: typer.Typer) -> None:
    from . import events as events_module

    app.add_typer(events_module.app, name="events", help="Event log tailing commands")


def _register_glossary(app: typer.Typer) -> None:
    from . import glossary as glossary_module

    app.add_typer(glossary_module.app, name="glossary", help="Glossary management commands")


def _register_implement(app: typer.Typer) -> None:
    from . import implement as implement_module

    app.command()(implement_module.implement)


def _register_intake(app: typer.Typer) -> None:
    from . import intake as intake_module

    app.command()(intake_module.intake)


def _register_issue_matrix(app: typer.Typer) -> None:
    # write-side-seam-matrix-tracer-01KYP3MH WP05 / T022 (FR-013): bulk
    # issue-matrix migration command, out-of-map registration (owned_files
    # for WP05 does not list this file; a rationale-backed minimal edit is
    # the only way to make `spec-kitty issue-matrix migrate` reachable).
    from specify_cli.tasks import issue_matrix_migration as issue_matrix_module

    app.add_typer(issue_matrix_module.app, name="issue-matrix", help="Issue-matrix commands (structured issue-matrix.json).")


def _register_lifecycle(app: typer.Typer) -> None:
    from . import lifecycle as lifecycle_module

    app.command()(lifecycle_module.specify)
    app.command()(lifecycle_module.plan)
    app.command()(lifecycle_module.tasks)


def _register_lint(app: typer.Typer) -> None:
    from . import lint as lint_module

    app.command(name="lint")(lint_module.lint_command)


def _register_materialize(app: typer.Typer) -> None:
    from . import materialize as materialize_module

    app.command(name="materialize")(materialize_module.materialize)


def _register_regen(app: typer.Typer) -> None:
    from . import regen as regen_module

    app.command(
        name="regen",
        help="Regenerate the committed generated agent-command + skill fixtures from source (#3447).",
    )(regen_module.regen)


def _register_merge(app: typer.Typer) -> None:
    from . import merge as merge_module

    app.command()(merge_module.merge)


def _register_commit_guard_hook(app: typer.Typer) -> None:
    from . import commit_guard_hook_cmd as commit_guard_hook_cmd_module

    app.command(name="commit-guard-hook", hidden=True)(commit_guard_hook_cmd_module.commit_guard_hook_cli)


def _register_merge_driver(app: typer.Typer) -> None:
    from . import merge_driver as merge_driver_module

    app.command(name="merge-driver-event-log", hidden=True)(merge_driver_module.merge_driver_event_log)
    app.command(name="merge-driver-meta", hidden=True)(merge_driver_module.merge_driver_meta)
    app.command(name="merge-driver-traces", hidden=True)(merge_driver_module.merge_driver_traces)
    app.command(name="merge-driver-acceptance-matrix", hidden=True)(merge_driver_module.merge_driver_acceptance_matrix)
    app.command(name="merge-driver-issue-matrix", hidden=True)(merge_driver_module.merge_driver_issue_matrix)
    app.command(name="merge-driver-review-cycle", hidden=True)(merge_driver_module.merge_driver_review_cycle)


def _register_migrate(app: typer.Typer) -> None:
    from . import migrate_cmd as migrate_module

    app.add_typer(migrate_module.app, name="migrate")


def _register_mission(app: typer.Typer) -> None:
    from . import mission as mission_module

    app.add_typer(mission_module.app, name="mission")


def _register_next(app: typer.Typer) -> None:
    from . import next_cmd as next_cmd_module

    app.command(name="next")(next_cmd_module.next_step)


def _register_mission_type(app: typer.Typer) -> None:
    from . import mission_type as mission_type_module

    app.add_typer(mission_type_module.app, name="mission-type")


def _register_moments(app: typer.Typer) -> None:
    from . import moments as moments_module

    app.add_typer(
        moments_module.moments_app,
        name="moments",
        help="Control which Zeitgeist status moments reach agent context (off / mine / team), per developer and per repo.",
    )


def _register_ops(app: typer.Typer) -> None:
    from . import ops as ops_module

    app.add_typer(ops_module.app, name="ops")


def _register_plugin(app: typer.Typer) -> None:
    from . import plugin as plugin_module

    app.add_typer(plugin_module.plugin_app, name="plugin", help="Plugin bundle commands")


def _register_orchestrator_api(app: typer.Typer) -> None:
    from specify_cli import orchestrator_api as orchestrator_api_module

    app.add_typer(orchestrator_api_module.app, name="orchestrator-api")


def _register_reconcile(app: typer.Typer) -> None:
    from . import reconcile as reconcile_module

    app.command(
        name="reconcile",
        help="Reconcile a mission dossier against its recorded snapshot (exit 0=parity, non-zero=divergence).",
    )(reconcile_module.reconcile)


def _register_research(app: typer.Typer) -> None:
    from . import research as research_module

    app.command()(research_module.research)


def _register_routes(app: typer.Typer) -> None:
    from . import routes as routes_module

    app.command(name="routes", help="Show which team admits this checkout and which relay carries its moments.")(routes_module.routes)


def _register_review(app: typer.Typer) -> None:
    from . import review as review_module

    app.command(name="review")(review_module.review_mission)


def _register_safe_commit(app: typer.Typer) -> None:
    from . import safe_commit_cmd as safe_commit_module

    app.command(name="safe-commit")(safe_commit_module.safe_commit_command)


def _register_spec_commit(app: typer.Typer) -> None:
    from . import spec_commit_cmd as spec_commit_module

    app.command(name="spec-commit")(spec_commit_module.spec_commit_command)


def _register_session_start(app: typer.Typer) -> None:
    from . import session_start as session_start_module

    app.command(name="session-start", help="Emit spec-kitty orientation for the Claude Code SessionStart hook.")(session_start_module.session_start)


def _register_session_stop(app: typer.Typer) -> None:
    from . import session_stop as session_stop_module

    app.command(name="session-stop", help="Emit the open-Ops reminder for the Claude Code Stop hook.")(session_stop_module.session_stop)


def _register_live_work(app: typer.Typer) -> None:
    from . import live_work as live_work_module

    app.add_typer(
        live_work_module.app,
        name="live-work",
        help=_LIVE_WORK_GROUP_HELP,
    )


def _register_tracker(app: typer.Typer) -> None:
    from . import tracker as tracker_module

    app.add_typer(tracker_module.app, name="tracker", help="Task tracker commands")
    app.command(name="issue-search", help="Search tracker issues via the hosted read path")(tracker_module.issue_search_command)


def _register_upgrade(app: typer.Typer) -> None:
    from . import upgrade as upgrade_module

    app.command()(upgrade_module.upgrade)


def _register_validate_encoding(app: typer.Typer) -> None:
    from . import validate_encoding as validate_encoding_module

    app.command(name="validate-encoding")(validate_encoding_module.validate_encoding)


def _register_validate_tasks(app: typer.Typer) -> None:
    from . import validate_tasks as validate_tasks_module

    app.command(name="validate-tasks")(validate_tasks_module.validate_tasks)


def _register_verify(app: typer.Typer) -> None:
    from . import verify as verify_module

    app.command()(verify_module.verify_setup)


def _register_workflow(app: typer.Typer) -> None:
    from . import workflow as workflow_module

    app.add_typer(workflow_module.app, name="workflow", help="Manage mission workflow definitions")


def _register_zeitgeist(app: typer.Typer) -> None:
    from . import zeitgeist as zeitgeist_module

    app.add_typer(
        zeitgeist_module.app,
        name="zeitgeist",
        help=(
            "Access to one team's live Zeitgeist presence/focus stream and status-moment events, "
            "authored peer messaging (#4269), a local human-gated prose approval surface, and operability drills."
        ),
    )


def _register_profiles(app: typer.Typer) -> None:
    from . import profiles_cmd as profiles_cmd_module

    app.add_typer(profiles_cmd_module.app, name="profiles")


def _register_dispatch(app: typer.Typer) -> None:
    from . import dispatch as dispatch_module

    app.command(name="dispatch", help="Dispatch a request to a governed Op (canonical surface).")(dispatch_module.dispatch)


def _register_profile_invocation(app: typer.Typer) -> None:
    from . import profile_invocation as profile_invocation_module

    app.add_typer(profile_invocation_module.profile_invocation_app, name="profile-invocation")


def _register_invocations(app: typer.Typer) -> None:
    from . import invocations_cmd as invocations_cmd_module

    app.add_typer(invocations_cmd_module.app, name="invocations")


def _register_retrospect(app: typer.Typer) -> None:
    from specify_cli.cli.commands.retrospect import app as retrospect_app  # WP05 (replaces WP09 single-command registration)

    app.add_typer(retrospect_app, name="retrospect", help="Retrospective authoring and summary (create / backfill / summary)")


# WP05 (#4417-deferred): one registrar per module import the eager branch used
# to run unconditionally. ``_ALL_COMMAND_REGISTRARS`` lists each function
# exactly once, in the same order the original unconditional-import block
# used, for the "register everything" fallback. ``_COMMAND_REGISTRARS`` maps
# every top-level command/group *name* Typer would end up exposing to the one
# registrar that backs it -- several names may map to the same registrar
# (e.g. ``specify``/``plan``/``tasks`` all come from ``lifecycle``; the six
# ``merge-driver-*`` hidden commands all come from ``merge_driver``) since a
# single module can back more than one registered leaf, exactly as the
# pre-existing module-to-command mapping already did.
_ALL_COMMAND_REGISTRARS: tuple[_CommandRegistrar, ...] = (
    _register_accept,
    _register_agent,
    _register_archive,
    _register_config,
    _register_auth,
    _register_charter,
    _register_context,
    _register_cutover_guard,
    _register_dashboard,
    _register_doctor,
    _register_doctrine,
    _register_docs,
    _register_events,
    _register_glossary,
    _register_implement,
    _register_intake,
    _register_issue_matrix,
    _register_lifecycle,
    _register_lint,
    _register_materialize,
    _register_regen,
    _register_merge,
    _register_commit_guard_hook,
    _register_merge_driver,
    _register_migrate,
    _register_mission,
    _register_next,
    _register_mission_type,
    _register_moments,
    _register_ops,
    _register_plugin,
    _register_orchestrator_api,
    _register_reconcile,
    _register_research,
    _register_routes,
    _register_review,
    _register_safe_commit,
    _register_spec_commit,
    _register_session_start,
    _register_session_stop,
    _register_live_work,
    _register_tracker,
    _register_upgrade,
    _register_validate_encoding,
    _register_validate_tasks,
    _register_verify,
    _register_workflow,
    _register_zeitgeist,
    _register_profiles,
    _register_dispatch,
    _register_profile_invocation,
    _register_invocations,
    _register_retrospect,
)

_COMMAND_REGISTRARS: dict[str, _CommandRegistrar] = {
    "accept": _register_accept,
    "agent": _register_agent,
    "archive": _register_archive,
    "config": _register_config,
    "auth": _register_auth,
    "charter": _register_charter,
    "context": _register_context,
    "cutover-guard": _register_cutover_guard,
    "dashboard": _register_dashboard,
    "doctor": _register_doctor,
    "doctrine": _register_doctrine,
    "docs": _register_docs,
    "events": _register_events,
    "glossary": _register_glossary,
    "implement": _register_implement,
    "intake": _register_intake,
    "issue-matrix": _register_issue_matrix,
    "specify": _register_lifecycle,
    "plan": _register_lifecycle,
    "tasks": _register_lifecycle,
    "lint": _register_lint,
    "materialize": _register_materialize,
    "regen": _register_regen,
    "merge": _register_merge,
    "commit-guard-hook": _register_commit_guard_hook,
    "merge-driver-event-log": _register_merge_driver,
    "merge-driver-meta": _register_merge_driver,
    "merge-driver-traces": _register_merge_driver,
    "merge-driver-acceptance-matrix": _register_merge_driver,
    "merge-driver-issue-matrix": _register_merge_driver,
    "merge-driver-review-cycle": _register_merge_driver,
    "migrate": _register_migrate,
    "mission": _register_mission,
    "next": _register_next,
    "mission-type": _register_mission_type,
    "moments": _register_moments,
    "ops": _register_ops,
    "plugin": _register_plugin,
    "orchestrator-api": _register_orchestrator_api,
    "reconcile": _register_reconcile,
    "research": _register_research,
    "routes": _register_routes,
    "review": _register_review,
    "safe-commit": _register_safe_commit,
    "spec-commit": _register_spec_commit,
    "session-start": _register_session_start,
    "session-stop": _register_session_stop,
    "live-work": _register_live_work,
    "tracker": _register_tracker,
    "issue-search": _register_tracker,
    "upgrade": _register_upgrade,
    "validate-encoding": _register_validate_encoding,
    "validate-tasks": _register_validate_tasks,
    "verify-setup": _register_verify,
    "workflow": _register_workflow,
    "zeitgeist": _register_zeitgeist,
    "profiles": _register_profiles,
    "dispatch": _register_dispatch,
    "profile-invocation": _register_profile_invocation,
    "invocations": _register_invocations,
    "retrospect": _register_retrospect,
}


def _root_boolean_flag_tokens(app: typer.Typer) -> frozenset[str]:
    """Return every root-callback CLI flag spelling that consumes NO value token.

    PR-CONTRACT-001: derived from the ACTUAL registered root callback
    (``main_callback``, already attached to *app* by the time
    ``register_commands()`` runs -- see ``specify_cli/__init__.py``'s
    ``_build_app()``), never hardcoded. Typer turns a ``bool``-annotated
    ``typer.Option`` into a value-less flag (``--version``/``-v`` today); any
    other annotation is a value-taking option and is deliberately excluded,
    so ``_resolve_single_leaf_command`` can tell the two apart instead of
    assuming every ``-``-prefixed token is safe to skip over.
    """
    info = app.registered_callback
    if info is None or info.callback is None:
        return frozenset()
    tokens: set[str] = set()
    for parameter in inspect.signature(info.callback).parameters.values():
        default = parameter.default
        if isinstance(default, typer.models.OptionInfo) and parameter.annotation is bool:
            tokens.update(decl for decl in default.param_decls if decl.startswith("-"))
    return frozenset(tokens)


def _resolve_single_leaf_command(argv: list[str], app: typer.Typer) -> str | None:
    """Return the one top-level command/group name argv resolves to, or ``None``.

    Mirrors ``_is_next_fast_path``'s argv-sniffing shape. ``None`` means argv
    does not cleanly resolve to exactly one known top-level command/group --
    no command token yet, ``--help``/``-h`` appears before one, an option
    token this function cannot prove is value-less precedes it, or the token
    does not name anything in ``_COMMAND_REGISTRARS`` -- and the caller must
    eagerly register everything to produce correct output: a full top-level
    ``--help`` listing, an "unknown command" error reported against the full
    command set, or shell completion.

    PR-CONTRACT-001: a bare ``arg.startswith("-")`` skip-and-continue is only
    safe for options that consume no value of their own -- a future
    value-taking root option (e.g. ``--config PATH``) would have its value
    token misread as the command name. Every ``-``-prefixed token is checked
    against ``_root_boolean_flag_tokens(app)`` (derived from the real root
    callback, not a hand-maintained guess); an unrecognized option token
    falls back to full registration rather than assuming it takes no value.
    """
    boolean_flags = _root_boolean_flag_tokens(app)
    for arg in argv[1:]:
        if arg in {"--help", "-h"}:
            return None
        if arg.startswith("-"):
            if arg not in boolean_flags:
                return None
            continue
        return arg if arg in _COMMAND_REGISTRARS else None
    return None


def register_commands(app: typer.Typer) -> None:
    """Attach all extracted commands to the root Typer application."""
    # #3953: every registration exit below applies the mission-agnostic
    # ``--mission`` classes, so a *re*-registration (e.g. the freshness
    # script's defensive ``register_commands(app)`` with spoofed argv, which
    # appends fresh CommandInfos that would otherwise override the already-
    # retargeted ones) can never leave un-retargeted leaves behind.
    from specify_cli.cli.helpers import make_leaf_commands_mission_agnostic

    if _is_next_fast_path(sys.argv):
        from . import next_cmd as next_cmd_module

        app.command(name="next")(next_cmd_module.next_step)
        _apply_short_help_options(app)
        make_leaf_commands_mission_agnostic(app)
        return

    if _is_live_work_hook_fast_path(sys.argv):
        from . import live_work as live_work_module

        app.add_typer(live_work_module.app, name="live-work", help=_LIVE_WORK_GROUP_HELP)
        _apply_short_help_options(app)
        make_leaf_commands_mission_agnostic(app)
        return

    # WP05 (#4417-deferred): generalizes the same argv-sniffing idiom the two
    # fast paths above already use. When argv cleanly resolves to exactly one
    # known top-level command/group, only that one module tree is imported
    # and registered. Anything that does not cleanly resolve -- no command,
    # `--help` at the top level, an unrecognized name, shell completion --
    # still imports and registers every command, exactly as before this WP.
    single_leaf = _resolve_single_leaf_command(sys.argv, app)
    if single_leaf is not None:
        _COMMAND_REGISTRARS[single_leaf](app)
    else:
        for registrar in _ALL_COMMAND_REGISTRARS:
            registrar(app)

    _sort_root_command_metadata(app)
    _enforce_top_level_empty_group_help(app)
    _apply_short_help_options(app)
    make_leaf_commands_mission_agnostic(app)


__all__ = ["register_commands"]
