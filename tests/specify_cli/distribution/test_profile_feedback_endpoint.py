"""Tests for ``DistributionProfile.feedback_endpoint`` (WP02 / T012)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from specify_cli.distribution.package_name import clear_cli_package_name_cache
from specify_cli.distribution.profile import (
    DISTRIBUTION_PROFILE_GROUP,
    DistributionProfile,
    clear_distribution_profile_cache,
    is_degraded_distribution_profile,
    resolve_distribution_profile,
    stock_distribution_profile,
)
from specify_cli.distribution.profile import _degraded_profile
from specify_cli.distribution.upgrade_provider import clear_upgrade_provider_cache

pytestmark = pytest.mark.fast

_EXAMPLE_ENDPOINT = "https://feedback.example.test/v1"


class _FakeEntryPoint:
    def __init__(self, name: str, payload: Any) -> None:
        self.name = name
        self._payload = payload

    def load(self) -> Any:
        if isinstance(self._payload, BaseException):
            raise self._payload
        return self._payload


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    clear_distribution_profile_cache()
    clear_cli_package_name_cache()
    clear_upgrade_provider_cache()
    yield
    clear_distribution_profile_cache()
    clear_cli_package_name_cache()
    clear_upgrade_provider_cache()


def test_stock_profile_feedback_endpoint_is_none() -> None:
    assert stock_distribution_profile().feedback_endpoint is None


def test_degraded_profile_feedback_endpoint_is_none() -> None:
    profile = _degraded_profile()
    assert is_degraded_distribution_profile(profile)
    assert profile.feedback_endpoint is None


def test_constructed_profile_keeps_feedback_endpoint() -> None:
    profile = DistributionProfile(
        package_name="fork-cli",
        feedback_endpoint=_EXAMPLE_ENDPOINT,
    )
    assert profile.feedback_endpoint == _EXAMPLE_ENDPOINT


def test_replace_from_stock_keeps_none_feedback_endpoint() -> None:
    profile = replace(stock_distribution_profile(), package_name="fork-cli")
    assert profile.feedback_endpoint is None


def test_entry_point_profile_exposes_feedback_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    custom = DistributionProfile(
        package_name="acme-spec-kitty-cli",
        feedback_endpoint=_EXAMPLE_ENDPOINT,
    )
    monkeypatch.setattr(
        "specify_cli.distribution.profile.entry_points",
        lambda group: [_FakeEntryPoint("acme", custom)] if group == DISTRIBUTION_PROFILE_GROUP else [],
    )

    profile = resolve_distribution_profile()
    assert profile.feedback_endpoint == _EXAMPLE_ENDPOINT
