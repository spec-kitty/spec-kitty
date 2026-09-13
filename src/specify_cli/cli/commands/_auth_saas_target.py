"""Shared SaaS-endpoint printer for ``auth status`` and ``auth whoami`` (#192).

Both commands print the identical ``SaaS:`` line (and the mismatch warning
underneath it) — ``print_saas_target`` and the formatters it composes with
live here, in one module neither command owns, instead of one command
importing the other's private helper (the shape that motivated #192: an
underscore-private symbol crossing module boundaries couples whoami's output
to status's internals and lets either module's refactor silently break the
other).
"""

from __future__ import annotations

from rich.markup import escape

from specify_cli.cli.console import console, sanitize_terminal_text

from specify_cli.auth.errors import ConfigurationError
from specify_cli.auth.server_target import (
    SAAS_URL_ENV_VAR,
    ResolvedServerTarget,
    ServerTargetSplitBrainError,
    resolve_server_target,
)
from specify_cli.auth.session import StoredSession


_SAAS_STATUS_LABEL = "  SaaS:           "


def print_saas_endpoint() -> ResolvedServerTarget | None:
    """Print the ``SaaS:`` endpoint line — the resolved URL + provenance, or
    the not-configured notice — and return the resolved target (``None`` on
    the not-configured branch).

    Split out of :func:`print_saas_target` so callers with no
    :class:`StoredSession` (the not-authenticated branch) can print this line
    alone, without the session-issuer/mismatch parts that need one (#189).

    The URL is the *same* resolved target ``auth login`` prints
    (:func:`specify_cli.auth.server_target.resolve_server_target`), so no two
    commands can ever name different endpoints. Since #3980 (D-5 revised)
    that resolver answers the packaged default ``https://team.spec-kitty.ai``
    when neither ``SPEC_KITTY_SAAS_URL`` nor ``config.toml`` names a server,
    so this line renders that default with ``(packaged default)`` provenance;
    the not-configured notice survives only for the resolver's genuine
    refusal shapes (a split-brain disagreement, rendered below).

    Resolved with ``process_wide_override=False`` (#193): this call is purely
    descriptive (no network, no config mutation), so it should show a
    genuine env/config disagreement instead of the whole-process override
    silently picking the env value — otherwise a split-brain machine looks
    identical to a clean one, with no hint that ``config.toml`` says
    something else. ``ServerTargetSplitBrainError`` is caught and rendered as
    a friendly line naming both values, never as a traceback.
    """
    try:
        target = resolve_server_target(process_wide_override=False)
    except ServerTargetSplitBrainError as exc:
        # escape(): the message embeds the raw config/env URLs, which are
        # attacker- or fat-finger-controlled and can contain
        # `[sync]`/`[/]`-shaped substrings (#182's rationale applies here too).
        console.print(f"{_SAAS_STATUS_LABEL}[red]split-brain[/red] [dim](env and config.toml disagree)[/dim]")
        console.print(f"  [yellow]{escape(sanitize_terminal_text(str(exc)))}[/yellow]")
        return None
    except ConfigurationError:
        # escape(): the remedy names `[sync].server_url` — unescaped, Rich
        # markup parses "[sync]" as a style tag and silently drops it (#182).
        remedy = escape(f"— set {SAAS_URL_ENV_VAR} (or [sync].server_url in config.toml)")
        console.print(f"{_SAAS_STATUS_LABEL}not configured [dim]{remedy}[/dim]")
        return None
    # escape(): both the resolved URL and the provenance suffix can contain
    # `[sync]`/`[/]`-shaped substrings (a config.toml server_url is
    # attacker- or fat-finger-controlled) — unescaped, Rich markup either
    # drops the bracketed text or raises MarkupError out of console.print,
    # which would violate this module's own never-fail invariant (#182).
    console.print(
        f"{_SAAS_STATUS_LABEL}{escape(sanitize_terminal_text(target.resolved_server_url))} "
        f"[dim]{escape(sanitize_terminal_text(format_saas_provenance(target)))}[/dim]"
    )
    return target


def print_saas_target(session: StoredSession) -> None:
    """Print the SaaS endpoint line plus, when it disagrees with where the
    session was minted, the mismatch warning.
    """
    target = print_saas_endpoint()
    _print_session_issuer(session.issuer_url)
    if target is None:
        return
    warning = format_saas_mismatch_warning(
        session.issuer_url,
        source_name=saas_source_name(target),
        resolved_server_url=target.resolved_server_url,
    )
    if warning is not None:
        console.print(f"  [yellow]{escape(sanitize_terminal_text(warning))}[/yellow]")


def _print_session_issuer(issuer_url: str | None) -> None:
    """Print where the stored session was minted, when the session knows it."""
    if issuer_url is None:
        return
    console.print(f"  Session SaaS:   {escape(sanitize_terminal_text(_normalize_endpoint(issuer_url)))} [dim](authenticated session)[/dim]")


def saas_source_name(target: ResolvedServerTarget) -> str:
    """Name the configuration source the resolved SaaS URL came from.

    Mirrors the precedence inside
    :func:`specify_cli.auth.server_target.resolve_server_target`: env first,
    then ``config.toml [sync].server_url``, then the packaged default
    ``https://team.spec-kitty.ai`` (#3980, D-5 revised — the packaged default
    is the target on a launch build with nothing else configured).
    Used in the mismatch warning so the sentence names the thing the user must
    change. Note ``.kittify/saas-auth.json`` is deliberately absent — it feeds
    the tracker/zeitgeist transport chain, not the OAuth login target.
    """
    if target.env_server_url is not None:
        # str(): SAAS_URL_ENV_VAR resolves as Any under mypy's
        # follow_imports=skip for specify_cli.* — the runtime value is a str.
        return str(SAAS_URL_ENV_VAR)
    if target.configured_server_url is not None:
        return "config.toml [sync].server_url"
    return "the packaged default"


def format_saas_provenance(target: ResolvedServerTarget) -> str:
    """Return the dim provenance suffix shown next to the ``SaaS:`` line."""
    if target.env_server_url is not None:
        return f"(from {SAAS_URL_ENV_VAR})"
    if target.configured_server_url is not None:
        return "(from config.toml [sync].server_url)"
    return "(packaged default)"


def format_saas_mismatch_warning(
    session_issuer_url: str | None,
    *,
    source_name: str,
    resolved_server_url: str,
) -> str | None:
    """Build the stale-session warning, or ``None`` when there is nothing to warn about.

    ``None`` when the session carries no issuer (minted before #176 recorded
    one — nothing to compare against) or when it matches the currently
    configured endpoint modulo a trailing slash.
    """
    if session_issuer_url is None:
        return None
    if _normalize_endpoint(session_issuer_url) == _normalize_endpoint(resolved_server_url):
        return None
    return f"Session is for {_normalize_endpoint(session_issuer_url)}; {source_name} now points at {resolved_server_url} — run spec-kitty auth login --force"


def _normalize_endpoint(url: str) -> str:
    """Normalize a URL for endpoint comparison.

    Same semantics as ``server_target._normalize_url`` (strip surrounding
    whitespace, drop one trailing slash); kept local so the comparison does
    not reach into another module's private helper.
    """
    return url.strip().rstrip("/")


# format_saas_provenance was demoted to module-private (#176/#192) when this
# module was its only consumer; #4259's pre-login target diagnostic in
# _auth_login.py is a second src/ consumer of the exact same provenance
# suffix, so it is re-exported rather than duplicated — login and auth
# status/whoami must never render different provenance for one target.
__all__ = [
    "print_saas_endpoint",
    "print_saas_target",
    "saas_source_name",
    "format_saas_mismatch_warning",
    "format_saas_provenance",
]
