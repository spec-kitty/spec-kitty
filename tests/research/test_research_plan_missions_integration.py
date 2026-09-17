"""Integration tests for the shipped research and plan mission artifacts.

Reconciled with the current canonical authorities (issue #4671). The retired
mission-DSL v1 sections (``mission``/``initial``/``states``/``transitions``/
``guards``/``inputs``/``outputs`` inside ``mission.yaml``) no longer exist in
any shipped artifact, so indexing them produced 32 baseline KeyError failures.
The lifecycle meaning those sections carried now lives in three authorities,
and these tests hold both missions' artifacts to each of them:

1. ``mission.yaml`` -- the v0 mission configuration (name/domain/workflow/
   artifacts/paths/agent_context/commands), which must stay backward
   compatible for every consumer that reads it.
2. ``mission-runtime.yaml`` -- the runtime planning template, which must load
   through the canonical ``MissionTemplate`` loader
   (``runtime.next._internal_runtime.schema.load_mission_template_file``)
   and carry a linear step chain (the old advance-transition chain, now
   expressed as ``depends_on``).
3. ``runtime_bridge_cores._GUARD_TABLES`` -- the executable guard authority.
   The gates the old DSL wrote as ``artifact_exists``/``event_count``/
   ``gate_passed`` conditions are now code in the per-family guard
   evaluators: artifact presence gates, the >=3 documented-sources evidence
   gate, and the publication-approval gate.

Nothing here restores retired YAML or drops a lifecycle constraint: every
gate the old file asserted is asserted against the authority that actually
enforces it today, and the closing class proves the replacement has teeth by
showing the new checks fail on genuinely broken variants of the *current*
schema (missing required step fields, a steps-free template, a broken
``depends_on`` chain, a step id the guard table does not know).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from runtime.next._internal_runtime.schema import (
    MissionTemplate,
    MissionTemplateHasNoStepsError,
    load_mission_template_file,
)
from runtime.next.runtime_bridge_cores import evaluate_guards
from runtime.next.runtime_bridge_io import ArtifactPresenceSnapshot

pytestmark = [pytest.mark.integration]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MISSIONS_DIR = Path(__file__).resolve().parents[2] / "src" / "specify_cli" / "missions"

_RESEARCH_ARTIFACTS = frozenset({"spec.md", "plan.md", "source-register.csv", "findings.md", "report.md", "research.md"})
_PLAN_ARTIFACTS = frozenset({"spec.md", "plan.md", "research.md"})

# Status facts that fully satisfy the research family's evidence gates
# (the >=3 documented-sources requirement and the publication-approval gate).
_SATISFIED_FACTS: Mapping[str, Any] = {
    "source_documented_count": 3,
    "publication_approved": True,
}


def _load_yaml(mission_name: str) -> dict[str, Any]:
    """Load a mission.yaml from the missions directory."""
    path = MISSIONS_DIR / mission_name / "mission.yaml"
    assert path.exists(), f"Missing mission.yaml at {path}"
    with open(path) as f:
        loaded = yaml.safe_load(f)
    assert isinstance(loaded, dict), f"{path} did not load as a mapping"
    return loaded


def _load_runtime(mission_name: str) -> MissionTemplate:
    """Load a mission-runtime.yaml through the canonical MissionTemplate loader."""
    path = MISSIONS_DIR / mission_name / "mission-runtime.yaml"
    assert path.exists(), f"Missing mission-runtime.yaml at {path}"
    return load_mission_template_file(path)


def _advance_chain(template: MissionTemplate) -> list[tuple[str, str]]:
    """Derive the (source, dest) lifecycle chain from ``depends_on``.

    The old DSL asserted a linear advance-transition chain per mission; the
    runtime template expresses the same constraint as each step depending on
    exactly its predecessor, with the first step depending on nothing.
    """
    steps = template.steps
    assert steps, f"Mission template {template.mission.key} has no steps"
    assert steps[0].depends_on == [], f"First step {steps[0].id} must not depend on other steps, got depends_on={steps[0].depends_on}"
    pairs: list[tuple[str, str]] = []
    for predecessor, current in zip(steps, steps[1:], strict=False):
        assert current.depends_on == [predecessor.id], f"Step {current.id} should advance from {predecessor.id}, got depends_on={current.depends_on}"
        pairs.append((predecessor.id, current.id))
    return pairs


def _guard_failures(
    mission_family: str,
    step_id: str,
    *,
    present_artifacts: frozenset[str] = frozenset(),
    status_facts: Mapping[str, Any] | None = None,
) -> list[str]:
    """Evaluate the executable guard authority for one (family, step) pair."""
    facts: dict[str, Any] = dict(_SATISFIED_FACTS)
    if status_facts is not None:
        facts.update(status_facts)
    snapshot = ArtifactPresenceSnapshot(
        present_artifacts=frozenset(present_artifacts),
        status_facts=facts,
        mission_family=mission_family,
        step_id=step_id,
    )
    return evaluate_guards(snapshot)


def _mutated_runtime(mission_name: str, mutate: Callable[[dict[str, Any]], None]) -> MissionTemplate:
    """Load a copy of a real mission-runtime.yaml after mutating its raw dict."""
    path = MISSIONS_DIR / mission_name / "mission-runtime.yaml"
    raw = yaml.safe_load(path.read_text())
    mutate(raw)
    return MissionTemplate.model_validate(raw)


# ---------------------------------------------------------------------------
# Research Mission: runtime template and v0 configuration
# ---------------------------------------------------------------------------


class TestResearchMissionArtifacts:
    """Research mission structure against the canonical runtime loader."""

    @pytest.fixture()
    def template(self) -> MissionTemplate:
        return _load_runtime("research")

    def test_mission_metadata(self, template: MissionTemplate) -> None:
        assert template.mission.key == "research"
        assert template.mission.name == "Deep Research Kitty"
        assert template.mission.version == "2.0.0"

    def test_initial_step_is_scoping(self, template: MissionTemplate) -> None:
        """The lifecycle starts at scoping (old ``initial: scoping``)."""
        assert template.steps[0].id == "scoping"

    def test_step_ids_in_lifecycle_order(self, template: MissionTemplate) -> None:
        """The lifecycle states, in order (the old ``states`` list; the old
        terminal ``done`` is now the acceptance status-commit step)."""
        assert [s.id for s in template.steps] == [
            "scoping",
            "methodology",
            "gathering",
            "synthesis",
            "output",
            "accept",
        ]

    def test_all_steps_have_title(self, template: MissionTemplate) -> None:
        """Every step carries a human-readable title (old display_name)."""
        for step in template.steps:
            assert step.title, f"Step {step.id} has an empty title"

    def test_step_chain_is_linear(self, template: MissionTemplate) -> None:
        """Steps advance linearly scoping -> methodology -> gathering ->
        synthesis -> output -> accept (old advance-transition chain)."""
        assert _advance_chain(template) == [
            ("scoping", "methodology"),
            ("methodology", "gathering"),
            ("gathering", "synthesis"),
            ("synthesis", "output"),
            ("output", "accept"),
        ]

    def test_output_step_dispatches_the_reviewer_profile(self, template: MissionTemplate) -> None:
        """The publication step is reviewed by a reviewer profile, not the
        research profile (the authorship separation the old guard set encoded
        by gating output on publication approval)."""
        by_id = {s.id: s for s in template.steps}
        assert by_id["output"].agent_profile == "reviewer-renata"
        assert by_id["scoping"].agent_profile == "researcher-robbie"

    def test_v0_configuration_fields_preserved(self) -> None:
        """v0 fields must still be present for backward compatibility."""
        config = _load_yaml("research")
        assert config["name"] == "Deep Research Kitty"
        assert config["domain"] == "research"
        assert "workflow" in config
        assert "phases" in config["workflow"]
        assert "artifacts" in config
        assert "paths" in config
        assert "agent_context" in config
        assert "commands" in config


# ---------------------------------------------------------------------------
# Research Mission: executable guard authority
# ---------------------------------------------------------------------------


class TestResearchGuardAuthority:
    """The research guard chain in ``runtime_bridge_cores._GUARD_TABLES``.

    These are the gates the old DSL expressed as transition ``conditions``:
    artifact presence (``artifact_exists``), the documented-sources evidence
    gate (``event_count('source_documented', 3)``), and the publication gate
    (``gate_passed('publication_approved')``).
    """

    def test_scoping_requires_spec_md(self) -> None:
        failures = _guard_failures("research", "scoping")
        assert failures == ["Required artifact missing: spec.md"]

    def test_methodology_requires_plan_md(self) -> None:
        failures = _guard_failures("research", "methodology")
        assert failures == ["Required artifact missing: plan.md"]

    def test_gathering_evidence_gate_requires_three_documented_sources(self) -> None:
        """gathering is gated on the source register AND >=3 documented
        sources (the old event_count evidence gate)."""
        with_register = _RESEARCH_ARTIFACTS
        for documented in (0, 2):
            failures = _guard_failures(
                "research",
                "gathering",
                present_artifacts=with_register,
                status_facts={"source_documented_count": documented},
            )
            assert failures == ["Insufficient sources documented (need >=3)"], f"count={documented} should fail the evidence gate"
        assert (
            _guard_failures(
                "research",
                "gathering",
                present_artifacts=with_register,
                status_facts={"source_documented_count": 3},
            )
            == []
        )

    def test_gathering_also_requires_the_source_register(self) -> None:
        failures = _guard_failures("research", "gathering", status_facts={"source_documented_count": 3})
        assert failures == ["Required artifact missing: source-register.csv"]

    def test_synthesis_requires_findings_md(self) -> None:
        failures = _guard_failures("research", "synthesis")
        assert failures == ["Required artifact missing: findings.md"]

    def test_output_requires_report_and_publication_approval(self) -> None:
        """output is gated on report.md AND the publication-approval gate
        (the old gate_passed condition), each failing independently."""
        unapproved = _guard_failures(
            "research",
            "output",
            present_artifacts=_RESEARCH_ARTIFACTS,
            status_facts={"publication_approved": False},
        )
        assert unapproved == ["Publication approval gate not passed"]
        without_report = _guard_failures("research", "output", status_facts={"publication_approved": False})
        assert without_report == [
            "Required artifact missing: report.md",
            "Publication approval gate not passed",
        ]
        assert _guard_failures("research", "output", present_artifacts=_RESEARCH_ARTIFACTS) == []

    def test_unknown_action_fails_closed(self) -> None:
        failures = _guard_failures("research", "not-a-real-research-action")
        assert failures == ["No guard registered for research action: not-a-real-research-action"]

    def test_every_non_terminal_step_is_a_registered_guard_action(self) -> None:
        """Artifact <-> guard-table consistency: every research runtime step
        other than the terminal ``accept`` status-commit step must be a
        registered action in the guard chain, so a renamed or newly added
        artifact step can never silently bypass its gate."""
        template = _load_runtime("research")
        for step in template.steps[:-1]:
            assert _guard_failures("research", step.id, present_artifacts=_RESEARCH_ARTIFACTS) == [], f"Step {step.id} has no guard registered for it"


# ---------------------------------------------------------------------------
# Plan Mission: runtime template and v0 configuration
# ---------------------------------------------------------------------------


class TestPlanMissionArtifacts:
    """Plan mission structure against the canonical runtime loader."""

    @pytest.fixture()
    def template(self) -> MissionTemplate:
        return _load_runtime("plan")

    def test_mission_metadata(self, template: MissionTemplate) -> None:
        assert template.mission.key == "plan"
        assert template.mission.name == "Planning Mission"
        assert template.mission.version == "1.0.0"

    def test_initial_step_is_specify(self, template: MissionTemplate) -> None:
        """The lifecycle starts at specify (the old ``initial: goals`` state
        is now the specify step)."""
        assert template.steps[0].id == "specify"

    def test_step_ids_in_lifecycle_order(self, template: MissionTemplate) -> None:
        assert [s.id for s in template.steps] == ["specify", "research", "plan", "review"]

    def test_all_steps_have_title(self, template: MissionTemplate) -> None:
        for step in template.steps:
            assert step.title, f"Step {step.id} has an empty title"

    def test_step_chain_is_linear(self, template: MissionTemplate) -> None:
        """Steps advance linearly specify -> research -> plan -> review (the
        old advance-transition chain; the old structure/draft/review/done
        states collapsed into plan/review)."""
        assert _advance_chain(template) == [
            ("specify", "research"),
            ("research", "plan"),
            ("plan", "review"),
        ]

    def test_mission_steps_mirror_matches_authoritative_steps(self, template: MissionTemplate) -> None:
        """The ``mission.steps`` mirror kept for legacy readers must agree
        with the authoritative top-level steps (FR-021's documented duality
        in the artifact header) -- the two shapes drifting apart is a real
        current-schema regression this file exists to catch."""
        raw = yaml.safe_load((MISSIONS_DIR / "plan" / "mission-runtime.yaml").read_text())
        mirror_ids = [s["id"] for s in raw["mission"]["steps"]]
        assert mirror_ids == [s.id for s in template.steps]
        mirror_deps = {s["id"]: s.get("depends_on", []) for s in raw["mission"]["steps"]}
        for step in template.steps:
            assert mirror_deps[step.id] == step.depends_on, f"mission.steps mirror for {step.id} disagrees with the authoritative top-level step"

    def test_v0_configuration_fields_present(self) -> None:
        """Plan mission includes v0 fields for backward compatibility."""
        config = _load_yaml("plan")
        assert config["name"] == "Planning Kitty"
        assert config["domain"] == "other"
        assert "workflow" in config
        assert "artifacts" in config
        assert "commands" in config


# ---------------------------------------------------------------------------
# Plan Mission: executable guard authority
# ---------------------------------------------------------------------------


class TestPlanGuardAuthority:
    """The plan guard chain in ``runtime_bridge_cores._GUARD_TABLES``
    (FR-002, issue #3386)."""

    def test_specify_requires_spec_md(self) -> None:
        failures = _guard_failures("plan", "specify")
        assert failures == ["Required artifact missing: spec.md"]

    def test_research_step_requires_research_md(self) -> None:
        failures = _guard_failures("plan", "research")
        assert failures == ["Required artifact missing: research.md"]

    def test_plan_step_requires_plan_md(self) -> None:
        failures = _guard_failures("plan", "plan")
        assert failures == ["Required artifact missing: plan.md"]

    def test_review_is_ungated_terminal_step(self) -> None:
        """review is the terminal status-commit step: the publish gate is
        sufficient and no artifact gate applies (superseding the old
        ``gate_passed('plan_approved')`` condition -- FR-002's design, not a
        dropped constraint)."""
        assert _guard_failures("plan", "review") == []

    def test_unknown_action_fails_closed(self) -> None:
        failures = _guard_failures("plan", "not-a-real-plan-action")
        assert failures == ["No guard registered for plan action: not-a-real-plan-action"]

    def test_every_step_is_a_registered_guard_action(self) -> None:
        """Artifact <-> guard-table consistency for all four plan steps."""
        template = _load_runtime("plan")
        for step in template.steps:
            assert _guard_failures("plan", step.id, present_artifacts=_PLAN_ARTIFACTS) == [], f"Step {step.id} has no guard registered for it"


# ---------------------------------------------------------------------------
# Directory structure tests
# ---------------------------------------------------------------------------


class TestPlanMissionDirectoryStructure:
    """Verify the plan mission directory has the expected layout."""

    def test_plan_directory_exists(self) -> None:
        assert (MISSIONS_DIR / "plan").is_dir()

    def test_plan_mission_yaml_exists(self) -> None:
        assert (MISSIONS_DIR / "plan" / "mission.yaml").is_file()

    def test_plan_templates_exists(self) -> None:
        assert (MISSIONS_DIR / "plan" / "templates").is_dir()


# ---------------------------------------------------------------------------
# Proof the replacement catches real current-schema regressions
# ---------------------------------------------------------------------------


class TestReplacementCatchesCurrentSchemaRegressions:
    """Issue #4671's acceptance requirement: prove the reconciled assertions
    are not vacuous by breaking variants of the *current* schema and showing
    the authority (or this file's lifecycle checks) rejects each break."""

    def test_loader_rejects_a_step_missing_its_title(self) -> None:
        """A current-schema regression: dropping a required step field."""

        def mutate(raw: dict[str, Any]) -> None:
            del raw["steps"][0]["title"]

        with pytest.raises(ValidationError):
            _mutated_runtime("research", mutate)

    def test_loader_rejects_a_template_with_no_steps(self, tmp_path: Path) -> None:
        """A current-schema regression: a steps-free template must fail
        closed through the canonical loader."""
        raw = yaml.safe_load((MISSIONS_DIR / "research" / "mission-runtime.yaml").read_text())
        raw["steps"] = []
        raw["audit_steps"] = []
        broken = tmp_path / "mission-runtime.yaml"
        broken.write_text(yaml.safe_dump(raw))
        with pytest.raises(MissionTemplateHasNoStepsError):
            load_mission_template_file(broken)

    def test_lifecycle_chain_check_rejects_a_broken_depends_on(self) -> None:
        """A current-schema regression the pydantic schema does NOT catch
        (it validates field types, not DAG integrity): a step that stops
        depending on its predecessor. The lifecycle-chain assertion is what
        holds this constraint, so it must fail on the break."""

        def mutate(raw: dict[str, Any]) -> None:
            raw["steps"][1]["depends_on"] = []

        broken = _mutated_runtime("research", mutate)
        with pytest.raises(AssertionError, match="should advance from"):
            _advance_chain(broken)

    def test_guard_vocabulary_check_rejects_a_renamed_step(self) -> None:
        """A current-schema regression: renaming an artifact step so the
        guard table no longer knows it (the guard would fail closed at
        runtime). The consistency check surfaces exactly this failure."""

        def mutate(raw: dict[str, Any]) -> None:
            for step in raw["steps"]:
                if step["id"] == "gathering":
                    step["id"] = "collection"

        broken = _mutated_runtime("research", mutate)
        assert "collection" in [s.id for s in broken.steps]
        assert _guard_failures("research", "collection", present_artifacts=_RESEARCH_ARTIFACTS) == ["No guard registered for research action: collection"]
