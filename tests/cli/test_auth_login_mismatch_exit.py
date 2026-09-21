"""``auth login`` folds #4265 (WP05, #4755, T022): the issuer-mismatch
refusal must exit non-zero, and the custom-endpoint label must compare
canonical hosts rather than raw strings.

Both defects were squad findings on PR #4262:

1. ``_auth_login.py:131`` (pre-fix): a plain ``auth login`` on an issuer
   mismatch refuses (prints the remedy, forwards no bearer) but returned
   exit code 0, so a script chaining ``spec-kitty auth login && ...`` would
   read the refusal as success.
2. ``_auth_login.py:192`` (pre-fix): the custom-endpoint label fired on raw
   string inequality with ``DEFAULT_HOSTED_SAAS_URL``, so a canonical host
   carrying an explicit default port (``https://team.spec-kitty.ai:443``)
   was mislabeled "Custom endpoint ... self-hosted".

These are CliRunner tests against the real Typer ``app``, mocking the
``_auth_login`` seam exactly as ``tests/cli/commands/test_auth_login.py``
does, so no browser flow or real auth store is touched.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from kernel.clock import now_utc, timedelta
from specify_cli.auth import reset_token_manager
from specify_cli.auth.session import StoredSession, Team
from specify_cli.cli.commands.auth import app

pytestmark = [pytest.mark.fast, pytest.mark.regression]

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_tm(monkeypatch: pytest.MonkeyPatch):
    """Default env target + a clean process-wide TokenManager per test."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://saas.test")
    reset_token_manager()
    yield
    reset_token_manager()


def _make_session(*, issuer_url: str | None) -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="user-1",
        email="alice@example.com",
        name="Alice",
        teams=[Team(id="t1", name="Team One", role="owner")],
        default_team_id="t1",
        access_token="access-xyz",
        refresh_token="refresh-xyz",
        session_id="sess-1",
        issued_at=now,
        access_token_expires_at=now + timedelta(hours=1),
        refresh_token_expires_at=now + timedelta(days=30),
        scope="offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=issuer_url,
    )


def _flat(text: str) -> str:
    """Collapse whitespace so assertions survive rich's line wrapping."""
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# T022 finding 1: non-zero exit on an issuer-mismatch refusal
# ---------------------------------------------------------------------------


def test_issuer_mismatch_refusal_exits_non_zero():
    """A refusal is not success: ``spec-kitty auth login && ...`` must see a
    failing exit code, not the exit-0 shape the pre-#4265 code returned."""
    existing = _make_session(issuer_url="https://app.spec-kitty.ai")

    async def _fail(*_args, **_kwargs):
        raise AssertionError("login must not forward an old-host session to a new target")

    with (
        patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
        patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_fail),
        ) as mock_browser,
    ):
        mock_tm = mock_factory.return_value
        mock_tm.is_authenticated = True
        mock_tm.get_current_session.return_value = existing

        result = runner.invoke(app, ["login"])

    assert result.exit_code != 0, result.stdout
    assert result.exit_code == 1, result.stdout
    flat = _flat(result.stdout)
    assert "fresh authentication is required" in flat
    assert not mock_browser.called


def test_matching_issuer_still_exits_zero():
    """The exit-code fix is scoped to the mismatch branch only: an
    already-logged-in session whose issuer matches the resolved target keeps
    exiting 0 (unchanged, non-refusal path)."""
    existing = _make_session(issuer_url="https://saas.test")

    async def _noop(*_args, **_kwargs):
        return None

    with (
        patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
        patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ),
    ):
        mock_tm = mock_factory.return_value
        mock_tm.is_authenticated = True
        mock_tm.get_current_session.return_value = existing

        result = runner.invoke(app, ["login"])

    assert result.exit_code == 0, result.stdout
    assert "Already logged in" in result.stdout


# ---------------------------------------------------------------------------
# T022 finding 2: canonical-host comparison for the custom-endpoint label
# ---------------------------------------------------------------------------


def test_canonical_host_with_explicit_default_port_is_not_labeled_custom(monkeypatch: pytest.MonkeyPatch):
    """``https://team.spec-kitty.ai:443`` names the same host as the packaged
    default over HTTPS's default port -- it must not be labelled "Custom
    endpoint", which the pre-#4265 raw ``!=`` string comparison did."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://team.spec-kitty.ai:443")

    async def _noop(*_args, **_kwargs):
        return None

    with (
        patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
        patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_browser,
    ):
        mock_factory.return_value.is_authenticated = False
        result = runner.invoke(app, ["login"])

    assert result.exit_code == 0, result.stdout
    flat = _flat(result.stdout)
    assert "Custom endpoint" not in flat
    assert mock_browser.called


def test_a_genuinely_different_host_is_still_labeled_custom():
    """The canonical-host fix must not silently widen what counts as
    canonical: an unrelated self-hosted host is still labelled custom."""

    async def _noop(*_args, **_kwargs):
        return None

    with (
        patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
        patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_browser,
    ):
        mock_factory.return_value.is_authenticated = False
        # Default env from the autouse fixture: "https://saas.test".
        result = runner.invoke(app, ["login"])

    assert result.exit_code == 0, result.stdout
    flat = _flat(result.stdout)
    assert "Custom endpoint" in flat
    assert mock_browser.called
