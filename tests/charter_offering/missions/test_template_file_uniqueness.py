"""T026 -- cross-type ``template_file`` uniqueness guard (NFR-006).

Each built-in mission type projects its own ``template_set`` mapping (see
:func:`~charter.offering.missions.step_projection.project_template_set`) --
``{artifact_key: template_file}`` -- from the ``template`` refs its own
sequence steps author. Nothing in the step-authority model itself prevents
two *different* mission types from independently authoring the SAME
``template_file`` name for their own ``spec``/``plan`` artifact, which would
let content silently collide or be contaminated across mission types (e.g. a
``plan`` mission type step accidentally resolving software-dev's
``spec-template.md`` because both authored the same filename).

This module asserts the guard positively: across all four built-in mission
types, every projected ``template_file`` is globally unique. This is what
lets each type author its own vocabulary-appropriate template filenames
(``documentation-spec-template.md``, ``research-plan-template.md``,
``plan-spec-skeleton.md``, ...) without a name from one type's authoring
silently shadowing or resolving into another's.

FR-008, NFR-006 (S-C mission-step-creatability-01KXQA6R WP05, T026).
"""

from __future__ import annotations

from collections import Counter

import pytest

from charter.offering.missions.mission_step_repository import MissionStepRepository
from charter.offering.missions.mission_type_repository import MissionTypeRepository
from charter.offering.missions.step_projection import project_template_set

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


def _all_template_files() -> list[tuple[str, str, str]]:
    """Every ``(mission_type, artifact_key, template_file)`` triple across
    all built-in mission types whose steps project a non-``None``
    ``template_set``."""
    triples: list[tuple[str, str, str]] = []
    for mission_type_id in sorted(MissionTypeRepository.default().ids()):
        steps = list(
            MissionStepRepository.default()
            .resolve_all_for_mission_type(mission_type_id, pack_context=None)
            .values()
        )
        template_set = project_template_set(steps)
        if template_set is None:
            continue
        for artifact_key, template_file in template_set.items():
            triples.append((mission_type_id, artifact_key, template_file))
    return triples


class TestTemplateFileIsGloballyUnique:
    """No two mission types may project the same ``template_file`` (NFR-006)."""

    def test_no_two_mission_types_project_the_same_template_file(self) -> None:
        triples = _all_template_files()
        template_files = [template_file for _, _, template_file in triples]

        counts = Counter(template_files)
        colliding = {name: count for name, count in counts.items() if count > 1}

        assert not colliding, (
            "template_file collision(s) across mission types (NFR-006): "
            f"{colliding} -- full projection: {triples}"
        )

    def test_all_template_files_are_distinct_via_set_cardinality(self) -> None:
        """Same invariant, expressed as the direct set-cardinality check the
        task description names -- kept alongside the collision-detail
        assertion above so a future failure names the offending type/file
        instead of only reporting a bare length mismatch."""
        triples = _all_template_files()
        template_files = [template_file for _, _, template_file in triples]
        assert len(template_files) == len(set(template_files))

    def test_projection_covers_the_four_built_in_types_authoring_templates(self) -> None:
        """Anti-vacuity guard: prove the census above is not silently empty --
        all four built-in mission types author template refs as of S-C's
        Concern B (WP01 software-dev cutover + WP02 documentation + WP03
        research + WP04 plan)."""
        triples = _all_template_files()
        covered_types = {mission_type for mission_type, _, _ in triples}
        assert covered_types == {"documentation", "research", "plan", "software-dev"}
