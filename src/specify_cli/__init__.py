#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "typer",
#     "rich",
#     "platformdirs",
#     "readchar",
#     "httpx",
# ]
# ///
"""
Spec Kitty CLI - setup tooling for Spec Kitty projects.

Usage:
    spec-kitty init
    spec-kitty init <project-name>
    spec-kitty init .
    spec-kitty init --here
"""

# Pre-import ``.kitty.env`` two-tier loader (FR-004/FR-004a/FR-005;
# contracts/kitty-env-loader.md C-LDR-1..7). Runs as the FIRST statements of
# this module -- before the SPEC_KITTY_TEST_MODE read below and before any
# other spec-kitty submodule is imported (C-LDR-2) -- so operator-configured
# env vars (incl. import-time-gated ones like SPEC_KITTY_SYNC_MINIMAL_IMPORT,
# see specify_cli/status/adapters.py) are already in os.environ by the time
# anything downstream reads them. specify_cli.bootstrap.env_file's own
# transitive imports are stdlib + kernel ONLY (arch-gated by
# tests/architectural/test_bootstrap_import_purity.py) -- it does not import
# specify_cli.core, which would force that package's heavy __init__ to run
# before this loader has even finished (see that module's docstring).
from specify_cli.bootstrap.env_file import load_operator_env_file  # noqa: E402

load_operator_env_file()

import logging  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
from collections.abc import Callable  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import TYPE_CHECKING, Any, TypeVar  # noqa: E402

T = TypeVar("T")


import typer  # noqa: E402

if TYPE_CHECKING:
    from rich.console import Console
    from specify_cli.cli import StepTracker

# Get version from package metadata
# Test mode: use environment override to ensure tests use source version
if os.environ.get("SPEC_KITTY_TEST_MODE") == "1":
    __version__ = os.environ.get("SPEC_KITTY_CLI_VERSION", "0.5.0-dev")
else:
    from specify_cli.version_utils import get_version

    __version__ = get_version()

_APP: typer.Typer | None = None


def root_callback(*args: Any, **kwargs: Any) -> Any:
    from specify_cli.cli.helpers import callback as _root_callback

    return _root_callback(*args, **kwargs)


def locate_project_root() -> Path | None:
    from specify_cli.core.project_resolver import locate_project_root as _locate_project_root

    return _locate_project_root()


def activate_mission(project_path: Path, mission_type: str, mission_display: str, console: "Console") -> str:
    """
    DEPRECATED: No-op function for backwards compatibility.

    As of v0.8.0, missions are selected per-feature during /spec-kitty.specify,
    not at the project level during init. This function is kept for backwards
    compatibility with existing init code but no longer sets an active mission.
    """
    # Just verify the mission directory exists
    kittify_root = project_path / ".kittify"
    missions_dir = kittify_root / "missions"
    mission_path = missions_dir / mission_type

    if mission_path.exists():
        return f"{mission_display} (per-feature selection)"
    else:
        console.print(f"[yellow]Note:[/yellow] Mission [cyan]{mission_display}[/cyan] templates will be available when you run [cyan]/spec-kitty.specify[/cyan].")
        return f"{mission_display} (templates pending)"


def version_callback(value: bool) -> None:
    """Display version and exit."""
    if value:
        from specify_cli.cli.console import console
        from specify_cli.distribution import resolve_distribution_profile

        # Identity flows through the DistributionProfile (the aggregated seam):
        # a fork's version_label wins, else its package_name.
        profile = resolve_distribution_profile()
        label = profile.version_label or profile.package_name
        console.print(
            f"{label} version {__version__}",
            soft_wrap=True,
            highlight=False,
            markup=False,
        )
        raise typer.Exit()


def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(  # noqa: ARG001
        None, "--version", "-v", callback=version_callback, is_eager=True, help="Show version and exit"
    ),
) -> None:
    """Main callback for root CLI setup."""
    import sys

    if "upgrade_intent" in ctx.meta:
        # The actual upgrade tail performs validated, configured global repair.
        # Even apply intent must not bootstrap before target/schema admission.
        return

    if ctx.meta.get("defer_root_bootstrap") is True:
        # Windows migration must relocate legacy state before global runtime reads.
        return

    next_fast_path = _is_next_invocation(sys.argv)
    live_work_hook_path = _is_live_work_hook_invocation(sys.argv)
    session_start_path = _is_session_start_invocation(sys.argv)
    if not next_fast_path and not live_work_hook_path and not session_start_path:
        root_callback(ctx)

        # FR-002: Ensure global runtime (~/.kittify/) is populated and current.
        # Must run BEFORE check_version_pin() so global assets are available.
        from specify_cli.runtime.agent_commands import ensure_global_agent_commands
        from specify_cli.runtime.agent_skills import ensure_global_agent_skills
        from specify_cli.runtime.bootstrap import ensure_runtime

        ensure_runtime()
        ensure_global_agent_skills()
        if not _is_doctor_skills_invocation(sys.argv):
            ensure_global_agent_commands()

    if not live_work_hook_path and not session_start_path:
        # The live-work hook is passive capture on the harness's per-tool-call
        # path, not a project command: the schema gate may SystemExit on a stale
        # project (breaking the hook's own always-exit-0 contract) and its import
        # chain alone outweighs the 4 s hook budget, so neither startup gate
        # runs there (#4353 fix round). session-start shares that exit-0 contract
        # (#4703): check_schema_version's SystemExit on a stale project would
        # break the Claude Code SessionStart hook, so it skips the gates too.
        _run_startup_project_gates(ctx)


def _run_startup_project_gates(ctx: typer.Context) -> None:
    """Run project-local safety gates shared by normal and startup-fast paths."""
    from specify_cli.runtime.bootstrap import check_version_pin

    # F-Pin-001 / 1A-16: Warn on runtime.pin_version for all project invocations.
    project_root = locate_project_root()
    if project_root is not None:
        check_version_pin(project_root)

    # FR-019 / FR-020: Schema version gate — refuse unmigrated or newer-than-CLI
    # projects before any command runs.  Exempt upgrade/init/--version/--help.
    if project_root is not None:
        from specify_cli.migration.gate import check_schema_version

        check_schema_version(project_root, invoked_subcommand=ctx.invoked_subcommand)


def _build_app() -> typer.Typer:
    from specify_cli.cli.commands import register_commands
    from specify_cli.cli.helpers import BannerGroup, make_leaf_commands_mission_agnostic

    app = typer.Typer(
        name="spec-kitty",
        help=("Setup tool for Spec Kitty spec-driven development projects.\n\nSet SPEC_KITTY_NO_UPGRADE_CHECK=1 to disable the upgrade-check notice."),
        add_completion=True,
        context_settings={"help_option_names": ["--help", "-h"]},
        invoke_without_command=True,
        cls=BannerGroup,
    )
    app.callback()(main_callback)
    if not _is_live_work_hook_invocation(sys.argv):
        # The init command's import graph (charter/jsonschema/provisioning)
        # is the heaviest single registration; the per-tool-call hook path
        # (#4353 fix round) never invokes it, so it stays unimported there.
        from specify_cli.cli.commands.init import register_init_command

        register_init_command(
            app,
            console=_get_console(),
            show_banner=_get_show_banner(),
            activate_mission=activate_mission,
            ensure_executable_scripts=ensure_executable_scripts,
        )
    register_commands(app)
    # #3953: the mission-step skill text says to pass --mission to every
    # spec-kitty command in multi-mission repos, so mission-agnostic leaf
    # commands accept-and-ignore it instead of exiting 2 with
    # "No such option: --mission". Runs after every registration path above
    # (including the register_commands fast paths) so all leaves are covered.
    make_leaf_commands_mission_agnostic(app)
    return app


def _is_doctor_skills_invocation(argv: list[str]) -> bool:
    """Return True for ``spec-kitty doctor skills`` invocations.

    ``doctor skills`` audits and reports slash-command gaps itself. Running the
    startup slash-command repair first would hide those gaps from the doctor's
    machine-readable repair payload.
    """
    args = [arg for arg in argv[1:] if not arg.startswith("-")]
    return len(args) >= 2 and args[0] == "doctor" and args[1] == "skills"


def _is_next_invocation(argv: list[str]) -> bool:
    """Return True for direct ``spec-kitty next`` invocations.

    ``next`` is the startup-sensitive mission loop command. It performs its
    own project-root resolution, charter preflight, and command validation, so
    the root callback must not run global asset repair on this path.
    """
    for arg in argv[1:]:
        if arg in {"--help", "-h"}:
            return False
        if arg == "next":
            return True
        if not arg.startswith("-"):
            return False
    return False


def _is_live_work_hook_invocation(argv: list[str]) -> bool:
    """Return True for direct ``spec-kitty live-work hook <harness>`` invocations.

    The hook runs synchronously on the harness's per-tool-call path
    (PreToolUse/PostToolUse, spec-kitty#4353 fix round), so it must not pay
    the global runtime bootstrap (~/.kittify asset repair) any more than the
    full command-registry import — the same startup-fast-path posture as
    ``next``. Its publisher resolves relay credentials per-repo, never from
    the global runtime.
    """
    args = [arg for arg in argv[1:] if not arg.startswith("-")]
    return len(args) >= 2 and args[0] == "live-work" and args[1] == "hook"


def _is_session_start_invocation(argv: list[str]) -> bool:
    """Return True for direct ``spec-kitty session-start`` invocations.

    ``session-start`` is the Claude Code ``SessionStart`` lifecycle hook. Its
    module contract is an unconditional exit 0 — it must NEVER cause a session to
    fail, regardless of any error in the spec-kitty stack. ``ensure_runtime`` and
    the startup project gates run in ``main_callback`` *before* dispatch, outside
    ``session_start()``'s own ``except Exception: pass`` guard, so a global
    runtime failure (e.g. #4703's Windows self-held-lock read) or the schema
    gate's ``SystemExit`` on a stale project would abort the hook with exit 1.
    Both must be skipped here — the same startup-fast-path posture as the
    live-work hook — so ``session_start()`` alone owns the exit-0 guarantee.
    ``session_start()`` does its own project-root resolution and reads only
    project-local surfaces, so it needs no global ``~/.kittify`` asset repair.
    """
    args = [arg for arg in argv[1:] if not arg.startswith("-")]
    return len(args) >= 1 and args[0] == "session-start"


def _get_app() -> typer.Typer:
    global _APP
    if _APP is None:
        _APP = _build_app()
    return _APP


def _get_console() -> Any:
    from specify_cli.cli.console import console

    return console


def _get_show_banner() -> Any:
    from specify_cli.cli.helpers import show_banner

    return show_banner


def __getattr__(name: str) -> Any:
    if name == "app":
        return _get_app()
    raise AttributeError(name)


def _compute_execute_mode(mode: int) -> int:
    new_mode = mode
    if mode & 0o400:
        new_mode |= 0o100
    if mode & 0o040:
        new_mode |= 0o010
    if mode & 0o004:
        new_mode |= 0o001
    if not (new_mode & 0o100):
        new_mode |= 0o100
    return new_mode


def _try_chmod_script(script: Path, scripts_root: Path) -> tuple[bool, str | None]:
    try:
        if script.is_symlink() or not script.is_file():
            return False, None
        try:
            with script.open("rb") as f:
                if f.read(2) != b"#!":
                    return False, None
        except Exception:
            return False, None
        mode = script.stat().st_mode
        if mode & 0o111:
            return False, None
        os.chmod(script, _compute_execute_mode(mode))
        return True, None
    except Exception as e:
        return False, f"{script.relative_to(scripts_root)}: {e}"


def _report_chmod_results(tracker: "StepTracker | None", updated: int, failures: list[str]) -> None:
    if tracker:
        detail = f"{updated} updated" + (f", {len(failures)} failed" if failures else "")
        tracker.add("chmod", "Set script permissions recursively")
        (tracker.error if failures else tracker.complete)("chmod", detail)
    else:
        console = _get_console()
        if updated:
            console.print(f"[cyan]Updated execute permissions on {updated} script(s) recursively[/cyan]")
        if failures:
            console.print("[yellow]Some scripts could not be updated:[/yellow]")
            for f in failures:
                console.print(f"  - {f}")


def ensure_executable_scripts(project_path: Path, tracker: "StepTracker | None" = None) -> None:
    """Ensure POSIX .sh scripts under .kittify/scripts (recursively) have execute bits (no-op on Windows)."""
    if os.name == "nt":
        return  # Windows: skip silently
    scripts_root = project_path / ".kittify" / "scripts"
    if not scripts_root.is_dir():
        return
    failures: list[str] = []
    updated = 0
    for script in scripts_root.rglob("*.sh"):
        was_updated, error = _try_chmod_script(script, scripts_root)
        if was_updated:
            updated += 1
        if error:
            failures.append(error)
    _report_chmod_results(tracker, updated, failures)


_JSON_VALUE_OPTIONS = {
    "--agent",
    "--answer",
    "--decision-id",
    "--feature",
    "--kind",
    "--mission",
    "--mode",
    "--provider",
    "--query",
    "--result",
    "--status",
    "--target",
    "--target-branch",
    "--tool",
}


def _argv_requests_json_mode(argv: list[str]) -> bool:
    """Return True when raw argv contains ``--json`` as a flag, not a value."""
    skip_next = False
    for arg in argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if arg == "--":
            return False
        if arg == "--json":
            return True
        if arg.startswith("--") and "=" not in arg:
            skip_next = arg in _JSON_VALUE_OPTIONS
            continue
        skip_next = False
    return False


def _assemble_app() -> typer.Typer:
    """Import-check the events adapter, then assemble the Typer app.

    Pure import/registration work (the events availability check exits before
    any command runs), which is what makes it safe to retry after a bytecode
    heal — see ``main()``.
    """
    # Check for spec-kitty-events library availability (required for 2.x branch)
    from specify_cli.events.adapter import EventAdapter

    if not EventAdapter.check_library_available():
        _get_console().print(f"[red]{EventAdapter.get_missing_library_error()}[/red]")
        raise typer.Exit(1)

    return _get_app()


def _invoke_unguarded(operation: Callable[[], T], **_kwargs: Any) -> T:
    """Run *operation* as-is (pre-#4124 behavior, used only as a fallback)."""
    return operation()


def _warn_bytecode_healed(removed: int) -> None:
    """Tell the operator an interrupted install was repaired, once, on stderr."""
    logging.getLogger("specify_cli").warning(
        "repaired %d stale bytecode cache file(s) left by an interrupted install; if this recurs, reinstall spec-kitty",
        removed,
    )


def _guarded_read_error_json_payload(exc: Any) -> dict[str, Any]:
    """Build the ``error``/``kind``/``path`` envelope (``contracts/error-envelope.md``)."""
    return {"error": str(exc), "kind": type(exc).__name__, "path": exc.path}


def _print_guarded_read_error(exc: Any, *, json_mode: bool) -> None:
    """Render *exc* per the hook contract: one JSON object on stdout, or one
    text line on stderr — never both (INV-1)."""
    if json_mode:
        import json

        print(json.dumps(_guarded_read_error_json_payload(exc)))
    else:
        print(f"Error: {exc}", file=sys.stderr)


def _run_app_with_error_hook(app: typer.Typer, *, json_mode: bool) -> None:
    """Invoke *app*, presenting a ``GuardedReadError`` uniformly at exit 1.

    The single global CLI error-presentation authority registered on the
    top-level app (FR-002/D2, ``contracts/error-envelope.md``, INV-4): a
    ``GuardedReadError`` (or subclass) raised by any command is rendered as a
    clean text line (stderr, no ``--json``) or a JSON object (stdout,
    ``--json``), then the process exits **1**. A Typer *usage* error (missing
    arg, bad option) is a ``SystemExit(2)`` raised inside ``app()`` itself —
    never a ``GuardedReadError`` — so it is never intercepted here (INV-2).
    Any other exception re-raises untouched so a genuine bug still surfaces
    as a traceback (INV-3).
    """
    from kernel.errors import GuardedReadError

    try:
        app()
    except GuardedReadError as exc:
        _print_guarded_read_error(exc, json_mode=json_mode)
        raise SystemExit(1) from exc


def _load_bytecode_heal_invoker() -> Callable[..., Any]:
    """Return ``invoke_with_bytecode_heal``, or a pass-through if unreachable.

    The heal module's own ``.pyc`` can be the corrupted one; delete just that
    cache file and retry the import once before falling back to running the
    CLI unguarded (#4124).
    """
    try:
        from specify_cli.bytecode_heal import invoke_with_bytecode_heal

        return invoke_with_bytecode_heal
    except Exception:
        import importlib
        from importlib.util import cache_from_source

        own_cache = Path(cache_from_source(str(Path(__file__).with_name("bytecode_heal.py"))))
        try:
            own_cache.unlink(missing_ok=True)
        except OSError:
            return _invoke_unguarded
        importlib.invalidate_caches()
        try:
            from specify_cli.bytecode_heal import invoke_with_bytecode_heal

            return invoke_with_bytecode_heal
        except Exception:
            return _invoke_unguarded


def main() -> None:
    # FR-130 / FR-131: Install the CLI logging bootstrap early — before the
    # Typer app runs — so that warnings.warn(...) calls (including
    # CharterCatalogMissWarning from charter.activation._catalog_miss) are routed through
    # the logging subsystem and appear in the operator's terminal.
    # This is additive-only: if a handler is already attached, no second
    # handler is installed (no double-printing).
    from specify_cli.cli.logging_bootstrap import install_cli_logging_bootstrap

    # Machine mode: when invoked with ``--json``, agents commonly capture the
    # merged ``2>&1`` stream and parse it — so diagnostic warnings/logs on stderr
    # would corrupt the JSON. Run the bootstrap in silent mode so a successful
    # ``--json`` run emits only the JSON object (errors are still emitted as JSON
    # on stdout by the commands themselves).
    json_mode = _argv_requests_json_mode(sys.argv)
    install_cli_logging_bootstrap(json_mode=json_mode)

    # Ensure UTF-8 encoding on Windows to handle Unicode characters in git output
    # Fixes: https://github.com/Priivacy-ai/spec-kitty/issues/66
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            # Python < 3.7 or reconfigure not available
            pass

    # Shell completion is latency-critical: every TAB press spawns this process
    # with a ``_SPEC_KITTY_COMPLETE`` instruction.  Serve command/subcommand-name
    # candidates from a small manifest instead of importing the whole command
    # tree (NFR-001 / SC-003, ~500 ms budget).  Returns ``None`` — falling
    # through to the full app — when completion is not requested or when an
    # option token is present (options are out of the manifest's scope).
    from specify_cli.completion import maybe_run_completion

    completion_exit = maybe_run_completion(sys.argv, os.environ)
    if completion_exit is not None:
        sys.stdout.flush()
        sys.stderr.flush()
        raise SystemExit(completion_exit)

    # Check for spec-kitty-events library availability (required for 2.x branch)
    # plus app assembly run inside the bytecode-heal wrapper (#4124): an
    # interrupted install can leave truncated ``.pyc`` bytecode that kills the
    # module-level ``specify_cli.upgrade`` import chain before any command
    # runs. Assembly is pure import/registration work, so a heal-and-retry
    # here is side-effect free; the command invocation itself stays outside
    # the wrapper so a mid-command failure is never re-run.
    app = _load_bytecode_heal_invoker()(_assemble_app, on_healed=_warn_bytecode_healed)
    _run_app_with_error_hook(app, json_mode=json_mode)


__all__ = ["main", "app", "__version__"]

if __name__ == "__main__":
    main()
