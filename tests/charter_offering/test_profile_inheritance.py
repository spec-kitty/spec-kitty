"""Tests for profile inheritance resolution and matching integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.agent_profiles.profile import TaskContext
from charter.offering.agent_profiles.repository import AgentProfileRepository
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]


def _lineage_drg(*pairs: tuple[str, str]) -> DRGGraph:
    """Build a DRG with ``specializes_from`` edges for ``(child, parent)`` pairs.

    Lineage is authored as DRG edges (FR-002 / WP05); the retired
    ``specializes-from`` profile field is gone.
    """
    ids = {pid for pair in pairs for pid in pair}
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-06-02T00:00:00Z",
        generated_by="test_profile_inheritance",
        nodes=[DRGNode(urn=f"agent_profile:{pid}", kind=NodeKind.AGENT_PROFILE) for pid in sorted(ids)],
        edges=[
            DRGEdge(
                source=f"agent_profile:{child}",
                target=f"agent_profile:{parent}",
                relation=Relation.SPECIALIZES_FROM,
            )
            for child, parent in pairs
        ],
    )



@pytest.fixture
def inheritance_repo(tmp_path: Path) -> AgentProfileRepository:
    shipped = tmp_path / "built-in"
    shipped.mkdir()

    (shipped / "implementer.agent.yaml").write_text(
        """profile-id: implementer
name: Implementer
roles:
  - implementer
purpose: Build missions
routing-priority: 70
specialization:
  primary-focus: implementation
specialization-context:
  languages: [python, javascript]
  frameworks: [django]
  domain-keywords: [api]
collaboration:
  handoff-to: [reviewer]
mode-defaults:
  - mode: analysis
    description: Analyze first
    use-case: plan
initialization-declaration: hello
""",
        encoding="utf-8",
    )

    (shipped / "python-pedro.agent.yaml").write_text(
        """profile-id: python-pedro
name: Python Pedro
roles:
  - implementer
purpose: Python specialist
specialization:
  primary-focus: python implementation
specialization-context:
  languages: [python]
mode-defaults:
  - mode: creative
    description: explore
    use-case: spike
""",
        encoding="utf-8",
    )

    (shipped / "backend-pedro.agent.yaml").write_text(
        """profile-id: backend-pedro
name: Backend Pedro
roles:
  - implementer
purpose: Backend specialist
specialization:
  primary-focus: backend apis
""",
        encoding="utf-8",
    )

    drg = _lineage_drg(("python-pedro", "implementer"), ("backend-pedro", "python-pedro"))
    return AgentProfileRepository(built_in_dir=shipped, project_dir=None, drg=drg)


def test_resolve_profile_inherits_missing_fields(inheritance_repo: AgentProfileRepository) -> None:
    resolved = inheritance_repo.resolve_profile("python-pedro")

    assert resolved.collaboration.handoff_to == ["reviewer"]
    assert resolved.specialization_context is not None
    assert resolved.specialization_context.languages == ["python"]
    assert resolved.specialization_context.frameworks == ["django"]


def test_resolve_profile_supports_multi_level_chain(inheritance_repo: AgentProfileRepository) -> None:
    resolved = inheritance_repo.resolve_profile("backend-pedro")

    assert resolved.specialization.primary_focus == "backend apis"
    assert resolved.specialization_context is not None
    assert resolved.specialization_context.languages == ["python"]
    assert resolved.specialization_context.frameworks == ["django"]


def test_resolve_profile_missing_parent_raises_key_error(tmp_path: Path) -> None:
    shipped = tmp_path / "built-in"
    shipped.mkdir()
    (shipped / "orphan.agent.yaml").write_text(
        """profile-id: orphan
name: Orphan
roles:
  - implementer
purpose: orphan
specialization:
  primary-focus: orphan
""",
        encoding="utf-8",
    )

    repo = AgentProfileRepository(
        built_in_dir=shipped, project_dir=None, drg=_lineage_drg(("orphan", "missing-parent"))
    )

    with pytest.raises(KeyError, match="missing-parent"):
        repo.resolve_profile("orphan")


def test_resolve_profile_cycle_raises(tmp_path: Path) -> None:
    shipped = tmp_path / "built-in"
    shipped.mkdir()
    (shipped / "a.agent.yaml").write_text(
        """profile-id: a
name: A
roles:
  - implementer
purpose: a
specialization:
  primary-focus: a
""",
        encoding="utf-8",
    )
    (shipped / "b.agent.yaml").write_text(
        """profile-id: b
name: B
roles:
  - implementer
purpose: b
specialization:
  primary-focus: b
""",
        encoding="utf-8",
    )

    repo = AgentProfileRepository(
        built_in_dir=shipped, project_dir=None, drg=_lineage_drg(("a", "b"), ("b", "a"))
    )

    with pytest.raises(ValueError, match="Cycle detected"):
        repo.resolve_profile("a")


def test_matching_uses_resolved_profile_context(inheritance_repo: AgentProfileRepository) -> None:
    context = TaskContext(language="python", framework="django", complexity="high")
    best = inheritance_repo.find_best_match(context)

    assert best is not None
    # backend-pedro inherits django framework through the chain and has the most specific focus.
    assert best.profile_id in {"python-pedro", "backend-pedro"}


# ── US-6 acceptance tests ─────────────────────────────────────────────────────


@pytest.fixture
def us6_repo(tmp_path: Path) -> AgentProfileRepository:
    """Fixture for US-6 inheritance and excluding scenarios."""
    shipped = tmp_path / "built-in"
    shipped.mkdir()

    (shipped / "base.agent.yaml").write_text(
        """profile-id: base
name: Base
roles:
  - implementer
purpose: Base profile
routing-priority: 50
specialization:
  primary-focus: general
directive-references:
  - code: "D010"
    name: Directive D010
    rationale: first base directive
  - code: "D020"
    name: Directive D020
    rationale: second base directive
capabilities:
  - base-cap-1
  - base-cap-2
mode-defaults:
  - mode: analysis
    description: Analyze
    use-case: plan
initialization-declaration: hello
""",
        encoding="utf-8",
    )

    (shipped / "child.agent.yaml").write_text(
        """profile-id: child
name: Child
roles:
  - implementer
purpose: Child profile
specialization:
  primary-focus: child focus
directive-references:
  - code: "D030"
    name: Directive D030
    rationale: child directive
capabilities:
  - child-cap-1
mode-defaults:
  - mode: creative
    description: Explore
    use-case: spike
""",
        encoding="utf-8",
    )

    (shipped / "grandchild.agent.yaml").write_text(
        """profile-id: grandchild
name: Grandchild
roles:
  - implementer
purpose: Grandchild profile
specialization:
  primary-focus: grandchild focus
""",
        encoding="utf-8",
    )

    (shipped / "child-excluding.agent.yaml").write_text(
        """profile-id: child-excluding
name: Child Excluding
roles:
  - implementer
purpose: Child that excludes a directive value
specialization:
  primary-focus: excluding focus
directive-references:
  - code: "D030"
    name: Directive D030
    rationale: child directive
excluding:
  directive-references:
    - "D010"
""",
        encoding="utf-8",
    )

    drg = _lineage_drg(
        ("child", "base"),
        ("grandchild", "child"),
        ("child-excluding", "base"),
    )
    return AgentProfileRepository(built_in_dir=shipped, project_dir=None, drg=drg)


def test_unspecified_fields_inherited(us6_repo: AgentProfileRepository) -> None:
    """US-6 S1: child with specializes-from=base, unspecified fields come from parent."""
    resolved = us6_repo.resolve_profile("child")

    # initialization-declaration not set on child → inherited from base
    assert resolved.initialization_declaration == "hello"
    # routing-priority not set on child → inherited from base
    assert resolved.routing_priority == 50


def test_child_overrides_scalar_field(us6_repo: AgentProfileRepository) -> None:
    """US-6 S2: child's primary_focus overrides parent's."""
    resolved = us6_repo.resolve_profile("child")

    assert resolved.specialization.primary_focus == "child focus"


def test_list_fields_merged_by_union(us6_repo: AgentProfileRepository) -> None:
    """US-6 S3: child adding one directive → resolved has parent + child directives, no duplicates."""
    resolved = us6_repo.resolve_profile("child")

    directive_codes = [ref.code for ref in resolved.directive_references]
    # Parent has D010 and D020; child adds D030 → all three present
    assert "D010" in directive_codes
    assert "D020" in directive_codes
    assert "D030" in directive_codes
    assert set(directive_codes) == {"D010", "D020", "D030"}

    cap_names = resolved.capabilities
    # Parent has base-cap-1, base-cap-2; child adds child-cap-1 → all three present
    assert "base-cap-1" in cap_names
    assert "base-cap-2" in cap_names
    assert "child-cap-1" in cap_names
    assert set(cap_names) == {"base-cap-1", "base-cap-2", "child-cap-1"}


def test_excluding_value_removed(us6_repo: AgentProfileRepository) -> None:
    """US-6 S4: excluding: {directive-references: [D010]} → D010 omitted from merged directives."""
    resolved = us6_repo.resolve_profile("child-excluding")

    directive_codes = [ref.code for ref in resolved.directive_references]
    # D020 from parent still present; D010 excluded; D030 from child
    assert "D010" not in directive_codes
    assert "D020" in directive_codes
    assert "D030" in directive_codes


def test_multi_level_chain(us6_repo: AgentProfileRepository) -> None:
    """US-6 S5: grandchild → child → base; inheritance cascades correctly."""
    resolved = us6_repo.resolve_profile("grandchild")

    # grandchild overrides primary_focus
    assert resolved.specialization.primary_focus == "grandchild focus"
    # initialization-declaration comes from base (2 levels up)
    assert resolved.initialization_declaration == "hello"
    # directive-references merged across all 3 levels (base + child → grandchild inherits)
    directive_codes = [ref.code for ref in resolved.directive_references]
    assert "D010" in directive_codes
    assert "D020" in directive_codes
    assert "D030" in directive_codes


def test_missing_parent_raises_key_error(tmp_path: Path) -> None:
    """US-6 S6: profile with specializes-from=nonexistent → KeyError with clear message."""
    shipped = tmp_path / "built-in"
    shipped.mkdir()
    (shipped / "orphan.agent.yaml").write_text(
        """profile-id: orphan
name: Orphan
roles:
  - implementer
purpose: orphan
specialization:
  primary-focus: orphan
""",
        encoding="utf-8",
    )

    repo = AgentProfileRepository(
        built_in_dir=shipped, project_dir=None, drg=_lineage_drg(("orphan", "nonexistent-parent"))
    )

    with pytest.raises(KeyError, match="nonexistent-parent"):
        repo.resolve_profile("orphan")


# ---------------------------------------------------------------------------
# WP09: Generic profile specialization tactic inheritance tests (FR-008)
# ---------------------------------------------------------------------------

# Post-relocation the shipped agent profiles live flattened under
# ``packs/built-in/agent_profiles/`` (the old ``src/charter/offering/agent_profiles/built-in/``
# tree is emptied). Reading the old path here silently returned zero profiles,
# so every assertion in this module passed VACUOUSLY (false-green; FR-008).
_SHIPPED_PROFILE_DIR = Path(__file__).parent.parent.parent / "packs" / "built-in" / "agent_profiles"


@pytest.fixture(scope="module")
def shipped_repo() -> AgentProfileRepository:
    """Load the real shipped profiles — used for tactic-inheritance invariant checks."""
    return AgentProfileRepository(built_in_dir=_SHIPPED_PROFILE_DIR, project_dir=None)


@pytest.mark.doctrine
@pytest.mark.fast
def test_resolved_specialist_profiles_include_base_tactic_references(
    shipped_repo: AgentProfileRepository,
) -> None:
    """
    Generic invariant: for every shipped profile P that specializes-from base B,
    resolve_profile(P) must include every tactic reference that B declares.

    This is a genuine regression guard: if 'tactic-references' is removed from
    _LIST_FIELDS, specialists that declare their own tactic refs will silently
    drop the base's refs. If the runtime AgentProfile model stops carrying
    tactic_references, this test also fails instead of passing by inspecting raw
    YAML only.

    Passes with zero specialization pairs. Does NOT hardcode profile or tactic IDs.
    """
    profiles = {p.profile_id: p for p in shipped_repo.list_all()}

    violations: list[str] = []
    for profile_id in profiles:
        # Lineage parent is resolved from the DRG (FR-002 / WP05), not a field.
        ancestors = shipped_repo.get_ancestors(profile_id)
        base_id = ancestors[0] if ancestors else None
        if not base_id or base_id not in profiles:
            continue

        base = shipped_repo.resolve_profile(base_id)
        base_tactic_ids = {
            ref.id for ref in base.tactic_references
        }
        if not base_tactic_ids:
            continue

        resolved = shipped_repo.resolve_profile(profile_id)
        resolved_tactic_ids = {ref.id for ref in resolved.tactic_references}

        for missing_id in base_tactic_ids - resolved_tactic_ids:
            violations.append(
                f"Profile '{profile_id}' (specializes-from '{base_id}'): "
                f"tactic '{missing_id}' absent after resolve_profile() — "
                f"verify 'tactic-references' is in _LIST_FIELDS in repository.py"
            )

    assert not violations, (
        f"Found {len(violations)} tactic inheritance violation(s):\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


@pytest.mark.doctrine
@pytest.mark.fast
def test_tactic_inheritance_passes_with_no_specialization_pairs(
    tmp_path: Path,
) -> None:
    """NFR-004: test must pass even when no profiles have specializes-from."""
    shipped = tmp_path / "built-in"
    shipped.mkdir()

    (shipped / "base.agent.yaml").write_text(
        """profile-id: base
name: Base
roles: [implementer]
purpose: Base agent
specialization:
  primary-focus: base work
""",
        encoding="utf-8",
    )
    (shipped / "standalone.agent.yaml").write_text(
        """profile-id: standalone
name: Standalone
roles: [implementer]
purpose: Standalone agent with no specialization
specialization:
  primary-focus: standalone work
""",
        encoding="utf-8",
    )

    repo = AgentProfileRepository(built_in_dir=shipped, project_dir=None)
    profiles = {p.profile_id: p for p in repo.list_all()}

    violations = []
    for pid in profiles:
        # No DRG lineage edges supplied → no specialization pairs.
        ancestors = repo.get_ancestors(pid)
        base_id = ancestors[0] if ancestors else None
        if not base_id or base_id not in profiles:
            continue
        violations.append(f"unexpected specialization found: {pid} -> {base_id}")

    assert not violations  # no specialization pairs → no violations


@pytest.mark.doctrine
@pytest.mark.fast
def test_tactic_refs_are_union_merged_not_overridden(tmp_path: Path) -> None:
    """
    Regression guard: when a specialist adds its own tactic-references,
    resolve_profile() must union-merge with the base's tactic-references,
    not replace them.

    If tactic-references is removed from _LIST_FIELDS, the specialist's
    explicit tactic list replaces the base's, and the resolved profile
    would be missing the base's tactic. This test catches that regression.
    """
    shipped = tmp_path / "built-in"
    shipped.mkdir()

    (shipped / "base-impl.agent.yaml").write_text(
        """profile-id: base-impl
name: Base Implementer
roles: [implementer]
purpose: Base
specialization:
  primary-focus: base
tactic-references:
  - id: base-tactic
    rationale: base declares this
""",
        encoding="utf-8",
    )
    (shipped / "specialist-impl.agent.yaml").write_text(
        """profile-id: specialist-impl
name: Specialist
roles: [implementer]
purpose: Specialist
specialization:
  primary-focus: specialist work
tactic-references:
  - id: specialist-tactic
    rationale: specialist adds this
  - id: base-tactic
    rationale: specialist repeats the base tactic with a narrower rationale
""",
        encoding="utf-8",
    )

    repo = AgentProfileRepository(
        built_in_dir=shipped, project_dir=None, drg=_lineage_drg(("specialist-impl", "base-impl"))
    )
    resolved = repo.resolve_profile("specialist-impl")

    merged_tactic_ids = {ref.id for ref in resolved.tactic_references}

    assert "base-tactic" in merged_tactic_ids, (
        "base-tactic must survive union merge — check that tactic-references is in _LIST_FIELDS"
    )
    assert "specialist-tactic" in merged_tactic_ids, (
        "specialist-tactic must be in merged profile"
    )
    assert [ref.id for ref in resolved.tactic_references].count("base-tactic") == 1
