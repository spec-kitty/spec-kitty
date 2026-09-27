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

import tomllib
from pathlib import Path
from typing import Any

import typer
from rich.markup import escape
from ruamel.yaml.error import YAMLError

from specify_cli.cli.console import console
from specify_cli.core import hosted_posture
from specify_cli.zeitgeist_client import moments

moments_app = typer.Typer(
    name="moments",
    help="Control which Zeitgeist status moments reach agent context (off / mine / team), per developer and per repo.",
)

#: Both scopes / no-env-can-enable, stated once (Sonar S1192 — `drain --help` and
#: `drain on --help` both need it; contracts/hosted-posture.md, R-1). The
#: leading backslash on ``\[hosted]`` escapes Rich markup in Typer's
#: rich-rendered ``--help`` output -- an unescaped ``[hosted]`` is parsed as a
#: (nonexistent) style tag and silently swallowed (review issue 2).
_DRAIN_BOTH_SCOPES_HELP = (
    "Live drain (moments/presence/capability/relay) is effective only when BOTH scopes "
    "are on: the repository (.kittify/config.yaml hosted.drain) and your personal "
    "runtime-root config.toml (\\[hosted] drain). No environment variable can turn drain "
    "on -- env vars only narrow it further (e.g. SPEC_KITTY_NO_MOMENT_HANDLERS)."
)

#: S1192: the "effective: " status-line prefix is shared by three human-readable
#: renderers (agents settings, drain-mutation confirmation, drain status).
_EFFECTIVE_PREFIX = "effective: "

drain_app = typer.Typer(name="drain", help=_DRAIN_BOTH_SCOPES_HELP)
moments_app.add_typer(drain_app, name="drain")

_JSON_OPTION = typer.Option(False, "--json", help="Emit plain JSON instead of a human-readable summary.")
_REPO_SCOPE_OPTION = typer.Option(
    False,
    "--repo",
    help="Write the per-repo override (<repo>/.kittify/config.toml) instead of the global home .kittify config.",
)
#: Drain-specific --repo help (review issue 1): the generic `_REPO_SCOPE_OPTION`
#: above describes the `off`/`on`/`status` moments-mode files, which are wrong
#: for drain -- drain's own two files are `.kittify/config.yaml` (repo) and the
#: runtime-root `config.toml` (personal), neither of which is `~/.kittify/`.
_DRAIN_REPO_SCOPE_OPTION = typer.Option(
    False,
    "--repo",
    help="Write the repository scope (<repo>/.kittify/config.yaml hosted.drain) instead of the personal scope (the runtime-root config.toml \\[hosted] drain).",
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
    console.print(f"{_EFFECTIVE_PREFIX}{settings.agents.value} ({settings.agents_source})", markup=False)


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


# --- drain -------------------------------------------------------------------


def _drain_parse_error(config_path: Path, fmt: str) -> None:
    """One-line, markup-safe refusal for a malformed hosted-posture config
    file: never a traceback, and never the literal tag text (review issue
    3b -- ``markup=False`` on a string containing ``[red]...[/red]`` prints
    the tag itself instead of styling it, so this prints WITH markup parsing
    on and escapes the untrusted path instead). ``fmt`` names the file kind
    only (never the raw exception text, which for a YAML/TOML parse error
    can itself span several lines and would break the one-line contract --
    review issue 3a)."""
    console.print(f"[red]Error:[/red] {escape(str(config_path))}: could not parse existing {fmt} -- left unchanged.")


def _drain_set(*, enabled: bool, repo_scoped: bool) -> None:
    """Shared body for ``drain on``/``drain off``: write the requested scope
    through ``core.hosted_posture`` (never a second reader/writer), then
    re-read and print the effective posture -- same idiom as ``off``/``on``
    above. Both scopes' unparseable-file cases are caught here and reduced to
    one line, exit 1, file left untouched (D7 for personal; the equivalent
    fail-loud contract `hosted_posture.set_repo_drain` documents for repo)."""
    label = "on" if enabled else "off"
    if repo_scoped:
        _, project_root = _resolve_scope(True)
        if project_root is None:
            # Unreachable in practice: `_resolve_scope(True)` always either
            # returns a non-None root or raises `typer.Exit(1)` first. Narrowing
            # via an explicit raise (not `assert`) since production asserts are
            # stripped under `-O` and must never carry real control flow.
            raise RuntimeError("_resolve_scope(True) returned no project root without exiting")
        try:
            written = hosted_posture.set_repo_drain(project_root, enabled)
        except YAMLError:
            _drain_parse_error(project_root / ".kittify" / "config.yaml", "YAML")
            raise typer.Exit(1) from None
    else:
        try:
            written = hosted_posture.set_personal_drain(enabled)
        except tomllib.TOMLDecodeError:
            _drain_parse_error(hosted_posture.personal_config_path(), "TOML")
            raise typer.Exit(1) from None
    console.print(f"{label} -- written to {written}", markup=False)
    posture = hosted_posture.drain_posture()
    console.print(f"{_EFFECTIVE_PREFIX}{'on' if posture.enabled else 'off'} ({posture.reason})", markup=False)


@drain_app.command("on", help=f"Turn live drain ON for one scope. {_DRAIN_BOTH_SCOPES_HELP}")
def drain_on(repo: bool = _DRAIN_REPO_SCOPE_OPTION) -> None:
    """Write ``True`` to the requested scope, then print the effective posture."""
    _drain_set(enabled=True, repo_scoped=repo)


@drain_app.command("off", help=f"Turn live drain OFF for one scope. {_DRAIN_BOTH_SCOPES_HELP}")
def drain_off(repo: bool = _DRAIN_REPO_SCOPE_OPTION) -> None:
    """Write ``False`` to the requested scope, then print the effective posture."""
    _drain_set(enabled=False, repo_scoped=repo)


def _drain_narrowers(posture: hosted_posture.DrainPosture) -> list[str]:
    """Every active narrower affecting the hosted-moment path: the env
    narrower ``drain_posture`` already resolved, plus the ``[moments] agents
    = "off"`` config narrower (a separate axis ``DrainPosture`` does not
    track, since it narrows moment delivery, not drain itself)."""
    narrowers: list[str] = []
    if posture.narrowed_by is not None:
        narrowers.append(posture.narrowed_by)
    settings = moments.load_settings()
    if settings.agents is moments.MomentsMode.OFF:
        narrowers.append(f'[moments] agents = "off" (source={settings.agents_source})')
    return narrowers


def _drain_posture_files(posture: hosted_posture.DrainPosture) -> dict[str, str]:
    """All four hosted-posture files by absolute path, existing or not
    (plan.md sec:F-7 minors): the two drain files (already resolved on
    ``posture``) plus the two ``[moments]`` files this module already reads
    through for ``off``/``on``/``status`` above."""
    project_root = moments.locate_repo_root()
    repo_moments_path = str(project_root / ".kittify" / "config.toml") if project_root else "(no repository checkout found)"
    return {
        "repository (hosted.drain)": posture.repo_source,
        "repository ([moments])": repo_moments_path,
        "global ([moments])": str(moments.global_config_path()),
        "personal (hosted.drain)": posture.personal_source,
    }


def _drain_status_dict(posture: hosted_posture.DrainPosture, ledger: hosted_posture.LedgerPosture) -> dict[str, Any]:
    """The single source of both the human render and the ``--json`` form."""
    return {
        "effective": posture.enabled,
        "reason": posture.reason,
        "repository": {"value": posture.repo_value, "source": posture.repo_source},
        "personal": {"value": posture.personal_value, "source": posture.personal_source},
        "narrowers": _drain_narrowers(posture),
        "ledger": {"enabled": ledger.enabled, "source": ledger.source},
        "files": _drain_posture_files(posture),
    }


def _render_drain_status_human(payload: dict[str, Any]) -> None:
    console.print(f"{_EFFECTIVE_PREFIX}{'on' if payload['effective'] else 'off'} ({payload['reason']})", markup=False)
    repository = payload["repository"]
    personal = payload["personal"]
    console.print(f"  repository: {repository['value']} (source={repository['source']})", markup=False)
    console.print(f"  personal: {personal['value']} (source={personal['source']})", markup=False)
    narrowers = payload["narrowers"]
    console.print(f"  narrowers: {', '.join(narrowers) if narrowers else '(none)'}", markup=False)
    ledger = payload["ledger"]
    console.print(f"  ledger: {'on' if ledger['enabled'] else 'off'} (source={ledger['source']})", markup=False)
    console.print("  hosted-posture files:", markup=False)
    for label, path in payload["files"].items():
        console.print(f"    {label}: {path}", markup=False)
    if not payload["effective"]:
        console.print(f"  {hosted_posture.DRAIN_GUIDANCE_LINE.format(reason=payload['reason'])}", markup=False)


@drain_app.command("status")
def drain_status(as_json: bool = _JSON_OPTION) -> None:
    """Show the effective live-drain posture, both scopes' values and source
    files, active narrowers, the ledger-projection posture, and all four
    hosted-posture file paths (existing or not)."""
    posture = hosted_posture.drain_posture()
    ledger = hosted_posture.ledger_posture()
    payload = _drain_status_dict(posture, ledger)
    if as_json:
        console.emit_json(payload)
        return
    _render_drain_status_human(payload)
