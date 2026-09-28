"""Testing/bug-fixing/BDD doctrine single-owner tests (WP05, epic #5218).

Resolves the 10 contradictions research R-9 pins for the testing, bug-fixing
and BDD doctrine surfaces so each rule has exactly one owner:

(a) ``bug-fixing-checklist`` (tactic) is retired; its four unique lines were
    folded into the ``test-first-bug-fixing`` procedure.
(b) ``test-first-bug-fixing`` carries a "refactor after the fix" instruction
    and states the commit-topology carve-out (test+fix together, unless a
    failing reproduction already landed on the mainline).
(c) The TypeScript mutation toolguide's CI break-gate example is an opt-in,
    with ``break: 0`` as the shipped default.
(d) Exactly one artifact (the ``mutation-testing-workflow`` tactic) carries a
    mutation band table; no other artifact states a numeric mutation target.
(e) ``testing-principles`` no longer defines "Predictive", "Inspiring", or
    "Clear Test Boundaries" (or a same-named rename), and references
    ``quadruple-a-test-format`` instead of restating its inline copy.
(f) The tactic id ``bdd-scenario-formulation`` exists under
    ``tactics/testing/``; the old id ``behavior-driven-development`` (tactic)
    is retired.
(g) ``development-bdd``'s step/reference order puts example mapping
    (Discovery) before Formulation, per the BDD paradigm's cycle order.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from tests.doctrine.conftest import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]

_PACKS_BUILT_IN = REPO_ROOT / "packs" / "built-in"
_TACTICS = _PACKS_BUILT_IN / "tactics"
_TACTICS_TESTING = _TACTICS / "testing"
_PROCEDURES = _PACKS_BUILT_IN / "procedures"
_STYLEGUIDES = _PACKS_BUILT_IN / "styleguides"
_TOOLGUIDES = _PACKS_BUILT_IN / "toolguides"
_DIRECTIVES = _PACKS_BUILT_IN / "directives"
_PARADIGMS = _PACKS_BUILT_IN / "paradigms"

# Artifacts that are allowed to carry a numeric mutation band/target table.
# Exactly one artifact in the whole owned surface may carry one -- everywhere
# else must point at it instead of restating the table.
_MUTATION_TABLE_OWNER = _TACTICS_TESTING / "mutation-testing-workflow.tactic.yaml"

# A mutation "band table" is any place that pairs a percentage range/threshold
# with a verdict word -- a markdown table row or a YAML value doing the same.
_MUTATION_BAND_PATTERN = re.compile(
    r"(\d{1,3}\s*%|\d{1,3}\s*-\s*\d{1,3}\s*%|>\s*\d{1,3}\s*%|<\s*\d{1,3}\s*%)"
    r".{0,40}(strong|good|moderate|weak|structurally weak)",
    re.IGNORECASE,
)

_CANDIDATE_MUTATION_SURFACES = [
    _TACTICS_TESTING / "mutation-testing-workflow.tactic.yaml",
    _STYLEGUIDES / "mutation-aware-test-design.styleguide.yaml",
    _TOOLGUIDES / "PYTHON_MUTATION_TOOLS.md",
    _TOOLGUIDES / "TYPESCRIPT_MUTATION_TOOLS.md",
    _DIRECTIVES / "use-mutation-testing-to-validate-test-quality.directive.yaml",
]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _yaml(path: Path) -> dict:
    return yaml.safe_load(_text(path))


class TestBugFixingChecklistRetired:
    """(a) bug-fixing-checklist is absent; its lines live in test-first-bug-fixing."""

    def test_bug_fixing_checklist_tactic_file_absent(self) -> None:
        stray = _TACTICS_TESTING / "bug-fixing-checklist.tactic.yaml"
        assert not stray.exists(), f"bug-fixing-checklist must be deleted -- test-first-bug-fixing is the single owner (#5220): {stray}"

    def test_test_first_bug_fixing_states_expected_actual_in_one_sentence(self) -> None:
        content = _text(_PROCEDURES / "test-first-bug-fixing.procedure.yaml")
        assert "one sentence" in content.lower(), "test-first-bug-fixing must fold in the bug-fixing-checklist line: state expected/actual in one sentence"

    def test_test_first_bug_fixing_states_cannot_write_test_means_not_understood(self) -> None:
        content = _text(_PROCEDURES / "test-first-bug-fixing.procedure.yaml")
        assert "not" in content and "understood" in content, (
            "test-first-bug-fixing must fold in: if you cannot write the reproduction test, the defect is not understood"
        )

    def test_test_first_bug_fixing_states_document_root_cause_and_fix(self) -> None:
        content = _text(_PROCEDURES / "test-first-bug-fixing.procedure.yaml").lower()
        assert "root cause" in content, "test-first-bug-fixing must fold in: document the root cause and the fix"

    def test_test_first_bug_fixing_states_test_after_fix_is_confirmation_only(self) -> None:
        content = _text(_PROCEDURES / "test-first-bug-fixing.procedure.yaml").lower()
        assert "confirmation" in content, "test-first-bug-fixing must fold in: a test written after the fix is only a confirmation test, not a regression test"


class TestTestFirstBugFixingTopologyAndRefactor:
    """(b) refactor-after instruction + commit-topology carve-out."""

    def test_states_refactor_after_green_before_the_fix_step(self) -> None:
        procedure = _yaml(_PROCEDURES / "test-first-bug-fixing.procedure.yaml")
        steps = procedure["steps"]
        titles = " ".join(step.get("title", "") + " " + step.get("description", "") for step in steps).lower()
        assert "refactor" in titles, "test-first-bug-fixing must state a refactor-after-green instruction, scoped to the fix's own code"

    def test_states_tidy_first_before_red_reproduction_with_025_citation(self) -> None:
        # Recorded decision: tidy-first is a separate, behaviour-preserving
        # commit on the surfaces the fix will touch, made BEFORE the red
        # reproduction test -- DIRECTIVE_025 (Boy Scout Rule) owns that rule,
        # so this procedure cites it by id instead of restating it.
        procedure = _yaml(_PROCEDURES / "test-first-bug-fixing.procedure.yaml")
        steps = procedure["steps"]
        step_texts = [step.get("title", "") + " " + step.get("description", "") for step in steps]
        tidy_index = next((i for i, t in enumerate(step_texts) if "tidy" in t.lower()), None)
        repro_index = next((i for i, t in enumerate(step_texts) if "failing test that reproduces" in t.lower()), None)
        assert tidy_index is not None, "test-first-bug-fixing must state a tidy-first step"
        assert repro_index is not None, "test-first-bug-fixing must state the red reproduction-test step"
        assert tidy_index < repro_index, "tidy-first must be ordered explicitly BEFORE the red reproduction test, not merely before the fix"
        ref_ids = {ref["id"] for ref in procedure.get("references", [])}
        assert "DIRECTIVE_025" in ref_ids, "test-first-bug-fixing must cite DIRECTIVE_025 for the tidy-first rule instead of restating it"

    def test_states_commit_topology_carve_out(self) -> None:
        content = _text(_PROCEDURES / "test-first-bug-fixing.procedure.yaml").lower()
        assert "red-main-release-discipline" in content or "already landed" in content, (
            "test-first-bug-fixing must state the commit-topology carve-out: test+fix commit together, unless a failing reproduction already landed on the mainline"
        )

    def test_references_034_and_red_main(self) -> None:
        # disciplined-defect-diagnosis already requires test-first-bug-fixing
        # (diagnose, then fix); a formal back-reference here would mint a
        # requires cycle, so the hand-off is prose-only in the "Understand
        # the bug" step, and the reverse edge is a curated suggests for WP09.
        procedure = _yaml(_PROCEDURES / "test-first-bug-fixing.procedure.yaml")
        ref_ids = {ref["id"] for ref in procedure.get("references", [])}
        expected = {"DIRECTIVE_034", "red-main-release-discipline"}
        missing = expected - ref_ids
        assert not missing, f"test-first-bug-fixing must reference {expected}, missing: {missing}"

    def test_mentions_disciplined_defect_diagnosis_handoff_in_prose(self) -> None:
        content = _text(_PROCEDURES / "test-first-bug-fixing.procedure.yaml")
        assert "disciplined-defect-diagnosis" in content, (
            "test-first-bug-fixing must mention disciplined-defect-diagnosis as the"
            " hard-bug hand-off (kept prose-only to avoid a requires cycle with its"
            " existing test-first-bug-fixing reference)"
        )

    def test_tdd_red_green_refactor_has_no_stray_refactor_after_fix_duplicate_wording(self) -> None:
        # tdd-red-green-refactor already states its own Refactor step; this is a
        # canary that no bug-fixing-checklist wording leaked into it verbatim.
        content = _text(_TACTICS_TESTING / "tdd-red-green-refactor.tactic.yaml")
        assert "Adapted from patterns.sddevelopment.be" not in content, "tdd-red-green-refactor must not absorb bug-fixing-checklist's notes verbatim"


class TestDisciplinedDefectDiagnosisNoChecklistCitation:
    """checklist citation removed; minimal-fix wording softened."""

    def test_no_bug_fixing_checklist_reference(self) -> None:
        procedure = _yaml(_PROCEDURES / "disciplined-defect-diagnosis.procedure.yaml")
        ref_ids = {ref["id"] for ref in procedure.get("references", [])}
        assert "bug-fixing-checklist" not in ref_ids, "disciplined-defect-diagnosis must drop its bug-fixing-checklist reference (retired id)"

    def test_minimal_fix_wording_is_proportional_to_diagnosed_cause(self) -> None:
        content = _text(_PROCEDURES / "disciplined-defect-diagnosis.procedure.yaml").lower()
        assert "proportional to the diagnosed cause" in content, "disciplined-defect-diagnosis must soften 'minimal fix' to 'proportional to the diagnosed cause'"


class TestMutationSingleOwner:
    """(c)/(d) exactly one mutation band table; TS CI gate is opt-in with break: 0."""

    def test_mutation_testing_workflow_carries_the_band_table(self) -> None:
        content = _text(_MUTATION_TABLE_OWNER)
        assert _MUTATION_BAND_PATTERN.search(content), "mutation-testing-workflow must carry the single mutation band table (framed as triage bands)"

    def test_mutation_table_owner_uses_triage_framing_not_a_numeric_target(self) -> None:
        # Recorded decision: no numeric target -- one table, framed as triage
        # bands (a signal for where to look, not a goal).
        content = _text(_MUTATION_TABLE_OWNER).lower()
        assert "triage band" in content, "mutation-testing-workflow must frame its band table as triage bands"
        assert "target mutation score" not in content, "mutation-testing-workflow must not frame the band table as a numeric target"

    @pytest.mark.parametrize("surface", [s for s in _CANDIDATE_MUTATION_SURFACES if s != _MUTATION_TABLE_OWNER])
    def test_no_other_surface_carries_a_mutation_band_table(self, surface: Path) -> None:
        content = _text(surface)
        matches = _MUTATION_BAND_PATTERN.findall(content)
        assert not matches, f"{surface}: mutation band/target table must be removed -- mutation-testing-workflow is the single owner (#5220): {matches}"

    def test_no_target_80_percent_phrase_anywhere_in_owned_mutation_surfaces(self) -> None:
        for surface in _CANDIDATE_MUTATION_SURFACES:
            content = _text(surface)
            assert "target 80" not in content.lower(), f"{surface}: must not restate a 'Target 80%' mutation goal"

    _BREAK_60_PATTERN = re.compile(r'"?break"?\s*:\s*60')

    def test_no_break_60_ci_gate_example_anywhere(self) -> None:
        for surface in _CANDIDATE_MUTATION_SURFACES:
            content = _text(surface)
            assert not self._BREAK_60_PATTERN.search(content), (
                f"{surface}: CI break-gate example must use break: 0 as the shipped default, not break: 60"
                ' (matches both YAML `break: 60` and JSON `"break": 60` forms)'
            )

    def test_typescript_toolguide_ci_example_is_marked_opt_in_with_break_zero(self) -> None:
        content = _text(_TOOLGUIDES / "TYPESCRIPT_MUTATION_TOOLS.md")
        assert "break: 0" in content, "TypeScript mutation toolguide's CI example must default to break: 0"
        assert "opt-in" in content.lower() or "opt in" in content.lower(), "TypeScript mutation toolguide's CI break-gate example must be marked as an opt-in"
        assert '"break": 0' in content, (
            'TypeScript mutation toolguide\'s CI JSON example itself must carry "break": 0 --'
            " prose alone ('ships break: 0') is not enough to pin the example against a reverted break: 60"
        )

    def test_directive_keeps_signal_not_a_gate_framing(self) -> None:
        content = _text(_DIRECTIVES / "use-mutation-testing-to-validate-test-quality.directive.yaml").lower()
        assert "signal" in content and "not" in content, "use-mutation-testing-to-validate-test-quality must keep the 'signal, not a gate' framing"


class TestTestingPrinciplesTermsSingleOwner:
    """(e) testing-principles drops colliding terms; references quadruple-a by id."""

    def test_no_literal_predictive_term(self) -> None:
        content = _text(_STYLEGUIDES / "testing-principles.styleguide.yaml")
        assert '"Predictive' not in content, "testing-principles must not define 'Predictive' -- test-desiderata-and-boundaries owns it"

    def test_no_literal_inspiring_term(self) -> None:
        content = _text(_STYLEGUIDES / "testing-principles.styleguide.yaml")
        assert '"Inspiring' not in content, "testing-principles must not define 'Inspiring' -- test-desiderata-and-boundaries owns it"

    def test_no_clear_test_boundaries_pattern_name(self) -> None:
        content = _text(_STYLEGUIDES / "testing-principles.styleguide.yaml")
        assert "Clear Test Boundaries" not in content, (
            "testing-principles must not define/rename-in-place 'Clear Test Boundaries' -- test-desiderata-and-boundaries owns the boundary sense"
        )

    def test_references_quadruple_a_test_format_by_id(self) -> None:
        styleguide = _yaml(_STYLEGUIDES / "testing-principles.styleguide.yaml")
        refs = styleguide.get("references", [])
        flat = " ".join(str(r) for r in refs)
        assert "quadruple-a-test-format" in flat, "testing-principles must reference quadruple-a-test-format by id instead of restating the Quad-A pattern"

    def test_no_inline_quad_a_test_structure_pattern_restated(self) -> None:
        content = _text(_STYLEGUIDES / "testing-principles.styleguide.yaml")
        assert "Quad-A Test Structure" not in content, "testing-principles must trim the inline Quad-A pattern and reference quadruple-a-test-format by id instead"


class TestInspiringCitationsRetargeted:
    """Inspiring citations move to test-desiderata-and-boundaries."""

    def test_test_to_system_reconstruction_cites_desiderata_for_inspiring(self) -> None:
        tactic = _yaml(_TACTICS_TESTING / "test-to-system-reconstruction.tactic.yaml")
        refs = [r for r in tactic.get("references", []) if "inspiring" in r.get("when", "").lower()]
        assert refs, "test-to-system-reconstruction's Inspiring citation must exist"
        assert all(r["id"] == "test-desiderata-and-boundaries" for r in refs), (
            "test-to-system-reconstruction's Inspiring citation must retarget from testing-principles to test-desiderata-and-boundaries"
        )


class TestBddScenarioFormulationSingleOwner:
    """(f) bdd-scenario-formulation exists under tactics/testing/; old id retired."""

    def test_old_behavior_driven_development_tactic_file_absent(self) -> None:
        stray = _TACTICS / "behavior-driven-development.tactic.yaml"
        assert not stray.exists(), f"behavior-driven-development (tactic) must be deleted -- renamed to bdd-scenario-formulation (#5220): {stray}"

    def test_bdd_scenario_formulation_exists_under_tactics_testing(self) -> None:
        new_home = _TACTICS_TESTING / "bdd-scenario-formulation.tactic.yaml"
        assert new_home.exists(), f"bdd-scenario-formulation must exist at {new_home}"
        tactic = _yaml(new_home)
        assert tactic["id"] == "bdd-scenario-formulation"

    def test_bdd_scenario_formulation_references_given_when_then_gherkin_and_lifecycle(self) -> None:
        tactic = _yaml(_TACTICS_TESTING / "bdd-scenario-formulation.tactic.yaml")
        ref_ids = {ref["id"] for ref in tactic.get("references", [])}
        expected = {"given-when-then-authoring", "gherkin", "bdd-scenario-lifecycle"}
        missing = expected - ref_ids
        assert not missing, f"bdd-scenario-formulation must reference {expected}, missing: {missing}"

    def test_paradigm_id_behaviour_driven_development_is_not_renamed(self) -> None:
        # The paradigm keeps its (British-spelling) id -- only the tactic id moved.
        paradigm = _yaml(_PARADIGMS / "behaviour-driven-development.paradigm.yaml")
        assert paradigm["id"] == "behaviour-driven-development"


class TestDevelopmentBddDiscoveryBeforeFormulation:
    """(g) development-bdd's order follows the paradigm's Discovery -> Formulation cycle."""

    def test_references_example_mapping_workshop_before_bdd_scenario_formulation(self) -> None:
        tactic = _yaml(_TACTICS / "architecture" / "development-bdd.tactic.yaml")
        refs = tactic.get("references", [])
        ref_ids = [r["id"] for r in refs]
        assert "example-mapping-workshop" in ref_ids, "development-bdd must reference example-mapping-workshop (Discovery)"
        assert "bdd-scenario-formulation" in ref_ids, (
            "development-bdd must reference bdd-scenario-formulation (Formulation), not the retired behavior-driven-development id"
        )
        discovery_index = ref_ids.index("example-mapping-workshop")
        formulation_index = ref_ids.index("bdd-scenario-formulation")
        assert discovery_index < formulation_index, (
            "development-bdd must order Discovery (example-mapping-workshop) before Formulation (bdd-scenario-formulation), per the paradigm's cycle order"
        )

    def test_no_stray_reference_to_retired_behavior_driven_development_tactic_id(self) -> None:
        # Widened (review cycle 1): must catch the bare id in prose, not only
        # a YAML `references` entry -- development-bdd's own purpose text
        # named the retired tactic by id outside of `references`.
        content = _text(_TACTICS / "architecture" / "development-bdd.tactic.yaml")
        assert "behavior-driven-development" not in content, (
            "development-bdd must not reference the retired behavior-driven-development tactic id,"
            " in a references entry or in prose -- cite bdd-scenario-formulation instead"
        )


class TestBddParadigmReferencesPractices:
    """The BDD paradigm gains references to its practices, if the schema allows it."""

    def test_paradigm_references_its_practices(self) -> None:
        paradigm = _yaml(_PARADIGMS / "behaviour-driven-development.paradigm.yaml")
        ref_ids = {r["id"] for r in paradigm.get("references", [])}
        expected = {"bdd-scenario-formulation", "bdd-scenario-lifecycle", "given-when-then-authoring", "gherkin"}
        missing = expected - ref_ids
        assert not missing, f"behaviour-driven-development paradigm must reference {expected}, missing: {missing}"


class TestGherkinToolchainNotesLiveInToolguide:
    """BDD tactic's toolchain notes move into GHERKIN.md / gherkin.toolguide.yaml."""

    def test_bdd_scenario_formulation_does_not_restate_full_toolchain_landscape(self) -> None:
        content = _text(_TACTICS_TESTING / "bdd-scenario-formulation.tactic.yaml")
        assert "Cucumber-JVM" not in content, (
            "bdd-scenario-formulation must not restate the toolchain landscape -- it belongs in GHERKIN.md / gherkin.toolguide.yaml"
        )


class TestNoIssueReferencesInPackProse:
    """New/rewritten owned artifacts must not carry #NNNN issue references.

    Scoped to the artifacts this WP creates or substantially rewrites --
    surfaces with a PRE-EXISTING, already-baselined provenance comment
    (``tests/architectural/_builtin_pack_provenance_baseline.yaml``, e.g.
    directives 030/034's ``#3009`` migration note) are out of scope; the
    shrink-only ratchet governs those, not this WP.
    """

    @pytest.mark.parametrize(
        "surface",
        [
            _PROCEDURES / "test-first-bug-fixing.procedure.yaml",
            _PROCEDURES / "disciplined-defect-diagnosis.procedure.yaml",
            _PROCEDURES / "bdd-scenario-lifecycle.procedure.yaml",
            _TACTICS_TESTING / "mutation-testing-workflow.tactic.yaml",
            _TACTICS_TESTING / "tdd-red-green-refactor.tactic.yaml",
            _STYLEGUIDES / "mutation-aware-test-design.styleguide.yaml",
            _DIRECTIVES / "036-black-box-integration-testing.directive.yaml",
            _DIRECTIVES / "use-mutation-testing-to-validate-test-quality.directive.yaml",
            _PARADIGMS / "behaviour-driven-development.paradigm.yaml",
            _TACTICS_TESTING / "bdd-scenario-formulation.tactic.yaml",
        ],
    )
    def test_no_hash_issue_reference(self, surface: Path) -> None:
        if not surface.exists():
            pytest.skip(f"{surface} does not exist yet")
        content = _text(surface)
        assert not re.search(r"#\d{3,5}\b", content), f"{surface}: pack prose must not cite #NNNN issue references"
