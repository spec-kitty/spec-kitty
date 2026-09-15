"""Canonical hosted-server resolution for the surfaces that still call out.

Re-homed from ``specify_cli.sync.target_authority`` when the sync transport was
deleted (issue #5): auth login and the SaaS tracker client still need one
answer to "which server are we hitting?", resolved with a single precedence —
``SPEC_KITTY_SAAS_URL`` over ``config.toml [sync].server_url`` over the
packaged default ``https://team.spec-kitty.ai`` (#3980, D-5 revised: the
packaged default is the target; the env var is a dev/self-host override) —
and one fail-closed guard, decided *before* any network call: an ambiguous
split-brain (env and config disagreeing without a clean whole-process
override). #179's "no target at all" fail-closed died with the opt-in era: a
machine naming no target now resolves to the packaged launch host. An
*unset* env var is *no opinion* — it never disagrees with a configured
target, so an existing ``config.toml`` entry never trips the guard — but an
*explicitly set* one is a real opinion even when its value equals the
packaged default (#4259): it wins in a whole-process context (``auth
login``) instead of letting a stale configured target through, and it can
trip the setup-only guard against a different configured target.

The queue-scope half of the old resolver died with the sync transport; what
remains is purely descriptive — no network, no config mutation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

import toml

from specify_cli.auth.config import DEFAULT_HOSTED_SAAS_URL, get_saas_url_env_override

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
    """How the resolved target was chosen (descriptive only)."""

    NONE = "none"
    PROCESS_OVERRIDE = "process_override"
    SETUP_ONLY = "setup_only"
    PACKAGED_DEFAULT = "packaged_default"


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


@dataclass(frozen=True, slots=True)
class ResolvedServerTarget:
    """The resolved hosted-server target plus its provenance."""

    configured_server_url: str | None
    env_server_url: str | None
    override_mode: OverrideMode
    resolved_server_url: str

    def to_diagnostics_dict(self) -> dict[str, str | None]:
        """Return the resolution inputs for structured output."""
        return {
            "configured_server_url": self.configured_server_url,
            "env_server_url": self.env_server_url,
            "override_mode": self.override_mode.value,
            "resolved_server_url": self.resolved_server_url,
        }


def _normalize_url(url: str) -> str:
    """Normalize a URL for comparison and resolution: strip + drop trailing ``/``."""
    return url.strip().rstrip("/")


def _read_configured_server_url() -> str | None:
    """Read ``[sync].server_url``, normalizing absent/unreadable/blank to ``None``.

    Blank gets the same treatment the env read gives a whitespace-only value
    (#179): an empty string is no opinion, not a candidate target, so it must
    not slip past the fail-closed guard or pose as a disagreeing config value.
    """
    from specify_cli.paths import get_runtime_root

    config_file = get_runtime_root().base / "config.toml"
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

    The env-only override read (#3980): an unset variable is no opinion, never
    the packaged default, so a configured ``config.toml`` target wins without
    a split-brain.
    """
    return get_saas_url_env_override()


def _classify_override(
    configured_server_url: str | None,
    env_server_url: str | None,
    *,
    process_wide_override: bool,
) -> tuple[OverrideMode, str]:
    """Decide ``(override_mode, resolved_server_url)`` — pure, no I/O.

    Precedence: env first, then config, then the packaged default. An
    *unset* (or blank) env variable is *no opinion* (#3980, D-5 revised):
    ``config.toml [sync].server_url`` then wins without a split-brain, and
    with neither source set the packaged default is the target. An env
    variable that *is* explicitly set is a real opinion even when its value
    equals :data:`specify_cli.auth.config.DEFAULT_HOSTED_SAAS_URL` (#4259:
    the 4.0.0rc1 regression treated such a value as no opinion and let a
    stale configured target — the retired first-party app endpoint — win
    over an explicit canonical override): it resolves as the target, wins
    over a *different* configured value in a whole-process context, and
    trips the fail-closed guard against one in a setup-only context. A
    missing config key is likewise *no opinion*: an env-only machine
    resolves cleanly (to the env URL) even in a setup-only context, because
    with no configured value there is nothing for the env var to disagree
    with.
    """
    if env_server_url is None:
        if configured_server_url is None:
            return OverrideMode.PACKAGED_DEFAULT, DEFAULT_HOSTED_SAAS_URL
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
            "%s=%r overrides configured [sync].server_url=%r for this process; "
            "bearer-token-bearing traffic now targets %r instead of the configured host.",
            SAAS_URL_ENV_VAR,
            resolved_server_url,
            configured_server_url,
            resolved_server_url,
        )


def resolve_server_target(*, process_wide_override: bool = True) -> ResolvedServerTarget:
    """Resolve the single canonical hosted-server target.

    Reads ``[sync].server_url`` and ``SPEC_KITTY_SAAS_URL``, classifies the
    :class:`OverrideMode`, and fails-closed before any network call on an
    ambiguous split-brain. With neither source naming a target the packaged
    default (:data:`specify_cli.auth.config.DEFAULT_HOSTED_SAAS_URL`) is the
    target (#3980, D-5 revised) — an unconfigured machine no longer fails
    closed. Purely descriptive: no network, no config mutation.

    Raises:
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
    _warn_process_override(override_mode, configured_server_url, resolved_server_url)
    return ResolvedServerTarget(
        configured_server_url=configured_server_url,
        env_server_url=env_server_url,
        override_mode=override_mode,
        resolved_server_url=resolved_server_url,
    )
