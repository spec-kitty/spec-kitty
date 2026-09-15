"""Command-surface health cluster for ``doctor`` (WP05, #2059).

Extracts Cluster A — the tool-surface + command-skill + slash-command checks —
out of ``doctor.py``. The ``skills`` command fuses command-skills + slash-commands
into one payload, so they live together here (research OQ1).

The ``skills`` command body and ``_repair_command_skill_state`` are decomposed
into <=15-CC helpers (I-4). The ``@app.command`` shells stay anchored in
``doctor.py`` and delegate to :func:`run_command_files`, :func:`run_skills_audit`,
and :func:`run_tool_surfaces_audit`.

Import discipline (one-way, I-2): this module imports shared infra from
:mod:`._doctor_shared`; it never imports ``doctor.py``. The frozen subcommand
names (``skills``, ``command-files``, ``tool-surfaces``) are owned by the shells
in ``doctor.py``; the safety predicates + argv fast-paths key on those names
(I-7) and are unaffected by this internal move.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, cast

import typer
from rich.table import Table

from specify_cli.core.checkout_identity import (
    CheckoutIdentity,
    FailClosedRefusal,
    Intent,
    resolve_checkout_identity,
)
from specify_cli.core.paths import locate_project_root

from ._doctor_shared import (
    _NOT_IN_PROJECT_MESSAGE,
    _emit_not_in_project,
    _json_error,
    _json_output_guard,
    console,
)

if TYPE_CHECKING:
    from specify_cli.skills.command_installer import VerifyReport
    from specify_cli.skills.manifest_store import SkillsManifest

logger = logging.getLogger(__name__)

# ``__all__`` lists this sibling's cross-module public contract only: the
# command entrypoints ``doctor.py`` delegates to plus the FR-006 test-facing
# symbols re-exported through the ``doctor`` shim. The remaining helpers are
# intra-module (exercised by this module + its own unit tests) and are
# deliberately NOT exported — listing them would make them orphan public
# symbols under the dead-symbol gate (tests/architectural/test_no_dead_symbols).
__all__ = [
    "SlashCommandGap",
    "run_command_files",
    "run_skills_audit",
    "run_tool_surfaces_audit",
    "_load_slash_command_state",
    "_repair_slash_command_state",
]


def _vibe_skill_path_configured(project_path: Path) -> bool:
    from specify_cli.skills.vibe_config import VIBE_SKILL_PATH

    config_path = project_path / ".vibe" / "config.toml"
    if not config_path.exists():
        return False

    try:
        import tomllib  # noqa: PLC0415

        raw = config_path.read_text(encoding="utf-8")
        data = tomllib.loads(raw) if raw.strip() else {}
    except Exception as exc:
        logger.debug("Failed to read %s: %s", config_path, exc)
        return False

    skill_paths = data.get("skill_paths")
    if isinstance(skill_paths, str):
        return bool(skill_paths == VIBE_SKILL_PATH)
    if isinstance(skill_paths, list):
        return VIBE_SKILL_PATH in [str(path) for path in skill_paths]
    return False


def _get_slash_command_agents(project_path: Path) -> list[str]:
    """Return configured slash-command agents (excludes Agent-Skills agents)."""
    from specify_cli.core.agent_config import load_agent_config
    from specify_cli.core.config import AGENT_COMMAND_CONFIG
    from specify_cli.skills.command_installer import SUPPORTED_AGENTS

    try:
        config = load_agent_config(project_path)
        available = set(config.available)
    except Exception:
        available = set(AGENT_COMMAND_CONFIG.keys())
    slash_agents = set(AGENT_COMMAND_CONFIG.keys()) - set(SUPPORTED_AGENTS)
    return sorted(available & slash_agents)


@dataclass
class SlashCommandGap:
    agent_key: str
    command: str
    expected_path: Path
    status: str  # "missing" | "stale"


def _slash_gap_for_path(
    agent_key: str,
    command: str,
    path: Path,
    current_version: str,
) -> SlashCommandGap | None:
    """Classify a single slash-command file as missing/stale, or None if healthy."""
    from specify_cli.runtime.agent_commands import (
        _VERSION_MARKER_HEAD_LINES,
        _VERSION_MARKER_PREFIX,
    )

    if not path.exists():
        return SlashCommandGap(agent_key, command, path, "missing")
    try:
        head = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            .splitlines()[:_VERSION_MARKER_HEAD_LINES]
        )
    except OSError:
        return SlashCommandGap(agent_key, command, path, "missing")
    if f"{_VERSION_MARKER_PREFIX} {current_version}" not in head:
        return SlashCommandGap(agent_key, command, path, "stale")
    return None


def _load_slash_command_state(
    project_path: Path,
) -> tuple[list[str], list[SlashCommandGap]]:
    """Return (configured_agents, gaps) for the slash-command pipeline."""
    from specify_cli.core.config import AGENT_COMMAND_CONFIG
    from specify_cli.runtime.agent_commands import (
        _compute_output_filename,
        get_global_command_dir,
    )
    from specify_cli.runtime.bootstrap import _get_cli_version
    from specify_cli.shims.registry import CLI_DRIVEN_COMMANDS, PROMPT_DRIVEN_COMMANDS

    current_version = _get_cli_version()
    configured = _get_slash_command_agents(project_path)
    gaps: list[SlashCommandGap] = []
    for agent_key in configured:
        cfg = AGENT_COMMAND_CONFIG.get(agent_key)
        if cfg is None:
            continue
        cmd_dir = get_global_command_dir(agent_key)
        for command in sorted(PROMPT_DRIVEN_COMMANDS | CLI_DRIVEN_COMMANDS):
            filename = _compute_output_filename(command, agent_key)
            gap = _slash_gap_for_path(
                agent_key, command, cmd_dir / filename, current_version
            )
            if gap is not None:
                gaps.append(gap)
    return configured, gaps


def _print_slash_command_report(
    configured_slash: list[str],
    slash_gaps: list[SlashCommandGap],
    fix: bool,
) -> bool:
    """Render slash-command audit section and return True if healthy."""
    # Single return (S3516): the health boolean is computed once; the branches
    # below only drive console output. Fall through to one trailing return.
    slash_healthy = not slash_gaps
    if configured_slash:
        console.print()
        if not slash_gaps:
            console.print(
                f"[green]✓ Slash Commands[/green]: all configured agents healthy"
                f" ({len(configured_slash)} agent(s))"
            )
        else:
            console.print("[bold]Slash Commands[/bold] — gap(s) found\n")
            for agent_key in configured_slash:
                agent_gaps = [g for g in slash_gaps if g.agent_key == agent_key]
                if agent_gaps:
                    console.print(f"  [red]✗[/red] {agent_key}: {len(agent_gaps)} gap(s)")
                    for gap in agent_gaps[:5]:
                        console.print(f"      {gap.status}: {gap.expected_path.name}")
                    if len(agent_gaps) > 5:
                        console.print(f"      ... and {len(agent_gaps) - 5} more")
                else:
                    console.print(f"  [green]✓[/green] {agent_key}: all commands present")
            if not fix:
                console.print(
                    "\nRun [cyan]spec-kitty doctor skills --fix[/cyan] to reinstall."
                )
    return slash_healthy


def _repair_slash_command_state(
    project_path: Path,
    configured_agents: list[str],
    gaps: list[SlashCommandGap],
) -> list[str]:
    """Reinstall missing/stale slash-command files. Returns list of repaired paths."""
    del project_path
    if not gaps:
        return []
    from specify_cli.runtime.agent_commands import ensure_global_agent_commands

    ensure_global_agent_commands(agent_keys=configured_agents)
    return [str(g.expected_path) for g in gaps]


def _slash_command_payload(
    configured_agents: list[str],
    gaps: list[SlashCommandGap],
    repaired: list[str],
    errors: list[str],
) -> dict[str, object]:
    """Build the JSON/human report payload for slash-command audit."""
    return {
        "configured_agents": configured_agents,
        "gaps": [
            {
                "agent_key": gap.agent_key,
                "command": gap.command,
                "expected_path": str(gap.expected_path),
                "status": gap.status,
            }
            for gap in gaps
        ],
        "repaired": repaired,
        "errors": errors,
        "ok": not gaps and not errors,
    }


def _load_and_optionally_repair_slash_commands(
    project_path: Path,
    fix: bool,
) -> dict[str, object]:
    """Load slash-command audit state and optionally repair detected gaps."""
    slash_repaired: list[str] = []
    slash_errors: list[str] = []
    try:
        configured_slash, slash_gaps = _load_slash_command_state(project_path)
        if fix and slash_gaps:
            slash_repaired = _repair_slash_command_state(
                project_path,
                configured_slash,
                slash_gaps,
            )
            configured_slash, slash_gaps = _load_slash_command_state(project_path)
    except Exception as exc:
        configured_slash = []
        slash_gaps = []
        slash_errors = [str(exc)]

    return _slash_command_payload(
        configured_slash,
        slash_gaps,
        slash_repaired,
        slash_errors,
    )


def _print_slash_command_payload(
    slash_payload: dict[str, object],
    fix: bool,
) -> None:
    """Render human output for slash-command audit payload."""
    if slash_payload.get("errors"):
        console.print("\n[bold red]Slash-command audit failed[/bold red]")
        for error in cast(list[object], slash_payload["errors"]):
            console.print(f"  [red]![/red] {error}")
        return

    configured_slash = cast(list[str], slash_payload["configured_agents"])
    slash_gaps = [
        SlashCommandGap(
            str(gap["agent_key"]),
            str(gap["command"]),
            Path(str(gap["expected_path"])),
            str(gap["status"]),
        )
        for gap in cast(list[dict[str, object]], slash_payload["gaps"])
        if isinstance(gap, dict)
    ]
    _print_slash_command_report(configured_slash, slash_gaps, fix)
    if fix and slash_payload["repaired"]:
        console.print(
            f"\n[green]Repaired:[/green] {len(cast(list[object], slash_payload['repaired']))} slash command file(s)"
        )


def _load_command_skill_state(
    project_path: Path,
) -> tuple[SkillsManifest, VerifyReport, list[str], list[str], list[str], bool]:
    """Load command-skill manifest state and configured command-skill agents."""
    from specify_cli.core.agent_config import load_agent_config
    from specify_cli.skills import command_installer, manifest_store

    config = load_agent_config(project_path)
    supported = set(command_installer.SUPPORTED_AGENTS)
    configured_agents = sorted(set(config.available) & supported)
    manifest = manifest_store.load(project_path)
    report = command_installer.verify(project_path)
    manifest_agents = sorted({agent for entry in manifest.entries for agent in entry.agents})
    uninstalled_agents = [
        agent for agent in configured_agents if agent not in set(manifest_agents)
    ]
    vibe_config_missing = "vibe" in configured_agents and not _vibe_skill_path_configured(
        project_path
    )
    return (
        manifest,
        report,
        configured_agents,
        manifest_agents,
        uninstalled_agents,
        vibe_config_missing,
    )


def _repair_refusal(report: VerifyReport) -> str | None:
    """Return a refusal reason if the repair must be blocked, else None."""
    if report.drift:
        return "Refusing --fix while managed skill files have edited-file drift."
    if report.unsafe:
        return "Refusing --fix while managed skill paths resolve outside the project."
    if report.orphans:
        return "Refusing --fix while unmanaged spec-kitty skill files exist."
    return None


def _install_command_skill_agents(
    project_path: Path,
    agents: list[str],
) -> tuple[list[str], bool, list[str]]:
    """Install command skills for *agents*; return (repaired, vibe_repaired, errors)."""
    from specify_cli.skills import command_installer
    from specify_cli.skills.vibe_config import ensure_project_skill_path

    repaired: list[str] = []
    repaired_vibe_config = False
    errors: list[str] = []
    for agent in sorted(set(agents)):
        try:
            command_installer.install(project_path, agent)
            if agent == "vibe":
                ensure_project_skill_path(project_path)
                repaired_vibe_config = True
            repaired.append(agent)
        except Exception as exc:  # pragma: no cover - exercised by CLI smoke paths
            errors.append(f"{agent}: {exc}")
    return repaired, repaired_vibe_config, errors


def _repair_command_skill_state(
    project_path: Path,
    manifest_agents: list[str],
    uninstalled_agents: list[str],
    report: VerifyReport,
    vibe_config_missing: bool,
) -> tuple[list[str], list[str], list[str], bool]:
    """Repair missing command-skill files unless edited-file drift is present."""
    from specify_cli.skills import command_installer
    from specify_cli.skills.vibe_config import ensure_project_skill_path

    if not (report.gaps or report.stale or uninstalled_agents or vibe_config_missing):
        return [], [], [], False
    refusal = _repair_refusal(report)
    if refusal is not None:
        return [], [], [refusal], False

    pruned: list[str] = []
    errors: list[str] = []
    repaired_vibe_config = False
    agents = set(manifest_agents) | set(uninstalled_agents)
    if report.stale:
        try:
            pruned = command_installer.prune_stale(project_path)
        except Exception as exc:  # pragma: no cover - exercised by CLI smoke paths
            errors.append(f"stale: {exc}")

    if vibe_config_missing and "vibe" in agents:
        try:
            ensure_project_skill_path(project_path)
            repaired_vibe_config = True
        except Exception as exc:  # pragma: no cover - exercised by CLI smoke paths
            errors.append(f"vibe-config: {exc}")

    repaired, install_vibe_repaired, install_errors = _install_command_skill_agents(
        project_path, sorted(agents)
    )
    repaired_vibe_config = repaired_vibe_config or install_vibe_repaired
    errors.extend(install_errors)
    return repaired, pruned, errors, repaired_vibe_config


def _command_skill_payload(
    manifest: SkillsManifest,
    report: VerifyReport,
    configured_agents: list[str],
    manifest_agents: list[str],
    uninstalled_agents: list[str],
    vibe_config_missing: bool,
    repaired: list[str],
    pruned: list[str],
    repaired_vibe_config: bool,
    repair_errors: list[str],
) -> dict[str, object]:
    """Build the JSON/human report payload for ``doctor skills``."""
    from specify_cli.skills import command_installer

    has_issues = bool(
        report.drift
        or report.gaps
        or report.orphans
        or report.stale
        or report.unsafe
        or uninstalled_agents
        or vibe_config_missing
        or repair_errors
    )
    return {
        "configured_agents": configured_agents,
        "manifest_agents": manifest_agents,
        "entries": len(manifest.entries),
        "canonical_commands": len(command_installer.CANONICAL_COMMANDS),
        "drift": sorted(report.drift),
        "gaps": sorted(report.gaps),
        "orphans": sorted(report.orphans),
        "stale": sorted(report.stale),
        "unsafe": sorted(report.unsafe),
        "uninstalled_agents": uninstalled_agents,
        "vibe_config_missing": vibe_config_missing,
        "repaired_agents": repaired,
        "pruned": pruned,
        "repaired_vibe_config": repaired_vibe_config,
        "repair_errors": repair_errors,
        "ok": not has_issues,
    }


def _print_command_skill_paths(title: str, paths: list[str]) -> None:
    if not paths:
        return
    console.print(f"\n[bold yellow]{title}[/bold yellow]")
    for path in paths:
        console.print(f"  [yellow]![/yellow] {path}")


def _print_command_skill_summary_table(payload: dict[str, object]) -> None:
    """Render the per-check count table for ``doctor skills`` (extracted helper)."""
    console.print("\n[bold]Command Skills[/bold] - issue(s) found\n")
    summary = Table(box=None, padding=(0, 2), show_edge=False)
    summary.add_column("Check", style="cyan", min_width=20)
    summary.add_column("Count", justify="right", min_width=6)
    summary.add_row("manifest entries", str(payload["entries"]))
    summary.add_row("drift", str(len(cast(list[str], payload["drift"]))))
    summary.add_row("gaps", str(len(cast(list[str], payload["gaps"]))))
    summary.add_row("orphans", str(len(cast(list[str], payload["orphans"]))))
    summary.add_row("stale", str(len(cast(list[str], payload["stale"]))))
    summary.add_row("unsafe", str(len(cast(list[str], payload["unsafe"]))))
    summary.add_row(
        "uninstalled agents",
        str(len(cast(list[str], payload["uninstalled_agents"]))),
    )
    console.print(summary)


def _print_command_skill_repairs(payload: dict[str, object]) -> None:
    """Render the repair-result lines for ``doctor skills`` (extracted helper)."""
    repaired = cast(list[str], payload["repaired_agents"])
    repair_errors = cast(list[str], payload["repair_errors"])
    if repaired:
        console.print(f"\n[green]Repaired:[/green] {', '.join(repaired)}")
    if payload["pruned"]:
        console.print(
            f"\n[green]Pruned stale entries:[/green] "
            f"{len(cast(list[object], payload['pruned']))}"
        )
    if payload["repaired_vibe_config"]:
        console.print("\n[green]Repaired:[/green] Vibe skill path config")
    if repair_errors:
        console.print("\n[bold red]Repair errors[/bold red]")
        for error in repair_errors:
            console.print(f"  [red]![/red] {error}")


def _print_command_skill_report(payload: dict[str, object], fix: bool) -> None:
    """Render human output for ``doctor skills``."""
    if payload["ok"]:
        console.print(
            "[green]Command Skills[/green]: all manifest entries healthy "
            f"({payload['entries']} file(s))"
        )
        return

    _print_command_skill_summary_table(payload)

    _print_command_skill_paths(
        "Edited managed files (manual review required)",
        cast(list[str], payload["drift"]),
    )
    _print_command_skill_paths("Missing managed files", cast(list[str], payload["gaps"]))
    _print_command_skill_paths(
        "Unmanaged spec-kitty skill files", cast(list[str], payload["orphans"])
    )
    _print_command_skill_paths("Stale managed files", cast(list[str], payload["stale"]))
    _print_command_skill_paths("Unsafe managed paths", cast(list[str], payload["unsafe"]))

    uninstalled_agents = cast(list[str], payload["uninstalled_agents"])
    if uninstalled_agents:
        console.print("\n[bold yellow]Configured agents without command skills[/bold yellow]")
        for agent in uninstalled_agents:
            console.print(f"  [yellow]![/yellow] {agent}")

    _print_command_skill_repairs(payload)

    gaps = cast(list[str], payload["gaps"])
    stale = cast(list[str], payload["stale"])
    if not fix and (gaps or uninstalled_agents or stale or payload["vibe_config_missing"]):
        console.print(
            "\nRun [cyan]spec-kitty doctor skills --fix[/cyan] "
            "to reinstall missing command skills."
        )


# --- command-files -----------------------------------------------------------


def _print_command_files_table(issues: list[dict[str, str]]) -> None:
    """Render the command-files issue table (extracted helper)."""
    console.print(f"\n[bold]Command Files[/bold] — {len(issues)} issue(s) found\n")
    table = Table(box=None, padding=(0, 2), show_edge=False)
    table.add_column("Agent", style="cyan", min_width=12)
    table.add_column("Command", min_width=16)
    table.add_column("File", min_width=40)
    table.add_column("Severity", min_width=8)
    table.add_column("Issue")
    for issue in issues:
        severity = issue["severity"]
        severity_display = (
            f"[red]{severity}[/red]"
            if severity == "error"
            else f"[yellow]{severity}[/yellow]"
        )
        table.add_row(
            issue["agent"],
            issue["command"],
            issue["file"],
            severity_display,
            issue["issue"],
        )
    console.print(table)
    console.print()


def _resolve_or_exit(exit_code: int, json_output: bool) -> Path:
    """Resolve the project root or exit with *exit_code*, honoring ``--json`` (#4242)."""
    try:
        project_path: Path | None = locate_project_root()
    except Exception as exc:
        _emit_not_in_project(json_output)
        raise typer.Exit(exit_code) from exc
    if project_path is None:
        _emit_not_in_project(json_output)
        raise typer.Exit(exit_code)
    return project_path


def run_command_files(json_output: bool) -> None:
    """Entry point for ``doctor command-files`` (0 healthy / 1 issues)."""
    from specify_cli.runtime.doctor import check_command_file_health

    project_path = _resolve_or_exit(1, json_output)
    issues = check_command_file_health(project_path)

    if json_output:
        console.print_json(json.dumps(issues, indent=2))
        raise typer.Exit(1 if issues else 0)

    if not issues:
        console.print("[green]Command Files[/green]: all files healthy")
        raise typer.Exit(0)

    _print_command_files_table(issues)
    raise typer.Exit(1)


# --- skills ------------------------------------------------------------------


def _skills_not_in_project(json_output: bool, exc: BaseException | None) -> NoReturn:
    """Emit the not-in-project response for ``doctor skills`` and exit(2)."""
    if json_output:
        console.print_json(
            json.dumps(_json_error("not_in_project", _NOT_IN_PROJECT_MESSAGE), indent=2)
        )
    else:
        console.print(f"[red]Error:[/red] {_NOT_IN_PROJECT_MESSAGE}")
    if exc is not None:
        raise typer.Exit(2) from exc
    raise typer.Exit(2)


_SkillState = tuple["SkillsManifest", "VerifyReport", list[str], list[str], list[str], bool]


def _load_skills_state_or_exit(project_path: Path, json_output: bool) -> _SkillState:
    """Load command-skill state, translating failures to the exit-2 contract."""
    from specify_cli.core.agent_config import AgentConfigError

    try:
        return _load_command_skill_state(project_path)
    except AgentConfigError as exc:
        if json_output:
            console.print_json(json.dumps(_json_error("config_error", str(exc)), indent=2))
            raise typer.Exit(2) from exc
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc
    except Exception as exc:
        if json_output:
            console.print_json(json.dumps(_json_error("manifest_error", str(exc)), indent=2))
            raise typer.Exit(2) from exc
        console.print(f"[red]Error:[/red] Could not read command-skill manifest: {exc}")
        raise typer.Exit(2) from exc


def run_skills_audit(
    fix: bool, json_output: bool, project_path: Path | None
) -> None:
    """Entry point for ``doctor skills`` (0 ok / 1 gaps / 2 not-in-project|config).

    *project_path* is resolved by the ``doctor.py`` command shell (which owns the
    patchable ``locate_project_root`` seam); ``None`` triggers the not-in-project
    exit-2 contract here.
    """
    if project_path is None:
        _skills_not_in_project(json_output, None)

    with _json_output_guard(json_output):
        # State load + repair must run under the guard to keep --json clean.
        state = _load_skills_state_or_exit(project_path, json_output)
        payload = _assemble_skills_payload(project_path, fix, state)

    if json_output:
        console.print_json(json.dumps(payload, indent=2))
        raise typer.Exit(0 if payload["ok"] else 1)

    _print_command_skill_report(payload, fix)

    slash_payload_raw = payload["slash_commands"]
    slash_payload_for_print: dict[str, object] = (
        {"ok": False, "errors": ["invalid slash-command payload"]}
        if not isinstance(slash_payload_raw, dict)
        else slash_payload_raw
    )
    _print_slash_command_payload(slash_payload_for_print, fix)

    raise typer.Exit(0 if payload["ok"] else 1)


def _assemble_skills_payload(
    project_path: Path, fix: bool, state: _SkillState
) -> dict[str, object]:
    """Build the fused command-skill + slash-command payload from loaded *state*."""
    (
        manifest,
        report,
        configured_agents,
        manifest_agents,
        uninstalled_agents,
        vibe_config_missing,
    ) = state

    repaired: list[str] = []
    pruned: list[str] = []
    repair_errors: list[str] = []
    repaired_vibe_config = False
    if fix:
        repaired, pruned, repair_errors, repaired_vibe_config = _repair_command_skill_state(
            project_path,
            manifest_agents,
            uninstalled_agents,
            report,
            vibe_config_missing,
        )
        if (repaired or pruned or repaired_vibe_config) and not repair_errors:
            try:
                (
                    manifest,
                    report,
                    configured_agents,
                    manifest_agents,
                    uninstalled_agents,
                    vibe_config_missing,
                ) = _load_command_skill_state(project_path)
            except Exception as exc:
                repair_errors.append(f"post-fix verify failed: {exc}")

    payload = _command_skill_payload(
        manifest,
        report,
        configured_agents,
        manifest_agents,
        uninstalled_agents,
        vibe_config_missing,
        repaired,
        pruned,
        repaired_vibe_config,
        repair_errors,
    )

    slash_payload = _load_and_optionally_repair_slash_commands(project_path, fix)
    payload["slash_commands"] = slash_payload
    payload["ok"] = bool(payload["ok"]) and bool(slash_payload["ok"])
    return payload


# --- tool-surfaces -----------------------------------------------------------


def _configured_tool_keys(project_path: Path) -> list[str]:
    """Return configured tool keys from ``.kittify/config.yaml`` (sorted)."""
    from specify_cli.core.agent_config import load_agent_config

    return sorted(set(load_agent_config(project_path).available))


def _configured_tool_keys_or_exit(project_path: Path, json_output: bool) -> list[str]:
    """Load configured tool keys, translating a config load failure to exit 2.

    Mirrors :func:`_load_skills_state_or_exit`'s ``AgentConfigError`` handling
    (the sibling ``doctor skills`` command) so a non-mapping
    ``.kittify/config.yaml`` produces the documented ``config_error`` JSON
    envelope instead of an uncaught traceback (OP-FRESH-001).
    """
    from specify_cli.core.agent_config import AgentConfigError

    try:
        return _configured_tool_keys(project_path)
    except AgentConfigError as exc:
        if json_output:
            console.print_json(json.dumps(_json_error("config_error", str(exc)), indent=2))
            raise typer.Exit(2) from exc
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc


def _print_tool_surface_human(outcome: object) -> None:
    """Render a compact human summary of a tool-surface outcome."""
    from specify_cli.tool_surface.service import ToolSurfaceOutcome

    assert isinstance(outcome, ToolSurfaceOutcome)
    report = outcome.report
    if report.ok and not report.findings:
        console.print(
            "[green]Tool Surfaces[/green]: all surfaces healthy "
            f"({report.summary.surfaces} checked)"
        )
        return
    console.print("\n[bold]Tool Surfaces[/bold] - issue(s) found\n")
    for finding in report.findings:
        colour = "red" if finding.severity == "error" else "yellow"
        console.print(f"  [{colour}]![/{colour}] [{finding.code}] {finding.message}")
    if outcome.repair is not None and outcome.repair.repaired:
        console.print(
            f"\n[green]Repaired:[/green] {len(outcome.repair.repaired)} surface(s)"
        )


_FIX_REFUSED_CODE = "foreign_checkout_write_refused"


class ToolSurfaceFixRefused(typer.Exit):
    """Fail-closed refusal of a foreign-checkout ``--fix`` (FR-003, #2613).

    Tool surfaces are per-checkout tracked agent files (``.claude/commands/*``
    etc.), NOT status — there is no deliberate-centralization defense here.
    ``doctor tool-surfaces --fix`` invoked from a linked lane worktree would
    otherwise silently repair the PRIMARY's manifest, because
    :func:`_resolve_tool_surfaces_project` re-anchors the worktree to the
    primary via :func:`locate_project_root`. This exception is raised instead:
    it REFUSES (it does not redirect the repair into the lane — the
    C-003/#3128-forbidden fake).

    It carries the single-channel :class:`FailClosedRefusal` value object
    (NFR-003) so the refusal names the primary checkout it declined to mutate,
    and subclasses :class:`typer.Exit` (code 2) so the CLI surfaces a clean
    non-zero exit rather than a traceback.
    """

    def __init__(self, refusal: FailClosedRefusal) -> None:
        self.refusal = refusal
        super().__init__(code=2)


def _guard_tool_surfaces_fix(json_output: bool) -> None:
    """Refuse a ``--fix`` mutation invoked from a foreign (non-owner) checkout.

    Consumes the WP01 seam: an invocation whose ``cwd`` is a linked lane
    worktree does not own its ``canonical_target`` (the primary the worktree
    pointer names), so a ``WRITE`` fails closed. Owner invocations (primary or
    a standalone clone) return no refusal and proceed unchanged; the read-only
    ``--audit`` path never calls this guard (FR-003 risk: over-refusing audit).
    """
    identity: CheckoutIdentity = resolve_checkout_identity(Path.cwd(), Intent.WRITE)
    refusal = identity.write_refusal()
    if refusal is None:
        return
    if json_output:
        console.print_json(
            json.dumps(_json_error(_FIX_REFUSED_CODE, refusal.message()), indent=2)
        )
    else:
        console.print(f"[red]Error:[/red] {refusal.message()}")
    raise ToolSurfaceFixRefused(refusal)


def _resolve_tool_surfaces_project(json_output: bool) -> Path:
    """Resolve project root for ``doctor tool-surfaces`` (exit 2 when not in project)."""
    try:
        project_path: Path | None = locate_project_root()
    except Exception as exc:
        if not json_output:
            console.print(f"[red]Error:[/red] {_NOT_IN_PROJECT_MESSAGE}")
        else:
            console.print_json(json.dumps(_json_error("not_in_project", str(exc)), indent=2))
        raise typer.Exit(2) from exc
    if project_path is None:
        if json_output:
            console.print_json(
                json.dumps(_json_error("not_in_project", _NOT_IN_PROJECT_MESSAGE), indent=2)
            )
        else:
            console.print(f"[red]Error:[/red] {_NOT_IN_PROJECT_MESSAGE}")
        raise typer.Exit(2)
    return project_path


def run_tool_surfaces_audit(
    kind: list[str] | None,
    tool: str | None,
    fix: bool,
    json_output: bool,
) -> None:
    """Entry point for ``doctor tool-surfaces`` (0 ok / 1 issues / 2 not-in-project|kind)."""
    from specify_cli.tool_surface.service import (
        UnknownSurfaceKind,
        run_tool_surfaces,
        surface_kind_from_token,
    )

    project_path = _resolve_tool_surfaces_project(json_output)

    # FR-003 (#2613): fail closed BEFORE any mutation when ``--fix`` is invoked
    # from a checkout that does not own the (re-anchored primary) target. The
    # read-only audit path is never gated.
    if fix:
        _guard_tool_surfaces_fix(json_output)

    try:
        kinds = [surface_kind_from_token(token) for token in (kind or [])]
    except UnknownSurfaceKind as exc:
        if json_output:
            console.print_json(json.dumps(_json_error("unknown_kind", str(exc)), indent=2))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc

    outcome = run_tool_surfaces(
        project_path,
        _configured_tool_keys_or_exit(project_path, json_output),
        tool_filter=tool,
        kinds=kinds or None,
        fix=fix,
    )

    if json_output:
        console.print_json(json.dumps(outcome.to_json(), indent=2))
        raise typer.Exit(0 if outcome.report.ok else 1)
    _print_tool_surface_human(outcome)
    raise typer.Exit(0 if outcome.report.ok else 1)
