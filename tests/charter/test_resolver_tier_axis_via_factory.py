"""FR-003 (WP05): the 5-tier resolver axis routed through the charter factory.

Equivalence/regression proof, not a smoke test. Three things are asserted:

1. **Tier ordering is unchanged.** For each of the five tiers (OVERRIDE,
   LEGACY, GLOBAL_MISSION, GLOBAL, PACKAGE_DEFAULT) the factory-routed call
   returns exactly the ``ResolutionResult`` the pre-existing
   ``charter.offering.resolver`` entry point returns, walked top-down by removing the
   winning tier's file and re-resolving.
2. **The old call sites' results are preserved.** ``specify_cli/runtime/resolver.py``'s
   tier-5 hop (now calling the factory directly) still produces the paths/tiers it
   produced before the consolidation — including the
   ``SPEC_KITTY_TEMPLATE_ROOT`` override the runtime tier-5 hop honours.
3. **The tier functions were not moved or duplicated.** The factory methods
   are proven to *delegate* to ``charter.offering.resolver``'s functions (patching the
   doctrine function changes the factory's answer), which is the falsifiable
   form of "``doctrine/resolver.py`` is untouched".
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

import charter.activation.resolver as charter_resolver_module
import charter.offering.resolver as doctrine_resolver_module
import specify_cli.runtime.resolver as runtime_resolver_module
from charter.resolution import ResolutionResult, ResolutionTier
from charter.activation.pack_context import PackContext
from charter.activation.resolver import ActiveCharterService
from charter.offering.missions.repository import MissionTemplateRepository

pytestmark = pytest.mark.fast

_MISSION = "software-dev"
_CONTENT_NAME = "spec-template.md"
_COMMAND_NAME = "plan.md"
_COMMAND_STEM = "plan"


# ---------------------------------------------------------------------------
# Fixtures: a project with every tier populated
# ---------------------------------------------------------------------------


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point both resolvers' ``~/.kittify`` at a fixture directory.

    ``cache/version.lock`` is created so the legacy tier takes the
    "global runtime configured" branch and emits the one-time stderr nudge
    instead of a ``DeprecationWarning`` — keeping the tier-walk assertions
    free of warning bookkeeping without suppressing anything.
    """
    home = tmp_path / "kittify-home"
    _write(home / "cache" / "version.lock", "1\n")
    monkeypatch.setattr(doctrine_resolver_module, "get_kittify_home", lambda: home)
    monkeypatch.setattr(runtime_resolver_module, "get_kittify_home", lambda: home)
    return home


@pytest.fixture
def package_missions_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A synthetic package missions root, wired into BOTH tier-5 lookups.

    ``charter.offering.resolver``'s tier 5 uses ``MissionTemplateRepository.default()``
    while ``specify_cli/runtime/resolver.py``'s uses
    ``get_package_asset_root()``. That divergence is pre-existing, named
    deferred debt (out of FR-003's scope); this fixture pins both to the same
    root so the tier-walk compares like with like. The divergence itself is
    pinned separately in
    :func:`test_runtime_tier5_hop_keeps_its_own_package_root_authority`.
    """
    root = tmp_path / "pkg-missions"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        MissionTemplateRepository, "default_missions_root", classmethod(lambda cls: root)
    )
    monkeypatch.setattr(runtime_resolver_module, "get_package_asset_root", lambda: root)
    charter_resolver_module._mission_template_repository.cache_clear()
    return root


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / ".kittify").mkdir(parents=True, exist_ok=True)
    return project


# ---------------------------------------------------------------------------
# 1. Tier ordering: factory result == charter.offering.resolver result, tier by tier
# ---------------------------------------------------------------------------


def test_content_asset_tier_walk_matches_doctrine_resolver(
    project_dir: Path,
    fake_home: Path,
    package_missions_root: Path,
) -> None:
    """All five tiers, top-down, factory-routed == doctrine-routed."""
    tiers: list[tuple[ResolutionTier, Path]] = [
        (
            ResolutionTier.OVERRIDE,
            _write(project_dir / ".kittify" / "overrides" / "templates" / _CONTENT_NAME, "t1"),
        ),
        (ResolutionTier.LEGACY, _write(project_dir / ".kittify" / "templates" / _CONTENT_NAME, "t2")),
        (
            ResolutionTier.GLOBAL_MISSION,
            _write(fake_home / "missions" / _MISSION / "templates" / _CONTENT_NAME, "t3"),
        ),
        (ResolutionTier.GLOBAL, _write(fake_home / "templates" / _CONTENT_NAME, "t4")),
        (
            ResolutionTier.PACKAGE_DEFAULT,
            _write(package_missions_root / _MISSION / "templates" / _CONTENT_NAME, "t5"),
        ),
    ]

    for expected_tier, expected_path in tiers:
        via_factory = ActiveCharterService.resolve_content_asset(_CONTENT_NAME, project_dir, _MISSION)
        via_doctrine = doctrine_resolver_module.resolve_template(_CONTENT_NAME, project_dir, _MISSION)

        assert via_factory == ResolutionResult(
            path=expected_path, tier=expected_tier, mission=_MISSION
        )
        assert via_factory == via_doctrine
        expected_path.unlink()

    with pytest.raises(FileNotFoundError):
        ActiveCharterService.resolve_content_asset(_CONTENT_NAME, project_dir, _MISSION)


def test_command_asset_tier_walk_matches_doctrine_resolver(
    project_dir: Path,
    fake_home: Path,
    package_missions_root: Path,
) -> None:
    """Same five-tier walk for the ``command-templates`` subdir."""
    tiers: list[tuple[ResolutionTier, Path]] = [
        (
            ResolutionTier.OVERRIDE,
            _write(project_dir / ".kittify" / "overrides" / "command-templates" / _COMMAND_NAME, "c1"),
        ),
        (
            ResolutionTier.LEGACY,
            _write(project_dir / ".kittify" / "command-templates" / _COMMAND_NAME, "c2"),
        ),
        (
            ResolutionTier.GLOBAL_MISSION,
            _write(fake_home / "missions" / _MISSION / "command-templates" / _COMMAND_NAME, "c3"),
        ),
        (ResolutionTier.GLOBAL, _write(fake_home / "command-templates" / _COMMAND_NAME, "c4")),
        (
            ResolutionTier.PACKAGE_DEFAULT,
            _write(package_missions_root / _MISSION / "command-templates" / _COMMAND_NAME, "c5"),
        ),
    ]

    for expected_tier, expected_path in tiers:
        via_factory = ActiveCharterService.resolve_command_asset(_COMMAND_NAME, project_dir, _MISSION)
        via_doctrine = doctrine_resolver_module.resolve_command(_COMMAND_NAME, project_dir, _MISSION)

        assert via_factory == ResolutionResult(
            path=expected_path, tier=expected_tier, mission=_MISSION
        )
        assert via_factory == via_doctrine
        expected_path.unlink()


def test_mission_definition_tier_walk_matches_doctrine_resolver(
    project_dir: Path,
    fake_home: Path,
    package_missions_root: Path,
) -> None:
    """The mission-config chain has four tiers (no GLOBAL tier)."""
    tiers: list[tuple[ResolutionTier, Path]] = [
        (
            ResolutionTier.OVERRIDE,
            _write(project_dir / ".kittify" / "overrides" / "missions" / _MISSION / "mission.yaml", "m1"),
        ),
        (
            ResolutionTier.LEGACY,
            _write(project_dir / ".kittify" / "missions" / _MISSION / "mission.yaml", "m2"),
        ),
        (
            ResolutionTier.GLOBAL_MISSION,
            _write(fake_home / "missions" / _MISSION / "mission.yaml", "m3"),
        ),
        (
            ResolutionTier.PACKAGE_DEFAULT,
            _write(package_missions_root / _MISSION / "mission.yaml", "m4"),
        ),
    ]

    for expected_tier, expected_path in tiers:
        via_factory = ActiveCharterService.resolve_mission_definition(_MISSION, project_dir)
        via_doctrine = doctrine_resolver_module.resolve_mission(_MISSION, project_dir)

        assert via_factory == ResolutionResult(
            path=expected_path, tier=expected_tier, mission=_MISSION
        )
        assert via_factory == via_doctrine
        expected_path.unlink()

    with pytest.raises(FileNotFoundError):
        ActiveCharterService.resolve_mission_definition(_MISSION, project_dir)


# ---------------------------------------------------------------------------
# 2. The retargeted call sites produce their pre-consolidation results
# ---------------------------------------------------------------------------


def test_package_default_paths_match_the_retired_resolver_calls(tmp_path: Path) -> None:
    """Factory tier-5 lookups land on the package-default paths.

    These are the exact lookups ``specify_cli/runtime/resolver.py`` makes for
    tier 5; the factory must answer with the package-default command, content,
    and mission-config paths for the given root.
    """
    missions_root = tmp_path / "missions"
    command = _write(missions_root / "mission-steps" / _MISSION / _COMMAND_STEM / "prompt.md", "prompt")
    content = _write(missions_root / _MISSION / "templates" / _CONTENT_NAME, "spec")
    mission_config = _write(missions_root / _MISSION / "mission.yaml", f"name: {_MISSION}\n")
    charter_resolver_module._mission_template_repository.cache_clear()

    assert (
        ActiveCharterService.resolve_package_default_asset_path(
            missions_root=missions_root, mission=_MISSION, subdir="command-templates", name=_COMMAND_NAME
        )
        == command
    )
    assert (
        ActiveCharterService.resolve_package_default_asset_path(
            missions_root=missions_root, mission=_MISSION, subdir="templates", name=_CONTENT_NAME
        )
        == content
    )
    assert (
        ActiveCharterService.resolve_package_default_mission_config_path(
            missions_root=missions_root, mission=_MISSION
        )
        == mission_config
    )


def test_package_default_asset_path_unknown_subdir_and_misses(tmp_path: Path) -> None:
    """The literal-path fallback and the absent-asset paths both degrade to ``None``."""
    missions_root = tmp_path / "missions"
    other = _write(missions_root / _MISSION / "actions" / "index.yaml", "x")
    charter_resolver_module._mission_template_repository.cache_clear()

    assert (
        ActiveCharterService.resolve_package_default_asset_path(
            missions_root=missions_root, mission=_MISSION, subdir="actions", name="index.yaml"
        )
        == other
    )
    assert (
        ActiveCharterService.resolve_package_default_asset_path(
            missions_root=missions_root, mission=_MISSION, subdir="actions", name="absent.yaml"
        )
        is None
    )
    assert (
        ActiveCharterService.resolve_package_default_asset_path(
            missions_root=missions_root, mission=_MISSION, subdir="templates", name="absent.md"
        )
        is None
    )
    assert (
        ActiveCharterService.resolve_package_default_mission_config_path(
            missions_root=missions_root, mission="no-such-mission"
        )
        is None
    )


def test_runtime_tier5_hop_resolves_all_three_asset_shapes_via_the_factory(
    project_dir: Path,
    fake_home: Path,
    package_missions_root: Path,
) -> None:
    """``specify_cli.runtime.resolver`` tier 5 now resolves via the factory.

    Its own tiers 1-4 stay in place (deferred debt); only the tier-5 hop is
    charter-mediated, and it must still land on the package default for all
    three asset shapes.
    """
    content = _write(package_missions_root / _MISSION / "templates" / _CONTENT_NAME, "pkg content")
    command = _write(package_missions_root / _MISSION / "command-templates" / _COMMAND_NAME, "pkg cmd")
    mission_config = _write(package_missions_root / _MISSION / "mission.yaml", "name: sd\n")
    charter_resolver_module._mission_template_repository.cache_clear()

    assert runtime_resolver_module.resolve_template(
        _CONTENT_NAME, project_dir, _MISSION
    ) == ResolutionResult(path=content, tier=ResolutionTier.PACKAGE_DEFAULT, mission=_MISSION)
    assert runtime_resolver_module.resolve_command(
        _COMMAND_NAME, project_dir, _MISSION
    ) == ResolutionResult(path=command, tier=ResolutionTier.PACKAGE_DEFAULT, mission=_MISSION)
    assert runtime_resolver_module.resolve_mission(_MISSION, project_dir) == ResolutionResult(
        path=mission_config, tier=ResolutionTier.PACKAGE_DEFAULT, mission=_MISSION
    )


def test_runtime_tier5_hop_keeps_its_own_package_root_authority(
    project_dir: Path,
    fake_home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tier 5 still reads ``get_package_asset_root()``, not the doctrine default.

    The behaviour the consolidation had to preserve: passing ``missions_root``
    into the factory's tier-5 methods (rather than letting them call
    ``MissionTemplateRepository.default()`` as ``doctrine/resolver.py`` does)
    is what keeps the runtime caller's ``SPEC_KITTY_TEMPLATE_ROOT``-driven root
    authoritative. Hard-wiring the doctrine default would have silently
    redirected every runtime tier-5 lookup.
    """
    runtime_root = tmp_path / "runtime-pkg"
    offering_root = tmp_path / "doctrine-pkg"
    expected = _write(runtime_root / _MISSION / "templates" / _CONTENT_NAME, "runtime root wins")
    _write(offering_root / _MISSION / "templates" / _CONTENT_NAME, "doctrine default")
    monkeypatch.setattr(runtime_resolver_module, "get_package_asset_root", lambda: runtime_root)
    monkeypatch.setattr(
        MissionTemplateRepository, "default_missions_root", classmethod(lambda cls: offering_root)
    )
    charter_resolver_module._mission_template_repository.cache_clear()

    assert runtime_resolver_module.resolve_template(
        _CONTENT_NAME, project_dir, _MISSION
    ) == ResolutionResult(path=expected, tier=ResolutionTier.PACKAGE_DEFAULT, mission=_MISSION)


# ---------------------------------------------------------------------------
# 3. Structural guards: delegation, not relocation; ungated by design
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("factory_method", "doctrine_symbol"),
    [
        ("resolve_content_asset", "_offering_resolve_template"),
        ("resolve_command_asset", "_offering_resolve_command"),
        ("resolve_mission_definition", "_offering_resolve_mission"),
    ],
)
def test_factory_methods_delegate_to_doctrine_tier_functions(
    factory_method: str,
    doctrine_symbol: str,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Patching the doctrine tier function changes the factory's answer.

    This is the falsifiable form of "``doctrine/resolver.py``'s tier functions
    stay put": the factory holds no copy of the tier logic, so intercepting
    the doctrine function is sufficient to intercept the factory.
    """
    marker = ResolutionResult(
        path=project_dir / "marker", tier=ResolutionTier.LEGACY, mission="marker-mission"
    )
    monkeypatch.setattr(charter_resolver_module, doctrine_symbol, lambda *a, **k: marker)

    method = getattr(ActiveCharterService, factory_method)
    if factory_method == "resolve_mission_definition":
        assert method(_MISSION, project_dir) is marker
    else:
        assert method(_CONTENT_NAME, project_dir, _MISSION) is marker


#: A project config that deactivates every kind but directives (so
#: ``templates`` is NOT an activated kind) while staying a valid config.
_TEMPLATES_DEACTIVATED_CONFIG = (
    "activated_kinds:\n  - directives\nmission_type_activations:\n  - software-dev\n"
)


def _override_content(project_dir: Path) -> tuple[Path, ResolutionResult, ResolutionResult]:
    path = _write(project_dir / ".kittify" / "overrides" / "templates" / _CONTENT_NAME, "o")
    return (
        path,
        ActiveCharterService.resolve_content_asset(_CONTENT_NAME, project_dir, _MISSION),
        doctrine_resolver_module.resolve_template(_CONTENT_NAME, project_dir, _MISSION),
    )


def _override_command(project_dir: Path) -> tuple[Path, ResolutionResult, ResolutionResult]:
    path = _write(project_dir / ".kittify" / "overrides" / "command-templates" / _COMMAND_NAME, "o")
    return (
        path,
        ActiveCharterService.resolve_command_asset(_COMMAND_NAME, project_dir, _MISSION),
        doctrine_resolver_module.resolve_command(_COMMAND_NAME, project_dir, _MISSION),
    )


def _override_mission(project_dir: Path) -> tuple[Path, ResolutionResult, ResolutionResult]:
    path = _write(project_dir / ".kittify" / "overrides" / "missions" / _MISSION / "mission.yaml", "o")
    return (
        path,
        ActiveCharterService.resolve_mission_definition(_MISSION, project_dir),
        doctrine_resolver_module.resolve_mission(_MISSION, project_dir),
    )


@pytest.mark.parametrize(
    "resolve_override",
    [_override_content, _override_command, _override_mission],
    ids=["content", "command", "mission"],
)
def test_tier_axis_is_ungated_by_activation_state(
    resolve_override: Callable[[Path], tuple[Path, ResolutionResult, ResolutionResult]],
    project_dir: Path,
    fake_home: Path,
    package_missions_root: Path,
) -> None:
    """The tier axis has no activation concept: a project that deactivates
    ``templates`` still resolves every asset shape exactly like the doctrine
    tier functions do.
    """
    _write(project_dir / ".kittify" / "config.yaml", _TEMPLATES_DEACTIVATED_CONFIG)
    # Assumption: the config really does deactivate templates.
    assert "templates" not in PackContext.from_config(project_dir).activated_kinds

    override_path, via_factory, via_doctrine = resolve_override(project_dir)

    assert via_factory == ResolutionResult(
        path=override_path, tier=ResolutionTier.OVERRIDE, mission=_MISSION
    )
    assert via_factory == via_doctrine


def test_mission_template_repository_cache_reuses_one_instance(tmp_path: Path) -> None:
    """The relocated ``lru_cache`` still amortizes repeated tier-5 lookups."""
    charter_resolver_module._mission_template_repository.cache_clear()
    first = charter_resolver_module._mission_template_repository(str(tmp_path))
    second = charter_resolver_module._mission_template_repository(str(tmp_path))
    other = charter_resolver_module._mission_template_repository(str(tmp_path / "other"))

    assert first is second
    assert first is not other
