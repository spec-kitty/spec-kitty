"""Scope: mock-boundary tests for tracker command registration, gating, and dispatch -- no real git."""

from __future__ import annotations

import importlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.tracker.saas_readiness import ReadinessResult, ReadinessState
from specify_cli.tracker.config import TrackerProjectConfig
from tests._support.ansi import strip_ansi
from specify_cli.tracker.discovery import BindCandidate, BindResult, ResolutionResult
from specify_cli.tracker.service import TrackerServiceError

pytestmark = pytest.mark.fast

runner = CliRunner()


# ---------------------------------------------------------------------------
# Autouse fixture: stub _check_readiness for all existing tests.
#
# New tests that want to exercise the real readiness dispatch use
# ``@pytest.mark.no_readiness_stub`` (or just patch things directly).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_check_readiness(request, monkeypatch):
    """Make _check_readiness a no-op for all tests unless marked otherwise.

    This preserves backward compatibility with existing tests that don't
    care about the readiness path.  Tests that explicitly test readiness
    should mark themselves with ``no_readiness_stub`` or use their own stubs.
    """
    # #3108 / PR #3135 HIGH-1: `_check_sync_readiness` now consults the hosted
    # `tracker_egress_verdict` before the readiness probe. These mock-boundary
    # tests mock `_service()` (bypassing the transport-layer gate) and carry no
    # recorded consent, so the real gate would refuse. Stub it to permit for
    # *every* test in this file — including `no_readiness_stub` ones, which
    # drive `_check_sync_readiness` directly — because egress consent is out of
    # scope here (it has its own suite under `tests/tracker/`); this file
    # asserts command dispatch/rendering only.
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker.tracker_egress_verdict",
        lambda *args, **kwargs: SimpleNamespace(refused=False),
    )
    if "no_readiness_stub" in {m.name for m in request.node.iter_markers()}:
        return
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker._check_readiness",
        lambda *, require_mission_binding, probe_reachability: None,
    )


def _build_root_app(*, enabled: bool, monkeypatch) -> typer.Typer:
    if enabled:
        monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    else:
        monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")

    import specify_cli.cli.commands as commands_module

    commands_module = importlib.reload(commands_module)
    app = typer.Typer()
    commands_module.register_commands(app)
    return app


# ---------------------------------------------------------------------------
# Feature flag gating tests (pre-existing)
# ---------------------------------------------------------------------------


def test_tracker_registered_when_flag_enabled(monkeypatch) -> None:
    """Tracker sub-command appears in help when SAAS_SYNC flag is on.

    ``issue-search`` is a hosted surface (ADR 2026-10-06-1): registered and
    runnable, but left out of the default root listing.
    """
    app = _build_root_app(enabled=True, monkeypatch=monkeypatch)
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "tracker" in result.output
    assert "issue-search" not in result.output
    assert runner.invoke(app, ["issue-search", "--help"]).exit_code == 0


def test_tracker_direct_invocation_fails_when_flag_disabled(monkeypatch) -> None:
    """Direct tracker invocation exits with code 1 and a flag-disabled message."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")

    from specify_cli.cli.commands import tracker as tracker_module

    result = runner.invoke(tracker_module.app, ["providers"])
    assert result.exit_code == 1
    assert "Hosted SaaS sync is disabled" in result.output


# ---------------------------------------------------------------------------
# Helpers for command-level tests
# ---------------------------------------------------------------------------


def _make_app(monkeypatch) -> typer.Typer:
    """Return the tracker app with the feature flag enabled."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    from specify_cli.cli.commands import tracker as tracker_module

    return tracker_module.app


def _mock_identity():
    """Return a mock ProjectIdentity for ensure_identity patches."""
    identity = MagicMock()
    identity.project_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    identity.project_slug = "test-project"
    identity.node_id = "abc123def456"
    identity.repo_slug = "owner/repo"
    return identity


def _make_bind_result(
    *,
    provider: str = "linear",
    binding_ref: str = "br_abc123",
    display_label: str = "My Linear Team",
) -> BindResult:
    return BindResult(
        binding_ref=binding_ref,
        display_label=display_label,
        provider=provider,
        provider_context={},
        bound_at="2026-04-04T12:00:00Z",
    )


def _make_tracker_config(
    *,
    provider: str = "linear",
    binding_ref: str = "br_abc123",
    display_label: str = "My Linear Team",
) -> TrackerProjectConfig:
    return TrackerProjectConfig(
        provider=provider,
        binding_ref=binding_ref,
        display_label=display_label,
    )


def _make_candidates_resolution() -> ResolutionResult:
    return ResolutionResult(
        match_type="candidates",
        candidates=[
            BindCandidate(
                candidate_token="tok_1",
                display_label="Team Alpha",
                confidence="high",
                match_reason="Name matches repository slug",
                sort_position=0,
            ),
            BindCandidate(
                candidate_token="tok_2",
                display_label="Team Beta",
                confidence="medium",
                match_reason="Partial slug overlap",
                sort_position=1,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# bind: --project-slug is no longer accepted for SaaS
# ---------------------------------------------------------------------------


def test_bind_no_project_slug_flag(monkeypatch) -> None:
    """--project-slug is not accepted by bind command."""
    app = _make_app(monkeypatch)

    result = runner.invoke(app, ["bind", "--provider", "linear", "--project-slug", "my-proj"])
    # typer rejects unknown options with exit code 2
    assert result.exit_code == 2
    assert "project-slug" in result.output.lower() or "no such option" in result.output.lower()


# ---------------------------------------------------------------------------
# bind: SaaS provider --credential hard-fail
# ---------------------------------------------------------------------------


def test_bind_saas_provider_credential_hard_fail(monkeypatch) -> None:
    """SaaS bind with --credential must hard-fail with dashboard guidance."""
    app = _make_app(monkeypatch)

    result = runner.invoke(
        app,
        [
            "bind",
            "--provider",
            "linear",
            "--credential",
            "api_key=xxx",
        ],
    )
    assert result.exit_code == 1
    assert "Direct provider credentials are no longer supported for linear" in result.output
    assert "spec-kitty auth login" in result.output
    assert "dashboard" in result.output.lower()


# ---------------------------------------------------------------------------
# bind: Azure DevOps hard-fail
# ---------------------------------------------------------------------------


def test_bind_azure_devops_hard_fail(monkeypatch) -> None:
    """Azure DevOps bind must hard-fail with 'no longer supported' message."""
    app = _make_app(monkeypatch)

    result = runner.invoke(app, ["bind", "--provider", "azure_devops", "--workspace", "w"])
    assert result.exit_code == 1
    assert "no longer supported" in result.output


# ---------------------------------------------------------------------------
# bind: SaaS discovery auto-bind (exact match)
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
@patch("specify_cli.cli.commands.tracker.ensure_identity")
@patch("specify_cli.cli.commands.tracker.load_tracker_config")
def test_bind_auto_bind(
    mock_load_cfg,
    mock_ensure_id,
    mock_service_fn,
    monkeypatch,
) -> None:
    """SaaS bind with exact match auto-binds and shows success."""
    app = _make_app(monkeypatch)
    mock_ensure_id.return_value = _mock_identity()
    mock_load_cfg.return_value = TrackerProjectConfig()  # no existing binding
    mock_svc = MagicMock()
    mock_svc.bind.return_value = _make_bind_result()
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["bind", "--provider", "linear"])
    assert result.exit_code == 0, result.output
    assert "Tracker binding saved" in result.output
    assert "br_abc123" in result.output
    assert "My Linear Team" in result.output


# ---------------------------------------------------------------------------
# bind: SaaS discovery with candidates (interactive)
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
@patch("specify_cli.cli.commands.tracker.ensure_identity")
@patch("specify_cli.cli.commands.tracker.load_tracker_config")
@patch("builtins.input")
def test_bind_candidates_interactive(
    mock_input,
    mock_load_cfg,
    mock_ensure_id,
    mock_service_fn,
    monkeypatch,
) -> None:
    """SaaS bind with candidates prompts user and binds selection."""
    app = _make_app(monkeypatch)
    mock_ensure_id.return_value = _mock_identity()
    mock_load_cfg.return_value = TrackerProjectConfig()
    mock_svc = MagicMock()
    # First call returns candidates, second call returns BindResult
    mock_svc.bind.side_effect = [
        _make_candidates_resolution(),
        _make_bind_result(display_label="Team Beta"),
    ]
    mock_service_fn.return_value = mock_svc
    mock_input.return_value = "2"  # Select second candidate

    result = runner.invoke(app, ["bind", "--provider", "linear"])
    assert result.exit_code == 0, result.output
    assert "Multiple resources found" in result.output
    assert "Team Alpha" in result.output
    assert "Team Beta" in result.output
    assert "Tracker binding saved" in result.output

    # Verify the second bind call included select_n=2
    assert mock_svc.bind.call_count == 2
    second_call = mock_svc.bind.call_args_list[1]
    assert second_call[1]["select_n"] == 2


# ---------------------------------------------------------------------------
# bind: SaaS no candidates
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
@patch("specify_cli.cli.commands.tracker.ensure_identity")
@patch("specify_cli.cli.commands.tracker.load_tracker_config")
def test_bind_no_candidates(
    mock_load_cfg,
    mock_ensure_id,
    mock_service_fn,
    monkeypatch,
) -> None:
    """SaaS bind with no match raises error with exit 1."""
    app = _make_app(monkeypatch)
    mock_ensure_id.return_value = _mock_identity()
    mock_load_cfg.return_value = TrackerProjectConfig()
    mock_svc = MagicMock()
    mock_svc.bind.side_effect = TrackerServiceError("No bindable resources found for provider 'linear'.")
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["bind", "--provider", "linear"])
    assert result.exit_code == 1
    assert "No bindable resources" in result.output


# ---------------------------------------------------------------------------
# bind: --bind-ref valid
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
@patch("specify_cli.cli.commands.tracker.ensure_identity")
def test_bind_ref_valid(mock_ensure_id, mock_service_fn, monkeypatch) -> None:
    """--bind-ref with valid ref persists binding and shows success."""
    app = _make_app(monkeypatch)
    mock_ensure_id.return_value = _mock_identity()
    mock_svc = MagicMock()
    mock_svc.bind.return_value = _make_tracker_config(binding_ref="br_known_ref")
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["bind", "--provider", "linear", "--bind-ref", "br_known_ref"])
    assert result.exit_code == 0, result.output
    assert "Tracker binding saved" in result.output
    assert "br_known_ref" in result.output

    # Verify bind was called with bind_ref
    call_kwargs = mock_svc.bind.call_args[1]
    assert call_kwargs["bind_ref"] == "br_known_ref"


# ---------------------------------------------------------------------------
# bind: --bind-ref invalid
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
@patch("specify_cli.cli.commands.tracker.ensure_identity")
def test_bind_ref_invalid(mock_ensure_id, mock_service_fn, monkeypatch) -> None:
    """--bind-ref with invalid ref shows error and exits 1."""
    app = _make_app(monkeypatch)
    mock_ensure_id.return_value = _mock_identity()
    mock_svc = MagicMock()
    mock_svc.bind.side_effect = TrackerServiceError("Binding ref 'br_bad' is not valid: deleted on host.")
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["bind", "--provider", "linear", "--bind-ref", "br_bad"])
    assert result.exit_code == 1
    assert "not valid" in result.output


# ---------------------------------------------------------------------------
# bind: --select N valid
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
@patch("specify_cli.cli.commands.tracker.ensure_identity")
@patch("specify_cli.cli.commands.tracker.load_tracker_config")
def test_bind_select_n(
    mock_load_cfg,
    mock_ensure_id,
    mock_service_fn,
    monkeypatch,
) -> None:
    """--select 1 auto-selects candidate without prompts."""
    app = _make_app(monkeypatch)
    mock_ensure_id.return_value = _mock_identity()
    mock_load_cfg.return_value = TrackerProjectConfig()
    mock_svc = MagicMock()
    mock_svc.bind.return_value = _make_bind_result(display_label="Team Alpha")
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["bind", "--provider", "linear", "--select", "1"])
    assert result.exit_code == 0, result.output
    assert "Tracker binding saved" in result.output
    assert "Team Alpha" in result.output

    # Verify select_n was passed
    call_kwargs = mock_svc.bind.call_args[1]
    assert call_kwargs["select_n"] == 1


# ---------------------------------------------------------------------------
# bind: --select N out of range
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
@patch("specify_cli.cli.commands.tracker.ensure_identity")
@patch("specify_cli.cli.commands.tracker.load_tracker_config")
def test_bind_select_out_of_range(
    mock_load_cfg,
    mock_ensure_id,
    mock_service_fn,
    monkeypatch,
) -> None:
    """--select 99 with out-of-range selection shows error and exits 1."""
    app = _make_app(monkeypatch)
    mock_ensure_id.return_value = _mock_identity()
    mock_load_cfg.return_value = TrackerProjectConfig()
    mock_svc = MagicMock()
    mock_svc.bind.side_effect = TrackerServiceError("Selection 99 is out of range. Valid range: 1-2.")
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["bind", "--provider", "linear", "--select", "99"])
    assert result.exit_code == 1
    assert "out of range" in result.output


# ---------------------------------------------------------------------------
# bind: re-bind confirmed
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
@patch("specify_cli.cli.commands.tracker.ensure_identity")
@patch("specify_cli.cli.commands.tracker.load_tracker_config")
@patch("builtins.input")
def test_bind_rebind_confirmed(
    mock_input,
    mock_load_cfg,
    mock_ensure_id,
    mock_service_fn,
    monkeypatch,
) -> None:
    """Re-bind with existing binding: user confirms 'y' -> proceeds."""
    app = _make_app(monkeypatch)
    mock_ensure_id.return_value = _mock_identity()
    mock_load_cfg.return_value = TrackerProjectConfig(
        provider="linear",
        binding_ref="br_old",
        display_label="Old Team",
    )
    mock_svc = MagicMock()
    mock_svc.bind.return_value = _make_bind_result(display_label="New Team")
    mock_service_fn.return_value = mock_svc
    mock_input.return_value = "y"

    result = runner.invoke(app, ["bind", "--provider", "linear"])
    assert result.exit_code == 0, result.output
    assert "Existing binding" in result.output
    assert "Tracker binding saved" in result.output


# ---------------------------------------------------------------------------
# bind: re-bind cancelled
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
@patch("specify_cli.cli.commands.tracker.ensure_identity")
@patch("specify_cli.cli.commands.tracker.load_tracker_config")
@patch("builtins.input")
def test_bind_rebind_cancelled(
    mock_input,
    mock_load_cfg,
    mock_ensure_id,
    mock_service_fn,
    monkeypatch,
) -> None:
    """Re-bind with existing binding: user declines -> exit 0, no bind."""
    app = _make_app(monkeypatch)
    mock_ensure_id.return_value = _mock_identity()
    mock_load_cfg.return_value = TrackerProjectConfig(
        provider="linear",
        binding_ref="br_old",
        display_label="Old Team",
    )
    mock_svc = MagicMock()
    mock_service_fn.return_value = mock_svc
    mock_input.return_value = "n"

    result = runner.invoke(app, ["bind", "--provider", "linear"])
    assert result.exit_code == 0
    assert "Bind cancelled" in result.output
    mock_svc.bind.assert_not_called()


# ---------------------------------------------------------------------------
# bind: local provider with --workspace --credential
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_bind_local_provider(mock_service_fn, monkeypatch) -> None:
    """Local bind with --workspace and --credential dispatches correctly."""
    app = _make_app(monkeypatch)
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
    app = _make_app(monkeypatch)
    mock_svc = _bind_mocks(mock_service_fn)

    result = runner.invoke(app, ["bind", "--provider", "beads", "--workspace", "w", "--ownership-mode", "split_ownership"])

    assert result.exit_code == 0, result.output
    assert mock_svc.bind.call_args[1]["ownership_mode"] == "split_ownership"
    assert "ownership_mode: split_ownership" in result.output


@patch("specify_cli.cli.commands.tracker._service")
def test_tracker_doctrine_mode_is_an_unknown_option(mock_service_fn, monkeypatch) -> None:
    """``--doctrine-mode`` is gone: an unknown option (exit 2), nothing is bound."""
    app = _make_app(monkeypatch)
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
    app = _make_app(monkeypatch)

    result = runner.invoke(app, ["bind", "--provider", "beads"])
    assert result.exit_code == 1
    assert "--workspace is required" in result.output


# ---------------------------------------------------------------------------
# providers: categorized list (SaaS vs Local)
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_providers_list(mock_service_fn, monkeypatch) -> None:
    """Providers command shows SaaS and local, no azure_devops."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["providers"])
    assert result.exit_code == 0
    assert "SaaS-backed" in result.output
    assert "Local" in result.output
    for p in ("github", "gitlab", "jira", "linear"):
        assert p in result.output
    for p in ("beads", "fp"):
        assert p in result.output
    assert "azure_devops" not in result.output


# ---------------------------------------------------------------------------
# providers: JSON output
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_providers_json(mock_service_fn, monkeypatch) -> None:
    """Providers --json returns structured JSON with categorization."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["providers", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "saas" in data
    assert "local" in data
    assert "linear" in data["saas"]
    assert "beads" in data["local"]


# ---------------------------------------------------------------------------
# sync pull: JSON output for SaaS envelope
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_sync_pull_json(mock_service_fn, monkeypatch) -> None:
    """sync pull --json outputs the raw envelope dict."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.sync_pull.return_value = {
        "status": "complete",
        "identity_path": {"type": "saas", "provider": "linear"},
        "summary": {"total": 10, "succeeded": 9, "failed": 1, "skipped": 0},
        "items": [],
    }
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["sync", "pull", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "complete"
    assert data["summary"]["total"] == 10


# ---------------------------------------------------------------------------
# sync push: JSON output for SaaS envelope
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker.require_repo_root")
@patch("specify_cli.cli.commands.tracker.load_tracker_config")
@patch("specify_cli.cli.commands.tracker._service")
def test_sync_push_saas_with_items_json(mock_service_fn, mock_load_cfg, mock_repo_root, monkeypatch, tmp_path) -> None:
    """SaaS push with --items-json sends items to the service."""
    from specify_cli.tracker.config import TrackerProjectConfig

    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.sync_push.return_value = {
        "status": "ok",
        "summary": {"total": 1, "succeeded": 1, "failed": 0, "skipped": 0},
    }
    mock_service_fn.return_value = mock_svc
    mock_load_cfg.return_value = TrackerProjectConfig(provider="linear", project_slug="proj")
    mock_repo_root.return_value = tmp_path

    items_file = tmp_path / "items.json"
    items_file.write_text('[{"ref": {"system": "linear", "id": "LIN-1", "workspace": "team"}, "action": "update"}]')

    result = runner.invoke(app, ["sync", "push", "--items-json", str(items_file), "--json"])
    assert result.exit_code == 0, result.output
    mock_svc.sync_push.assert_called_once()
    call_kwargs = mock_svc.sync_push.call_args[1]
    assert len(call_kwargs["items"]) == 1
    assert call_kwargs["items"][0]["action"] == "update"


@patch("specify_cli.cli.commands.tracker.require_repo_root")
@patch("specify_cli.cli.commands.tracker.load_tracker_config")
@patch("specify_cli.cli.commands.tracker._service")
def test_sync_push_saas_requires_items_json(mock_service_fn, mock_load_cfg, mock_repo_root, monkeypatch, tmp_path) -> None:
    """SaaS push without --items-json fails with clear guidance."""
    from specify_cli.tracker.config import TrackerProjectConfig

    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_service_fn.return_value = mock_svc
    mock_load_cfg.return_value = TrackerProjectConfig(provider="jira", project_slug="proj")
    mock_repo_root.return_value = tmp_path

    result = runner.invoke(app, ["sync", "push"])
    assert result.exit_code == 1
    assert "--items-json is required" in result.output
    assert "tracker sync run" in result.output
    # Verify sync_push was never called (we errored before reaching it)
    mock_svc.sync_push.assert_not_called()


@patch("specify_cli.cli.commands.tracker._service")
def test_sync_push_local_uses_limit(mock_service_fn, monkeypatch) -> None:
    """Local push passes limit kwarg (not items)."""
    app = _make_app(monkeypatch)
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
    """sync push --json outputs the raw envelope dict (local provider path)."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.sync_push.return_value = {
        "status": "complete",
        "summary": {"total": 5, "succeeded": 5, "failed": 0, "skipped": 0},
    }
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["sync", "push", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "complete"


@patch("specify_cli.cli.commands.tracker.require_repo_root")
@patch("specify_cli.cli.commands.tracker.load_tracker_config")
@patch("specify_cli.cli.commands.tracker._service")
def test_sync_push_saas_human_output_includes_identity_path(mock_service_fn, mock_load_cfg, mock_repo_root, monkeypatch, tmp_path) -> None:
    """sync push human output shows identity_path (#1221), matching sync pull."""
    from specify_cli.tracker.config import TrackerProjectConfig

    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.sync_push.return_value = {
        "status": "complete",
        "identity_path": {"type": "user_link", "provider": "linear"},
        "summary": {"total": 1, "succeeded": 1, "failed": 0, "skipped": 0},
    }
    mock_service_fn.return_value = mock_svc
    mock_load_cfg.return_value = TrackerProjectConfig(provider="linear", project_slug="proj")
    mock_repo_root.return_value = tmp_path

    items_file = tmp_path / "items.json"
    items_file.write_text('[{"ref": {"system": "linear", "id": "LIN-1", "workspace": "team"}, "action": "update"}]')

    result = runner.invoke(app, ["sync", "push", "--items-json", str(items_file)])
    assert result.exit_code == 0, result.output
    assert "- provider: linear" in result.output
    assert "- type: user_link" in result.output


# ---------------------------------------------------------------------------
# sync run: JSON output
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_sync_run_json(mock_service_fn, monkeypatch) -> None:
    """sync run --json outputs the raw envelope dict."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.sync_run.return_value = {
        "status": "complete",
        "summary": {"total": 8, "succeeded": 8, "failed": 0, "skipped": 0},
    }
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["sync", "run", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "complete"


@patch("specify_cli.cli.commands.tracker._service")
def test_sync_run_saas_human_output_includes_identity_path(mock_service_fn, monkeypatch) -> None:
    """sync run human output shows identity_path (#1221), matching sync pull."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.sync_run.return_value = {
        "status": "complete",
        "identity_path": {"type": "installation", "provider": "linear"},
        "summary": {"total": 8, "succeeded": 8, "failed": 0, "skipped": 0},
    }
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["sync", "run"])
    assert result.exit_code == 0, result.output
    assert "- provider: linear" in result.output
    assert "- type: installation" in result.output


# ---------------------------------------------------------------------------
# status: dispatches through facade
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_status_command(mock_service_fn, monkeypatch) -> None:
    """Status command dispatches through the facade."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.status.return_value = {
        "configured": True,
        "provider": "linear",
        "identity_path": {"type": "saas", "provider": "linear"},
        "sync_state": "idle",
    }
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "linear" in result.output


# ---------------------------------------------------------------------------
# status: JSON output
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_status_json(mock_service_fn, monkeypatch) -> None:
    """Status --json outputs the raw dict."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.status.return_value = {
        "configured": True,
        "provider": "linear",
    }
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["provider"] == "linear"


# ---------------------------------------------------------------------------
# map add: hard-fail for SaaS is handled by service
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_map_add_dispatches(mock_service_fn, monkeypatch) -> None:
    """map add dispatches through the facade."""
    app = _make_app(monkeypatch)
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


# ---------------------------------------------------------------------------
# map list: dispatches through facade
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.tracker._service")
def test_map_list_dispatches(mock_service_fn, monkeypatch) -> None:
    """map list dispatches through the facade."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.map_list.return_value = [
        {"wp_id": "WP01", "external_id": "123", "external_key": "PROJ-1", "system": "linear"},
    ]
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["map", "list"])
    assert result.exit_code == 0
    assert "WP01" in result.output


@patch("specify_cli.cli.commands.tracker._service")
def test_map_list_with_provider_dispatches_without_bound_repo(mock_service_fn, monkeypatch) -> None:
    """map list --provider uses the provider-scoped service path."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.map_list.return_value = [{"wp_id": "WP01", "external_id": "123"}]
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(app, ["map", "list", "--provider", "linear", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["mappings"][0]["wp_id"] == "WP01"
    mock_service_fn.assert_called_once_with(allow_unbound=True)
    mock_svc.map_list.assert_called_once_with(provider="linear")


@patch("specify_cli.cli.commands.tracker._service")
def test_issue_search_root_dispatches(mock_service_fn, monkeypatch) -> None:
    """issue-search dispatches through the tracker service and returns JSON array."""
    app = _build_root_app(enabled=True, monkeypatch=monkeypatch)
    mock_svc = MagicMock()
    mock_svc.issue_search.return_value = [
        {
            "identifier": "PRI-17",
            "title": "Wire hosted tracker reads",
            "url": "https://linear.app/priivacy/issue/PRI-17",
            "state": {"name": "todo"},
            "team": {"key": "PRI"},
            "assignee": None,
            "created_at": None,
            "updated_at": None,
            "body": "body",
        }
    ]
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(
        app,
        ["issue-search", "--provider", "linear", "--query", "PRI-17", "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload[0]["identifier"] == "PRI-17"
    mock_service_fn.assert_called_once_with(allow_unbound=True)
    mock_svc.issue_search.assert_called_once_with(provider="linear", query="PRI-17")


@patch("specify_cli.cli.commands.tracker._service")
def test_list_tickets_dispatches(mock_service_fn, monkeypatch) -> None:
    """tracker list-tickets dispatches through the provider-scoped service path."""
    app = _make_app(monkeypatch)
    mock_svc = MagicMock()
    mock_svc.list_tickets.return_value = [
        {
            "identifier": "PRI-1",
            "title": "First ticket",
            "url": "https://linear.app/priivacy/issue/PRI-1",
            "state": {"name": "todo"},
            "team": {"key": "PRI"},
            "assignee": None,
            "created_at": None,
            "updated_at": None,
            "body": None,
        }
    ]
    mock_service_fn.return_value = mock_svc

    result = runner.invoke(
        app,
        ["list-tickets", "--provider", "linear", "--limit", "20", "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload[0]["identifier"] == "PRI-1"
    mock_service_fn.assert_called_once_with(allow_unbound=True)
    mock_svc.list_tickets.assert_called_once_with(provider="linear", limit=20)


# ---------------------------------------------------------------------------
# T024: Rollout × readiness matrix tests
# ---------------------------------------------------------------------------


@pytest.mark.no_readiness_stub
def test_tracker_visible_when_rollout_enabled_root_app(monkeypatch) -> None:
    """Tracker sub-command appears in root app help when rollout is on."""
    app = _build_root_app(enabled=True, monkeypatch=monkeypatch)
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "tracker" in result.output


@pytest.mark.no_readiness_stub
def test_providers_ignores_hosted_readiness(monkeypatch) -> None:
    """`tracker providers` is static informational output.

    It must run successfully even when hosted readiness would otherwise
    fail (e.g. no auth token, no SaaS host config).  The rollout gate is
    enforced solely by ``tracker_callback()``, while the per-command readiness
    chain is deliberately NOT consulted for this command.
    """
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    from specify_cli.cli.commands import tracker as tracker_module

    # Set a trip-wire: if any code path called evaluate_readiness,
    # the command would exit 1 with this failing state.  The fact that
    # the command exits 0 is the proof that readiness is no longer
    # consulted.
    trip_wire = ReadinessResult(
        state=ReadinessState.MISSING_AUTH,
        message="tripwire: readiness should not be consulted by providers",
        next_action="Do not run readiness for providers.",
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker.evaluate_readiness",
        lambda **_kwargs: trip_wire,
    )

    result = runner.invoke(tracker_module.app, ["providers"])
    assert result.exit_code == 0, result.output
    assert "tripwire" not in result.output
    assert "Supported providers" in result.output
    assert "linear" in result.output  # a SaaS provider
    assert "beads" in result.output  # a local provider


@pytest.mark.no_readiness_stub
def test_providers_still_blocked_when_rollout_disabled(monkeypatch) -> None:
    """When the rollout gate is off, `tracker providers` is unreachable.

    Registration in ``cli/commands/__init__.py`` is unconditional.  This test
    invokes the tracker app object directly with the env var unset to exercise
    the sole rollout gate in ``tracker_callback``.  It verifies that removing
    the per-command readiness call did not accidentally open a hole in that
    gate.
    """
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    from specify_cli.cli.commands import tracker as tracker_module

    result = runner.invoke(tracker_module.app, ["providers"])
    assert result.exit_code == 1
    assert "disabled" in result.output.lower()


@pytest.mark.no_readiness_stub
def test_status_readiness_missing_auth_message(monkeypatch, tmp_path) -> None:
    """status command exits 1 with MISSING_AUTH wording when auth probe fails."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    from specify_cli.cli.commands import tracker as tracker_module
    from specify_cli.tracker.saas_readiness import _WORDING  # noqa: PLC2701

    msg, action = _WORDING[ReadinessState.MISSING_AUTH]
    failing_result = ReadinessResult(
        state=ReadinessState.MISSING_AUTH,
        message=msg,
        next_action=action,
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
    # WS5 (issue #18): force INTERACTIVE policy so the 2-line human wording
    # is rendered under pytest (where stdout is not a TTY → would otherwise
    # default to NON_INTERACTIVE).
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker._resolve_output_policy_for_tracker",
        lambda: "interactive",
    )

    result = runner.invoke(tracker_module.app, ["status"])
    assert result.exit_code == 1
    assert msg in result.output
    assert action in result.output


@pytest.mark.no_readiness_stub
def test_status_readiness_ready_passes_through(monkeypatch, tmp_path) -> None:
    """When readiness is READY, status proceeds to the service call."""
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
    mock_svc.status.return_value = {
        "configured": True,
        "provider": "linear",
        "identity_path": {"type": "saas", "provider": "linear"},
        "sync_state": "idle",
    }

    with patch("specify_cli.cli.commands.tracker._service", return_value=mock_svc):
        result = runner.invoke(tracker_module.app, ["status"])
    assert result.exit_code == 0
    assert "linear" in result.output


# ---------------------------------------------------------------------------
# T024: Manual-mode tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Provider-aware sync readiness (local-provider bypass)
# ---------------------------------------------------------------------------
#
# Local tracker providers (beads, fp) use direct connectors and do not
# interact with the SaaS background daemon or the hosted readiness chain.
# Sync commands for local-provider bindings must NOT trip on manual daemon
# policy, missing auth, missing host config, or reachability failures —
# those are SaaS concerns.  These tests assert that the provider-aware
# helpers in ``tracker.py`` (``_is_local_binding`` and
# ``_check_sync_readiness``) short-circuit correctly.


def _local_binding_config():
    """Return a TrackerProjectConfig that reports a local (beads) binding."""
    from specify_cli.tracker.config import TrackerProjectConfig

    return TrackerProjectConfig(
        provider="beads",
        workspace="local-workspace",
    )


# ---------------------------------------------------------------------------
# Module-level import structural guardrail (RISK-2 from mission review)
# ---------------------------------------------------------------------------


def test_tracker_keeps_readiness_imports_at_module_level() -> None:
    """Structural guardrail: ``evaluate_readiness`` / ``SyncConfig`` must be
    module-level imports on ``specify_cli.cli.commands.tracker``.

    The manual-mode tests in this file and the readiness-failure tests in
    the discover/status modules all patch these names via
    ``monkeypatch.setattr("specify_cli.cli.commands.tracker.<name>", ...)``.
    If a future refactor moves either import back to function-local (e.g.
    to avoid a perceived circular dependency), those patches would silently
    stop applying and every manual-mode / readiness-failure test would
    regress into false passes.  This guardrail fails loudly instead.
    """
    from specify_cli.cli.commands import tracker as tracker_module
    from specify_cli.tracker import saas_readiness as readiness_module

    assert hasattr(tracker_module, "evaluate_readiness"), "tracker.py must import evaluate_readiness at module level so tests can monkeypatch the consumer binding."
    assert tracker_module.evaluate_readiness is readiness_module.evaluate_readiness


# ---------------------------------------------------------------------------
# WS5 (mission tracker-readiness-alignment-01KS7PZ7, issue #18):
# Tracker readiness output is aligned with the central coordinator's
# OutputPolicy buckets. The 6-row test matrix from spec.md is covered below.
# ---------------------------------------------------------------------------


def _ws5_failing_missing_auth_result():
    """Return a synthetic MISSING_AUTH ReadinessResult using the canonical wording."""
    from specify_cli.tracker.saas_readiness import _WORDING  # noqa: PLC2701

    msg, action = _WORDING[ReadinessState.MISSING_AUTH]
    return ReadinessResult(
        state=ReadinessState.MISSING_AUTH,
        message=msg,
        next_action=action,
    )


def _ws5_install_failing_readiness(monkeypatch, tmp_path):
    """Wire the tracker module so ``status`` will land on a MISSING_AUTH render."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker.evaluate_readiness",
        lambda **_kwargs: _ws5_failing_missing_auth_result(),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker.require_repo_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker._resolve_active_feature_slug",
        lambda _repo_root: None,
    )


@pytest.mark.no_readiness_stub
def test_ws5_hosted_no_auth_interactive_two_line_human_format(monkeypatch, tmp_path) -> None:
    """AC#6 row 1: INTERACTIVE policy → 2-line human format unchanged."""
    _ws5_install_failing_readiness(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker._resolve_output_policy_for_tracker",
        lambda: "interactive",
    )

    from specify_cli.cli.commands import tracker as tracker_module
    from specify_cli.tracker.saas_readiness import _WORDING  # noqa: PLC2701

    msg, action = _WORDING[ReadinessState.MISSING_AUTH]
    result = runner.invoke(tracker_module.app, ["status"])
    assert result.exit_code == 1
    assert msg in result.output
    assert action in result.output


@pytest.mark.no_readiness_stub
def test_ws5_hosted_no_auth_machine_output_single_line_stderr(monkeypatch, tmp_path) -> None:
    """AC#6 row 2: MACHINE_OUTPUT (--json/--quiet) → single line stderr, stdout untouched.

    With CliRunner's mixed-output capture we cannot perfectly separate stdout
    from stderr, but we can assert (a) the canonical remediation appears
    exactly once in ``output`` and (b) the long human ``message`` does NOT
    appear (because MACHINE_OUTPUT writes only the next_action line).
    """
    _ws5_install_failing_readiness(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker._resolve_output_policy_for_tracker",
        lambda: "machine_output",
    )

    from specify_cli.cli.commands import tracker as tracker_module
    from specify_cli.tracker.saas_readiness import _WORDING  # noqa: PLC2701

    msg, action = _WORDING[ReadinessState.MISSING_AUTH]
    result = runner.invoke(tracker_module.app, ["status"])

    assert result.exit_code == 1
    # next_action is present (single-line stderr).
    assert action in result.output
    # The long human message is NOT echoed in machine_output mode.
    assert msg not in result.output
    # Single line: exactly one non-empty line in the captured output.
    non_empty_lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(non_empty_lines) == 1, non_empty_lines


@pytest.mark.no_readiness_stub
def test_ws5_hosted_no_auth_non_interactive_stable_machine_line(monkeypatch, tmp_path) -> None:
    """AC#6 row 3: NON_INTERACTIVE → stable single-line machine-readable stderr."""
    _ws5_install_failing_readiness(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker._resolve_output_policy_for_tracker",
        lambda: "non_interactive",
    )

    from specify_cli.cli.commands import tracker as tracker_module

    result = runner.invoke(tracker_module.app, ["status"])
    assert result.exit_code == 1

    expected = "spec-kitty tracker: readiness=missing_auth next=spec-kitty-auth-login"
    assert expected in result.output, result.output
    # Exactly one non-empty line emitted.
    non_empty_lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(non_empty_lines) == 1, non_empty_lines


@pytest.mark.no_readiness_stub
def test_ws5_local_tracker_skips_hosted_readiness_probe(monkeypatch, tmp_path) -> None:
    """AC#3/6: a local binding (``fp``/``beads``) does NOT invoke the hosted readiness probe.

    Drive ``_check_binding_readiness`` directly with ``_is_local_binding``
    forced to True; assert ``evaluate_readiness`` is never called.
    """
    from specify_cli.cli.commands import tracker as tracker_module

    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")

    def _spy_evaluate(**_kwargs):
        raise AssertionError("evaluate_readiness MUST NOT be called for local bindings")

    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker.evaluate_readiness",
        _spy_evaluate,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker._is_local_binding",
        lambda: True,
    )

    # Should return without raising.
    tracker_module._check_binding_readiness(probe_reachability=False)
    tracker_module._check_sync_readiness()


@pytest.mark.no_readiness_stub
def test_ws5_remediation_string_matches_saas_readiness_source(monkeypatch) -> None:
    """AC#2/7: the remediation string is sourced from ``_WORDING`` (single source of truth).

    A regression guardrail: if anyone duplicates a literal ``Run \\`spec-kitty
    auth login\\`.`` string into tracker.py or another module, this test still
    passes — but any drift in the canonical source would immediately surface
    in every test that asserts the rendered output. Asserts the exact byte
    sequence expected by the WS2 auth-recovery probe.
    """
    from specify_cli.tracker.saas_readiness import _WORDING  # noqa: PLC2701

    _msg, action = _WORDING[ReadinessState.MISSING_AUTH]
    assert action == "Run `spec-kitty auth login`."


@pytest.mark.no_readiness_stub
def test_sync_pull_pre_flight_gate_and_transport_share_one_resolved_root(monkeypatch, tmp_path) -> None:
    """#3108 landing hardening: the hosted egress pre-flight and the transport must
    judge the SAME project.

    ``_check_sync_readiness`` consults ``tracker_egress_verdict`` for the hosted
    destination, and the transport (``SaaSTrackerClient._request`` via ``_service``)
    consults it again. If each resolved ``require_repo_root()`` independently, a
    caller whose cwd is not the data-owning root could have the two gates answer for
    two different projects. The four sync commands now resolve the root ONCE and
    thread the same value into both ``_check_sync_readiness(root=...)`` and
    ``_service(root=...)``.

    Red-first: a stateful ``require_repo_root`` that returns a distinct path per call
    makes the pre-fix code feed the gate call #1 and the transport call #2 — two
    different roots. The fix resolves once, so both see the same path.
    """
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    from specify_cli.cli.commands import tracker as tracker_module

    roots = [tmp_path / "p0", tmp_path / "p1", tmp_path / "p2", tmp_path / "p3"]
    for p in roots:
        p.mkdir()
    call_iter = iter(roots)
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker.require_repo_root",
        lambda: next(call_iter),
    )
    # Force the hosted branch (not a local binding) so the pre-flight consults the verdict.
    monkeypatch.setattr("specify_cli.cli.commands.tracker._is_local_binding", lambda: False)
    monkeypatch.setattr(
        "specify_cli.cli.commands.tracker._check_readiness",
        lambda *, require_mission_binding, probe_reachability: None,
    )
    seen: dict[str, object] = {}

    def _record_verdict(root, *, destination, identifiers):
        seen["gate_root"] = root
        return SimpleNamespace(refused=False)

    monkeypatch.setattr("specify_cli.cli.commands.tracker.tracker_egress_verdict", _record_verdict)

    def _fake_service(*, allow_unbound: bool = False, root=None):
        # Mirror the real _service resolution so an unthreaded call (root=None)
        # resolves its OWN require_repo_root() — the exact divergence under test.
        effective = root if root is not None else tracker_module.require_repo_root()
        seen["transport_root"] = effective
        svc = MagicMock()
        svc.sync_pull.return_value = {"stats": {}}
        return svc

    monkeypatch.setattr("specify_cli.cli.commands.tracker._service", _fake_service)

    result = runner.invoke(tracker_module.app, ["sync", "pull"])
    assert result.exit_code == 0, result.output
    assert seen["gate_root"] == seen["transport_root"], (
        f"pre-flight gate judged {seen['gate_root']} but the transport used {seen['transport_root']} — the two hosted gates answered for different projects"
    )
