"""Canonical hosted-server resolution for the surfaces that still call out.

Re-homed from ``specify_cli.sync.target_authority`` when the sync transport was
deleted (issue #5): auth login and the SaaS tracker client still need one
answer to "which server are we hitting?", resolved with a single precedence —
``SPEC_KITTY_SAAS_URL`` over ``config.toml [sync].server_url`` — plus two
fail-closed guards, both decided *before* any network call: no target at all
(endpoint opt-in, mission ``hosted-opt-in-drain-ledger``, FR-011/FR-012 — this
reverses #3980 D-5: there is no packaged default any more), and an ambiguous
split-brain (env and config disagreeing without a clean whole-process
override). An *unset* env var is *no opinion* — it never disagrees with a
configured target, so an existing ``config.toml`` entry never trips the
split-brain guard — but an *explicitly set* one is a real opinion even when
its value equals the first-party host's identity
(:data:`specify_cli.auth.config.DEFAULT_HOSTED_SAAS_URL`, #4259): it wins in
a whole-process context (``auth login``) instead of letting a stale
configured target through, and it can trip the setup-only guard against a
different configured target.

The queue-scope half of the old resolver died with the sync transport; what
remains is purely descriptive — no network, no config mutation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import toml

from specify_cli.auth.config import format_endpoint_unconfigured_message, get_saas_url_env_override
from specify_cli.auth.errors import ConfigurationError, IssuerTargetMismatchError

if TYPE_CHECKING:
    from specify_cli.auth.session import StoredSession

_LOG = logging.getLogger(__name__)

#: Mirrors ``specify_cli.auth.config._ENV_VAR``; named here so the fail-closed
#: and split-brain messages and the env read share one literal (Sonar S1192).
#: Explicitly typed: consumers under ``follow_imports = "skip"`` would
#: otherwise see ``Any``.
SAAS_URL_ENV_VAR: str = "SPEC_KITTY_SAAS_URL"

_SPLIT_BRAIN_MESSAGE = (
    "Server target split-brain detected before any network call: config.toml "
    "[sync].server_url={config!r} disagrees with environment "
    "{env_var}={env!r}. Either set {env_var} as an explicit whole-process "
    "override so every hosted call resolves to a single target, or remove "
    "{env_var}."
)


class OverrideMode(StrEnum):
    """How the resolved target was chosen (descriptive only).

    ``PACKAGED_DEFAULT`` was removed entirely (endpoint opt-in, F-5/F-7 m4):
    it becomes unreachable rather than merely unused, since
    :func:`resolve_server_target` now raises
    :class:`HostedEndpointUnconfigured` before ever constructing a
    :class:`ResolvedServerTarget` for the "neither source names a target"
    case.
    """

    NONE = "none"
    PROCESS_OVERRIDE = "process_override"
    SETUP_ONLY = "setup_only"


class ServerTargetSplitBrainError(RuntimeError):
    """Raised when env and config disagree without a clean whole-process override.

    The message names both URLs and the source so an operator can reconcile
    ``config.toml`` and ``SPEC_KITTY_SAAS_URL``.
    """

    def __init__(self, *, configured_server_url: str | None, env_server_url: str | None) -> None:
        super().__init__(
            _SPLIT_BRAIN_MESSAGE.format(
                config=configured_server_url,
                env=env_server_url,
                env_var=SAAS_URL_ENV_VAR,
            )
        )
        self.configured_server_url = configured_server_url
        self.env_server_url = env_server_url


class HostedEndpointUnconfigured(ConfigurationError):
    """Raised when neither SPEC_KITTY_SAAS_URL nor config.toml [sync].server_url names a hosted endpoint.

    Endpoint opt-in (mission ``hosted-opt-in-drain-ledger``, FR-011/FR-012):
    reverses #3980 D-5's packaged-default fallback. A
    :class:`~specify_cli.auth.errors.ConfigurationError` subclass, so every
    pre-existing ``except ConfigurationError`` boundary (e.g.
    ``cli/commands/_auth_login.py``) already handles it with no code change.
    """


@dataclass(frozen=True, slots=True)
class ResolvedServerTarget:
    """The resolved hosted-server target plus its provenance."""

    configured_server_url: str | None
    env_server_url: str | None
    override_mode: OverrideMode
    resolved_server_url: str


def _normalize_url(url: str) -> str:
    """Normalize a URL for comparison and resolution: strip + drop trailing ``/``."""
    return url.strip().rstrip("/")


def _read_configured_server_url() -> str | None:
    """Read ``[sync].server_url``, normalizing absent/unreadable/blank to ``None``.

    Blank gets the same treatment the env read gives a whitespace-only value
    (#179): an empty string is no opinion, not a candidate target, so it must
    not slip past the fail-closed guard or pose as a disagreeing config value.
    """
    from specify_cli.paths import get_runtime_config_toml_path

    config_file = get_runtime_config_toml_path()
    if not config_file.exists():
        return None
    try:
        data = toml.load(config_file)
    except (toml.TomlDecodeError, OSError):
        return None
    sync_table = data.get("sync")
    if not isinstance(sync_table, dict):
        return None
    value = sync_table.get("server_url")
    if value is None:
        return None
    return _normalize_url(str(value)) or None


def _read_env_server_url() -> str | None:
    """Read ``SPEC_KITTY_SAAS_URL``, normalizing blank/whitespace to ``None``.

    The env-only override read (#3980): an unset variable is no opinion, so a
    configured ``config.toml`` target wins without a split-brain.
    """
    # ``specify_cli.*`` is type-checked with ``follow_imports = skip``, so the
    # cross-module ``get_saas_url_env_override()`` is seen as ``Any`` here; bind to a
    # ``str | None``-typed local to keep the declared return type honest (campsite, #4755).
    env_override: str | None = get_saas_url_env_override()
    return env_override


def _classify_override(
    configured_server_url: str | None,
    env_server_url: str | None,
    *,
    process_wide_override: bool,
) -> tuple[OverrideMode, str | None]:
    """Decide ``(override_mode, resolved_server_url)`` — pure, no I/O.

    Precedence: env first, then config. An *unset* (or blank) env variable
    is *no opinion*: ``config.toml [sync].server_url`` then wins without a
    split-brain, and with neither source set the resolution is unconfigured
    — ``resolved_server_url`` is ``None`` (endpoint opt-in, FR-011: this
    reverses #3980 D-5's packaged-default fallback; :func:`resolve_server_target`
    raises :class:`HostedEndpointUnconfigured` for that case rather than
    ever returning a ``None`` target). An env variable that *is* explicitly
    set is a real opinion even when its value equals
    :data:`specify_cli.auth.config.DEFAULT_HOSTED_SAAS_URL` (#4259: the
    4.0.0rc1 regression treated such a value as no opinion and let a stale
    configured target — the retired first-party app endpoint — win over an
    explicit canonical override): it resolves as the target, wins over a
    *different* configured value in a whole-process context, and trips the
    fail-closed guard against one in a setup-only context. A missing config
    key is likewise *no opinion*: an env-only machine resolves cleanly (to
    the env URL) even in a setup-only context, because with no configured
    value there is nothing for the env var to disagree with.
    """
    if env_server_url is None:
        if configured_server_url is None:
            return OverrideMode.NONE, None
        return OverrideMode.NONE, _normalize_url(str(configured_server_url))
    env_normalized = _normalize_url(env_server_url)
    if configured_server_url is None:
        return OverrideMode.PROCESS_OVERRIDE, env_normalized
    effective_config = _normalize_url(configured_server_url)
    if env_normalized == effective_config:
        return OverrideMode.NONE, effective_config
    if process_wide_override:
        # Whole-process override: env wins everywhere.
        return OverrideMode.PROCESS_OVERRIDE, env_normalized
    # Disagreement scoped to a setup/diagnostic context — the guard fails-closed.
    return OverrideMode.SETUP_ONLY, effective_config


def _guard_split_brain(
    override_mode: OverrideMode,
    configured_server_url: str | None,
    env_server_url: str | None,
) -> None:
    """Fail-closed for an ambiguous env/config disagreement."""
    if override_mode is OverrideMode.SETUP_ONLY:
        raise ServerTargetSplitBrainError(
            configured_server_url=configured_server_url,
            env_server_url=env_server_url,
        )


def _warn_process_override(
    override_mode: OverrideMode,
    configured_server_url: str | None,
    resolved_server_url: str,
) -> None:
    """Log when a whole-process override silently redirects a *configured* target.

    Only fires when ``configured_server_url`` names an actual, different target
    that ``{env_var}`` is overriding — an env-only machine has no configured
    opinion to override, so it is not a redirection and stays quiet (#117:
    editing ``[sync].server_url`` or ``{env_var}`` used to be cross-checked
    against a durable per-project admission binding before that binding was
    deleted with the sync transport; this is the visible signal that survives
    without resurrecting that store).
    """
    if override_mode is OverrideMode.PROCESS_OVERRIDE and configured_server_url is not None:
        _LOG.warning(
            "%s=%r overrides configured [sync].server_url=%r for this process; bearer-token-bearing traffic now targets %r instead of the configured host.",
            SAAS_URL_ENV_VAR,
            resolved_server_url,
            configured_server_url,
            resolved_server_url,
        )


def resolve_server_target(*, process_wide_override: bool = True) -> ResolvedServerTarget:
    """Resolve the single canonical hosted-server target.

    Reads ``[sync].server_url`` and ``SPEC_KITTY_SAAS_URL``, classifies the
    :class:`OverrideMode`, and fails-closed before any network call on
    either of two conditions: an ambiguous split-brain, or neither source
    naming a target at all (endpoint opt-in, FR-011 — this reverses #3980
    D-5's packaged-default fallback). Purely descriptive: no network, no
    config mutation.

    Raises:
        HostedEndpointUnconfigured: Neither ``SPEC_KITTY_SAAS_URL`` nor
            ``config.toml [sync].server_url`` names a target.
        ServerTargetSplitBrainError: When env and config disagree without a
            clean whole-process override.
    """
    configured_server_url = _read_configured_server_url()
    env_server_url = _read_env_server_url()
    override_mode, resolved_server_url = _classify_override(
        configured_server_url,
        env_server_url,
        process_wide_override=process_wide_override,
    )
    _guard_split_brain(override_mode, configured_server_url, env_server_url)
    if resolved_server_url is None:
        raise HostedEndpointUnconfigured(format_endpoint_unconfigured_message())
    _warn_process_override(override_mode, configured_server_url, resolved_server_url)
    return ResolvedServerTarget(
        configured_server_url=configured_server_url,
        env_server_url=env_server_url,
        override_mode=override_mode,
        resolved_server_url=resolved_server_url,
    )


def resolve_server_target_or_none(*, process_wide_override: bool = True) -> ResolvedServerTarget | None:
    """Like :func:`resolve_server_target`, but returns ``None`` instead of raising.

    For automatic/best-effort callers (FR-012) that must degrade quietly when
    nothing is configured, rather than surface setup guidance the caller
    cannot act on. :class:`ServerTargetSplitBrainError` still propagates — an
    ambiguous env/config disagreement is not "unconfigured", it is a real
    ambiguity a caller must not silently paper over (C-005/#4311 coupling: a
    future retry must not paper over a split-brain).
    """
    try:
        return resolve_server_target(process_wide_override=process_wide_override)
    except HostedEndpointUnconfigured:
        return None


def _source_name_for_target(target: ResolvedServerTarget) -> str:
    """Name the configuration source ``target.resolved_server_url`` came from.

    Mirrors ``specify_cli.saas_client.auth._saas_source_name`` (#300, #423):
    each consumer keeps its own local copy of this small naming rule instead
    of importing another module's private helper, so this reference doesn't
    go stale as those copies move independently.

    A real :func:`resolve_server_target` call can no longer produce a
    ``target`` whose ``env_server_url`` and ``configured_server_url`` are
    both ``None`` (endpoint opt-in, FR-011: it raises
    :class:`HostedEndpointUnconfigured` before constructing one in that
    case) — but a caller can still hand this function a stale or
    hand-built :class:`ResolvedServerTarget` in that shape (e.g. a test
    double), so the third branch stays a real, coverable fallback rather
    than a coverage-suppressed dead one.
    """
    if target.env_server_url is not None:
        return SAAS_URL_ENV_VAR
    if target.configured_server_url is not None:
        return "config.toml [sync].server_url"
    return "the default endpoint"


def _issuer_target_decision(
    session: StoredSession | None,
) -> tuple[str, IssuerTargetMismatchError | None]:
    """Decide the token endpoint and, when applicable, the mismatch verdict.

    Pure decision, separated from the raise-based reaction in
    :func:`resolve_token_endpoint`, so a display-only consumer (e.g. a future
    ``auth status`` surface) can render the verdict without raising.

    Per ``contracts/issuer-target-helper.md``: the ONE ``_normalize_url`` is
    reused for both the comparison and the returned endpoint (NFR-002) —
    never a second, divergent normalizer.

    Raises:
        ServerTargetSplitBrainError: Propagated unchanged from
            ``resolve_server_target`` on an ambiguous env/config
            disagreement; callers map it themselves.
    """
    target = resolve_server_target(process_wide_override=False)
    resolved_endpoint = _normalize_url(target.resolved_server_url)
    if session is None or session.issuer_url is None:
        # Legacy/no-compare: never falls back to get_saas_base_url().
        return resolved_endpoint, None
    issuer_endpoint = _normalize_url(session.issuer_url)
    if issuer_endpoint == resolved_endpoint:
        return resolved_endpoint, None
    mismatch = IssuerTargetMismatchError(
        issuer_url=issuer_endpoint,
        resolved_url=resolved_endpoint,
        source_name=_source_name_for_target(target),
    )
    return resolved_endpoint, mismatch


def resolve_token_endpoint(session: StoredSession | None) -> str:
    """Resolve the single canonical endpoint a session's tokens may be sent to.

    This is the shared issuer-target authority every token-bearing flow
    (refresh, revoke, the SaaS client OAuth-session bridge)
    must consume instead of growing its own copy of the compare-and-refuse
    rule. See ``contracts/issuer-target-helper.md`` for the full contract.

    Args:
        session: The current :class:`StoredSession`, or ``None`` when no
            session is available. ``None`` follows the legacy/no-compare
            branch — it is never itself a mismatch.

    Returns:
        The normalized resolved server target a token-bearing call should
        use.

    Raises:
        IssuerTargetMismatchError: When ``session.issuer_url`` is set and
            disagrees with the resolved target.
        HostedEndpointUnconfigured: Propagated unchanged from
            ``resolve_server_target`` when neither source names a target
            (endpoint opt-in, FR-011/FR-012).
        ServerTargetSplitBrainError: Propagated unchanged from
            ``resolve_server_target`` on an ambiguous env/config
            disagreement.
    """
    endpoint, mismatch = _issuer_target_decision(session)
    if mismatch is not None:
        raise mismatch
    return endpoint
