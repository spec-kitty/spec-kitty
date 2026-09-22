"""Agent configuration management commands."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer
from specify_cli.cli.console import console
from rich.table import Table

from specify_cli.asset_preservation import ManifestProver, guard_destructive_removal
from specify_cli.core.config import AGENT_COMMAND_CONFIG
from specify_cli.core.env import is_truthy
from specify_cli.core.agent_config import (
    load_agent_config,
    save_agent_config,
    AgentConfig,
    AgentConfigError,
)
from specify_cli.core.utils import write_text_within_directory
from specify_cli.runtime.agent_commands import get_global_command_dir
from specify_cli.session_presence.hooks.claude_code_hook import ClaudeCodeHookRegistrar
from specify_cli.upgrade.migrations.m_0_9_1_complete_lane_migration import (
    AGENT_DIR_TO_KEY,
    CompleteLaneMigration,
)
from specify_cli.skills._agent_roster import SUPPORTED_AGENTS as _SKILL_ONLY_ROSTER
from specify_cli.task_utils import find_repo_root

from .surface_presence import SurfacePresenceIndex

#: Command wired into harness post-edit hooks when ``lint_on_edit`` is enabled.
#: It takes no path argument — the edited file is delivered on stdin by the
#: harness and resolved by ``spec-kitty lint`` (see lint.py).
LINT_HOOK_COMMAND = "spec-kitty lint --json"
#: Claude PostToolUse matcher scoping the hook to file-editing tools.
LINT_HOOK_MATCHER = "Edit|Write"
_ENABLED_LABEL = "[green]enabled[/green]"
_DISABLED_LABEL = "[yellow]disabled[/yellow]"

app = typer.Typer(
    name="config",
    help="Manage project AI agent configuration (add, remove, list agents)",
    no_args_is_help=True,
)

# Reverse mapping: key to (dir, subdir)
KEY_TO_AGENT_DIR = {
    AGENT_DIR_TO_KEY[agent_dir]: (agent_dir, subdir)
    for agent_dir, subdir in CompleteLaneMigration.AGENT_DIRS
    if agent_dir in AGENT_DIR_TO_KEY
}
#: Derived from the single roster authority (#1941); no standalone literal
#: tool-universe lives here. Patching ``_agent_roster.SUPPORTED_AGENTS`` and
#: reloading this module flows straight through to ``SKILL_ONLY_AGENTS`` and the
#: ``VALID_AGENTS`` union.
SKILL_ONLY_AGENTS = set(_SKILL_ONLY_ROSTER)
GLOBAL_COMMAND_AGENTS = frozenset(AGENT_COMMAND_CONFIG)
VALID_AGENTS = set(AGENT_DIR_TO_KEY.values()) | SKILL_ONLY_AGENTS


def _display_path(path: Path) -> str:
    """Render paths compactly for CLI output."""
    try:
        rel = path.relative_to(Path.home())
        label = f"~/{rel.as_posix()}"
    except ValueError:
        label = path.as_posix()
    return label.rstrip("/") + "/"


def _agent_location(
    repo_root: Path,
    agent_key: str,
    presence: SurfacePresenceIndex | None = None,
) -> tuple[Path | None, str, bool]:
    """Return the managed command/skill location for an agent.

    Install state ("does the managed surface exist?") is resolved through the
    surface contract via ``presence`` when supplied, so ``agent config`` no
    longer recomputes its own per-agent existence probe. The *labels* below stay
    owned here because they are part of the frozen ``agent config`` interface.
    """

    def _exists(path: Path) -> bool:
        return presence.exists(agent_key) if presence is not None else path.exists()

    if agent_key in GLOBAL_COMMAND_AGENTS:
        path = get_global_command_dir(agent_key)
        return path, f"{_display_path(path)} (global)", _exists(path)

    if agent_key in SKILL_ONLY_AGENTS:
        path = repo_root / ".agents" / "skills"
        return path, ".agents/skills/ (project skills)", _exists(path)

    agent_dir_info = KEY_TO_AGENT_DIR.get(agent_key)
    if agent_dir_info:
        agent_dir, subdir = agent_dir_info
        path = repo_root / agent_dir / subdir
        return path, f"{agent_dir}/{subdir}/", _exists(path)

    return None, "unknown agent", False


def _project_agent_root(repo_root: Path, agent_key: str) -> Path | None:
    """Return the legacy project-local root for command-layer agents."""
    agent_dir_info = KEY_TO_AGENT_DIR.get(agent_key)
    if agent_dir_info is None:
        return None
    agent_root, _ = agent_dir_info
    return repo_root / agent_root


def _project_agent_surface(repo_root: Path, agent_key: str) -> tuple[Path, Path, str] | None:
    """Return root, managed surface, and display label for a project agent."""
    agent_dir_info = KEY_TO_AGENT_DIR.get(agent_key)
    if agent_dir_info is None:
        return None
    agent_root, subdir = agent_dir_info
    root = repo_root / agent_root
    return root, root / subdir, f"{agent_root}/{subdir}/"


def _remove_project_agent_surface(repo_root: Path, agent_key: str) -> tuple[bool, str]:
    """Remove only the managed command surface for an agent.

    Routes the destructive removal through ``guard_destructive_removal`` — the
    ONE prove-or-preserve chokepoint (charter L463-479 / NFR-006) — instead of
    a raw ``rmtree``/``unlink`` literal (#4907, #2691). ``ManifestProver``
    proves ownership from the command-skills manifest; anything unprovable
    (untracked, drifted, or a mixed manifest+user directory — dir-level
    routing gives pure-owned⇒remove-whole, any-unproven⇒preserve-whole via
    ``_prove_dir``) is preserved in place, never deleted. The return tuple is
    verdict-driven so a preserved surface can never report "Removed"
    (FR-014/FR-015): today's bug is that ``root.rmdir()`` raising ``OSError``
    on a non-empty (preserved) dir was caught and still returned "Removed".
    """
    paths = _project_agent_surface(repo_root, agent_key)
    if paths is None:
        return False, f"Unknown agent: {agent_key}"

    root, surface, label = paths
    if not surface.exists():
        return False, f"{label} already removed"

    try:
        verdict = guard_destructive_removal(
            surface,
            repo_root,
            prover=ManifestProver(check_command=True),
            is_tree=surface.is_dir(),
            backup_parent=None,
        )
    except OSError as exc:
        return False, f"Failed to remove {label}: {exc}"

    if not verdict.owned:
        return False, verdict.diagnostic

    # verdict.owned: the guard already removed `surface` itself. This is the
    # single remaining destructive literal — an empty-only prune of the
    # now-possibly-empty parent `root`; it only runs on the owned branch, so
    # it can never fire (and never report "Removed") on a preserved surface.
    try:
        root.rmdir()
        return True, f"Removed {root.name}/"
    except OSError:
        return True, f"Removed {label}"


def _load_config_or_exit(repo_root: Path) -> AgentConfig:
    try:
        return load_agent_config(repo_root)
    except AgentConfigError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


def _register_skill_agent(
    repo_root: Path,
    config: AgentConfig,
    agent_key: str,
    *,
    update_config: bool = True,
) -> tuple[bool, str | None]:
    """Install command skills for skill-only agents and update config."""
    from specify_cli.skills import command_installer  # noqa: PLC0415
    from specify_cli.skills.vibe_config import ensure_project_skill_path  # noqa: PLC0415

    try:
        report = command_installer.install(repo_root, agent_key)
        if agent_key == "vibe":
            ensure_project_skill_path(repo_root)
        installed = len(report.added) + len(report.reused_shared)
        if update_config:
            config.available.append(agent_key)
        console.print(
            f"[green]✓[/green] Registered {agent_key} "
            f"({installed} command skills in .agents/skills/)"
        )
        return True, None
    except Exception as exc:
        return False, f"Failed to install {agent_key} skills: {exc}"


def _register_global_command_agent(config: AgentConfig, agent_key: str) -> None:
    """Register a slash-command agent whose command files are global."""
    global_dir = get_global_command_dir(agent_key)
    config.available.append(agent_key)
    console.print(
        f"[green]✓[/green] Registered {agent_key} "
        f"(global commands at {_display_path(global_dir)})"
    )


def _create_project_agent_dir(repo_root: Path, config: AgentConfig, agent_key: str) -> tuple[bool, str | None]:
    """Fallback for legacy project-local command agents."""
    agent_dir_info = KEY_TO_AGENT_DIR.get(agent_key)
    if not agent_dir_info:
        return False, f"Unknown agent: {agent_key}"

    agent_root, subdir = agent_dir_info
    agent_dir = repo_root / agent_root / subdir

    try:
        agent_dir.mkdir(parents=True, exist_ok=True)
        missions_dir = repo_root / ".kittify" / "missions" / "software-dev" / "command-templates"

        if missions_dir.exists():
            for template_file in missions_dir.glob("*.md"):
                dest_file = agent_dir / f"spec-kitty.{template_file.name}"
                shutil.copy2(template_file, dest_file)

        config.available.append(agent_key)
        console.print(f"[green]✓[/green] Added {agent_root}/{subdir}/")
        return True, None
    except OSError as exc:
        return False, f"Failed to create {agent_root}/{subdir}/: {exc}"


def _remove_orphaned_agent_dirs(repo_root: Path, config: AgentConfig) -> bool:
    """Remove project-local command dirs for agents not in config."""
    console.print("[cyan]Checking for orphaned directories...[/cyan]")
    changes_made = False
    all_agent_keys = set(AGENT_DIR_TO_KEY.values())
    orphaned = [
        key
        for key in all_agent_keys
        if key not in config.available
        and (surface := _project_agent_surface(repo_root, key)) is not None
        and surface[1].exists()
    ]

    for agent_key in orphaned:
        removed, message = _remove_project_agent_surface(repo_root, agent_key)
        if removed:
            removed_label = message.removeprefix("Removed ")
            console.print(f"  [green]✓[/green] Removed orphaned {removed_label}")
            changes_made = True
        elif message.startswith("Preserved "):
            # Verdict-driven preserve (FR-015): not an error, so it must not
            # read as one — the surface was deliberately left in place because
            # ownership was unprovable.
            console.print(f"  [yellow]⚠[/yellow] {message}")
        else:
            console.print(f"  [red]✗[/red] {message}")

    return changes_made


def _skill_agent_already_installed(repo_root: Path, agent_key: str) -> bool:
    """Return True when *agent_key* already owns a command-skills manifest entry.

    ``sync --create-missing`` must only CREATE a genuinely missing skill
    install, never refresh one that already exists — refreshing an already-
    installed agent is exactly how a normal sync silently replaced
    repository-pinned release/hash values with whatever the executing host
    CLI happened to render (#2691 manifest half). A missing/corrupt manifest
    is treated as "not yet installed" so the existing (already safe) install
    path still runs and fails closed on any real drift.
    """
    from specify_cli.skills import manifest_store  # noqa: PLC0415
    from specify_cli.skills.manifest_errors import ManifestError  # noqa: PLC0415

    try:
        manifest = manifest_store.load(repo_root)
    except (ManifestError, OSError):
        return False
    return any(agent_key in entry.agents for entry in manifest.entries)


def _check_or_create_configured_agent_dirs(repo_root: Path, config: AgentConfig) -> bool:
    """Check configured managed surfaces and create legacy local dirs if needed."""
    console.print("\n[cyan]Checking for missing directories...[/cyan]")
    changes_made = False
    errors_found = False
    missions_dir = repo_root / ".kittify" / "missions" / "software-dev" / "command-templates"

    for agent_key in config.available:
        if agent_key in GLOBAL_COMMAND_AGENTS:
            global_dir = get_global_command_dir(agent_key)
            if global_dir.exists():
                console.print(
                    f"  [green]✓[/green] Global commands present for {agent_key} at {_display_path(global_dir)}"
                )
            else:
                console.print(
                    f"  [yellow]⚠[/yellow] Global commands missing for {agent_key} at {_display_path(global_dir)}"
                )
            continue

        if agent_key in SKILL_ONLY_AGENTS:
            if _skill_agent_already_installed(repo_root, agent_key):
                console.print(f"  [green]✓[/green] Skill commands present for {agent_key} in .agents/skills/")
                continue
            ok, error = _register_skill_agent(
                repo_root,
                config,
                agent_key,
                update_config=False,
            )
            if ok:
                changes_made = True
            elif error:
                console.print(f"  [red]✗[/red] {error}")
                errors_found = True
            continue

        agent_dir_info = KEY_TO_AGENT_DIR.get(agent_key)
        if not agent_dir_info:
            console.print(f"  [yellow]⚠[/yellow] Unknown agent: {agent_key}")
            errors_found = True
            continue

        agent_root, subdir = agent_dir_info
        agent_dir = repo_root / agent_root / subdir
        if agent_dir.exists():
            continue

        try:
            agent_dir.mkdir(parents=True, exist_ok=True)
            if missions_dir.exists():
                for template_file in missions_dir.glob("*.md"):
                    dest_file = agent_dir / f"spec-kitty.{template_file.name}"
                    shutil.copy2(template_file, dest_file)

            console.print(f"  [green]✓[/green] Created {agent_root}/{subdir}/")
            changes_made = True
        except OSError as exc:
            console.print(f"  [red]✗[/red] Failed to create {agent_root}/{subdir}/: {exc}")
            errors_found = True

    if errors_found:
        raise typer.Exit(1)

    return changes_made


@app.command(name="list")
def list_agents():
    """List configured agents and their status."""
    try:
        repo_root = find_repo_root()
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Load config
    config = _load_config_or_exit(repo_root)

    if not config.available:
        console.print("[yellow]No agents configured.[/yellow]")
        console.print("\nRun 'spec-kitty init' or use 'spec-kitty agent config add' to add agents.")
        return

    # Resolve install state through the surface contract (WP07): the plan is the
    # source of truth for "is this tool's managed surface present?".
    presence = SurfacePresenceIndex.build(
        repo_root, config.available, global_command_dir=get_global_command_dir
    )

    # Display configured agents
    console.print("[cyan]Configured agents:[/cyan]")
    for agent_key in config.available:
        _, location, exists = _agent_location(repo_root, agent_key, presence)
        status = "✓" if exists else "⚠"
        console.print(f"  {status} {agent_key} ({location})")

    # Show auto-commit setting
    auto_commit_label = _ENABLED_LABEL if config.auto_commit else _DISABLED_LABEL
    console.print(f"\n[cyan]Auto-commit:[/cyan] {auto_commit_label}")
    if not config.auto_commit:
        console.print("[dim]  Agents will stage changes but not create commits unless explicitly instructed.[/dim]")
        console.print("[dim]  Override per-command with --auto-commit flag.[/dim]")

    # Show available but not configured
    all_agent_keys = VALID_AGENTS
    not_configured = all_agent_keys - set(config.available)

    if not_configured:
        console.print("\n[dim]Available but not configured:[/dim]")
        for agent_key in sorted(not_configured):
            console.print(f"  - {agent_key}")


@app.command(name="add")
def add_agents(
    agents: list[str] = typer.Argument(..., help="Agent keys to add (e.g., claude codex)"),
):
    """Add agents to the project.

    Creates agent directories and updates config.yaml.

    Example:
        spec-kitty agent config add claude codex
    """
    try:
        repo_root = find_repo_root()
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Load current config
    config = _load_config_or_exit(repo_root)

    # Validate agent keys — command-layer agents come from AGENT_DIR_TO_KEY;
    # skill-only agents have their own installer path.
    invalid = [a for a in agents if a not in VALID_AGENTS]
    if invalid:
        console.print(f"[red]Error:[/red] Invalid agent keys: {', '.join(invalid)}")
        console.print(f"\nValid agents: {', '.join(sorted(VALID_AGENTS))}")
        raise typer.Exit(1)

    added = []
    already_configured = []
    errors = []

    for agent_key in agents:
        # Check if already configured
        if agent_key in config.available:
            already_configured.append(agent_key)
            continue

        if agent_key in SKILL_ONLY_AGENTS:
            ok, error = _register_skill_agent(repo_root, config, agent_key)
            if ok:
                added.append(agent_key)
            elif error:
                errors.append(error)
            continue

        if agent_key in GLOBAL_COMMAND_AGENTS:
            _register_global_command_agent(config, agent_key)
            added.append(agent_key)
            continue

        ok, error = _create_project_agent_dir(repo_root, config, agent_key)
        if ok:
            added.append(agent_key)
        elif error:
            errors.append(error)

    # Save updated config
    if added:
        save_agent_config(repo_root, config)
        console.print(f"\n[cyan]Updated config.yaml:[/cyan] added {', '.join(added)}")

    if already_configured:
        console.print(f"\n[dim]Already configured:[/dim] {', '.join(already_configured)}")

    if errors:
        console.print("\n[red]Errors:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        raise typer.Exit(1)


@app.command(name="remove")
def remove_agents(
    agents: list[str] = typer.Argument(..., help="Agent keys to remove"),
    keep_config: bool = typer.Option(
        False,
        "--keep-config",
        help="Keep in config.yaml but delete directory",
    ),
):
    """Remove agents from the project.

    Deletes agent directories and updates config.yaml.

    Example:
        spec-kitty agent config remove codex gemini
    """
    try:
        repo_root = find_repo_root()
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Load current config
    config = _load_config_or_exit(repo_root)

    # Validate agent keys — command-layer agents come from AGENT_DIR_TO_KEY;
    # skill-only agents have their own installer path.
    invalid = [a for a in agents if a not in VALID_AGENTS]
    if invalid:
        console.print(f"[red]Error:[/red] Invalid agent keys: {', '.join(invalid)}")
        console.print(f"\nValid agents: {', '.join(sorted(VALID_AGENTS))}")
        raise typer.Exit(1)

    removed = []
    removed_from_config = []
    errors = []

    for agent_key in agents:
        if agent_key in SKILL_ONLY_AGENTS:
            from specify_cli.skills import command_installer
            try:
                report = command_installer.remove(repo_root, agent_key)
                removed.append(agent_key)
                console.print(f"[green]✓[/green] Removed skills for {agent_key} ({len(report.deleted)} files deleted)")
            except Exception as e:
                errors.append(f"Failed to remove skills for {agent_key}: {e}")
            # Update config (unless --keep-config)
            if not keep_config and agent_key in config.available:
                config.available.remove(agent_key)
                removed_from_config.append(agent_key)
            continue

        surface_removed, message = _remove_project_agent_surface(repo_root, agent_key)
        if surface_removed:
            removed.append(agent_key)
            console.print(f"[green]✓[/green] {message}")
        else:
            console.print(f"[dim]• {message}[/dim]")

        # Update config (unless --keep-config)
        if not keep_config and agent_key in config.available:
            config.available.remove(agent_key)
            removed_from_config.append(agent_key)

    # Save updated config
    if not keep_config and removed_from_config:
        save_agent_config(repo_root, config)
        console.print(f"\n[cyan]Updated config.yaml:[/cyan] removed {', '.join(removed_from_config)}")

    if errors:
        console.print("\n[yellow]Warnings:[/yellow]")
        for error in errors:
            console.print(f"  - {error}")


@app.command(name="status")
def agent_status():
    """Show which agents are configured vs present on filesystem.

    Identifies:
    - Configured and present (✓)
    - Configured but missing (⚠)
    - Not configured but present (orphaned) (✗)
    """
    try:
        repo_root = find_repo_root()
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Load config
    config = _load_config_or_exit(repo_root)

    # Check filesystem for each agent
    table = Table(title="Agent Status")
    table.add_column("Agent Key", style="cyan")
    table.add_column("Directory", style="dim")
    table.add_column("Configured", justify="center")
    table.add_column("Exists", justify="center")
    table.add_column("Status")

    all_agent_keys = sorted(VALID_AGENTS)

    # Resolve install state through the surface contract (WP07) for every known
    # tool, so the status table no longer recomputes existence per agent.
    presence = SurfacePresenceIndex.build(
        repo_root, all_agent_keys, global_command_dir=get_global_command_dir
    )

    for agent_key in all_agent_keys:
        _, location, exists_bool = _agent_location(repo_root, agent_key, presence)
        configured = "✓" if agent_key in config.available else "✗"
        exists = "✓" if exists_bool else "✗"

        if agent_key in config.available and exists_bool:
            status = "[green]OK[/green]"
        elif agent_key in config.available and not exists_bool:
            status = "[yellow]Missing[/yellow]"
        elif (
            agent_key not in config.available
            and (surface := _project_agent_surface(repo_root, agent_key)) is not None
            and surface[1].exists()
        ):
            status = "[red]Orphaned[/red]"
        else:
            status = "[dim]Not used[/dim]"

        table.add_row(agent_key, location, configured, exists, status)

    console.print(table)

    # Summary
    orphaned = [
        key
        for key in all_agent_keys
        if key not in config.available
        and (surface := _project_agent_surface(repo_root, key)) is not None
        and surface[1].exists()
    ]

    if orphaned:
        console.print(
            f"\n[yellow]⚠ {len(orphaned)} orphaned directories found[/yellow] "
            f"(present but not configured)"
        )
        console.print("Run 'spec-kitty agent config sync --remove-orphaned' to clean up")


@app.command(name="sync")
def sync_agents(
    create_missing: bool = typer.Option(
        False,
        "--create-missing",
        help="Create directories for configured agents that are missing",
    ),
    remove_orphaned: bool = typer.Option(
        True,
        "--remove-orphaned/--keep-orphaned",
        help="Remove directories for agents not in config",
    ),
    sync_hooks: bool = typer.Option(
        False,
        "--sync-hooks",
        help="Update AI harness hook configurations (Claude, Cursor, etc.)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit a JSON summary listing every tracked-manifest mutation (#2691).",
    ),
):
    """Sync filesystem with config.yaml.

    By default, removes orphaned directories (present but not configured).
    Use --create-missing to also create directories for configured agents.
    Use --sync-hooks to update harness-specific post-edit hooks.
    """
    try:
        repo_root = find_repo_root()
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Load config
    config = _load_config_or_exit(repo_root)

    manifest_path = repo_root / ".kittify" / "command-skills-manifest.json"
    manifest_before = manifest_path.read_bytes() if manifest_path.exists() else None

    changes_made = False

    # Remove orphaned directories
    if remove_orphaned:
        changes_made = _remove_orphaned_agent_dirs(repo_root, config) or changes_made

    # Create missing directories
    if create_missing:
        changes_made = _check_or_create_configured_agent_dirs(repo_root, config) or changes_made

    # Sync hooks
    if sync_hooks:
        changes_made = _sync_harness_hooks(repo_root, config) or changes_made

    manifest_after = manifest_path.read_bytes() if manifest_path.exists() else None
    tracked_mutations = [".kittify/command-skills-manifest.json"] if manifest_before != manifest_after else []

    if json_output:
        console.print(
            json.dumps(
                {"changes_made": changes_made, "tracked_mutations": tracked_mutations},
                indent=2,
            )
        )
        return

    if not changes_made:
        console.print("[dim]No changes needed - filesystem matches config[/dim]")
    else:
        console.print("\n[green]✓ Sync complete[/green]")


def _parse_bool_value(value: str) -> bool | None:
    """Parse a CLI boolean string; return None when it is not a valid bool."""
    if is_truthy(value):
        return True
    if value.strip().casefold() in ("false", "0", "no", "off"):
        return False
    return None


def _sync_harness_hooks(repo_root: Path, config: AgentConfig) -> bool:
    """Update harness hook configurations based on lint_on_edit setting.

    config.yaml is the single source of truth: a harness is synced only when
    its agent key is in ``config.available`` (a stray ``.claude``/``.cursor``
    directory never triggers a write — see CLAUDE.md agent-config rules).
    """
    console.print("\n[cyan]Syncing harness hooks...[/cyan]")
    changes = False

    if "claude" in config.available and _sync_claude_hooks(repo_root, config.lint_on_edit):
        changes = True

    if "cursor" in config.available and _sync_cursor_hooks(repo_root, config.lint_on_edit):
        changes = True

    return changes


def _sync_claude_hooks(repo_root: Path, enabled: bool) -> bool:
    """Register/unregister the lint PostToolUse hook in .claude/settings.json.

    Delegates to the canonical :class:`ClaudeCodeHookRegistrar`, which writes
    atomically, preserves all unrelated keys/hooks, removes only the lint hook
    (never sibling hooks), and backs up invalid JSON before rewriting.
    """
    registrar = ClaudeCodeHookRegistrar(event_key="PostToolUse")
    already = registrar.is_registered(repo_root, LINT_HOOK_COMMAND)

    changed = False
    if enabled and not already:
        registrar.register(repo_root, LINT_HOOK_COMMAND, matcher=LINT_HOOK_MATCHER)
        changed = True
    elif not enabled and already:
        registrar.unregister(repo_root, LINT_HOOK_COMMAND)
        changed = True

    if changed:
        console.print(f"  [green]✓[/green] {'Updated' if enabled else 'Removed'} Claude Code lint hook")
    else:
        console.print("  [dim]• Claude Code hooks already in sync[/dim]")
    return changed


def _load_cursor_hooks(path: Path) -> dict | None:
    """Load Cursor hooks.json, or ``None`` if it exists but is corrupt.

    A corrupt file returns ``None`` so the caller refuses to overwrite it
    (no silent data loss); a missing file returns the empty default.
    """
    if not path.exists():
        return {"version": 1, "hooks": {}}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        console.print(
            f"  [yellow]![/yellow] Cursor hooks file is unreadable ({exc}); "
            "leaving it untouched. Fix or remove it, then re-run."
        )
        return None
    return loaded if isinstance(loaded, dict) else {"version": 1, "hooks": {}}


def _sync_cursor_hooks(repo_root: Path, enabled: bool) -> bool:
    path = repo_root / ".cursor" / "hooks.json"
    data = _load_cursor_hooks(path)
    if data is None:
        return False  # corrupt config: refuse to clobber

    hooks = data.setdefault("hooks", {})
    after_file_edit = hooks.get("afterFileEdit", [])
    existing_idx = next(
        (i for i, h in enumerate(after_file_edit) if h.get("command") == LINT_HOOK_COMMAND),
        -1,
    )

    changed = False
    if enabled and existing_idx == -1:
        after_file_edit.append({"command": LINT_HOOK_COMMAND})
        changed = True
    elif not enabled and existing_idx != -1:
        after_file_edit.pop(existing_idx)
        changed = True

    if changed:
        hooks["afterFileEdit"] = after_file_edit
        data["hooks"] = hooks
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_within_directory(path, json.dumps(data, indent=2) + "\n", root=path.parent)
        console.print(f"  [green]✓[/green] {'Updated' if enabled else 'Removed'} Cursor lint hook")
    else:
        console.print("  [dim]• Cursor hooks already in sync[/dim]")
    return changed


@app.command(name="set")
def set_config(
    key: str = typer.Argument(..., help="Configuration key (e.g., auto_commit)"),
    value: str = typer.Argument(..., help="Configuration value (e.g., true, false)"),
):
    """Set a project-level agent configuration value.

    Currently supported keys:
        auto_commit  - Enable/disable automatic commits by agents (true/false)
        lint_on_edit - Enable/disable auto-linting feedback loop (true/false)

    Examples:
        spec-kitty agent config set auto_commit false
        spec-kitty agent config set lint_on_edit true
    """
    try:
        repo_root = find_repo_root()
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    config = _load_config_or_exit(repo_root)

    if key == "auto_commit":
        parsed = _parse_bool_value(value)
        if parsed is None:
            console.print(f"[red]Error:[/red] Invalid value for auto_commit: '{value}'. Use 'true' or 'false'.")
            raise typer.Exit(1)
        config.auto_commit = parsed
        save_agent_config(repo_root, config)

        status_label = _ENABLED_LABEL if config.auto_commit else _DISABLED_LABEL
        console.print(f"[green]✓[/green] auto_commit set to {status_label}")
        if not config.auto_commit:
            console.print("[dim]Agents will stage changes but not create commits unless explicitly instructed.[/dim]")
            console.print("[dim]Per-command flags (--auto-commit/--no-auto-commit) override this setting.[/dim]")
    elif key == "lint_on_edit":
        parsed = _parse_bool_value(value)
        if parsed is None:
            console.print(f"[red]Error:[/red] Invalid value for lint_on_edit: '{value}'. Use 'true' or 'false'.")
            raise typer.Exit(1)
        config.lint_on_edit = parsed
        save_agent_config(repo_root, config)

        status_label = _ENABLED_LABEL if config.lint_on_edit else _DISABLED_LABEL
        console.print(f"[green]✓[/green] lint_on_edit set to {status_label}")
        if config.lint_on_edit:
            console.print("[cyan]Tip:[/cyan] Run 'spec-kitty agent config sync --sync-hooks' to update harness configurations.")
    else:
        console.print(f"[red]Error:[/red] Unknown configuration key: '{key}'")
        console.print("\nSupported keys:")
        console.print("  auto_commit  - Enable/disable automatic commits by agents (true/false)")
        console.print("  lint_on_edit - Enable/disable auto-linting feedback loop (true/false)")
        raise typer.Exit(1)


__all__ = ["app"]
