"""Tests for dashboard API handler — specifically that health is read-only (Fix #9)."""

from __future__ import annotations

import inspect
import io
import json
import urllib.request
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.dashboard.csp import DASHBOARD_CSP
from specify_cli.mission import MissionError

pytestmark = pytest.mark.fast


class TestHealthEndpointNoSideEffects:
    """/api/health observes local state only: no daemon spawn, no sync payload."""

    def test_health_reports_project_without_sync_block(self, tmp_path):
        """handle_health returns the project identity and nothing daemon-shaped."""
        from specify_cli.dashboard.handlers import api as api_module

        handler = MagicMock()
        handler.project_dir = str(tmp_path)
        handler.project_token = "tok"
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        buf = io.BytesIO()
        handler.wfile = buf

        # Call the real handle_health method
        api_module.APIHandler.handle_health(handler)

        handler.send_response.assert_called_once_with(200)
        buf.seek(0)
        data = json.loads(buf.read().decode("utf-8"))
        assert data["status"] == "ok"
        assert data["project_path"] == str(tmp_path.resolve())
        assert data["token"] == "tok"
        assert "sync" not in data, "/api/health no longer reports sync-daemon state"
        assert "websocket_status" not in data, "/api/health no longer reports websocket state"

    def test_dashboard_api_module_has_no_sync_daemon_dependency(self):
        """The re-homed dashboard must not import or call the sync daemon.

        Guards the E4 re-homing (planning epic #4): the borrowed
        ``ensure_sync_daemon_running``/``get_sync_daemon_status`` helpers left
        ``dashboard/`` with the route and health fields they served.
        """
        import specify_cli.dashboard.handlers.api as api_module

        source = inspect.getsource(api_module)
        assert "ensure_sync_daemon_running" not in source
        assert "get_sync_daemon_status" not in source
        assert "urllib.request" not in source, (
            "the dashboard API handler holds no transmit primitive of its own"
        )
        assert not hasattr(api_module.APIHandler, "handle_sync_trigger"), (
            "/api/sync/trigger was deleted; do not reintroduce it"
        )

    def test_health_never_touches_urlopen(self, tmp_path):
        """A hostile/unreachable loopback cannot make /api/health transmit."""
        from specify_cli.dashboard.handlers import api as api_module

        def boom(*args, **kwargs):
            raise AssertionError("/api/health must not perform network I/O")

        handler = MagicMock()
        handler.project_dir = str(tmp_path)
        handler.project_token = None
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = io.BytesIO()

        with patch.object(urllib.request, "urlopen", boom):
            api_module.APIHandler.handle_health(handler)

        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        assert payload == {"status": "ok", "project_path": str(tmp_path.resolve())}


class TestFeaturesEndpointErrorHandling:
    """Feature list handler should return JSON errors, not partial responses."""

    def test_features_endpoint_returns_structured_error_without_project_dir(self):
        from specify_cli.dashboard.handlers import features as features_module

        handler = MagicMock()
        handler.project_dir = None
        handler._send_json = MagicMock()

        features_module.FeatureHandler.handle_features_list(handler)

        handler._send_json.assert_called_once()
        status_code, payload = handler._send_json.call_args.args
        assert status_code == 500
        assert payload["error"] == "failed_to_scan_features"
        assert "project_dir" in payload["detail"]

    def test_features_endpoint_hides_discarded_missions(self, tmp_path):
        # #704: the discarded mission keeps its kitty-specs/<slug>/ directory, so
        # the scan still finds it. The dashboard is what has to stop listing it.
        from specify_cli.dashboard.handlers import features as features_module

        handler = MagicMock()
        handler.project_dir = str(tmp_path)
        handler._send_json = MagicMock()

        scanned = [
            {"id": "001-live", "path": "kitty-specs/001-live", "mission_status": "active"},
            {"id": "002-gone", "path": "kitty-specs/002-gone", "mission_status": "discarded"},
        ]
        with (
            patch.object(features_module, "scan_all_features", return_value=scanned),
            patch.object(features_module, "is_legacy_format", return_value=False),
        ):
            features_module.FeatureHandler.handle_features_list(handler)

        handler._send_json.assert_called_once()
        _status_code, payload = handler._send_json.call_args.args
        assert [f["id"] for f in payload["features"]] == ["001-live"]

    def test_features_endpoint_returns_structured_error_on_scan_failure(self, tmp_path):
        from specify_cli.dashboard.handlers import features as features_module

        handler = MagicMock()
        handler.project_dir = str(tmp_path)
        handler._send_json = MagicMock()

        with patch.object(features_module, "scan_all_features", side_effect=RuntimeError("boom")):
            features_module.FeatureHandler.handle_features_list(handler)

        handler._send_json.assert_called_once()
        status_code, payload = handler._send_json.call_args.args
        assert status_code == 500
        assert payload["error"] == "failed_to_scan_features"
        assert "boom" in payload["detail"]

    def test_features_endpoint_returns_full_success_payload(self, tmp_path, monkeypatch):
        from specify_cli.dashboard.handlers import features as features_module

        feature_dir = tmp_path / "kitty-specs" / "001-test"
        feature_dir.mkdir(parents=True)
        worktree_dir = tmp_path / ".worktrees" / "001-test"
        worktree_dir.mkdir(parents=True)
        monkeypatch.chdir(worktree_dir)

        feature = {
            "id": "001-test",
            "name": "Test Feature",
            "path": "kitty-specs/001-test",
            "meta": {"mission": "software-dev"},
        }
        mission = SimpleNamespace(
            name="Software Dev",
            config=SimpleNamespace(domain="engineering", version="3.1", description="Build software"),
            path=tmp_path / ".kittify" / "missions" / "software-dev",
        )

        handler = MagicMock()
        handler.project_dir = str(tmp_path)
        handler._send_json = MagicMock()

        with (
            patch.object(features_module, "scan_all_features", return_value=[feature.copy()]),
            patch.object(features_module, "resolve_active_feature", return_value=feature),
            patch.object(features_module, "get_mission_by_name", return_value=mission),
            patch.object(features_module, "is_legacy_format", return_value=False),
        ):
            features_module.FeatureHandler.handle_features_list(handler)

        status_code, payload = handler._send_json.call_args.args
        assert status_code == 200
        assert payload["features"][0]["is_legacy"] is False
        assert payload["active_feature_id"] == "001-test"
        assert payload["active_mission"]["name"] == "Software Dev"
        assert payload["active_mission"]["feature"] == "Test Feature"
        assert payload["worktrees_root"] is not None
        assert payload["active_worktree"] is not None

    def test_features_endpoint_uses_unknown_mission_fallback(self, tmp_path, monkeypatch):
        from specify_cli.dashboard.handlers import features as features_module

        feature_dir = tmp_path / "kitty-specs" / "001-test"
        feature_dir.mkdir(parents=True)
        worktrees_root = tmp_path / ".worktrees"
        worktrees_root.mkdir(parents=True)
        outside_dir = tmp_path / "outside-worktree"
        outside_dir.mkdir()
        monkeypatch.chdir(outside_dir)

        feature = {
            "id": "001-test",
            "name": "Test Feature",
            "path": "kitty-specs/001-test",
            "meta": {"mission_type": "mystery-mission"},
        }

        handler = MagicMock()
        handler.project_dir = str(tmp_path)
        handler._send_json = MagicMock()

        with (
            patch.object(features_module, "scan_all_features", return_value=[feature.copy()]),
            patch.object(features_module, "resolve_active_feature", return_value=feature),
            patch.object(features_module, "get_mission_by_name", side_effect=MissionError("missing")),
            patch.object(features_module, "is_legacy_format", return_value=True),
        ):
            features_module.FeatureHandler.handle_features_list(handler)

        status_code, payload = handler._send_json.call_args.args
        assert status_code == 200
        assert payload["features"][0]["is_legacy"] is True
        assert payload["active_mission"]["name"] == "Unknown (mystery-mission)"
        assert payload["active_mission"]["feature"] == "Test Feature"
        assert payload["active_worktree"] is not None

    def test_features_endpoint_falls_back_when_path_resolution_breaks(self, tmp_path):
        from specify_cli.dashboard.handlers import features as features_module

        project_path = tmp_path.resolve()
        worktrees_root = project_path / ".worktrees"
        fallback_cwd = project_path / "cwd-fallback"
        fallback_cwd.mkdir()
        path_cls = type(project_path)
        original_resolve = path_cls.resolve

        def flaky_resolve(self, *args, **kwargs):
            if self == worktrees_root or self == fallback_cwd:
                raise RuntimeError("resolution failed")
            return original_resolve(self, *args, **kwargs)

        handler = MagicMock()
        handler.project_dir = str(project_path)
        handler._send_json = MagicMock()

        with (
            patch.object(features_module, "scan_all_features", return_value=[]),
            patch.object(features_module, "resolve_active_feature", return_value=None),
            patch.object(features_module.Path, "cwd", return_value=fallback_cwd),
            patch.object(path_cls, "resolve", flaky_resolve),
        ):
            features_module.FeatureHandler.handle_features_list(handler)

        status_code, payload = handler._send_json.call_args.args
        assert status_code == 200
        assert payload["features"] == []
        assert payload["worktrees_root"] is None
        assert payload["active_worktree"] is not None

    def test_handle_kanban_computes_weighted_progress_for_nonlegacy(self, tmp_path):
        """Non-legacy features compute weighted_percentage from the canonical snapshot."""
        from specify_cli.dashboard.handlers import features as features_module

        feature_dir = tmp_path / "kitty-specs" / "001-wp"
        feature_dir.mkdir(parents=True)

        handler = MagicMock()
        handler.project_dir = str(tmp_path)

        progress = SimpleNamespace(percentage=42.345)
        with (
            patch.object(features_module, "scan_feature_kanban", return_value={"planned": []}),
            patch.object(features_module, "resolve_feature_dir", return_value=feature_dir),
            patch.object(features_module, "is_legacy_format", return_value=False),
            patch("specify_cli.status.materialize", return_value=object()),
            patch("specify_cli.status.compute_weighted_progress", return_value=progress),
        ):
            features_module.FeatureHandler.handle_kanban(handler, "/api/kanban/001-wp")

        handler.wfile.write.assert_called_once()
        payload = json.loads(handler.wfile.write.call_args.args[0].decode())
        assert payload["weighted_percentage"] == 42.3
        assert payload["is_legacy"] is False

    def test_feature_subhandlers_require_project_dir(self):
        from specify_cli.dashboard.handlers import features as features_module

        handler = MagicMock()
        handler.project_dir = None

        with pytest.raises(RuntimeError, match="project_dir"):
            features_module.FeatureHandler.handle_kanban(handler, "/api/kanban/001-test")
        with pytest.raises(RuntimeError, match="project_dir"):
            features_module.FeatureHandler.handle_research(handler, "/api/research/001-test")
        with pytest.raises(RuntimeError, match="project_dir"):
            features_module.FeatureHandler._handle_artifact_directory(
                handler,
                "/api/contracts/001-test",
                "contracts",
            )
        with pytest.raises(RuntimeError, match="project_dir"):
            features_module.FeatureHandler.handle_artifact(handler, "/api/artifact/001-test/spec")


class TestDossierEndpointRouting:
    def _make_handler(self, tmp_path, path: str):
        from specify_cli.dashboard.handlers import api as api_module

        handler = MagicMock()
        handler.project_dir = str(tmp_path)
        handler.project_token = "tok"
        handler.path = path
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = io.BytesIO()
        return api_module, handler

    def test_dossier_endpoint_requires_feature_query_param(self, tmp_path):
        api_module, handler = self._make_handler(tmp_path, "/api/dossier/overview")

        api_module.APIHandler.handle_dossier(handler, handler.path)

        handler.send_response.assert_called_once_with(400)
        handler.wfile.seek(0)
        payload = json.loads(handler.wfile.read().decode("utf-8"))
        assert payload["error"] == "Missing feature parameter"

    def test_dossier_overview_routes_with_mission_slug(self, tmp_path):
        api_module, handler = self._make_handler(
            tmp_path,
            "/api/dossier/overview?feature=064-complete-mission-identity-cutover",
        )
        response = {"overview": "ok"}

        with patch("specify_cli.dossier.api.DossierAPIHandler") as mock_cls:
            mock_cls.return_value.handle_dossier_overview.return_value = response
            api_module.APIHandler.handle_dossier(handler, handler.path)

        mock_cls.return_value.handle_dossier_overview.assert_called_once_with(
            "064-complete-mission-identity-cutover"
        )
        handler.send_response.assert_called_once_with(200)

    def test_dossier_artifacts_routes_with_filters(self, tmp_path):
        api_module, handler = self._make_handler(
            tmp_path,
            "/api/dossier/artifacts?feature=064-complete-mission-identity-cutover&class=decision&required_only=true",
        )
        response = {"artifacts": []}

        with patch("specify_cli.dossier.api.DossierAPIHandler") as mock_cls:
            mock_cls.return_value.handle_dossier_artifacts.return_value = response
            api_module.APIHandler.handle_dossier(handler, handler.path)

        mock_cls.return_value.handle_dossier_artifacts.assert_called_once_with(
            "064-complete-mission-identity-cutover",
            **{"class": "decision", "required_only": "true"},
        )
        handler.send_response.assert_called_once_with(200)

    def test_dossier_detail_and_export_routes_with_mission_slug(self, tmp_path):
        api_module, detail_handler = self._make_handler(
            tmp_path,
            "/api/dossier/artifacts/artifact-123?feature=064-complete-mission-identity-cutover",
        )
        _, export_handler = self._make_handler(
            tmp_path,
            "/api/dossier/snapshots/export?feature=064-complete-mission-identity-cutover",
        )

        with patch("specify_cli.dossier.api.DossierAPIHandler") as mock_cls:
            mock_cls.return_value.handle_dossier_artifact_detail.return_value = {"artifact": "ok"}
            mock_cls.return_value.handle_dossier_snapshot_export.return_value = {"export": "ok"}

            api_module.APIHandler.handle_dossier(detail_handler, detail_handler.path)
            api_module.APIHandler.handle_dossier(export_handler, export_handler.path)

        mock_cls.return_value.handle_dossier_artifact_detail.assert_called_once_with(
            "064-complete-mission-identity-cutover",
            "artifact-123",
        )
        mock_cls.return_value.handle_dossier_snapshot_export.assert_called_once_with(
            "064-complete-mission-identity-cutover"
        )

    def test_dossier_handler_hides_internal_errors(self, tmp_path):
        api_module, handler = self._make_handler(
            tmp_path,
            "/api/dossier/overview?feature=064-complete-mission-identity-cutover",
        )
        handler._send_json = MagicMock()

        with patch("specify_cli.dossier.api.DossierAPIHandler", side_effect=RuntimeError("secret traceback")):
            api_module.APIHandler.handle_dossier(handler, handler.path)

        handler._send_json.assert_called_once_with(500, {"error": "dossier_handler_failed"})


class TestDashboardApiSecurityHardening:
    def test_root_serves_preencoded_dashboard_html(self, tmp_path):
        from specify_cli.dashboard.handlers import api as api_module

        handler = MagicMock()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = io.BytesIO()

        with patch.object(api_module, "get_dashboard_html_bytes", return_value=b"<html>ok</html>"):
            api_module.APIHandler.handle_root(handler)

        handler.send_response.assert_called_once_with(200)
        # D2-T1 (HIC-M1-D5-DOMCSP): every dashboard response also carries the
        # Content-Security-Policy header alongside its content-type header.
        handler.send_header.assert_any_call("Content-type", "text/html; charset=utf-8")
        handler.send_header.assert_any_call("Content-Security-Policy", DASHBOARD_CSP)
        assert handler.send_header.call_count == 2
        handler.wfile.seek(0)
        assert handler.wfile.read() == b"<html>ok</html>"

    def test_diagnostics_hides_internal_errors(self, tmp_path):
        from specify_cli.dashboard.handlers import api as api_module

        handler = MagicMock()
        handler.project_dir = str(tmp_path)
        handler._send_json = MagicMock()

        with patch.object(api_module, "run_diagnostics", side_effect=RuntimeError("boom")):
            api_module.APIHandler.handle_diagnostics(handler)

        handler._send_json.assert_called_once_with(500, {"error": "diagnostics_failed"})

    def test_charter_hides_internal_errors(self, tmp_path):
        from specify_cli.dashboard.handlers import api as api_module

        handler = MagicMock()
        handler.project_dir = str(tmp_path)
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = io.BytesIO()

        # FR-003 (#3150): the presence gate (resolve_project_charter_presence)
        # now runs first in handle_charter; an internal error there must be
        # hidden the same way as a body-read error.
        with patch.object(api_module, "resolve_project_charter_presence", side_effect=RuntimeError("secret")):
            api_module.APIHandler.handle_charter(handler)

        handler.send_response.assert_called_once_with(500)
        handler.wfile.seek(0)
        assert handler.wfile.read().decode("utf-8") == "Error loading charter"

    def test_charter_hides_internal_errors_from_body_read(self, tmp_path):
        """The body-reading path (resolve_project_charter_path) still hides errors too."""
        from specify_cli.dashboard.handlers import api as api_module

        charter_dir = tmp_path / ".kittify" / "charter"
        charter_dir.mkdir(parents=True)
        (charter_dir / "charter.yaml").write_text("schema_version: '2.0.0'\n", encoding="utf-8")

        handler = MagicMock()
        handler.project_dir = str(tmp_path)
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = io.BytesIO()

        with patch.object(api_module, "resolve_project_charter_path", side_effect=RuntimeError("secret")):
            api_module.APIHandler.handle_charter(handler)

        handler.send_response.assert_called_once_with(500)
        handler.wfile.seek(0)
        assert handler.wfile.read().decode("utf-8") == "Error loading charter"
