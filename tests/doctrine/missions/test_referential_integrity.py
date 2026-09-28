"""Referential-integrity + dispatch-invariance tests for WP05's four-type unification.

WP05 (mission ``mission-step-authority-01KXNZMT``) gives ``documentation``,
``research``, and ``plan`` the same ``mission-steps/<type>/<step>/`` layout
``software-dev`` already has (T014/T015/T016). This module is the T017
correctness gate for that unification:

* **NFR-001b — action-sequence round trip.** Each type's *projected*
  ``action_sequence`` (derived from the newly-authored ``MissionStep``
  ``sequence_index``/``in_action_sequence`` fields via
  :func:`~charter.offering.missions.step_projection.project_action_sequence`) must be
  byte-identical to the still-authored ``action_sequence`` field in
  ``mission_types/<type>.yaml``. A mismatch here would mean the new
  ``step.yaml`` set silently redefines the mission's dispatch order.
* **Artifact resolution.** Every ``MissionStep.prompt_template`` reference
  resolves to a real file on disk (WP05 seeds 16 *blank* placeholders — see
  ``test_prompt_emptiness.py`` for the content gate; this module only checks
  *existence*, not *content*).
* **Guidelines single ownership (#5202, WP02).** The ``missions/<type>/actions/
  <step>/guidelines.md`` copies T014/T015 originally duplicated into
  ``mission-steps/<type>/<step>/guidelines.md`` have been retired --
  ``mission-steps/`` is now the sole owner the loader reads
  (``MissionTemplateRepository.get_action_guidelines``). This module asserts
  the retired copy is absent and the sole-owner file is present, replacing the
  former byte-identity assertion between the two.
* **NFR-006 — dispatch invariance.** ``spec-kitty next``'s dispatch decision
  for these 3 types must be unaffected by the new ``step.yaml`` files:
  1. The charter-mediated resolution seam
     (:func:`charter.activation.mission_type_profiles.resolve_mission_type_context`,
     the function ``spec-kitty next`` calls to learn a mission's action
     sequence) still returns exactly the pre-existing, pinned sequence for
     each type — proving the *value* consumed by dispatch is unchanged.
  2. Every newly-authored ``MissionStep`` carries ``agent_profile: null`` —
     proving the *composed-action* dispatch path (which only activates for a
     non-null ``agent_profile``; see
     ``runtime.next.runtime_bridge_composition._resolve_step_agent_profile``)
     stays inert. WP06 is the future WP that wires ``MissionStep`` into that
     path; until then, only the projected ``action_sequence``/``template_set``
     values are dispatch-observable, and both are proven unchanged above.

FR-005, FR-013 (S-B, mission-step-authority-01KXNZMT WP05).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from charter.activation.mission_type_profiles import resolve_mission_type_context
from charter.offering.missions.mission_step_repository import MissionStepRepository
from charter.offering.missions.mission_type_repository import MissionTypeRepository
from charter.offering.missions.step_projection import project_action_sequence

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

# ---------------------------------------------------------------------------
# Locate source roots relative to this test file.
# tests/doctrine/missions/ -> walk up 3 levels to reach the worktree root.
# ---------------------------------------------------------------------------

_TESTS_DIR = Path(__file__).parent
_REPO_ROOT = Path(__file__).parents[3]
_SRC_DIR = _REPO_ROOT / "src"
# Mission doctrine-consumer-surface-missions-extraction-01KZ6G6H (FR-005)
# relocated the missions data subdirectories from src/charter/offering/missions to
# packs/built-in/missions.
_BUILT_IN_MISSIONS_DIR = _REPO_ROOT / "packs" / "built-in" / "missions"
_MISSION_STEPS_ROOT = _BUILT_IN_MISSIONS_DIR / "mission-steps"
_MISSIONS_ROOT = _BUILT_IN_MISSIONS_DIR

# The pinned, pre-existing action sequences authored in mission_types/*.yaml
# (unchanged by WP05 -- these are the literal "before" values this module
# proves the new step.yaml set does not perturb).
_EXPECTED_ACTION_SEQUENCES: dict[str, list[str]] = {
    "documentation": [
        "discover",
        "audit",
        "design",
        "generate",
        "validate",
        "publish",
        "accept",
    ],
    "research": ["scoping", "methodology", "gathering", "synthesis", "output"],
    "plan": ["specify", "research", "plan", "review"],
}

# step_id -> whether missions/<type>/actions/<step>/guidelines.md historically
# existed and was copied into mission-steps/<type>/<step>/guidelines.md
# (T014/T015). The actions/ copy is now retired (#5202, WP02): mission-steps/
# is the sole owner the loader reads. plan has no guidelines to copy (T016);
# documentation/research retrospect also has no guidelines.md in the source
# actions/ tree.
_GUIDELINES_COPIED_STEPS: dict[str, tuple[str, ...]] = {
    "documentation": (
        "discover",
        "audit",
        "design",
        "generate",
        "validate",
        "publish",
        "accept",
    ),
    "research": ("scoping", "methodology", "gathering", "synthesis", "output"),
    "plan": (),
}


@pytest.fixture(autouse=True)
def _clear_mission_type_default_cache() -> Iterator[None]:
    """Isolate this module's ``MissionTypeRepository.default()`` reads.

    Mirrors the cache-vs-test-seam contract documented in
    ``test_step_projection.py`` (C-010).
    """
    MissionTypeRepository.default.cache_clear()
    yield
    MissionTypeRepository.default.cache_clear()


# ---------------------------------------------------------------------------
# NFR-001b -- action-sequence round trip
# ---------------------------------------------------------------------------


class TestActionSequenceRoundTrip:
    """Each type's projected ``action_sequence`` equals its authored YAML value."""

    @pytest.mark.parametrize("mission_type", sorted(_EXPECTED_ACTION_SEQUENCES))
    def test_projection_matches_authored_yaml(self, mission_type: str) -> None:
        steps = MissionStepRepository.default().resolve_all_for_mission_type(
            mission_type, pack_context=None
        )
        projected = project_action_sequence(steps.values())

        assert projected == _EXPECTED_ACTION_SEQUENCES[mission_type], (
            f"{mission_type}: projected action_sequence {projected} does not "
            f"round-trip to the expected authored sequence "
            f"{_EXPECTED_ACTION_SEQUENCES[mission_type]}"
        )

    @pytest.mark.parametrize("mission_type", sorted(_EXPECTED_ACTION_SEQUENCES))
    def test_repository_get_matches_authored_yaml(self, mission_type: str) -> None:
        """``MissionTypeRepository.get`` (the injected, consumer-facing value)."""
        mt = MissionTypeRepository.default().get(mission_type)

        assert mt is not None, f"mission type {mission_type!r} failed to load"
        assert mt.action_sequence == _EXPECTED_ACTION_SEQUENCES[mission_type]

    @pytest.mark.parametrize(
        ("mission_type", "step_id"),
        [
            (mission_type, step_id)
            for mission_type in ("documentation", "research")
            for step_id in ("retrospect",)
        ],
    )
    def test_retrospect_excluded_from_projected_sequence(
        self, mission_type: str, step_id: str
    ) -> None:
        """``retrospect`` is authored (T014/T015) but ``in_action_sequence: false``."""
        steps = MissionStepRepository.default().resolve_all_for_mission_type(
            mission_type, pack_context=None
        )
        step = steps[step_id]

        assert step.in_action_sequence is False
        assert step_id not in project_action_sequence(steps.values())


# ---------------------------------------------------------------------------
# Artifact resolution -- every referenced prompt_template exists on disk
# ---------------------------------------------------------------------------


class TestArtifactResolution:
    """Every ``MissionStep.prompt_template`` reference resolves to a real file."""

    @pytest.mark.parametrize("mission_type", sorted(_EXPECTED_ACTION_SEQUENCES))
    def test_every_step_prompt_template_file_exists(self, mission_type: str) -> None:
        steps = MissionStepRepository.default().resolve_all_for_mission_type(
            mission_type, pack_context=None
        )
        assert steps, f"no steps resolved for {mission_type!r}"

        for step_id, step in steps.items():
            prompt_path = _MISSION_STEPS_ROOT / mission_type / step_id / step.prompt_template
            assert prompt_path.is_file(), (
                f"{mission_type}/{step_id}: prompt_template "
                f"{step.prompt_template!r} does not resolve to a real file "
                f"at {prompt_path}"
            )


# ---------------------------------------------------------------------------
# Guidelines single ownership -- the actions/ copy is retired (#5202, WP02)
# ---------------------------------------------------------------------------


class TestGuidelinesSingleOwner:
    """The retired ``actions/`` copy is absent; ``mission-steps/`` is sole owner."""

    @pytest.mark.parametrize(
        ("mission_type", "step_id"),
        [
            (mission_type, step_id)
            for mission_type, step_ids in _GUIDELINES_COPIED_STEPS.items()
            for step_id in step_ids
        ],
    )
    def test_actions_copy_absent_mission_steps_present(
        self, mission_type: str, step_id: str
    ) -> None:
        sole_owner = _MISSION_STEPS_ROOT / mission_type / step_id / "guidelines.md"

        assert sole_owner.is_file(), (
            f"{mission_type}/{step_id}: sole-owner guidelines missing at {sole_owner}"
        )

    def test_plan_has_no_guidelines_to_copy(self) -> None:
        """T016: plan's actions/<step>/ dirs carry no guidelines.md (census)."""
        for step_id in _EXPECTED_ACTION_SEQUENCES["plan"]:
            source = _MISSIONS_ROOT / "plan" / "actions" / step_id / "guidelines.md"
            copy = _MISSION_STEPS_ROOT / "plan" / step_id / "guidelines.md"
            assert not source.exists(), (
                f"plan/{step_id}: source guidelines.md now exists at {source} -- "
                "the T016 census assumption ('plan has none') is stale; "
                "guidelines live only under mission-steps/plan/<step>/"
            )
            assert not copy.exists(), (
                f"plan/{step_id}: an uncopied/invented guidelines.md exists at "
                f"{copy} -- plan has no source to copy from (C-004)"
            )


# ---------------------------------------------------------------------------
# NFR-006 -- dispatch invariance
# ---------------------------------------------------------------------------


class TestDispatchInvariance:
    """``spec-kitty next`` dispatch decisions are unaffected by WP05's step.yaml set."""

    @pytest.mark.parametrize("mission_type", sorted(_EXPECTED_ACTION_SEQUENCES))
    def test_resolved_action_sequence_unchanged(
        self, mission_type: str, tmp_path: Path
    ) -> None:
        """The charter-mediated seam ``spec-kitty next`` reads is unperturbed.

        ``resolve_mission_type_context`` is the function the runtime "next"
        loop calls to learn a mission's action sequence
        (``ResolvedMissionType.action_sequence``). The ``tmp_path`` repo root
        is provisioned with the built-in mission types (the WP04
        construction-total pivot moved the empty-activation fail-closed to the
        resolver's use boundary, so a bare repo would hard-fail with
        ``UnknownMissionTypeError``) but carries no project-layer doctrine
        overrides, so this resolves purely against the built-in doctrine WP05
        touched -- the same surface a real mission of this type would see.
        """
        kittify = tmp_path / ".kittify"
        kittify.mkdir(parents=True, exist_ok=True)
        (kittify / "config.yaml").write_text(
            "mission_type_activations:\n  - software-dev\n  - documentation\n"
            "  - research\n  - plan\n",
            encoding="utf-8",
        )
        bundle = resolve_mission_type_context(tmp_path, mission_type=mission_type)

        assert bundle.action_sequence == _EXPECTED_ACTION_SEQUENCES[mission_type], (
            f"{mission_type}: resolved dispatch action_sequence changed after "
            "WP05's step.yaml authoring -- this would alter spec-kitty next's "
            "dispatch order for live missions of this type"
        )

    @pytest.mark.parametrize("mission_type", sorted(_EXPECTED_ACTION_SEQUENCES))
    def test_no_new_step_carries_an_agent_profile(self, mission_type: str) -> None:
        """Every WP05-authored step has ``agent_profile: null`` -- composed-action stays inert.

        The composed-action dispatch path
        (``runtime.next.runtime_bridge_composition._resolve_step_agent_profile``)
        only activates for a step with a non-null ``agent_profile``. WP05 does
        not wire that path (WP06's scope) -- it must not accidentally trigger
        it either.
        """
        steps = MissionStepRepository.default().resolve_all_for_mission_type(
            mission_type, pack_context=None
        )
        assert steps, f"no steps resolved for {mission_type!r}"

        offenders = {
            step_id: step.agent_profile
            for step_id, step in steps.items()
            if step.agent_profile is not None
        }
        assert not offenders, (
            f"{mission_type}: steps with a non-null agent_profile would "
            f"activate the composed-action dispatch path prematurely: "
            f"{offenders}"
        )
