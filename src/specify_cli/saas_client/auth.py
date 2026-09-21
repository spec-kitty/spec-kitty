"""Auth context loading for the SaaS client.

Reads ``SPEC_KITTY_SAAS_URL``, ``SPEC_KITTY_SAAS_TOKEN``, and optional
``SPEC_KITTY_TEAM_SLUG`` from the environment, falling back to
``.kittify/saas-auth.json`` when env vars are absent, and finally to the
OAuth session ``spec-kitty auth login`` persists (spec-kitty#198).  Raises
``SaasAuthError`` if no token can be resolved. D-5 revised (#3980): the
packaged default ``https://team.spec-kitty.ai`` is the target — the env var
is a dev/self-host override — so a missing URL no longer fails closed here;
the refusal below is reachable only when the canonical resolver itself is
unavailable.

Scope of the #237 trust boundary (#289): this module only ever pairs
``.kittify/saas-auth.json``'s ``saas_url`` with its own token, never with an
env-supplied one — that is what #237 fixed and what the docstrings below
describe. That boundary does not, and cannot, extend to ``os.environ``
itself: the per-repo ``.kittify/.kitty.env`` tier
(:mod:`specify_cli.bootstrap.env_file`) seeds ``SPEC_KITTY_SAAS_URL`` (and
other governed vars) into ``os.environ`` from committed, checkout-controlled
content, before this module ever runs. That is documented, intended
behaviour (``docs/api/environment-variables.md``, "The ``.kitty.env``
file"), not a bug in this module — #289 is the tracking issue for the
resulting residual: a value this module treats as "the environment" may
itself trace back to a cloned repository.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specify_cli.saas_client.errors import SaasAuthError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthContext:
    """Resolved SaaS authentication context."""

    saas_url: str
    token: str
    team_slug: str | None = None  # extracted from token payload if available


def load_auth_context(repo_root: Path | None = None) -> AuthContext:
    """Load SaaS auth context.

    Resolution order:
    1. ``SPEC_KITTY_SAAS_TOKEN`` env var. Its URL comes from
       ``SPEC_KITTY_SAAS_URL`` if set, else the canonical server target
       (:func:`specify_cli.auth.server_target.resolve_server_target`) —
       never from ``.kittify/saas-auth.json``, which a checkout controls
       (#237: a repo-local URL must not redirect an env-supplied token).
       Its ``team_slug`` comes only from ``SPEC_KITTY_TEAM_SLUG``, for the
       same reason: the file must not override the scope of an env-resolved
       token. ``.kittify/saas-auth.json`` is not read at all once
       ``SPEC_KITTY_SAAS_TOKEN`` is set — its url and team_slug are never
       consulted then either, so reading it would only risk failing on a
       malformed file the caller never needed (#291).
    2. ``.kittify/saas-auth.json`` relative to *repo_root* (if provided) —
       its ``token`` paired with its own ``saas_url`` and ``team_slug``
       (falling back to ``SPEC_KITTY_SAAS_URL`` / ``SPEC_KITTY_TEAM_SLUG``
       only when the file omits them).
    3. The stored OAuth session written by ``spec-kitty auth login``
       (#198): its access token as the bearer, paired with the canonical
       server target (:func:`specify_cli.auth.server_target.resolve_server_target`)
       — refreshed first through the renewable-session flow when expired.
       Its ``team_slug`` comes only from ``SPEC_KITTY_TEAM_SLUG``; a
       repo-local file may not scope an operator's stored session.
    4. Raises ``SaasAuthError`` if no token is found, or if no SaaS URL is
       supplied by any source and the canonical resolver is unavailable (D-5
       revised, #3980: the packaged default is the target, so a missing URL
       resolves to it rather than failing closed).

    Args:
        repo_root: Optional path to the repository root.  Used to locate
            ``.kittify/saas-auth.json`` when env vars are absent.

    Returns:
        Resolved :class:`AuthContext`.

    Raises:
        SaasAuthError: If no token can be resolved, or if no SaaS URL is
            supplied by env var, auth file, or the canonical resolver (the
            packaged default included — the refusal below fires only when
            that resolver itself is unavailable).
    """
    env_url = os.environ.get("SPEC_KITTY_SAAS_URL", "").strip()
    env_token = os.environ.get("SPEC_KITTY_SAAS_TOKEN", "").strip()
    env_team_slug = os.environ.get("SPEC_KITTY_TEAM_SLUG", "").strip() or None
    team_slug = env_team_slug

    file_url = ""
    file_token = ""
    file_team_slug: str | None = None
    # Only touch the file when there is no env token — the file's token,
    # url, and team_slug are all discarded once env_token is set (#237: an
    # env-supplied token never pairs with a checkout-controlled url/scope),
    # so a caller with env_token set never needed the file, regardless of
    # whether SPEC_KITTY_SAAS_URL is also set (#291: reading it anyway turned
    # a merely-present malformed file into a hard failure for such a caller,
    # even though every field it could have contributed was already dead).
    if repo_root is not None and not env_token:
        auth_file = repo_root / ".kittify" / "saas-auth.json"
        if auth_file.exists():
            try:
                data = json.loads(auth_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                raise SaasAuthError(f"Failed to read .kittify/saas-auth.json: {exc}") from exc
            file_token = data.get("token", "").strip()
            file_url = data.get("saas_url", "").strip()
            file_team_slug = data.get("team_slug") or None

    # Trust boundary (#237): the URL and the bearer must come from the same
    # source. A checkout-controlled .kittify/saas-auth.json may name a
    # saas_url, but only alongside its own token — never paired with the
    # env-supplied service token, which is typically longer-lived and more
    # broadly scoped than what a checkout should be able to redirect. The
    # same invariant applies to team_slug: it is a per-request scope selector
    # (zeitgeist_client/resolution.py), so the file may only supply it
    # alongside its own token, never as an override of an env-resolved token
    # or the stored OAuth session.
    if env_token:
        token = env_token
        url = env_url or _server_target_url()
    elif file_token:
        token = file_token
        # #3980 (D-5 revised): a file token with no repo-local url pairs with
        # the env override or the canonical resolver's target (packaged
        # default included) — the file's own url still only ever rides with
        # its own token (#237).
        url = file_url or env_url or _server_target_url()
        team_slug = team_slug or file_team_slug
    else:
        token = ""
        url = env_url or file_url
        team_slug = env_team_slug

    if not token:
        bridged = _oauth_session_context()
        if bridged is not None:
            # Keep the OAuth bearer and SaaS URL inside one trust boundary.
            # A repo-local auth file may name a SaaS URL, but it must not
            # redirect a personal login token to a checkout-controlled host.
            return AuthContext(
                saas_url=bridged.saas_url,
                token=bridged.token,
                team_slug=team_slug,
            )
        raise SaasAuthError("no SaaS token configured: set SPEC_KITTY_SAAS_TOKEN, provide .kittify/saas-auth.json, or run `spec-kitty auth login`")

    # D-5 revised (#3980): the packaged default is the target, so this refusal
    # is reachable only when the canonical resolver itself is unavailable
    # (``_server_target_url`` degrades any resolver failure to ``""`` — e.g.
    # an env/config split-brain, which :func:`resolve_server_target` fails
    # closed on before any network call). The URL must come from the
    # environment, the auth file, or that resolver; falling back further would
    # silently point the client at the wrong server (#2248 / #2146 canonical
    # target authority). Fail closed instead.
    if not url:
        if env_token:
            # #290: an env-supplied token never pairs with .kittify/saas-auth.json's
            # saas_url (#237) — naming that file here would send an operator to set
            # a key that this exact path refuses to honour.
            raise SaasAuthError(
                "SaaS URL not configured: set SPEC_KITTY_SAAS_URL or config.toml's "
                "[sync].server_url (an env-supplied SPEC_KITTY_SAAS_TOKEN is never "
                "paired with .kittify/saas-auth.json's saas_url — #237; the hosted "
                "target could not be resolved)."
            )
        raise SaasAuthError(
            'SaaS URL not configured: set SPEC_KITTY_SAAS_URL or provide "saas_url" in .kittify/saas-auth.json (the hosted target could not be resolved).'
        )

    return AuthContext(saas_url=url, token=token, team_slug=team_slug)


def _oauth_session_context() -> AuthContext | None:
    """The step-3 bridge to the ``spec-kitty auth login`` session (#198).

    A human on the documented path authenticates once with ``auth login``
    and never writes a service token anywhere, so when neither env nor
    ``.kittify/saas-auth.json`` carries a bearer this resolves the persisted
    OAuth session instead — otherwise ``spec-kitty routes``, the relay
    capability mint, and every other consumer of this module would refuse a
    fully authenticated laptop.

    The session's token is paired with :func:`resolve_server_target`'s
    answer — the same env-over-config-over-default resolution ``auth login``
    itself used to pick the server it authenticated against (#3406) — but
    only when that answer matches the session's own ``issuer_url``; a
    session recorded against one server is refused, not paired, when the
    resolved target now names a different one (#234).
    ``resolve_server_target`` still fails closed on an ambiguous split-brain;
    that refusal surfaces here as a distinct ``SaasAuthError`` naming both
    URLs (#306) rather than folding into the caller's generic "no SaaS token
    configured: ... run `spec-kitty auth login`" message — on a split-brain
    machine login already succeeded (FR-005 lets it win), so pointing the
    operator back at it is a no-op loop; the real fix is reconciling
    ``config.toml``/``SPEC_KITTY_SAAS_URL``.

    Every other *bridge-unavailable* failure still degrades to ``None`` plus
    a debug log: for the fire-and-forget status fan-out an unusable session
    means "stay silent". A dead session or an issuer mismatch is different —
    both are refusals that must reach interactive callers as a
    ``SaasAuthError`` naming the remedy, not silence. The token is only ever
    read from the store, never written anywhere.
    """
    from specify_cli.auth.errors import IssuerTargetMismatchError  # noqa: PLC0415
    from specify_cli.auth.server_target import ServerTargetSplitBrainError  # noqa: PLC0415

    try:
        manager = _token_manager()
        target = _resolved_server_target()
        session = manager.get_current_session()
    except ServerTargetSplitBrainError as exc:
        raise SaasAuthError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — any other bridge trouble means "not available"
        logger.debug("OAuth session bridge unavailable (%s)", exc)
        return None

    if session is None:
        return None

    # Deliberately outside the guard above: a dead stored session, or one
    # minted for a server other than the one resolved_server_url now names,
    # is a refusal that must reach interactive callers, not a silent "not
    # available" (#234). ``_guard_session_issuer`` raises the shared
    # ``IssuerTargetMismatchError`` (WP01); the ``SaasAuthError`` translation
    # stays here so the bridge's public contract (raise ``SaasAuthError``)
    # is unchanged.
    try:
        _guard_session_issuer(session, target)
    except IssuerTargetMismatchError as exc:
        raise _issuer_mismatch_to_saas_auth_error(exc, target) from exc

    return AuthContext(
        saas_url=target.resolved_server_url,
        token=_usable_access_token(manager, session),
    )


def _guard_session_issuer(session: Any, target: Any) -> None:
    """Refuse to pair *session* with a server it was not minted for (#234).

    ``spec-kitty auth status`` has warned about this exact mismatch since
    #176 (``format_saas_mismatch_warning``) — the OAuth bridge must refuse
    the same way instead of silently sending a personal bearer to a server
    it never authenticated against. Sessions minted before #176 carry
    ``issuer_url=None``: nothing was recorded to compare, so they keep
    working unchanged.

    Consumes the shared issuer/target decision (WP01,
    ``specify_cli.auth.server_target``): the canonical ``_normalize_url``
    for the comparison (no local duplicate normalizer participates in a
    token-bearing comparison, NFR-002) and the canonical
    :class:`~specify_cli.auth.errors.IssuerTargetMismatchError` carrying the
    shared remedy id — rather than reimplementing the compare/normalize/
    remedy logic locally. Raises the raw error; :func:`_oauth_session_context`
    (this function's only caller) translates it to ``SaasAuthError``.
    """
    from specify_cli.auth.errors import IssuerTargetMismatchError  # noqa: PLC0415
    from specify_cli.auth.server_target import _normalize_url  # noqa: PLC0415

    issuer_url: str | None = session.issuer_url
    if issuer_url is None:
        return
    normalized_issuer = _normalize_url(issuer_url)
    normalized_target = _normalize_url(target.resolved_server_url)
    if normalized_issuer == normalized_target:
        return
    raise IssuerTargetMismatchError(
        issuer_url=normalized_issuer,
        resolved_url=normalized_target,
        source_name=_saas_source_name(target),
    )


def _issuer_mismatch_to_saas_auth_error(exc: Any, target: Any) -> SaasAuthError:
    """Build the ``SaasAuthError`` this module raises for an issuer mismatch.

    Reconstructs the pre-existing wording (no backticks, no trailing period —
    the format ``spec-kitty auth status``/#300 users already see) from
    ``IssuerTargetMismatchError``'s structured fields rather than using its
    own ``str()`` (which carries backticks + a period). Shared by
    :func:`_oauth_session_context` and :func:`_usable_access_token` so the
    two call sites do not duplicate the f-string.
    """
    return SaasAuthError(f"Session is for {exc.issuer_url}; {_saas_source_name(target)} now points at {exc.resolved_url} — run spec-kitty {exc.remedy}")


def _saas_source_name(target: Any) -> str:
    """Name the configuration source ``target.resolved_server_url`` came from.

    Mirrors ``specify_cli.cli.commands._auth_status.saas_source_name``
    (#300) so this refusal names the same override source ``spec-kitty auth
    status`` would — duplicated locally so this module does not reach into
    a CLI-presentation module's helper.
    """
    from specify_cli.auth.server_target import SAAS_URL_ENV_VAR  # noqa: PLC0415

    if target.env_server_url is not None:
        return str(SAAS_URL_ENV_VAR)
    if target.configured_server_url is not None:
        return "config.toml [sync].server_url"
    return "the default endpoint"


def _token_manager() -> Any:
    """The process-wide :class:`specify_cli.auth.TokenManager`.

    Imported lazily: the auth package pulls the encrypted-store machinery,
    which nothing else in ``saas_client`` should pay for at import time (and
    which would make this module's import order matter to every CLI start).
    """
    from specify_cli.auth import get_token_manager  # noqa: PLC0415

    return get_token_manager()


def _resolved_server_target() -> Any:
    """The canonical hosted-server target (env over config over default).

    ``process_wide_override=False`` (#117): every caller of this helper —
    :func:`_oauth_session_context` (bridged into the fire-and-forget
    status-moment credential mint) and :func:`_server_target_url` (paired
    with an env-supplied bearer token) — sends a bearer token with no human
    confirming the target at call time. An ambiguous env/config disagreement
    must fail closed here (as ``ServerTargetSplitBrainError``) rather than
    silently letting the env value win, the way the interactive `auth login`
    command's whole-process override is allowed to. Both callers already
    degrade any exception from this function to ``None``/``""``.
    """
    from specify_cli.auth.server_target import resolve_server_target  # noqa: PLC0415

    return resolve_server_target(process_wide_override=False)


def _server_target_url() -> str:
    """Best-effort canonical server target URL, for pairing with an
    env-supplied token when ``SPEC_KITTY_SAAS_URL`` itself is unset (#237).

    Resolved via :func:`resolve_server_target` (env or ``config.toml``), which
    this function treats as trusted *relative to
    ``.kittify/saas-auth.json``* — a checkout-controlled file this module
    reads directly and refuses to pair with an env token (#237). It is not a
    claim that ``os.environ`` is itself checkout-free: the module docstring
    above (#289) names the separate, documented trust surface the per-repo
    ``.kitty.env`` tier introduces. Any resolution trouble (nothing
    configured, split-brain) degrades to ``""`` — the caller's own "SaaS URL
    not configured" refusal already says what to do.
    """
    try:
        # Bound to a typed local because ``resolve_server_target``'s result is
        # seen as ``Any`` under ``follow_imports = skip`` (campsite, #4755).
        resolved: str = _resolved_server_target().resolved_server_url
        return resolved
    except Exception as exc:  # noqa: BLE001 — any resolution trouble means "no url from this source"
        logger.debug("Server target resolution unavailable for env-token pairing (%s)", exc)
        return ""


def _dead_session_errors() -> tuple[type[Exception], ...]:
    """Refresh failures that mean *this session is finished* — as opposed to
    transient transport/lock trouble, which must not log the user out of the
    bridge (Team Kitty will answer 401 to a truly dead held token anyway).

    ``IssuerTargetMismatchError`` (WP01) is a member so
    :func:`_usable_access_token`'s first ``except`` below catches it as a
    hard refusal — it must never fall through to the bare
    ``except Exception`` branch that keeps the held token (FR-008, the
    held-token re-leak trap: a refresh refusal for the wrong reason must not
    be mistaken for transient trouble)."""
    from specify_cli.auth.errors import (  # noqa: PLC0415
        IssuerTargetMismatchError,
        NotAuthenticatedError,
        RefreshTokenExpiredError,
        SessionInvalidError,
    )

    return (
        IssuerTargetMismatchError,
        NotAuthenticatedError,
        RefreshTokenExpiredError,
        SessionInvalidError,
    )


def _usable_access_token(manager: Any, session: Any) -> str:
    """A current access token for *session*, refreshing when it has expired.

    Raises :class:`SaasAuthError` when the renewable-session flow reports the
    stored session dead — that is a refusal, not silence: ``routes`` should
    tell the human to log in again. Transient refresh trouble (network down,
    lock contention) keeps the held token: the gateway call will surface the
    real fault, and resolution caches nothing behind a 401.

    Guards the SEND, not only the refresh (FR-008, D-2 adversarial finding):
    a still-valid *held* access token must also be blocked when the session's
    issuer disagrees with the resolved target, independent of whether a
    caller already ran ``_guard_session_issuer`` upstream — this function is
    exercised directly (in isolation) by
    ``tests/saas_client/test_held_token_non_demotion.py``. Resolves the
    target via this module's own :func:`_resolved_server_target` (the same
    seam :func:`_oauth_session_context` uses) rather than a second,
    independent live resolution, so both guards always agree on one
    decision for a given call.
    """
    from specify_cli.auth.errors import IssuerTargetMismatchError  # noqa: PLC0415
    from specify_cli.auth.server_target import ServerTargetSplitBrainError  # noqa: PLC0415

    try:
        target = _resolved_server_target()
        _guard_session_issuer(session, target)
    except ServerTargetSplitBrainError as exc:
        raise SaasAuthError(str(exc)) from exc
    except IssuerTargetMismatchError as exc:
        raise _issuer_mismatch_to_saas_auth_error(exc, target) from exc

    # ``specify_cli.*`` is type-checked with ``follow_imports = skip``, so the
    # cross-package session attributes are seen as ``Any``; bind to a
    # ``str``-typed local to keep the declared return type honest.
    held: str = session.access_token

    if not session.is_access_token_expired():
        return held

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        # A loop owns this thread; asyncio.run would raise. Best effort: hand
        # back what we hold rather than fail an otherwise-working checkout.
        logger.debug("OAuth session expired but an event loop owns this thread; using the held token")
        return held

    try:
        asyncio.run(manager.refresh_if_needed())
    except SaasAuthError:
        raise
    except _dead_session_errors() as exc:
        raise SaasAuthError(f"The stored spec-kitty session is no longer usable ({exc}); run `spec-kitty auth login` again.") from exc
    except Exception as exc:  # noqa: BLE001 — refresh trouble falls back to the held token
        logger.debug("OAuth session refresh failed (%s); using the held token", exc)

    refreshed = manager.get_current_session()
    if refreshed is None:
        raise SaasAuthError("The stored spec-kitty session disappeared while refreshing; run `spec-kitty auth login` again.")
    rotated: str = refreshed.access_token
    return rotated
