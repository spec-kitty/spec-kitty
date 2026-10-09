"""Tests for doctrine template discovery + DRG addressing (WP18, FR-033/034).

Covers:
- T077 discovery enumerates built-in + mission templates with tier annotation;
  cross-mission same-named templates are distinct refs; multi-tier dedupes to
  the highest-precedence tier.
- T078 minted DRG nodes carry ``template:<mission>/<name>`` URNs; cross-mission
  duplicates mint distinct nodes.
- T079 resolution by template ID respects the 5-tier precedence.

Tier equality is asserted via ``.name`` rather than ``is``/``==`` for the same
reason documented in ``test_resolver.py``: under ``--import-mode=importlib`` the
``ResolutionTier`` enum can be loaded twice with distinct class identities.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.models import NodeKind
from charter.offering.resolver import ResolutionTier
from charter.offering.template_catalog import (
    TemplateRef,
    TierRoot,
    discover_templates,
    resolve_template_by_id,
    template_id_for,
    template_node,
    template_nodes,
    template_urn,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_template(missions_root: Path, mission: str, subdir: str, name: str, body: str) -> Path:
    path = missions_root / mission / subdir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


@pytest.fixture
def package_root(tmp_path: Path) -> Path:
    """A package-tier missions root with two missions, one shared template name."""
    root = tmp_path / "pkg" / "missions"
    _make_template(root, "software-dev", "templates", "spec-template.md", "pkg sw spec")
    _make_template(root, "software-dev", "templates", "plan-template.md", "pkg sw plan")
    _make_template(root, "software-dev", "command-templates", "implement.md", "pkg sw impl")
    # README must be filtered out.
    _make_template(root, "software-dev", "templates", "README.md", "readme")
    # documentation mission has a same-named ``spec-template.md`` + a nested one.
    _make_template(root, "documentation", "templates", "spec-template.md", "pkg doc spec")
    _make_template(root, "documentation", "templates", "divio/tutorial.md", "pkg doc tutorial")
    return root


# ---------------------------------------------------------------------------
# T077 -- discovery surface
# ---------------------------------------------------------------------------


def test_discovery_enumerates_with_tier_annotation(package_root: Path) -> None:
    roots = [TierRoot(tier=ResolutionTier.PACKAGE_DEFAULT, missions_root=package_root)]
    refs = discover_templates(tier_roots=roots)

    ids = {r.template_id for r in refs}
    assert "software-dev/spec-template.md" in ids
    assert "software-dev/plan-template.md" in ids
    assert "software-dev/implement.md" in ids  # command-template discovered
    assert "documentation/spec-template.md" in ids
    # Nested template discovered recursively.
    assert "documentation/tutorial.md" in ids
    # README filtered out.
    assert "software-dev/README.md" not in ids

    for ref in refs:
        assert ref.tier.name == ResolutionTier.PACKAGE_DEFAULT.name
        assert ref.path.is_file()


def test_discovery_disambiguates_same_name_across_missions(package_root: Path) -> None:
    roots = [TierRoot(tier=ResolutionTier.PACKAGE_DEFAULT, missions_root=package_root)]
    refs = discover_templates(tier_roots=roots)

    spec_refs = [r for r in refs if r.name == "spec-template.md"]
    missions = {r.mission for r in spec_refs}
    assert missions == {"software-dev", "documentation"}
    # Distinct mission-qualified IDs.
    assert {r.template_id for r in spec_refs} == {
        "software-dev/spec-template.md",
        "documentation/spec-template.md",
    }


def test_discovery_dedupes_multi_tier_to_highest_precedence(
    tmp_path: Path, package_root: Path
) -> None:
    override_root = tmp_path / "override" / "missions"
    _make_template(override_root, "software-dev", "templates", "spec-template.md", "override spec")

    roots = [
        TierRoot(tier=ResolutionTier.OVERRIDE, missions_root=override_root),
        TierRoot(tier=ResolutionTier.PACKAGE_DEFAULT, missions_root=package_root),
    ]
    refs = discover_templates(tier_roots=roots)

    spec_sw = [r for r in refs if r.template_id == "software-dev/spec-template.md"]
    assert len(spec_sw) == 1  # (dedup collapses duplicate refs to one)
    assert {r.tier.name for r in spec_sw} == {ResolutionTier.OVERRIDE.name}
    assert spec_sw[0].tier.name == ResolutionTier.OVERRIDE.name
    assert spec_sw[0].path.read_text(encoding="utf-8") == "override spec"


def test_discovery_handles_missing_root(tmp_path: Path) -> None:
    roots = [TierRoot(tier=ResolutionTier.GLOBAL, missions_root=tmp_path / "does-not-exist")]
    assert discover_templates(tier_roots=roots) == []


def test_discovery_output_is_deterministic(package_root: Path) -> None:
    roots = [TierRoot(tier=ResolutionTier.PACKAGE_DEFAULT, missions_root=package_root)]
    first = discover_templates(tier_roots=roots)
    second = discover_templates(tier_roots=roots)
    assert [r.template_id for r in first] == [r.template_id for r in second]
    assert [r.template_id for r in first] == sorted(r.template_id for r in first)


# ---------------------------------------------------------------------------
# T078 -- DRG template nodes
# ---------------------------------------------------------------------------


def test_template_node_urn_format(package_root: Path) -> None:
    roots = [TierRoot(tier=ResolutionTier.PACKAGE_DEFAULT, missions_root=package_root)]
    refs = discover_templates(tier_roots=roots)
    ref = next(r for r in refs if r.template_id == "software-dev/spec-template.md")

    node = template_node(ref)
    assert node.kind == NodeKind.TEMPLATE
    assert node.urn == "template:software-dev/spec-template.md"
    assert node.label == "software-dev/spec-template.md"


def test_template_urn_helper() -> None:
    assert template_urn(template_id_for("software-dev", "spec-template.md")) == (
        "template:software-dev/spec-template.md"
    )


def test_cross_mission_nodes_are_distinct(package_root: Path) -> None:
    roots = [TierRoot(tier=ResolutionTier.PACKAGE_DEFAULT, missions_root=package_root)]
    refs = discover_templates(tier_roots=roots)
    spec_refs = [r for r in refs if r.name == "spec-template.md"]

    nodes = template_nodes(spec_refs)
    urns = {n.urn for n in nodes}
    assert urns == {
        "template:software-dev/spec-template.md",
        "template:documentation/spec-template.md",
    }


def test_template_nodes_validate_as_drg_nodes(package_root: Path) -> None:
    roots = [TierRoot(tier=ResolutionTier.PACKAGE_DEFAULT, missions_root=package_root)]
    refs = discover_templates(tier_roots=roots)
    # Every minted node must pass DRGNode's URN/kind validator (prefix==kind).
    for node in template_nodes(refs):
        assert node.urn.startswith("template:")
        assert node.kind == NodeKind.TEMPLATE


# ---------------------------------------------------------------------------
# T079 -- resolution by template ID
# ---------------------------------------------------------------------------


def _project_with_override_and_legacy(tmp_path: Path) -> Path:
    """Build a project dir whose override tier wins over legacy for a template."""
    project = tmp_path / "project"
    overrides = project / ".kittify" / "overrides" / "templates"
    overrides.mkdir(parents=True)
    (overrides / "spec-template.md").write_text("OVERRIDE WINS", encoding="utf-8")

    legacy = project / ".kittify" / "templates"
    legacy.mkdir(parents=True)
    (legacy / "spec-template.md").write_text("legacy loses", encoding="utf-8")
    return project


def test_resolve_by_id_respects_tier_precedence(tmp_path: Path) -> None:
    project = _project_with_override_and_legacy(tmp_path)
    roots = [
        TierRoot(
            tier=ResolutionTier.OVERRIDE,
            missions_root=tmp_path / "unused",
            project_dir=project,
        )
    ]
    result = resolve_template_by_id("software-dev/spec-template.md", tier_roots=roots)
    assert result.tier.name == ResolutionTier.OVERRIDE.name
    assert result.path.read_text(encoding="utf-8") == "OVERRIDE WINS"
    assert result.mission == "software-dev"


def test_resolve_by_id_falls_through_to_package_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No project dir supplied -> override/legacy skipped. Point the global home
    # at an empty dir so the global-mission/global tiers are also skipped, and
    # the package default wins for a real shipped template
    # (``spec-template.md`` exists in software-dev).
    empty_home = tmp_path / "empty-home"
    empty_home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(empty_home))

    roots = [TierRoot(tier=ResolutionTier.PACKAGE_DEFAULT, missions_root=tmp_path / "unused")]
    result = resolve_template_by_id("software-dev/spec-template.md", tier_roots=roots)
    assert result.tier.name == ResolutionTier.PACKAGE_DEFAULT.name
    assert result.mission == "software-dev"
    assert result.path.is_file()


def test_resolve_by_id_rejects_unqualified_id(tmp_path: Path) -> None:
    roots = [TierRoot(tier=ResolutionTier.PACKAGE_DEFAULT, missions_root=tmp_path)]
    with pytest.raises(ValueError, match="<mission>/<name>"):
        resolve_template_by_id("spec-template.md", tier_roots=roots)
    with pytest.raises(ValueError, match="<mission>/<name>"):
        resolve_template_by_id("software-dev/", tier_roots=roots)


def test_resolve_by_id_raises_for_missing_template(tmp_path: Path) -> None:
    roots = [TierRoot(tier=ResolutionTier.PACKAGE_DEFAULT, missions_root=tmp_path)]
    with pytest.raises(FileNotFoundError):
        resolve_template_by_id("software-dev/does-not-exist.md", tier_roots=roots)


# ---------------------------------------------------------------------------
# Layering guard (zero upward dependency)
# ---------------------------------------------------------------------------


def test_template_catalog_has_no_upward_imports() -> None:
    """charter.offering.template_catalog must not import charter's activation layer.

    Mission ``charter-code-topology-01M152G1`` relocated the top-level
    ``doctrine`` package to ``src/charter/offering``, so an in-layer sibling
    import (``charter.offering.resolver`` / ``charter.offering.drg.models``)
    now textually starts with ``"charter"`` too. Import lines are matched
    per-line and exempted when they target ``charter.offering`` itself
    (same self-reference exemption as
    ``test_charter_offering_does_not_import_activation.py``); any import of
    ``charter.<non-offering>`` still fails this test.
    """
    import charter.offering.template_catalog as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("import charter.offering") or stripped.startswith("from charter.offering"):
            continue
        assert not stripped.startswith("import charter"), f"upward import: {line!r}"
        assert not stripped.startswith("from charter"), f"upward import: {line!r}"
        assert "import specify_cli" not in stripped
        assert "from specify_cli" not in stripped


def test_template_ref_is_frozen() -> None:
    ref = TemplateRef(
        template_id="software-dev/x.md",
        mission="software-dev",
        name="x.md",
        tier=ResolutionTier.PACKAGE_DEFAULT,
        path=Path("/nonexistent/x.md"),
    )
    with pytest.raises(Exception):  # noqa: B017 -- FrozenInstanceError
        ref.mission = "other"  # type: ignore[misc]
