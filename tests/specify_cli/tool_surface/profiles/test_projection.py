"""Unit tests for ``tool_surface.profiles.projection``."""

from __future__ import annotations

from pathlib import Path

from charter.offering.agent_profiles.repository import AgentProfileRepository
from specify_cli.tool_surface.findings import (
    PROFILE_NAME_INVALID,
    PROFILE_OVERLAY_CONFLICT,
    PROFILE_SENTINEL_SKIPPED,
    PROFILE_SOURCE_INVALID,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SurfaceFinding,
)
from specify_cli.tool_surface.profiles.projection import (
    ProfileProjector,
    default_profile_repository,
)
from specify_cli.tool_surface.profiles.manifest import PROJECTION_VERSION, hash_file

from .test_renderers import make_test_profile

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _builtin_repo() -> AgentProfileRepository:
    return AgentProfileRepository()


def _codes(findings: list[SurfaceFinding]) -> set[str]:
    return {f.code for f in findings}


def test_project_claude_returns_builtin_profiles() -> None:
    projector = ProfileProjector(_builtin_repo())
    projected = projector.project("claude", Path("/project"))
    assert projected, "expected at least the built-in profiles"
    urns = {p.profile_urn for p in projected}
    assert "agent_profile:architect-alphonso" in urns
    sample = projected[0]
    assert sample.tool_key == "claude"
    assert sample.format == "claude-agent"
    assert sample.source_layer == "built-in"
    assert sample.file_hash is None  # computed only after write


def test_project_unsupported_tool_returns_empty() -> None:
    # "codex" now has a renderer (WP02), so use a truly unsupported tool key.
    projector = ProfileProjector(_builtin_repo())
    assert projector.project("unknown_tool_xyz", Path("/project")) == []
    assert projector.project("windsurf", Path("/project")) == []


def test_project_excludes_sentinel_profiles() -> None:
    repo = _builtin_repo()
    projector = ProfileProjector(repo)
    projected_ids = {
        p.profile_urn.split(":", 1)[1]
        for p in projector.project("claude", Path("/project"))
    }
    sentinel_ids = {
        prof.profile_id for prof in repo.list_all() if prof.sentinel
    }
    assert sentinel_ids  # there is at least one sentinel built-in
    assert projected_ids.isdisjoint(sentinel_ids)


def test_project_source_layer_filter() -> None:
    projector = ProfileProjector(_builtin_repo())
    builtin_only = projector.project(
        "claude", Path("/project"), source_layers=["built-in"]
    )
    org_only = projector.project(
        "claude", Path("/project"), source_layers=["org"]
    )
    assert builtin_only  # all built-ins survive the builtin filter
    assert org_only == []  # no org overlay in a default setup


def test_project_does_not_mutate_repository() -> None:
    repo = _builtin_repo()
    before = {p.profile_id for p in repo.list_all()}
    ProfileProjector(repo).project("claude", Path("/project"))
    after = {p.profile_id for p in repo.list_all()}
    assert before == after


def test_render_returns_body_for_known_profile() -> None:
    projector = ProfileProjector(_builtin_repo())
    body = projector.render("claude", "agent_profile:architect-alphonso")
    assert body is not None
    assert body.startswith("---\n")
    assert "name: architect-alphonso" in body


def test_render_returns_none_for_unsupported_tool() -> None:
    # "codex" now has a renderer (WP02); use a tool with no native primitive.
    projector = ProfileProjector(_builtin_repo())
    assert projector.render("unknown_tool_xyz", "agent_profile:architect-alphonso") is None
    assert projector.render("windsurf", "agent_profile:architect-alphonso") is None


def test_render_returns_none_for_unknown_profile() -> None:
    projector = ProfileProjector(_builtin_repo())
    assert projector.render("claude", "agent_profile:does-not-exist") is None


def test_default_profile_repository_loads_builtins(tmp_path: Path) -> None:
    repo = default_profile_repository(tmp_path)
    ids = {p.profile_id for p in repo.list_all()}
    assert "architect-alphonso" in ids


def test_project_uses_injected_repo_provenance() -> None:
    """A project-layer profile is tagged with its provenance layer."""
    repo = _builtin_repo()
    profile = make_test_profile(slug="custom-carol")
    repo._profiles[profile.profile_id] = profile  # noqa: SLF001 - test seam
    repo._provenance[profile.profile_id] = "project"  # noqa: SLF001 - test seam
    projector = ProfileProjector(repo)
    projected = {
        p.profile_urn: p for p in projector.project("claude", Path("/project"))
    }
    assert projected["agent_profile:custom-carol"].source_layer == "project"


def test_project_populates_manifest_source_provenance_for_project_profile(
    tmp_path: Path,
) -> None:
    """Projected profiles carry source path/hash/version for manifest writes."""
    project_dir = tmp_path / ".kittify" / "agent_profiles"
    project_dir.mkdir(parents=True)
    source = project_dir / "custom-carol.agent.yaml"
    source.write_text(
        "\n".join(
            [
                "profile-id: custom-carol",
                "name: Custom Carol",
                "description: Project profile.",
                "roles:",
                "  - architect",
                "purpose: Project-only profile.",
                "specialization:",
                "  primary-focus: testing projections",
                "  avoidance-boundary: unrelated work",
                "",
            ]
        ),
        encoding="utf-8",
    )
    repo = AgentProfileRepository(project_dir=project_dir)

    projected = {
        p.profile_urn: p for p in ProfileProjector(repo).project("claude", tmp_path)
    }

    native = projected["agent_profile:custom-carol"]
    assert native.source_layer == "project"
    assert native.source_path == ".kittify/agent_profiles/custom-carol.agent.yaml"
    assert native.source_hash == hash_file(source)
    assert native.projection_version == PROJECTION_VERSION


# --- #1940 finding-code emission (drive the CONDITION, assert it is emitted) --


def _project_dir_with_invalid_profile(tmp_path: Path) -> Path:
    """Write a project-layer profile dir holding one schema-invalid profile.

    The YAML parses fine but fails ``AgentProfile`` validation (no ``roles``),
    so ``AgentProfileRepository`` records it as a skipped/invalid source — the
    exact condition ``profile-source-invalid`` must surface.
    """
    project_dir = tmp_path / ".kittify" / "agent_profiles"
    project_dir.mkdir(parents=True)
    (project_dir / "broken.agent.yaml").write_text(
        # Valid profile-id so the repo attributes the skip, but missing the
        # required ``roles``/``purpose``/``specialization`` -> ValidationError.
        "profile-id: broken-bob\nname: Broken Bob\n",
        encoding="utf-8",
    )
    return project_dir


def test_diagnose_emits_profile_source_invalid(tmp_path: Path) -> None:
    """A profile YAML that fails repository validation emits source-invalid."""
    project_dir = _project_dir_with_invalid_profile(tmp_path)
    repo = AgentProfileRepository(project_dir=project_dir)
    # Pre-condition: the repository actually recorded the invalid source.
    assert any(s.profile_id == "broken-bob" for s in repo.skipped_profiles())

    findings = ProfileProjector(repo).diagnose("claude", tmp_path)

    invalid = [f for f in findings if f.code == PROFILE_SOURCE_INVALID]
    assert invalid, "expected a profile-source-invalid finding to be emitted"
    finding = invalid[0]
    assert finding.severity == SEVERITY_ERROR
    assert "broken-bob" in finding.message
    # The skip reason is carried through, not swallowed.
    assert finding.details


def test_diagnose_does_not_emit_source_invalid_for_clean_repo(
    tmp_path: Path,
) -> None:
    """A repo with no invalid sources emits no source-invalid finding."""
    findings = ProfileProjector(_builtin_repo()).diagnose("claude", tmp_path)
    assert PROFILE_SOURCE_INVALID not in _codes(findings)


def test_diagnose_emits_profile_sentinel_skipped(tmp_path: Path) -> None:
    """Sentinel profiles are RECORDED as info findings, never silently dropped."""
    repo = _builtin_repo()
    sentinels = [p.profile_id for p in repo.list_all() if p.sentinel]
    assert sentinels, "fixture precondition: a sentinel built-in must exist"

    findings = ProfileProjector(repo).diagnose("claude", tmp_path)

    skipped = [f for f in findings if f.code == PROFILE_SENTINEL_SKIPPED]
    assert skipped, "expected sentinel profiles to be recorded as findings"
    assert all(f.severity == SEVERITY_INFO for f in skipped)
    skipped_ids = {
        f.surface_id.split(":", 1)[-1] for f in skipped if f.surface_id
    }
    assert set(sentinels).issubset(skipped_ids)


def test_diagnose_emits_profile_overlay_conflict(tmp_path: Path) -> None:
    """An id loaded in one layer but rejected in another is an overlay conflict.

    A project-layer file redefines ``architect-alphonso`` (a built-in) with
    invalid content. The repository keeps the valid built-in and *skips* the
    project override, leaving the same id both loaded and skipped across two
    layers — an ambiguous/unsafe overlay resolution.
    """
    project_dir = tmp_path / ".kittify" / "agent_profiles"
    project_dir.mkdir(parents=True)
    (project_dir / "arch-override.agent.yaml").write_text(
        "profile-id: architect-alphonso\nroles: []\n", encoding="utf-8"
    )
    repo = AgentProfileRepository(project_dir=project_dir)
    assert "architect-alphonso" in {p.profile_id for p in repo.list_all()}
    assert "architect-alphonso" in {
        s.profile_id for s in repo.skipped_profiles()
    }

    findings = ProfileProjector(repo).diagnose("claude", tmp_path)

    conflicts = [f for f in findings if f.code == PROFILE_OVERLAY_CONFLICT]
    assert conflicts, "expected a profile-overlay-conflict finding to be emitted"
    assert all(f.severity == SEVERITY_ERROR for f in conflicts)
    assert any("architect-alphonso" in f.message for f in conflicts)


def test_diagnose_clean_builtin_repo_has_no_conflict(tmp_path: Path) -> None:
    """The shipped built-ins do not collide on output paths."""
    findings = ProfileProjector(_builtin_repo()).diagnose("claude", tmp_path)
    assert PROFILE_OVERLAY_CONFLICT not in _codes(findings)


def test_diagnose_emits_profile_name_invalid(tmp_path: Path) -> None:
    """A profile id illegal for the native filename emits name-invalid."""
    repo = _builtin_repo()
    profile = make_test_profile(slug="custom-carol")
    profile.profile_id = "bad/slash"  # illegal for .claude/agents/<id>.md
    repo._profiles[profile.profile_id] = profile  # noqa: SLF001 - test seam
    repo._provenance[profile.profile_id] = "project"  # noqa: SLF001 - test seam

    findings = ProfileProjector(repo).diagnose("claude", tmp_path)

    invalid = [f for f in findings if f.code == PROFILE_NAME_INVALID]
    assert invalid, "expected a profile-name-invalid finding to be emitted"
    assert all(f.severity == SEVERITY_ERROR for f in invalid)
    assert any("bad/slash" in f.message for f in invalid)


def test_diagnose_clean_builtin_repo_has_no_name_invalid(tmp_path: Path) -> None:
    """Canonical built-in ids are all legal native filenames."""
    findings = ProfileProjector(_builtin_repo()).diagnose("claude", tmp_path)
    assert PROFILE_NAME_INVALID not in _codes(findings)
