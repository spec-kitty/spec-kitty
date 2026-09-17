"""Shared CLI helpers for Spec Kitty commands."""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import click
import typer
from rich.align import Align
from rich.text import Text
from typer.core import TyperCommand, TyperGroup, TyperOption

# Deferred (TYPE_CHECKING + function-local in git_resolution_failure_message):
# charter.resolution's module-level import chain (jsonschema/rfc3987) is the
# heaviest single import every CLI startup paid, including the per-tool-call
# live-work hook path (#4353 fix round) — and these two names are only needed
# on the rare git-resolution failure path, where the raiser has already
# imported charter.resolution to raise the exception in the first place.
if TYPE_CHECKING:
    from charter.resolution import GitCommonDirUnavailableError, NotInsideRepositoryError

from specify_cli.cli.console import CliConsole, console
from specify_cli.cli.json_contract import json_error
from specify_cli.core.config import BANNER
from specify_cli.core.env import is_truthy
from specify_cli.core.project_resolver import locate_project_root

TAGLINE = "Spec Kitty - Spec-Driven Development Toolkit (forked from GitHub Spec Kit)"

# ---------------------------------------------------------------------------
# Nag-suppression helper (T032)
# ---------------------------------------------------------------------------


def _should_suppress_nag(argv: list[str] | None = None) -> bool:
    """Return True when nag output should be suppressed for this invocation.

    Suppression conditions (any one is sufficient):
    - ``--no-nag`` in argv.
    - ``--json`` in argv.
    - ``--quiet`` in argv.
    - ``--help`` / ``-h`` in argv.
    - ``--version`` / ``-v`` in argv.
    - ``CI`` environment variable is truthy.
    - ``SPEC_KITTY_NO_NAG`` environment variable is truthy.
    - stdout is not a TTY.

    Note: This function intentionally re-evaluates the suppression criteria
    from raw argv/env rather than delegating entirely to Invocation.suppresses_nag()
    in order to catch ``--json`` and ``--quiet`` which are command-level flags
    that Invocation.suppresses_nag() does not check (belt-and-suspenders per T032).
    """
    if argv is None:
        argv = sys.argv[1:]

    suppress_flags = frozenset({"--no-nag", "--json", "--plan-json", "--quiet", "--help", "-h", "--version", "-v"})
    if any(tok in suppress_flags for tok in argv):
        return True

    from specify_cli.compat.planner import is_ci_env  # noqa: PLC0415

    if is_ci_env():
        return True

    no_nag_val = os.environ.get("SPEC_KITTY_NO_NAG", "")
    if no_nag_val and no_nag_val.lower() not in ("0", "false", "no", "off"):
        return True

    try:
        if not sys.stdout.isatty():
            return True
    except Exception:  # noqa: BLE001 — isatty() can raise on exotic stream objects; treat as non-tty (safe to suppress)
        return True

    return False


class BannerGroup(TyperGroup):
    """Custom Typer group that renders the banner before help output."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        command_args = list(args)
        remaining = super().parse_args(ctx, args)
        if command_args:
            name, command, upgrade_args = self.resolve_command(ctx, command_args)
            if name == "migrate":
                ctx.meta["defer_root_bootstrap"] = True
            if name == "upgrade" and command is not None:
                from specify_cli.upgrade.intent import parse_upgrade_intent

                ctx.meta["upgrade_intent"] = parse_upgrade_intent(command, upgrade_args, project_available=(Path.cwd() / ".kittify").is_dir())
        return remaining

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted(super().list_commands(ctx))

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        if _should_use_simple_help():
            _format_simple_help(self, ctx, formatter)
            return
        show_banner()
        super().format_help(ctx, formatter)


# ---------------------------------------------------------------------------
# Mission-agnostic ``--mission`` accept-and-ignore (#3953)
# ---------------------------------------------------------------------------

_MISSION_OPTION_NAME = "--mission"


def _ignored_mission_option() -> TyperOption:
    """The hidden, non-exposed ``--mission`` option appended to mission-agnostic commands.

    Built from :class:`typer.core.TyperOption` — typer's own option class —
    and never a bare ``click.Option``: wheel installs resolve any typer in
    the declared ``>=0.24.1,<0.28`` range, and the 0.26+/0.27 era vendors its
    own click (``typer._click``) whose parser shares no classes with the
    real ``click`` package. A real-click ``Option`` injected into a
    vendored-click command crashes every invocation with
    ``'Context' object has no attribute '_param_default_explicit'``
    (found by ``tests/architectural/test_remediation_effectiveness.py``
    against its wheel-install venv, typer 0.27.2 + click 8.5.0).
    ``TyperOption`` is the one option class guaranteed to live in the same
    click universe as ``TyperCommand`` in both eras, and takes the same
    click-style keyword arguments.
    """
    return TyperOption(
        param_decls=[_MISSION_OPTION_NAME],
        expose_value=False,
        hidden=True,
        help="Accepted and ignored: this command is not mission-scoped.",
    )


def _with_ignored_mission_option(params: list[click.Parameter]) -> list[click.Parameter]:
    """Append the ignored ``--mission`` option unless ``params`` already declares one."""
    if any(_MISSION_OPTION_NAME in param.opts for param in params):
        return params
    return [*params, _ignored_mission_option()]


class MissionAgnosticCommand(TyperCommand):
    """Leaf command class that accepts-and-ignores ``--mission``.

    The shipped mission-step skill text (``packs/built-in/missions/
    mission-steps/**/prompt.md``) instructs agents to pass
    ``--mission <handle>`` to *every* spec-kitty command in multi-mission
    repos. Mission-scoped commands declare a real ``--mission`` option;
    mission-agnostic ones (``agent profile list`` and the like) rejected it
    with ``No such option: --mission``, so the instruction was contradicted
    by the CLI once per session (#3953). Appending a hidden, non-exposed
    ``--mission`` option here makes those commands accept and ignore the
    flag: the value parses and is discarded, the callback never sees it,
    and ``--help`` stays unchanged. Commands that declare their own
    ``--mission`` — matched by option name, not parameter name, since
    several declare it behind a ``feature`` parameter — are untouched.
    """

    def get_params(self, ctx: click.Context) -> list[click.Parameter]:
        return _with_ignored_mission_option(super().get_params(ctx))


class MissionAgnosticGroup(TyperGroup):
    """Group form of :class:`MissionAgnosticCommand` for sub-apps used as leaf commands.

    A sub-app registered via ``add_typer`` whose callback owns the options and
    which registers no commands (``charter list``) is a leaf surface at click
    level — its group object is what parses the options, so the ignored
    ``--mission`` rides on the group class.
    """

    def get_params(self, ctx: click.Context) -> list[click.Parameter]:
        return _with_ignored_mission_option(super().get_params(ctx))


def make_leaf_commands_mission_agnostic(app: typer.Typer) -> int:
    """Point every registered leaf command's click class at the mission-agnostic classes.

    Two leaf shapes exist. A registered command (``@app.command``) becomes a
    click Command and is retargeted to :class:`MissionAgnosticCommand`. A
    sub-app registered via ``add_typer`` that declares no commands of its own
    (callback-owned options, e.g. ``charter list``) is a leaf *group* and is
    retargeted to :class:`MissionAgnosticGroup`; anything else is a real
    group and is recursed into.

    Commands already carrying a custom click class are left alone — that
    class was chosen deliberately — and both mission-agnostic classes
    no-op for commands that declare a real ``--mission``. Idempotent.
    Returns the number of leaf commands retargeted.
    """
    retargeted = 0
    for info in app.registered_commands:
        if info.cls is None or info.cls is TyperCommand:
            info.cls = MissionAgnosticCommand
            retargeted += 1
    for group_info in app.registered_groups:
        sub = group_info.typer_instance
        if sub is None:
            continue
        if not sub.registered_commands and not sub.registered_groups:
            # ``info.cls`` defaults to a DefaultPlaceholder wrapping None.
            cls = getattr(sub.info.cls, "value", sub.info.cls)
            if cls is None or cls is TyperGroup:
                sub.info.cls = MissionAgnosticGroup
                retargeted += 1
        else:
            retargeted += make_leaf_commands_mission_agnostic(sub)
    return retargeted


def _should_use_simple_help() -> bool:
    """Choose a plain help renderer for narrow terminals or explicit opt-in."""
    raw = os.environ.get("SPEC_KITTY_SIMPLE_HELP", "").strip().lower()
    if is_truthy(raw):
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool(console.width < 100)


def _format_simple_help(group: TyperGroup, ctx: click.Context, formatter: click.HelpFormatter) -> None:
    """Render machine-friendly help without Rich tables/banner noise."""
    formatter.write_usage(ctx.command_path, "[OPTIONS] COMMAND [ARGS]...")

    if group.help:
        formatter.write_paragraph()
        formatter.write_text(group.help)

    options = []
    for param in group.get_params(ctx):
        record = param.get_help_record(ctx)
        if record is not None:
            options.append(record)
    if options:
        with formatter.section("Options"):
            formatter.write_dl(options)

    commands = []
    for name in group.list_commands(ctx):
        cmd = group.get_command(ctx, name)
        if cmd is None or cmd.hidden:
            continue
        commands.append((name, cmd.get_short_help_str()))
    if commands:
        with formatter.section("Commands"):
            formatter.write_dl(commands)


def _should_render_banner_for_invocation(argv: list[str] | None = None) -> bool:
    """Return True only for invocations that should render ASCII art."""
    # Agent/tool contexts should never receive decorative banner output.
    # It pollutes deterministic parsing and wastes tokens.
    if is_truthy(os.environ.get("SPEC_KITTY_NO_BANNER")):
        return False

    agent_env_markers = (
        "CLAUDECODE",
        "CLAUDE_CODE",
        "CODEX",
        "OPENCODE",
        "CURSOR_TRACE_ID",
    )
    if any(key in os.environ for key in agent_env_markers):
        return False

    tokens = [token.strip().lower() for token in (argv if argv is not None else sys.argv[1:]) if token.strip()]
    command = next((token for token in tokens if not token.startswith("-")), None)
    return command == "init"


def show_banner(force: bool = False) -> None:
    """Display the ASCII art banner with gradient styling."""
    if not force and not _should_render_banner_for_invocation():
        return

    banner_lines = BANNER.strip().split("\n")
    colors = ["bright_blue", "blue", "cyan", "bright_cyan", "white", "bright_white"]
    max_width = max((len(line) for line in banner_lines), default=0)

    styled_banner = Text()
    for index, line in enumerate(banner_lines):
        color = colors[index % len(colors)]
        padded_line = line.ljust(max_width)
        styled_banner.append(padded_line + "\n", style=color)

    try:
        pkg_version = version("spec-kitty-cli")
        version_text = f"v{pkg_version}"
    except PackageNotFoundError:
        version_text = "dev"

    console.print(Align.center(styled_banner))
    console.print(Align.center(Text(TAGLINE, style="italic bright_yellow")))
    console.print(Align.center(Text(version_text, style="dim cyan")))
    console.print()


def _render_nag_if_needed(ctx: typer.Context) -> None:
    """Consult the compat planner and render a nag message when appropriate.

    This is the WP08 hook.  It is called once per CLI invocation from
    ``callback()`` (the single chokepoint) *before* the schema gate runs.

    Design choice (Option C from WP08 spec): we make a separate planner call
    here specifically for nag rendering.  The schema gate (migration/gate.py)
    makes its own planner call for block enforcement.  The cost of two planner
    calls per invocation is low; the gain is clean separation of concerns and
    no disruption to the gate's existing contract.

    Key invariants:
    - Only renders for ALLOW_WITH_NAG decisions.
    - Never updates last_shown_at when the nag is suppressed (preserves the
      user's throttle window across CI/non-interactive runs).
    - Uses stderr so stdout consumers (``--json``) see clean output.
    - Color disabled when stderr is not a TTY.
    """
    # Fast-path: suppress early to avoid the planner call cost.
    if _should_suppress_nag():
        return

    try:
        # Deferred imports to avoid circular imports at module load time.
        from kernel.clock import now_utc  # noqa: PLC0415

        from specify_cli.compat import Decision  # noqa: PLC0415
        from specify_cli.compat import Invocation  # noqa: PLC0415
        from specify_cli.compat import NagCache  # noqa: PLC0415
        from specify_cli.compat import NagCacheRecord  # noqa: PLC0415
        from specify_cli.compat import plan as compat_plan  # noqa: PLC0415

        # Build Invocation from argv (best-effort; never raises).
        inv = Invocation.from_argv()

        # If Invocation itself says suppress, honour it (belt-and-suspenders).
        if inv.suppresses_nag():
            return

        result = compat_plan(inv)

        # Stash on ctx.obj so subcommands can read it without re-planning.
        if ctx.obj is None:
            ctx.obj = {}
        if isinstance(ctx.obj, dict):
            ctx.obj["compat_plan_result"] = result

        if result.decision != Decision.ALLOW_WITH_NAG:
            # ALLOW → nothing to render.
            # BLOCK_* → handled by the schema gate (migration/gate.py).
            return

        # Render the nag to stderr.
        # Use Literal "auto" when stderr is a TTY, None (no color) otherwise.
        from typing import Literal  # noqa: PLC0415

        _color: Literal["auto"] | None = "auto" if sys.stderr.isatty() else None
        stderr_console = CliConsole(stderr=True, color_system=_color)
        message = result.rendered_human.rstrip()
        if message:
            stderr_console.print(message)

        # Update last_shown_at in the nag cache so the throttle window starts.
        # This is intentionally NOT done when the nag is suppressed (CI / no-TTY).
        try:
            nag_cache = NagCache.default()
            existing = nag_cache.read()
            now = now_utc()
            if existing is not None:
                updated_record = replace(existing, last_shown_at=now)
            else:
                # No existing record — write a minimal one to record the show time.
                updated_record = NagCacheRecord(
                    cli_version_key=result.cli_status.installed_version,
                    latest_version=result.cli_status.latest_version,
                    latest_source=result.cli_status.latest_source,
                    fetched_at=now,
                    last_shown_at=now,
                )
            nag_cache.write(updated_record)
        except Exception:  # noqa: BLE001 — nag-cache write is best-effort; failure must not block the CLI
            pass  # Cache update failure is non-fatal.

    except Exception:  # noqa: BLE001 — nag rendering must never crash the CLI; planner errors are suppressed here
        # Fail open for nag rendering: if the planner errors, don't block the CLI.
        pass


def callback(ctx: typer.Context) -> None:
    """Display the banner when CLI is invoked without a subcommand."""
    if ctx.invoked_subcommand is None and "--help" not in sys.argv and "-h" not in sys.argv:
        click.echo(ctx.get_help(), color=ctx.color)

    # Teamspace CLI auth/upgrade readiness coordinator
    # (Priivacy-ai/spec-kitty#1093). First-gated on is_saas_sync_enabled();
    # no-ops when hosted mode is disabled. The coordinator owns the call to
    # _render_nag_if_needed() so downstream missions (WS2 auth, WS3 upgrade
    # UX) can extend behavior through one seam. Lazy import to avoid
    # module-load circularity (readiness/coordinator.py imports
    # _render_nag_if_needed back from this module at call time).
    from specify_cli.readiness import evaluate_readiness  # noqa: PLC0415

    evaluate_readiness(ctx)

    # WP09 (FR-007): emit "no upgrade available" notice when warranted.
    # Reuses should_check_version() — no parallel gate. The notifier itself
    # is fully exception-safe; the extra try/except here is defence in depth.
    try:
        command_name = ctx.invoked_subcommand or "help"
        # Suppress when the user has asked for quiet/json/help/version output:
        # the existing nag-suppression heuristic is the right gate.
        if not _should_suppress_nag():
            from specify_cli.core.version_checker import (  # noqa: PLC0415 — deferred import
                maybe_emit_no_upgrade_notice,
            )

            maybe_emit_no_upgrade_notice(command_name)
    except Exception:  # noqa: BLE001 — notifier must never block the CLI
        pass


def get_project_root_or_exit(start: Path | None = None, *, json_output: bool = False) -> Path:
    """Return the project root or exit 1, optionally emitting the JSON error contract.

    Existing callers retain their human-readable diagnostics unless they opt in.
    """
    project_root: Path | None = locate_project_root(start)
    if project_root is None:
        if json_output:
            console.emit_json(json_error("not_in_project", "Unable to locate the Spec Kitty project root (.kittify directory not found)."))
            raise typer.Exit(1)
        console.print("[red]Error:[/red] Unable to locate the Spec Kitty project root (.kittify directory not found).")
        console.print("[dim]Run this command from the project root or from a feature worktree under .worktrees/<feature>/.[/dim]")
        console.print("[dim]Tip: Initialize a project with 'spec-kitty init <name>' if one does not exist.[/dim]")
        raise typer.Exit(1)
    return project_root


def git_resolution_failure_message(
    exc: NotInsideRepositoryError | GitCommonDirUnavailableError,
    project_root: Path,
) -> str:
    """Build the actionable message for a charter-resolution git failure (#4123).

    ``spec-kitty init`` deliberately allows non-git init (canonical invariant
    01KQ84P1AJ8H3FPJN9J5C12CBY: non-git init is allowed; silent non-git init
    is not), so a user whose only mistake is a missing ``git init`` must be
    told exactly that -- never handed a raw traceback or a "re-run init"
    misdirection.
    """
    from charter.resolution import NotInsideRepositoryError

    if isinstance(exc, NotInsideRepositoryError):
        return f"This project is not inside a git repository. Run `git init` (and an initial commit) in {project_root} -- see the spec-kitty init output."
    # GitCommonDirUnavailableError's own message already names the recovery
    # ("Install a supported git binary and retry"), so it is surfaced verbatim.
    return str(exc)


def exit_git_resolution_failure(
    exc: NotInsideRepositoryError | GitCommonDirUnavailableError,
    project_root: Path,
    *,
    json_output: bool = False,
) -> NoReturn:
    """Render the git-resolution failure actionable message and exit 1 (#4123).

    Shared command-layer catch for the ``charter.resolution`` errors that
    escape when a ``spec-kitty init``-ed project was never ``git init``-ed.
    Callers that need their own console/JSON envelope (e.g. the charter
    subcommands' ``--json`` contract) build the text with
    :func:`git_resolution_failure_message` instead.
    """
    message = git_resolution_failure_message(exc, project_root)
    if json_output:
        console.emit_json(json_error("git_resolution_failed", message))
    else:
        console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(1) from exc


def check_version_compatibility(project_root: Path, command_name: str) -> None:
    """Check CLI/project version compatibility and exit if mismatch.

    Args:
        project_root: Path to project root (.kittify parent)
        command_name: Name of command being run (for should_check_version)

    Raises:
        typer.Exit(1) if version mismatch detected
    """
    from specify_cli.core.version_checker import (
        get_cli_version,
        get_project_version,
        compare_versions,
        format_version_error,
        should_check_version,
    )

    # Skip check for certain commands
    if not should_check_version(command_name):
        return

    cli_version = get_cli_version()
    project_version = get_project_version(project_root)

    # Handle missing metadata (legacy project)
    if project_version is None:
        console.print("[yellow]Warning:[/yellow] Project metadata not found (.kittify/metadata.yaml)")
        console.print("[yellow]Please run:[/yellow] spec-kitty upgrade")
        console.print()
        return  # Warn but don't block

    comparison, mismatch_type = compare_versions(cli_version, project_version)

    # Handle version mismatches
    if mismatch_type != "match":
        if mismatch_type == "unknown":
            console.print("[yellow]Warning:[/yellow] Unable to determine version compatibility")
            console.print(f"  CLI version: {cli_version}")
            console.print(f"  Project version: {project_version}")
            console.print()
            return  # Warn but don't block

        # Hard error for known version mismatches
        error_msg = format_version_error(cli_version, project_version, mismatch_type)
        console.print(error_msg)
        console.print()
        raise typer.Exit(1)


__all__ = [
    "BannerGroup",
    "callback",
    "exit_git_resolution_failure",
    "get_project_root_or_exit",
    "git_resolution_failure_message",
    "show_banner",
    "_render_nag_if_needed",
    "_should_suppress_nag",
]
