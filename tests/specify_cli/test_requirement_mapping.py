"""Unit tests for requirement_mapping module."""

from __future__ import annotations

from pathlib import Path

from specify_cli.cli.commands.agent.tasks_mapping_core import MappingRequest, plan_mapping
from specify_cli.requirement_mapping import (
    classify_stale_refs,
    compute_coverage,
    find_bare_prose_requirement_ids,
    find_undeclared_requirement_citations,
    normalize_requirement_refs_value,
    parse_requirement_ids_from_spec_md,
    read_all_wp_raw_requirement_refs,
    read_all_wp_requirement_refs,
    validate_ref_format,
    validate_refs,
)


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class TestValidateRefs:
    """Test ref validation against spec IDs."""

    def test_all_valid(self):
        valid, unknown = validate_refs(["FR-001", "NFR-002"], {"FR-001", "NFR-002", "FR-003"})
        assert valid == ["FR-001", "NFR-002"]
        assert unknown == []

    def test_some_unknown(self):
        valid, unknown = validate_refs(["FR-001", "FR-999"], {"FR-001", "FR-002"})
        assert valid == ["FR-001"]
        assert unknown == ["FR-999"]

    def test_case_insensitive(self):
        valid, unknown = validate_refs(["fr-001"], {"FR-001"})
        assert valid == ["FR-001"]
        assert unknown == []


class TestValidateRefFormat:
    """Test ref format validation."""

    def test_valid_formats(self):
        well_formed, malformed = validate_ref_format(["FR-001", "NFR-002", "C-003"])
        assert well_formed == ["FR-001", "NFR-002", "C-003"]
        assert malformed == []

    def test_malformed_formats(self):
        well_formed, malformed = validate_ref_format(["FR-001", "INVALID", "REQ-001"])
        assert well_formed == ["FR-001"]
        assert malformed == ["INVALID", "REQ-001"]


class TestClassifyStaleRefs:
    """Test #2066 stale-ref diagnostics classification."""

    def test_splits_malformed_and_unknown(self):
        # FR-003a is malformed (letter suffix); FR-999 is well-formed but absent
        # from spec → unknown_spec_id.
        reasons = classify_stale_refs(
            {"WP02": ["FR-003a", "FR-999"]},
            malformed=["FR-003A"],
        )
        assert reasons == {"WP02": {"malformed": ["FR-003a"], "unknown_spec_id": ["FR-999"]}}

    def test_unfilled_placeholder_is_malformed(self):
        # An unfilled <FR-XXX> template placeholder is classified malformed, not unknown.
        reasons = classify_stale_refs({"WP01": ["<FR-XXX>"]}, malformed=[])
        assert reasons["WP01"] == {"malformed": ["<FR-XXX>"], "unknown_spec_id": []}

    def test_preserves_raw_case_and_sorts(self):
        reasons = classify_stale_refs(
            {"WP03": ["fr-002", "FR-001"]},
            malformed=[],
        )
        # Both well-formed-but-unknown here; raw case preserved, sorted.
        assert reasons["WP03"]["unknown_spec_id"] == ["FR-001", "fr-002"]
        assert reasons["WP03"]["malformed"] == []


class TestComputeCoverage:
    """Test coverage summary computation."""

    def test_full_coverage(self):
        mappings = {"WP01": ["FR-001", "FR-002"], "WP02": ["FR-003"]}
        coverage = compute_coverage(mappings, {"FR-001", "FR-002", "FR-003"})
        assert coverage["total_functional"] == 3
        assert coverage["mapped_functional"] == 3
        assert coverage["unmapped_functional"] == []

    def test_partial_coverage(self):
        mappings = {"WP01": ["FR-001"]}
        coverage = compute_coverage(mappings, {"FR-001", "FR-002", "FR-003"})
        assert coverage["total_functional"] == 3
        assert coverage["mapped_functional"] == 1
        assert sorted(coverage["unmapped_functional"]) == ["FR-002", "FR-003"]

    def test_empty_mappings(self):
        coverage = compute_coverage({}, {"FR-001", "FR-002"})
        assert coverage["total_functional"] == 2
        assert coverage["mapped_functional"] == 0
        assert len(coverage["unmapped_functional"]) == 2


class TestParseRequirementIdsFromSpecMd:
    """Test spec.md ID extraction."""

    def test_extracts_fr_nfr_c(self):
        content = """
| FR-001 | First req |
| FR-002 | Second req |
| NFR-001 | Non-functional |
| C-001 | Constraint |
"""
        result = parse_requirement_ids_from_spec_md(content)
        assert "FR-001" in result["all"]
        assert "NFR-001" in result["all"]
        assert "C-001" in result["all"]
        assert result["functional"] == ["FR-001", "FR-002"]

    def test_case_insensitive(self):
        # Case-insensitivity of a DECLARED id (table row) -- a bare prose
        # mention like "fr-001 and nfr-002" is a citation, not a declaration
        # (see TestDeclaredVsCitedRequirements below), so this fixture uses
        # the same declared shape as test_extracts_fr_nfr_c.
        content = "| fr-001 | First req |\n| nfr-002 | Second req |\n"
        result = parse_requirement_ids_from_spec_md(content)
        assert "FR-001" in result["all"]
        assert "NFR-002" in result["all"]


class TestDeclaredVsCitedRequirements:
    """#3394: a spec.md may CITE a foreign mission's requirement id in prose
    (background/rationale text) without that citation being a requirement
    THIS spec declares and its work packages must therefore cover.

    Regression for the real-world repro (issue #3385, mission
    ``org-activation-scan-dirs-01KZY1PT``): the spec's prose cited
    ``CharterPackManager.activate``'s FR-021 default-pack materialization as
    background evidence for why the bug being fixed is easy to miss. FR-021
    belongs to a different, already-shipped part of the codebase; the citing
    mission does not implement it and never should have been forced to route
    it to a work package. ``finalize-tasks`` refused with
    ``"unmapped_functional_requirements": ["FR-021"]`` even though the
    spec's own 3 requirements were correctly mapped.
    """

    def test_prose_citation_of_foreign_fr_is_excluded_from_functional(self):
        """The reported defect, reproduced directly: a spec that declares its
        own FR-001..FR-003 in a table, and separately CITES a foreign FR-021
        in prose as background context, must not report FR-021 as declared.
        """
        content = (
            "## Background\n\n"
            "This bug is easy to miss -- see CharterPackManager.activate's "
            "FR-021 default-pack materialization for related prior art.\n\n"
            "### Functional Requirements\n\n"
            "| ID | Requirement | Status |\n"
            "|----|-------------|--------|\n"
            "| FR-001 | First requirement. | Open |\n"
            "| FR-002 | Second requirement. | Open |\n"
            "| FR-003 | Third requirement. | Open |\n"
        )
        result = parse_requirement_ids_from_spec_md(content)
        assert result["functional"] == ["FR-001", "FR-002", "FR-003"]
        assert "FR-021" not in result["functional"]
        assert "FR-021" not in result["all"]

    def test_mid_sentence_citation_excluded_even_without_any_table(self):
        """A bare prose mention, with no declaration shape anywhere, yields
        nothing declared -- it never promotes a citation to a requirement.
        """
        content = "# Spec\n\nAs established by FR-019 in another mission, this holds.\n"
        result = parse_requirement_ids_from_spec_md(content)
        assert result == {"all": [], "functional": []}

    def test_declared_table_row_shape(self):
        content = "### Functional Requirements\n\n| ID | Requirement |\n|---|---|\n| FR-007 | Do the thing. |\n"
        result = parse_requirement_ids_from_spec_md(content)
        assert result["functional"] == ["FR-007"]

    def test_declared_bold_table_cell_shape(self):
        """The id cell itself may be bold (``| **FR-016** | ... |``) -- common
        across the kitty-specs/ corpus."""
        content = "### Functional Requirements\n\n| ID | Requirement |\n|---|---|\n| **FR-016** | Do the thing. |\n"
        result = parse_requirement_ids_from_spec_md(content)
        assert result["functional"] == ["FR-016"]

    def test_declared_bullet_shape(self):
        content = "### Functional Requirements\n\n- **FR-008**: Do the thing.\n"
        result = parse_requirement_ids_from_spec_md(content)
        assert result["functional"] == ["FR-008"]

    def test_declared_bold_title_bullet_shape(self):
        """The bold span may wrap an id+title, not just the bare id
        (``- **NFR-001 -- complexity ceiling.** body...``)."""
        content = "### Non-Functional Requirements\n\n- **NFR-001 -- complexity ceiling.** Every function ...\n"
        result = parse_requirement_ids_from_spec_md(content)
        assert "NFR-001" in result["all"]

    def test_declared_heading_shape(self):
        """An id may itself open a subsection heading (``### FR-001: Title``)."""
        content = "## Functional Requirements\n\n### FR-001: Some Title\n\nBody text.\n"
        result = parse_requirement_ids_from_spec_md(content)
        assert result["functional"] == ["FR-001"]

    def test_declared_bold_paragraph_lead_without_bullet(self):
        """A bold id may lead a plain paragraph with no bullet marker at all
        (``**FR-019 -- title.** body...``)."""
        content = "## Functional Requirements\n\n**FR-019 -- consent lives in the project.** Today ...\n"
        result = parse_requirement_ids_from_spec_md(content)
        assert result["functional"] == ["FR-019"]

    def test_no_declared_shape_returns_empty_not_a_crash(self):
        """A Requirements section whose shape matches none of the three
        recognized declaration forms yields zero declared ids for that
        section (silent, not a hard failure) -- see the accompanying report
        for why a hard-fail-on-unparsed-section layer was prototyped and
        deliberately NOT shipped in this Op (real-corpus false-positive rate)."""
        content = "## Functional Requirements\n\nFR-001 must hold. FR-002 too.\n"
        result = parse_requirement_ids_from_spec_md(content)
        assert result == {"all": [], "functional": []}

    def test_prose_citation_of_foreign_nfr_and_c_is_excluded_from_all(self):
        """#3394 review F3: the four declared-shape patterns are genuinely
        prefix-agnostic, but every prior citation-exclusion test only
        exercised a cited FR- id. Pin the NFR-/C- behaviour explicitly: a
        cited foreign C-009 and NFR-014 in prose, alongside DECLARED ids of a
        different prefix, must not appear in "all".
        """
        content = (
            "## Background\n\n"
            "This mirrors the approach from C-009 (see the sibling mission's "
            "constraint) and NFR-014's latency budget, cited here only as prior art.\n\n"
            "### Functional Requirements\n\n"
            "| ID | Requirement |\n"
            "|----|-------------|\n"
            "| FR-001 | First requirement. |\n"
        )
        result = parse_requirement_ids_from_spec_md(content)
        assert result["all"] == ["FR-001"]
        assert "C-009" not in result["all"]
        assert "NFR-014" not in result["all"]


class TestFindUndeclaredRequirementCitations:
    """#3394 review F1: a soft, non-blocking signal for the declared-shape-miss
    case -- a spec whose requirements are written in NONE of the four
    recognized declared shapes yields zero declared ids silently from
    ``parse_requirement_ids_from_spec_md``. ``find_undeclared_requirement_citations``
    is the accompanying non-blocking diagnostic that flags this, without
    changing what counts as declared or gating anything.
    """

    def test_whole_document_bare_sentences_yield_a_warning(self):
        """The exact F1 scenario: a spec with no declared shape ANYWHERE
        still names its raw tokens in a warning instead of staying silent."""
        content = "## Functional Requirements\n\nFR-001 must hold. FR-002 too.\n"
        warnings = find_undeclared_requirement_citations(content)
        assert len(warnings) == 1
        assert "FR-001" in warnings[0]
        assert "FR-002" in warnings[0]

    def test_fully_declared_document_yields_no_warning(self):
        """No false positive: a spec whose requirements are declared in a
        recognized shape produces zero warnings."""
        content = "### Functional Requirements\n\n| ID | Requirement |\n|---|---|\n| FR-007 | Do the thing. |\n"
        assert find_undeclared_requirement_citations(content) == []

    def test_no_ref_tokens_at_all_yields_no_warning(self):
        """A spec with no FR/NFR/C tokens anywhere never warns."""
        assert find_undeclared_requirement_citations("# Spec\n\nJust prose, no requirements.\n") == []

    def test_requirements_heading_with_bare_sentences_warns_even_when_other_ids_are_declared(self):
        """The scoped case F1 explicitly calls out: a doc-wide declared-id
        check alone would MISS this, because the document as a whole has
        declared ids elsewhere (so the whole-document branch does not fire).
        The heading-scoped check still catches the "Functional Requirements"
        section that opens with plain, undeclared prose.
        """
        content = "## Non-Functional Requirements\n\n- **NFR-001**: Some constraint.\n\n## Functional Requirements\n\nFR-001 must hold. FR-002 too.\n"
        warnings = find_undeclared_requirement_citations(content)
        assert len(warnings) == 1
        assert "FR-001" in warnings[0]
        assert "FR-002" in warnings[0]
        assert "Functional Requirements" in warnings[0]

    def test_prose_citation_with_no_requirements_heading_and_other_declared_ids_does_not_warn(self):
        """The #3394 base-case citation scenario (foreign FR cited in a
        Background section, this spec's own FRs declared in a table)
        produces no warning -- the citation sentence is not itself inside a
        heading naming "requirement", and the document as a whole has
        declared ids, so neither warning branch fires.
        """
        content = (
            "## Background\n\n"
            "This bug is easy to miss -- see FR-021's default-pack materialization.\n\n"
            "### Functional Requirements\n\n"
            "| ID | Requirement |\n"
            "|----|-------------|\n"
            "| FR-001 | First requirement. |\n"
        )
        assert find_undeclared_requirement_citations(content) == []


class TestFindBareProseRequirementIds:
    """#3396: the NEW per-token, per-line, document-scoped blocking predicate.

    Unlike ``find_undeclared_requirement_citations`` (#3395), which fires only
    when a scope's *own* declared-id set is entirely empty, this predicate
    catches the mixed case: a section that declares SOME requirements
    correctly and writes OTHERS as bare, unbulleted, unbolded prose.
    """

    def test_story1_repro_mixed_declared_and_bare_prose_is_flagged(self):
        """Issue #3396's exact repro: a declared NFR-001 table row alongside
        bare-prose FR-001/FR-002 sentences under the same "Functional
        Requirements" heading must be flagged -- this is the mission's whole
        reason to exist."""
        content = (
            "### Functional Requirements\n\n"
            "FR-001 the loader must reject an unknown pack.\n"
            "FR-002 the error must name the offending path.\n\n"
            "| ID | Requirement |\n"
            "|----|-------------|\n"
            "| NFR-001 | Resolution completes within 200ms |\n"
        )
        result = find_bare_prose_requirement_ids(content)
        assert len(result) == 1
        assert result[0].section_heading == "Functional Requirements"
        assert result[0].ids == ["FR-001", "FR-002"]

    def test_story2_ac3_description_column_citation_not_flagged(self):
        """Story 2 AC3: a table row whose ID cell is properly declared but
        whose description column cites a foreign/malformed id-shaped token
        must produce NO candidate for that row -- the per-line skip rule
        that keeps this predicate from repeating #3395's rejected ~6%
        false-positive rate."""
        content = "### Functional Requirements\n\n| ID | Requirement |\n|----|-------------|\n| FR-001 | See FR-999 for related context. |\n"
        assert find_bare_prose_requirement_ids(content) == []

    def test_story5_fault_injection_surfaces_explicit_failure_not_silent_clean(self, monkeypatch):
        """Story 5 / NFR-002: when the classification logic hits an
        unresolvable state, the pure function must never silently return
        ``[]`` -- it must let the failure surface explicitly (here: the
        underlying exception propagates, rather than being swallowed into a
        quietly-clean result). The call-site conversion of that exception
        into a caller-visible blocking message is IC-04, delivered per call
        site elsewhere in this mission -- not tested here."""
        import specify_cli.requirement_mapping as rm

        def _boom(spec_content: str) -> list[tuple[str, str]]:
            raise RuntimeError("simulated unresolvable classification state")

        monkeypatch.setattr(rm, "_requirement_named_sections", _boom)
        content = "### Functional Requirements\n\nFR-001 the loader must reject an unknown pack.\n"
        with pytest.raises(RuntimeError, match="simulated unresolvable classification state"):
            rm.find_bare_prose_requirement_ids(content)

    def test_story4_negative_space_foreign_citation_outside_requirements_section_not_flagged(self):
        """Story 4 / #3394 negative-space pin: a spec whose own requirements
        are all declared correctly, citing a foreign id in prose OUTSIDE any
        Requirements-named section, must not produce a candidate -- the two
        stories are inseparable."""
        content = (
            "## Background\n\n"
            "This bug is easy to miss -- see FR-021's default-pack materialization.\n\n"
            "### Functional Requirements\n\n"
            "| ID | Requirement |\n"
            "|----|-------------|\n"
            "| FR-001 | First requirement. |\n"
        )
        assert find_bare_prose_requirement_ids(content) == []


class TestNormalizeRequirementRefsValue:
    """Test normalize_requirement_refs_value()."""

    def test_string_input(self):
        assert normalize_requirement_refs_value("FR-001, FR-002") == [
            "FR-001",
            "FR-002",
        ]

    def test_list_of_strings(self):
        assert normalize_requirement_refs_value(["FR-001", "NFR-002"]) == [
            "FR-001",
            "NFR-002",
        ]

    def test_mixed_list(self):
        assert normalize_requirement_refs_value(["FR-001", 42, "NFR-002"]) == [
            "FR-001",
            "NFR-002",
        ]

    def test_empty_list(self):
        assert normalize_requirement_refs_value([]) == []

    def test_none(self):
        assert normalize_requirement_refs_value(None) == []

    def test_deduplicates(self):
        assert normalize_requirement_refs_value(["FR-001", "FR-001"]) == ["FR-001"]

    def test_uppercases(self):
        assert normalize_requirement_refs_value(["fr-001"]) == ["FR-001"]


class TestReadAllWpRequirementRefs:
    """Test read_all_wp_requirement_refs()."""

    def test_reads_from_wp_frontmatter(self, tmp_path: Path):
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01-test.md").write_text(
            '---\nwork_package_id: "WP01"\ntitle: "WP01"\nrequirement_refs:\n  - FR-001\n  - FR-002\n---\n\n# WP01\n',
            encoding="utf-8",
        )
        (tasks_dir / "WP02-test.md").write_text(
            '---\nwork_package_id: "WP02"\ntitle: "WP02"\n---\n\n# WP02\n',
            encoding="utf-8",
        )

        result = read_all_wp_requirement_refs(tasks_dir)
        assert result["WP01"] == ["FR-001", "FR-002"]
        assert result["WP02"] == []

    def test_returns_empty_for_missing_dir(self, tmp_path: Path):
        assert read_all_wp_requirement_refs(tmp_path / "nonexistent") == {}


class TestReadAllWpRawRequirementRefs:
    """Test read_all_wp_raw_requirement_refs()."""

    def test_preserves_malformed_values(self, tmp_path: Path):
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01-test.md").write_text(
            '---\nwork_package_id: "WP01"\ntitle: "WP01"\nrequirement_refs:\n  - FR-001\n  - BOGUS\n---\n\n# WP01\n',
            encoding="utf-8",
        )

        result = read_all_wp_raw_requirement_refs(tasks_dir)
        assert "FR-001" in result["WP01"]
        assert "BOGUS" in result["WP01"]

    def test_normalized_reader_drops_malformed(self, tmp_path: Path):
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01-test.md").write_text(
            '---\nwork_package_id: "WP01"\ntitle: "WP01"\nrequirement_refs:\n  - FR-001\n  - BOGUS\n---\n\n# WP01\n',
            encoding="utf-8",
        )

        normalized = read_all_wp_requirement_refs(tasks_dir)
        assert "FR-001" in normalized["WP01"]
        assert "BOGUS" not in normalized["WP01"]

    def test_splits_scalar_string(self, tmp_path: Path):
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01-test.md").write_text(
            '---\nwork_package_id: "WP01"\ntitle: "WP01"\nrequirement_refs: "FR-002, FR-003"\n---\n\n# WP01\n',
            encoding="utf-8",
        )

        result = read_all_wp_raw_requirement_refs(tasks_dir)
        assert "FR-002" in result["WP01"]
        assert "FR-003" in result["WP01"]

    def test_surfaces_non_string_items(self, tmp_path: Path):
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01-test.md").write_text(
            '---\nwork_package_id: "WP01"\ntitle: "WP01"\nrequirement_refs:\n  - FR-001\n  - 42\n---\n\n# WP01\n',
            encoding="utf-8",
        )

        result = read_all_wp_raw_requirement_refs(tasks_dir)
        assert "FR-001" in result["WP01"]
        non_string_tokens = [token for token in result["WP01"] if token.startswith("<NON_STRING:")]
        assert len(non_string_tokens) == 1
        assert "42" in non_string_tokens[0]


class TestDeliveryLabelledRequirementRows:
    """A trailing ``Delivery`` / ``No-op passable?`` column pair must never
    change which requirement ids are declared, nor the functional set the
    production requirement-coverage path computes (the label sits in
    trailing columns only, never in/before the id cell -- the id-parser
    patterns themselves are not widened).

    Every "this row is not declared" assertion here is paired with a
    same-fixture "this row IS declared" positive control (the correctly
    labelled FR-001 row), per the ``acceptance-criteria-non-vacuity``
    doctrine tactic (referenced here by id only -- the rule definition
    stays in that one tactic).
    """

    # One fixture: a correctly labelled row (FR-001) and a mis-placed-label
    # row whose label sits INSIDE the id cell (FR-002) -- the exact
    # placement violation this rule forbids. Same fixture, same table, so
    # the "not declared" result for FR-002 is proven against a positive
    # control (FR-001, declared) rather than in isolation.
    _SPEC_LABELLED = """## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Title | story | High | Open | [build] | no |
| FR-002 [ratchet] | Title | story | High | Open | | |
"""

    # The labelled fixture's twin: the same correctly-labelled row with the
    # two trailing columns removed entirely (the pre-Delivery-column shape). The
    # mis-placed-label row has no twin counterpart -- its id was never
    # declared regardless of the trailing columns' presence, so "labelled
    # rows only, excluding the mis-placed one" means comparing FR-001 alone.
    _SPEC_TWIN = """## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Title | story | High | Open |
"""

    # A trailing label column that CITES another declared id (a `[folded]`
    # row naming the row it is satisfied by) -- distinct from the mis-placed
    # case above: the id cell itself is untouched, only the Delivery column
    # carries the citation.
    # The bare-prose line (FR-099) is the positive control: it proves the
    # detector run against THIS fixture can still find a genuinely
    # undeclared id, so the citation row's "not found" result below is not
    # merely a collapsed, always-empty detector.
    _SPEC_CITING_LABEL = """## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Title | story | High | Open | [build] | no |
| FR-010 | Title | story | High | Open | [folded] (FR-001) | no |

FR-099 must hold.
"""

    def test_mis_placed_label_row_is_not_declared(self) -> None:
        """Positive control: FR-001 (same fixture) IS declared; FR-002 is not."""
        parsed = parse_requirement_ids_from_spec_md(self._SPEC_LABELLED)
        assert "FR-001" in parsed["functional"]
        assert "FR-002" not in parsed["functional"]
        assert "FR-002" not in parsed["all"]

    def test_labelled_and_twin_yield_identical_functional_sets(self) -> None:
        labelled = parse_requirement_ids_from_spec_md(self._SPEC_LABELLED)
        twin = parse_requirement_ids_from_spec_md(self._SPEC_TWIN)
        assert labelled["functional"] == twin["functional"] == ["FR-001"]

    def test_labelled_and_twin_give_same_unmapped_set_through_production_path(self) -> None:
        """Drive the SAME pure decision core ``map-requirements`` calls
        (``plan_mapping`` -> ``compute_coverage``), not a re-implementation.
        """
        labelled_ids = parse_requirement_ids_from_spec_md(self._SPEC_LABELLED)
        twin_ids = parse_requirement_ids_from_spec_md(self._SPEC_TWIN)

        # Same WP refs on both sides -- and nothing is mapped, so FR-001 (the
        # only functional id either fixture declares) must show up as
        # unmapped on BOTH sides. An empty ``existing_all_refs`` also means
        # this assertion cannot pass vacuously the way a fully-mapped one
        # would if a declaration silently dropped: dropping FR-001's
        # declaration on either side would flip its ``unmapped_fr`` to
        # ``[]``, a real, observable difference.
        existing_all_refs: dict[str, list[str]] = {"WP01": []}

        labelled_plan = plan_mapping(
            MappingRequest(
                spec_all_ids=frozenset(labelled_ids["all"]),
                spec_functional_ids=frozenset(labelled_ids["functional"]),
                new_mappings={},
                existing_all_refs=existing_all_refs,
                tasks_md_refs={},
                mode="wp_refs",
                replace=False,
            )
        )
        twin_plan = plan_mapping(
            MappingRequest(
                spec_all_ids=frozenset(twin_ids["all"]),
                spec_functional_ids=frozenset(twin_ids["functional"]),
                new_mappings={},
                existing_all_refs=existing_all_refs,
                tasks_md_refs={},
                mode="wp_refs",
                replace=False,
            )
        )

        # The exact-set equality above already proves the mis-placed-label
        # row (FR-002) is undeclared on the labelled side -- it never even
        # reaches the coverage projection, it is neither mapped nor
        # unmapped, it simply does not exist.
        assert labelled_plan.unmapped_fr == twin_plan.unmapped_fr == ["FR-001"]

    def test_trailing_label_citation_does_not_create_bare_prose_finding(self) -> None:
        """A `[folded] (FR-001)` citation inside a properly declared row's
        trailing Delivery column must not be mistaken for a bare-prose,
        undeclared requirement id -- proven on the SAME fixture as a
        positive control: the fixture's genuinely bare-prose `FR-099` line
        IS reported, so the citation's absence is not a vacuous, always-
        empty result.
        """
        result = find_bare_prose_requirement_ids(self._SPEC_CITING_LABEL)
        assert len(result) == 1
        candidate = result[0]
        assert candidate.ids == ["FR-099"]
        assert "FR-001" not in candidate.ids
