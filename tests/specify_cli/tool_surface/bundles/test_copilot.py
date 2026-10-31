"""Unit tests for the Copilot CLI and VS Code plugin bundle projectors."""

from __future__ import annotations

import json
from pathlib import Path

from specify_cli.tool_surface.bundles.copilot import CopilotBundleProjector
from specify_cli.tool_surface.bundles.projection import AGENT_PLUGINS_SCHEMA
from specify_cli.tool_surface.bundles.vscode import VsCodeBundleProjector

from ._support import full_plans, skills_only_plans

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_copilot_bundle_plugin_json_at_root(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    out = tmp_path / "dist"
    bundle = CopilotBundleProjector().project(full_plans(project), project, out)
    # plugin.json at the output ROOT (not in a subdirectory).
    assert (out / "plugin.json").is_file()
    assert not (out / ".claude-plugin").exists()
    # Agent files use the .agent.md suffix.
    assert (out / "agents" / "architect-alphonso.agent.md").is_file()
    # hooks.json and .mcp.json at root.
    assert (out / "hooks.json").is_file()
    assert (out / ".mcp.json").is_file()
    payload = json.loads((out / "plugin.json").read_text(encoding="utf-8"))
    # The manifest is the pinned Agent Plugins 1.0.0 document (closed schema):
    # the target label is a projector attribute, never a manifest field.
    assert payload["$schema"] == AGENT_PLUGINS_SCHEMA
    assert "distribution_target" not in payload
    assert bundle.distribution_target == "copilot_skill_package"


def test_copilot_validate_fails_when_profiles_missing(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    out = tmp_path / "dist"
    projector = CopilotBundleProjector()
    bundle = projector.project(skills_only_plans(project), project, out)
    result = projector.validate(bundle)
    assert result.passed is False
    assert all(f.code == "bundle-component-missing" for f in result.missing_surfaces)


def test_vscode_uses_same_layout_with_distinct_target(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    out = tmp_path / "dist"
    bundle = VsCodeBundleProjector().project(full_plans(project), project, out)
    assert (out / "plugin.json").is_file()
    assert (out / "agents" / "architect-alphonso.agent.md").is_file()
    payload = json.loads((out / "plugin.json").read_text(encoding="utf-8"))
    assert payload["$schema"] == AGENT_PLUGINS_SCHEMA
    assert "distribution_target" not in payload
    assert bundle.distribution_target == "vscode_extension"


def test_vscode_projector_is_real_not_stub(tmp_path: Path) -> None:
    """VS Code projection produces concrete entries -- no NotImplementedError."""
    project = tmp_path / "proj"
    out = tmp_path / "dist"
    bundle = VsCodeBundleProjector().project(full_plans(project), project, out)
    assert len(bundle.entries) >= 3
