"""``spec-kitty moments`` — the one-line switch for what reaches agent
context (Priivacy-ai/spec-kitty#190, "Moments in agent context").

Three subcommands, each one line of output, over
``zeitgeist_client.moments``' settings — never a second config reader or a
second writer:

* ``off``   — write ``[moments] agents = "off"``; the MCP server then refuses
  to start (exit 0, one line) and every other agent surface goes quiet.
* ``on``    — write the documented default back (``team``), undoing an off.
* ``status``— say which mode is effective, WHICH file decided it, and what
  else filters the stream.

The write target defaults to the developer-global home ``.kittify/config.toml``
because this is a per-developer preference; ``--repo`` writes the per-repo
``<root>/.kittify/config.toml`` override instead for "quiet in THIS checkout
only". Narrow-only precedence lives in
:func:`zeitgeist_client.moments.load_settings` — after any write this module
re-reads and prints the *effective* mode, because with both files in play
the file just written is not always the one that decides.

A ``[moments] kinds`` entry MUST spell a volatile family name off the real
wire (``WPStatusChanged``, ``MissionCreated``, ``PhaseEntered``, … — the full
list is :data:`zeitgeist_client.moments.KNOWN_KIND_NAMES`), never the dotted
style Priivacy-ai/spec-kitty#190's own text used (``wp.move``,
``mission.created``): a dotted or otherwise unknown entry is valid TOML, so
it is never reported alongside a malformed filter, but it can never match a
frame's ``kind`` and so silently surfaces zero moments
(Priivacy-ai/spec-kitty#210). ``status`` warns on exactly that entry instead
of staying silent about it.
"""

from __future__ import annotations

from pathlib import Path

import typer

from specify_cli.cli.console import console
from specify_cli.zeitgeist_client import moments

moments_app = typer.Typer(
    name="moments",
    help="Control which Zeitgeist status moments reach agent context (off / mine / team), per developer and per repo.",
)

_JSON_OPTION = typer.Option(False, "--json", help="Emit plain JSON instead of a human-readable summary.")
_REPO_SCOPE_OPTION = typer.Option(
    False,
    "--repo",
    help="Write the per-repo override (<repo>/.kittify/config.toml) instead of the global home .kittify config.",
)


def _resolve_scope(repo_scoped: bool) -> tuple[str, Path | None]:
    """``(scope label, project root when repo-scoped)`` for a write. Repo
    scope needs a Spec Kitty checkout to write into — there is no such thing
    as a repo override outside one."""
    if not repo_scoped:
        return "global", None
    project_root = moments.locate_repo_root()
    if project_root is None:
        console.print("[red]Error:[/red] --repo needs a Spec Kitty checkout (.kittify/) — run this from inside one.")
        raise typer.Exit(1)
    return "repo", project_root


def _print_effective(settings: moments.MomentSettings) -> None:
    console.print(f"effective: {settings.agents.value} ({settings.agents_source})", markup=False)


@moments_app.command()
def off(repo: bool = _REPO_SCOPE_OPTION) -> None:
    """Switch moments to agents OFF: nothing surfaces, and
    the internal agent-context bridge exits cleanly with one line."""
    scope, project_root = _resolve_scope(repo)
    written = moments.write_agents_mode(moments.MomentsMode.OFF, scope=scope, project_root=project_root)
    console.print(f"off — written to {written}", markup=False)
    _print_effective(moments.load_settings(project_root=project_root))


@moments_app.command()
def on(repo: bool = _REPO_SCOPE_OPTION) -> None:
    """Switch moments back ON at the documented default (`team`)."""
    scope, project_root = _resolve_scope(repo)
    written = moments.write_agents_mode(moments.DEFAULT_AGENTS_MODE, scope=scope, project_root=project_root)
    console.print(f"on — {moments.DEFAULT_AGENTS_MODE.value} written to {written}", markup=False)
    _print_effective(moments.load_settings(project_root=project_root))


@moments_app.command()
def status(as_json: bool = _JSON_OPTION) -> None:
    """Show the effective mode, which file decided it, and the active filters."""
    settings = moments.load_settings()
    if as_json:
        console.emit_json(settings.as_dict())
        return
    console.print(f"{settings.agents.value}  source={settings.agents_source}", markup=False)
    for name in ("repos", "missions", "teammates", "kinds"):
        if name in settings.invalid_filters:
            rendered = "invalid value in config — failing closed (blocks everything on this filter)"
        elif name in settings.blocked_filters:
            rendered = "global and repo allowlists do not overlap — blocks everything on this filter"
        else:
            values = getattr(settings, name)
            rendered = ", ".join(values) if values else "(no filter)"
        console.print(f"  {name}: {rendered}", markup=False)
        if name == "kinds" and name not in settings.invalid_filters:
            unknown = moments.unknown_kind_names(settings.kinds)
            if unknown:
                known = ", ".join(sorted(moments.KNOWN_KIND_NAMES))
                console.print(
                    f"    warning: {', '.join(unknown)} — not a known event-kind name, will never match, so this filter admits nothing; known names: {known}",
                    markup=False,
                )
    console.print(f"  rate_per_minute: {settings.rate_per_minute}", markup=False)
    if settings.agents is moments.MomentsMode.OFF:
        console.print("  agent-context bridge refuses to start while agents = off.")
