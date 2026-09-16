"""Artifact containment for the dashboard's artifact routes, on a lane CI runs.

The behaviour under test is the same one
``tests/test_dashboard/test_api_handler.py::TestArtifactDirectoryEndpoint``
asserts: an artifact route serves only files that live inside BOTH the
mission directory and the artifact directory it advertises, so neither a
symlinked artifact root nor an individual symlinked file can hand a viewer
something from elsewhere on disk.

Why the duplication is deliberate: ``tests/test_dashboard/`` is not part of
any row in ``.github/ci-module-registry.yml`` — the ``dashboard`` module row
has no explicit ``test_dirs``, so its shard runs the mirrored ``tests/dashboard``
directory only. Tests under ``tests/test_dashboard/`` therefore never execute
in the per-PR module matrix, which is why the containment lines below had no
coverage evidence in ``ci-aggregate``'s diff-cover gate even though they were
exercised locally. These cases are fast and server-free, so they belong on the
lane that actually runs: the registry gap itself is filed as spec-kitty#4369,
and when it closes this file can fold back into the fuller suite.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.dashboard.handlers import features as features_module

pytestmark = pytest.mark.fast

MISSION_RELATIVE = ("kitty-specs", "001-test-mission")


def _mission_dir(tmp_path: Path) -> Path:
    return tmp_path.joinpath(*MISSION_RELATIVE)


def _handler(project_dir: Path) -> MagicMock:
    """The handler seam these routes need: response recording plus a buffer."""
    handler = MagicMock()
    handler.project_dir = str(project_dir)
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.wfile = io.BytesIO()
    return handler


class TestArtifactPathIsContained:
    """Both boundaries are required, and an unreadable path is not contained."""

    def test_file_inside_both_roots_is_contained(self, tmp_path: Path) -> None:
        mission_dir = _mission_dir(tmp_path)
        artifact_dir = mission_dir / "contracts"
        artifact_dir.mkdir(parents=True)
        target = artifact_dir / "api.md"
        target.write_text("# API contract\n", encoding="utf-8")

        assert features_module._artifact_path_is_contained(target, mission_dir, artifact_dir) is True

    def test_file_inside_the_mission_but_outside_the_artifact_dir_is_not_contained(self, tmp_path: Path) -> None:
        mission_dir = _mission_dir(tmp_path)
        artifact_dir = mission_dir / "contracts"
        artifact_dir.mkdir(parents=True)
        spec = mission_dir / "spec.md"
        spec.write_text("# Mission specification\n", encoding="utf-8")

        assert features_module._artifact_path_is_contained(spec, mission_dir, artifact_dir) is False

    def test_symlinked_artifact_root_escaping_the_mission_is_not_contained(self, tmp_path: Path) -> None:
        mission_dir = _mission_dir(tmp_path)
        mission_dir.mkdir(parents=True)
        external = tmp_path / "outside-mission"
        external.mkdir()
        (external / "private.md").write_text("outside content", encoding="utf-8")
        artifact_dir = mission_dir / "contracts"
        artifact_dir.symlink_to(external, target_is_directory=True)

        assert features_module._artifact_path_is_contained(artifact_dir, mission_dir, artifact_dir) is False

    def test_unresolvable_path_is_not_contained(self, tmp_path: Path) -> None:
        """A symlink loop makes ``resolve()`` raise; the guard answers "no"
        rather than propagating an OSError out of a request handler."""
        mission_dir = _mission_dir(tmp_path)
        artifact_dir = mission_dir / "contracts"
        artifact_dir.mkdir(parents=True)
        first = artifact_dir / "loop-a"
        second = artifact_dir / "loop-b"
        first.symlink_to(second)
        second.symlink_to(first)

        assert features_module._artifact_path_is_contained(first, mission_dir, artifact_dir) is False


class TestArtifactRoutesHonourContainment:
    """The listing and the file route both refuse what the guard refuses."""

    def test_listing_returns_only_files_under_the_artifact_directory(self, tmp_path: Path) -> None:
        mission_dir = _mission_dir(tmp_path)
        artifact_dir = mission_dir / "contracts"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "public.md").write_text("public contract", encoding="utf-8")
        (mission_dir / "spec.md").write_text("private specification", encoding="utf-8")
        (artifact_dir / "alias.md").symlink_to(mission_dir / "spec.md")
        handler = _handler(tmp_path)

        with patch.object(features_module, "resolve_feature_planning_dir", return_value=mission_dir):
            features_module.FeatureHandler._handle_artifact_directory(
                handler,
                "/api/contracts/001-test-mission",
                "contracts",
            )

        handler.send_response.assert_called_once_with(200)
        assert json.loads(handler.wfile.getvalue()) == {"files": [{"name": "public.md", "path": "contracts/public.md", "icon": "📝"}]}

    def test_file_route_refuses_a_mission_file_outside_the_artifact_directory(self, tmp_path: Path) -> None:
        mission_dir = _mission_dir(tmp_path)
        artifact_dir = mission_dir / "contracts"
        artifact_dir.mkdir(parents=True)
        (mission_dir / "spec.md").write_text("private specification", encoding="utf-8")
        handler = _handler(tmp_path)

        with patch.object(features_module, "resolve_feature_planning_dir", return_value=mission_dir):
            features_module.FeatureHandler._handle_artifact_directory(
                handler,
                "/api/contracts/001-test-mission/spec.md",
                "contracts",
            )

        handler.send_response.assert_called_once_with(404)
        assert handler.wfile.getvalue() == b""

    def test_file_route_serves_a_file_inside_the_artifact_directory(self, tmp_path: Path) -> None:
        mission_dir = _mission_dir(tmp_path)
        artifact_dir = mission_dir / "contracts"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "api.md").write_text("# API contract\n", encoding="utf-8")
        handler = _handler(tmp_path)

        with patch.object(features_module, "resolve_feature_planning_dir", return_value=mission_dir):
            features_module.FeatureHandler._handle_artifact_directory(
                handler,
                "/api/contracts/001-test-mission/contracts%2Fapi.md",
                "contracts",
            )

        handler.send_response.assert_called_once_with(200)
        assert handler.wfile.getvalue() == b"# API contract\n"


class TestResearchRouteHonoursContainment:
    """``handle_research`` confines both its listing and file-serve branches
    the same way ``_handle_artifact_directory`` does — a research file is
    served, a mission file outside ``research/`` (including a symlinked
    ``research/`` root escaping the mission) is refused."""

    def test_listing_returns_only_files_under_research(self, tmp_path: Path) -> None:
        mission_dir = _mission_dir(tmp_path)
        research_dir = mission_dir / "research"
        research_dir.mkdir(parents=True)
        (research_dir / "notes.md").write_text("# Research notes\n", encoding="utf-8")
        (mission_dir / "plan.md").write_text("private plan", encoding="utf-8")
        (research_dir / "alias.md").symlink_to(mission_dir / "plan.md")
        handler = _handler(tmp_path)

        with patch.object(features_module, "resolve_feature_planning_dir", return_value=mission_dir):
            features_module.FeatureHandler.handle_research(handler, "/api/research/001-test-mission")

        handler.send_response.assert_called_once_with(200)
        body = json.loads(handler.wfile.getvalue())
        assert body["artifacts"] == [{"name": "notes.md", "path": "research/notes.md", "icon": "📝"}]

    def test_file_route_serves_a_file_inside_research(self, tmp_path: Path) -> None:
        mission_dir = _mission_dir(tmp_path)
        research_dir = mission_dir / "research"
        research_dir.mkdir(parents=True)
        (research_dir / "notes.md").write_text("# Research notes\n", encoding="utf-8")
        handler = _handler(tmp_path)

        with patch.object(features_module, "resolve_feature_planning_dir", return_value=mission_dir):
            features_module.FeatureHandler.handle_research(
                handler,
                "/api/research/001-test-mission/research%2Fnotes.md",
            )

        handler.send_response.assert_called_once_with(200)
        assert handler.wfile.getvalue() == b"# Research notes\n"

    def test_file_route_refuses_a_mission_file_outside_research(self, tmp_path: Path) -> None:
        mission_dir = _mission_dir(tmp_path)
        research_dir = mission_dir / "research"
        research_dir.mkdir(parents=True)
        (mission_dir / "plan.md").write_text("private plan", encoding="utf-8")
        handler = _handler(tmp_path)

        with patch.object(features_module, "resolve_feature_planning_dir", return_value=mission_dir):
            features_module.FeatureHandler.handle_research(
                handler,
                "/api/research/001-test-mission/plan.md",
            )

        handler.send_response.assert_called_once_with(404)
        assert handler.wfile.getvalue() == b""

    def test_file_route_refuses_the_missions_own_spec_via_the_research_route(self, tmp_path: Path) -> None:
        mission_dir = _mission_dir(tmp_path)
        research_dir = mission_dir / "research"
        research_dir.mkdir(parents=True)
        (mission_dir / "spec.md").write_text("private specification", encoding="utf-8")
        handler = _handler(tmp_path)

        with patch.object(features_module, "resolve_feature_planning_dir", return_value=mission_dir):
            features_module.FeatureHandler.handle_research(
                handler,
                "/api/research/001-test-mission/spec.md",
            )

        handler.send_response.assert_called_once_with(404)
        assert handler.wfile.getvalue() == b""

    def test_symlinked_research_root_escaping_the_mission_is_not_listed(self, tmp_path: Path) -> None:
        mission_dir = _mission_dir(tmp_path)
        mission_dir.mkdir(parents=True)
        external = tmp_path / "outside-mission"
        external.mkdir()
        (external / "private.md").write_text("outside content", encoding="utf-8")
        research_dir = mission_dir / "research"
        research_dir.symlink_to(external, target_is_directory=True)
        handler = _handler(tmp_path)

        with patch.object(features_module, "resolve_feature_planning_dir", return_value=mission_dir):
            features_module.FeatureHandler.handle_research(handler, "/api/research/001-test-mission")

        handler.send_response.assert_called_once_with(200)
        body = json.loads(handler.wfile.getvalue())
        assert body["artifacts"] == []

    def test_symlinked_research_root_escaping_the_mission_is_not_served(self, tmp_path: Path) -> None:
        mission_dir = _mission_dir(tmp_path)
        mission_dir.mkdir(parents=True)
        external = tmp_path / "outside-mission"
        external.mkdir()
        (external / "private.md").write_text("outside content", encoding="utf-8")
        research_dir = mission_dir / "research"
        research_dir.symlink_to(external, target_is_directory=True)
        handler = _handler(tmp_path)

        with patch.object(features_module, "resolve_feature_planning_dir", return_value=mission_dir):
            features_module.FeatureHandler.handle_research(
                handler,
                "/api/research/001-test-mission/research%2Fprivate.md",
            )

        handler.send_response.assert_called_once_with(404)
        assert handler.wfile.getvalue() == b""
