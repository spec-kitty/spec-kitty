"""Feature-centric dashboard handlers."""

from __future__ import annotations

import contextlib
import json
import logging
import urllib.parse
from pathlib import Path
from typing import Optional, cast

from ..api_types import (
    ArtifactDirectoryResponse,
    FeatureItem,
    FeaturesListResponse,
    KanbanResponse,
    KanbanTaskData,
    MissionContext,
    ResearchResponse,
)
from ..csp import send_csp_header
from ..scanner import (
    format_path_for_display,
    read_only_weighted_percentage,
    resolve_active_feature,
    resolve_feature_dir,
    resolve_feature_planning_dir,
    scan_all_features,
    scan_feature_kanban,
)
from .base import DashboardHandler
from charter.activation.mission_type_key import read_mission_type
from specify_cli.upgrade.legacy_detector import is_legacy_format
from specify_cli.mission import MissionError, get_mission_by_name

__all__ = ["FeatureHandler"]


logger = logging.getLogger(__name__)
_PROJECT_DIR_NOT_CONFIGURED = "dashboard project_dir is not configured"


def _require_project_path(project_dir: str | None) -> Path:
    if project_dir is None:
        raise RuntimeError(_PROJECT_DIR_NOT_CONFIGURED)
    return Path(project_dir).resolve()


def _artifact_path_is_contained(path: Path, mission_dir: Path, artifact_dir: Path) -> bool:
    """Require both boundaries, including when the artifact root is a symlink."""
    try:
        resolved = path.resolve()
        return resolved.is_relative_to(mission_dir.resolve()) and resolved.is_relative_to(artifact_dir.resolve())
    except (OSError, RuntimeError):
        return False


def _string_field(mapping: dict[str, object], key: str, default: str = "") -> str:
    value = mapping.get(key, default)
    return value if isinstance(value, str) else str(value)


def _resolve_active_mission_context(project_path: Path) -> tuple[dict[str, object] | None, MissionContext]:
    active_feature = cast(dict[str, object] | None, resolve_active_feature(project_path))
    mission_context: MissionContext = {
        "name": "No active feature",
        "domain": "unknown",
        "version": "",
        "slug": "",
        "description": "",
        "path": "",
    }
    if not active_feature:
        return None, mission_context

    meta = active_feature.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    # rc3 M5 (FR-005): resolve the canonical mission_type via the one shared
    # reader — drops the legacy `mission` read and the silent `software-dev`
    # default. A typeless mission yields "" here and surfaces as "Unknown (…)"
    # below, rather than being masked as software-dev.
    feature_mission_type = read_mission_type(meta) or ""
    feature_name = _string_field(active_feature, "name")
    try:
        kittify_dir = project_path / ".kittify"
        mission = get_mission_by_name(feature_mission_type, kittify_dir)
    except MissionError:
        mission_context = {
            "name": f"Unknown ({feature_mission_type})",
            "domain": "unknown",
            "version": "",
            "slug": feature_mission_type,
            "description": "",
            "path": "",
            "feature": feature_name,
        }
        return active_feature, mission_context

    mission_context = {
        "name": mission.name,
        "domain": mission.config.domain,
        "version": mission.config.version,
        "slug": mission.path.name,
        "description": mission.config.description or "",
        "path": format_path_for_display(str(mission.path)),
        "feature": feature_name,
    }
    return active_feature, mission_context


class FeatureHandler(DashboardHandler):
    """Serve feature lists, kanban lanes, and artifact viewers."""

    def handle_features_list(self) -> None:
        """Return summary data for all features."""
        try:
            project_path = _require_project_path(self.project_dir)
            features = cast(list[FeatureItem], scan_all_features(project_path))

            # #704: a discarded mission keeps its kitty-specs/<slug>/ directory
            # (the runtime_abandoned retrospective lives there), so the scan
            # still finds it. Filtering here rather than in the scanner keeps
            # scan_all_features a pure scan for every other consumer.
            features = [f for f in features if f.get("mission_status") != "discarded"]

            # Add legacy format indicator to each feature
            for feature in features:
                feature_dir = project_path / feature["path"]
                feature["is_legacy"] = is_legacy_format(feature_dir)

            active_feature, mission_context = _resolve_active_mission_context(project_path)

            worktrees_root_path = project_path / ".worktrees"
            try:
                worktrees_root_resolved = worktrees_root_path.resolve()
            except Exception:
                worktrees_root_resolved = worktrees_root_path

            try:
                current_path = Path.cwd().resolve()
            except Exception:
                current_path = Path.cwd()

            worktrees_root_exists = worktrees_root_path.exists()
            worktrees_root_display = format_path_for_display(str(worktrees_root_resolved)) if worktrees_root_exists else None

            active_worktree_display: str | None = None
            if worktrees_root_exists:
                try:
                    current_path.relative_to(worktrees_root_resolved)
                    active_worktree_display = format_path_for_display(str(current_path))
                except ValueError:
                    active_worktree_display = None

            if not active_worktree_display and current_path != project_path:
                active_worktree_display = format_path_for_display(str(current_path))

            active_feature_id = _string_field(active_feature, "id") if active_feature else None
            response: FeaturesListResponse = {
                "features": features,
                "active_feature_id": active_feature_id,
                "project_path": format_path_for_display(str(project_path)),
                "worktrees_root": worktrees_root_display,
                "active_worktree": active_worktree_display,
                "active_mission": mission_context,
            }
            self._send_json(200, dict(response))
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.exception("Failed to scan dashboard features")
            self._send_json(500, {"error": "failed_to_scan_features", "detail": str(exc)})

    def handle_kanban(self, path: str) -> None:
        """Return kanban data for a specific feature slug."""
        parts = path.split("/")
        if len(parts) >= 4:
            feature_id = parts[3]
            project_path = _require_project_path(self.project_dir)
            kanban_data = cast(dict[str, list[KanbanTaskData]], scan_feature_kanban(project_path, feature_id))

            # Legacy-format is a PLANNING-surface question — a coord husk has
            # no tasks/ tree and would wrongly read as non-legacy (#2502). The
            # weighted-percentage read below stays on the coord-first dir:
            # the live event log is a STATUS-surface artifact.
            planning_dir = resolve_feature_planning_dir(project_path, feature_id)
            is_legacy = is_legacy_format(planning_dir) if planning_dir else False
            feature_dir = resolve_feature_dir(project_path, feature_id)

            # Pre-compute weighted progress for the kanban panel.
            # WP11/FR-014(a): the dashboard is a read-only viewer. It MUST NOT
            # write tracked status (status.json) as a side-effect of serving a
            # kanban request — doing so clobbers status during git ops (#1789).
            # The shared read-only helper reduces the event log without writing
            # and consumes WP07's single git-op detection source (C-005).
            weighted_pct = None
            if feature_dir and not is_legacy:
                with contextlib.suppress(Exception):
                    weighted_pct = read_only_weighted_percentage(feature_dir)

            response: KanbanResponse = {
                "lanes": kanban_data,
                "is_legacy": is_legacy,
                "upgrade_needed": is_legacy,
                "weighted_percentage": weighted_pct,
            }

            self.send_response(200)
            send_csp_header(self)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            return

        self.send_response(404)
        send_csp_header(self)
        self.end_headers()

    def handle_research(self, path: str) -> None:
        """Return research.md contents + artifacts, or serve a specific file."""
        parts = path.split("/")
        if len(parts) < 4:
            self.send_response(404)
            send_csp_header(self)
            self.end_headers()
            return

        feature_id = parts[3]
        project_path = _require_project_path(self.project_dir)
        # Planning-surface read: an in-flight coordination mission's coord
        # copy holds only status writes, so viewers must re-anchor to the
        # primary planning surface (#2502).
        feature_dir = resolve_feature_planning_dir(project_path, feature_id)

        if len(parts) == 4:
            response: ResearchResponse = {"main_file": None, "artifacts": []}

            if feature_dir:
                research_md = feature_dir / "research.md"
                if research_md.exists():
                    try:
                        response["main_file"] = research_md.read_text(encoding="utf-8")
                    except UnicodeDecodeError as err:
                        error_msg = (
                            f"⚠️ **Encoding Error in research.md**\\n\\n"
                            f"This file contains non-UTF-8 characters at position {err.start}.\\n"
                            "Please convert the file to UTF-8 encoding.\\n\\n"
                            "Attempting to read with error recovery...\\n\\n---\\n\\n"
                        )
                        response["main_file"] = error_msg + research_md.read_text(encoding="utf-8", errors="replace")

                research_dir = feature_dir / "research"
                if research_dir.exists() and research_dir.is_dir():
                    for file_path in sorted(research_dir.rglob("*")):
                        if file_path.is_file():
                            relative_path = str(file_path.relative_to(feature_dir))
                            icon = "📄"
                            if file_path.suffix == ".csv":
                                icon = "📊"
                            elif file_path.suffix == ".md":
                                icon = "📝"
                            elif file_path.suffix in [".xlsx", ".xls"]:
                                icon = "📈"
                            elif file_path.suffix == ".json":
                                icon = "📋"
                            response["artifacts"].append(
                                {
                                    "name": file_path.name,
                                    "path": relative_path,
                                    "icon": icon,
                                }
                            )

            self.send_response(200)
            send_csp_header(self)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            return

        if len(parts) >= 5 and feature_dir:
            file_path_encoded = parts[4]
            file_path_str = urllib.parse.unquote(file_path_encoded)
            artifact_file = (feature_dir / file_path_str).resolve()

            try:
                artifact_file.relative_to(feature_dir.resolve())
            except ValueError:
                self.send_response(404)
                send_csp_header(self)
                self.end_headers()
                return

            if artifact_file.exists() and artifact_file.is_file():
                self.send_response(200)
                send_csp_header(self)
                self.send_header("Content-type", "text/plain")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                try:
                    content = artifact_file.read_text(encoding="utf-8")
                    self.wfile.write(content.encode("utf-8"))
                except UnicodeDecodeError as err:
                    error_msg = (
                        f"⚠️ Encoding Error in {artifact_file.name}\\n\\n"
                        f"This file contains non-UTF-8 characters at position {err.start}.\\n"
                        "Please convert the file to UTF-8 encoding.\\n\\n"
                        "Attempting to read with error recovery...\\n\\n"
                    )
                    content = artifact_file.read_text(encoding="utf-8", errors="replace")
                    self.wfile.write(error_msg.encode("utf-8") + content.encode("utf-8"))
                except Exception as exc:
                    self.wfile.write(f"Error reading file: {exc}".encode())
                return

        self.send_response(404)
        send_csp_header(self)
        self.end_headers()

    def _handle_artifact_directory(self, path: str, directory_name: str, md_icon: str = "📝") -> None:
        """Serve an artifact-directory listing or a contained file.

        The endpoint accepts ``/api/{directory_name}/{mission}`` for a JSON
        listing and appends one URL-encoded repository-relative path to serve a
        file.  The Mission planning directory is resolved through the canonical
        planning seam; file requests must remain below the named artifact
        directory or receive ``404``.

        Args:
            path: Request path, including the Mission selector and optional file.
            directory_name: Artifact subdirectory, such as ``contracts``.
            md_icon: Icon used for Markdown files in a listing.
        """
        parts = path.split("/")
        if len(parts) < 4:
            self.send_response(404)
            send_csp_header(self)
            self.end_headers()
            return

        feature_id = parts[3]
        if self.project_dir is None:
            raise RuntimeError("dashboard project_dir is not configured")
        project_path = Path(self.project_dir)
        # Planning-surface read: an in-flight coordination mission's coord
        # copy holds only status writes, so viewers must re-anchor to the
        # primary planning surface (#2502).
        feature_dir = resolve_feature_planning_dir(project_path, feature_id)

        if len(parts) == 4:
            # Return directory listing
            response: ArtifactDirectoryResponse = {"files": []}

            if feature_dir:
                artifact_dir = feature_dir / directory_name
                if _artifact_path_is_contained(artifact_dir, feature_dir, artifact_dir) and artifact_dir.is_dir():
                    for file_path in sorted(artifact_dir.rglob("*")):
                        if file_path.is_file() and _artifact_path_is_contained(file_path, feature_dir, artifact_dir):
                            relative_path = str(file_path.relative_to(feature_dir))
                            icon = "📄"
                            if file_path.suffix == ".md":
                                icon = md_icon
                            elif file_path.suffix == ".json":
                                icon = "📋"
                            response["files"].append(
                                {
                                    "name": file_path.name,
                                    "path": relative_path,
                                    "icon": icon,
                                }
                            )

            self.send_response(200)
            send_csp_header(self)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            return

        if len(parts) >= 5 and feature_dir:
            # Serve specific file
            file_path_encoded = parts[4]
            file_path_str = urllib.parse.unquote(file_path_encoded)
            artifact_file = (feature_dir / file_path_str).resolve()
            artifact_dir = (feature_dir / directory_name).resolve()

            if not _artifact_path_is_contained(artifact_file, feature_dir, artifact_dir):
                self.send_response(404)
                send_csp_header(self)
                self.end_headers()
                return

            if artifact_file.exists() and artifact_file.is_file():
                self.send_response(200)
                send_csp_header(self)
                self.send_header("Content-type", "text/plain")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                try:
                    content = artifact_file.read_text(encoding="utf-8")
                    self.wfile.write(content.encode("utf-8"))
                except UnicodeDecodeError as err:
                    error_msg = (
                        f"⚠️ Encoding Error in {artifact_file.name}\\n\\n"
                        f"This file contains non-UTF-8 characters at position {err.start}.\\n"
                        "Please convert the file to UTF-8 encoding.\\n\\n"
                        "Attempting to read with error recovery...\\n\\n"
                    )
                    content = artifact_file.read_text(encoding="utf-8", errors="replace")
                    self.wfile.write(error_msg.encode("utf-8") + content.encode("utf-8"))
                except Exception as exc:
                    self.wfile.write(f"Error reading file: {exc}".encode())
                return

        self.send_response(404)
        send_csp_header(self)
        self.end_headers()

    def handle_contracts(self, path: str) -> None:
        """Return contracts directory listing or serve a specific file."""
        self._handle_artifact_directory(path, "contracts", md_icon="📝")

    def handle_checklists(self, path: str) -> None:
        """Return checklists directory listing or serve a specific file."""
        self._handle_artifact_directory(path, "checklists", md_icon="✅")

    def handle_artifact(self, path: str) -> None:
        """Serve primary artifacts like spec.md and plan.md."""
        parts = path.split("/")
        if len(parts) < 4:
            self.send_response(404)
            send_csp_header(self)
            self.end_headers()
            return

        feature_id = parts[3]
        artifact_name = parts[4] if len(parts) > 4 else ""

        if self.project_dir is None:
            raise RuntimeError("dashboard project_dir is not configured")
        project_path = Path(self.project_dir)
        # Planning-surface read: an in-flight coordination mission's coord
        # copy holds only status writes, so viewers must re-anchor to the
        # primary planning surface (#2502).
        feature_dir = resolve_feature_planning_dir(project_path, feature_id)

        artifact_map = {
            "spec": "spec.md",
            "plan": "plan.md",
            "tasks": "tasks.md",
            "research": "research.md",
            "quickstart": "quickstart.md",
            "data-model": "data-model.md",
        }

        filename = artifact_map.get(artifact_name)
        if feature_dir and filename:
            artifact_file = feature_dir / filename
            if artifact_file.exists():
                self.send_response(200)
                send_csp_header(self)
                self.send_header("Content-type", "text/plain")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                try:
                    content = artifact_file.read_text(encoding="utf-8")
                    self.wfile.write(content.encode("utf-8"))
                except UnicodeDecodeError as err:
                    error_msg = (
                        f"⚠️ **Encoding Error in {filename}**\\n\\n"
                        f"This file contains non-UTF-8 characters at position {err.start}.\\n"
                        "Please convert the file to UTF-8 encoding.\\n\\n"
                        "Attempting to read with error recovery...\\n\\n---\\n\\n"
                    )
                    content = artifact_file.read_text(encoding="utf-8", errors="replace")
                    self.wfile.write(error_msg.encode("utf-8") + content.encode("utf-8"))
                except Exception as exc:
                    self.wfile.write(f"Error reading {filename}: {exc}".encode())
                return

        self.send_response(404)
        send_csp_header(self)
        self.end_headers()
