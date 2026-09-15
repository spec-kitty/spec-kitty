"""Scope: mock-boundary tests for `tracker discover` command — no real git or SaaS calls.

Owned by WP10 of feature 062-tracker-binding-context-discovery.
Extended by WP05 of feature 082-stealth-gated-saas-sync-hardening (readiness-aware).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import typer
from typer.testing import CliRunner

from specify_cli.tracker import saas_client as saas_client_module
from specify_cli.tracker.saas_readiness import ReadinessResult, ReadinessState
from specify_cli.tracker.discovery import BindableResource
from specify_cli.tracker.saas_client import SaaSTrackerClientError
from specify_cli.tracker.service import TrackerServiceError

pytestmark = pytest.mark.fast

runner = CliRunner()


# ---------------------------------------------------------------------------
# Autouse fixture: stub _check_readiness for all existing tests.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_check_readiness(request, monkeypatch):
    """Make _check_readiness a no-op for all tests unless marked otherwise."""
    if "no_readiness_stub" in {m.name for m in request.node.iter_markers()}:
        return
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker._check_readiness",
        lambda *, require_mission_binding, probe_reachability: None,
    )


def _make_app(monkeypatch) -> typer.Typer:
    """Return the tracker app with the feature flag enabled."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    from specify_cli.cli.commands import tracker as tracker_module

    return tracker_module.app


def _make_resource(
    *,
    candidate_token: str = "tok-1",
    display_label: str = "My Team / My Project",
    provider: str = "linear",
    provider_context: dict[str, str] | None = None,
    binding_ref: str | None = None,
    bound_project_slug: str | None = None,
    bound_at: str | None = None,
) -> BindableResource:
    return BindableResource(
        candidate_token=candidate_token,
        display_label=display_label,
        provider=provider,
        provider_context=provider_context or {"workspace_name": "My Team"},
        binding_ref=binding_ref,
        bound_project_slug=bound_project_slug,
        bound_at=bound_at,
    )


# ---------------------------------------------------------------------------
# T052: Rich table output
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_discover_rich_table(mock_service_fn, monkeypatch) -> None:
    """Default discover output contains resource labels and provider in a table."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.discover.return_value = [
        _make_resource(display_label="Eng / Backend", binding_ref=None),
        _make_resource(
            candidate_token="tok-2",
            display_label="Eng / Frontend",
            binding_ref="bind-ref-1",
            bound_project_slug="proj-x",
            bound_at="2026-04-01T00:00:00Z",
        ),
    ]
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["discover", "--provider", "linear"])
    assert result.exit_code == 0, result.output
    assert "Eng / Backend" in result.output
    assert "Eng / Frontend" in result.output
    assert "linear" in result.output
    # Bound/unbound distinction
    assert "available" in result.output
    assert "bound" in result.output


# ---------------------------------------------------------------------------
# T052: JSON output
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_discover_json_output(mock_service_fn, monkeypatch) -> None:
    """--json flag outputs valid JSON with all resource fields (no truncation)."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.discover.return_value = [
        _make_resource(
            candidate_token="tok-abc",
            display_label="Team Alpha",
            provider="linear",
            provider_context={"workspace_name": "Alpha WS"},
            binding_ref="br-1",
            bound_project_slug="proj-alpha",
            bound_at="2026-01-15T10:30:00Z",
        ),
    ]
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["discover", "--provider", "linear", "--json"])
    assert result.exit_code == 0, result.output

    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1

    item = data[0]
    assert item["number"] == 1
    assert item["candidate_token"] == "tok-abc"
    assert item["display_label"] == "Team Alpha"
    assert item["provider"] == "linear"
    assert item["provider_context"] == {"workspace_name": "Alpha WS"}
    assert item["binding_ref"] == "br-1"
    assert item["bound_project_slug"] == "proj-alpha"
    assert item["bound_at"] == "2026-01-15T10:30:00Z"
    assert item["is_bound"] is True


# ---------------------------------------------------------------------------
# T052: Empty resources
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_discover_empty_resources(mock_service_fn, monkeypatch) -> None:
    """Empty discover results produce an informational message (not an error)."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.discover.return_value = []
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["discover", "--provider", "linear"])
    assert result.exit_code == 0, result.output
    assert "No bindable resources found" in result.output
    assert "linear" in result.output


# ---------------------------------------------------------------------------
# T052: Service error
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_discover_service_error(mock_service_fn, monkeypatch) -> None:
    """TrackerServiceError produces error message + exit code 1."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.discover.side_effect = TrackerServiceError("Connection refused")
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["discover", "--provider", "linear"])
    assert result.exit_code == 1
    assert "Connection refused" in result.output


# ---------------------------------------------------------------------------
# Issue #4233: a SaaS non-2xx (403/404/429/5xx) is raised as
# ``SaaSTrackerClientError`` — a *sibling* of ``TrackerServiceError`` (both
# derive from ``RuntimeError``, neither from the other). The command must
# render it as a clean CLI error, never leak an uncaught traceback that
# exposes internal module paths.
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_discover_saas_client_error_renders_clean(mock_service_fn, monkeypatch) -> None:
    """A SaaS 403 becomes a one-line CLI error + Exit(1), not a raw traceback."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.discover.side_effect = SaaSTrackerClientError("HTTP 403")
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["discover", "--provider", "linear"])

    assert result.exit_code == 1
    # The failure must be surfaced as rendered CLI output, not swallowed.
    assert "HTTP 403" in result.output
    # And it must be a handled exit, NOT the raw client error propagating out
    # (which is what leaks the Rich traceback with internal module paths).
    assert not isinstance(result.exception, SaaSTrackerClientError), (
        "SaaSTrackerClientError propagated uncaught out of discover — the operator would see a raw traceback"
    )
    assert "Traceback (most recent call last)" not in result.output


@patch("specify_cli.cli.commands.tracker._service")
def test_discover_saas_client_error_json(mock_service_fn, monkeypatch) -> None:
    """The SaaS-error clean path also holds under ``--json``."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.discover.side_effect = SaaSTrackerClientError("HTTP 429")
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["discover", "--provider", "linear", "--json"])

    assert result.exit_code == 1
    assert "HTTP 429" in result.output
    assert not isinstance(result.exception, SaaSTrackerClientError)


# ---------------------------------------------------------------------------
# Issue #4233 September extension: drive the REAL CLI command against mocked
# SaaS HTTP error responses (not injected service errors) and pin the full
# error-boundary contract — structured server error codes preserved, the
# distinct failure classes actionable, a machine-readable failure object on
# stdout in ``--json`` mode, nonzero exit, no raw traceback, no secrets, and
# no conversion of a failure into a successful empty result.
# ---------------------------------------------------------------------------


def _http_response(status_code: int, json_body: dict[str, object]) -> httpx.Response:
    """Build a fake ``httpx.Response`` carrying a server error payload."""
    resp = httpx.Response(
        status_code=status_code,
        request=httpx.Request("GET", "https://saas.test.example/api/v1/tracker/resources/"),
    )
    resp._content = json.dumps(json_body).encode()
    resp.headers["content-type"] = "application/json"
    return resp


def _mock_saas_http(monkeypatch, tmp_path, responses: list[httpx.Response]) -> None:
    """Point the real tracker stack at a mocked SaaS HTTP transport.

    Only the wire is faked: ``httpx.Client`` inside the tracker client (the
    documented patch seam — 130+ tests under ``tests/tracker/`` use it) and
    the two process-wide auth bridges. The service facade, the client's
    retry/error classification, the PRI-12 envelope parser, and the command's
    error boundary are all the real code under test, driven through a real
    CLI invocation.
    """
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://saas.test.example")
    monkeypatch.setattr(
        "specify_cli.tracker.saas_client._fetch_access_token_sync",
        lambda: "test-access-token",
    )
    monkeypatch.setattr(
        "specify_cli.tracker.saas_client._hosted_authority_for_token",
        lambda _token: saas_client_module._HostedTrackerAuthority(
            account_identity="test-account",
            private_teamspace_id="test-private-teamspace",
            collaborative_team_slug="test-team",
        ),
    )
    mock_http = MagicMock()
    mock_http.request.side_effect = list(responses)
    mock_cls = MagicMock(return_value=MagicMock())
    mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
    mock_cls.return_value.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr("specify_cli.tracker.saas_client.httpx.Client", mock_cls)


def test_discover_saas_403_feature_disabled_renders_clean(monkeypatch, tmp_path) -> None:
    """The exact observed #4233 payload: a clean, actionable error, no traceback.

    ``{"ok": false, "error": "Feature not available.", "error_code":
    "FEATURE_DISABLED"}`` on HTTP 403 must surface the server message, the
    structured code, and a rollout/permission hint — never a raw traceback.
    """
    app = _make_app(monkeypatch)
    _mock_saas_http(
        monkeypatch,
        tmp_path,
        [
            _http_response(
                403,
                {"ok": False, "error": "Feature not available.", "error_code": "FEATURE_DISABLED"},
            )
        ],
    )

    result = runner.invoke(app, ["discover", "--provider", "github"])

    assert result.exit_code == 1
    assert not isinstance(result.exception, SaaSTrackerClientError)
    assert "Traceback (most recent call last)" not in result.output
    # The server message and the structured machine code are both preserved.
    assert "Feature not available." in result.output
    assert "FEATURE_DISABLED" in result.output
    assert "403" in result.output
    # Distinguishing the failure class gives the operator an actionable hint.
    assert "dashboard" in result.output
    # No secrets: the bearer token never reaches operator output.
    assert "test-access-token" not in result.output
    # A failure is never converted into a successful empty result.
    assert "No bindable resources found" not in result.output


def test_discover_saas_403_user_action_required_single_dashboard_hint(monkeypatch, tmp_path) -> None:
    """A ``user_action_required`` failure renders exactly one dashboard instruction.

    The client already suffixes such messages with "(action required — check
    the Spec Kitty dashboard)"; the CLI error boundary must not append a
    second dashboard-pointing hint on top of it. The old suppression
    (``"spec-kitty" in message``) missed the "Spec Kitty" spelling (#4270).
    """
    app = _make_app(monkeypatch)
    _mock_saas_http(
        monkeypatch,
        tmp_path,
        [
            _http_response(
                403,
                {
                    "ok": False,
                    "error": "Feature not available.",
                    "error_code": "FEATURE_DISABLED",
                    "user_action_required": True,
                },
            )
        ],
    )

    result = runner.invoke(app, ["discover", "--provider", "github"])

    assert result.exit_code == 1
    assert not isinstance(result.exception, SaaSTrackerClientError)
    assert "action required — check the Spec Kitty dashboard" in result.output
    # One dashboard instruction (the message's own), not two.
    assert result.output.count("dashboard") == 1


def test_render_cli_error_keeps_hint_when_message_carries_no_guidance(capsys) -> None:
    """``user_action_required`` without dashboard text in the message keeps its hint.

    The suppression is message-content-based, not attribute-based: the
    deadline-exceeded rate-limit failures carry ``user_action_required=True``
    but no dashboard guidance in the message, so their rate-limit hint is not
    a duplicate and must survive (#4270).
    """
    from specify_cli.cli.commands.tracker import _render_cli_error

    exc = SaaSTrackerClientError(
        "Rate-limit retry would exceed the transport operation deadline.",
        error_code="deadline_exceeded",
        status_code=429,
        user_action_required=True,
    )

    _render_cli_error(exc, json_mode=False)

    err = capsys.readouterr().err
    assert "Rate-limit retry" in err
    assert "rate limiting" in err
    assert "dashboard" not in err


@pytest.mark.parametrize(
    ("error_code", "status_code", "expected_guidance"),
    [
        ("binding_not_found", None, "Rebind the tracker"),
        ("session_expired", 401, "spec-kitty auth login"),
        (None, 503, "retry shortly"),
    ],
)
def test_render_cli_error_keeps_distinct_hint_when_message_mentions_dashboard(
    capsys,
    error_code,
    status_code,
    expected_guidance,
) -> None:
    """A dashboard suffix cannot suppress a different computed CLI remedy."""
    from specify_cli.cli.commands.tracker import _render_cli_error

    exc = SaaSTrackerClientError(
        "Action required — check the Spec Kitty dashboard",
        error_code=error_code,
        status_code=status_code,
        user_action_required=True,
    )

    _render_cli_error(exc, json_mode=False)

    err = capsys.readouterr().err
    assert expected_guidance in err
    assert err.lower().count("dashboard") == 1


def test_render_cli_error_suppresses_only_matching_command_guidance(capsys) -> None:
    """A command mention suppresses its own hint, not an unrelated remedy."""
    from specify_cli.cli.commands.tracker import _render_cli_error

    exc = SaaSTrackerClientError(
        "Run `spec-kitty auth login` to refresh the session.",
        error_code="session_expired",
        status_code=401,
    )

    _render_cli_error(exc, json_mode=False)

    err = capsys.readouterr().err
    assert err.count("spec-kitty auth login") == 1


def test_discover_saas_403_feature_disabled_json_machine_readable(monkeypatch, tmp_path) -> None:
    """Under ``--json`` the failure is a parseable machine-readable object."""
    app = _make_app(monkeypatch)
    _mock_saas_http(
        monkeypatch,
        tmp_path,
        [
            _http_response(
                403,
                {"ok": False, "error": "Feature not available.", "error_code": "FEATURE_DISABLED"},
            )
        ],
    )

    result = runner.invoke(app, ["discover", "--provider", "github", "--json"])

    assert result.exit_code == 1
    assert not isinstance(result.exception, SaaSTrackerClientError)
    assert "Traceback (most recent call last)" not in result.output
    # stdout carries exactly one parseable JSON failure object.
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"] == "Feature not available."
    assert payload["error_code"] == "FEATURE_DISABLED"
    assert payload["http_status"] == 403
    assert "action" in payload
    # The human line still reaches stderr; no secrets anywhere.
    assert "test-access-token" not in result.output


def test_discover_saas_429_rate_limited_pri12_code(monkeypatch, tmp_path) -> None:
    """A PRI-12 ``code`` envelope on 429 renders the rate-limit class.

    The client backs off once (``retry_after_seconds: 0``) and re-requests;
    the second 429 raises ``rate_limited``. Parsing the canonical ``code``
    key (not just legacy ``error_code``) is the #2944 coordination.
    """
    app = _make_app(monkeypatch)
    _mock_saas_http(
        monkeypatch,
        tmp_path,
        [
            _http_response(
                429,
                {"code": "rate_limited", "message": "Too many requests", "retry_after_seconds": 0},
            ),
            _http_response(
                429,
                {"code": "rate_limited", "message": "Too many requests", "retry_after_seconds": 0},
            ),
        ],
    )

    result = runner.invoke(app, ["discover", "--provider", "github"])

    assert result.exit_code == 1
    assert not isinstance(result.exception, SaaSTrackerClientError)
    assert "Traceback (most recent call last)" not in result.output
    assert "Too many requests" in result.output
    assert "rate_limited" in result.output
    assert "429" in result.output
    assert "rate limiting" in result.output


def test_discover_saas_401_session_expired(monkeypatch, tmp_path) -> None:
    """A 401 whose token refresh fails renders the re-authenticate class."""
    from specify_cli.auth.errors import AuthenticationError

    app = _make_app(monkeypatch)
    _mock_saas_http(monkeypatch, tmp_path, [_http_response(401, {"message": "Unauthorized"})])
    monkeypatch.setattr(
        "specify_cli.tracker.saas_client._force_refresh_sync",
        MagicMock(side_effect=AuthenticationError("refresh token expired")),
    )

    result = runner.invoke(app, ["discover", "--provider", "github"])

    assert result.exit_code == 1
    assert not isinstance(result.exception, SaaSTrackerClientError)
    assert "Traceback (most recent call last)" not in result.output
    assert "auth login" in result.output
    assert "session_expired" in result.output


def test_discover_saas_5xx_server_failure_pri12_code(monkeypatch, tmp_path) -> None:
    """A 5xx with a canonical ``code`` envelope renders the server-failure class."""
    app = _make_app(monkeypatch)
    _mock_saas_http(
        monkeypatch,
        tmp_path,
        [_http_response(503, {"code": "remote_unavailable", "message": "Backend unavailable"})],
    )

    result = runner.invoke(app, ["discover", "--provider", "github"])

    assert result.exit_code == 1
    assert not isinstance(result.exception, SaaSTrackerClientError)
    assert "Traceback (most recent call last)" not in result.output
    assert "Backend unavailable" in result.output
    assert "remote_unavailable" in result.output
    assert "503" in result.output
    assert "server failure" in result.output


def test_discover_saas_binding_not_found_rebind_hint(monkeypatch, tmp_path) -> None:
    """A canonical-code stale-binding envelope renders the rebind class.

    ``code`` must outrank ``error_category`` on the raised error (the old
    category-first order masked ``binding_not_found`` from every code-driven
    consumer — the #2944 coordination).
    """
    app = _make_app(monkeypatch)
    _mock_saas_http(
        monkeypatch,
        tmp_path,
        [
            _http_response(
                404,
                {
                    "code": "binding_not_found",
                    "error_category": "identity_resolution",
                    "message": "No binding",
                },
            )
        ],
    )

    result = runner.invoke(app, ["discover", "--provider", "github"])

    assert result.exit_code == 1
    assert not isinstance(result.exception, SaaSTrackerClientError)
    assert "Traceback (most recent call last)" not in result.output
    assert "No binding" in result.output
    assert "binding_not_found" in result.output
    assert "Rebind" in result.output


def test_list_tickets_saas_error_json_shared_boundary(monkeypatch, tmp_path) -> None:
    """The shared error boundary covers the other SaaS read commands too."""
    app = _make_app(monkeypatch)
    _mock_saas_http(
        monkeypatch,
        tmp_path,
        [
            _http_response(
                403,
                {"ok": False, "error": "Feature not available.", "error_code": "FEATURE_DISABLED"},
            )
        ],
    )

    result = runner.invoke(app, ["list-tickets", "--provider", "github", "--json"])

    assert result.exit_code == 1
    assert not isinstance(result.exception, SaaSTrackerClientError)
    assert "Traceback (most recent call last)" not in result.output
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error_code"] == "FEATURE_DISABLED"


@pytest.mark.parametrize(
    ("error_code", "status_code", "expected_fragment"),
    [
        ("session_expired", 401, "auth login"),
        ("binding_not_found", None, "Rebind"),
        ("mapping_disabled", None, "Rebind"),
        ("rate_limited", 429, "rate limiting"),
        (None, 503, "server failure"),
        ("FEATURE_DISABLED", 403, "dashboard"),
        (None, None, "__none__"),
    ],
)
def test_saas_error_hint_classification(error_code, status_code, expected_fragment) -> None:
    """The hint classifier distinguishes the #4233 failure classes."""
    from specify_cli.cli.commands.tracker import _saas_error_hint

    hint = _saas_error_hint(error_code, status_code)
    if expected_fragment == "__none__":
        assert hint is None
    else:
        assert hint is not None
        assert expected_fragment in hint


# ---------------------------------------------------------------------------
# T052: Numbering (1-indexed)
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_discover_numbering(mock_service_fn, monkeypatch) -> None:
    """Three resources produce rows numbered 1, 2, 3 in output."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.discover.return_value = [
        _make_resource(candidate_token="t1", display_label="Project A"),
        _make_resource(candidate_token="t2", display_label="Project B"),
        _make_resource(candidate_token="t3", display_label="Project C"),
    ]
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["discover", "--provider", "linear"])
    assert result.exit_code == 0, result.output
    # Rich table renders numbers; verify all three appear
    assert "Project A" in result.output
    assert "Project B" in result.output
    assert "Project C" in result.output


@patch("specify_cli.cli.commands.tracker._service")
def test_discover_json_numbering(mock_service_fn, monkeypatch) -> None:
    """JSON output includes 1-indexed numbers for all resources."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.discover.return_value = [
        _make_resource(candidate_token="t1", display_label="Project A"),
        _make_resource(candidate_token="t2", display_label="Project B"),
        _make_resource(candidate_token="t3", display_label="Project C"),
    ]
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["discover", "--provider", "linear", "--json"])
    assert result.exit_code == 0, result.output

    data = json.loads(result.output)
    assert len(data) == 3
    assert data[0]["number"] == 1
    assert data[1]["number"] == 2
    assert data[2]["number"] == 3


# ---------------------------------------------------------------------------
# T052: Bound vs unbound distinction in rich table
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_discover_bound_unbound_distinction(mock_service_fn, monkeypatch) -> None:
    """Rich table distinguishes bound (has binding_ref) from unbound resources."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.discover.return_value = [
        _make_resource(
            candidate_token="t-unbound",
            display_label="Unbound Proj",
            binding_ref=None,
        ),
        _make_resource(
            candidate_token="t-bound",
            display_label="Bound Proj",
            binding_ref="ref-123",
            bound_project_slug="slug-x",
            bound_at="2026-04-01T00:00:00Z",
        ),
    ]
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["discover", "--provider", "linear"])
    assert result.exit_code == 0, result.output
    # The output should contain both status markers
    assert "available" in result.output
    assert "bound" in result.output


# ---------------------------------------------------------------------------
# T052: JSON output for unbound resource has null fields
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_discover_json_unbound_resource(mock_service_fn, monkeypatch) -> None:
    """JSON output for unbound resource has null binding fields."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.discover.return_value = [
        _make_resource(
            candidate_token="tok-free",
            display_label="Free Project",
            binding_ref=None,
            bound_project_slug=None,
            bound_at=None,
        ),
    ]
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["discover", "--provider", "linear", "--json"])
    assert result.exit_code == 0, result.output

    data = json.loads(result.output)
    assert len(data) == 1
    item = data[0]
    assert item["binding_ref"] is None
    assert item["bound_project_slug"] is None
    assert item["bound_at"] is None
    assert item["is_bound"] is False


# ---------------------------------------------------------------------------
# T025: Readiness-aware tests for discover
# ---------------------------------------------------------------------------


@pytest.mark.no_readiness_stub
@pytest.mark.parametrize(
    "state,expected_message",
    [
        (
            ReadinessState.MISSING_AUTH,
            "No SaaS authentication token is present.",
        ),
        (
            ReadinessState.MISSING_HOST_CONFIG,
            "No SaaS host URL is configured.",
        ),
        # NOTE: ``MISSING_MISSION_BINDING`` is *deliberately absent* from this
        # parametrize matrix.  ``tracker discover`` is the pre-binding command
        # users run to *find* something to bind, so it must NOT gate on an
        # existing binding.  A regression that reintroduces
        # ``require_mission_binding=True`` on this command would be caught by
        # ``test_discover_does_not_require_binding`` below.
    ],
)
def test_discover_readiness_failure(state, expected_message, monkeypatch, tmp_path) -> None:
    """discover exits 1 with the per-prerequisite message on readiness failure."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    from specify_cli.cli.commands import tracker as tracker_module

    failing_result = ReadinessResult(
        state=state,
        message=expected_message,
        next_action="Do something to fix it.",
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker.evaluate_readiness",
        lambda **_kwargs: failing_result,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker.require_repo_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker._resolve_active_feature_slug",
        lambda _repo_root: None,
    )
    # WS5 (issue #18): force INTERACTIVE policy so the human wording is rendered
    # under pytest (otherwise NON_INTERACTIVE single-line format kicks in,
    # which is covered separately in test_tracker.py::test_ws5_*).
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker._resolve_output_policy_for_tracker",
        lambda: "interactive",
    )

    result = runner.invoke(tracker_module.app, ["discover", "--provider", "linear"])
    assert result.exit_code == 1
    assert expected_message in result.output


@pytest.mark.no_readiness_stub
def test_discover_readiness_rollout_disabled(monkeypatch) -> None:
    """discover is invisible (not registered) when rollout flag is off."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")

    import importlib
    import specify_cli.cli.commands as commands_module

    commands_module = importlib.reload(commands_module)
    root = typer.Typer()
    commands_module.register_commands(root)

    result = runner.invoke(root, ["--help"])
    assert result.exit_code == 0
    assert "discover" not in result.output or "tracker" not in result.output


@pytest.mark.no_readiness_stub
def test_discover_readiness_ready_passes_through(monkeypatch, tmp_path) -> None:
    """When readiness is READY, discover proceeds to the service call."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    from specify_cli.cli.commands import tracker as tracker_module

    ready_result = ReadinessResult(
        state=ReadinessState.READY,
        message="",
        next_action=None,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker.evaluate_readiness",
        lambda **_kwargs: ready_result,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker.require_repo_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker._resolve_active_feature_slug",
        lambda _repo_root: None,
    )

    mock_svc = MagicMock()
    mock_svc.discover.return_value = [
        _make_resource(display_label="Alpha Project"),
    ]

    with patch("specify_cli.cli.commands.tracker._service", return_value=mock_svc):
        result = runner.invoke(tracker_module.app, ["discover", "--provider", "linear"])

    assert result.exit_code == 0, result.output
    assert "Alpha Project" in result.output


@pytest.mark.no_readiness_stub
def test_discover_does_not_require_binding(monkeypatch, tmp_path) -> None:
    """`tracker discover` must proceed when no mission binding exists.

    This is a regression guard against a real P1 bug: ``discover`` was
    once wired with ``require_mission_binding=True``, which made fresh
    bind flows impossible because users need ``discover`` to find
    something to bind.  This test asserts the ``require_mission_binding``
    kwarg reaching the readiness evaluator is always ``False`` for
    ``discover``, regardless of whether a binding happens to exist.
    """
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    from specify_cli.cli.commands import tracker as tracker_module

    captured_kwargs: dict[str, object] = {}

    def _fake_evaluate(**kwargs: object) -> ReadinessResult:
        captured_kwargs.update(kwargs)
        return ReadinessResult(
            state=ReadinessState.READY,
            message="",
            next_action=None,
        )

    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker.evaluate_readiness",
        _fake_evaluate,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker.require_repo_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker._resolve_active_feature_slug",
        lambda _repo_root: None,
    )

    mock_svc = MagicMock()
    mock_svc.discover.return_value = [
        _make_resource(display_label="Pre-binding Project"),
    ]

    with patch("specify_cli.cli.commands.tracker._service", return_value=mock_svc):
        result = runner.invoke(tracker_module.app, ["discover", "--provider", "linear"])

    # The command must proceed to the service call — discover is the
    # pre-binding lookup, so it must never gate on binding presence.
    assert result.exit_code == 0, result.output
    assert "Pre-binding Project" in result.output

    # And the flag that would enforce binding presence must be False.
    assert captured_kwargs.get("require_mission_binding") is False, (
        f"discover must pass require_mission_binding=False to the readiness evaluator; got {captured_kwargs.get('require_mission_binding')!r}"
    )
