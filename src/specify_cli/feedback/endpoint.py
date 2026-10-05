"""Resolve the effective Feedback Endpoint for the Feedback Survey.

Precedence (first present candidate wins; an invalid higher-precedence value
does **not** fall through):

1. ``SPEC_KITTY_FEEDBACK_URL`` environment variable
2. Caller-supplied user override (typically ``SurveyPreferences.endpoint_override``)
3. ``DistributionProfile.feedback_endpoint``
4. none (automatic surveys dormant)

Validation: scheme must be ``https``, or ``http`` with a loopback hostname
(``127.0.0.1``, ``::1``, or ``localhost``). Never raises.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from specify_cli.distribution.profile import (
    DistributionProfile,
    resolve_distribution_profile,
)

__all__ = [
    "ENV_FEEDBACK_URL",
    "EndpointSource",
    "RejectedReason",
    "ResolvedEndpoint",
    "describe_endpoint",
    "resolve_feedback_endpoint",
]

ENV_FEEDBACK_URL = "SPEC_KITTY_FEEDBACK_URL"

EndpointSource = Literal["env", "user", "distribution", "none"]
RejectedReason = Literal["insecure_scheme", "invalid_url"]

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

_DESC_FROM_ENV = " (from SPEC_KITTY_FEEDBACK_URL)"
_DESC_FROM_USER = " (from user override)"
_DESC_FROM_DISTRIBUTION = " (from distribution default)"
_DESC_NONE_CONFIGURED = "none (no feedback endpoint configured)"
_DESC_ENV_INSECURE = "none (SPEC_KITTY_FEEDBACK_URL rejected: must use https unless loopback)"
_DESC_USER_INSECURE = "none (user override rejected: must use https unless loopback)"
_DESC_DISTRIBUTION_INSECURE = "none (distribution default rejected: must use https unless loopback)"
_DESC_ENV_INVALID = "none (SPEC_KITTY_FEEDBACK_URL rejected: invalid URL)"
_DESC_USER_INVALID = "none (user override rejected: invalid URL)"
_DESC_DISTRIBUTION_INVALID = "none (distribution default rejected: invalid URL)"

_SOURCE_OK_SUFFIX: Mapping[EndpointSource, str] = {
    "env": _DESC_FROM_ENV,
    "user": _DESC_FROM_USER,
    "distribution": _DESC_FROM_DISTRIBUTION,
    "none": "",
}

_INSECURE_BY_SOURCE: Mapping[EndpointSource, str] = {
    "env": _DESC_ENV_INSECURE,
    "user": _DESC_USER_INSECURE,
    "distribution": _DESC_DISTRIBUTION_INSECURE,
    "none": _DESC_NONE_CONFIGURED,
}

_INVALID_BY_SOURCE: Mapping[EndpointSource, str] = {
    "env": _DESC_ENV_INVALID,
    "user": _DESC_USER_INVALID,
    "distribution": _DESC_DISTRIBUTION_INVALID,
    "none": _DESC_NONE_CONFIGURED,
}


@dataclass(frozen=True)
class ResolvedEndpoint:
    """The effective Feedback Endpoint after precedence and validation."""

    url: str | None
    source: EndpointSource
    rejected_reason: RejectedReason | None = None


def resolve_feedback_endpoint(
    *,
    override: str | None,
    env: Mapping[str, str] | None = None,
    profile: DistributionProfile | None = None,
) -> ResolvedEndpoint:
    """Resolve the effective Feedback Endpoint. Never raises."""
    env_map = os.environ if env is None else env
    active_profile = resolve_distribution_profile() if profile is None else profile

    candidates: list[tuple[EndpointSource, str | None]] = [
        ("env", env_map.get(ENV_FEEDBACK_URL)),
        ("user", override),
        ("distribution", active_profile.feedback_endpoint),
    ]

    for source, raw in candidates:
        if raw is None:
            continue
        return _validate_candidate(raw, source)

    return ResolvedEndpoint(url=None, source="none", rejected_reason=None)


def describe_endpoint(resolved: ResolvedEndpoint) -> str:
    """Human-readable summary for ``spec-kitty feedback --status``."""
    if resolved.url is not None:
        return f"{resolved.url}{_SOURCE_OK_SUFFIX[resolved.source]}"
    if resolved.rejected_reason == "insecure_scheme":
        return _INSECURE_BY_SOURCE[resolved.source]
    if resolved.rejected_reason == "invalid_url":
        return _INVALID_BY_SOURCE[resolved.source]
    return _DESC_NONE_CONFIGURED


def _validate_candidate(raw: str, source: EndpointSource) -> ResolvedEndpoint:
    candidate = raw.strip()
    if not candidate:
        return ResolvedEndpoint(url=None, source=source, rejected_reason="invalid_url")

    try:
        parts = urlsplit(candidate)
    except ValueError:
        return ResolvedEndpoint(url=None, source=source, rejected_reason="invalid_url")

    hostname = parts.hostname
    if not parts.scheme or hostname is None:
        return ResolvedEndpoint(url=None, source=source, rejected_reason="invalid_url")

    scheme = parts.scheme.lower()
    if scheme == "https":
        return ResolvedEndpoint(url=candidate, source=source, rejected_reason=None)
    if scheme == "http":
        if hostname.lower() in _LOOPBACK_HOSTS:
            return ResolvedEndpoint(url=candidate, source=source, rejected_reason=None)
        return ResolvedEndpoint(url=None, source=source, rejected_reason="insecure_scheme")

    return ResolvedEndpoint(url=None, source=source, rejected_reason="invalid_url")
