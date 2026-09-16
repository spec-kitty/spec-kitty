"""Tests for specify_cli.saas_client.

Full integration tests using ``respx`` are deferred to WP10.  This module
contains smoke-level unit tests to verify the import surface, error hierarchy,
and basic client construction — all without network access.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from kernel.clock import now_utc, timedelta

from specify_cli.auth import reset_token_manager
from specify_cli.auth.config import DEFAULT_HOSTED_SAAS_URL
from specify_cli.auth.errors import ConfigurationError, NetworkError, RefreshTokenExpiredError
from specify_cli.auth.session import StoredSession, Team
from specify_cli.auth.token_manager import TokenManager
from specify_cli.saas_client import (
    AuthContext,
    SaasAuthError,
    SaasClient,
    SaasClientError,
    SaasNotFoundError,
    SaasTimeoutError,
    load_auth_context,
)
from specify_cli.saas_client import auth as saas_auth_module


# ---------------------------------------------------------------------------
# Import smoke tests
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.usefixtures("stub_project_authority")]


def test_public_api_imports() -> None:
    """All public names are importable from the package root."""
    assert SaasClient is not None
    assert SaasClientError is not None
    assert SaasTimeoutError is not None
    assert SaasAuthError is not None
    assert SaasNotFoundError is not None
    assert AuthContext is not None
    assert load_auth_context is not None


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


def test_error_hierarchy() -> None:
    """Subclasses are proper subclasses of SaasClientError."""
    assert issubclass(SaasTimeoutError, SaasClientError)
    assert issubclass(SaasAuthError, SaasClientError)
    assert issubclass(SaasNotFoundError, SaasClientError)


def test_saas_client_error_carries_status_code() -> None:
    err = SaasClientError("oops", status_code=500)
    assert err.status_code == 500
    assert str(err) == "oops"


def test_saas_client_error_status_code_optional() -> None:
    err = SaasClientError("no code")
    assert err.status_code is None


# ---------------------------------------------------------------------------
# SaasClient construction
# ---------------------------------------------------------------------------


def test_client_constructs_with_explicit_http() -> None:
    """SaasClient accepts an injected httpx.Client without raising."""
    mock_http = MagicMock(spec=httpx.Client)
    client = SaasClient("http://localhost:8000", "tok", _http=mock_http)
    assert client._base_url == "http://localhost:8000"
    assert client._token == "tok"


def test_client_strips_trailing_slash_from_base_url() -> None:
    mock_http = MagicMock(spec=httpx.Client)
    client = SaasClient("http://localhost:8000/", "tok", _http=mock_http)
    assert client._base_url == "http://localhost:8000"


def test_has_token_true_when_token_present() -> None:
    """has_token property returns True for a non-empty token."""
    mock_http = MagicMock(spec=httpx.Client)
    client = SaasClient("http://localhost:8000", "my-token", _http=mock_http)
    assert client.has_token is True


def test_has_token_false_when_token_empty() -> None:
    """has_token property returns False when token is an empty string."""
    mock_http = MagicMock(spec=httpx.Client)
    client = SaasClient("http://localhost:8000", "", _http=mock_http)
    assert client.has_token is False


# ---------------------------------------------------------------------------
# auth.load_auth_context
# ---------------------------------------------------------------------------


def test_load_auth_context_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_SAAS_TOKEN", "test-token")
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://example.com")
    monkeypatch.setenv("SPEC_KITTY_TEAM_SLUG", "my-team")
    ctx = load_auth_context()
    assert ctx.token == "test-token"
    assert ctx.saas_url == "https://example.com"
    assert ctx.team_slug == "my-team"


def test_load_auth_context_env_token_no_url_resolves_packaged_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#3980 (D-5 revised): with a token but no SaaS URL from env or file, the
    packaged default is the target — no hardcoded ``api.spec-kitty.io``
    fallback ever existed (#2248 / #2146); the packaged launch host is not a
    guess, it is the shipped default."""
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_SAAS_TOKEN", "test-token")
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    ctx = load_auth_context()
    assert ctx.token == "test-token"
    assert ctx.saas_url == DEFAULT_HOSTED_SAAS_URL


def test_load_auth_context_env_token_no_url_names_env_and_config_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#290: an env-supplied token's "no URL" remedy must name only
    SPEC_KITTY_SAAS_URL and config.toml's [sync].server_url — never
    .kittify/saas-auth.json's saas_url, which #237 already refuses to pair
    with an env-supplied token. The refusal is reached here with the
    canonical resolver degraded (#3980: with it available, the packaged
    default is the target instead)."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_TOKEN", "test-token")
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    monkeypatch.setattr(saas_auth_module, "_resolved_server_target", _raise_unavailable)
    with pytest.raises(SaasAuthError) as exc_info:
        load_auth_context()
    message = str(exc_info.value)
    assert "SPEC_KITTY_SAAS_URL" in message
    assert "[sync].server_url" in message
    assert "never paired with .kittify/saas-auth.json" in message
    assert 'provide "saas_url" in .kittify/saas-auth.json' not in message


def test_load_auth_context_env_token_ignores_file_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#237: an env-supplied token must not be redirected by a checkout's
    ``.kittify/saas-auth.json`` saas_url. With no SPEC_KITTY_SAAS_URL and no
    resolvable server target, this fails closed rather than trusting the file.
    """
    monkeypatch.setenv("SPEC_KITTY_SAAS_TOKEN", "env-token")
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    auth_dir = tmp_path / ".kittify"
    auth_dir.mkdir()
    (auth_dir / "saas-auth.json").write_text(json.dumps({"saas_url": "https://evil.example"}))
    monkeypatch.setattr(saas_auth_module, "_resolved_server_target", _raise_unavailable)
    with pytest.raises(SaasAuthError, match="SaaS URL not configured"):
        load_auth_context(repo_root=tmp_path)


def test_load_auth_context_env_token_pairs_with_env_url_over_file_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#237: when both an env token and an env URL are set, the env URL wins
    even if a checkout-controlled file also names a (different) saas_url."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_TOKEN", "env-token")
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://env-url.example")
    auth_dir = tmp_path / ".kittify"
    auth_dir.mkdir()
    (auth_dir / "saas-auth.json").write_text(json.dumps({"saas_url": "https://evil.example"}))
    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.token == "env-token"
    assert ctx.saas_url == "https://env-url.example"


def test_load_auth_context_fully_env_configured_ignores_malformed_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#264 fix round: when both SPEC_KITTY_SAAS_TOKEN and SPEC_KITTY_SAAS_URL
    are set, a stray/malformed ``.kittify/saas-auth.json`` must not be read at
    all — an already-fully-resolved env identity cannot be broken by a
    checkout it never needed to consult."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_TOKEN", "env-token")
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://env-url.example")
    auth_dir = tmp_path / ".kittify"
    auth_dir.mkdir()
    (auth_dir / "saas-auth.json").write_text("{not valid json")
    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.token == "env-token"
    assert ctx.saas_url == "https://env-url.example"


def test_load_auth_context_env_token_only_ignores_malformed_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#291: with only SPEC_KITTY_SAAS_TOKEN set (no SPEC_KITTY_SAAS_URL), the
    file's every field is still dead per the #237 trust boundary, so a
    malformed ``.kittify/saas-auth.json`` must not be read at all — the
    caller gets the clearer "SaaS URL not configured" refusal, not a JSON
    parse error about a file it never needed."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_TOKEN", "env-token")
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    auth_dir = tmp_path / ".kittify"
    auth_dir.mkdir()
    (auth_dir / "saas-auth.json").write_text("{not valid json")
    monkeypatch.setattr(saas_auth_module, "_resolved_server_target", _raise_unavailable)
    with pytest.raises(SaasAuthError, match="SaaS URL not configured"):
        load_auth_context(repo_root=tmp_path)


def test_load_auth_context_fully_env_configured_ignores_file_team_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#264 fix round: a checkout-controlled ``.kittify/saas-auth.json`` must
    not be able to override the team scope of an already-fully-resolved
    env token+url identity — the same same-source invariant #237 established
    for saas_url applies to team_slug (zeitgeist_client/resolution.py uses it
    as a per-request scope selector)."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_TOKEN", "env-token")
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://env-url.example")
    monkeypatch.delenv("SPEC_KITTY_TEAM_SLUG", raising=False)
    auth_dir = tmp_path / ".kittify"
    auth_dir.mkdir()
    (auth_dir / "saas-auth.json").write_text(json.dumps({"team_slug": "attacker-controlled-team"}))
    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.token == "env-token"
    assert ctx.saas_url == "https://env-url.example"
    assert ctx.team_slug is None


def test_load_auth_context_env_token_falls_back_to_resolved_server_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#237: with no SPEC_KITTY_SAAS_URL, an env token pairs with the
    canonical resolved server target — a trusted source — not the file's url."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_TOKEN", "env-token")
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    auth_dir = tmp_path / ".kittify"
    auth_dir.mkdir()
    (auth_dir / "saas-auth.json").write_text(json.dumps({"saas_url": "https://evil.example"}))

    class _Target:
        resolved_server_url = "https://resolved-target.example"

    monkeypatch.setattr(saas_auth_module, "_resolved_server_target", lambda: _Target())
    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.token == "env-token"
    assert ctx.saas_url == "https://resolved-target.example"


def test_load_auth_context_file_token_pairs_with_env_url_when_file_has_no_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A repo-local token with no repo-local url may still pair with an
    operator-set SPEC_KITTY_SAAS_URL: only a checkout-controlled url paired
    with a non-checkout token is the #237 hazard, not the reverse."""
    monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://env-url.example")
    auth_dir = tmp_path / ".kittify"
    auth_dir.mkdir()
    (auth_dir / "saas-auth.json").write_text(json.dumps({"token": "file-token"}))
    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.token == "file-token"
    assert ctx.saas_url == "https://env-url.example"


def test_load_auth_context_file_token_no_url_resolves_packaged_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#3980 (D-5 revised) file branch: file token present but no saas_url key
    → the packaged default (the file's own url still only ever rides with its
    own token, #237)."""
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    auth_dir = tmp_path / ".kittify"
    auth_dir.mkdir()
    (auth_dir / "saas-auth.json").write_text(json.dumps({"token": "file-token"}))
    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.token == "file-token"
    assert ctx.saas_url == DEFAULT_HOSTED_SAAS_URL


def test_load_auth_context_file_token_no_url_still_names_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#290: the file-token "no URL" remedy is unchanged by the env-token
    branch above — naming the file's own saas_url is still a fair remedy on
    this path, since #237's trust boundary never applied to it. Reached with
    the canonical resolver degraded (#3980)."""
    monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    monkeypatch.setattr(saas_auth_module, "_resolved_server_target", _raise_unavailable)
    auth_dir = tmp_path / ".kittify"
    auth_dir.mkdir()
    (auth_dir / "saas-auth.json").write_text(json.dumps({"token": "file-token"}))
    with pytest.raises(SaasAuthError) as exc_info:
        load_auth_context(repo_root=tmp_path)
    assert '"saas_url" in .kittify/saas-auth.json' in str(exc_info.value)


def test_load_auth_context_file_token_empty_url_resolves_packaged_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#3980 (D-5 revised) file branch: empty-string saas_url in file is no
    opinion (strip normalises it) → the packaged default."""
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    auth_dir = tmp_path / ".kittify"
    auth_dir.mkdir()
    (auth_dir / "saas-auth.json").write_text(json.dumps({"token": "file-token", "saas_url": ""}))
    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.saas_url == DEFAULT_HOSTED_SAAS_URL


def test_load_auth_context_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    monkeypatch.delenv("SPEC_KITTY_TEAM_SLUG", raising=False)
    auth_dir = tmp_path / ".kittify"
    auth_dir.mkdir()
    (auth_dir / "saas-auth.json").write_text(json.dumps({"token": "file-token", "saas_url": "https://file-url.example", "team_slug": "file-team"}))
    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.token == "file-token"
    assert ctx.saas_url == "https://file-url.example"
    assert ctx.team_slug == "file-team"


def test_load_auth_context_cannot_distinguish_repo_tier_kitty_env_from_real_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#289: ``load_auth_context`` reads ``os.environ`` after
    ``bootstrap.env_file.load_operator_env_file`` has already merged the
    repo-tier ``.kittify/.kitty.env`` into it (that loader runs as the first
    statements of ``specify_cli/__init__.py``, before this module is ever
    imported). By the time this function runs, a value seeded from a cloned
    repo's committed ``.kitty.env`` is indistinguishable from one the
    operator exported themselves — this module's #237 trust boundary is
    strictly narrower: it governs ``.kittify/saas-auth.json`` vs. an env
    token, not the provenance of ``os.environ`` itself. See
    ``docs/api/environment-variables.md``'s ``.kitty.env`` section and this
    module's docstring for the documented scope of that boundary.
    """
    monkeypatch.setenv("SPEC_KITTY_SAAS_TOKEN", "ci-service-token")
    # Simulates a value that arrived via the repo-tier .kitty.env tier rather
    # than a genuine shell export -- from this function's point of view the
    # two are the same os.environ entry.
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://repo-tier.example")
    monkeypatch.setenv("SPEC_KITTY_TEAM_SLUG", "repo-tier-team")

    ctx = load_auth_context()

    assert ctx.saas_url == "https://repo-tier.example"
    assert ctx.team_slug == "repo-tier-team"


def test_load_auth_context_raises_when_no_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing configured anywhere — no env, no auth file, no stored OAuth
    session — still refuses, and the refusal names all three ways in."""
    monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    monkeypatch.setattr(saas_auth_module, "_token_manager", _raise_unavailable)
    with pytest.raises(SaasAuthError, match="SPEC_KITTY_SAAS_TOKEN"):
        load_auth_context(repo_root=tmp_path)


# ---------------------------------------------------------------------------
# auth.load_auth_context step 3: the stored `auth login` session (#198)
# ---------------------------------------------------------------------------


class _ScriptedSessionManager:
    """TokenManager double: holds one session and records refresh calls.

    ``refresh_if_needed`` rotates the access token exactly once, the way
    ``TokenRefreshFlow`` + the refresh transaction leave the manager's
    session behind.
    """

    def __init__(self, session: StoredSession) -> None:
        self._session = session
        self.refresh_calls = 0
        self.session_reads = 0

    def get_current_session(self) -> StoredSession | None:
        self.session_reads += 1
        return self._session

    async def refresh_if_needed(self) -> bool:
        self.refresh_calls += 1
        self._session.access_token = "access-refreshed"
        self._session.access_token_expires_at = now_utc() + timedelta(seconds=900)
        return True


def _oauth_session(*, expires_in: int = 900, access_token: str = "access-v1") -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="user-1",
        email="a@b.com",
        name="A B",
        teams=[Team(id="t1", name="T1", role="owner", is_private_teamspace=True)],
        default_team_id="t1",
        access_token=access_token,
        refresh_token="refresh-v1",
        session_id="sess-1",
        issued_at=now,
        access_token_expires_at=now + timedelta(seconds=expires_in),
        refresh_token_expires_at=None,
        scope="openid",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


def _bridge_env(
    monkeypatch: pytest.MonkeyPatch,
    manager: Any,
    *,
    env_server_url: str | None = None,
    configured_server_url: str | None = None,
) -> None:
    """Aim the bridge at a scripted manager and a fixed server target.

    The bridge resolves both seams through this module's own lazy helpers,
    so patching here reaches every caller of ``load_auth_context`` without
    touching the real session store or ``specify_cli.auth`` globals.
    ``manager=None`` stands in for an unusable session store. ``env_server_url``
    / ``configured_server_url`` mirror ``ResolvedServerTarget``'s real fields
    (#300) so ``_saas_source_name`` has something to inspect."""
    if manager is None:
        monkeypatch.setattr(saas_auth_module, "_token_manager", _raise_unavailable)
    else:
        monkeypatch.setattr(saas_auth_module, "_token_manager", lambda: manager)

    class _Target:
        resolved_server_url = "https://team.example"

    _Target.env_server_url = env_server_url  # type: ignore[attr-defined]
    _Target.configured_server_url = configured_server_url  # type: ignore[attr-defined]

    monkeypatch.setattr(saas_auth_module, "_resolved_server_target", lambda: _Target())


def _raise_unavailable() -> None:
    raise RuntimeError("no session store here")


@pytest.fixture()
def _no_env_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("SPEC_KITTY_SAAS_TOKEN", "SPEC_KITTY_SAAS_URL", "SPEC_KITTY_TEAM_SLUG"):
        monkeypatch.delenv(var, raising=False)


def test_stored_oauth_session_answers_when_nothing_else_is_configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """The documented laptop path (#198): `auth login` once, then `routes`
    and the capability mint work with no service token anywhere."""
    manager = _ScriptedSessionManager(_oauth_session())
    _bridge_env(monkeypatch, manager)

    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.token == "access-v1"
    # The token is paired with the server target the login flow itself used.
    assert ctx.saas_url == "https://team.example"
    assert ctx.team_slug is None
    # A live session costs no refresh round trip.
    assert manager.refresh_calls == 0


def test_expired_oauth_session_is_refreshed_before_use(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    manager = _ScriptedSessionManager(_oauth_session(expires_in=-30))
    _bridge_env(monkeypatch, manager)

    ctx = load_auth_context(repo_root=tmp_path)
    assert manager.refresh_calls == 1
    assert ctx.token == "access-refreshed"


def test_dead_oauth_session_refuses_with_a_login_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """Refresh rejected the refresh token: that is a refusal naming the way
    out, not a silent fall-through to 'nothing configured'."""

    class _DeadManager(_ScriptedSessionManager):
        async def refresh_if_needed(self) -> bool:
            self.refresh_calls += 1
            raise RefreshTokenExpiredError("refresh token expired")

    _bridge_env(monkeypatch, _DeadManager(_oauth_session(expires_in=-30)))

    with pytest.raises(SaasAuthError, match="auth login"):
        load_auth_context(repo_root=tmp_path)


def test_transient_refresh_failure_keeps_the_held_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """Network down mid-refresh must not log the checkout out: the held
    token goes to Team Kitty, which will answer for it."""

    class _FlakyManager(_ScriptedSessionManager):
        async def refresh_if_needed(self) -> bool:
            self.refresh_calls += 1
            raise NetworkError("connection refused")

    manager = _FlakyManager(_oauth_session(expires_in=-30))
    _bridge_env(monkeypatch, manager)

    ctx = load_auth_context(repo_root=tmp_path)
    assert manager.refresh_calls == 1
    assert ctx.token == "access-v1"


def test_no_session_at_all_falls_through_to_the_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """A store that holds no session is not a bridge failure — the normal
    refusal fires, with its login hint."""

    class _EmptyManager:
        def get_current_session(self) -> StoredSession | None:
            return None

        async def refresh_if_needed(self) -> bool:  # pragma: no cover - never reached
            return False

    manager = _EmptyManager()
    _bridge_env(monkeypatch, manager)  # type: ignore[arg-type]
    with pytest.raises(SaasAuthError, match="auth login"):
        load_auth_context(repo_root=tmp_path)


def test_oauth_bridge_uses_the_resolved_target_not_a_stale_env_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """The OAuth-bridged saas_url must come from ``_resolved_server_target``,
    never from a separately-read copy of ``SPEC_KITTY_SAAS_URL`` — even
    though the two usually agree in practice, since ``resolve_server_target``
    already puts env over config itself (``server_target.py:151``).

    ``SPEC_KITTY_SAAS_URL`` is set here to a value that differs from
    ``_bridge_env``'s target double (``https://team.example``) specifically
    so the assertion below discriminates: it fails if the bridge falls back
    to reading the env var directly instead of trusting the resolved target.
    Proven by mutation: reintroducing #206's pass-1 bug
    (``saas_url=url or bridged.saas_url`` at ``auth.py:82``) prefers the env
    copy whenever it is set, which this would now catch (#235)."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://env.example")
    _bridge_env(monkeypatch, _ScriptedSessionManager(_oauth_session()))

    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.saas_url == "https://team.example"
    assert ctx.token == "access-v1"


def test_repo_auth_file_url_cannot_redirect_the_oauth_session_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """A checkout-controlled auth file may not choose where the user's
    personal OAuth session bearer is sent."""
    auth_dir = tmp_path / ".kittify"
    auth_dir.mkdir()
    (auth_dir / "saas-auth.json").write_text(json.dumps({"saas_url": "https://evil.example"}))
    _bridge_env(monkeypatch, _ScriptedSessionManager(_oauth_session(access_token="oauth-secret-token")))

    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.saas_url == "https://team.example"
    assert ctx.token == "oauth-secret-token"


def test_repo_auth_file_team_slug_cannot_scope_the_oauth_session_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _no_env_auth: None,
) -> None:
    """A checkout-controlled auth file may not choose the team scope of the
    user's personal OAuth session bearer (#765)."""
    auth_dir = tmp_path / ".kittify"
    auth_dir.mkdir()
    (auth_dir / "saas-auth.json").write_text(json.dumps({"team_slug": "attacker-team"}))
    _bridge_env(monkeypatch, _ScriptedSessionManager(_oauth_session()))

    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.saas_url == "https://team.example"
    assert ctx.token == "access-v1"
    assert ctx.team_slug is None


def test_env_team_slug_can_scope_the_oauth_session_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _no_env_auth: None,
) -> None:
    """The operator-controlled environment remains the supported way to choose
    a team when the OAuth bridge supplies the bearer."""
    monkeypatch.setenv("SPEC_KITTY_TEAM_SLUG", "operator-team")
    _bridge_env(monkeypatch, _ScriptedSessionManager(_oauth_session()))

    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.token == "access-v1"
    assert ctx.team_slug == "operator-team"


def test_server_target_that_cannot_resolve_falls_through_to_the_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """No SPEC_KITTY_SAAS_URL and no config.toml target: even a stored session
    cannot name the server its token belongs to (D-5) — refuse rather than
    guess a domain."""

    def _no_target() -> Any:
        raise ConfigurationError("no server target configured")

    _bridge_env(monkeypatch, _ScriptedSessionManager(_oauth_session()))
    monkeypatch.setattr(saas_auth_module, "_resolved_server_target", _no_target)

    with pytest.raises(SaasAuthError, match="auth login"):
        load_auth_context(repo_root=tmp_path)


def test_split_brain_server_target_falls_through_to_the_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """#117 finding 3 / #306: the OAuth bridge is a no-human-in-the-loop,
    bearer-token-bearing caller of ``resolve_server_target``. When
    ``[sync].server_url`` and ``SPEC_KITTY_SAAS_URL`` name *different* hosts
    with no whole-process override, the real resolver (not mocked here)
    must raise ``ServerTargetSplitBrainError`` — rather than silently
    minting the OAuth session's bearer token against the env-overridden
    host. The bridge re-raises it as a distinct ``SaasAuthError`` naming
    both URLs instead of folding it into the generic "run auth login"
    refusal: login already succeeded on a split-brain machine (FR-005), so
    that remedy is a no-op loop (#306)."""
    home = tmp_path / "split-brain-home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    (home / "config.toml").write_text('[sync]\nserver_url = "https://legit-team-kitty.example.com"\n', encoding="utf-8")
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://attacker.example.com")

    manager = _ScriptedSessionManager(_oauth_session())
    monkeypatch.setattr(saas_auth_module, "_token_manager", lambda: manager)

    with pytest.raises(SaasAuthError, match="split-brain") as excinfo:
        load_auth_context(repo_root=tmp_path)
    assert "legit-team-kitty.example.com" in str(excinfo.value)
    assert "attacker.example.com" in str(excinfo.value)
    # The bridge never reached the session store: resolution failed first.
    assert manager.session_reads == 0


def test_session_store_that_raises_degrades_to_the_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """A store that explodes on read is bridge trouble, not a crash: it
    degrades to 'no session' and the ordinary refusal fires."""

    class _ExplodingStore:
        def get_current_session(self) -> StoredSession:
            raise RuntimeError("storage backend exploded")

        async def refresh_if_needed(self) -> bool:  # pragma: no cover - never reached
            return False

    _bridge_env(monkeypatch, _ExplodingStore())  # type: ignore[arg-type]
    with pytest.raises(SaasAuthError, match="auth login"):
        load_auth_context(repo_root=tmp_path)


async def test_expired_session_inside_a_running_loop_keeps_the_held_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """When an event loop already owns this thread a blocking refresh cannot
    run — the held (expired) token goes out instead of raising, so a
    fire-and-forget fan-out stays silent rather than crashing its loop."""
    manager = _ScriptedSessionManager(_oauth_session(expires_in=-30))
    _bridge_env(monkeypatch, manager)

    ctx = load_auth_context(repo_root=tmp_path)

    assert manager.refresh_calls == 0  # asyncio.run would have raised in here
    assert ctx.token == "access-v1"


def test_session_issuer_mismatch_is_refused_not_paired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """#234: a session minted for one server must not be paired with another.

    ``_bridge_env`` resolves the target to ``https://team.example``; a
    session recorded with a different ``issuer_url`` must raise instead of
    silently sending its bearer to the resolved target.
    """
    session = _oauth_session()
    session.issuer_url = "https://other.example"
    _bridge_env(monkeypatch, _ScriptedSessionManager(session))

    with pytest.raises(SaasAuthError, match="auth login --force"):
        load_auth_context(repo_root=tmp_path)


def test_session_issuer_mismatch_names_the_default_endpoint_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """#300: the refusal names *where* the resolved URL came from, matching
    ``format_saas_mismatch_warning``'s wording — and drops the backticks
    around the remedy that the sibling message never had."""
    session = _oauth_session()
    session.issuer_url = "https://other.example"
    _bridge_env(monkeypatch, _ScriptedSessionManager(session))

    with pytest.raises(
        SaasAuthError,
        match=r"Session is for https://other\.example; the default endpoint now points at https://team\.example — run spec-kitty auth login --force",
    ):
        load_auth_context(repo_root=tmp_path)


def test_session_issuer_mismatch_names_the_env_var_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """#300: when the resolved target came from ``SPEC_KITTY_SAAS_URL``, the
    refusal names that env var, not a generic "the resolved server"."""
    session = _oauth_session()
    session.issuer_url = "https://other.example"
    _bridge_env(monkeypatch, _ScriptedSessionManager(session), env_server_url="https://team.example")

    with pytest.raises(
        SaasAuthError,
        match=r"Session is for https://other\.example; SPEC_KITTY_SAAS_URL now points at https://team\.example — run spec-kitty auth login --force",
    ):
        load_auth_context(repo_root=tmp_path)


def test_session_issuer_mismatch_names_the_config_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """#300: when the resolved target came from ``config.toml``, the refusal
    names that source."""
    session = _oauth_session()
    session.issuer_url = "https://other.example"
    _bridge_env(monkeypatch, _ScriptedSessionManager(session), configured_server_url="https://team.example")

    with pytest.raises(
        SaasAuthError,
        match=r"Session is for https://other\.example; config\.toml \[sync\]\.server_url now points at https://team\.example — run spec-kitty auth login --force",
    ):
        load_auth_context(repo_root=tmp_path)


def test_session_issuer_matching_target_is_paired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """A session recorded against the same server the target resolves to
    (modulo a trailing slash) is paired normally — no false-positive refusal."""
    session = _oauth_session()
    session.issuer_url = "https://team.example/"
    _bridge_env(monkeypatch, _ScriptedSessionManager(session))

    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.saas_url == "https://team.example"
    assert ctx.token == "access-v1"


def test_session_with_no_issuer_url_keeps_working(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    """Sessions minted before #176 carry ``issuer_url=None`` — nothing was
    recorded to compare, so the bridge pairs them exactly as before."""
    session = _oauth_session()
    assert session.issuer_url is None
    _bridge_env(monkeypatch, _ScriptedSessionManager(session))

    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.saas_url == "https://team.example"
    assert ctx.token == "access-v1"


def test_env_token_wins_and_never_consults_the_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_env_auth: None) -> None:
    monkeypatch.setenv("SPEC_KITTY_SAAS_TOKEN", "service-token")
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://env.example")
    manager = _ScriptedSessionManager(_oauth_session())
    _bridge_env(monkeypatch, manager)

    ctx = load_auth_context(repo_root=tmp_path)
    assert ctx.token == "service-token"
    assert manager.session_reads == 0


def test_bridge_seams_are_real_and_unpatched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#236: every test above patches ``_token_manager`` and
    ``_resolved_server_target`` before exercising the bridge, so the lazy
    imports those two helpers wrap (``from specify_cli.auth import
    get_token_manager``, ``from specify_cli.auth.server_target import
    resolve_server_target``) never actually run in this suite — and
    ``_oauth_session_context``'s bare ``except Exception`` would swallow a
    broken import into a silent ``None``, reinstating #198's P0 with the
    whole suite green. This test calls the three seams unpatched, against an
    isolated empty ``SPEC_KITTY_HOME``."""
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://team.example")
    monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
    reset_token_manager()
    try:
        manager = saas_auth_module._token_manager()
        assert isinstance(manager, TokenManager)
        assert manager.get_current_session() is None  # empty store, no crash

        target = saas_auth_module._resolved_server_target()
        assert target.resolved_server_url == "https://team.example"

        # No stored session anywhere: the bridge degrades to None, not a raise.
        assert saas_auth_module._oauth_session_context() is None
    finally:
        reset_token_manager()


# ---------------------------------------------------------------------------
# SaasClient endpoint method signatures (dependency-injected mock)
# ---------------------------------------------------------------------------


def _make_client(response_data: object, status_code: int = 200) -> SaasClient:
    """Build a SaasClient backed by a mock httpx.Client returning fixed data."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status_code
    mock_resp.is_success = 200 <= status_code < 300
    mock_resp.json.return_value = response_data
    mock_resp.text = json.dumps(response_data) if isinstance(response_data, (dict, list)) else str(response_data)

    mock_http = MagicMock(spec=httpx.Client)
    mock_http.get.return_value = mock_resp
    mock_http.post.return_value = mock_resp
    return SaasClient("http://test", "tok", team_slug="my-team", _http=mock_http)


def test_get_audience_default_returns_list() -> None:
    client = _make_client({"members": [{"user_id": 1, "display_name": "Alice"}]})
    result = client.get_audience_default("mission-123")
    assert result == [{"user_id": 1, "display_name": "Alice"}]


def test_get_audience_default_accepts_bare_list() -> None:
    client = _make_client(["Alice", "Bob"])
    result = client.get_audience_default("mission-123")
    assert result == [{"display_name": "Alice"}, {"display_name": "Bob"}]


def test_post_widen_returns_widen_response() -> None:
    client = _make_client(
        {
            "decision_id": "dec-1",
            "widened_at": "2026-04-23T10:00:00Z",
            "slack_thread_url": "https://slack.com/x",
            "invited_count": 2,
        }
    )
    result = client.post_widen("dec-1", [1, 2])
    assert result["decision_id"] == "dec-1"
    assert result["invited_count"] == 2


def test_get_team_integrations_returns_list() -> None:
    client = _make_client({"integrations": ["slack"]})
    result = client.get_team_integrations("my-team")
    assert result == ["slack"]


def test_health_probe_returns_true_on_200() -> None:
    client = _make_client({"status": "ok"})
    assert client.health_probe() is True


def test_health_probe_returns_false_on_error() -> None:
    """health_probe never raises — returns False on any error."""
    mock_http = MagicMock(spec=httpx.Client)
    mock_http.get.side_effect = httpx.TimeoutException("timeout")
    client = SaasClient("http://test", "tok", team_slug="my-team", _http=mock_http)
    assert client.health_probe() is False


def test_fetch_discussion_returns_discussion_data() -> None:
    client = _make_client(
        {
            "decision_id": "dec-1",
            "participants": ["Alice", "Bob"],
            "messages": [{"author": "Alice", "text": "Hello", "timestamp": None}],
            "thread_url": "https://slack.com/y",
            "message_count": 1,
        }
    )
    result = client.fetch_discussion("dec-1")
    assert result["decision_id"] == "dec-1"
    assert result["participants"] == ["Alice", "Bob"]
    assert len(result["messages"]) == 1


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


def test_timeout_exception_maps_to_saas_timeout_error() -> None:
    mock_http = MagicMock(spec=httpx.Client)
    mock_http.get.side_effect = httpx.TimeoutException("timed out")
    client = SaasClient("http://test", "tok", team_slug="my-team", _http=mock_http)
    with pytest.raises(SaasTimeoutError):
        client.get_audience_default("m-1")


def test_401_maps_to_saas_auth_error() -> None:
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.is_success = False
    mock_resp.text = "Unauthorized"
    mock_http = MagicMock(spec=httpx.Client)
    mock_http.get.return_value = mock_resp
    client = SaasClient("http://test", "tok", team_slug="my-team", _http=mock_http)
    with pytest.raises(SaasAuthError) as exc_info:
        client.get_audience_default("m-1")
    assert exc_info.value.status_code == 401


def test_404_maps_to_saas_not_found_error() -> None:
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 404
    mock_resp.is_success = False
    mock_resp.text = "Not Found"
    mock_http = MagicMock(spec=httpx.Client)
    mock_http.get.return_value = mock_resp
    client = SaasClient("http://test", "tok", team_slug="my-team", _http=mock_http)
    with pytest.raises(SaasNotFoundError) as exc_info:
        client.get_audience_default("m-1")
    assert exc_info.value.status_code == 404


def test_request_error_maps_to_saas_client_error() -> None:
    """A non-timeout transport failure (e.g. connection refused) maps to SaasClientError."""
    mock_http = MagicMock(spec=httpx.Client)
    mock_http.get.side_effect = httpx.ConnectError("boom")
    client = SaasClient("http://test", "tok", team_slug="my-team", _http=mock_http)
    with pytest.raises(SaasClientError, match="failed") as exc_info:
        client.get_audience_default("m-1")
    assert not isinstance(exc_info.value, SaasTimeoutError)


def test_500_maps_to_generic_saas_client_error() -> None:
    """A non-401/403/404 error status falls through to the generic SaasClientError branch."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 500
    mock_resp.is_success = False
    mock_resp.text = "Internal Server Error"
    mock_http = MagicMock(spec=httpx.Client)
    mock_http.get.return_value = mock_resp
    client = SaasClient("http://test", "tok", team_slug="my-team", _http=mock_http)
    with pytest.raises(SaasClientError) as exc_info:
        client.get_audience_default("m-1")
    assert not isinstance(exc_info.value, (SaasAuthError, SaasNotFoundError, SaasTimeoutError))
    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Consent-refusal exchange paths (issue #3 fix round: these are the surviving
# refusal branches in ``SaasClient._exchange`` — token-authority absent,
# server-side project_not_admitted, and the refusal reference/message
# rendering they share)
# ---------------------------------------------------------------------------


def test_absent_token_authority_refuses_before_any_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """A token matching no authenticated authority refuses without sending."""
    from specify_cli.saas_client import client as client_module
    from specify_cli.saas_client.errors import SaasConsentError

    monkeypatch.setattr(client_module, "_authenticated_authority_for_token", lambda _token: None)
    mock_http = MagicMock(spec=httpx.Client)
    client = SaasClient("http://test", "tok", _http=mock_http)
    with pytest.raises(SaasConsentError, match="target_authority_mismatch"):
        client.check_repo_admission("owner/repo")
    mock_http.get.assert_not_called()


def test_project_not_admitted_body_maps_to_consent_error() -> None:
    """A non-2xx body carrying ``error_category=project_not_admitted`` is a consent refusal."""
    from specify_cli.saas_client.errors import SaasConsentError

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 403
    mock_resp.is_success = False
    mock_resp.json.return_value = {
        "error_category": "project_not_admitted",
        "idempotency_key": "logical-operation:write:abc",
        "message": "this repo is not admitted to any team",
        "status": "rejected",
        "retryable": False,
    }
    mock_http = MagicMock(spec=httpx.Client)
    mock_http.get.return_value = mock_resp
    client = SaasClient("http://test", "tok", _http=mock_http)
    with pytest.raises(SaasConsentError, match="this repo is not admitted to any team"):
        client.check_repo_admission("owner/repo")


def test_generic_refusal_reference_pins_status_and_envelope_and_message_falls_back() -> None:
    """The refusal reference keeps only its closed key set; bad references fall back."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 403
    mock_resp.json.return_value = {
        "error_category": "project_not_admitted",
        "message": "admission refused by hosted target",
        "not_part_of_the_envelope": "dropped",
        "retryable": False,
        "status": "rejected",
    }

    reference = SaasClient._generic_refusal_reference(mock_resp)

    assert json.loads(reference) == {
        "envelope": {
            "error_category": "project_not_admitted",
            "message": "admission refused by hosted target",
            "retryable": False,
            "status": "rejected",
        },
        "http_status": 403,
    }
    assert SaasClient._generic_refusal_message(reference) == "admission refused by hosted target"
    fallback = "project_not_admitted: hosted target refused this project"
    assert SaasClient._generic_refusal_message(None) == fallback
    assert SaasClient._generic_refusal_message("not-json") == fallback
    assert SaasClient._generic_refusal_message('{"no_envelope": true}') == fallback
    assert SaasClient._generic_refusal_message('{"envelope": {"message": ""}}') == fallback


# ---------------------------------------------------------------------------
# respx integration tests — WP10 (T050)
# ---------------------------------------------------------------------------


class TestRespxIntegration:
    """Full HTTP-level tests using respx to mock httpx transports (WP10)."""

    BASE = "http://saas-test"

    def _client(self, http_client: httpx.Client) -> SaasClient:
        return SaasClient(self.BASE, "test-token", team_slug="my-team", _http=http_client)

    def test_get_audience_default_success_respx(self) -> None:
        """respx: GET /audience-default returns list from {'members': [...]}."""
        import respx

        with respx.mock:
            respx.get(f"{self.BASE}/a/my-team/collaboration/missions/M1/audience-default").respond(200, json={"members": [{"user_id": 1, "display_name": "Alice"}]})
            client = self._client(httpx.Client())
            result = client.get_audience_default("M1")
        assert result == [{"user_id": 1, "display_name": "Alice"}]

    def test_get_audience_default_bare_list_respx(self) -> None:
        """respx: GET /audience-default also accepts a bare JSON list."""
        import respx

        with respx.mock:
            respx.get(f"{self.BASE}/a/my-team/collaboration/missions/M2/audience-default").respond(200, json=["Carol", "Dana"])
            client = self._client(httpx.Client())
            result = client.get_audience_default("M2")
        assert result == [{"display_name": "Carol"}, {"display_name": "Dana"}]

    def test_post_widen_returns_widen_response_respx(self) -> None:
        """respx: POST /widen parses WidenResponse fields (TypedDict)."""
        import respx

        with respx.mock:
            respx.post(f"{self.BASE}/a/my-team/collaboration/decision-points/D1/widen").respond(
                200,
                json={
                    "decision_id": "D1",
                    "widened_at": "2026-04-23T12:00:00Z",
                    "slack_thread_url": "https://slack.com/thread/1",
                    "invited_count": 2,
                },
            )
            client = self._client(httpx.Client())
            result = client.post_widen("D1", [1, 2])
        # WidenResponse is a TypedDict — use dict-style access
        assert result["decision_id"] == "D1"
        assert result["invited_count"] == 2
        assert result["slack_thread_url"] == "https://slack.com/thread/1"

    def test_post_widen_sends_invited_list_respx(self) -> None:
        """respx: POST /widen sends the correct request body."""
        import respx

        route = None
        with respx.mock as mock:
            route = mock.post(f"{self.BASE}/a/my-team/collaboration/decision-points/D2/widen").respond(
                200,
                json={
                    "decision_id": "D2",
                    "widened_at": "2026-04-23T12:00:00Z",
                    "slack_thread_url": None,
                    "invited_count": 1,
                },
            )
            client = self._client(httpx.Client())
            client.post_widen("D2", [3])

        assert route.called
        req_body = json.loads(route.calls[0].request.content)
        assert req_body["invited_user_ids"] == [3]

    def test_health_probe_true_on_200_respx(self) -> None:
        """respx: health_probe() returns True when GET /health returns 200."""
        import respx

        with respx.mock:
            respx.get(f"{self.BASE}/api/v1/health").respond(200, json={"status": "ok"})
            client = self._client(httpx.Client())
            assert client.health_probe() is True

    def test_health_probe_false_on_timeout_respx(self) -> None:
        """respx: health_probe() returns False when httpx raises TimeoutException."""
        import respx

        with respx.mock:
            respx.get(f"{self.BASE}/api/v1/health").mock(side_effect=httpx.TimeoutException("timed out"))
            client = self._client(httpx.Client())
            assert client.health_probe() is False

    def test_get_team_integrations_respx(self) -> None:
        """respx: GET /integrations returns parsed list."""
        import respx

        with respx.mock:
            respx.get(f"{self.BASE}/a/my-team/collaboration/integrations/").respond(200, json={"integrations": ["slack", "github"]})
            client = self._client(httpx.Client())
            result = client.get_team_integrations("my-team")
        assert "slack" in result
        assert "github" in result

    def test_401_maps_to_saas_auth_error_respx(self) -> None:
        """respx: 401 response raises SaasAuthError."""
        import respx

        with respx.mock:
            respx.get(f"{self.BASE}/a/my-team/collaboration/missions/M3/audience-default").respond(401, text="Unauthorized")
            client = self._client(httpx.Client())
            with pytest.raises(SaasAuthError) as exc_info:
                client.get_audience_default("M3")
        assert exc_info.value.status_code == 401

    def test_fetch_discussion_respx(self) -> None:
        """respx: GET /discussion returns parsed DiscussionData (TypedDict)."""
        import respx

        with respx.mock:
            respx.get(f"{self.BASE}/a/my-team/collaboration/decision-points/D3/discussion/").respond(
                200,
                json={
                    "decision_id": "D3",
                    "participants": [{"display_name": "Alice"}, {"display_name": "Bob"}],
                    "messages": [
                        {"author_display_name": "Alice", "text": "Use Postgres", "ts": "1.0"},
                        {"author_display_name": "Bob", "text": "Agreed", "ts": "2.0"},
                    ],
                    "thread_url": "https://slack.com/t3",
                    "message_count": 2,
                },
            )
            client = self._client(httpx.Client())
            result = client.fetch_discussion("D3")

        # DiscussionData is a TypedDict — use dict-style access
        assert result["decision_id"] == "D3"
        assert result["participants"] == ["Alice", "Bob"]
        assert result["message_count"] == 2
        assert result["thread_url"] == "https://slack.com/t3"
        assert len(result["messages"]) == 2
