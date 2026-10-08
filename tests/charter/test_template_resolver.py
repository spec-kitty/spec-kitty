"""Tests for charter-level template resolution."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from charter.activation.resolver import ActiveCharterService
from charter.activation.template_resolver import CharterTemplateResolver
from charter.offering.missions.repository import TemplateResult
from charter.offering.resolver import ResolutionResult, ResolutionTier

pytestmark = pytest.mark.fast


def test_resolve_command_template_with_project_context_uses_runtime_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "plan.md"
    path.write_text("override command", encoding="utf-8")
    # FR-003 (WP05): the tier-chain seam moved from a module-level
    # ``charter.offering.resolver`` re-export in charter.activation.template_resolver onto the
    # canonical factory, so the patch target moved with it.
    monkeypatch.setattr(
        ActiveCharterService,
        "resolve_command_asset",
        lambda *args, **kwargs: ResolutionResult(path=path, tier=ResolutionTier.OVERRIDE, mission="software-dev"),
    )

    resolver = CharterTemplateResolver(repo=SimpleNamespace())
    result = resolver.resolve_command_template("software-dev", "plan", project_dir=tmp_path)

    assert result.content == "override command"
    assert result.origin == "override/software-dev/command-templates/plan.md"
    assert result.tier.name == ResolutionTier.OVERRIDE.name


def test_resolve_content_template_with_project_context_uses_runtime_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "spec-template.md"
    path.write_text("legacy content", encoding="utf-8")
    # FR-003 (WP05): see the sibling test — patch target follows the seam.
    monkeypatch.setattr(
        ActiveCharterService,
        "resolve_content_asset",
        lambda *args, **kwargs: ResolutionResult(path=path, tier=ResolutionTier.LEGACY, mission="software-dev"),
    )

    resolver = CharterTemplateResolver(repo=SimpleNamespace())
    result = resolver.resolve_content_template("software-dev", "spec-template.md", project_dir=tmp_path)

    assert result.content == "legacy content"
    assert result.origin == "legacy/software-dev/templates/spec-template.md"
    assert result.tier.name == ResolutionTier.LEGACY.name


def test_resolve_templates_without_project_context_use_doctrine_repo() -> None:
    repo = SimpleNamespace(
        get_command_template=lambda mission, name: TemplateResult("command body", "doctrine/software-dev/command-templates/plan.md"),
        get_content_template=lambda mission, name: TemplateResult("template body", "doctrine/software-dev/templates/spec-template.md"),
    )

    resolver = CharterTemplateResolver(repo=repo)

    command = resolver.resolve_command_template("software-dev", "plan")
    content = resolver.resolve_content_template("software-dev", "spec-template.md")

    assert command.content == "command body"
    assert command.origin == "doctrine/software-dev/command-templates/plan.md"
    assert command.tier.name == ResolutionTier.PACKAGE_DEFAULT.name
    assert content.content == "template body"
    assert content.origin == "doctrine/software-dev/templates/spec-template.md"
    assert content.tier.name == ResolutionTier.PACKAGE_DEFAULT.name


def test_resolve_templates_raise_when_doctrine_repo_has_no_match() -> None:
    repo = SimpleNamespace(
        get_command_template=lambda mission, name: None,
        get_content_template=lambda mission, name: None,
    )
    resolver = CharterTemplateResolver(repo=repo)

    with pytest.raises(FileNotFoundError):
        resolver.resolve_command_template("software-dev", "plan")

    with pytest.raises(FileNotFoundError):
        resolver.resolve_content_template("software-dev", "spec-template.md")


def test_from_missions_root_resolves_package_default_paths(tmp_path: Path) -> None:
    missions_root = tmp_path / "missions"
    command = missions_root / "mission-steps" / "software-dev" / "plan" / "prompt.md"
    command.parent.mkdir(parents=True)
    command.write_text("plan prompt", encoding="utf-8")
    content = missions_root / "software-dev" / "templates" / "spec-template.md"
    content.parent.mkdir(parents=True)
    content.write_text("spec template", encoding="utf-8")
    mission_config = missions_root / "software-dev" / "mission.yaml"
    mission_config.write_text("name: software-dev\n", encoding="utf-8")

    resolver = CharterTemplateResolver.from_missions_root(missions_root)

    assert resolver.resolve_command_template_path("software-dev", "plan") == command
    assert resolver.resolve_content_template_path("software-dev", "spec-template.md") == content
    assert resolver.resolve_mission_config_path("software-dev") == mission_config


def test_tier_to_origin_falls_back_to_unknown_prefix() -> None:
    origin = CharterTemplateResolver._tier_to_origin(object(), "software-dev", "templates", "spec-template.md")
    assert origin == "unknown/software-dev/templates/spec-template.md"


def test_tier_to_origin_reports_org_prefix_not_unknown() -> None:
    """T008/FR-012 (DEC-008): a real ``ResolutionTier.ORG`` member is a known
    tier, distinct from the generic ``object()`` sentinel used above to test
    the fallback path in general. Before the ``ORG`` entry is added to
    ``_tier_to_origin``'s ``tier_prefix`` dict, this renders
    ``"unknown/..."`` -- the exact silent-degradation defect FR-012 fixes.
    """
    origin = CharterTemplateResolver._tier_to_origin(
        ResolutionTier.ORG, "software-dev", "templates", "spec-template.md"
    )
    assert origin == "org/software-dev/templates/spec-template.md"
