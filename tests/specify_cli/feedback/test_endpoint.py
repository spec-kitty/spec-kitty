"""Acceptance tests for Feedback Endpoint resolution (WP02 / T008 + T012)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest

from specify_cli.distribution.profile import (
    DistributionProfile,
    stock_distribution_profile,
)
from specify_cli.feedback.endpoint import ResolvedEndpoint, describe_endpoint, resolve_feedback_endpoint

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# Reserved names only — vendor-neutral fixtures (RFC 6761 / loopback).
_EXAMPLE_HTTPS = "https://feedback.example.test/v1"
_LOOPBACK_IPV4 = "http://127.0.0.1:8765/x"
_LOOPBACK_LOCALHOST = "http://localhost/x"
_LOOPBACK_IPV6 = "http://[::1]/x"
_NON_LOOPBACK_HTTP = "http://feedback.example.test/x"

_SRC_FEEDBACK = Path(__file__).resolve().parents[3] / "src" / "specify_cli" / "feedback"
_URL_LITERAL = re.compile(r"https?://", re.IGNORECASE)
_LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")


def _resolve(
    *,
    override: str | None,
    env: Mapping[str, str] | None = None,
    profile: DistributionProfile | None = None,
) -> ResolvedEndpoint:
    return resolve_feedback_endpoint(override=override, env=env, profile=profile)


def _describe(resolved: ResolvedEndpoint) -> str:
    return describe_endpoint(resolved)


def _profile_with_endpoint(url: str | None) -> DistributionProfile:
    return replace(stock_distribution_profile(), feedback_endpoint=url)


# ---------------------------------------------------------------------------
# T008 – precedence and validation
# ---------------------------------------------------------------------------


def test_stock_profile_with_no_env_or_override_is_dormant() -> None:
    resolved = _resolve(override=None, env={}, profile=stock_distribution_profile())

    assert resolved.url is None
    assert resolved.source == "none"
    assert resolved.rejected_reason is None


def test_distribution_default_used_when_no_env_or_override() -> None:
    profile = _profile_with_endpoint(_EXAMPLE_HTTPS)

    resolved = _resolve(override=None, env={}, profile=profile)

    assert resolved.url == _EXAMPLE_HTTPS
    assert resolved.source == "distribution"
    assert resolved.rejected_reason is None


def test_user_override_wins_over_distribution_default() -> None:
    profile = _profile_with_endpoint(_EXAMPLE_HTTPS)
    override = "https://override.example.test/v1"

    resolved = _resolve(override=override, env={}, profile=profile)

    assert resolved.url == override
    assert resolved.source == "user"


def test_env_wins_over_override_and_distribution() -> None:
    profile = _profile_with_endpoint(_EXAMPLE_HTTPS)
    env_url = "https://env.example.test/v1"
    override = "https://override.example.test/v1"

    from specify_cli.feedback.endpoint import ENV_FEEDBACK_URL

    resolved = _resolve(
        override=override,
        env={ENV_FEEDBACK_URL: env_url},
        profile=profile,
    )

    assert resolved.url == env_url
    assert resolved.source == "env"


@pytest.mark.parametrize(
    "url",
    [_LOOPBACK_IPV4, _LOOPBACK_LOCALHOST, _LOOPBACK_IPV6],
)
def test_loopback_http_is_accepted(url: str) -> None:
    resolved = _resolve(override=url, env={}, profile=stock_distribution_profile())

    assert resolved.url == url
    assert resolved.source == "user"
    assert resolved.rejected_reason is None


def test_non_loopback_http_rejected_as_insecure_scheme() -> None:
    resolved = _resolve(
        override=_NON_LOOPBACK_HTTP,
        env={},
        profile=stock_distribution_profile(),
    )

    assert resolved.url is None
    assert resolved.source == "user"
    assert resolved.rejected_reason == "insecure_scheme"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://feedback.example.test/x",
        "not a url",
        "",
        "   ",
    ],
)
def test_invalid_url_candidates_resolve_to_none(url: str) -> None:
    resolved = _resolve(override=url, env={}, profile=stock_distribution_profile())

    assert resolved.url is None
    assert resolved.source == "user"
    assert resolved.rejected_reason == "invalid_url"


def test_invalid_higher_precedence_does_not_fall_through() -> None:
    profile = _profile_with_endpoint(_EXAMPLE_HTTPS)

    resolved = _resolve(
        override=_NON_LOOPBACK_HTTP,
        env={},
        profile=profile,
    )

    assert resolved.url is None
    assert resolved.source == "user"
    assert resolved.rejected_reason == "insecure_scheme"


def test_degraded_profile_resolves_to_none() -> None:
    from specify_cli.distribution.profile import _degraded_profile

    resolved = _resolve(override=None, env={}, profile=_degraded_profile())

    assert resolved.url is None
    assert resolved.source == "none"
    assert resolved.rejected_reason is None


def test_default_profile_and_env_come_from_live_resolvers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``profile`` / ``env`` defaults are the live distribution + ``os.environ``."""
    from specify_cli.feedback import endpoint as endpoint_mod

    monkeypatch.setenv(endpoint_mod.ENV_FEEDBACK_URL, _EXAMPLE_HTTPS)
    monkeypatch.setattr(
        endpoint_mod,
        "resolve_distribution_profile",
        lambda: stock_distribution_profile(),
    )

    resolved = endpoint_mod.resolve_feedback_endpoint(override=None)

    assert resolved.url == _EXAMPLE_HTTPS
    assert resolved.source == "env"


# ---------------------------------------------------------------------------
# T011 / T012 – describe_endpoint
# ---------------------------------------------------------------------------


def test_describe_endpoint_distribution_default() -> None:
    from specify_cli.feedback.endpoint import ResolvedEndpoint

    text = _describe(ResolvedEndpoint(url=_EXAMPLE_HTTPS, source="distribution", rejected_reason=None))

    assert text == f"{_EXAMPLE_HTTPS} (from distribution default)"


def test_describe_endpoint_none_configured() -> None:
    from specify_cli.feedback.endpoint import ResolvedEndpoint

    text = _describe(ResolvedEndpoint(url=None, source="none", rejected_reason=None))

    assert text == "none (no feedback endpoint configured)"


def test_describe_endpoint_env_rejected_insecure() -> None:
    from specify_cli.feedback.endpoint import ResolvedEndpoint

    text = _describe(ResolvedEndpoint(url=None, source="env", rejected_reason="insecure_scheme"))

    assert text == ("none (SPEC_KITTY_FEEDBACK_URL rejected: must use https unless loopback)")


def test_describe_endpoint_user_source_label() -> None:
    from specify_cli.feedback.endpoint import ResolvedEndpoint

    text = _describe(ResolvedEndpoint(url=_EXAMPLE_HTTPS, source="user", rejected_reason=None))

    assert text == f"{_EXAMPLE_HTTPS} (from user override)"


def test_describe_endpoint_env_source_label() -> None:
    from specify_cli.feedback.endpoint import ResolvedEndpoint

    text = _describe(ResolvedEndpoint(url=_EXAMPLE_HTTPS, source="env", rejected_reason=None))

    assert text == f"{_EXAMPLE_HTTPS} (from SPEC_KITTY_FEEDBACK_URL)"


def test_describe_endpoint_invalid_url_rejection() -> None:
    from specify_cli.feedback.endpoint import ResolvedEndpoint

    text = _describe(ResolvedEndpoint(url=None, source="user", rejected_reason="invalid_url"))

    assert "rejected" in text
    assert "invalid" in text.lower()


def test_urlsplit_value_error_is_invalid_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.feedback import endpoint as endpoint_mod

    def boom(_value: str) -> object:
        raise ValueError("synthetic urlsplit failure")

    monkeypatch.setattr(endpoint_mod, "urlsplit", boom)
    resolved = _resolve(
        override="https://feedback.example.test/v1",
        env={},
        profile=stock_distribution_profile(),
    )

    assert resolved.url is None
    assert resolved.source == "user"
    assert resolved.rejected_reason == "invalid_url"


def test_describe_endpoint_distribution_insecure() -> None:
    from specify_cli.feedback.endpoint import ResolvedEndpoint

    text = _describe(ResolvedEndpoint(url=None, source="distribution", rejected_reason="insecure_scheme"))

    assert "distribution default rejected" in text
    assert "https" in text


def test_describe_endpoint_distribution_invalid() -> None:
    from specify_cli.feedback.endpoint import ResolvedEndpoint

    text = _describe(ResolvedEndpoint(url=None, source="distribution", rejected_reason="invalid_url"))

    assert "distribution default rejected" in text
    assert "invalid" in text.lower()


# ---------------------------------------------------------------------------
# T012 – neutrality guard
# ---------------------------------------------------------------------------


def _http_url_literals_in(text: str) -> list[str]:
    """Return http(s) URL substrings found in *text* (for scanning source)."""
    return _URL_LITERAL.findall(text)  # scheme markers; full match via finditer below


def _non_loopback_http_urls_in(text: str) -> list[str]:
    """Return full ``http(s)://…`` spans whose host is not a loopback example."""
    found: list[str] = []
    for match in re.finditer(r"https?://[^\s'\"`)\]]+", text, flags=re.IGNORECASE):
        span = match.group(0)
        lowered = span.lower()
        if any(host in lowered for host in _LOOPBACK_HOSTS):
            continue
        found.append(span)
    return found


def test_neutrality_scanner_positive_control() -> None:
    """The scanner must flag a synthetic non-loopback URL (non-vacuous gate)."""
    synthetic = 'endpoint = "https://feedback.example.test/v1"\n'
    assert _non_loopback_http_urls_in(synthetic) == ["https://feedback.example.test/v1"]
    assert _http_url_literals_in(synthetic)  # scheme markers present


def test_feedback_package_has_no_hardcoded_non_loopback_urls() -> None:
    offenders: list[str] = []
    for path in sorted(_SRC_FEEDBACK.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for url in _non_loopback_http_urls_in(text):
            offenders.append(f"{path.relative_to(_SRC_FEEDBACK.parent.parent.parent)}: {url}")

    assert offenders == [], f"Feedback package must not hard-code non-loopback http(s) URLs (vendor neutrality / dormant upstream): {offenders}"
