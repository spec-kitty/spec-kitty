"""Smoke tests for the SPDD/REASONS doctrine pack (WP01).

Validates that the six new shipped doctrine artifacts load through DoctrineService
with correct shape, that DIRECTIVE_038 declares lenient-adherence with four
explicit allowances, and that the canvas template fragment carries all seven
canonical section headers.
"""

from __future__ import annotations

import pytest

from charter.offering.pack_paths import resolve_pack_root
from charter.offering.service import DoctrineService

from tests.doctrine.conftest import DOCTRINE_SOURCE_ROOT

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]


# Post-relocation the shipped built-in doctrine kinds live flattened under
# ``packs/built-in/<kind>/`` (the per-kind ``built-in/`` subdir was removed).
# ``templates/`` was NOT relocated and still lives under ``src/charter/offering/``.
PACKS_BUILT_IN = resolve_pack_root("built-in")
DOCTRINE_ROOT = DOCTRINE_SOURCE_ROOT


@pytest.fixture(scope="module")
def service() -> DoctrineService:
    # No explicit built-in root: repositories self-resolve packs/built-in/<kind>
    # (WP04 seam); src/doctrine is emptied of built-in content post-relocation.
    return DoctrineService()


def test_paradigm_loads_with_required_shape(service: DoctrineService) -> None:
    paradigm = service.paradigms.get("structured-prompt-driven-development")
    assert paradigm is not None, "paradigm structured-prompt-driven-development not loaded"
    assert paradigm.id == "structured-prompt-driven-development"
    assert paradigm.schema_version == "1.0"
    assert paradigm.name
    assert paradigm.summary

    shipped_path = (
        PACKS_BUILT_IN
        / "paradigms"
        / "structured-prompt-driven-development.paradigm.yaml"
    )
    assert shipped_path.is_file(), f"paradigm must live in shipped/: {shipped_path}"


@pytest.mark.parametrize("tactic_id", ["reasons-canvas-fill", "reasons-canvas-review"])
def test_tactic_loads_with_required_shape(
    service: DoctrineService, tactic_id: str
) -> None:
    tactic = service.tactics.get(tactic_id)
    assert tactic is not None, f"tactic {tactic_id} not loaded"
    assert tactic.id == tactic_id
    assert tactic.schema_version == "1.0"
    assert tactic.name
    assert tactic.steps, "tactic must declare at least one step"
    for step in tactic.steps:
        assert getattr(step, "title", None), f"every step in {tactic_id} requires a title"

    shipped_path = PACKS_BUILT_IN / "tactics" / f"{tactic_id}.tactic.yaml"
    assert shipped_path.is_file(), f"tactic must live in shipped/: {shipped_path}"


def test_styleguide_loads_with_required_shape(service: DoctrineService) -> None:
    styleguide = service.styleguides.get("reasons-canvas-writing")
    assert styleguide is not None, "styleguide reasons-canvas-writing not loaded"
    assert styleguide.id == "reasons-canvas-writing"
    assert styleguide.schema_version == "1.0"
    assert styleguide.title
    assert styleguide.scope == "docs"
    assert styleguide.principles, "styleguide must declare principles"

    shipped_path = (
        PACKS_BUILT_IN
        / "styleguides"
        / "reasons-canvas-writing.styleguide.yaml"
    )
    assert shipped_path.is_file(), f"styleguide must live in shipped/: {shipped_path}"


def test_directive_038_lenient_adherence_with_four_allowances(
    service: DoctrineService,
) -> None:
    directive = service.directives.get("DIRECTIVE_038")
    assert directive is not None, "DIRECTIVE_038 not loaded"
    assert directive.id == "DIRECTIVE_038"
    assert directive.schema_version == "1.0"
    assert directive.title
    assert directive.intent
    enforcement_value = getattr(directive.enforcement, "value", directive.enforcement)
    assert str(enforcement_value) == "lenient-adherence", (
        f"DIRECTIVE_038 enforcement must be 'lenient-adherence', got {enforcement_value!r}"
    )
    allowances = directive.explicit_allowances or []
    assert len(allowances) == 4, (
        f"DIRECTIVE_038 must declare exactly 4 explicit_allowances, got {len(allowances)}"
    )

    shipped_path = (
        PACKS_BUILT_IN
        / "directives"
        / "038-structured-prompt-boundary.directive.yaml"
    )
    assert shipped_path.is_file(), f"directive must live in shipped/: {shipped_path}"


def test_template_fragment_has_all_seven_canvas_sections() -> None:
    fragment_path = (
        DOCTRINE_ROOT / "templates" / "fragments" / "reasons-canvas-template.md"
    )
    assert fragment_path.is_file(), f"template fragment missing at {fragment_path}"
    body = fragment_path.read_text(encoding="utf-8")

    required_headers = [
        "## Requirements",
        "## Entities",
        "## Approach",
        "## Structure",
        "## Operations",
        "## Norms",
        "## Safeguards",
    ]
    missing = [h for h in required_headers if h not in body]
    assert not missing, f"REASONS canvas template missing section headers: {missing}"
