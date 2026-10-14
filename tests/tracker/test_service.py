"""Tests for TrackerService facade dispatch (local-only after #6164).

The hosted/SaaS providers (linear, jira, github, gitlab) were removed from
open-core together with the hosted tracker surface (#6164); they now resolve as
removed providers. Only the local providers (beads, fp) dispatch to a backend.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.tracker.config import (
    TrackerProjectConfig,
    save_tracker_config,
)
from specify_cli.tracker.service import TrackerService, TrackerServiceError

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# _resolve_backend dispatch tests
# ---------------------------------------------------------------------------


class TestResolveBackendLocal:
    """Local providers dispatch to LocalTrackerService."""

    @pytest.mark.parametrize("provider", ["beads", "fp"])
    def test_local_provider_returns_local_service(self, tmp_path: Path, provider: str) -> None:
        from specify_cli.tracker.local_service import LocalTrackerService

        _setup_config(tmp_path, provider=provider, workspace="my-ws")
        service = TrackerService(tmp_path)
        backend = service._resolve_backend()
        assert isinstance(backend, LocalTrackerService)


class TestResolveBackendRemoved:
    """Removed providers raise immediately -- includes the former SaaS providers."""

    @pytest.mark.parametrize("provider", ["azure_devops", "linear", "jira", "github", "gitlab"])
    def test_removed_provider_raises(self, tmp_path: Path, provider: str) -> None:
        _setup_config(tmp_path, provider=provider, workspace="org/proj")
        service = TrackerService(tmp_path)
        with pytest.raises(TrackerServiceError, match="no longer supported"):
            service._resolve_backend()


class TestResolveBackendNoBinding:
    """No binding raises immediately."""

    def test_no_config_raises(self, tmp_path: Path) -> None:
        service = TrackerService(tmp_path)
        with pytest.raises(TrackerServiceError, match="No tracker bound"):
            service._resolve_backend()

    def test_empty_provider_raises(self, tmp_path: Path) -> None:
        # Config file exists but provider is empty
        _setup_config(tmp_path, provider=None)
        service = TrackerService(tmp_path)
        with pytest.raises(TrackerServiceError, match="No tracker bound"):
            service._resolve_backend()


class TestResolveBackendUnknown:
    """Unknown providers raise immediately."""

    def test_unknown_provider_raises(self, tmp_path: Path) -> None:
        _setup_config(tmp_path, provider="notion", workspace="ws")
        service = TrackerService(tmp_path)
        with pytest.raises(TrackerServiceError, match="Unknown provider"):
            service._resolve_backend()


# ---------------------------------------------------------------------------
# supported_providers()
# ---------------------------------------------------------------------------


class TestSupportedProviders:
    """supported_providers() returns only the active (local) providers."""

    def test_includes_local_providers(self) -> None:
        providers = TrackerService.supported_providers()
        for p in ("beads", "fp"):
            assert p in providers

    def test_excludes_removed_providers(self) -> None:
        providers = TrackerService.supported_providers()
        for p in ("azure_devops", "linear", "jira", "github", "gitlab"):
            assert p not in providers

    def test_returns_sorted_tuple(self) -> None:
        providers = TrackerService.supported_providers()
        assert isinstance(providers, tuple)
        assert providers == tuple(sorted(providers))


# ---------------------------------------------------------------------------
# bind dispatch tests
# ---------------------------------------------------------------------------


class TestBindDispatch:
    """bind() dispatches to the local backend or refuses removed/unknown providers."""

    def test_bind_local_provider_dispatches_to_local(self, tmp_path: Path) -> None:
        from specify_cli.tracker.local_service import LocalTrackerService

        service = TrackerService(tmp_path)
        with patch.object(
            LocalTrackerService,
            "bind",
            return_value=TrackerProjectConfig(provider="beads", workspace="ws"),
        ) as mock_bind:
            result = service.bind(
                provider="beads",
                workspace="ws",
                ownership_mode="external_authoritative",
                ownership_field_owners={},
                credentials={},
            )
            mock_bind.assert_called_once_with(
                provider="beads",
                workspace="ws",
                ownership_mode="external_authoritative",
                ownership_field_owners={},
                credentials={},
            )
            assert result.provider == "beads"

    @pytest.mark.parametrize("provider", ["azure_devops", "linear", "jira", "github", "gitlab"])
    def test_bind_removed_provider_raises(self, tmp_path: Path, provider: str) -> None:
        service = TrackerService(tmp_path)
        with pytest.raises(TrackerServiceError, match="no longer supported"):
            service.bind(provider=provider, workspace="org/proj")

    def test_bind_unknown_provider_raises(self, tmp_path: Path) -> None:
        service = TrackerService(tmp_path)
        with pytest.raises(TrackerServiceError, match="Unknown provider"):
            service.bind(provider="notion", workspace="ws")


# ---------------------------------------------------------------------------
# Delegation tests (verify methods call through to backend)
# ---------------------------------------------------------------------------


class TestDelegation:
    """Verify delegating methods call _resolve_backend()."""

    def test_unbind_delegates(self, tmp_path: Path) -> None:
        from specify_cli.tracker.local_service import LocalTrackerService

        _setup_config(tmp_path, provider="beads", workspace="ws")
        service = TrackerService(tmp_path)
        with patch.object(LocalTrackerService, "unbind") as mock_unbind:
            service.unbind()
            mock_unbind.assert_called_once()

    def test_status_delegates(self, tmp_path: Path) -> None:
        from specify_cli.tracker.local_service import LocalTrackerService

        _setup_config(tmp_path, provider="beads", workspace="ws")
        service = TrackerService(tmp_path)
        with patch.object(LocalTrackerService, "status", return_value={"configured": True}) as mock_status:
            result = service.status()
            mock_status.assert_called_once()
            assert result == {"configured": True}

    def test_map_list_delegates(self, tmp_path: Path) -> None:
        from specify_cli.tracker.local_service import LocalTrackerService

        _setup_config(tmp_path, provider="beads", workspace="ws")
        service = TrackerService(tmp_path)
        with patch.object(LocalTrackerService, "map_list", return_value=[{"wp_id": "WP01"}]) as mock_map_list:
            result = service.map_list()
            mock_map_list.assert_called_once()
            assert result == [{"wp_id": "WP01"}]


# ---------------------------------------------------------------------------
# parse_kv_pairs preserved
# ---------------------------------------------------------------------------


class TestParseKvPairsPreserved:
    """parse_kv_pairs must still be importable from service module."""

    def test_importable(self) -> None:
        from specify_cli.tracker.service import parse_kv_pairs

        result = parse_kv_pairs(["key=value", "a=b"])
        assert result == {"key": "value", "a": "b"}

    def test_invalid_entry_raises(self) -> None:
        from specify_cli.tracker.service import parse_kv_pairs

        with pytest.raises(TrackerServiceError, match="Invalid"):
            parse_kv_pairs(["noequals"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_config(
    repo_root: Path,
    *,
    provider: str | None = None,
    workspace: str | None = None,
    project_slug: str | None = None,
) -> None:
    """Create a minimal tracker config for testing."""
    config = TrackerProjectConfig(
        provider=provider,
        workspace=workspace,
        project_slug=project_slug,
    )
    save_tracker_config(repo_root, config)
