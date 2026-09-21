"""Unit tests for the shared issuer-target authority (WP01, #4755, T003).

Covers ``specify_cli.auth.server_target.resolve_token_endpoint`` per
``kitty-specs/token-target-issuer-guard-01M319HS/contracts/issuer-target-helper.md``:
deterministic, network-free (config.toml/env are monkeypatched via an
isolated ``SPEC_KITTY_HOME``), no consumer wiring — this WP only exercises
the helper itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.clock import now_utc, timedelta
from specify_cli.auth.errors import ISSUER_MISMATCH_REMEDY, IssuerTargetMismatchError
from specify_cli.auth.server_target import (
    SAAS_URL_ENV_VAR,
    ServerTargetSplitBrainError,
    resolve_token_endpoint,
)
from specify_cli.auth.session import StoredSession, Team

pytestmark = [pytest.mark.fast]

CONFIG_URL = "https://config.example.com"
ENV_URL = "https://env.example.com"
ISSUER_URL = "https://issuer.example.com"

#: Fixture token values — asserted ABSENT from every mismatch message
#: (NFR-006: the helper's error must contain zero token material).
ACCESS_TOKEN_FIXTURE = "access-token-should-never-leak-abc123"
REFRESH_TOKEN_FIXTURE = "refresh-token-should-never-leak-xyz789"


@pytest.fixture
def target_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Isolate config.toml under a throwaway ``SPEC_KITTY_HOME`` with no env leakage."""
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
    monkeypatch.delenv(SAAS_URL_ENV_VAR, raising=False)
    return tmp_path


def _write_config(root: Path, server_url: str) -> None:
    (root / "config.toml").write_text(f'[sync]\nserver_url = "{server_url}"\n', encoding="utf-8")


def _make_session(*, issuer_url: str | None) -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="user-abc",
        email="jane@example.com",
        name="Jane Doe",
        teams=[Team(id="team-1", name="Primary", role="owner", is_private_teamspace=True)],
        default_team_id="team-1",
        access_token=ACCESS_TOKEN_FIXTURE,
        refresh_token=REFRESH_TOKEN_FIXTURE,
        session_id="session-xyz",
        issued_at=now,
        access_token_expires_at=now + timedelta(minutes=15),
        refresh_token_expires_at=None,
        scope="openid profile email offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=issuer_url,
    )


# ---------------------------------------------------------------------------
# issuer == target
# ---------------------------------------------------------------------------


def test_issuer_matches_target_returns_normalized_endpoint(target_root: Path) -> None:
    _write_config(target_root, CONFIG_URL)
    session = _make_session(issuer_url=CONFIG_URL)

    endpoint = resolve_token_endpoint(session)

    assert endpoint == CONFIG_URL


def test_issuer_matches_target_normalizes_trailing_slash_and_whitespace(target_root: Path) -> None:
    _write_config(target_root, CONFIG_URL)
    session = _make_session(issuer_url=f"  {CONFIG_URL}/  ")

    endpoint = resolve_token_endpoint(session)

    assert endpoint == CONFIG_URL
    assert not endpoint.endswith("/")
    assert endpoint == endpoint.strip()


# ---------------------------------------------------------------------------
# issuer != target — mismatch
# ---------------------------------------------------------------------------


def test_issuer_mismatch_raises_with_correct_fields(target_root: Path) -> None:
    _write_config(target_root, CONFIG_URL)
    session = _make_session(issuer_url=ISSUER_URL)

    with pytest.raises(IssuerTargetMismatchError) as excinfo:
        resolve_token_endpoint(session)

    err = excinfo.value
    assert err.issuer_url == ISSUER_URL
    assert err.resolved_url == CONFIG_URL
    assert err.remedy == ISSUER_MISMATCH_REMEDY


def test_issuer_mismatch_message_contains_no_token_material(target_root: Path) -> None:
    _write_config(target_root, CONFIG_URL)
    session = _make_session(issuer_url=ISSUER_URL)

    with pytest.raises(IssuerTargetMismatchError) as excinfo:
        resolve_token_endpoint(session)

    message = str(excinfo.value)
    assert ACCESS_TOKEN_FIXTURE not in message
    assert REFRESH_TOKEN_FIXTURE not in message
    # Operator-actionable: names both hosts.
    assert ISSUER_URL in message
    assert CONFIG_URL in message


def test_issuer_mismatch_trailing_slash_only_is_not_a_mismatch(target_root: Path) -> None:
    """The one normalizer used for the endpoint is reused for the compare (NFR-002)."""
    _write_config(target_root, CONFIG_URL)
    session = _make_session(issuer_url=CONFIG_URL + "/")

    endpoint = resolve_token_endpoint(session)

    assert endpoint == CONFIG_URL


# ---------------------------------------------------------------------------
# Null-session / null-issuer contract (M7): legacy branch, never falls back
# to the SaaS default accessor.
# ---------------------------------------------------------------------------


def test_none_session_resolves_to_target_without_raising(target_root: Path) -> None:
    _write_config(target_root, CONFIG_URL)

    endpoint = resolve_token_endpoint(None)

    assert endpoint == CONFIG_URL


def test_none_issuer_url_resolves_to_target_without_raising(target_root: Path) -> None:
    _write_config(target_root, CONFIG_URL)
    session = _make_session(issuer_url=None)

    endpoint = resolve_token_endpoint(session)

    assert endpoint == CONFIG_URL


def test_none_session_is_not_the_packaged_default_when_config_names_another_host(
    target_root: Path,
) -> None:
    """FR-006/FR-012: the null path must resolve the real configured target,
    not silently fall back to the packaged default."""
    dev_host = "https://spec-kitty-dev.fly.dev"
    _write_config(target_root, dev_host)

    endpoint = resolve_token_endpoint(None)

    assert endpoint == dev_host
    from specify_cli.auth.config import DEFAULT_HOSTED_SAAS_URL  # noqa: PLC0415

    assert endpoint != DEFAULT_HOSTED_SAAS_URL


# ---------------------------------------------------------------------------
# Split-brain propagation
# ---------------------------------------------------------------------------


def test_split_brain_propagates_uncaught(target_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(target_root, CONFIG_URL)
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)
    session = _make_session(issuer_url=ISSUER_URL)

    with pytest.raises(ServerTargetSplitBrainError):
        resolve_token_endpoint(session)


def test_split_brain_propagates_uncaught_with_none_session(target_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(target_root, CONFIG_URL)
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)

    with pytest.raises(ServerTargetSplitBrainError):
        resolve_token_endpoint(None)
