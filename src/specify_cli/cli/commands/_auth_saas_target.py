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

from specify_cli.auth.server_target import (
    SAAS_URL_ENV_VAR,
    OverrideMode,
    ResolvedServerTarget,
    ServerTargetSplitBrainError,
    _normalize_url,
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
    ``resolve_server_target`` now raises only :class:`ServerTargetSplitBrainError`
    (#4053: the prior ``ConfigurationError`` branch here was dead — that
    resolver stopped raising it once the packaged default became the
    fallback — and has been removed rather than left unreachable).

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
    console.print(f"  Session SaaS:   {escape(sanitize_terminal_text(_normalize_url(issuer_url)))} [dim](authenticated session)[/dim]")


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

    Keyed off :attr:`ResolvedServerTarget.override_mode` — the resolver's own
    verdict of which source *decided* the target — rather than the raw
    ``env_server_url``/``configured_server_url`` presence checks this used
    before #4053: those two fields can both be non-``None`` and still agree
    (``OverrideMode.NONE``, config wins with env matching it), a shape the
    old presence-first check mislabeled as ``SPEC_KITTY_SAAS_URL`` provenance.
    ``override_mode`` names the actual decision, so it cannot drift from it.
    """
    if target.override_mode is OverrideMode.PACKAGED_DEFAULT:
        return "the packaged default"
    if target.override_mode is OverrideMode.PROCESS_OVERRIDE:
        # str(): SAAS_URL_ENV_VAR resolves as Any under mypy's
        # follow_imports=skip for specify_cli.* — the runtime value is a str.
        return str(SAAS_URL_ENV_VAR)
    return "config.toml [sync].server_url"


def format_saas_provenance(target: ResolvedServerTarget) -> str:
    """Return the dim provenance suffix shown next to the ``SaaS:`` line.

    Keyed off ``override_mode``; see :func:`saas_source_name` for why (#4053).
    """
    if target.override_mode is OverrideMode.PACKAGED_DEFAULT:
        return "(packaged default)"
    if target.override_mode is OverrideMode.PROCESS_OVERRIDE:
        return f"(from {SAAS_URL_ENV_VAR})"
    return "(from config.toml [sync].server_url)"


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

    A display-only reaction on WP01's shared issuer-target decision
    (``contracts/issuer-target-helper.md``): it renders the verdict as a
    string and always returns, never raises, so ``auth status``/``doctor``
    keep rendering on a mismatch instead of aborting. The comparison reuses
    the canonical :func:`specify_cli.auth.server_target._normalize_url` — the
    same normalizer the token-bearing comparison uses — rather than a second,
    locally-defined copy (#4755 WP05, folding the module's former
    ``_normalize_endpoint`` into the one shared normalizer).
    """
    if session_issuer_url is None:
        return None
    if _normalize_url(session_issuer_url) == _normalize_url(resolved_server_url):
        return None
    return f"Session is for {_normalize_url(session_issuer_url)}; {source_name} now points at {resolved_server_url} — run spec-kitty auth login --force"


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
