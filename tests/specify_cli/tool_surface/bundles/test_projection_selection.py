"""Target-native agent-profile selection for plugin bundles (#6273).

A bundle member must take exactly one rendering, and that rendering must be one its
distribution target can consume. A Codex ``.toml`` profile is never a candidate for a
Markdown agent member; the other Markdown family is only a lower-priority fallback.
Genuinely conflicting accepted sources still fail closed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.tool_surface.bundles.claude import ClaudeCodeBundleProjector
from specify_cli.tool_surface.bundles.copilot import CopilotBundleProjector
from specify_cli.tool_surface.bundles.projection import files_for_entries
from specify_cli.tool_surface.bundles.vscode import VsCodeBundleProjector
from specify_cli.tool_surface.enums import ToolSurfaceKind
from specify_cli.tool_surface.model import SurfacePlan
from specify_cli.tool_surface.operations import OperationRoot

from ._support import _instance, _write

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _plan(*instances: object) -> list[SurfacePlan]:
    return [SurfacePlan(tool_key="all", instances=tuple(instances), computed_at="t")]  # type: ignore[arg-type]


def _profile(path: Path, owner: str) -> object:
    return _instance(ToolSurfaceKind.AGENT_PROFILE, path, owner)


def _members(projector: ClaudeCodeBundleProjector | CopilotBundleProjector | VsCodeBundleProjector, project: Path, plan: list[SurfacePlan]):
    return [entry for entry in projector.entries(plan, project) if entry.surface_kind == ToolSurfaceKind.AGENT_PROFILE]


def test_claude_bundle_never_renames_a_codex_toml_profile(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    claude = _write(project / ".claude/agents/analyst-annie.md", "# claude body\n")
    codex = _write(project / ".codex/agents/analyst-annie.toml", 'name = "Analyst Annie"\n')
    plan = _plan(_profile(claude, "claude"), _profile(codex, "codex"))

    members = _members(ClaudeCodeBundleProjector(), project, plan)

    assert [m.bundle_relative_path for m in members] == ["agents/analyst-annie.md"]
    assert members[0].sources == (project.resolve() / ".claude/agents/analyst-annie.md",)


def test_copilot_bundle_prefers_its_native_agent_rendering(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    claude = _write(project / ".claude/agents/analyst-annie.md", "# claude body\n")
    copilot = _write(project / ".github/agents/analyst-annie.agent.md", "# copilot body\n")
    plan = _plan(_profile(claude, "claude"), _profile(copilot, "copilot"))

    members = _members(CopilotBundleProjector(), project, plan)

    assert [m.bundle_relative_path for m in members] == ["agents/analyst-annie.agent.md"]
    assert members[0].sources == (project.resolve() / ".github/agents/analyst-annie.agent.md",)


def test_claude_bundle_prefers_claude_over_the_copilot_fallback(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    claude = _write(project / ".claude/agents/architect-alphonso.md", "# claude body\n")
    copilot = _write(project / ".github/agents/architect-alphonso.agent.md", "# copilot body\n")
    plan = _plan(_profile(claude, "claude"), _profile(copilot, "copilot"))

    members = _members(ClaudeCodeBundleProjector(), project, plan)

    assert [m.bundle_relative_path for m in members] == ["agents/architect-alphonso.md"]
    assert members[0].sources == (project.resolve() / ".claude/agents/architect-alphonso.md",)


@pytest.mark.parametrize("projector", [CopilotBundleProjector(), VsCodeBundleProjector()])
def test_copilot_family_keeps_staging_from_a_claude_only_project(tmp_path: Path, projector) -> None:
    project = tmp_path / "proj"
    claude = _write(project / ".claude/agents/architect-alphonso.md", "# claude body\n")
    plan = _plan(_profile(claude, "claude"))

    members = _members(projector, project, plan)

    assert [m.bundle_relative_path for m in members] == ["agents/architect-alphonso.agent.md"]
    assert members[0].sources == (project.resolve() / ".claude/agents/architect-alphonso.md",)


def test_claude_bundle_keeps_staging_from_a_copilot_only_project(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    copilot = _write(project / ".github/agents/architect-alphonso.agent.md", "# copilot body\n")
    plan = _plan(_profile(copilot, "copilot"))

    members = _members(ClaudeCodeBundleProjector(), project, plan)

    assert [m.bundle_relative_path for m in members] == ["agents/architect-alphonso.md"]
    assert members[0].sources == (project.resolve() / ".github/agents/architect-alphonso.agent.md",)


def test_two_differing_same_family_sources_still_conflict(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    first = _write(project / ".claude/agents/analyst-annie.md", "# first\n")
    second = _write(project / "custom/agents/analyst-annie.md", "# second\n")
    plan = _plan(_profile(first, "claude"), _profile(second, "claude"))
    entries = ClaudeCodeBundleProjector().entries(plan, project)
    assert len(entries) == 1 and len(entries[0].sources) == 2

    with pytest.raises(ValueError, match="Conflicting bundle members: agents/analyst-annie.md"):
        files_for_entries(entries, project / "dist", OperationRoot("project", "project", project.resolve()), [])
