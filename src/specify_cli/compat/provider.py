"""PyPI-backed version provider for the compat upgrade-nag planner.

Public surface
--------------
LatestVersionResult  – frozen dataclass encoding a single PyPI lookup outcome.
LatestVersionProvider – Protocol: one method, never raises.
PyPIProvider          – production implementation; hits pypi.org/pypi/<pkg>/json.
NoNetworkProvider     – CI / offline mode; always returns version=None.
FakeLatestVersionProvider – deterministic test double.

Security properties enforced here
-----------------------------------
CHK011  TLS verification ON (httpx default, never disabled).
CHK012  Response body capped at 1 MB; oversized returns error="oversized".
CHK013  Only pypi.org is contacted; follow_redirects=False.
CHK014  Redirects NOT followed (follow_redirects=False).
CHK015  Version string regex-validated before return; downgrade payloads rejected.
CHK016  ANSI / shell-metacharacter injection blocked by version sanitisation.
CHK018  Only the User-Agent header is set; no other request headers.
CHK048  No telemetry beyond the User-Agent string.
CHK049  User-Agent: ``spec-kitty-cli/<version> compat-planner``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PYPI_URL_TEMPLATE = "https://pypi.org/pypi/{package}/json"
_MAX_RESPONSE_BYTES: int = 1_048_576  # 1 MiB
_VERSION_RE = re.compile(r"^[A-Za-z0-9.\-+]{1,64}$")


def _get_installed_version() -> str:
    """Return the installed CLI version string for the active distribution.

    Resolves through the ``DistributionProfile`` (package name + aliases) so a
    renamed / private-index fork reports its own installed version rather than
    the upstream ``spec-kitty-cli`` metadata (#2857). Falls back to ``"unknown"``
    when no matching distribution metadata is installed (e.g. editable dev
    installs without metadata in the path).
    """
    try:
        from specify_cli.distribution import resolve_distribution_profile
        from specify_cli.distribution.installed_version import (
            resolve_installed_distribution_version,
        )

        profile = resolve_distribution_profile()
        return resolve_installed_distribution_version(
            profile.package_name, profile.package_aliases, default="unknown"
        )
    except Exception:  # noqa: BLE001
        return "unknown"


def _compat_user_agent() -> str:
    """Build the outbound User-Agent, self-identifying as the active distribution.

    A fork registers its own name via ``spec_kitty.cli_package`` /
    ``DistributionProfile`` so its private index sees the fork's identity, not
    the upstream ``spec-kitty-cli`` literal (#2857).
    """
    try:
        from specify_cli.distribution import resolve_cli_package_name

        name = resolve_cli_package_name()
    except Exception:  # noqa: BLE001
        name = "spec-kitty-cli"
    return f"{name}/{_get_installed_version()} compat-planner"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LatestVersionResult:
    """Outcome of a ``LatestVersionProvider.get_latest()`` call.

    Attributes:
        version: The sanitised version string returned by PyPI, or ``None`` when
            no version could be retrieved.
        source: Where the result came from.  ``"pypi"`` for a successful public
            PyPI lookup; ``"simple_index"`` for a successful PEP 503 simple-index
            lookup; ``"none"`` for offline / error paths.
        error: A fixed-vocabulary token describing the failure, or ``None`` on
            success.  Tokens: ``"timeout"``, ``"http_error"``, ``"parse_error"``,
            ``"oversized"``.  Never contains PII, file paths, or user data.
    """

    version: str | None
    source: Literal["pypi", "simple_index", "none"]
    error: str | None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class LatestVersionProvider(Protocol):
    """Abstract contract for any component that can report the latest published version.

    Implementations MUST NOT raise from ``get_latest``.  All failure modes are
    encoded as ``LatestVersionResult(version=None, source="none", error="<token>")``.
    """

    def get_latest(self, package: str, *, prerelease: bool = False) -> LatestVersionResult:
        """Return the latest published version for *package*.

        Args:
            package: The PyPI package name to query (e.g. ``"spec-kitty-cli"``).
            prerelease: When True (rc-channel opt-in, C-CHN-2), the highest
                version considered includes PEP 440 pre-releases. Default
                False reports the latest **stable** release only (C-CHN-1) —
                byte-identical to the pre-WP05 behaviour.

        Returns:
            A :class:`LatestVersionResult`.  Never raises.
        """
        ...  # pragma: no cover


def _highest_including_prerelease(stable_version: str, payload: object) -> str | None:
    """Return the highest installable version, rc's included.

    Yanked and fileless releases are excluded before applying
    ``simple_index._highest_version`` so the PyPI JSON and PEP 503 paths
    agree on which builds are available.
    Deferred import — ``simple_index`` imports from this module at load time,
    so a module-level import here would be circular.

    Falls back to *stable_version* when ``releases`` is absent/malformed or
    nothing in it parses.
    """
    from specify_cli.core.pypi_releases import installable_release_versions
    from specify_cli.distribution.simple_index import _highest_version

    candidates = [stable_version, *installable_release_versions(payload)]
    highest = _highest_version(candidates, include_prerelease=True)
    return highest if highest is not None else stable_version


# ---------------------------------------------------------------------------
# PyPIProvider
# ---------------------------------------------------------------------------


class PyPIProvider:
    """Fetch the latest version of a package from the PyPI JSON API.

    The provider constructs a short-lived :class:`httpx.Client` per call so that
    there is no long-lived connection state to manage.  TLS verification is on by
    default (httpx default) and is never disabled.

    Args:
        timeout_s: Seconds to wait before declaring a timeout (default 2.0).
        package_name_default: Ignored by ``get_latest`` — present for callers
            that want to record the intended package at construction time.
    """

    def __init__(
        self,
        timeout_s: float = 2.0,
        package_name_default: str = "spec-kitty-cli",
    ) -> None:
        self._timeout_s = timeout_s
        self._package_name_default = package_name_default

    def get_latest(self, package: str, *, prerelease: bool = False) -> LatestVersionResult:
        """Query ``https://pypi.org/pypi/{package}/json`` and return the version.

        Security properties enforced:

        - Only ``pypi.org`` is contacted; redirects are not followed (CHK013, CHK014).
        - The response body is capped at 1 MiB (CHK012).
        - The version string is regex-validated (CHK015, CHK016).
        - Only the ``User-Agent`` header is sent; no cookies, auth, or other headers
          (CHK018, CHK048, CHK049).

        Args:
            package: PyPI package name to look up.
            prerelease: When True (rc-channel opt-in, C-CHN-2), compute the
                highest version from ``payload["releases"]`` (PEP 440
                pre-releases included) instead of the maintainer-designated
                stable ``info.version``. Default False is byte-identical to
                the pre-WP05 behaviour (C-CHN-1) — the default-off consumer
                guarantee this WP exists to protect.

        Returns:
            A :class:`LatestVersionResult` describing the outcome.  Never raises.
        """
        user_agent = _compat_user_agent()
        url = _PYPI_URL_TEMPLATE.format(package=package)

        try:
            with httpx.Client(follow_redirects=False, timeout=self._timeout_s) as client:
                response = client.get(url, headers={"User-Agent": user_agent})
                # Enforce the 1 MiB cap BEFORE parsing JSON.
                raw = response.content
                if len(raw) > _MAX_RESPONSE_BYTES:
                    return LatestVersionResult(version=None, source="none", error="oversized")

                if response.is_error:
                    return LatestVersionResult(version=None, source="none", error="http_error")

                try:
                    payload = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    return LatestVersionResult(version=None, source="none", error="parse_error")

                try:
                    raw_version: object = payload["info"]["version"]
                except (KeyError, TypeError):
                    return LatestVersionResult(version=None, source="none", error="parse_error")

                if not isinstance(raw_version, str):
                    return LatestVersionResult(version=None, source="none", error="parse_error")

                if not _VERSION_RE.match(raw_version):
                    return LatestVersionResult(version=None, source="none", error="parse_error")

                if not prerelease:
                    return LatestVersionResult(version=raw_version, source="pypi", error=None)

                chosen = _highest_including_prerelease(raw_version, payload)
                if chosen is None or not _VERSION_RE.match(chosen):
                    return LatestVersionResult(version=None, source="none", error="parse_error")

                return LatestVersionResult(version=chosen, source="pypi", error=None)

        except httpx.TimeoutException:
            return LatestVersionResult(version=None, source="none", error="timeout")
        except httpx.HTTPError:
            return LatestVersionResult(version=None, source="none", error="http_error")


# ---------------------------------------------------------------------------
# NoNetworkProvider
# ---------------------------------------------------------------------------


class NoNetworkProvider:
    """Offline / CI provider that never opens a socket.

    Always returns ``LatestVersionResult(version=None, source="none", error=None)``.
    No ``httpx`` client is constructed by this class.
    """

    def get_latest(self, package: str, *, prerelease: bool = False) -> LatestVersionResult:  # noqa: ARG002
        """Return a no-network sentinel result.

        Args:
            package: Ignored; present for Protocol compatibility.
            prerelease: Ignored; present for Protocol compatibility.

        Returns:
            ``LatestVersionResult(version=None, source="none", error=None)``.
        """
        return LatestVersionResult(version=None, source="none", error=None)


# ---------------------------------------------------------------------------
# FakeLatestVersionProvider
# ---------------------------------------------------------------------------


class FakeLatestVersionProvider:
    """Deterministic test double for :class:`LatestVersionProvider`.

    Args:
        version: The version string to return.  ``None`` simulates "no version
            available" without an error (or with one if *error* is also set).
        error: If given, the returned result carries this error token and
            ``source="none"``.
        prerelease_version: Optional distinct version returned when the
            caller passes ``prerelease=True`` (T025 — lets a test observe
            that the channel bool was actually threaded through). Falls back
            to *version* when unset, so existing single-version callers are
            unaffected.
    """

    def __init__(
        self,
        version: str | None = None,
        *,
        error: str | None = None,
        prerelease_version: str | None = None,
    ) -> None:
        self._version = version
        self._error = error
        self._prerelease_version = prerelease_version

    def get_latest(self, package: str, *, prerelease: bool = False) -> LatestVersionResult:  # noqa: ARG002
        """Return the pre-configured result.

        Args:
            package: Ignored; present for Protocol compatibility.
            prerelease: When True and ``prerelease_version`` was supplied at
                construction, that version is returned instead of *version*.

        Returns:
            The :class:`LatestVersionResult` configured at construction time.
        """
        if self._error is not None:
            return LatestVersionResult(version=None, source="none", error=self._error)
        effective_version = (
            self._prerelease_version
            if prerelease and self._prerelease_version is not None
            else self._version
        )
        if effective_version is not None:
            return LatestVersionResult(version=effective_version, source="pypi", error=None)
        return LatestVersionResult(version=None, source="none", error=None)


def __getattr__(name: str) -> object:
    """Lazy re-export for discoverability without import cycles."""
    if name == "SimpleIndexProvider":
        from specify_cli.distribution.simple_index import SimpleIndexProvider

        return SimpleIndexProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
