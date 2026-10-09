"""Byte-for-byte round-trip parity for software-dev's authored step data (T010, NFR-001a).

WP03 (mission ``mission-step-authority-01KXNZMT``) annotates the 12 built-in
software-dev ``step.yaml`` files with the relocated ``sequence_index`` /
``in_action_sequence`` / ``template`` fields (S-B). This module proves the
WP02 projection seam (:func:`~charter.offering.missions.step_projection.project_action_sequence`,
:func:`~charter.offering.missions.step_projection.project_template_set`) reproduces
today's pre-mission authored ``mission_types/software-dev.yaml`` values --
``action_sequence`` and ``template_set`` -- exactly, from the annotated
per-step data alone.

Two layers are asserted:

1. The pure projection over ``MissionStepRepository``-resolved software-dev
   steps (bypasses ``MissionTypeRepository`` caching/fallback entirely).
2. ``MissionTypeRepository.default()`` resolving software-dev's
   ``MissionType.action_sequence`` to the same value -- proving the
   projection is *live* (wins over the YAML fallback) for software-dev, per
   the transitional contract in
   ``mission_type_repository._inject_projected_fields``.

``template_set`` (S-C cutover, mission-step-creatability-01KXQA6R WP01,
C-005): the persisted ``MissionType.template_set`` field is retired, so
layer 2's equivalent no longer exists at the ``MissionType`` level -- the
pure-projection assertion in layer 1
(``TestSoftwareDevProjectionParity.test_template_set_matches_authored_value_byte_for_byte``)
remains the enduring parity guard; the consumer-facing (resolved-context)
equivalent lives in ``tests/charter/test_resolved_mission_type_context.py``.

FR-001, FR-014 (mission-step-authority-01KXNZMT WP03).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from charter.offering.missions.mission_step_repository import MissionStepRepository
from charter.offering.missions.mission_type_repository import MissionTypeRepository
from charter.offering.missions.models import MissionStep
from charter.offering.missions.step_projection import (
    project_action_sequence,
    project_template_set,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

#: The authored ``action_sequence`` from ``mission_types/software-dev.yaml``,
#: pre-mission -- the value this WP's per-step annotations must reproduce
#: byte-for-byte (NFR-001a).
_AUTHORED_ACTION_SEQUENCE = ["specify", "plan", "tasks", "implement", "review"]

#: The authored ``template_set`` from ``mission_types/software-dev.yaml``,
#: pre-mission -- same parity requirement.
_AUTHORED_TEMPLATE_SET = {"spec": "spec-template.md", "plan": "plan-template.md"}


@pytest.fixture(autouse=True)
def _clear_mission_type_default_cache() -> Iterator[None]:
    """Isolate ``MissionTypeRepository.default()`` memoization from other tests (C-010)."""
    MissionTypeRepository.default.cache_clear()
    yield
    MissionTypeRepository.default.cache_clear()


def _software_dev_steps() -> list[MissionStep]:
    """Resolve all 12 built-in software-dev steps (built-in layer only)."""
    return list(
        MissionStepRepository.default()
        .resolve_all_for_mission_type("software-dev", pack_context=None)
        .values()
    )


class TestSoftwareDevProjectionParity:
    """Direct projection over the annotated software-dev step.yaml set."""

    def test_action_sequence_matches_authored_value_byte_for_byte(self) -> None:
        steps = _software_dev_steps()

        assert project_action_sequence(steps) == _AUTHORED_ACTION_SEQUENCE

    def test_template_set_matches_authored_value_byte_for_byte(self) -> None:
        steps = _software_dev_steps()

        assert project_template_set(steps) == _AUTHORED_TEMPLATE_SET

    def test_exactly_five_steps_are_sequence_members(self) -> None:
        steps = _software_dev_steps()

        members = [step for step in steps if step.in_action_sequence]

        assert len(members) == len(_AUTHORED_ACTION_SEQUENCE)
        assert {step.id for step in members} == set(_AUTHORED_ACTION_SEQUENCE)

    def test_the_other_seven_steps_are_not_sequence_members(self) -> None:
        steps = _software_dev_steps()

        non_members = {step.id for step in steps if not step.in_action_sequence}

        assert non_members == {
            "accept",
            "analyze",
            "charter",
            "research",
            "tasks-outline",
            "tasks-finalize",
            "tasks-packages",
        }
        for step in steps:
            if not step.in_action_sequence:
                assert step.sequence_index is None

    def test_only_specify_and_plan_carry_a_template_ref(self) -> None:
        steps = _software_dev_steps()

        templated = {step.id for step in steps if step.template is not None}

        assert templated == {"specify", "plan"}


class TestMissionTypeRepositoryLiveProjection:
    """``MissionTypeRepository.default()`` now resolves software-dev via the live projection.

    Once WP03's per-step annotations exist, the WP02 injection seam
    (``_inject_projected_fields``) no longer falls back to the raw YAML --
    the projected, non-empty ``action_sequence``/``template_set`` wins. This
    proves that switch is live, not just that the pure functions agree with
    the YAML in isolation.
    """

    def test_default_resolves_software_dev_action_sequence(self) -> None:
        mission_type = MissionTypeRepository.default().get("software-dev")

        assert mission_type is not None
        assert mission_type.action_sequence == _AUTHORED_ACTION_SEQUENCE

    # ``test_default_resolves_software_dev_template_set`` retired (S-C cutover,
    # mission-step-creatability-01KXQA6R WP01, C-005): ``MissionType`` no
    # longer carries a ``template_set`` field to resolve -- the consumer-facing
    # equivalent is ``TestSoftwareDevProjectionParity.test_template_set_matches_authored_value_byte_for_byte``
    # above, plus the resolved-context coverage in
    # ``tests/charter/test_resolved_mission_type_context.py``.

    def test_default_get_constructs_and_projects_template_set(self) -> None:
        """T007 proof #2 (WP01, SC-002 acceptance scenario 1): the atomic
        cutover leaves ``MissionTypeRepository.default().get("software-dev")``
        constructing cleanly (no dangling ``.template_set`` model-field read
        under ``extra="forbid"`` -- that would raise ``AttributeError``), and
        the step authority still projects the full ``{spec, plan}`` mapping,
        sourced independently via ``MissionStepRepository``/``project_template_set``
        (the same seam ``_resolve_template_set_slot`` now uses)."""
        mission_type = MissionTypeRepository.default().get("software-dev")
        assert mission_type is not None

        steps = list(
            MissionStepRepository.default()
            .resolve_all_for_mission_type("software-dev", pack_context=None)
            .values()
        )
        assert project_template_set(steps) == _AUTHORED_TEMPLATE_SET
