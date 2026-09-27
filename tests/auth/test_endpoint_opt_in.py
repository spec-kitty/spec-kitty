"""ATDD contract for the endpoint opt-in reversal (FR-011/FR-012, C-006).

Reverses #3980 D-5: the packaged live-endpoint fallback (``PACKAGED_DEFAULT``)
is removed from ``auth/server_target.py`` and ``auth/config.py::get_saas_base_url()``
so a fresh install resolves the hosted endpoint **only** from
``SPEC_KITTY_SAAS_URL`` or ``config.toml [sync].server_url``. Every explicit
caller now raises ``HostedEndpointUnconfigured`` with setup guidance instead
of silently resolving to ``https://team.spec-kitty.ai``; every automatic /
best-effort caller degrades to ``None``/tolerant fallback via the new
``resolve_server_target_or_none()`` sibling.

Caller census (authoritative artifact for the caller classification --
check this list against the diff). Each entry: call site -- classification
-- action.

1. ``cli/commands/_auth_saas_target.py::print_saas_endpoint`` -- Explicit --
   added ``except HostedEndpointUnconfigured`` (guidance line, no
   traceback).
2. ``cli/commands/_auth_login.py::login_impl`` -- Explicit -- no code
   change; the pre-existing ``except ConfigurationError`` becomes live.
3. ``tracker/saas_client.py::SaaSTrackerClient.__init__`` -- Explicit --
   wrapped in ``try/except HostedEndpointUnconfigured`` that raises
   ``SaaSTrackerClientError(error_code="hosted_endpoint_unconfigured")``.
   Test: ``test_saas_tracker_client_construction_raises_guarded_error_when_unconfigured``.
4. ``tracker/saas_readiness.py::_probe_host_config`` -- Automatic -- no
   code change; the existing broad ``except Exception`` was already
   tolerant. Verification test added.
5. ``saas_client/auth.py::_resolved_server_target``/``_server_target_url``
   -- Automatic -- no code change; already ``except Exception``.
   Verification test added.
6. ``cli/commands/_auth_doctor.py::_server_issuer_mismatch_error`` --
   Automatic -- no code change; already ``except Exception``.
   ``HostedEndpointUnconfigured``-specific verification test added
   (``test_server_issuer_mismatch_error_degrades_to_none_when_unconfigured``).
7. ``cli/commands/_auth_doctor.py::_check_server_session`` -- Automatic --
   no code change; already tolerant via ``_resolve_target_for_server_session``,
   message already correct. ``HostedEndpointUnconfigured``-specific
   verification test added
   (``test_check_server_session_reports_saas_url_not_configured``).
8. ``cli/commands/_auth_logout.py::_print_issuer_mismatch_warning`` --
   Explicit -- added ``except HostedEndpointUnconfigured`` alongside the
   existing two. Test (real, unmocked ``RevokeFlow.revoke``):
   ``test_logout_prints_guidance_with_no_traceback_when_endpoint_unconfigured``.
9. ``auth/flows/revoke.py::RevokeFlow.revoke`` -- Explicit (never raises)
   -- widened the except tuple to fold into
   ``RevokeOutcome.ISSUER_MISMATCH``. Test:
   ``test_revoke_flow_folds_unconfigured_endpoint_into_issuer_mismatch``.
10. ``auth/token_manager.py:455,618`` via ``resolve_token_endpoint`` --
    Explicit -- gap found at the rehydrate boundary (line ~498): added
    ``HostedEndpointUnconfigured`` to its fail-closed no-op except tuple.
    The ``refresh_if_needed`` boundary (line ~618) is left to propagate --
    it is the top-level explicit boundary. Test:
    ``test_rehydrate_membership_returns_false_without_raising_when_unconfigured``.
11. ``auth/flows/refresh.py::TokenRefreshFlow.refresh`` -- Explicit --
    verified; caller (``token_manager.py``, #10) already covers it.
12. ``auth/websocket/token_provisioning.py`` -- Explicit -- verified; no
    live ``src/`` caller wires this up yet (grep confirmed).
13. ``auth/http/transport.py::_targets_configured_saas`` -- Automatic --
    code change (D4): resolves via ``resolve_server_target_or_none()``
    instead of ``get_saas_base_url()``. Tests: ``TestTargetsConfiguredSaas``
    below (env-configured match, config.toml-only-configured match/
    non-match, unconfigured -> False, env-wins-over-disagreeing-config).
14. ``auth/flows/authorization_code.py``/``device_code.py``
    ``get_saas_base_url()`` fallback -- Explicit, dead-path-in-login -- no
    code change; direct-construction test added proving the raise.

Out-of-map note (T028): ``zeitgeist_client/resolution.py::_default_gateway``
(owned by WP03) was greped and found **not** to call ``get_saas_base_url``,
``resolve_server_target``, or ``resolve_token_endpoint`` directly -- it
resolves its own gateway config independently. No action needed from WP06;
flagged for the WP03 implementer/reviewer to confirm.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.auth.config import ENDPOINT_UNCONFIGURED_GUIDANCE, get_saas_base_url
from specify_cli.auth.errors import ConfigurationError
from specify_cli.auth.server_target import (
    SAAS_URL_ENV_VAR,
    HostedEndpointUnconfigured,
    OverrideMode,
    ServerTargetSplitBrainError,
    resolve_server_target,
    resolve_server_target_or_none,
)

pytestmark = [pytest.mark.fast]

CONFIG_URL = "https://config.example.com"
ENV_URL = "https://env.example.com"


@pytest.fixture
def unconfigured_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Isolate a throwaway ``SPEC_KITTY_HOME`` with no env override and no
    ``config.toml`` -- and no ``.kittify/saas-auth.json`` (a fresh checkout
    has no ``.kittify`` under a throwaway home either)."""
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
    monkeypatch.delenv(SAAS_URL_ENV_VAR, raising=False)
    return tmp_path


def _expected_config_path() -> str:
    from specify_cli.paths import get_runtime_root

    return str(get_runtime_root().base / "config.toml")


# ---------------------------------------------------------------------------
# resolve_server_target() raises when unconfigured
# ---------------------------------------------------------------------------


def test_resolve_server_target_raises_when_unconfigured(unconfigured_root: Path) -> None:
    with pytest.raises(HostedEndpointUnconfigured) as excinfo:
        resolve_server_target()

    message = str(excinfo.value)
    assert SAAS_URL_ENV_VAR in message
    assert _expected_config_path() in message


def test_hosted_endpoint_unconfigured_is_a_configuration_error() -> None:
    assert issubclass(HostedEndpointUnconfigured, ConfigurationError)


def test_resolve_server_target_or_none_returns_none_when_unconfigured(
    unconfigured_root: Path,
) -> None:
    assert resolve_server_target_or_none() is None


# ---------------------------------------------------------------------------
# get_saas_base_url() delegates through the same guidance
# ---------------------------------------------------------------------------


def test_get_saas_base_url_raises_when_env_unset(unconfigured_root: Path) -> None:
    with pytest.raises(HostedEndpointUnconfigured) as excinfo:
        get_saas_base_url()

    message = str(excinfo.value)
    assert SAAS_URL_ENV_VAR in message
    assert _expected_config_path() in message


def test_get_saas_base_url_still_returns_env_override_when_set(unconfigured_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)
    assert get_saas_base_url() == ENV_URL


def test_endpoint_unconfigured_guidance_is_a_single_source_constant() -> None:
    """Sonar S1192: the guidance text is one module constant, reused by both
    ``get_saas_base_url()`` and the resolver -- not two independent
    literals that could drift."""
    assert "{config_path}" in ENDPOINT_UNCONFIGURED_GUIDANCE
    assert SAAS_URL_ENV_VAR in ENDPOINT_UNCONFIGURED_GUIDANCE
    assert "[sync].server_url" in ENDPOINT_UNCONFIGURED_GUIDANCE


# ---------------------------------------------------------------------------
# The configured path is unchanged (env or config.toml)
# ---------------------------------------------------------------------------


def test_resolve_server_target_returns_configured_env_value(unconfigured_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)
    target = resolve_server_target()
    assert target.resolved_server_url == ENV_URL
    assert target.override_mode is OverrideMode.PROCESS_OVERRIDE


def test_resolve_server_target_returns_configured_toml_value(
    unconfigured_root: Path,
) -> None:
    (unconfigured_root / "config.toml").write_text(f'[sync]\nserver_url = "{CONFIG_URL}"\n', encoding="utf-8")
    target = resolve_server_target()
    assert target.resolved_server_url == CONFIG_URL
    assert target.override_mode is OverrideMode.NONE


def test_split_brain_guard_still_fires_without_a_whole_process_override(unconfigured_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (unconfigured_root / "config.toml").write_text(f'[sync]\nserver_url = "{CONFIG_URL}"\n', encoding="utf-8")
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)

    with pytest.raises(ServerTargetSplitBrainError):
        resolve_server_target(process_wide_override=False)


def test_split_brain_guard_unaffected_by_or_none_variant(unconfigured_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``resolve_server_target_or_none`` swallows only the unconfigured case
    -- a genuine split-brain ambiguity still propagates (it is not
    "unconfigured", it is a real ambiguity a caller must not silently
    paper over, C-005/#4311)."""
    (unconfigured_root / "config.toml").write_text(f'[sync]\nserver_url = "{CONFIG_URL}"\n', encoding="utf-8")
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)

    with pytest.raises(ServerTargetSplitBrainError):
        resolve_server_target_or_none(process_wide_override=False)


# ---------------------------------------------------------------------------
# R-2: explicit sources unaffected by removing the packaged fallback
# ---------------------------------------------------------------------------


def test_saas_client_resolved_server_target_degrades_to_none_when_unconfigured(
    unconfigured_root: Path,
) -> None:
    """R-2 / item 5 verification: ``saas_client/auth.py``'s own endpoint
    resolution (feeding ``.kittify/saas-auth.json``-token pairing) already
    degrades any resolution trouble to a falsy value -- confirm this holds
    for the new ``HostedEndpointUnconfigured`` case specifically, not just
    incidentally via the pre-existing broad except."""
    from specify_cli.saas_client.auth import _server_target_url

    assert _server_target_url() == ""


def test_saas_readiness_probe_degrades_to_none_when_unconfigured(
    unconfigured_root: Path,
) -> None:
    """T028 item 4 verification: the readiness probe's existing broad
    ``except Exception`` already tolerates ``HostedEndpointUnconfigured`` --
    assert this explicitly rather than relying on incidental coverage."""
    from specify_cli.tracker.saas_readiness import _probe_host_config

    assert _probe_host_config() is None


# ---------------------------------------------------------------------------
# T028 item 14: direct construction of the OAuth flow classes (dead in
# practice via _auth_login.py, which always pre-resolves) now raises rather
# than silently defaulting.
# ---------------------------------------------------------------------------


def test_authorization_code_flow_direct_construction_raises_when_unconfigured(
    unconfigured_root: Path,
) -> None:
    from specify_cli.auth.flows.authorization_code import AuthorizationCodeFlow

    with pytest.raises(HostedEndpointUnconfigured):
        AuthorizationCodeFlow()


def test_device_code_flow_direct_construction_raises_when_unconfigured(
    unconfigured_root: Path,
) -> None:
    from specify_cli.auth.flows.device_code import DeviceCodeFlow

    with pytest.raises(HostedEndpointUnconfigured):
        DeviceCodeFlow()


# ---------------------------------------------------------------------------
# T028 item 12: websocket token provisioning has no live src/ caller today;
# pin that a direct call still raises cleanly (ConfigurationError family),
# not an unrelated traceback shape.
# ---------------------------------------------------------------------------


def test_resolve_token_endpoint_raises_hosted_endpoint_unconfigured(
    unconfigured_root: Path,
) -> None:
    from specify_cli.auth.server_target import resolve_token_endpoint

    with pytest.raises(HostedEndpointUnconfigured):
        resolve_token_endpoint(None)


# ---------------------------------------------------------------------------
# T029 step 3 (R-2): two sources stay explicit and unaffected by removing
# the packaged fallback -- neither is touched by this WP's owned_files, but
# both must keep resolving without HostedEndpointUnconfigured.
# ---------------------------------------------------------------------------


def test_saas_auth_json_saas_url_resolves_without_raising(
    unconfigured_root: Path,
) -> None:
    """R-2 source 1: ``.kittify/saas-auth.json``'s own ``saas_url`` (paired
    with its own token) resolves through ``saas_client.auth.load_auth_context``
    without ever consulting ``resolve_server_target``/``get_saas_base_url``
    -- confirmed here by leaving both fully unconfigured (``unconfigured_root``)
    and proving the call still succeeds using only the file's own fields."""
    import json

    from specify_cli.saas_client.auth import load_auth_context

    kittify_dir = unconfigured_root / ".kittify"
    kittify_dir.mkdir(parents=True, exist_ok=True)
    (kittify_dir / "saas-auth.json").write_text(
        json.dumps({"saas_url": "https://file-configured.example", "token": "file-token-123"}),
        encoding="utf-8",
    )

    ctx = load_auth_context(repo_root=unconfigured_root)

    assert ctx.saas_url == "https://file-configured.example"
    assert ctx.token == "file-token-123"


def test_kitty_env_sourced_saas_url_resolves_without_raising(
    unconfigured_root: Path,
) -> None:
    """R-2 source 2: a ``SPEC_KITTY_SAAS_URL`` value sourced from a committed
    ``.kittify/.kitty.env`` file (not a real shell env var) still resolves
    explicitly through the real env-loading entry point
    (``bootstrap.env_file.load_operator_env_file``), which merges the
    ``.kitty.env`` tier into ``environ`` via ``setdefault`` before this
    module ever reads ``SPEC_KITTY_SAAS_URL``."""
    from specify_cli.bootstrap.env_file import load_operator_env_file

    kittify_dir = unconfigured_root / ".kittify"
    kittify_dir.mkdir(parents=True, exist_ok=True)
    (kittify_dir / ".kitty.env").write_text(
        'SPEC_KITTY_SAAS_URL="https://kitty-env-configured.example"\n',
        encoding="utf-8",
    )
    # A plain dict stands in for os.environ (full isolation, no monkeypatch
    # teardown needed for the merge logic itself) -- but resolve_server_target
    # reads the real os.environ via get_saas_url_env_override(), so seed the
    # real one the same way production does (repo_root resolved from cwd).
    fake_environ: dict[str, str] = {}
    load_operator_env_file(start=unconfigured_root, environ=fake_environ)
    assert fake_environ["SPEC_KITTY_SAAS_URL"] == "https://kitty-env-configured.example"

    # Prove the real production entry point (os.environ, repo root found by
    # walking up from `start`) resolves it too, end to end.
    import os

    load_operator_env_file(start=unconfigured_root)
    try:
        assert os.environ["SPEC_KITTY_SAAS_URL"] == "https://kitty-env-configured.example"
        assert resolve_server_target().resolved_server_url == "https://kitty-env-configured.example"
        assert get_saas_base_url() == "https://kitty-env-configured.example"
    finally:
        os.environ.pop("SPEC_KITTY_SAAS_URL", None)


# ---------------------------------------------------------------------------
# T028 item 13 (D4): auth/http/transport.py::_targets_configured_saas
# resolves through resolve_server_target_or_none() rather than the now
# env-only-and-raising get_saas_base_url(), so a config.toml-only user keeps
# the stdlib fallback.
# ---------------------------------------------------------------------------


class TestTargetsConfiguredSaas:
    def test_matches_when_env_configured(self, unconfigured_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.auth.http.transport import _targets_configured_saas

        monkeypatch.setenv(SAAS_URL_ENV_VAR, "https://env-saas.example")

        assert _targets_configured_saas("https://env-saas.example/api/v1/thing") is True
        assert _targets_configured_saas("https://other.example/api/v1/thing") is False

    def test_matches_when_config_toml_only_configured(self, unconfigured_root: Path) -> None:
        """A config.toml-only-configured user (no env var) still gets the
        stdlib fallback -- the exact D4 regression this WP fixes: the old
        call through the now env-only get_saas_base_url() would have
        silently disabled this fallback for such a user."""
        from specify_cli.auth.http.transport import _targets_configured_saas

        (unconfigured_root / "config.toml").write_text('[sync]\nserver_url = "https://config-saas.example"\n', encoding="utf-8")

        assert _targets_configured_saas("https://config-saas.example/api/v1/thing") is True
        assert _targets_configured_saas("https://other.example/api/v1/thing") is False

    def test_false_when_unconfigured(self, unconfigured_root: Path) -> None:
        from specify_cli.auth.http.transport import _targets_configured_saas

        assert _targets_configured_saas("https://anything.example/api/v1/thing") is False

    def test_env_wins_over_disagreeing_config_never_raises(self, unconfigured_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``resolve_server_target_or_none()`` is called with its default
        ``process_wide_override=True``, so an env/config disagreement here
        resolves to the env value (whole-process override) rather than a
        split-brain -- this comparison never raises regardless."""
        from specify_cli.auth.http.transport import _targets_configured_saas

        (unconfigured_root / "config.toml").write_text(f'[sync]\nserver_url = "{CONFIG_URL}"\n', encoding="utf-8")
        monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)

        assert _targets_configured_saas(f"{ENV_URL}/api/v1/thing") is True
        assert _targets_configured_saas(f"{CONFIG_URL}/api/v1/thing") is False


# ---------------------------------------------------------------------------
# T028 item 3: SaaSTrackerClient.__init__ wraps the resolver's
# HostedEndpointUnconfigured into a guarded SaaSTrackerClientError.
# ---------------------------------------------------------------------------


def test_saas_tracker_client_construction_raises_guarded_error_when_unconfigured(
    unconfigured_root: Path,
) -> None:
    from specify_cli.tracker.saas_client import SaaSTrackerClient, SaaSTrackerClientError

    with pytest.raises(SaaSTrackerClientError) as excinfo:
        SaaSTrackerClient()

    assert excinfo.value.error_code == "hosted_endpoint_unconfigured"
    assert SAAS_URL_ENV_VAR in str(excinfo.value)


# ---------------------------------------------------------------------------
# T028 item 8: _auth_logout.py::_print_issuer_mismatch_warning's new
# except HostedEndpointUnconfigured branch.
# ---------------------------------------------------------------------------


def test_logout_prints_guidance_with_no_traceback_when_endpoint_unconfigured(
    unconfigured_root: Path,
) -> None:
    """Exercised through the real (unmocked) RevokeFlow.revoke, per the
    reviewer's requested scenario: a stored session, no endpoint configured,
    logout must print the guidance and never traceback."""
    from unittest.mock import Mock

    from kernel.clock import now_utc, timedelta
    from typer.testing import CliRunner

    from specify_cli.auth import reset_token_manager
    from specify_cli.auth.session import StoredSession, Team
    from specify_cli.cli.commands.auth import app

    now = now_utc()
    session = StoredSession(
        user_id="u_1",
        email="alice@example.com",
        name="Alice",
        teams=[Team(id="tm_1", name="Acme", role="admin", is_private_teamspace=True)],
        default_team_id="tm_1",
        access_token="at_1",
        refresh_token="rt_1",
        session_id="sess_1",
        issued_at=now,
        access_token_expires_at=now + timedelta(seconds=3600),
        refresh_token_expires_at=now + timedelta(days=89),
        scope="offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=None,
    )
    mock_storage = Mock()
    mock_storage.backend_name = "file"
    mock_storage.read.return_value = session
    mock_storage.write = Mock(return_value=None)
    mock_storage.delete = Mock(return_value=None)

    from unittest.mock import patch

    reset_token_manager()
    with patch(
        "specify_cli.auth.secure_storage.SecureStorage.from_environment",
        return_value=mock_storage,
    ):
        result = CliRunner().invoke(app, ["logout"])

    assert result.exit_code == 0, result.stdout
    assert "Traceback" not in result.stdout
    assert "Server-side revocation skipped" in result.stdout
    assert "No hosted endpoint configured" in result.stdout
    assert "Logged out" in result.stdout
    mock_storage.delete.assert_called_once()


# ---------------------------------------------------------------------------
# T028 item 9: RevokeFlow.revoke folds HostedEndpointUnconfigured into
# RevokeOutcome.ISSUER_MISMATCH -- never raises.
# ---------------------------------------------------------------------------


async def test_revoke_flow_folds_unconfigured_endpoint_into_issuer_mismatch(
    unconfigured_root: Path,
) -> None:
    from kernel.clock import now_utc, timedelta

    from specify_cli.auth.flows.revoke import RevokeFlow, RevokeOutcome
    from specify_cli.auth.session import StoredSession, Team

    now = now_utc()
    session = StoredSession(
        user_id="u_1",
        email="alice@example.com",
        name="Alice",
        teams=[Team(id="tm_1", name="Acme", role="admin", is_private_teamspace=True)],
        default_team_id="tm_1",
        access_token="at_1",
        refresh_token="rt_1",
        session_id="sess_1",
        issued_at=now,
        access_token_expires_at=now + timedelta(seconds=3600),
        refresh_token_expires_at=now + timedelta(days=89),
        scope="offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=None,
    )

    outcome = await RevokeFlow().revoke(session)

    assert outcome is RevokeOutcome.ISSUER_MISMATCH


# ---------------------------------------------------------------------------
# T028 item 10: the token_manager.rehydrate_membership_if_needed gap fix --
# a genuine gap this WP found and closed (its except tuple predated
# HostedEndpointUnconfigured). Must return False and log, never raise, when
# the endpoint is unconfigured -- the path WP07's backfill relies on.
# ---------------------------------------------------------------------------


async def test_rehydrate_membership_returns_false_without_raising_when_unconfigured(unconfigured_root: Path, caplog: pytest.LogCaptureFixture) -> None:
    from kernel.clock import now_utc, timedelta

    from specify_cli.auth.secure_storage.file_fallback import FileFallbackStorage
    from specify_cli.auth.session import StoredSession, Team
    from specify_cli.auth.token_manager import TokenManager

    now = now_utc()
    session = StoredSession(
        user_id="u_1",
        email="alice@example.com",
        name="Alice",
        teams=[Team(id="tm_1", name="Acme", role="member")],  # no private teamspace
        default_team_id="tm_1",
        access_token="at_1",
        refresh_token="rt_1",
        session_id="sess_1",
        issued_at=now,
        access_token_expires_at=now + timedelta(seconds=3600),
        refresh_token_expires_at=now + timedelta(days=89),
        scope="offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=None,
    )
    storage = FileFallbackStorage(base_dir=unconfigured_root / "auth")
    tm = TokenManager(storage=storage)
    tm.set_session(session)

    with caplog.at_level("WARNING", logger="specify_cli.auth.token_manager"):
        result = tm.rehydrate_membership_if_needed(force=True)

    assert result is False
    assert any("skipping /api/v1/me fetch" in record.getMessage() for record in caplog.records)


# ---------------------------------------------------------------------------
# T028 items 6/7 (non-blocking review note): a HostedEndpointUnconfigured-
# specific case for the two _auth_doctor.py best-effort paths, rather than
# relying only on a generic-exception helper test.
# ---------------------------------------------------------------------------


def test_server_issuer_mismatch_error_degrades_to_none_when_unconfigured(
    unconfigured_root: Path,
) -> None:
    """Item 6: with a session naming an issuer but no target passed and no
    endpoint configured, the resolver's HostedEndpointUnconfigured is
    caught by the existing broad except -- never propagates."""
    from unittest.mock import Mock

    from specify_cli.cli.commands._auth_doctor import _server_issuer_mismatch_error

    session = Mock(issuer_url="https://saas.test")
    tm = Mock()
    tm.get_current_session.return_value = session

    result = _server_issuer_mismatch_error(tm)

    assert result is None


async def test_check_server_session_reports_saas_url_not_configured(unconfigured_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Item 7: _check_server_session()'s end-to-end tolerant handling of an
    unconfigured endpoint, specifically via HostedEndpointUnconfigured (not
    merely any Exception)."""
    from unittest.mock import Mock

    import specify_cli.auth as _auth_module
    from specify_cli.cli.commands._auth_doctor import ServerSessionStatus, _check_server_session

    monkeypatch.setattr(_auth_module, "get_token_manager", lambda: Mock(session_assessment=None))

    result = await _check_server_session()

    assert result == ServerSessionStatus(active=False, error="SaaS URL not configured")
