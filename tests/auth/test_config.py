"""Tests for ``specify_cli.auth.config`` (feature 080, WP01 T002)."""

from __future__ import annotations

import pytest

from specify_cli.auth.config import (
    DEFAULT_HOSTED_SAAS_URL,
    RETIRED_HOSTED_SAAS_HOSTNAME,
    RETIRED_HOSTED_SAAS_URL,
    get_saas_base_url,
    get_saas_url_env_override,
    is_noncanonical_first_party_url,
    is_retired_first_party_url,
)
from specify_cli.auth.errors import ConfigurationError


pytestmark = [pytest.mark.integration]

def test_get_saas_base_url_reads_env_var(monkeypatch):
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://saas.test")
    assert get_saas_base_url() == "https://saas.test"


def test_get_saas_base_url_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://saas.test/")
    assert get_saas_base_url() == "https://saas.test"


def test_get_saas_base_url_strips_multiple_trailing_slashes(monkeypatch):
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://saas.test///")
    assert get_saas_base_url() == "https://saas.test"


def test_get_saas_base_url_returns_packaged_default_when_unset(monkeypatch):
    """#3980 (D-5 revised): the packaged default is the target — an unset
    override resolves to it instead of raising."""
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    assert get_saas_base_url() == DEFAULT_HOSTED_SAAS_URL


def test_get_saas_base_url_returns_packaged_default_when_empty(monkeypatch):
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "")
    assert get_saas_base_url() == DEFAULT_HOSTED_SAAS_URL


def test_get_saas_url_env_override_reader_is_env_only(monkeypatch):
    """The env-override accessor the resolver consumes: unset/blank is no
    opinion (``None``), never the packaged default itself."""
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    assert get_saas_url_env_override() is None
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "  ")
    assert get_saas_url_env_override() is None
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://env.test/")
    assert get_saas_url_env_override() == "https://env.test"


def test_configuration_error_is_authentication_error():
    from specify_cli.auth.errors import AuthenticationError

    assert issubclass(ConfigurationError, AuthenticationError)


# ---------------------------------------------------------------------------
# Retired first-party endpoint classification (#4259)
# ---------------------------------------------------------------------------


def test_retired_literal_is_the_pre_launch_app_subdomain():
    """The retired address is exactly the pre-#3980 first-party app host —
    pinned here so a typo in the constant cannot silently widen (or narrow)
    the migration's or the login warning's scope."""
    assert RETIRED_HOSTED_SAAS_URL == "https://app.spec-kitty.ai"
    assert RETIRED_HOSTED_SAAS_HOSTNAME == "app.spec-kitty.ai"
    assert RETIRED_HOSTED_SAAS_URL != DEFAULT_HOSTED_SAAS_URL


def test_is_retired_first_party_url_matches_the_retired_host_exactly():
    assert is_retired_first_party_url(RETIRED_HOSTED_SAAS_URL) is True
    assert is_retired_first_party_url("https://APP.SPEC-KITTY.AI/") is True
    assert is_retired_first_party_url(f"{RETIRED_HOSTED_SAAS_URL}:8443/dead/path") is True
    assert is_retired_first_party_url(f"  {RETIRED_HOSTED_SAAS_URL}  ") is True


def test_is_retired_first_party_url_never_fires_on_look_alikes_or_custom_hosts():
    """Hostname-exact, never substring (#4259): other domains, subdomains of
    the first-party domain that are not the retired app host, and hosts that
    merely contain the literal are all somebody else's endpoint."""
    assert is_retired_first_party_url("https://team.spec-kitty.ai") is False
    assert is_retired_first_party_url("https://myapp.spec-kitty.ai") is False
    assert is_retired_first_party_url("https://app.spec-kitty.ai.evil.example.com") is False
    assert is_retired_first_party_url("https://app.spec-kitty-ai.example.com") is False
    assert is_retired_first_party_url("https://saas.internal.example.com:8443/prefix") is False
    assert is_retired_first_party_url("") is False
    assert is_retired_first_party_url("not a url") is False


def test_is_noncanonical_first_party_url_classifies_first_party_only():
    """First-party but not canonical warns; canonical and self-hosted do
    not (#4259: legitimate self-hosting is never nagged as noncanonical)."""
    assert is_noncanonical_first_party_url(RETIRED_HOSTED_SAAS_URL) is True
    assert is_noncanonical_first_party_url("https://docs.spec-kitty.ai") is True
    assert is_noncanonical_first_party_url("https://spec-kitty.ai") is True
    assert is_noncanonical_first_party_url(DEFAULT_HOSTED_SAAS_URL) is False
    assert is_noncanonical_first_party_url("https://saas.internal.example.com") is False
    assert is_noncanonical_first_party_url("https://app.spec-kitty.ai.evil.example.com") is False
    assert is_noncanonical_first_party_url("") is False
