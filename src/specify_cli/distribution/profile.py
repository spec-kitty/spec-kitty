"""Packager-facing ``DistributionProfile`` and its resolver.

Precedence for :func:`resolve_distribution_profile`:

1. ``spec_kitty.distribution_profile`` entry point (zero-arg callable/type →
   :class:`DistributionProfile`)
2. Synthesize from :func:`resolve_cli_package_name` +
   :func:`resolve_upgrade_provider` (Phase 1 thin aliases)
3. Stock defaults (what those resolvers return when nothing is registered)

Never raises. Multi-registration picks the first entry point name
alphabetically (same deterministic rule as the upgrade-provider resolver).
A registered profile that cannot be loaded or constructed resolves to the
degraded sentinel instead of substituting the public-PyPI stock profile.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from importlib.metadata import EntryPoint, entry_points

from specify_cli.compat.provider import (
    LatestVersionProvider,
    NoNetworkProvider,
    PyPIProvider,
)
from specify_cli.distribution.package_name import (
    DEFAULT_CLI_PACKAGE_NAME,
    resolve_cli_package_name,
)
from specify_cli.distribution.upgrade_provider import resolve_upgrade_provider

__all__ = [
    "DISTRIBUTION_PROFILE_GROUP",
    "DegradedDistributionProfile",
    "DistributionProfile",
    "clear_distribution_profile_cache",
    "is_degraded_distribution_profile",
    "resolve_distribution_profile",
    "stock_distribution_profile",
]

DISTRIBUTION_PROFILE_GROUP = "spec_kitty.distribution_profile"

_cached_profile: DistributionProfile | None = None


_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DistributionProfile:
    """Aggregated packager knobs for CLI identity, upgrade source, and UX.

    Attributes:
        package_name: Canonical distribution name (never from a runtime env var).
        package_aliases: Ordered fallbacks for installed-version lookup.
        upgrade_provider: Resolved :class:`LatestVersionProvider` instance, or
            ``None`` when the packager leaves upgrade lookup unset.
        index_url: Primary simple/PyPI-compatible index for remediation argv.
        extra_index_url: Secondary index for remediation argv.
        data_freshness_seconds: Optional TTL override for re-query decisions.
        disable_public_pypi_notifier: When ``True``, suppress the stock
            public-PyPI “no upgrade” notice.
        version_label: Optional ``--version`` banner label; ``None`` means use
            ``package_name``.
        feedback_endpoint: Default Feedback Endpoint for the Feedback Survey;
            ``None`` leaves automatic surveys dormant. Validated at resolution
            time, not here.
    """

    package_name: str
    package_aliases: tuple[str, ...] = ()
    upgrade_provider: LatestVersionProvider | object | None = None
    index_url: str | None = None
    extra_index_url: str | None = None
    data_freshness_seconds: int | None = None
    disable_public_pypi_notifier: bool = False
    version_label: str | None = None
    feedback_endpoint: str | None = None


@dataclass(frozen=True)
class DegradedDistributionProfile(DistributionProfile):
    """Fail-closed profile returned when a registered profile cannot load."""


def clear_distribution_profile_cache() -> None:
    """Clear the process-level memo (tests only)."""
    global _cached_profile
    _cached_profile = None


def stock_distribution_profile() -> DistributionProfile:
    """Return the public-PyPI / ``spec-kitty-cli`` stock profile."""
    return DistributionProfile(
        package_name=DEFAULT_CLI_PACKAGE_NAME,
        package_aliases=(),
        upgrade_provider=PyPIProvider(),
        index_url=None,
        extra_index_url=None,
        data_freshness_seconds=None,
        disable_public_pypi_notifier=False,
        version_label=None,
        feedback_endpoint=None,
    )


def is_degraded_distribution_profile(profile: DistributionProfile) -> bool:
    """Return whether *profile* is the fail-closed distribution sentinel."""
    return isinstance(profile, DegradedDistributionProfile)


def resolve_distribution_profile() -> DistributionProfile:
    """Return the active distribution profile. Never raises."""
    global _cached_profile
    if _cached_profile is not None:
        return _cached_profile
    profile = _resolve_distribution_profile_uncached()
    _cached_profile = profile
    return profile


def _resolve_distribution_profile_uncached() -> DistributionProfile:
    try:
        discovered = list(entry_points(group=DISTRIBUTION_PROFILE_GROUP))
    except Exception:
        return _synthesize_from_phase1()

    selected = _select_entry_point(discovered)
    if selected is None:
        return _synthesize_from_phase1()

    return _profile_from_entry_point(selected)


def _synthesize_from_phase1() -> DistributionProfile:
    """Build a minimal profile from Phase 1 resolvers (FR-017 thin aliases)."""
    try:
        package_name = resolve_cli_package_name()
    except Exception:
        package_name = DEFAULT_CLI_PACKAGE_NAME

    try:
        provider: LatestVersionProvider | object | None = resolve_upgrade_provider()
    except Exception:
        provider = PyPIProvider()

    # Derive from the single stock definition so field defaults (index_url,
    # freshness TTL, notifier flag, …) live in one place and cannot drift; only
    # the Phase-1-resolvable fields are overridden.
    return replace(
        stock_distribution_profile(),
        package_name=package_name,
        upgrade_provider=provider,
    )


def _select_entry_point(discovered: list[EntryPoint]) -> EntryPoint | None:
    if not discovered:
        return None
    if len(discovered) == 1:
        return discovered[0]
    return sorted(discovered, key=lambda entry: entry.name)[0]


def _profile_from_entry_point(entry: EntryPoint) -> DistributionProfile:
    try:
        loaded = entry.load()
    except Exception:
        _log.error(
            "spec_kitty.distribution_profile entry point %r failed to load; using the degraded profile and disabling remediation",
            entry.name,
            exc_info=True,
        )
        return _degraded_profile()

    try:
        if isinstance(loaded, DistributionProfile):
            return loaded
        if isinstance(loaded, type):
            instance = loaded()
            if isinstance(instance, DistributionProfile):
                return instance
        elif callable(loaded):
            value = loaded()
            if isinstance(value, DistributionProfile):
                return value
    except TypeError:
        _log.error(
            "spec_kitty.distribution_profile entry point %r raised TypeError "
            "while constructing its DistributionProfile; "
            "using the degraded profile and disabling remediation.",
            entry.name,
            exc_info=True,
        )
        return _degraded_profile()
    except Exception:
        _log.error(
            "spec_kitty.distribution_profile entry point %r raised while constructing a profile; using the degraded profile and disabling remediation",
            entry.name,
            exc_info=True,
        )
        return _degraded_profile()

    _log.error(
        "spec_kitty.distribution_profile entry point %r did not produce a DistributionProfile; using the degraded profile and disabling remediation",
        entry.name,
    )
    return _degraded_profile()


def _degraded_profile() -> DegradedDistributionProfile:
    return DegradedDistributionProfile(
        package_name="",
        upgrade_provider=NoNetworkProvider(),
        disable_public_pypi_notifier=True,
    )
