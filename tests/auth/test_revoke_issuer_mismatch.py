"""Unit tests for issuer/target-guarded revocation (WP03, #4755, T014).

Covers ``specify_cli.auth.flows.revoke.RevokeFlow.revoke`` per
``kitty-specs/token-target-issuer-guard-01M319HS/contracts/issuer-target-helper.md``:

- mismatch/split-brain -> ``RevokeOutcome.ISSUER_MISMATCH``, HTTP client
  never invoked (no POST is issued).
- issuer == target -> normal revoke path unchanged (NFR-005).
- legacy ``issuer_url=None`` + config-only host -> revoke targets the
  config host, no refusal (US1-AC4 flow-level confirmation; the helper
  test in WP01 T003 is the primary coverage).

Deterministic and network-free: config.toml/env are isolated via a
throwaway ``SPEC_KITTY_HOME``, and the HTTP seam is mocked so no real
network traffic occurs.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kernel.clock import now_utc, timedelta
from specify_cli.auth.flows.revoke import RevokeFlow, RevokeOutcome
from specify_cli.auth.server_target import SAAS_URL_ENV_VAR
from specify_cli.auth.session import StoredSession, Team

pytestmark = [pytest.mark.fast]

CONFIG_URL = "https://config.example.com"
ENV_URL = "https://env.example.com"
ISSUER_URL = "https://issuer.example.com"

#: Fixture token values — asserted ABSENT from any warning/message the
#: mismatch path might produce (NFR-006).
ACCESS_TOKEN_FIXTURE = "access-token-should-never-leak-def456"
REFRESH_TOKEN_FIXTURE = "refresh-token-should-never-leak-uvw012"


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
        user_id="u_mismatch",
        email="mismatch@example.com",
        name="Mismatch User",
        teams=[Team(id="tm_mismatch", name="Mismatch", role="member")],
        default_team_id="tm_mismatch",
        access_token=ACCESS_TOKEN_FIXTURE,
        refresh_token=REFRESH_TOKEN_FIXTURE,
        session_id="sess_mismatch",
        issued_at=now,
        access_token_expires_at=now + timedelta(hours=1),
        refresh_token_expires_at=now + timedelta(days=89),
        scope="offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=issuer_url,
    )


def _make_async_client(post_return=None) -> MagicMock:
    """Build a mock httpx.AsyncClient context manager whose ``post`` is spyable."""
    async_client = MagicMock()
    async_client.__aenter__ = AsyncMock(return_value=async_client)
    async_client.__aexit__ = AsyncMock(return_value=None)
    async_client.post = AsyncMock(return_value=post_return)
    return async_client


def _make_response(status_code: int, json_body: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    if json_body is not None:
        response.json = MagicMock(return_value=json_body)
    else:
        response.json = MagicMock(side_effect=ValueError("no JSON"))
    return response


# ---------------------------------------------------------------------------
# Mismatch -> ISSUER_MISMATCH, no HTTP call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issuer_mismatch_returns_issuer_mismatch_outcome(target_root: Path) -> None:
    _write_config(target_root, CONFIG_URL)
    session = _make_session(issuer_url=ISSUER_URL)
    async_client = _make_async_client(post_return=_make_response(200, {"revoked": True}))

    with patch(
        "specify_cli.auth.flows.revoke.httpx.AsyncClient",
        return_value=async_client,
    ):
        outcome = await RevokeFlow().revoke(session)

    assert outcome is RevokeOutcome.ISSUER_MISMATCH


@pytest.mark.asyncio
async def test_issuer_mismatch_never_invokes_http_client(target_root: Path) -> None:
    """The client constructor itself must never be reached on a mismatch refusal."""
    _write_config(target_root, CONFIG_URL)
    session = _make_session(issuer_url=ISSUER_URL)

    with patch("specify_cli.auth.flows.revoke.httpx.AsyncClient") as client_cls:
        outcome = await RevokeFlow().revoke(session)

    assert outcome is RevokeOutcome.ISSUER_MISMATCH
    client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_split_brain_returns_issuer_mismatch_outcome_no_http_call(target_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A split-brain (env/config disagreement) is a refusal, same as a mismatch."""
    _write_config(target_root, CONFIG_URL)
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)
    session = _make_session(issuer_url=ISSUER_URL)

    with patch("specify_cli.auth.flows.revoke.httpx.AsyncClient") as client_cls:
        outcome = await RevokeFlow().revoke(session)

    assert outcome is RevokeOutcome.ISSUER_MISMATCH
    client_cls.assert_not_called()


# ---------------------------------------------------------------------------
# issuer == target -> normal revoke path unchanged (NFR-005)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issuer_matches_target_revokes_normally(target_root: Path) -> None:
    _write_config(target_root, CONFIG_URL)
    session = _make_session(issuer_url=CONFIG_URL)
    response = _make_response(200, {"revoked": True})
    async_client = _make_async_client(post_return=response)

    with patch(
        "specify_cli.auth.flows.revoke.httpx.AsyncClient",
        return_value=async_client,
    ):
        outcome = await RevokeFlow().revoke(session)

    assert outcome is RevokeOutcome.REVOKED
    async_client.post.assert_awaited_once()
    called_url = async_client.post.call_args.args[0]
    assert called_url == f"{CONFIG_URL}/oauth/revoke"


# ---------------------------------------------------------------------------
# Legacy issuer_url=None + config-only host -> revoke targets config host,
# no refusal (US1-AC4 flow-level confirmation).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_null_issuer_targets_config_host_no_refusal(target_root: Path) -> None:
    _write_config(target_root, CONFIG_URL)
    session = _make_session(issuer_url=None)
    response = _make_response(200, {"revoked": True})
    async_client = _make_async_client(post_return=response)

    with patch(
        "specify_cli.auth.flows.revoke.httpx.AsyncClient",
        return_value=async_client,
    ):
        outcome = await RevokeFlow().revoke(session)

    assert outcome is RevokeOutcome.REVOKED
    called_url = async_client.post.call_args.args[0]
    assert called_url == f"{CONFIG_URL}/oauth/revoke"


# ---------------------------------------------------------------------------
# NFR-006: refusal path leaks no token material anywhere observable.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issuer_mismatch_refusal_is_token_free(target_root: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_config(target_root, CONFIG_URL)
    session = _make_session(issuer_url=ISSUER_URL)

    with (
        patch("specify_cli.auth.flows.revoke.httpx.AsyncClient") as client_cls,
        caplog.at_level("WARNING"),
    ):
        outcome = await RevokeFlow().revoke(session)

    assert outcome is RevokeOutcome.ISSUER_MISMATCH
    client_cls.assert_not_called()
    log_text = caplog.text
    assert ACCESS_TOKEN_FIXTURE not in log_text
    assert REFRESH_TOKEN_FIXTURE not in log_text
