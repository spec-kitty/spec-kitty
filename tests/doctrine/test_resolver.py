"""Focused tests for doctrine-level asset resolution branches."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import charter.offering.missions as missions_module
import charter.offering.resolver as resolver_module
from charter.offering.resolver import (
    ResolutionTier,
    _resolve_asset,
    _warn_legacy_asset,
    resolve_command,
    resolve_mission,
    resolve_template,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# Note: tier equality is asserted via ``.name == .name`` rather than ``is``
# or ``==``. Under pytest ``--import-mode=importlib`` combined with
# ``pytestarch`` (which walks ``src/`` and can load ``doctrine/resolver.py``
# under alternate module names), ``ResolutionTier`` can end up defined twice
# in-process with identical members but distinct class identities. Python
# enums' ``==`` delegates to ``is`` after a type check, so cross-class
# comparison returns False even when ``.name`` / ``.value`` match. Comparing
# ``.name`` verifies the semantic invariant these tests care about
# ("resolve_* returned a PACKAGE_DEFAULT tier") without coupling to which
# of the possibly-duplicated class objects the resolver implementation
# happened to reference.


def _build_fake_repo(root: Path) -> SimpleNamespace:
    missions_root = root / "missions"
    mission_root = missions_root / "software-dev"
    (mission_root / "templates").mkdir(parents=True)
    (mission_root / "extras").mkdir(parents=True)
    (mission_root / "templates" / "spec-template.md").write_text("package template", encoding="utf-8")
    (mission_root / "command-plan.md").write_text("package command", encoding="utf-8")
    (mission_root / "mission.yaml").write_text("name: software-dev\n", encoding="utf-8")
    (mission_root / "extras" / "custom.txt").write_text("custom asset", encoding="utf-8")

    def _content_template_path(mission: str | None, name: str) -> Path:
        if mission is None:
            raise FileNotFoundError("mission arg is None")
        return mission_root / "templates" / name

    def _command_template_path(mission: str | None, name: str) -> Path:
        if mission is None:
            raise FileNotFoundError("mission arg is None")
        return mission_root / f"command-{name}.md"

    def _mission_config_path(mission: str | None) -> Path:
        if mission is None:
            raise FileNotFoundError("mission arg is None")
        return mission_root / "mission.yaml"

    return SimpleNamespace(
        _missions_root=missions_root,
        _content_template_path=_content_template_path,
        _command_template_path=_command_template_path,
        _mission_config_path=_mission_config_path,
    )


def test_is_global_runtime_configured_detects_bootstrapped_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    (home / "cache").mkdir(parents=True)
    (home / "cache" / "version.lock").write_text("3.0.0\n", encoding="utf-8")

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: home)

    assert resolver_module._is_global_runtime_configured() is True


def test_is_global_runtime_configured_handles_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_runtime_error() -> Path:
        raise RuntimeError("home unavailable")

    monkeypatch.setattr(resolver_module, "get_kittify_home", _raise_runtime_error)

    assert resolver_module._is_global_runtime_configured() is False


def test_warn_legacy_asset_emits_single_migrate_nudge_after_runtime_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(resolver_module, "_is_global_runtime_configured", lambda: True)
    resolver_module._reset_migrate_nudge()

    _warn_legacy_asset(Path("/nonexistent/spec-template.md"))
    _warn_legacy_asset(Path("/nonexistent/plan-template.md"))

    stderr = capsys.readouterr().err
    assert stderr.count("spec-kitty migrate") == 1


def test_resolve_template_and_command_use_package_default_when_global_home_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    fake_repo = _build_fake_repo(tmp_path / "package-root")

    def _raise_runtime_error() -> Path:
        raise RuntimeError("no global runtime")

    monkeypatch.setattr(resolver_module, "get_kittify_home", _raise_runtime_error)
    monkeypatch.setattr(missions_module.MissionTemplateRepository, "default", lambda: fake_repo)

    template = resolve_template("spec-template.md", project, mission="software-dev")
    command = resolve_command("plan.md", project, mission="software-dev")

    assert template.tier.name == ResolutionTier.PACKAGE_DEFAULT.name
    assert template.path.read_text(encoding="utf-8") == "package template"
    assert command.tier.name == ResolutionTier.PACKAGE_DEFAULT.name
    assert command.path.read_text(encoding="utf-8") == "package command"


def test_resolve_asset_unknown_subdir_uses_package_root_and_raises_when_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    fake_repo = _build_fake_repo(tmp_path / "package-root")

    def _raise_runtime_error() -> Path:
        raise RuntimeError("no global runtime")

    monkeypatch.setattr(resolver_module, "get_kittify_home", _raise_runtime_error)
    monkeypatch.setattr(missions_module.MissionTemplateRepository, "default", lambda: fake_repo)

    custom = _resolve_asset("custom.txt", "extras", project, mission="software-dev")
    assert custom.tier.name == ResolutionTier.PACKAGE_DEFAULT.name
    assert custom.path.read_text(encoding="utf-8") == "custom asset"

    (fake_repo._missions_root / "software-dev" / "extras" / "custom.txt").unlink()

    with pytest.raises(FileNotFoundError):
        _resolve_asset("custom.txt", "extras", project, mission="software-dev")


def test_resolve_mission_covers_all_resolution_tiers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    kittify = project / ".kittify"
    fake_home = tmp_path / "global-home"
    fake_repo = _build_fake_repo(tmp_path / "package-root")

    (kittify / "overrides" / "missions" / "software-dev").mkdir(parents=True)
    override = kittify / "overrides" / "missions" / "software-dev" / "mission.yaml"
    override.write_text("name: override\n", encoding="utf-8")

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: fake_home)
    monkeypatch.setattr(missions_module.MissionTemplateRepository, "default", lambda: fake_repo)

    result = resolve_mission("software-dev", project)
    assert result.tier.name == ResolutionTier.OVERRIDE.name
    assert result.path == override
    assert result.mission == "software-dev"

    override.unlink()
    (kittify / "missions" / "software-dev").mkdir(parents=True)
    legacy = kittify / "missions" / "software-dev" / "mission.yaml"
    legacy.write_text("name: legacy\n", encoding="utf-8")

    monkeypatch.setattr(resolver_module, "_is_global_runtime_configured", lambda: False)
    with pytest.warns(DeprecationWarning, match="mission.yaml"):
        result = resolve_mission("software-dev", project)
    assert result.tier.name == ResolutionTier.LEGACY.name
    assert result.path == legacy
    assert result.mission == "software-dev"

    legacy.unlink()
    (fake_home / "missions" / "software-dev").mkdir(parents=True)
    global_mission = fake_home / "missions" / "software-dev" / "mission.yaml"
    global_mission.write_text("name: global\n", encoding="utf-8")

    result = resolve_mission("software-dev", project)
    assert result.tier.name == ResolutionTier.GLOBAL_MISSION.name
    assert result.path == global_mission
    assert result.mission == "software-dev"

    global_mission.unlink()
    result = resolve_mission("software-dev", project)
    assert result.tier.name == ResolutionTier.PACKAGE_DEFAULT.name
    assert result.path is not None
    assert result.mission == "software-dev"

    monkeypatch.setattr(
        missions_module.MissionTemplateRepository,
        "default",
        lambda: SimpleNamespace(_mission_config_path=lambda mission: None),
    )
    with pytest.raises(FileNotFoundError):
        resolve_mission("software-dev", project)


# ---------------------------------------------------------------------------
# T017 – _resolve_asset tier precedence with full field assertions
# ---------------------------------------------------------------------------


def test_resolve_asset_tier1_override_asserts_path_tier_mission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tier-1 override result has correct path, tier, and mission."""
    project = tmp_path / "project"
    kittify = project / ".kittify"
    (kittify / "overrides" / "templates").mkdir(parents=True)
    asset = kittify / "overrides" / "templates" / "spec-template.md"
    asset.write_text("override content", encoding="utf-8")

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: tmp_path / "no-home")

    result = _resolve_asset("spec-template.md", "templates", project, mission="docs")

    assert result.tier.name == ResolutionTier.OVERRIDE.name
    assert result.path == asset
    assert result.mission == "docs"


def test_resolve_asset_tier1_mission_scoped_override_resolves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tier-1 override resolves a MISSION-SCOPED override at
    ``.kittify/overrides/missions/{mission}/{subdir}/{name}`` (e.g. the
    dogfood layout ``.kittify/overrides/missions/software-dev/command-templates/implement.md``).

    Before this fix, Tier-1 only checked the flat
    ``.kittify/overrides/{subdir}/{name}`` path, so every mission-scoped
    override was inert (never found, silently falling through to a lower
    tier or raising FileNotFoundError).
    """
    project = tmp_path / "project"
    kittify = project / ".kittify"
    mission_scoped_dir = kittify / "overrides" / "missions" / "software-dev" / "command-templates"
    mission_scoped_dir.mkdir(parents=True)
    asset = mission_scoped_dir / "implement.md"
    asset.write_text("mission-scoped override content", encoding="utf-8")

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: tmp_path / "no-home")

    result = _resolve_asset("implement.md", "command-templates", project, mission="software-dev")

    assert result.tier.name == ResolutionTier.OVERRIDE.name
    assert result.path == asset
    assert result.mission == "software-dev"


def test_resolve_asset_tier1_mission_scoped_override_wins_over_global_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both a mission-scoped and a global (non-mission-scoped) override
    exist, the more specific mission-scoped override wins."""
    project = tmp_path / "project"
    kittify = project / ".kittify"

    global_dir = kittify / "overrides" / "command-templates"
    global_dir.mkdir(parents=True)
    (global_dir / "implement.md").write_text("global override content", encoding="utf-8")

    mission_scoped_dir = kittify / "overrides" / "missions" / "software-dev" / "command-templates"
    mission_scoped_dir.mkdir(parents=True)
    mission_scoped_asset = mission_scoped_dir / "implement.md"
    mission_scoped_asset.write_text("mission-scoped override content", encoding="utf-8")

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: tmp_path / "no-home")

    result = _resolve_asset("implement.md", "command-templates", project, mission="software-dev")

    assert result.tier.name == ResolutionTier.OVERRIDE.name
    assert result.path == mission_scoped_asset
    assert result.path.read_text(encoding="utf-8") == "mission-scoped override content"


def test_resolve_asset_tier1_global_override_backward_compat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A global (non-mission-scoped) override at
    ``.kittify/overrides/{subdir}/{name}`` still resolves as Tier-1 OVERRIDE
    when no mission-scoped override exists (backward compatibility)."""
    project = tmp_path / "project"
    kittify = project / ".kittify"
    global_dir = kittify / "overrides" / "command-templates"
    global_dir.mkdir(parents=True)
    asset = global_dir / "implement.md"
    asset.write_text("global override content", encoding="utf-8")

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: tmp_path / "no-home")

    result = _resolve_asset("implement.md", "command-templates", project, mission="software-dev")

    assert result.tier.name == ResolutionTier.OVERRIDE.name
    assert result.path == asset
    assert result.mission == "software-dev"


def test_resolve_asset_tier2_legacy_asserts_path_tier_mission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tier-2 legacy result has correct path, tier, mission; warning names the path."""
    project = tmp_path / "project"
    kittify = project / ".kittify"
    (kittify / "templates").mkdir(parents=True)
    asset = kittify / "templates" / "spec-template.md"
    asset.write_text("legacy content", encoding="utf-8")

    monkeypatch.setattr(resolver_module, "_is_global_runtime_configured", lambda: False)
    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: tmp_path / "no-home")

    with pytest.warns(DeprecationWarning, match="spec-template.md"):
        result = _resolve_asset("spec-template.md", "templates", project, mission="docs")

    assert result.tier.name == ResolutionTier.LEGACY.name
    assert result.path == asset
    assert result.mission == "docs"


def test_resolve_asset_tier3_global_mission_asserts_path_tier_mission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tier-3 global-mission result has correct path, tier, and mission."""
    project = tmp_path / "project"
    project.mkdir()
    fake_home = tmp_path / "global-home"
    (fake_home / "missions" / "docs" / "templates").mkdir(parents=True)
    asset = fake_home / "missions" / "docs" / "templates" / "spec-template.md"
    asset.write_text("global-mission content", encoding="utf-8")

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: fake_home)

    result = _resolve_asset("spec-template.md", "templates", project, mission="docs")

    assert result.tier.name == ResolutionTier.GLOBAL_MISSION.name
    assert result.path == asset
    assert result.mission == "docs"


def test_resolve_asset_tier4_global_asserts_path_tier_mission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tier-4 global result has correct path, tier, and mission."""
    project = tmp_path / "project"
    project.mkdir()
    fake_home = tmp_path / "global-home"
    (fake_home / "templates").mkdir(parents=True)
    asset = fake_home / "templates" / "spec-template.md"
    asset.write_text("global content", encoding="utf-8")

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: fake_home)

    result = _resolve_asset("spec-template.md", "templates", project, mission="docs")

    assert result.tier.name == ResolutionTier.GLOBAL.name
    assert result.path == asset
    assert result.mission == "docs"


def test_resolve_asset_default_mission_is_software_dev(
    tmp_path: Path,
) -> None:
    """Calling _resolve_asset without explicit mission defaults to software-dev."""
    project = tmp_path / "project"
    kittify = project / ".kittify"
    (kittify / "overrides" / "templates").mkdir(parents=True)
    (kittify / "overrides" / "templates" / "x.md").write_text("x", encoding="utf-8")

    result = _resolve_asset("x.md", "templates", project)

    assert result.mission == "software-dev"


# ---------------------------------------------------------------------------
# T018 – _warn_legacy_asset message content and _reset_migrate_nudge exact value
# ---------------------------------------------------------------------------


def test_warn_legacy_asset_message_contains_path_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deprecation warning message contains the actual path text."""
    monkeypatch.setattr(resolver_module, "_is_global_runtime_configured", lambda: False)

    with pytest.warns(DeprecationWarning, match="spec-template.md"):
        _warn_legacy_asset(Path("/nonexistent/spec-template.md"))


def test_reset_migrate_nudge_allows_nudge_to_fire_again(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """After _reset_migrate_nudge, calling _emit_migrate_nudge emits a second nudge."""
    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: Path("/nonexistent/fake-home"))
    resolver_module._emit_migrate_nudge()
    capsys.readouterr()  # consume the first nudge
    resolver_module._reset_migrate_nudge()

    resolver_module._emit_migrate_nudge()

    stderr = capsys.readouterr().err
    assert "spec-kitty migrate" in stderr


def test_emit_migrate_nudge_message_starts_with_note(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Nudge message begins with 'Note:' (case-sensitive)."""
    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: Path("/nonexistent/fake-home"))
    resolver_module._reset_migrate_nudge()

    resolver_module._emit_migrate_nudge()

    stderr = capsys.readouterr().err
    assert "Note:" in stderr


def test_emit_migrate_nudge_suppressed_for_json_invocation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """JSON invocations must keep merged stdout/stderr streams parseable."""
    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: Path("/nonexistent/fake-home"))
    monkeypatch.setattr(sys, "argv", ["spec-kitty", "status", "--json"])
    resolver_module._reset_migrate_nudge()

    resolver_module._emit_migrate_nudge()

    assert capsys.readouterr().err == ""

    monkeypatch.setattr(sys, "argv", ["spec-kitty", "status"])
    resolver_module._emit_migrate_nudge()

    assert "spec-kitty migrate" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# T019 – resolve_template / resolve_command default mission and passthrough
# ---------------------------------------------------------------------------


def test_resolve_template_default_mission_is_software_dev(
    tmp_path: Path,
) -> None:
    """resolve_template default mission is 'software-dev'."""
    project = tmp_path / "project"
    kittify = project / ".kittify"
    (kittify / "overrides" / "templates").mkdir(parents=True)
    (kittify / "overrides" / "templates" / "t.md").write_text("t", encoding="utf-8")

    result = resolve_template("t.md", project)

    assert result.mission == "software-dev"


def test_resolve_template_passes_mission_to_resolve_asset(
    tmp_path: Path,
) -> None:
    """resolve_template passes the mission argument through to _resolve_asset."""
    project = tmp_path / "project"
    kittify = project / ".kittify"
    (kittify / "overrides" / "templates").mkdir(parents=True)
    (kittify / "overrides" / "templates" / "t.md").write_text("t", encoding="utf-8")

    result = resolve_template("t.md", project, mission="docs")

    assert result.mission == "docs"


def test_resolve_command_default_mission_is_software_dev(
    tmp_path: Path,
) -> None:
    """resolve_command default mission is 'software-dev'."""
    project = tmp_path / "project"
    kittify = project / ".kittify"
    (kittify / "overrides" / "command-templates").mkdir(parents=True)
    (kittify / "overrides" / "command-templates" / "plan.md").write_text("p", encoding="utf-8")

    result = resolve_command("plan.md", project)

    assert result.mission == "software-dev"


def test_resolve_command_passes_mission_to_resolve_asset(
    tmp_path: Path,
) -> None:
    """resolve_command passes the mission argument through to _resolve_asset."""
    project = tmp_path / "project"
    kittify = project / ".kittify"
    (kittify / "overrides" / "command-templates").mkdir(parents=True)
    (kittify / "overrides" / "command-templates" / "plan.md").write_text("p", encoding="utf-8")

    result = resolve_command("plan.md", project, mission="docs")

    assert result.mission == "docs"


def test_resolve_template_and_command_package_tier_assert_path_and_mission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Package-tier results for resolve_template and resolve_command include path and mission."""
    project = tmp_path / "project"
    project.mkdir()
    fake_repo = _build_fake_repo(tmp_path / "package-root")

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: tmp_path / "no-home")
    monkeypatch.setattr(missions_module.MissionTemplateRepository, "default", lambda: fake_repo)

    template = resolve_template("spec-template.md", project, mission="software-dev")
    command = resolve_command("plan.md", project, mission="software-dev")

    assert template.tier.name == ResolutionTier.PACKAGE_DEFAULT.name
    assert template.path is not None
    assert template.mission == "software-dev"
    assert command.tier.name == ResolutionTier.PACKAGE_DEFAULT.name
    assert command.path is not None
    assert command.mission == "software-dev"


# ---------------------------------------------------------------------------
# T007 (WP02, FR-002) – ResolutionTier.ORG exists and is re-exported by
# identity through charter.resolution, not merely by value equality.
# ---------------------------------------------------------------------------


def test_resolution_tier_org_member_exists() -> None:
    """``ResolutionTier`` gains a real ``ORG`` member (FR-002)."""
    assert hasattr(ResolutionTier, "ORG")
    assert ResolutionTier.ORG.value == "org"


def test_charter_resolution_tier_is_doctrine_resolution_tier_by_identity() -> None:
    """``charter.resolution.ResolutionTier`` is the *same class object* as
    ``charter.offering.resolver.ResolutionTier`` (a pure re-export), not a parallel
    declaration with matching member values. Value equality (``==``) would
    pass even for two distinct enum classes with identically-named/valued
    members, which is not what the re-export contract guarantees -- so this
    asserts identity (``is``) instead.
    """
    from charter.resolution import ResolutionTier as CharterResolutionTier

    assert CharterResolutionTier is ResolutionTier
    assert CharterResolutionTier.ORG is ResolutionTier.ORG


# ---------------------------------------------------------------------------
# WP03 (FR-003, FR-005) – org tier in charter.offering.resolver's _resolve_asset and
# resolve_mission. Slots between LEGACY and GLOBAL_MISSION, sourced from
# charter.offering.drg.org_pack_config.resolve_org_roots via a same-layer direct
# import (DEC-003 -- no facade needed inside the doctrine layer itself).
# ---------------------------------------------------------------------------


def _write_org_pack_config(repo_root: Path, *, pack_name: str, local_path: Path) -> None:
    """Write a canonical ``doctrine.org.packs[].local_path`` config.yaml entry."""
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        "doctrine:\n"
        "  org:\n"
        "    packs:\n"
        f"      - name: {pack_name}\n"
        f"        local_path: {local_path}\n",
        encoding="utf-8",
    )


def test_org_tier_resolves_template_in_doctrine_resolver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-003: an org-pack ``spec-template.md`` resolves at ``ResolutionTier.ORG``.

    Before this WP: no tier between LEGACY and GLOBAL_MISSION probed org-pack
    roots at all, so this fixture fell through to PACKAGE_DEFAULT (see the WP
    report for the exact pre-fix measurement).
    """
    project = tmp_path / "project"
    project.mkdir()
    org_root = tmp_path / "org-pack"
    org_template = org_root / "missions" / "software-dev" / "templates" / "spec-template.md"
    org_template.parent.mkdir(parents=True)
    org_template.write_text("org template", encoding="utf-8")

    _write_org_pack_config(project, pack_name="acme", local_path=org_root)

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: tmp_path / "no-home")

    result = resolve_template("spec-template.md", project, mission="software-dev")

    assert result.tier.name == ResolutionTier.ORG.name
    assert result.path == org_template
    assert result.mission == "software-dev"


def test_org_tier_resolves_mission_yaml_in_doctrine_resolver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-005: an org-pack ``mission.yaml`` resolves at ``ResolutionTier.ORG``,
    at the same relative position as the template case."""
    project = tmp_path / "project"
    project.mkdir()
    org_root = tmp_path / "org-pack"
    org_mission = org_root / "missions" / "software-dev" / "mission.yaml"
    org_mission.parent.mkdir(parents=True)
    org_mission.write_text("name: org\n", encoding="utf-8")

    _write_org_pack_config(project, pack_name="acme", local_path=org_root)

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: tmp_path / "no-home")

    result = resolve_mission("software-dev", project)

    assert result.tier.name == ResolutionTier.ORG.name
    assert result.path == org_mission
    assert result.mission == "software-dev"


def test_org_tier_sits_below_project_override_in_doctrine_resolver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User Story 1, Acceptance Scenario 2: a project override still wins
    over an org-pack asset -- the org tier sits below OVERRIDE, not above it."""
    project = tmp_path / "project"
    org_root = tmp_path / "org-pack"
    org_template = org_root / "missions" / "software-dev" / "templates" / "spec-template.md"
    org_template.parent.mkdir(parents=True)
    org_template.write_text("org template", encoding="utf-8")

    _write_org_pack_config(project, pack_name="acme", local_path=org_root)

    override_dir = project / ".kittify" / "overrides" / "missions" / "software-dev" / "templates"
    override_dir.mkdir(parents=True)
    override_asset = override_dir / "spec-template.md"
    override_asset.write_text("project override", encoding="utf-8")

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: tmp_path / "no-home")

    result = resolve_template("spec-template.md", project, mission="software-dev")

    assert result.tier.name == ResolutionTier.OVERRIDE.name
    assert result.path == override_asset


def test_org_tier_falls_through_to_global_mission_when_org_pack_missing_asset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A configured org pack that does not contain the requested asset is a
    miss, not an error -- resolution falls through to the next tier."""
    project = tmp_path / "project"
    project.mkdir()
    org_root = tmp_path / "org-pack"
    org_root.mkdir()  # configured, but has no missions/ subtree at all

    _write_org_pack_config(project, pack_name="acme", local_path=org_root)

    fake_home = tmp_path / "global-home"
    global_template = fake_home / "missions" / "software-dev" / "templates" / "spec-template.md"
    global_template.parent.mkdir(parents=True)
    global_template.write_text("global content", encoding="utf-8")

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: fake_home)

    result = resolve_template("spec-template.md", project, mission="software-dev")

    assert result.tier.name == ResolutionTier.GLOBAL_MISSION.name
    assert result.path == global_template


def test_no_org_packs_configured_is_a_noop_in_doctrine_resolver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NFR-005/SC-007: with zero ``doctrine.org.packs`` entries (no
    ``.kittify/config.yaml`` at all -- the overwhelmingly common case),
    resolution is byte-identical to before this WP: same path, same tier."""
    project = tmp_path / "project"
    project.mkdir()
    fake_home = tmp_path / "global-home"
    global_template = fake_home / "missions" / "software-dev" / "templates" / "spec-template.md"
    global_template.parent.mkdir(parents=True)
    global_template.write_text("global content", encoding="utf-8")

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: fake_home)

    result = resolve_template("spec-template.md", project, mission="software-dev")

    assert result.tier.name == ResolutionTier.GLOBAL_MISSION.name
    assert result.path == global_template


def test_malformed_org_config_still_resolves_package_default_in_doctrine_resolver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NFR-001(b): a malformed ``.kittify/config.yaml`` still resolves
    built-in templates, with zero org roots contributed (``load_pack_registry``'s
    pre-existing fail-soft, exercised through the new org tier -- not a new
    try/except added by this WP).

    Regression guard (pre-merge lens, mission
    ``up-org-template-fsm-01M06F9K``): resolution is a hot path that may run
    many times per invocation. A project with no readable org-pack intent
    (this config can't even be parsed) must see ZERO new warning output --
    NFR-005/SC-007 requires byte-identical behaviour, explicitly including
    "same log output, no new warnings", for a project with no org pack
    configured. Before the fix this asserted the opposite
    (``pytest.warns(UserWarning)``), codifying the regression as expected."""
    import warnings

    project = tmp_path / "project"
    kittify = project / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "config.yaml").write_text("not: [valid, doctrine.org.packs shape\n", encoding="utf-8")

    fake_repo = _build_fake_repo(tmp_path / "package-root")

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: tmp_path / "no-home")
    monkeypatch.setattr(missions_module.MissionTemplateRepository, "default", lambda: fake_repo)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = resolve_template("spec-template.md", project, mission="software-dev")

    assert caught == []

    assert result.tier.name == ResolutionTier.PACKAGE_DEFAULT.name
    assert result.path.read_text(encoding="utf-8") == "package template"


def test_declared_but_broken_org_pack_still_warns_in_doctrine_resolver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Positive case for the fix above: a config that DOES declare
    ``doctrine.org.packs`` but fails schema validation (two packs sharing
    the same ``name``) is a genuinely misconfigured org pack -- the operator
    demonstrably opted in and deserves to know it's broken. Unlike the
    unparseable-file case above, that signal must remain a loud
    ``UserWarning`` through this same resolution hot path."""
    import warnings

    project = tmp_path / "project"
    kittify = project / ".kittify"
    kittify.mkdir(parents=True)
    acme_one = tmp_path / "acme-one"
    acme_two = tmp_path / "acme-two"
    (kittify / "config.yaml").write_text(
        "doctrine:\n"
        "  org:\n"
        "    packs:\n"
        "      - name: acme\n"
        f"        local_path: {acme_one}\n"
        "      - name: acme\n"
        f"        local_path: {acme_two}\n",
        encoding="utf-8",
    )

    fake_repo = _build_fake_repo(tmp_path / "package-root")

    monkeypatch.setattr(resolver_module, "get_kittify_home", lambda: tmp_path / "no-home")
    monkeypatch.setattr(missions_module.MissionTemplateRepository, "default", lambda: fake_repo)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = resolve_template("spec-template.md", project, mission="software-dev")

    assert len(caught) == 1
    assert "Invalid org-pack config" in str(caught[0].message)
    # Fails soft to zero org roots -- resolution still proceeds.
    assert result.tier.name == ResolutionTier.PACKAGE_DEFAULT.name
