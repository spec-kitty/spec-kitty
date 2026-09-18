"""PyPI upgrade probe with no-upgrade classification.

This module is the network-touching half of the "no-upgrade available" UX
introduced for FR-007 / WP09. It performs a single, timeout-bounded GET against
PyPI's JSON metadata endpoint and classifies the installed CLI version.

The probe applies the **secure-design-checklist** tactic
(`packs/built-in/tactics/secure-design-checklist.tactic.yaml`) to the new
external surface. Specifically:

- **Least Privilege**: a single GET against a public endpoint, no auth, no PII.
- **Fail-Safe Defaults**: every exception is caught and resolves to
  ``UpgradeChannel.UNKNOWN`` with the error captured. No exception escapes
  into the CLI hot path.
- **Complete Mediation**: the timeout is enforced via ``httpx.Client(timeout=...)``
  and applied to the request.
- **Economy of Mechanism**: pure functions, frozen dataclasses, no I/O outside
  the GET. The cache is a sibling module's concern.

The probe **never** raises. Callers can rely on the returned
``UpgradeProbeResult`` being well-formed even on total network failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

from kernel.clock import datetime, now_utc

from specify_cli.core.version_compare import is_version_newer, try_parse_version

PYPI_JSON_URL = "https://pypi.org/pypi/spec-kitty-cli/json"
"""PyPI's standard JSON metadata endpoint for the ``spec-kitty-cli`` package."""

DEFAULT_TIMEOUT_S = 2.0
"""Hard ceiling on the probe wall-clock budget. Any timeout resolves to UNKNOWN."""


class UpgradeChannel(StrEnum):
    """Classification of installed CLI version relative to PyPI metadata.

    The four values correspond to the channel-classification rules in
    ``contracts/upgrade-probe-and-notifier.md``.
    """

    ALREADY_CURRENT = "already_current"
    """Installed version equals PyPI ``info.version`` (you're on the latest)."""

    AHEAD_OF_PYPI = "ahead_of_pypi"
    """Installed version > PyPI ``info.version`` (RC/dev build ahead of release)."""

    NO_UPGRADE_PATH = "no_upgrade_path"
    """Installed version not present in PyPI ``releases`` (non-PyPI build)."""

    UPGRADE_AVAILABLE = "upgrade_available"
    """Installed version is older than PyPI ``info.version``; existing nag owns it."""

    UNKNOWN = "unknown"
    """Probe failed: timeout, HTTP error, parse error, or malformed response."""


@dataclass(frozen=True)
class UpgradeProbeResult:
    """Outcome of a single PyPI probe.

    Frozen dataclass — caller cannot mutate. Serialized to JSON for the
    sibling notifier's cache; see ``upgrade_notifier`` for the cache schema.
    """

    installed_version: str
    """The value ``get_cli_version()`` returned at probe time."""

    latest_pypi_version: str | None
    """``info.version`` from PyPI, or ``None`` when the probe failed.

    Channel-aware (T022, C-CHN-2): when the rc channel is opted into (see
    ``prerelease`` on :func:`probe_pypi`), this is instead the highest
    version across ``releases`` (pre-releases included). Default-off (the
    common case) this is byte-identical to ``info.version``.
    """

    channel: UpgradeChannel
    """Classification of ``installed_version`` relative to PyPI metadata."""

    probed_at: datetime
    """UTC timestamp of the probe. ISO-8601 when serialized to the cache."""

    error: str | None = None
    """Populated when ``channel == UNKNOWN``; otherwise ``None``."""

    releases: tuple[str, ...] = field(default=())
    """All known PyPI release versions. Empty tuple on probe failure.

    Kept in the result so the notifier's cache layer can re-classify if the
    installed version changes mid-cache-window without re-probing.
    """


def probe_pypi(
    cli_version: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    transport: httpx.BaseTransport | None = None,
    prerelease: bool | None = None,
) -> UpgradeProbeResult:
    """Query PyPI and classify the installed CLI version.

    Args:
        cli_version: The installed CLI version (from ``get_cli_version()``).
        timeout_s: Hard timeout on the network call. Defaults to 2 s.
        transport: Optional httpx transport for tests (``MockTransport`` etc.).
            Production callers should leave this unset.
        prerelease: Channel override for tests. ``None`` (the production
            default) resolves the single read via
            ``core.channel.prerelease_enabled()`` — this function is the top
            of its own call graph (the notifier caller doesn't thread the
            channel through), so it is the one place the flag is read rather
            than accepted as a required argument. When True (T022, C-CHN-2),
            classification uses the highest version across all published
            releases (pre-releases included) instead of PyPI's stable
            ``info.version``, so an installed rc build is classified against
            its own channel instead of always reading ``AHEAD_OF_PYPI``.

    Returns:
        A well-formed ``UpgradeProbeResult``. Never raises.

    Notes:
        - The User-Agent identifies the CLI per the secure-design-checklist
          "Open Design" principle (auditable client identity).
        - The function swallows ``Exception`` deliberately. PyPI / network
          failures must not break the user's command invocation. The error
          message is captured in ``UpgradeProbeResult.error`` for debugging.
    """
    if prerelease is None:
        from specify_cli.core.channel import prerelease_enabled

        prerelease = prerelease_enabled()

    user_agent = f"spec-kitty-cli/{cli_version} (https://github.com/spec-kitty/spec-kitty)"
    probed_at = now_utc()

    try:
        client_kwargs: dict[str, Any] = {
            "timeout": httpx.Timeout(timeout_s),
            "headers": {"User-Agent": user_agent},
        }
        if transport is not None:
            client_kwargs["transport"] = transport

        with httpx.Client(**client_kwargs) as client:
            response = client.get(PYPI_JSON_URL)
            response.raise_for_status()
            payload = response.json()

        info = payload.get("info") or {}
        latest = info.get("version")
        if not isinstance(latest, str) or not latest:
            return _unknown(
                cli_version,
                probed_at,
                "PyPI response missing info.version",
            )

        releases_dict = payload.get("releases") or {}
        if not isinstance(releases_dict, dict):
            return _unknown(
                cli_version,
                probed_at,
                "PyPI response releases is not an object",
            )
        releases = tuple(releases_dict.keys())

        from specify_cli.core.pypi_releases import installable_release_versions

        channel_latest = _channel_latest(
            latest, installable_release_versions(payload), prerelease=prerelease
        )
        channel = _classify(cli_version, channel_latest, releases)
        return UpgradeProbeResult(
            installed_version=cli_version,
            latest_pypi_version=channel_latest,
            channel=channel,
            probed_at=probed_at,
            error=None,
            releases=releases,
        )

    except Exception as exc:  # noqa: BLE001 — fail-safe-default per secure-design-checklist
        return _unknown(cli_version, probed_at, f"{type(exc).__name__}: {exc}")


def _channel_latest(stable_latest: str, releases: tuple[str, ...], *, prerelease: bool) -> str:
    """Return the "latest" version to classify against, per the active channel.

    Default (``prerelease=False``, C-CHN-1): *stable_latest* — PyPI's
    maintainer-designated ``info.version`` — unchanged. Opted in
    (``prerelease=True``, C-CHN-2): the highest version across installable *releases*
    (pre-releases included), reusing ``simple_index._highest_version`` as the
    single source of truth so this module and ``compat.provider`` never
    drift on "highest version, rc's included" semantics.
    """
    if not prerelease:
        return stable_latest

    from specify_cli.distribution.simple_index import _highest_version

    highest = _highest_version([stable_latest, *releases], include_prerelease=True)
    return highest if highest is not None else stable_latest


def _unknown(cli_version: str, probed_at: datetime, error: str) -> UpgradeProbeResult:
    """Build an UNKNOWN-channel result with a debug-friendly error string."""
    return UpgradeProbeResult(
        installed_version=cli_version,
        latest_pypi_version=None,
        channel=UpgradeChannel.UNKNOWN,
        probed_at=probed_at,
        error=error,
        releases=(),
    )


def _classify(
    installed: str,
    latest: str,
    releases: tuple[str, ...],
) -> UpgradeChannel:
    """Classify the installed version against PyPI metadata per the contract.

    Returns ``UNKNOWN`` only when the installed version cannot be parsed as a
    PEP 440 version. Network/parse failures are handled upstream in
    :func:`probe_pypi`.
    """
    installed_ver = try_parse_version(installed)
    if installed_ver is None:
        return UpgradeChannel.UNKNOWN

    # ``latest`` may be malformed — try_parse_version falls through to the
    # releases-membership check below (via is_version_newer returning False)
    # rather than raising.
    latest_ver = try_parse_version(latest)

    if latest_ver is not None and installed_ver == latest_ver:
        return UpgradeChannel.ALREADY_CURRENT
    if is_version_newer(installed, latest):
        return UpgradeChannel.AHEAD_OF_PYPI

    # installed != latest (or latest unparseable). Check releases membership.
    if installed not in releases:
        return UpgradeChannel.NO_UPGRADE_PATH

    # Installed version is in releases but is older than latest. There IS an
    # upgrade path, so the no-upgrade notifier must stay silent and let the
    # existing upgrade nag render the actionable prompt.
    return UpgradeChannel.UPGRADE_AVAILABLE


__all__ = [
    "PYPI_JSON_URL",
    "DEFAULT_TIMEOUT_S",
    "UpgradeChannel",
    "UpgradeProbeResult",
    "probe_pypi",
]
