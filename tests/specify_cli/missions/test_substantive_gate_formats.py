"""Pinning tests for the substantive-plan gate's tolerance of source formats.

WP01 / FR-013 (#1896): ``_has_substantive_technical_context`` must accept a
Technical Context section whose fields are rendered as Markdown bullets
(``- **Language/Version**: ...``) — the exact shape the canonical plan
template emits — not only the un-bulleted ``**Field**: value`` form. A real,
populated bulleted section was previously rejected as non-substantive,
falsely blocking ``setup-plan``.

These tests pin the FIXED behaviour: mutate the peer-field regex back to the
bullet-intolerant form and ``test_bulleted_technical_context_is_substantive``
fails — proving the pin genuinely reproduces #1896.

WP03 / #3832 (FR-006/FR-008, NFR-003/004/005): the classes below extend this
file with the template-derived, per-mission-type generalization of the same
gate. ``TestNonVacuityFixtureMatrix`` is the NFR-005 proof obligation —  a
positive (must PASS) and negative (must FAIL) fixture for every mission type
the gate applies to (``software-dev``, ``documentation``, ``research``,
``plan``, and the ``example-custom`` pack-provided-declaration proof-of-
mechanism fixture — see ``_substantive.py``'s ``_PLAN_FIELD_DECLARATIONS``
docstring and plan.md Decision 1/T002(b)). ``software-dev``'s own
positive/negative coverage already exists above and in
``tests/integration/test_specify_plan_commit_boundary.py`` (NFR-003: unchanged
behaviour) — the matrix below adds a same-shape direct-call pair for
self-containment of the table plan.md documents.

#3830 (fix round, severity 3+4): the ``qa`` mission-type name was removed
from core's hardcoded ``_PLAN_FIELD_DECLARATIONS`` — core must not carry a
field declaration for an org-tier pack it has never seen (a real
``qa`` pack's shipped template uses numbered headings and has no bold
``Primary Item`` field at all, so the old core entry matched on name and
then failed permanently with misleading guidance). The synthetic
proof-of-mechanism fixture below is renamed ``example-custom`` — a name no
real pack would claim — and is now wired through the FIX-1 pack-provided
declaration seam (:class:`TestPackProvidedDeclarationSeam`) instead of a
core dict entry, which is the behaviour that actually needs proving: a
custom mission type's OWN pack can register its plan fields with zero core
change.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from charter.resolution import ResolutionTier
from specify_cli.missions._substantive import (
    _is_plan_substantive_for_type,
    _PLAN_FIELD_DECLARATIONS,
    describe_technical_context_gap,
    is_substantive,
)
from specify_cli.requirement_mapping import parse_requirement_ids_from_spec_md

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[3]


# Canonical bulleted Technical Context (real values) — the plan-template shape.
_BULLETED_REAL = """# Implementation Plan

## Technical Context
- **Language/Version**: Python 3.12
- **Primary Dependencies**: typer, rich, ruamel.yaml
- **Testing**: pytest

## Constitution Check
"""

# Bulleted form but every value is still a placeholder → NOT substantive.
_BULLETED_PLACEHOLDERS = """# Implementation Plan

## Technical Context
- **Language/Version**: [e.g., Python 3.12]
- **Primary Dependencies**: [e.g., typer]
- **Testing**: [NEEDS CLARIFICATION]

## Constitution Check
"""

# Real Language/Version but every PEER field is a placeholder → not substantive,
# and the gap reason should name the peer-field shape.
_BULLETED_PEERS_PLACEHOLDER = """# Implementation Plan

## Technical Context
- **Language/Version**: Python 3.12
- **Primary Dependencies**: [e.g., typer]
- **Testing**: [NEEDS CLARIFICATION]

## Constitution Check
"""

# Un-bulleted form (already worked before #1896) — guard against regressing it.
_PLAIN_REAL = """# Implementation Plan

## Technical Context
**Language/Version**: Python 3.12
**Primary Dependencies**: typer, rich

## Constitution Check
"""

# Asterisk-bullet variant (``* **Field**: value``).
_STAR_BULLETED_REAL = """# Implementation Plan

## Technical Context
* **Language/Version**: Python 3.12
* **Primary Dependencies**: typer, rich

## Constitution Check
"""


def test_bulleted_technical_context_is_substantive() -> None:
    """#1896 pin: a real, dash-bulleted Technical Context is substantive."""
    assert _is_plan_substantive_for_type(_BULLETED_REAL, "software-dev") is True


def test_star_bulleted_technical_context_is_substantive() -> None:
    """The asterisk-bullet rendering is equally tolerated."""
    assert _is_plan_substantive_for_type(_STAR_BULLETED_REAL, "software-dev") is True


def test_bulleted_placeholders_remain_non_substantive() -> None:
    """Bulleting MUST NOT relax the placeholder filter (no false positives)."""
    assert _is_plan_substantive_for_type(_BULLETED_PLACEHOLDERS, "software-dev") is False


def test_plain_technical_context_still_substantive() -> None:
    """The pre-#1896 un-bulleted shape keeps passing (no regression)."""
    assert _is_plan_substantive_for_type(_PLAIN_REAL, "software-dev") is True


def test_describe_gap_none_when_substantive() -> None:
    """No gap is reported for a real bulleted section."""
    assert describe_technical_context_gap(_BULLETED_REAL) is None


def test_describe_gap_names_peer_field_format() -> None:
    """FR-013: real Language/Version but placeholder peers → name the format."""
    reason = describe_technical_context_gap(_BULLETED_PEERS_PLACEHOLDER)
    assert reason is not None
    # The diagnostic must mention the offending peer-field shape.
    assert "peer field" in reason
    assert "bulleted" in reason


def test_describe_gap_names_language_version_when_missing() -> None:
    """A placeholder Language/Version is reported with field-level precision."""
    reason = describe_technical_context_gap(_BULLETED_PLACEHOLDERS)
    assert reason is not None
    assert "Language/Version" in reason


def test_describe_gap_missing_section() -> None:
    """An absent Technical Context section is named explicitly."""
    reason = describe_technical_context_gap("# Plan\n\n## Other\n")
    assert reason is not None
    assert "missing" in reason


# ---------------------------------------------------------------------------
# WP03 / #3832: per-type shape detectors (T003-T006)
# ---------------------------------------------------------------------------

# documentation: real Documentation Framework, and Build Commands (sub-list
# -valued, Decision 3(a)'s value-capture extension) is the ONLY populated
# peer — the other three declared peers are placeholder-only, so this fixture
# would falsely read as non-substantive if the sub-list-value-capture
# extension regressed (plan.md §Architectural Gate Non-Vacuity).
_DOCUMENTATION_BUILD_COMMANDS_ONLY = """# Implementation Plan: Docs

## Technical Context

**Documentation Framework**: Sphinx
**Languages Detected**: [NEEDS CLARIFICATION]
**Output Format**: [NEEDS CLARIFICATION]
**Hosting Platform**: [NEEDS CLARIFICATION]
**Build Commands**:

- sphinx-build -b html docs/ docs/_build/html/
"""

# research: real Research Question (primary) plus real Data Sources content
# (peer, sub-shape c-ii — Decision 3(c)).
_RESEARCH_REAL = """# Research Plan

## Research Context

**Research Question**: Does async I/O reduce p95 latency under load?
**Research Type**: Empirical Study

## Methodology

### Research Design

**Approach**: Experiment

### Data Sources

**Keywords**: async io benchmarking, latency
**Inclusion Criteria**: peer-reviewed within 5 years

### Analysis Framework

**Coding Scheme**: thematic
"""

# plan: real Problem Decomposition (primary, shape (b)) plus real content in
# every peer (Scope-MoSCoW shape (a), Sequencing shape (b), Decisions shape
# (c-i)).
_PLAN_REAL = """# Plan

## Problem Decomposition

| # | Sub-problem | Cluster / bounded context | Depends on |
|---|-------------|----------------------------|------------|
| SP-1 | Split the monolith into services | Core platform | none |

## Scope — MoSCoW

- **Must**: Ship the core split
- **Should**: Add observability
- **Could**: Add tracing
- **Won't (this cut)**: Rewrite the UI

## Sequencing & Prioritisation

| Order | Sub-problem | Importance | Urgency | Rationale |
|-------|-------------|------------|---------|-----------|
| 1 | SP-1 | High | High | Blocks everything else |

## Decisions

### Decision D-1: Use a strangler fig migration

- **Context**: The monolith cannot be rewritten in one pass
- **Decision**: Route new traffic through a facade
"""

# plan: shape-dispatch fixture (TASKS-FRESH2-001) — the PRIMARY field
# (Problem Decomposition, shape (b)) is genuinely populated, but every
# declared PEER (Scope-MoSCoW shape (a), Sequencing shape (b), Decisions
# shape (c-i)) is placeholder-only. A naive label-only relabeling of the
# pre-#3832 shape-(a)-only diagnosis would misreport this as "primary field
# missing" even though the primary is real — the real failure is the peer.
_PLAN_PRIMARY_ONLY = """# Plan

## Problem Decomposition

| # | Sub-problem | Cluster / bounded context | Depends on |
|---|-------------|----------------------------|------------|
| SP-1 | Split the monolith into services | Core platform | none |

## Scope — MoSCoW

- **Must**: [Without this, the plan fails its purpose]
- **Should**: [Important, painful to omit, but not fatal if deferred]
- **Could**: [Desirable, included only if Must/Should leave room]
- **Won't (this cut)**: [Explicitly deferred — may return in a later cut]

## Sequencing & Prioritisation

| Order | Sub-problem | Importance | Urgency | Rationale |
|-------|-------------|------------|---------|-----------|
| 1 | [SP-#] | [High/Low] | [High/Low] | [Why it goes first] |

## Decisions

### Decision D-1: [Decision title]

- **Context**: [Problem, drivers, constraints forcing this decision now]
- **Decision**: [Chosen option, stated plainly]
- **Rationale**: [Why this option wins]
- **Alternatives considered**:
  - [Alternative A] — rejected because [reason]
- **Consequences**: [Accepted trade-offs, positive and negative]
"""

# example-custom: proof-of-mechanism fixture for a genuinely CUSTOM
# (non-built-in) mission type whose field declaration is shipped by the
# mission type's OWN pack, not core (#3830 FIX-1). "example-custom" is a
# name no real pack would claim — it replaces the earlier "qa" fixture name,
# which squatted the identifier of the one real custom mission type this
# mission was built from (#3830 FIX-2: core no longer carries a "qa" field
# declaration at all). Placeholder text reuses the existing
# ``[NEEDS CLARIFICATION]`` literal rather than inventing new bracket
# vocabulary for a fixture that is not itself a real template. See
# ``example_custom_project_dir`` below for the pack-provided declaration
# these fixtures are checked against.
_EXAMPLE_CUSTOM_REAL = """# Test Plan: Checkout flow

## Summary

Verify the checkout flow end to end.

## Test Items

**Primary Item**: Checkout API happy path
**Secondary Item**: Payment retries

## Environments

**Target OS**: Ubuntu 22.04, macOS 14

## Test-Data Strategy

Use synthetic card numbers from the sandbox test suite.

## Suite Breakdown

Smoke, regression, load.

## Tooling

pytest, k6

## Schedule

Sprint 42

## Responsibilities

QA guild owns execution.

## Traceability-Matrix Skeleton

Linked to REQ-118.
"""

_EXAMPLE_CUSTOM_PLACEHOLDERS = """# Test Plan: [PLAN TITLE]

## Summary

[NEEDS CLARIFICATION]

## Test Items

**Primary Item**: [NEEDS CLARIFICATION]
**Secondary Item**: [NEEDS CLARIFICATION]

## Environments

**Target OS**: [NEEDS CLARIFICATION]

## Test-Data Strategy

[NEEDS CLARIFICATION]

## Suite Breakdown

[NEEDS CLARIFICATION]

## Tooling

[NEEDS CLARIFICATION]

## Schedule

[NEEDS CLARIFICATION]

## Responsibilities

[NEEDS CLARIFICATION]

## Traceability-Matrix Skeleton

[NEEDS CLARIFICATION]
"""


@pytest.fixture(scope="module")
def example_custom_project_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A project root whose OVERRIDE tier ships an ``example-custom`` plan
    field declaration (#3830 FIX-1): a pack-provided
    ``plan-field-declaration.yaml`` resolved through the SAME
    ``resolve_template`` seam that resolves the mission type's plan
    template, at ``.kittify/overrides/missions/{mission}/templates/`` — tier
    1 of the 6-tier chain. ORG-tier reachability of this exact seam is
    proven separately by :class:`TestPackProvidedDeclarationOrgTier`, which
    mirrors ``tests/runtime/test_resolver_unit.py::TestOrgTierResolution``.
    """
    project_dir = tmp_path_factory.mktemp("example-custom-project")
    declaration_dir = project_dir / ".kittify" / "overrides" / "missions" / "example-custom" / "templates"
    declaration_dir.mkdir(parents=True)
    (declaration_dir / "plan-field-declaration.yaml").write_text(
        "primary:\n  kind: bold_field\n  heading: Test Items\n  label: Primary Item\npeers:\n  - kind: any_bold_field\n    heading: Environments\n",
        encoding="utf-8",
    )
    return project_dir


def test_documentation_build_commands_only_peer_is_substantive() -> None:
    """Decision 3(a) value-capture extension: a sub-list-valued peer counts."""
    assert _is_plan_substantive_for_type(_DOCUMENTATION_BUILD_COMMANDS_ONLY, "documentation") is True


def test_research_real_data_sources_is_substantive() -> None:
    """Decision 3(c-ii): the named-sibling nested-heading detector."""
    assert _is_plan_substantive_for_type(_RESEARCH_REAL, "research") is True


def test_plan_real_all_peers_is_substantive() -> None:
    """Decision 3(b)/(c-i): table primary plus every peer shape populated."""
    assert _is_plan_substantive_for_type(_PLAN_REAL, "plan") is True


def test_example_custom_real_is_substantive(example_custom_project_dir: Path) -> None:
    """#3830 FIX-1: a pack-provided declaration (no core dict entry) resolves
    a genuinely custom mission type through the real ``resolve_template`` seam."""
    assert _is_plan_substantive_for_type(_EXAMPLE_CUSTOM_REAL, "example-custom", project_dir=example_custom_project_dir) is True


def test_example_custom_placeholder_scaffold_is_not_substantive(example_custom_project_dir: Path) -> None:
    """example-custom's own unfilled scaffold fails through the normal shape path."""
    assert _is_plan_substantive_for_type(_EXAMPLE_CUSTOM_PLACEHOLDERS, "example-custom", project_dir=example_custom_project_dir) is False


def test_qa_has_no_core_declaration() -> None:
    """#3830 FIX-2: core must not carry a field declaration for an org-tier
    pack it has never seen. Removing this entry is the operator-ruled fix —
    a real ``qa`` pack's shipped template (numbered headings, no bold
    ``Primary Item`` field) would otherwise match on name and fail
    permanently with misleading "missing peer field" guidance instead of an
    honest "unregistered type" diagnosis."""
    assert "qa" not in _PLAN_FIELD_DECLARATIONS


def test_plan_primary_only_shape_dispatch_message_names_the_real_peer_failure() -> None:
    """TASKS-FRESH2-001: primary real, peers placeholder -> peer diagnosis, not primary."""
    assert _is_plan_substantive_for_type(_PLAN_PRIMARY_ONLY, "plan") is False
    reason = describe_technical_context_gap(_PLAN_PRIMARY_ONLY, "plan")
    assert reason is not None
    assert "no peer field" in reason
    assert "Problem Decomposition" in reason
    assert "Technical Context" not in reason
    assert "Language/Version" not in reason


# ---------------------------------------------------------------------------
# WP03 / #3832 / NFR-005: non-vacuity fixture matrix — a positive (must PASS)
# and negative (must FAIL) fixture for every mission type the gate applies
# to, read from the REAL, live template files (not a hand-copied excerpt) so
# a future template edit that drifts from its declaration shows up here as a
# newly-failing fixture (plan.md Decision 1's non-vacuity justification).
# ---------------------------------------------------------------------------


def _read_template(relative_path: str) -> str:
    return (_REPO_ROOT / relative_path).read_text(encoding="utf-8")


class TestNonVacuityFixtureMatrix:
    """NFR-005: the gate must be able to PASS and FAIL for every mission type."""

    def test_software_dev_positive(self) -> None:
        assert _is_plan_substantive_for_type(_BULLETED_REAL, "software-dev") is True

    def test_software_dev_negative_unfilled_scaffold(self) -> None:
        scaffold = _read_template("packs/built-in/missions/software-dev/templates/plan-template.md")
        assert _is_plan_substantive_for_type(scaffold, "software-dev") is False

    def test_documentation_positive(self) -> None:
        assert _is_plan_substantive_for_type(_DOCUMENTATION_BUILD_COMMANDS_ONLY, "documentation") is True

    def test_documentation_negative_unfilled_scaffold(self) -> None:
        scaffold = _read_template("packs/built-in/missions/documentation/templates/documentation-plan-template.md")
        assert _is_plan_substantive_for_type(scaffold, "documentation") is False

    def test_research_positive(self) -> None:
        assert _is_plan_substantive_for_type(_RESEARCH_REAL, "research") is True

    def test_research_negative_unfilled_scaffold(self) -> None:
        scaffold = _read_template("packs/built-in/missions/research/templates/research-plan-template.md")
        assert _is_plan_substantive_for_type(scaffold, "research") is False

    def test_plan_positive(self) -> None:
        assert _is_plan_substantive_for_type(_PLAN_REAL, "plan") is True

    def test_plan_negative_unfilled_scaffold(self) -> None:
        scaffold = _read_template("packs/built-in/missions/plan/templates/plan-plan-skeleton.md")
        assert _is_plan_substantive_for_type(scaffold, "plan") is False

    def test_example_custom_positive(self, example_custom_project_dir: Path) -> None:
        """#3830 FIX-1: PASS branch for a pack-declared (not core-declared) type."""
        assert _is_plan_substantive_for_type(_EXAMPLE_CUSTOM_REAL, "example-custom", project_dir=example_custom_project_dir) is True

    def test_example_custom_negative_unfilled_scaffold(self, example_custom_project_dir: Path) -> None:
        """#3830 FIX-1: FAIL branch for the same pack-declared type."""
        assert _is_plan_substantive_for_type(_EXAMPLE_CUSTOM_PLACEHOLDERS, "example-custom", project_dir=example_custom_project_dir) is False


class TestFailClosedEdgeCases:
    """T008: two DISTINCT fail-closed edge cases — neither substitutes for the other."""

    def test_malformed_missing_template_fails_closed(self, tmp_path: Path) -> None:
        """A plan.md that cannot even be read must not crash or silently pass."""
        missing = tmp_path / "plan.md"
        with pytest.raises(OSError):
            is_substantive(missing, "plan", mission_type="software-dev")

    def test_undeclared_mission_type_fails_closed(self) -> None:
        """T002(b): a RESOLVABLE template whose type has NO declaration entry.

        Different code path from the malformed-template case above (there,
        resolution/reading itself fails; here, the content is real and
        well-formed but the declaration lookup has nothing to check it
        against) and from the ``example-custom`` negative fixture above
        (there, ``example-custom`` HAS a pack-provided declaration and fails
        on content; here, the type has no declaration anywhere -- and no
        ``project_dir`` is even passed, so the pack-provided seam is never
        consulted).
        """
        assert _is_plan_substantive_for_type(_EXAMPLE_CUSTOM_REAL, "unlisted") is False
        reason = describe_technical_context_gap(_EXAMPLE_CUSTOM_REAL, "unlisted")
        assert reason is not None
        assert "no field declaration is registered" in reason.lower()
        assert "unlisted" in reason


# ---------------------------------------------------------------------------
# #3830 FIX-1 (severity-4 blocker): the pack-provided field-declaration seam
# must genuinely reach the ORG tier, not just OVERRIDE (which every project
# already writes to, org packs do not). Mirrors
# ``tests/runtime/test_resolver_unit.py::TestOrgTierResolution`` exactly --
# same ``_write_org_pack_config`` shape, same ``get_kittify_home`` patch --
# because this seam is LITERALLY the same ``resolve_template`` 6-tier chain,
# called for a sibling asset name (``plan-field-declaration.yaml``) next to
# the mission type's own plan template.
# ---------------------------------------------------------------------------


def _write_org_pack_config(repo_root: Path, *, pack_name: str, local_path: Path) -> None:
    """Write a canonical ``doctrine.org.packs[].local_path`` config.yaml entry."""
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        f"doctrine:\n  org:\n    packs:\n      - name: {pack_name}\n        local_path: {local_path}\n",
        encoding="utf-8",
    )


class TestPackProvidedDeclarationOrgTier:
    """#3830 FIX-1: an org pack ships ``plan-field-declaration.yaml`` next to
    its ``plan-template.md`` and the gate honours it with NO core change."""

    def test_org_tier_declaration_resolves_and_passes(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        org_root = tmp_path / "org-pack"
        declaration_dir = org_root / "missions" / "acme-custom" / "templates"
        declaration_dir.mkdir(parents=True)
        (declaration_dir / "plan-field-declaration.yaml").write_text(
            "primary:\n  kind: bold_field\n  heading: Test Items\n  label: Primary Item\npeers:\n  - kind: any_bold_field\n    heading: Environments\n",
            encoding="utf-8",
        )
        _write_org_pack_config(project, pack_name="acme", local_path=org_root)

        with patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            return_value=tmp_path / "no_home",
        ):
            from specify_cli.runtime.resolver import resolve_template

            resolution = resolve_template("plan-field-declaration.yaml", project, mission="acme-custom")
            assert resolution.tier == ResolutionTier.ORG
            assert resolution.path == declaration_dir / "plan-field-declaration.yaml"

            assert _is_plan_substantive_for_type(_EXAMPLE_CUSTOM_REAL, "acme-custom", project_dir=project) is True
            assert _is_plan_substantive_for_type(_EXAMPLE_CUSTOM_PLACEHOLDERS, "acme-custom", project_dir=project) is False

    def test_no_org_pack_and_no_builtin_still_fails_closed(self, tmp_path: Path) -> None:
        """A genuinely unregistered type with an org root configured but no
        matching pack asset stays fail-closed (NFR-005: no accidental
        neutral pass)."""
        project = tmp_path / "project"
        project.mkdir()
        org_root = tmp_path / "org-pack"
        org_root.mkdir()  # configured, but no missions/ subtree at all

        _write_org_pack_config(project, pack_name="acme", local_path=org_root)

        with patch(
            "specify_cli.runtime.resolver.get_kittify_home",
            return_value=tmp_path / "no_home",
        ):
            assert _is_plan_substantive_for_type(_EXAMPLE_CUSTOM_REAL, "never-declared", project_dir=project) is False

    def test_mission_agnostic_legacy_tier_declaration_is_ignored(self, tmp_path: Path) -> None:
        """#3832 fold: ``resolve_template`` tiers 1b/2/5 (override, legacy,
        global) are mission-agnostic -- a ``plan-field-declaration.yaml`` at
        one of those tiers is NOT scoped to any single mission type, so
        honouring it would gate EVERY undeclared custom type's plan against
        one type's fields. Only a mission-scoped hit (path containing
        ``/missions/{mission_type}/``) is a genuine declaration. Here a
        legacy-tier file (``.kittify/templates/plan-field-declaration.yaml``)
        resolves but must be ignored, so an undeclared type still fails
        closed via the ordinary undeclared-gap path."""
        project = tmp_path / "project"
        legacy_templates = project / ".kittify" / "templates"
        legacy_templates.mkdir(parents=True)
        (legacy_templates / "plan-field-declaration.yaml").write_text(
            "primary:\n  kind: bold_field\n  heading: Test Items\n  label: Primary Item\npeers:\n  - kind: any_bold_field\n    heading: Environments\n",
            encoding="utf-8",
        )

        from specify_cli.missions._substantive import _pack_provided_declaration

        assert _pack_provided_declaration("never-declared", project) is None
        assert _is_plan_substantive_for_type(_EXAMPLE_CUSTOM_REAL, "never-declared", project_dir=project) is False
        reason = describe_technical_context_gap(_EXAMPLE_CUSTOM_REAL, "never-declared", project_dir=project)
        assert reason is not None
        assert "no field declaration is registered" in reason.lower()


# ---------------------------------------------------------------------------
# #3832 fold: a pack-provided plan-field-declaration.yaml that is present
# but unreadable, mis-encoded, or carries an unknown key must fail LOUD via
# _PackDeclarationError -- parity with expected-artifacts.yaml's
# extra="forbid" posture -- rather than being silently ignored or crashing
# with an unguarded OSError/UnicodeDecodeError.
# ---------------------------------------------------------------------------


class TestPackDeclarationFailsLoud:
    def test_unknown_optional_key_raises_pack_declaration_error(self, tmp_path: Path) -> None:
        """A typo'd optional key (``labell`` instead of ``label``) on a
        ``bold_field`` entry must raise, not be silently dropped by
        ``dict.get`` and leave the field looking valid but mislabelled."""
        from specify_cli.missions._substantive import (
            _PackDeclarationError,
            _plan_field_declaration_from_yaml,
        )

        path = tmp_path / "plan-field-declaration.yaml"
        path.write_text(
            "primary:\n"
            "  kind: bold_field\n"
            "  heading: Test Items\n"
            "  label: Primary Item\n"
            "  labell: typo\n"
            "peers:\n"
            "  - kind: any_bold_field\n"
            "    heading: Environments\n",
            encoding="utf-8",
        )

        with pytest.raises(_PackDeclarationError, match="unknown key"):
            _plan_field_declaration_from_yaml(path)

    def test_unknown_top_level_key_raises_pack_declaration_error(self, tmp_path: Path) -> None:
        """A typo'd top-level key (anything besides 'primary'/'peers') must raise."""
        from specify_cli.missions._substantive import (
            _PackDeclarationError,
            _plan_field_declaration_from_yaml,
        )

        path = tmp_path / "plan-field-declaration.yaml"
        path.write_text(
            "primary:\n  kind: table_field\n  heading: Test Items\npeers:\n  - kind: any_bold_field\n    heading: Environments\nextra_top_level_key: oops\n",
            encoding="utf-8",
        )

        with pytest.raises(_PackDeclarationError, match="unknown top-level key"):
            _plan_field_declaration_from_yaml(path)

    def test_mis_encoded_file_raises_pack_declaration_error(self, tmp_path: Path) -> None:
        """A file that cannot be decoded as UTF-8 must raise
        ``_PackDeclarationError``, not an unguarded ``UnicodeDecodeError``."""
        from specify_cli.missions._substantive import (
            _PackDeclarationError,
            _plan_field_declaration_from_yaml,
        )

        path = tmp_path / "plan-field-declaration.yaml"
        path.write_bytes(b"primary:\n  kind: bold_field\n  heading: \xff\xfe invalid utf-8\n")

        with pytest.raises(_PackDeclarationError, match="could not be read"):
            _plan_field_declaration_from_yaml(path)


# ---------------------------------------------------------------------------
# #3830/#3832 fold: parity guard between the built-in mission types that ship
# a ``plan.md`` artifact and the built-in ``_PLAN_FIELD_DECLARATIONS`` table.
# A future 5th built-in mission type that requires a plan.md but forgets to
# register its own declaration would otherwise silently fail the gate closed
# with no signal at authoring time -- this test fails loud instead, at the
# same commit that adds the new type's mission.yaml.
# ---------------------------------------------------------------------------


def _builtin_mission_types_requiring_plan_md() -> set[str]:
    """Directory names under ``src/specify_cli/missions/`` whose ``mission.yaml``
    declares ``plan.md`` as a required artifact."""
    import yaml

    missions_root = _REPO_ROOT / "src" / "specify_cli" / "missions"
    types: set[str] = set()
    for mission_dir in missions_root.iterdir():
        mission_yaml = mission_dir / "mission.yaml"
        if not mission_yaml.is_file():
            continue
        raw = yaml.safe_load(mission_yaml.read_text(encoding="utf-8"))
        required = (raw or {}).get("artifacts", {}).get("required", [])
        if "plan.md" in required:
            types.add(mission_dir.name)
    return types


def test_plan_field_declarations_cover_every_builtin_plan_md_type() -> None:
    """Every built-in mission type that ships a ``plan.md`` artifact must have
    a registered ``_PLAN_FIELD_DECLARATIONS`` entry -- no silent gap."""
    assert set(_PLAN_FIELD_DECLARATIONS) == _builtin_mission_types_requiring_plan_md()


# ---------------------------------------------------------------------------
# The live software-dev spec template's trailing ``Delivery`` /
# ``No-op passable?`` columns (+ legend + filled example) must not let the
# unfilled scaffold pass the spec-commit substantive gate, and must not add
# a phantom declared requirement id via the legend's filled example row.
# ---------------------------------------------------------------------------

_SPEC_TEMPLATE_PATH = _REPO_ROOT / "packs" / "built-in" / "missions" / "software-dev" / "templates" / "spec-template.md"


class TestSpecTemplateDeliveryLabels:
    """Reads the LIVE built-in template directly off disk (repo-root relative).

    The ``.kittify/overrides`` copy is guarded separately by
    ``tests/cross_cutting/test_kittify_override_parity.py``.
    """

    def _template_text(self) -> str:
        return _SPEC_TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_unfilled_scaffold_is_not_substantive(self, tmp_path: Path) -> None:
        """(1) Ratchet -- the unfilled scaffold marks itself
        ``[ratchet] · no-op passable: yes``, controlled by (2) below on the
        SAME fixture."""
        scaffold = tmp_path / "spec.md"
        scaffold.write_text(self._template_text(), encoding="utf-8")

        assert is_substantive(scaffold, "spec") is False

    def test_scaffold_with_title_and_user_story_filled_is_substantive(self, tmp_path: Path) -> None:
        """(2) Positive control (same fixture as (1)): fill only the first FR
        row's Title/User Story -- label placeholders stay untouched -- and the
        gate must flip to True. This is what proves (1) is a real, live
        assertion and not a vacuously-always-False detector."""
        text = self._template_text()
        filled = text.replace(
            "| FR-001 | [Short title] | As a [role], I want [goal] so that [benefit]. | High | Open",
            "| FR-001 | Real title | As a user, I want a real goal so that a real benefit. | High | Open",
            1,
        )
        assert filled != text, "fixture setup: the FR-001 row text to replace was not found in the live template"

        scaffold = tmp_path / "spec.md"
        scaffold.write_text(filled, encoding="utf-8")

        assert is_substantive(scaffold, "spec") is True

    def test_declared_id_set_is_unchanged_by_the_new_columns(self) -> None:
        """(3) The template's declared id set equals the frozen pre-existing
        set (FR-001..003, NFR-001..003, C-001..003) -- the legend's filled
        example (``FR-EXAMPLE``) declares nothing extra.

        Positive control on the same fixture: the example line is genuinely
        present in the template text, so the exact-set equality below is a
        real id-parser result, not a vacuous pass over a template that never
        contained the example at all.
        """
        text = self._template_text()
        assert "| FR-EXAMPLE |" in text

        declared = parse_requirement_ids_from_spec_md(text)
        assert set(declared["all"]) == {
            "FR-001",
            "FR-002",
            "FR-003",
            "NFR-001",
            "NFR-002",
            "NFR-003",
            "C-001",
            "C-002",
            "C-003",
        }

    # -----------------------------------------------------------------
    # Build (must-pin) assertions on the LIVE template's actual content.
    # Deletion-tested against the template's prior content -- every
    # assertion below goes red on that content.
    # -----------------------------------------------------------------

    def test_fr_table_header_and_placeholder_rows_carry_delivery_columns(self) -> None:
        text = self._template_text()
        assert "| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |" in text
        for row in (
            "| FR-001 | [Short title] | As a [role], I want [goal] so that [benefit]. | High | Open | [build/ratchet/folded] | [yes/no] |",
            "| FR-002 | [Short title] | As a [role], I want [goal] so that [benefit]. | Medium | Open | [build/ratchet/folded] | [yes/no] |",
            "| FR-003 | [Short title] | As a [role], I want [goal] so that [benefit]. | Low | Open | [build/ratchet/folded] | [yes/no] |",
        ):
            assert row in text

    def test_success_criteria_bullets_carry_the_label_suffix(self) -> None:
        text = self._template_text()
        suffix = "— [build/ratchet/folded] · no-op passable: [yes/no]"
        for sc_id in ("SC-001", "SC-002", "SC-003", "SC-004"):
            marker = f"**{sc_id}**"
            idx = text.index(marker)
            line_end = text.index("\n", idx)
            assert suffix in text[idx:line_end], f"{sc_id} bullet is missing the delivery-label suffix"

    def test_legend_names_the_tactic_fetch_command_and_the_filled_example(self) -> None:
        text = self._template_text()
        assert "acceptance-criteria-non-vacuity" in text
        assert "spec-kitty charter context --include tactic:acceptance-criteria-non-vacuity" in text
        assert "| FR-EXAMPLE |" in text
        # Exactly one gloss line is marked as the tactic's summary -- this
        # must not read as a second, independent label definition.
        assert text.count("summary of tactic") == 1

    def test_nfr_and_constraint_tables_are_unchanged(self) -> None:
        """NFR/C tables carry no Delivery/No-op columns (out of scope per spec.md)."""
        text = self._template_text()
        assert "| ID | Title | Requirement | Category | Priority | Status |" in text
        assert "| NFR-001 | [Short title] | [Measurable threshold, e.g., p95 latency under 300ms] | Performance | High | Open |" in text
        assert "| ID | Title | Constraint | Category | Priority | Status |" in text
        assert "| C-001 | [Short title] | [Required boundary or limitation] | Technical | High | Open |" in text
