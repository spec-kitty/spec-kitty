"""Scope: mock-boundary tests for the local-only tracker CLI -- no real git.

The hosted/SaaS surface (discover, issue-search, list-tickets, the SaaS
discovery-bind flow, ``status --all``, the hosted readiness chain and the
rollout callback) was removed from open-core together with the hosted tracker
transport (#6164). These tests cover the surviving local providers (beads, fp):
bind, providers, status, map add/list, and sync pull/push/run/publish.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.tracker.service import TrackerServiceError
from tests._support.ansi import strip_ansi

pytestmark = pytest.mark.fast

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app() -> typer.Typer:
    """Return the tracker Typer app."""
    from specify_cli.cli.commands import tracker as tracker_module

    return tracker_module.app


# ---------------------------------------------------------------------------
# bind: removed providers hard-fail (azure_devops + the former SaaS providers)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", ["azure_devops", "linear", "jira", "github", "gitlab"])
def test_bind_removed_provider_hard_fail(provider, monkeypatch) -> None:
    """Binding a removed provider hard-fails with 'no longer supported' and exit 1."""
    app = _make_app()

    result = runner.invoke(app, ["bind", "--provider", provider, "--workspace", "w"])
    assert result.exit_code == 1
    assert "no longer supported" in result.output


# ---------------------------------------------------------------------------
# bind: local provider with --workspace --credential
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_bind_local_provider(mock_service_fn, monkeypatch) -> None:
    """Local bind with --workspace and --credential dispatches correctly."""
    app = _make_app()
    mock_svc = MagicMock()
    mock_config = MagicMock()
    mock_config.provider = "beads"
    mock_config.workspace = "w"
    mock_config.ownership_mode = "external_authoritative"
    mock_config.ownership_field_owners = {}
    mock_svc.bind.return_value = mock_config
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(
        app,
        [
            "bind",
            "--provider",
            "beads",
            "--workspace",
            "w",
            "--credential",
            "command=beads",
        ],
    )
    assert result.exit_code == 0
    mock_svc.bind.assert_called_once()
    call_kwargs = mock_svc.bind.call_args[1]
    assert call_kwargs["provider"] == "beads"
    assert call_kwargs["workspace"] == "w"
    assert call_kwargs["credentials"] == {"command": "beads"}
    assert "Tracker binding saved" in result.output


# ---------------------------------------------------------------------------
# bind: --ownership-mode is the only ownership flag (CR-03; the --doctrine-mode
# alias was deleted by mission charter-pack-cutover-01M491G6, FR-011)
# ---------------------------------------------------------------------------


def _bind_mocks(mock_service_fn: MagicMock) -> MagicMock:
    mock_svc = MagicMock()
    mock_config = MagicMock()
    mock_config.provider = "beads"
    mock_config.workspace = "w"
    mock_config.ownership_mode = "split_ownership"
    mock_config.ownership_field_owners = {}
    mock_svc.bind.return_value = mock_config
    mock_service_fn.return_value = mock_svc
    return mock_svc


@patch("specify_cli.cli.commands.tracker._service")
def test_tracker_ownership_mode_canonical(mock_service_fn, monkeypatch) -> None:
    """The canonical ``--ownership-mode`` flag passes its value straight
    through to ``LocalTrackerService.bind``."""
    app = _make_app()
    mock_svc = _bind_mocks(mock_service_fn)

    result = runner.invoke(app, ["bind", "--provider", "beads", "--workspace", "w", "--ownership-mode", "split_ownership"])

    assert result.exit_code == 0, result.output
    assert mock_svc.bind.call_args[1]["ownership_mode"] == "split_ownership"
    assert "ownership_mode: split_ownership" in result.output


@patch("specify_cli.cli.commands.tracker._service")
def test_tracker_doctrine_mode_is_an_unknown_option(mock_service_fn, monkeypatch) -> None:
    """``--doctrine-mode`` is gone: an unknown option (exit 2), nothing is bound."""
    app = _make_app()
    mock_svc = _bind_mocks(mock_service_fn)

    result = runner.invoke(app, ["bind", "--provider", "beads", "--workspace", "w", "--doctrine-mode", "split_ownership"])

    assert result.exit_code == 2, result.output
    assert "--doctrine-mode" in strip_ansi(result.output)
    mock_svc.bind.assert_not_called()


# ---------------------------------------------------------------------------
# bind: local provider missing --workspace
# ---------------------------------------------------------------------------


def test_bind_local_provider_missing_workspace(monkeypatch) -> None:
    """Local bind without --workspace must hard-fail."""
    app = _make_app()

    result = runner.invoke(app, ["bind", "--provider", "beads"])
    assert result.exit_code == 1
    assert "--workspace is required" in result.output


# ---------------------------------------------------------------------------
# providers: categorized list (Local vs Removed)
# ---------------------------------------------------------------------------


def test_providers_list(monkeypatch) -> None:
    """Providers command shows local providers and the removed ones."""
    app = _make_app()

    result = runner.invoke(app, ["providers"])
    assert result.exit_code == 0
    assert "Local" in result.output
    assert "Removed" in result.output
    for p in ("beads", "fp"):
        assert p in result.output
    # The former SaaS providers are now listed as removed, alongside azure_devops.
    for p in ("github", "gitlab", "jira", "linear", "azure_devops"):
        assert p in result.output


def test_providers_json(monkeypatch) -> None:
    """Providers --json returns structured JSON with local + removed categories."""
    app = _make_app()

    result = runner.invoke(app, ["providers", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "local" in data
    assert "removed" in data
    assert "saas" not in data
    assert "beads" in data["local"]
    assert "linear" in data["removed"]
    assert "azure_devops" in data["removed"]


# ---------------------------------------------------------------------------
# sync pull: JSON output
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_sync_pull_json(mock_service_fn, monkeypatch) -> None:
    """sync pull --json outputs the raw result dict."""
    app = _make_app()
    mock_svc = MagicMock()
    mock_svc.sync_pull.return_value = {
        "provider": "beads",
        "stats": {"pulled_created": 10, "pulled_updated": 0, "skipped": 0},
        "conflicts": [],
        "errors": [],
    }
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["sync", "pull", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["provider"] == "beads"
    assert data["stats"]["pulled_created"] == 10


# ---------------------------------------------------------------------------
# sync push: local provider path
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_sync_push_local_uses_limit(mock_service_fn, monkeypatch) -> None:
    """Local push passes the limit kwarg."""
    app = _make_app()
    mock_svc = MagicMock()
    mock_svc.sync_push.return_value = {
        "provider": "beads",
        "stats": {"pushed_created": 2, "pushed_updated": 0, "skipped": 0},
        "conflicts": [],
        "errors": [],
    }
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["sync", "push", "--limit", "50"])
    assert result.exit_code == 0
    mock_svc.sync_push.assert_called_once_with(limit=50)


@patch("specify_cli.cli.commands.tracker._service")
def test_sync_push_json(mock_service_fn, monkeypatch) -> None:
    """sync push --json outputs the raw result dict (local provider path)."""
    app = _make_app()
    mock_svc = MagicMock()
    mock_svc.sync_push.return_value = {
        "provider": "beads",
        "stats": {"pushed_created": 5, "pushed_updated": 0, "skipped": 0},
        "conflicts": [],
        "errors": [],
    }
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["sync", "push", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["provider"] == "beads"


# ---------------------------------------------------------------------------
# sync run: JSON output
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_sync_run_json(mock_service_fn, monkeypatch) -> None:
    """sync run --json outputs the raw result dict."""
    app = _make_app()
    mock_svc = MagicMock()
    mock_svc.sync_run.return_value = {
        "provider": "beads",
        "stats": {
            "pulled_created": 4,
            "pulled_updated": 0,
            "pushed_created": 4,
            "pushed_updated": 0,
            "skipped": 0,
        },
        "conflicts": [],
        "errors": [],
    }
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["sync", "run", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["provider"] == "beads"


# ---------------------------------------------------------------------------
# sync publish: local providers have no snapshot transport
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_sync_publish_local_unsupported(mock_service_fn, monkeypatch) -> None:
    """A local provider's publish error is rendered cleanly and exits 1."""
    app = _make_app()
    mock_svc = MagicMock()
    mock_svc.sync_publish.side_effect = TrackerServiceError("Snapshot publish is not supported for local providers (beads/fp).")
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["sync", "publish"])
    assert result.exit_code == 1
    assert "not supported for local providers" in result.output


# ---------------------------------------------------------------------------
# a repo that still carries a binding to a removed provider can leave it
# ---------------------------------------------------------------------------


@pytest.fixture
def linear_bound_repo(tmp_path, monkeypatch):
    """A repo whose .kittify/config.yaml still binds the removed ``linear`` provider."""
    from specify_cli.tracker.config import TrackerProjectConfig, save_tracker_config

    save_tracker_config(tmp_path, TrackerProjectConfig(provider="linear", workspace="org/proj"))
    monkeypatch.setattr("specify_cli.cli.commands.tracker.require_repo_root", lambda: tmp_path)
    return tmp_path


def test_removed_provider_binding_can_be_inspected_and_unbound(linear_bound_repo) -> None:
    from specify_cli.tracker.config import load_tracker_config

    app = _make_app()

    status = runner.invoke(app, ["status"])
    assert status.exit_code == 0, status.output
    out = strip_ansi(status.output)
    assert "removed provider 'linear'" in out
    assert "tracker unbind" in out

    # Other commands keep refusing, and the refusal names the way out.
    refused = runner.invoke(app, ["map", "list"])
    assert refused.exit_code == 1
    assert "tracker unbind" in strip_ansi(refused.output)

    unbound = runner.invoke(app, ["unbind"])
    assert unbound.exit_code == 0, unbound.output
    assert load_tracker_config(linear_bound_repo).provider is None


# ---------------------------------------------------------------------------
# status: dispatches through facade (local rendering)
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_status_command(mock_service_fn, monkeypatch) -> None:
    """Status command dispatches through the facade and renders local fields."""
    app = _make_app()
    mock_svc = MagicMock()
    mock_svc.status.return_value = {
        "configured": True,
        "provider": "beads",
        "workspace": "local-ws",
        "ownership_mode": "external_authoritative",
        "db_path": "local-ws/tracker.db",  # #6164: no shared /tmp literal in the test corpus
        "issue_count": 3,
        "mapping_count": 1,
        "credentials_present": True,
    }
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "beads" in result.output
    assert "local-ws" in result.output


@patch("specify_cli.cli.commands.tracker._service")
def test_status_not_configured(mock_service_fn, monkeypatch) -> None:
    """Status with no binding reports 'not configured'."""
    app = _make_app()
    mock_svc = MagicMock()
    mock_svc.status.return_value = {"configured": False, "provider": None}
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "not configured" in result.output.lower()


@patch("specify_cli.cli.commands.tracker._service")
def test_status_json(mock_service_fn, monkeypatch) -> None:
    """Status --json outputs the raw dict."""
    app = _make_app()
    mock_svc = MagicMock()
    mock_svc.status.return_value = {
        "configured": True,
        "provider": "beads",
    }
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["provider"] == "beads"


# ---------------------------------------------------------------------------
# map add / map list: dispatch through facade
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_map_add_dispatches(mock_service_fn, monkeypatch) -> None:
    """map add dispatches through the facade."""
    app = _make_app()
    mock_svc = MagicMock()
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(
        app,
        [
            "map",
            "add",
            "--wp-id",
            "WP01",
            "--external-id",
            "123",
        ],
    )
    assert result.exit_code == 0
    mock_svc.map_add.assert_called_once()


@patch("specify_cli.cli.commands.tracker._service")
def test_map_list_dispatches(mock_service_fn, monkeypatch) -> None:
    """map list dispatches through the facade."""
    app = _make_app()
    mock_svc = MagicMock()
    mock_svc.map_list.return_value = [
        {"wp_id": "WP01", "external_id": "123", "external_key": "PROJ-1", "system": "beads"},
    ]
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["map", "list"])
    assert result.exit_code == 0
    assert "WP01" in result.output


@patch("specify_cli.cli.commands.tracker._service")
def test_map_list_json(mock_service_fn, monkeypatch) -> None:
    """map list --json outputs the mappings array."""
    app = _make_app()
    mock_svc = MagicMock()
    mock_svc.map_list.return_value = [{"wp_id": "WP01", "external_id": "123"}]
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["map", "list", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["mappings"][0]["wp_id"] == "WP01"
