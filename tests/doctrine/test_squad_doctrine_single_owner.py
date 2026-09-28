"""Red-first owner test for squad-doctrine-single-owner-01M3KBP7 WP04 (#5219, #5221).

Pins the shape of the single-owner fold: ``adversarial-squad-deployment`` (the
procedure) becomes the ONLY shipped artifact that states the squad playbook,
the point-cut list, the profile-per-task rule, and the findings-disposition
contract. Every other citer references it by id instead of restating it, and
the ``adversarial-squad-cadence`` styleguide is deleted.

This test is authored RED (T015) before the content change (T016-T020).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.offering import pack_paths
from charter.offering.agent_profiles.repository import AgentProfileRepository
from charter.offering.artifact_kinds import ArtifactKind

from tests.doctrine._single_owner_detectors import (
    has_headcount_language,
    restates_point_cut_list,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUILT_IN_ROOT = pack_paths.built_in_root()

_PROCEDURE_PATH = _BUILT_IN_ROOT / "procedures" / "adversarial-squad-deployment.procedure.yaml"
_TRACER_PROCEDURE_PATH = _BUILT_IN_ROOT / "procedures" / "mission-tracer-files.procedure.yaml"
_STYLEGUIDE_PATH = _BUILT_IN_ROOT / "styleguides" / "adversarial-squad-cadence.styleguide.yaml"
_BROWNFIELD_PATH = _BUILT_IN_ROOT / "paradigms" / "brownfield-onboarding.paradigm.yaml"
_DIRECTIVE_040_PATH = _BUILT_IN_ROOT / "directives" / "040-recurring-bug-structural-intervention.directive.yaml"
_DIRECTIVE_043_PATH = _BUILT_IN_ROOT / "directives" / "043-close-defect-class-by-construction.directive.yaml"
_DIRECTIVE_052_PATH = _BUILT_IN_ROOT / "directives" / "052-prefer-durable-fixes.directive.yaml"
_FIVE_PARADIGM_PATH = _BUILT_IN_ROOT / "tactics" / "five-paradigm-parallel-debugging.tactic.yaml"
_PAULA_TACTIC_PATH = _BUILT_IN_ROOT / "tactics" / "architecture" / "paula-patterns-architecture-scout-review.tactic.yaml"
_ACCEPTANCE_NON_VACUITY_PATH = _BUILT_IN_ROOT / "tactics" / "testing" / "acceptance-criteria-non-vacuity.tactic.yaml"
_SKILL_PATH = _REPO_ROOT / "src" / "charter" / "offering" / "skills" / "adversarial-squad" / "SKILL.md"

_CASTING_ANCHOR = "Example casting (examples, not rules):"
_CASTING_LINE_RE = re.compile(r"^\s*-\s*(?P<label>[a-z][a-z-]*)\s*:\s*(?P<ids>(?:`[a-z][a-z0-9-]*`,?\s*)+)—", re.MULTILINE)
_ID_RE = re.compile(r"`([a-z][a-z0-9-]*)`")

_VALID_CASTING_LABELS = frozenset({"pre-spec", "post-spec", "post-plan", "post-tasks", "pre-merge", "ad-hoc", "escalation"})

# Fixture reproducing the pre-change SKILL.md "When to use" block, byte-for-byte
# (the old point-cut restatement this WP removes). Used as the detector's
# positive control so a vacuous detector cannot pass silently.
_OLD_SKILL_WHEN_TO_USE_FIXTURE = """\
A squad is worth its tokens at a high-leverage point-cut where one reviewer's blind spot
is expensive:

- **after `/spec-kitty.specify`** -> pre-spec investigation (scope, prior art, live repros)
- **after `/spec-kitty.plan`** -> post-planning brownfield check (foldable issues, split-brain, deprecations)
- **after `/spec-kitty.tasks`** -> post-tasks anti-laziness pass (fakeable DoDs, decomposition realism)
- **before merge** -> architectural-gate / cross-base sweep
- **ad-hoc decision** -> proponent + adversaries + synthesizer (e.g. delete-vs-migrate)
"""


def _load_yaml(path: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.load(handle) or {}
    assert isinstance(data, dict), f"{path}: expected mapping root"
    return data


def _raw_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _procedure() -> dict[str, Any]:
    return _load_yaml(_PROCEDURE_PATH)


def _procedure_step_descriptions() -> list[str]:
    return [step.get("description", "") for step in _procedure().get("steps", [])]


def _procedure_anti_pattern_descriptions() -> list[str]:
    return [ap.get("description", "") for ap in _procedure().get("anti_patterns", [])]


def _profile_repo() -> AgentProfileRepository:
    return AgentProfileRepository(built_in_dir=pack_paths.built_in_dir(ArtifactKind.AGENT_PROFILE))


def _parse_casting_block(text: str) -> list[tuple[str, list[str]]]:
    """Parse the procedure notes' casting table into (label, [ids]) rows."""
    anchor_index = text.index(_CASTING_ANCHOR)
    tail = text[anchor_index:]
    rows: list[tuple[str, list[str]]] = []
    for match in _CASTING_LINE_RE.finditer(tail):
        label = match.group("label")
        ids = _ID_RE.findall(match.group("ids"))
        rows.append((label, ids))
    return rows


# ---------------------------------------------------------------------------
# FR-001 -- the profile-per-task rule
# ---------------------------------------------------------------------------


def test_procedure_states_the_profile_per_task_rule() -> None:
    text = _raw_text(_PROCEDURE_PATH)
    assert "Choose profiles whose declared focus answers this point-cut's question." in text


# ---------------------------------------------------------------------------
# FR-002 -- the single point-cut list
# ---------------------------------------------------------------------------


def test_point_cut_detector_positive_control() -> None:
    """The detector must flag the pre-change SKILL.md 'When to use' block."""
    assert restates_point_cut_list(_OLD_SKILL_WHEN_TO_USE_FIXTURE)


def test_procedure_owns_the_point_cut_list() -> None:
    procedure_text = _raw_text(_PROCEDURE_PATH)
    assert restates_point_cut_list(procedure_text)
    # Exactly one restating block: only the notes section (not a step
    # description) should trip the detector.
    step_hits = sum(1 for desc in _procedure_step_descriptions() if restates_point_cut_list(desc))
    notes_text = str(_procedure().get("notes", ""))
    notes_hits = 1 if restates_point_cut_list(notes_text) else 0
    assert step_hits == 0, "the point-cut list must live only in notes, not restated in a step description"
    assert notes_hits == 1, "the procedure's notes must own the single point-cut list"


def test_procedure_pre_spec_names_the_specify_command() -> None:
    text = _raw_text(_PROCEDURE_PATH)
    assert re.search(r"pre-spec[^\n]*before\s*/spec-kitty\.specify", text), "the procedure's point-cut list must label pre-spec as 'before /spec-kitty.specify'"


def test_skill_does_not_restate_the_point_cut_list() -> None:
    assert not restates_point_cut_list(_raw_text(_SKILL_PATH))


def test_directive_052_does_not_restate_the_point_cut_list() -> None:
    directive = _load_yaml(_DIRECTIVE_052_PATH)
    procedures_text = "\n".join(str(p) for p in directive.get("procedures", []))
    assert not restates_point_cut_list(procedures_text)


# ---------------------------------------------------------------------------
# FR-003 -- no headcount in the procedure or the skill
# ---------------------------------------------------------------------------


def test_headcount_detector_positive_control() -> None:
    assert has_headcount_language("Invariants: bounded (3-4)")
    assert has_headcount_language("3-4 distinct lenses")
    assert has_headcount_language("three to four distinct lenses"), "word-number range must be flagged, not just the digit-range form"


def test_procedure_anti_patterns_have_no_headcount() -> None:
    for description in _procedure_anti_pattern_descriptions():
        assert not has_headcount_language(description), description


def test_procedure_steps_have_no_headcount() -> None:
    for description in _procedure_step_descriptions():
        assert not has_headcount_language(description), description


def test_procedure_notes_before_casting_anchor_have_no_headcount() -> None:
    notes_text = str(_procedure().get("notes", ""))
    anchor_index = notes_text.find(_CASTING_ANCHOR)
    before_casting = notes_text if anchor_index == -1 else notes_text[:anchor_index]
    assert not has_headcount_language(before_casting), before_casting


def test_skill_has_no_headcount() -> None:
    assert not has_headcount_language(_raw_text(_SKILL_PATH))


# ---------------------------------------------------------------------------
# FR-005 -- model tier delegated to model-task-routing
# ---------------------------------------------------------------------------


def test_procedure_delegates_model_tier_to_model_task_routing() -> None:
    text = _raw_text(_PROCEDURE_PATH)
    assert "model-task-routing" in text
    assert "stronger model tier" not in text
    assert "lighter tier" not in text


# ---------------------------------------------------------------------------
# FR-007 -- folded styleguide content
# ---------------------------------------------------------------------------


def test_procedure_folds_the_styleguide_unique_content() -> None:
    notes_text = str(_procedure().get("notes", ""))
    assert "highest-value" in notes_text
    assert "post-tasks" in notes_text
    assert re.search(r"post-tasks[^.\n]{0,120}highest-value|highest-value[^.\n]{0,120}post-tasks", notes_text), (
        "'highest-value' must be stated in connection with post-tasks"
    )
    assert "timebox" in notes_text

    anti_pattern_names = {ap.get("name", "") for ap in _procedure().get("anti_patterns", [])}
    assert "Hard-wiring the squad as a gate" in anti_pattern_names, "the gate-hardwiring bad/good example must be folded into this anti-pattern"


# ---------------------------------------------------------------------------
# FR-013 -- squad-delegate cross-reference
# ---------------------------------------------------------------------------


def test_procedure_dispatch_step_names_squad_delegate_mode() -> None:
    steps = _procedure().get("steps", [])
    dispatch_steps = [s for s in steps if "dispatch" in s.get("title", "").lower()]
    assert dispatch_steps, "expected a dispatch step in the procedure"
    assert any("squad-delegate" in s.get("description", "") for s in dispatch_steps)


@pytest.mark.parametrize("profile_id", ["debugger-debbie", "paula-patterns"])
def test_fixed_lens_profiles_declare_squad_delegate_mode(profile_id: str) -> None:
    repo = _profile_repo()
    profile = repo.get(profile_id)
    assert profile is not None, f"{profile_id} must be loadable"
    mode_names = {m.mode for m in profile.mode_defaults}
    assert "squad-delegate" in mode_names, f"{profile_id} must declare a squad-delegate mode"


# ---------------------------------------------------------------------------
# FR-008 / FR-012 -- reference ratchets
# ---------------------------------------------------------------------------


def test_directive_040_names_the_procedure() -> None:
    directive = _load_yaml(_DIRECTIVE_040_PATH)
    procedures_text = "\n".join(str(p) for p in directive.get("procedures", []))
    assert "adversarial-squad-deployment" in procedures_text


def test_five_paradigm_tactic_names_the_procedure() -> None:
    assert "adversarial-squad-deployment" in _raw_text(_FIVE_PARADIGM_PATH)


def test_paula_scout_tactic_names_the_procedure() -> None:
    assert "adversarial-squad-deployment" in _raw_text(_PAULA_TACTIC_PATH)


def test_directive_052_names_the_procedure() -> None:
    directive = _load_yaml(_DIRECTIVE_052_PATH)
    procedures_text = "\n".join(str(p) for p in directive.get("procedures", []))
    assert "adversarial-squad-deployment" in procedures_text


def test_directive_043_references_the_procedure() -> None:
    directive = _load_yaml(_DIRECTIVE_043_PATH)
    references = directive.get("references", [])
    assert {"type": "procedure", "id": "adversarial-squad-deployment"} in [{"type": r.get("type"), "id": r.get("id")} for r in references]


def test_brownfield_no_longer_references_the_styleguide() -> None:
    brownfield = _load_yaml(_BROWNFIELD_PATH)
    references = brownfield.get("references", [])
    assert not any(r.get("type") == "styleguide" and r.get("id") == "adversarial-squad-cadence" for r in references)


def test_styleguide_file_is_absent() -> None:
    assert not _STYLEGUIDE_PATH.exists(), "adversarial-squad-cadence.styleguide.yaml must be deleted"


def test_acceptance_criteria_non_vacuity_comment_no_longer_names_the_styleguide() -> None:
    text = _raw_text(_ACCEPTANCE_NON_VACUITY_PATH)
    assert "adversarial-squad-cadence" not in text


def test_mission_tracer_files_yaml_reference_to_styleguide_removed() -> None:
    tracer = _load_yaml(_TRACER_PROCEDURE_PATH)
    references = tracer.get("references", [])
    assert not any(r.get("type") == "styleguide" and r.get("id") == "adversarial-squad-cadence" for r in references)


# ---------------------------------------------------------------------------
# Procedure references drop five-paradigm-parallel-debugging
# ---------------------------------------------------------------------------


def test_procedure_references_drop_five_paradigm_entry() -> None:
    references = _procedure().get("references", [])
    assert not any(r.get("type") == "tactic" and r.get("id") == "five-paradigm-parallel-debugging" for r in references)


# ---------------------------------------------------------------------------
# FR-027 -- findings-disposition contract
# ---------------------------------------------------------------------------


def test_procedure_defines_the_findings_disposition_contract() -> None:
    notes_text = str(_procedure().get("notes", ""))
    assert "Findings disposition contract:" in notes_text
    for label in ("accepted", "changed", "deferred_with_rationale"):
        assert label in notes_text, f"disposition contract must name '{label}'"
    assert "evidence" in notes_text.lower(), "each disposition must require an evidence location"


# ---------------------------------------------------------------------------
# FR-004 -- casting table, parsed as in T018
# ---------------------------------------------------------------------------


def test_casting_table_labels_and_ids_resolve() -> None:
    text = _raw_text(_PROCEDURE_PATH)
    rows = _parse_casting_block(text)
    assert rows, "expected at least one casting row"

    repo = _profile_repo()
    escalation_ids: set[str] = set()
    for label, ids in rows:
        assert label in _VALID_CASTING_LABELS, f"unexpected casting label: {label}"
        assert ids, f"casting row for '{label}' has no ids"
        for profile_id in ids:
            profile = repo.get(profile_id)
            assert profile is not None, f"casting id '{profile_id}' must resolve via AgentProfileRepository"
        if label == "escalation":
            escalation_ids.update(ids)
        else:
            for profile_id in ids:
                profile = repo.get(profile_id)
                assert profile is not None
                assert "first-occurrence" not in profile.specialization.avoidance_boundary, (
                    f"'{profile_id}' avoids first-occurrence work and must only be cast on escalation, not '{label}'"
                )

    first_occurrence_avoiders = {
        profile_id
        for profile_id in escalation_ids
        if (profile := repo.get(profile_id)) is not None and "first-occurrence" in profile.specialization.avoidance_boundary
    }
    assert {"debugger-debbie", "paula-patterns"} <= first_occurrence_avoiders


def test_casting_table_negative_control_rejects_researcher_ryan() -> None:
    """A casting line naming researcher-ryan parses but must not resolve (FR-004).

    Feeds a mutated casting line through the same ``_parse_casting_block``
    parser the real assertions use, then through ``AgentProfileRepository``,
    so this control exercises "a line casting researcher-ryan fails" end to
    end rather than only checking the resolver in isolation.
    """
    mutated_text = f"{_CASTING_ANCHOR}\n- escalation: `researcher-ryan` — mutated casting row\n"
    rows = _parse_casting_block(mutated_text)
    assert rows, "expected the mutated casting line to parse"
    label, ids = rows[0]
    assert label == "escalation"
    assert "researcher-ryan" in ids

    repo = _profile_repo()
    for profile_id in ids:
        assert repo.get(profile_id) is None, f"casting id '{profile_id}' must not resolve via AgentProfileRepository"


def test_casting_table_ids_are_in_default_pack_activation() -> None:
    from charter.activation.default_pack import load_default_pack_activation_ids

    activated = frozenset(load_default_pack_activation_ids().get("activated_agent_profiles", []))
    text = _raw_text(_PROCEDURE_PATH)
    rows = _parse_casting_block(text)
    all_ids = {profile_id for _, ids in rows for profile_id in ids}
    missing = all_ids - activated
    assert not missing, f"casting ids missing from activated_agent_profiles: {sorted(missing)}"
    assert {"doctrine-daphne", "randy-reducer"} <= all_ids
