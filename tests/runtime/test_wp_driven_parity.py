"""Charter- vs runtime-derived ``wp_driven``: advisory facet, authoritative DAG (#6330).

``ResolvedMissionType.wp_driven`` mirrors the type's curated ``action_sequence``;
the guard's ``wp_driven`` fact derives the same kernel rule
(``step_ids_declare_wp_iteration``) from the run's **frozen runtime DAG**. For the
four built-ins the two agree. For a custom type that curates its
``action_sequence`` away from its DAG they disagree — and the runtime side must
win, otherwise editing an advisory list would silently switch the guard off.

This module pins that split of authority at the fact the guard consumes, and pins
the DTO's own statement of it, so documentation and behaviour cannot drift apart.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.runtime._next_mission_scaffold import (
    CUSTOM_ANALYZE_FAMILY,
    scaffold_custom_analyze_mission,
)

pytestmark = [pytest.mark.git_repo]

#: A control DAG with no ``implement`` step at all (the negative control).
_NON_WP_STEPS = ("specify", "plan", "review")
#: The scaffolded DAG, whose ``implement`` step must stay authoritative.
_WP_STEPS = ("specify", "plan", "tasks", "analyze", "implement", "review")


def _curate_action_sequence_away_from_implement(repo_root: Path, family: str, steps: tuple[str, ...]) -> None:
    """Author project-layer step files that exclude ``implement`` from the sequence.

    ``action_sequence`` is *projected* from the step set, so curating it away
    means marking the step ``in_action_sequence: false`` while the runtime DAG
    (``mission-runtime.yaml``) still declares it — the exact divergence this
    mission pins. Every other step stays a sequence member, so the projection is
    non-empty and wins over any YAML-authored value.
    """
    from charter.offering.missions.mission_step_repository import MissionStepRepository
    from charter.offering.missions.mission_type_repository import resolve_layered_mission_types

    steps_dir = repo_root / ".kittify" / "overrides" / "mission-steps" / family
    for index, step in enumerate(steps):
        step_dir = steps_dir / step
        step_dir.mkdir(parents=True, exist_ok=True)
        lines = [f"id: {step}", f"display_name: {step}", "step_type: agent", 'prompt_template: ""']
        if step == "implement":
            lines.append("in_action_sequence: false")
        else:
            lines.extend([f"sequence_index: {index}", "in_action_sequence: true"])
        (step_dir / "step.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    MissionStepRepository.cache_clear()
    resolve_layered_mission_types.cache_clear()


def _bundle(repo_root: Path):
    from charter.activation.mission_type_profiles import resolve_mission_type_context
    from charter.offering.missions.mission_step_repository import MissionStepRepository
    from charter.offering.missions.mission_type_repository import resolve_layered_mission_types

    try:
        return resolve_mission_type_context(repo_root, mission_type=CUSTOM_ANALYZE_FAMILY)
    finally:
        MissionStepRepository.cache_clear()
        resolve_layered_mission_types.cache_clear()


def _guard_fact(repo_root: Path, slug: str) -> bool:
    """The ``wp_driven`` fact exactly as the guard consumes it (run in hand)."""
    from runtime.next.runtime_bridge import get_or_start_run
    from runtime.next.runtime_bridge_io import gather_artifact_presence

    run_ref = get_or_start_run(slug, repo_root, CUSTOM_ANALYZE_FAMILY)
    snapshot = gather_artifact_presence(
        repo_root / "kitty-specs" / slug,
        mission_family=CUSTOM_ANALYZE_FAMILY,
        step_id="implement",
        repo_root=repo_root,
        run_dir=Path(run_ref.run_dir),
    )
    return snapshot.wp_driven


def test_curated_away_action_sequence_does_not_switch_the_guard_off(tmp_path: Path) -> None:
    """The DTO follows the curated list (advisory); the fact follows the frozen DAG."""
    slug = scaffold_custom_analyze_mission(tmp_path)
    _curate_action_sequence_away_from_implement(tmp_path, CUSTOM_ANALYZE_FAMILY, _WP_STEPS)

    bundle = _bundle(tmp_path)
    assert "implement" not in bundle.action_sequence
    assert bundle.wp_driven is False, "the advisory facet mirrors the curated action_sequence"

    assert _guard_fact(tmp_path, slug) is True, "the frozen runtime DAG is authoritative"


def test_a_dag_without_implement_is_still_ungated(tmp_path: Path) -> None:
    """Same-fixture control: when the DAG itself has no ``implement``, nothing gates."""
    slug = scaffold_custom_analyze_mission(tmp_path, steps=_NON_WP_STEPS)
    _curate_action_sequence_away_from_implement(tmp_path, CUSTOM_ANALYZE_FAMILY, _NON_WP_STEPS)

    bundle = _bundle(tmp_path)
    assert bundle.wp_driven is False
    assert _guard_fact(tmp_path, slug) is False


def test_dto_states_that_the_facet_is_advisory_and_the_dag_authoritative() -> None:
    """The authority split is documented where a reader meets the facet."""
    from charter.activation.mission_type_profiles import ResolvedMissionType

    doc = (ResolvedMissionType.__doc__ or "").lower()
    assert "advisory" in doc
    assert "frozen" in doc and "dag" in doc, "the docstring must name the authoritative runtime input"
