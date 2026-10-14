"""Upgrade-readiness UX (WS3, issue Priivacy-ai/spec-kitty#1092).

Real prompt UX layered over the existing upgrade-nag chain:

- Snooze cadence (24h → 48h → 7d) anchored per remote version.
- Four choices: Upgrade now, Always keep me up to date, Not now, Never ask again.
- Safe auto-upgrade only for known-safe installers
  (``compat._detect.install_method.is_safe_for_auto_upgrade``).
- Env-driven preferences for "always", "never-ask", and a hard kill switch.

Hard guarantees:

- This module MUST NEVER prompt, MUST NEVER mutate the cache for a Not-now
  decision, and MUST NEVER invoke an auto-upgrade subprocess when the
  canonical ``_should_suppress_nag()`` returns True.  That predicate is the
  single source of truth for suppression (``--json``, ``--quiet``,
  ``--help``, ``--version``, ``CI``, non-TTY, ``SPEC_KITTY_NO_NAG``).
- This module MUST NOT add a new pip dependency.  Only stdlib + already-shipped
  pieces of the CLI.

The prompt/auto-upgrade orchestrator that used to live here ran only on the
hosted-enabled readiness path and was removed with the hosted surfaces
(#6164); what remains is the pure preference/cadence/choice logic used by
``spec-kitty upgrade``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from kernel.clock import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from specify_cli.core.env import is_truthy


class _CliStatusLike(Protocol):
    @property
    def installed_version(self) -> str: ...

    @property
    def latest_version(self) -> str | None: ...

    @property
    def latest_source(self) -> str: ...


# Public env keys (WS3 acceptance criterion 4).
ENV_UPGRADE_AUTO = "SPEC_KITTY_UPGRADE_AUTO"
ENV_UPGRADE_NEVER_ASK = "SPEC_KITTY_UPGRADE_NEVER_ASK"
ENV_UPGRADE_DISABLED = "SPEC_KITTY_UPGRADE_DISABLED"


# ---------------------------------------------------------------------------
# Choice + cadence
# ---------------------------------------------------------------------------


class UpgradeChoice(StrEnum):
    """Four prompt choices presented to the user.

    Values are stable identifiers; tests assert against them.
    """

    UPGRADE_NOW = "upgrade_now"
    ALWAYS = "always"
    NOT_NOW = "not_now"
    NEVER_ASK = "never_ask"


# Ladder of snooze durations (anchored per remote version).
_CADENCE_SECONDS: dict[str | None, tuple[str, int]] = {
    None: ("24h", 24 * 3600),
    "24h": ("48h", 48 * 3600),
    "48h": ("7d", 7 * 24 * 3600),
    "7d": ("7d", 7 * 24 * 3600),  # ceiling
}


def advance_snooze(
    current: str | None, *, now: datetime
) -> tuple[str, datetime]:
    """Advance the cadence ladder one step.

    The mapping is::

        None -> 24h (+24h)
        24h  -> 48h (+48h)
        48h  -> 7d  (+7d)
        7d   -> 7d  (+7d)   # ceiling

    Args:
        current: Current snooze step token, or ``None`` for "no snooze yet".
        now: Current UTC datetime; ``snoozed_until = now + step_duration``.

    Returns:
        ``(next_step_token, snoozed_until)``.
    """
    next_step, seconds = _CADENCE_SECONDS[current]
    return next_step, now + timedelta(seconds=seconds)


# ---------------------------------------------------------------------------
# Effective-preference resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectivePreference:
    """Per-invocation resolved user preference.

    Combines persisted NagCache state with env-var overrides.  The env
    overrides take effect for the current invocation only; they do not
    persist into the cache unless the user explicitly picks the matching
    choice at the prompt.
    """

    disabled: bool  # kill switch — short-circuit everything
    never_ask: bool
    always_upgrade: bool


def resolve_effective_preference(
    *,
    persisted_never_ask: bool,
    persisted_always_upgrade: bool,
    env: dict[str, str] | None = None,
) -> EffectivePreference:
    """Merge persisted preferences with env-var overrides.

    Args:
        persisted_never_ask: ``NagCacheRecord.never_ask``.
        persisted_always_upgrade: ``NagCacheRecord.always_upgrade``.
        env: Environment mapping (defaults to ``os.environ``).

    Returns:
        Effective preference flags for this invocation.
    """
    if env is None:
        env = dict(os.environ)
    return EffectivePreference(
        disabled=is_truthy(env.get(ENV_UPGRADE_DISABLED)),
        never_ask=persisted_never_ask or is_truthy(env.get(ENV_UPGRADE_NEVER_ASK)),
        always_upgrade=persisted_always_upgrade or is_truthy(env.get(ENV_UPGRADE_AUTO)),
    )


# ---------------------------------------------------------------------------
# Cadence anchoring
# ---------------------------------------------------------------------------


def needs_reset(
    *,
    record_remote_version: str | None,
    current_latest: str | None,
) -> bool:
    """Return True if the remote version has changed since the last cycle.

    A reset clears ``snooze_step`` / ``snoozed_until`` / ``never_ask``
    (per spec acceptance criterion 1, "A new remote version resets the
    cadence" — and the "Never ask again" choice is also bound to the
    specific remote version the user said it about).

    Args:
        record_remote_version: ``NagCacheRecord.remote_version_seen``.
        current_latest: ``CliStatus.latest_version`` from the planner.

    Returns:
        True iff ``record_remote_version is None`` or differs from
        ``current_latest`` (and ``current_latest`` is not None).
    """
    if current_latest is None:
        # Planner couldn't determine a remote; don't churn cadence.
        return False
    return record_remote_version != current_latest


def is_currently_snoozed(
    *, snoozed_until: datetime | None, now: datetime
) -> bool:
    """Return True iff the prompt should be suppressed by an active snooze."""
    if snoozed_until is None:
        return False
    return now < snoozed_until


# ---------------------------------------------------------------------------
# Mutation helpers (pure: take + return a NagCacheRecord)
# ---------------------------------------------------------------------------


def apply_choice(
    record_kwargs: dict[str, object],
    *,
    choice: UpgradeChoice,
    current_latest: str | None,
    now: datetime,
) -> dict[str, object]:
    """Return updated NagCacheRecord kwargs for the chosen action.

    Pure function: callers re-construct the record via ``dataclasses.replace``
    using these kwargs.

    Args:
        record_kwargs: Current record kwargs (as from ``dataclasses.asdict``-like).
        choice: The user's choice.
        current_latest: Remote latest_version from the planner.
        now: Current UTC datetime.

    Returns:
        Updated kwargs dict.
    """
    updated: dict[str, object] = dict(record_kwargs)
    # Anchor cadence to the version the user is responding about.
    if current_latest is not None:
        updated["remote_version_seen"] = current_latest

    if choice == UpgradeChoice.UPGRADE_NOW:
        # Clear snooze on a successful upgrade attempt (the caller may
        # still re-set it if the upgrade subprocess fails); also reset
        # cadence so a new version restarts cleanly.
        updated["snooze_step"] = None
        updated["snoozed_until"] = None
    elif choice == UpgradeChoice.ALWAYS:
        updated["always_upgrade"] = True
        updated["snooze_step"] = None
        updated["snoozed_until"] = None
    elif choice == UpgradeChoice.NOT_NOW:
        current_step = updated.get("snooze_step")
        if not isinstance(current_step, str):
            current_step = None
        next_step, snoozed_until = advance_snooze(current_step, now=now)
        updated["snooze_step"] = next_step
        updated["snoozed_until"] = snoozed_until
    elif choice == UpgradeChoice.NEVER_ASK:
        updated["never_ask"] = True
        updated["snooze_step"] = None
        updated["snoozed_until"] = None

    return updated


__all__ = [
    # ENV_UPGRADE_AUTO, ENV_UPGRADE_NEVER_ASK: demoted — env-var constants
    # consumed only within this module (WP01 harden-dead-symbol-gate-01KW0RJR).
    "ENV_UPGRADE_DISABLED",
    # EffectivePreference, PromptCallback, UpgradeUxOutcome, advance_snooze:
    # demoted — no cross-module src/ from-import callers (WP01).
    "UpgradeChoice",
    "apply_choice",
    "is_currently_snoozed",
    "needs_reset",
    "resolve_effective_preference",
]
