"""T024/T025 -- emptiness-scaffold retirement + positive prompt-floor gate.

``mission-step-authority-01KXNZMT`` WP05 seeded 16 blank placeholder
``prompt.md`` files across ``documentation`` (7), ``research`` (5), and
``plan`` (4) -- the same ``mission-steps/<type>/<step>/`` layout
``software-dev`` already had. Each blank was tracked as a named,
individually-visible ``xfail`` so the gate stayed green while content
authoring (S-C's Concern B: WP02/documentation, WP03/research, WP04/plan)
was still in flight.

**mission-step-creatability-01KXQA6R WP05 retires that scaffold.** All 16
prompts are now authored (WP02/WP03/WP04 landed and were approved before
this WP started) -- ``_SEEDED_BLANK_STEPS`` is empty, so the ``xfail``/
``zero-bytes``/``_currently_blank`` parametrized tests that exercised the
seeded-blank census are vacuous and have been removed. In their place this
module asserts, **positively**, that every dispatch-relevant sequence-step
``prompt.md`` across all four built-in mission types clears a structural
floor.

IMPORTANT -- this machine floor is necessary, not sufficient (NFR-004):
clearing every check below (non-empty, no dummy marker, references
``$ARGUMENTS``, has at least one ``## `` heading, clears a minimum length)
proves a prompt is not a *stub*. It does NOT prove the prompt's content is
substantively correct, complete, or genuinely walks an agent through that
step's domain-specific process -- a filler paragraph padded past the length
floor with a heading and ``$ARGUMENTS`` sprinkled in would still pass this
test. **Genuine per-type substance is a human reviewer gate**, owned by the
content-authoring work packages themselves (WP02/documentation, WP03/
research, WP04/plan) at their own review checkpoints -- this test is the
machine half of that two-part guard, not a replacement for the human half.

``retrospect`` (documentation, research) stays out of scope here, same as
the retired scaffold: it is authored with ``in_action_sequence: false``
(never a member of the dispatched action sequence, NFR-006) and its
prompt is validated only for model presence (``MissionStep.prompt_template``
is required), never for content quality.

FR-005, FR-013, NFR-004 (S-B mission-step-authority-01KXNZMT WP05 origin;
S-C mission-step-creatability-01KXQA6R WP05 retirement, T024/T025).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.missions.mission_step_repository import MissionStepRepository
from charter.offering.missions.mission_type_repository import MissionTypeRepository
from charter.offering.missions.step_projection import project_action_sequence

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

_REPO_ROOT = Path(__file__).parents[3]
# Mission doctrine-consumer-surface-missions-extraction-01KZ6G6H (FR-005)
# relocated mission-steps/ from src/charter/offering/missions/mission-steps to
# packs/built-in/missions/mission-steps.
_MISSION_STEPS_ROOT = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps"

# A prompt counts as "empty/dummy" if it has no meaningful content: zero
# bytes, or nothing but whitespace / a placeholder TODO marker.
_DUMMY_MARKERS = ("TODO", "PLACEHOLDER", "FIXME")

#: Minimum stripped-character length a genuine prompt must clear. This is a
#: partial defence against filler-stub prompts, not a content-quality proof
#: (see the module docstring's NFR-004 disclaimer): a real authored prompt
#: clears this floor several times over (the smallest of the 21 dispatch-
#: relevant prompts today is ~3.1K chars); a one-liner or a bare heading
#: does not.
_MIN_PROMPT_LENGTH = 800


def _prompt_path(mission_type: str, step_id: str) -> Path:
    return _MISSION_STEPS_ROOT / mission_type / step_id / "prompt.md"


def _every_dispatch_relevant_sequence_step() -> list[tuple[str, str]]:
    """Every ``(mission_type, step_id)`` pair in a dispatched action sequence.

    Derived from the same step-authority projection the runtime seam
    consumes (:func:`~charter.offering.missions.step_projection.project_action_sequence`)
    rather than a hand-maintained literal list -- so this census can never
    silently drift from the authority it is meant to police (C-003, "one
    ordering authority"). Steps with ``in_action_sequence: false`` (e.g.
    ``retrospect``) are excluded by the projection itself.
    """
    pairs: list[tuple[str, str]] = []
    for mission_type_id in sorted(MissionTypeRepository.default().ids()):
        steps = list(
            MissionStepRepository.default()
            .resolve_all_for_mission_type(mission_type_id, pack_context=None)
            .values()
        )
        for step_id in project_action_sequence(steps):
            pairs.append((mission_type_id, step_id))
    return pairs


_SEQUENCE_STEPS: list[tuple[str, str]] = _every_dispatch_relevant_sequence_step()


# ---------------------------------------------------------------------------
# Positive structural floor -- every dispatch-relevant prompt, every type.
# ---------------------------------------------------------------------------


class TestEverySequenceStepPromptClearsTheStructuralFloor:
    """T025: the positive replacement for the retired seeded-blank scaffold.

    Each dispatch-relevant sequence step's ``prompt.md``, across all four
    built-in mission types, must be (i) non-empty, (ii) free of dummy/
    placeholder markers, (iii) reference ``$ARGUMENTS``, (iv) contain at
    least one ``## `` heading, and (v) clear a minimum length. See the
    module docstring for the NFR-004 necessary-not-sufficient disclaimer.
    """

    @pytest.mark.parametrize(
        ("mission_type", "step_id"),
        _SEQUENCE_STEPS,
        ids=[f"{mt}/{sid}" for mt, sid in _SEQUENCE_STEPS],
    )
    def test_prompt_clears_structural_floor(
        self, mission_type: str, step_id: str
    ) -> None:
        prompt_path = _prompt_path(mission_type, step_id)
        assert prompt_path.is_file(), f"expected prompt.md at {prompt_path}"

        text = prompt_path.read_text(encoding="utf-8")
        stripped = text.strip()

        assert stripped, (
            f"{mission_type}/{step_id}: prompt.md at {prompt_path} is empty"
        )
        for marker in _DUMMY_MARKERS:
            assert marker not in text, (
                f"{mission_type}/{step_id}: prompt.md at {prompt_path} "
                f"contains dummy marker {marker!r}"
            )
        assert "$ARGUMENTS" in text, (
            f"{mission_type}/{step_id}: prompt.md at {prompt_path} does not "
            "reference $ARGUMENTS"
        )
        assert "## " in text, (
            f"{mission_type}/{step_id}: prompt.md at {prompt_path} has no "
            "`## ` heading"
        )
        assert len(stripped) >= _MIN_PROMPT_LENGTH, (
            f"{mission_type}/{step_id}: prompt.md at {prompt_path} is only "
            f"{len(stripped)} chars (floor: {_MIN_PROMPT_LENGTH})"
        )


# ---------------------------------------------------------------------------
# Anti-vacuity guard -- prove the census above is actually exercising all
# four built-in types (not silently collapsing to zero parametrizations).
# ---------------------------------------------------------------------------


class TestSequenceStepCensusIsNotVacuous:
    """A parametrized suite over an empty list passes trivially and proves
    nothing. This guards the census derivation itself so a future regression
    in ``project_action_sequence`` (or a mission-steps tree that goes
    missing) surfaces here instead of the suite above silently collecting
    zero tests.
    """

    def test_census_covers_all_four_built_in_types(self) -> None:
        covered_types = {mission_type for mission_type, _ in _SEQUENCE_STEPS}
        assert covered_types == {"documentation", "research", "plan", "software-dev"}

    def test_census_is_non_empty(self) -> None:
        assert len(_SEQUENCE_STEPS) > 0
