"""``spec-kitty routes`` (Priivacy-ai/spec-kitty#10): which team admits
this checkout, and which relay carries its moments.

Covers the three answers the command can honestly give — admitted (team +
relay), not admitted (no relay), no answer this run — plus the offline
fast paths (a stored credential or a remembered negative never touch the
network), the fault paths (no hosted remote, nothing to authenticate with),
and ``--json``. The gateway is a scripted subclass of the real class, so no
branch depends on HTTP; the credential store and the resolution seam are the
real ones, isolated per test via ``SPEC_KITTY_HOME``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from collections.abc import Iterator

import pytest
from typer.testing import CliRunner
from kernel.clock import now_utc, timedelta

from specify_cli import app
from specify_cli.auth import reset_token_manager
from specify_cli.auth.server_target import ServerTargetSplitBrainError
from specify_cli.auth.session import StoredSession, Team
from specify_cli.saas_client.errors import SaasAuthError
from specify_cli.zeitgeist_client import credentials, resolution
from specify_cli.zeitgeist_client.resolution import GatewayError, MintedCredential

pytestmark = pytest.mark.fast

runner = CliRunner()


@pytest.fixture()
def state_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "spec-kitty-home"))
    return tmp_path / "spec-kitty-home"


@pytest.fixture()
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "http://saas.test")
    monkeypatch.setenv("SPEC_KITTY_SAAS_TOKEN", "tok")


@pytest.fixture(autouse=True)
def _fresh_token_manager() -> Iterator[None]:
    """Reset the process-wide TokenManager around each test.

    ``load_auth_context``'s OAuth-session fallback (#198) consults that
    singleton, which caches whichever ``SPEC_KITTY_HOME`` was current when
    it was first built — without the reset one test's empty store would leak
    into the next test's expectation."""
    reset_token_manager()
    yield
    reset_token_manager()


class _StoredLoginSession:
    """A stored ``auth login`` session behind a TokenManager-shaped double.

    Starts with an already-expired access token; ``refresh_if_needed``
    rotates it once and records that it ran."""

    def __init__(self, *, expires_in: float = -30) -> None:
        now = now_utc()
        self.refresh_calls = 0
        self.session = StoredSession(
            user_id="user-1",
            email="member@example.com",
            name="Member",
            teams=[Team(id="t1", name="Demo", role="member", is_private_teamspace=False)],
            default_team_id="t1",
            access_token="access-expired",
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

    def get_current_session(self) -> StoredSession:
        return self.session

    async def refresh_if_needed(self) -> bool:
        self.refresh_calls += 1
        self.session.access_token = "access-refreshed"
        self.session.access_token_expires_at = now_utc() + timedelta(seconds=900)
        return True


def _login_only(monkeypatch: pytest.MonkeyPatch, session: _StoredLoginSession) -> None:
    """The #198 laptop shape: SPEC_KITTY_SAAS_URL set, no service token
    anywhere, the stored OAuth session as the only credential."""
    monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
    monkeypatch.delenv("SPEC_KITTY_TEAM_SLUG", raising=False)

    target = SimpleNamespace(resolved_server_url="http://saas.test")

    from specify_cli.saas_client import auth as saas_auth_module

    monkeypatch.setattr(saas_auth_module, "_token_manager", lambda: session)
    monkeypatch.setattr(saas_auth_module, "_resolved_server_target", lambda: target)


def _iso_in(seconds: float) -> str:
    from kernel.clock import now_utc, timedelta

    return (now_utc() + timedelta(seconds=seconds)).isoformat()


class ScriptedGateway(resolution.SaasCapabilityGateway):
    """Records calls, plays back scripted outcomes; never touches the
    network and never chains __init__. Re-derived here rather than imported:
    ``tests`` is not an importable package (pytest.ini keeps ``.`` off
    pythonpath), matching test_resolution.py's own copy."""

    def __init__(
        self,
        *,
        admission: object = None,
        mint: object = None,
    ) -> None:
        self.admission_script = admission if admission is not None else {"admitted": True}
        self.mint_script = mint if mint is not None else self._default_mint()
        self.admission_calls: list[dict[str, str | None]] = []
        self.mint_calls: list[dict[str, str | None]] = []

    @staticmethod
    def _default_mint() -> MintedCredential:
        return MintedCredential(
            relay_url="http://relay",
            relay_token="bearer",
            capability_credential="jwt",
            expires_at=_iso_in(3600),
        )

    def check_repo_admission(self, *, repo_slug: str, host: str | None = None) -> resolution.AdmissionAnswer:
        self.admission_calls.append({"repo_slug": repo_slug, "host": host})
        outcome = self.admission_script
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, dict)
        team = outcome.get("team_slug")
        return resolution.AdmissionAnswer(
            admitted=bool(outcome.get("admitted", False)),
            team_slug=str(team) if team is not None else None,
            reason=outcome.get("reason"),
        )

    def mint_capability(
        self,
        *,
        repo_slug: str,
        kind: str = resolution.KIND_PRESENCE,
        team_slug: str | None = None,
    ) -> MintedCredential:
        self.mint_calls.append({"repo_slug": repo_slug, "kind": kind, "team_slug": team_slug})
        outcome = self.mint_script
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, MintedCredential)
        return outcome


@pytest.fixture()
def clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A checkout whose origin claims to be github.com/acme/widget, made the
    working directory the command runs in."""
    bare = tmp_path / "gh" / "acme" / "widget.git"
    bare.mkdir(parents=True)
    subprocess.run(["git", "init", "--bare", "-q"], cwd=bare, check=True, capture_output=True)
    dest = tmp_path / "work" / "widget"
    dest.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(dest)], check=True, capture_output=True)
    subprocess.run(["git", "remote", "set-url", "origin", "https://github.com/acme/widget.git"], cwd=dest, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=dest, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=dest, check=True, capture_output=True)
    (dest / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=dest, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=dest, check=True, capture_output=True)
    monkeypatch.chdir(dest)
    return dest


def _script_gateway(monkeypatch: pytest.MonkeyPatch, gateway: ScriptedGateway) -> None:
    from specify_cli.cli.commands import routes as routes_module

    monkeypatch.setattr(routes_module.resolution, "SaasCapabilityGateway", lambda *args, **kwargs: gateway)


# --- admitted ---------------------------------------------------------------


def test_fresh_checkout_mints_and_names_the_team_and_relay(state_root: Path, auth_env: None, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The E2E-MVP step-0.4 shape: right after login, `routes` answers with
    the admitting team and the relay — and stores both for next time."""
    gateway = ScriptedGateway(admission={"admitted": True, "team_slug": "demo"})
    _script_gateway(monkeypatch, gateway)

    result = runner.invoke(app, ["routes"])
    assert result.exit_code == 0
    assert "team: demo · relay: http://relay" in result.stdout
    # Team Kitty was asked about the slug/host the checkout itself names.
    assert gateway.admission_calls == [{"repo_slug": "acme/widget", "host": "github.com"}]
    stored = credentials.load(repo="github.com/acme/widget")
    assert stored is not None
    assert stored.team == "demo"
    assert stored.relay_url == "http://relay"


def test_cached_credential_answers_offline_without_asking_team_kitty(state_root: Path, auth_env: None, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    credentials.store(
        repo="github.com/acme/widget",
        relay_url="http://relay",
        token="bearer",
        token_kind="presence",
        expires_at=_iso_in(3600),
        host="github.com",
        repo_slug="acme/widget",
        team="demo",
    )
    gateway = ScriptedGateway(admission=AssertionError("must not be called"), mint=AssertionError("must not be called"))
    _script_gateway(monkeypatch, gateway)

    result = runner.invoke(app, ["routes"])
    assert result.exit_code == 0
    assert "team: demo · relay: http://relay" in result.stdout


def test_cached_credential_answers_offline_even_with_nothing_configured_to_authenticate_with(
    state_root: Path, clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Priivacy-ai/spec-kitty#151: a checkout with a valid stored credential
    but no auth configured anywhere (no env vars, no saas-auth.json, no
    `auth login` session) must still answer offline — the gateway is never
    needed for a cache hit."""
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
    monkeypatch.delenv("SPEC_KITTY_TEAM_SLUG", raising=False)
    credentials.store(
        repo="github.com/acme/widget",
        relay_url="http://relay",
        token="bearer",
        token_kind="presence",
        expires_at=_iso_in(3600),
        host="github.com",
        repo_slug="acme/widget",
        team="demo",
    )

    result = runner.invoke(app, ["routes"])
    assert result.exit_code == 0
    assert "team: demo · relay: http://relay" in result.stdout


def test_cached_negative_answers_offline_even_with_nothing_configured_to_authenticate_with(state_root: Path, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same fix, the remembered-negative branch: "not admitted" must not
    require auth to be configured either."""
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
    monkeypatch.delenv("SPEC_KITTY_TEAM_SLUG", raising=False)
    credentials.store_negative(repo="github.com/acme/widget", reason="stale-reason")

    result = runner.invoke(app, ["routes"])
    assert result.exit_code == 0
    assert "No accessible team route found — no relay" in result.stdout


# --- not admitted -----------------------------------------------------------


def test_no_match_reports_access_scope_and_account_recovery(state_root: Path, auth_env: None, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Foreign-team and genuinely unadmitted repos share a non-disclosing answer."""
    gateway = ScriptedGateway(admission={"admitted": False, "reason": "no_match"})
    _script_gateway(monkeypatch, gateway)

    result = runner.invoke(app, ["routes"])

    assert result.exit_code == 0
    assert "No accessible team route found" in result.stdout
    assert "not admitted to any team" not in result.stdout
    assert "A repo no team admits" not in result.stdout
    assert "spec-kitty auth status" in result.stdout
    assert "spec-kitty auth login --force" in result.stdout
    assert "SPEC_KITTY_SAAS_TOKEN" in result.stdout
    assert gateway.mint_calls == []


def test_not_admitted_prints_the_verdict_and_no_relay(state_root: Path, auth_env: None, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """E2E-MVP step 3.2: a repo no team admits produces nothing anywhere —
    that verdict is the system working, so exit zero."""
    gateway = ScriptedGateway(admission={"admitted": False, "reason": "no team admits acme/widget"})
    _script_gateway(monkeypatch, gateway)

    result = runner.invoke(app, ["routes"])
    assert result.exit_code == 0
    assert "No accessible team route found — no relay" in result.stdout
    assert "no team admits acme/widget" in result.stdout
    negative = credentials.load_negative(repo="github.com/acme/widget")
    assert negative is not None  # remembered, exactly as a transition would


def test_cached_negative_answers_offline(state_root: Path, auth_env: None, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    credentials.store_negative(repo="github.com/acme/widget", reason="stale-reason")
    gateway = ScriptedGateway(admission=AssertionError("must not be called"), mint=AssertionError("must not be called"))
    _script_gateway(monkeypatch, gateway)

    result = runner.invoke(app, ["routes"])
    assert result.exit_code == 0
    assert "No accessible team route found — no relay" in result.stdout


def test_cached_negative_is_loaded_once_for_routes(state_root: Path, auth_env: None, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The offline negative found by ``cached_answer`` is reused by routes."""
    credentials.store_negative(repo="github.com/acme/widget", reason="stale-reason")
    original_load_negative = credentials.load_negative
    load_calls = 0

    def count_negative_load(*, repo: str) -> credentials.NegativeEntry | None:
        nonlocal load_calls
        load_calls += 1
        return original_load_negative(repo=repo)

    monkeypatch.setattr(credentials, "load_negative", count_negative_load)

    result = runner.invoke(app, ["routes"])

    assert result.exit_code == 0
    assert load_calls == 1


# --- faults -----------------------------------------------------------------


def test_unreachable_team_kitty_is_not_dressed_up_as_not_admitted(state_root: Path, auth_env: None, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = ScriptedGateway(admission=GatewayError("connection refused"))
    _script_gateway(monkeypatch, gateway)

    result = runner.invoke(app, ["routes"])
    assert result.exit_code == 1
    assert "gave no answer" in result.stdout
    assert credentials.load_negative(repo="github.com/acme/widget") is None  # transient: cached nothing


def test_unauthenticated_checkout_exits_nonzero_with_a_login_hint(state_root: Path, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
    monkeypatch.delenv("SPEC_KITTY_TEAM_SLUG", raising=False)

    result = runner.invoke(app, ["routes"])
    assert result.exit_code == 1
    assert "auth login" in result.stdout


def test_config_source_refusal_survives_rich_rendering(clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The auth refusal's ``[sync]`` source label is data, not Rich markup."""
    from specify_cli.cli.commands import routes as routes_module

    def _raise_config_source_mismatch(repo_root: Path) -> None:
        raise SaasAuthError(
            "Session is for https://other.example; config.toml [sync].server_url now points at https://team.example — run spec-kitty auth login --force"
        )

    monkeypatch.setattr(routes_module, "load_auth_context", _raise_config_source_mismatch)

    result = runner.invoke(app, ["routes"])

    assert result.exit_code == 1
    assert "config.toml [sync].server_url now points at" in result.stdout


def test_split_brain_auth_refusal_keeps_its_specific_remediation(clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The route wrapper must not turn a split-brain refusal back into a login hint."""
    from specify_cli.cli.commands import routes as routes_module

    def _raise_split_brain(repo_root: Path) -> None:
        cause = ServerTargetSplitBrainError(
            configured_server_url="https://legit-team-kitty.example.com",
            env_server_url="https://attacker.example.com",
        )
        raise SaasAuthError(str(cause)) from cause

    monkeypatch.setattr(routes_module, "load_auth_context", _raise_split_brain)

    result = runner.invoke(app, ["routes"])

    assert result.exit_code == 1
    assert "Server target split-brain detected" in result.stdout
    assert "legit-team-kitty.example.com" in result.stdout
    assert "attacker.example.com" in result.stdout
    assert "Run `spec-kitty auth login` first." not in result.stdout


# --- the documented login path (#198) ----------------------------------------


def test_oauth_session_alone_carries_routes(state_root: Path, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """E2E-MVP §0.4 as a human runs it: SPEC_KITTY_SAAS_URL set, `auth login`
    once, no service token anywhere — and `routes` still answers with the
    team and the relay."""
    session = _StoredLoginSession(expires_in=900)  # a live access token
    gateway = ScriptedGateway(admission={"admitted": True, "team_slug": "demo"})
    _script_gateway(monkeypatch, gateway)
    _login_only(monkeypatch, session)

    result = runner.invoke(app, ["routes"])
    assert result.exit_code == 0
    assert "team: demo · relay: http://relay" in result.stdout
    assert session.refresh_calls == 0  # live token: no refresh round trip


def test_expired_oauth_session_is_refreshed_then_carries_routes(state_root: Path, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The laptop woke up with an expired access token: routes refreshes the
    renewable session first and answers anyway."""
    session = _StoredLoginSession()  # starts expired
    gateway = ScriptedGateway(admission={"admitted": True, "team_slug": "demo"})
    _script_gateway(monkeypatch, gateway)
    _login_only(monkeypatch, session)

    result = runner.invoke(app, ["routes"])
    assert result.exit_code == 0
    assert "team: demo · relay: http://relay" in result.stdout
    assert session.refresh_calls == 1


def test_expired_session_that_cannot_refresh_exits_with_the_login_hint(state_root: Path, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Refresh rejected the stored refresh token: the refusal names the way
    out instead of dressing up as 'nothing configured'."""

    class _DeadSession(_StoredLoginSession):
        async def refresh_if_needed(self) -> bool:
            self.refresh_calls += 1
            from specify_cli.auth.errors import RefreshTokenExpiredError

            raise RefreshTokenExpiredError("refresh token expired")

    gateway = ScriptedGateway(admission=AssertionError("must not be called"))
    _script_gateway(monkeypatch, gateway)
    _login_only(monkeypatch, _DeadSession())

    result = runner.invoke(app, ["routes"])
    assert result.exit_code == 1
    assert "auth login" in result.stdout


def test_unadmitted_repo_through_the_login_session_prints_the_verdict(state_root: Path, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Still no error for a repo nobody admits — even authenticated via the
    OAuth session, "produces nothing anywhere" is exit zero."""
    gateway = ScriptedGateway(admission={"admitted": False, "reason": "no team admits acme/widget"})
    _script_gateway(monkeypatch, gateway)
    _login_only(monkeypatch, _StoredLoginSession())

    result = runner.invoke(app, ["routes"])
    assert result.exit_code == 0
    assert "No accessible team route found — no relay" in result.stdout


def test_checkout_without_a_hosted_remote_has_nothing_to_ask(
    state_root: Path, auth_env: None, clone: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local_only = tmp_path / "somewhere" / "repo.git"  # a path-shaped origin parses to no host/slug
    local_only.mkdir(parents=True)
    subprocess.run(["git", "remote", "set-url", "origin", str(local_only)], cwd=clone, check=True, capture_output=True)

    result = runner.invoke(app, ["routes"])
    assert result.exit_code == 1
    assert "no hosted forge remote" in result.stdout


def test_routes_is_registered_at_the_top_level() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "routes" in result.stdout


# --- --json -----------------------------------------------------------------


def test_json_shape_when_admitted(state_root: Path, auth_env: None, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = ScriptedGateway(admission={"admitted": True, "team_slug": "demo"})
    _script_gateway(monkeypatch, gateway)

    result = runner.invoke(app, ["routes", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["admitted"] is True
    assert payload["team"] == "demo"
    assert payload["relay_url"] == "http://relay"
    assert payload["repository"]["slug"] == "acme/widget"
    assert payload["repository"]["host"] == "github.com"
    assert payload["credential"]["token_kind"] == "presence"


def test_json_shape_when_not_admitted(state_root: Path, auth_env: None, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = ScriptedGateway(admission={"admitted": False, "reason": "denied"})
    _script_gateway(monkeypatch, gateway)

    result = runner.invoke(app, ["routes", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["admitted"] is False
    assert payload["relay_url"] is None
    assert payload["team"] is None
    assert payload["reason"] == "denied"
