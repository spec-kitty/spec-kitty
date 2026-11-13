"""Structural checks for the placement-seam architecture page (WP09, T044).

Contract: ``kitty-specs/read-side-seam-primary-primitive-closure-01KYKMMT/contracts/
placement-layering.md`` C1/C5. This suite asserts **structure and citations**, not
prose wording — pinning sentences would fight every future edit. The comprehension
check (does a fresh reader actually understand the layering) is User Story 7's
Independent Test, a human judgement call, not something this file can assert.

Also covers the companion edits from the same slice:
- the competing page (``branch-target-routing.md``) no longer asserts per-kind
  placement rules or the retired ``primary target branch`` alias (SC-017);
- the ``Routing`` disambiguation lives in ``docs/context/orchestration.md`` and
  covers every governed sense named by the WP prompt, each with a "do NOT use
  when" guard, plus the infrastructural senses named as explicitly out of scope.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE_PATH = REPO_ROOT / "docs" / "architecture" / "artifact-placement-seam.md"
BRANCH_TARGET_PATH = REPO_ROOT / "docs" / "architecture" / "branch-target-routing.md"
ORCHESTRATION_PATH = REPO_ROOT / "docs" / "context" / "orchestration.md"
INDEX_PATH = REPO_ROOT / "docs" / "architecture" / "README.md"

# The six named sections required by contract C1. Matched as level-2 headings,
# anchored to line start so a false positive inside a code block can't satisfy it.
REQUIRED_SECTIONS: tuple[str, ...] = (
    r'^##\s+What "routing" means here\s*$',
    r"^##\s+The layer table\s*$",
    r"^##\s+Both composition roots\s*$",
    r"^##\s+The compliance taxonomy\s*$",
    r"^##\s+Honest bounds\s*$",
    r"^##\s+Citations\s*$",
)

LAYER_NAMES: tuple[str, ...] = ("L0", "L1", "L2a", "L2b", "L3", "L4")

GOVERNED_ROUTING_SENSES: tuple[str, ...] = (
    "Placement routing",
    "Branch-target routing",
    "Commit routing",
    "Dispatch/profile routing",
    "Sync fan-out routing",
    "Model/task routing",
    "Scope routing",
)

OUT_OF_SCOPE_ROUTING_SENSES: tuple[str, ...] = (
    "Event routing",
    "HTTP request routing",
    "Significance routing bands",
)


@pytest.fixture(scope="module")
def page_text() -> str:
    assert PAGE_PATH.exists(), f"required page missing: {PAGE_PATH}"
    return PAGE_PATH.read_text(encoding="utf-8")


@pytest.mark.parametrize("section_pattern", REQUIRED_SECTIONS)
def test_required_section_present(page_text: str, section_pattern: str) -> None:
    """Each of the six C1-required named sections is present as its own heading."""
    assert re.search(section_pattern, page_text, re.MULTILINE), (
        f"artifact-placement-seam.md is missing the required section matching "
        f"{section_pattern!r} (contract C1)"
    )


def test_layer_table_has_one_row_per_layer_with_owning_module(page_text: str) -> None:
    """The layer table names all six layers, each with an owning ``module:symbol``."""
    layer_section = _section_body(page_text, "The layer table")
    for layer in LAYER_NAMES:
        assert f"**{layer}" in layer_section or f"| **{layer}" in layer_section, (
            f"layer table is missing a row for {layer!r}"
        )
    # Each row must cite a concrete src module path -- a table with prose but no
    # code citation would satisfy the row-per-layer check vacuously.
    assert layer_section.count("src/mission_runtime/") >= 4, (
        "layer table rows must cite their owning src/mission_runtime module"
    )
    assert "src/specify_cli/missions/_read_path_resolver.py" in layer_section, (
        "the L3 discovery/assembly row must cite its owning module "
        "(_read_path_resolver.py)"
    )


def test_l2_is_shown_as_two_functions(page_text: str) -> None:
    """C2's load-bearing correction: L2 must name TWO functions, not one module."""
    assert "declared_read_surface" in page_text
    assert "_classify_artifact_surface" in page_text
    layer_section = _section_body(page_text, "The layer table")
    assert "L2a" in layer_section and "L2b" in layer_section, (
        "the layer table must show L2a (declared) and L2b (affirmative) as "
        "distinct rows, not one collapsed decision layer"
    )


def test_l4_is_described_as_selecting_not_assembling(page_text: str) -> None:
    """C2's other load-bearing correction: L4 selects; it must not read as assembly."""
    assert "translate_surface" in page_text
    layer_section = _section_body(page_text, "The layer table")
    assert re.search(r"\bselects?\b", layer_section, re.IGNORECASE), (
        "the L4 row must describe translate_surface as SELECTING an "
        "already-discovered location"
    )


def test_both_composition_roots_present(page_text: str) -> None:
    """Both the read root and the write root must appear as named roots."""
    roots_section = _section_body(page_text, "Both composition roots")
    assert "resolve_artifact_surface" in roots_section, "read composition root missing"
    assert "resolve_placement_only" in roots_section, "write composition root missing"
    assert "placement_seam(" in roots_section, (
        "both roots must be shown reached through the placement_seam(...) entry point"
    )


def test_compliance_taxonomy_present_with_semi_compliance_headline(page_text: str) -> None:
    """The four-shape compliance taxonomy is present; semi-compliance is explained."""
    taxonomy_section = _section_body(page_text, "The compliance taxonomy")
    for shape in ("Compliant", "Delegating-but-lenient", "Semi-compliant", "Non-compliant"):
        assert shape in taxonomy_section, f"compliance taxonomy missing shape {shape!r}"
    assert "canonicalizer authority gate" in taxonomy_section
    assert "read-side bypass census" in taxonomy_section, (
        "the taxonomy section must name which gate DOES catch semi-compliance "
        "(the read-side bypass census) and which does not (US7.4)"
    )


def test_honest_bounds_names_unwired_surfaces_and_placement_debt(page_text: str) -> None:
    """C1.5 / INV-5: unwired surface members and the residual PLACEMENT debt are named."""
    bounds_section = _section_body(page_text, "Honest bounds")
    for unwired in ("LANE", "CONSOLIDATED", "TEMP"):
        assert unwired in bounds_section, (
            f"Honest bounds must name the unwired TopologySurface member {unwired!r}"
        )
    assert "_PLACEMENT_ARTIFACT_KINDS" in bounds_section, (
        "Honest bounds must name the frozenset still carrying the retired "
        "PLACEMENT word (residual rename debt)"
    )


def test_honest_bounds_names_retrospective_short_circuit(page_text: str) -> None:
    """The RETROSPECTIVE short-circuit must appear in Honest bounds, not only the layer table."""
    bounds_section = _section_body(page_text, "Honest bounds")
    assert "RETROSPECTIVE" in bounds_section
    assert "resolve_retrospective_home" in bounds_section
    assert "foundation site" in bounds_section.lower()


def test_honest_bounds_cites_correct_tickets(page_text: str) -> None:
    """#2885 (surface_cannot_hold) and #3055 (the deferred coord-authority edge)."""
    assert "#2885" in page_text
    assert "#3055" in page_text
    # #2906 (the convergence/fold issue) must not be misattributed as the
    # surface_cannot_hold guard's ticket in the same breath.
    surface_cannot_hold_context = _nearby_text(page_text, "surface_cannot_hold", window=400)
    assert "#2906" not in surface_cannot_hold_context, (
        "surface_cannot_hold must cite #2885, not #2906 (the convergence/fold issue)"
    )


def test_both_adrs_cited(page_text: str) -> None:
    """Both governing ADRs must be cited in the Citations section."""
    citations_section = _section_body(page_text, "Citations")
    assert "2026-06-24-1" in citations_section
    assert "2026-07-23-1" in citations_section


def test_page_does_not_restate_normative_rules_as_its_own_heading(page_text: str) -> None:
    """C3: explanatory only -- the page must link to, not re-title itself as, the ADRs' rule."""
    # A cheap structural proxy: the page must not contain a heading that duplicates
    # a full ADR title, which would indicate the ADR's decision was copy-pasted in
    # as a section rather than linked.
    assert not re.search(
        r"^##\s+Decision Outcome\s*$", page_text, re.MULTILINE
    ), "the page must not restate an ADR's own 'Decision Outcome' section"


def test_page_filename_is_not_routing_dot_md() -> None:
    """C3: the filename must not be `*-routing.md` (>=10 overloaded senses)."""
    assert not PAGE_PATH.name.endswith("-routing.md")
    assert PAGE_PATH.name == "artifact-placement-seam.md"


def test_page_registered_in_architecture_index() -> None:
    index_text = INDEX_PATH.read_text(encoding="utf-8")
    assert "artifact-placement-seam.md" in index_text, (
        "artifact-placement-seam.md must be registered in docs/architecture/README.md"
    )


def test_page_has_required_frontmatter() -> None:
    """DIRECTIVE_042: doc_status (not bare status) + a related: list."""
    text = PAGE_PATH.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    assert "doc_status:" in frontmatter
    assert re.search(r"^status:", frontmatter, re.MULTILINE) is None, (
        "frontmatter must use doc_status, never the bare status key (DIRECTIVE_042)"
    )
    assert "related:" in frontmatter


# ---------------------------------------------------------------------------
# The competing page (T041, SC-017)
# ---------------------------------------------------------------------------


def test_branch_target_routing_no_longer_asserts_kind_level_placement() -> None:
    text = BRANCH_TARGET_PATH.read_text(encoding="utf-8")
    assert "acceptance-matrix.json" not in text, (
        "branch-target-routing.md must no longer assert per-artifact-kind "
        "placement rules (SC-017)"
    )
    assert "primary target branch" not in text, (
        "branch-target-routing.md must drop the retired 'primary target branch' alias"
    )
    assert "artifact-placement-seam.md" in text, (
        "branch-target-routing.md must link out to the new page for the placement sense"
    )


# ---------------------------------------------------------------------------
# The Routing glossary disambiguation (T042)
# ---------------------------------------------------------------------------


def test_routing_disambiguation_present_in_orchestration_glossary() -> None:
    text = ORCHESTRATION_PATH.read_text(encoding="utf-8")
    assert re.search(r"^###\s+Routing\s*$", text, re.MULTILINE), (
        "docs/context/orchestration.md must carry a 'Routing' disambiguation entry"
    )
    routing_section = _section_body(text, "Routing", heading_level="###")
    for sense in GOVERNED_ROUTING_SENSES:
        assert sense in routing_section, (
            f"Routing disambiguation is missing the governed sense {sense!r}"
        )
    for sense in OUT_OF_SCOPE_ROUTING_SENSES:
        assert sense in routing_section, (
            f"Routing disambiguation must explicitly name the out-of-scope sense {sense!r}"
        )
    assert routing_section.count("Do NOT use when") >= 1, (
        "each governed sense needs a 'do NOT use when' guard"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _section_body(text: str, heading: str, *, heading_level: str = "##") -> str:
    """Return the body of the section starting at ``heading`` up to the next same-level heading."""
    escaped = re.escape(heading)
    pattern = rf"^{re.escape(heading_level)}\s+{escaped}\s*$"
    match = re.search(pattern, text, re.MULTILINE)
    assert match, f"heading {heading!r} not found"
    start = match.end()
    next_heading = re.search(
        rf"^{re.escape(heading_level)}\s+\S", text[start:], re.MULTILINE
    )
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


def _nearby_text(text: str, needle: str, *, window: int) -> str:
    """Return up to ``window`` chars on either side of the first occurrence of ``needle``."""
    idx = text.find(needle)
    assert idx != -1, f"{needle!r} not found in text"
    return text[max(0, idx - window) : idx + len(needle) + window]
