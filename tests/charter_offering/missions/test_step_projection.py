"""Tests for the WP02 projection seam (``charter.offering.missions.step_projection``).

Covers (T008):

- ``project_action_sequence``: determinism regardless of input order,
  ``in_action_sequence: false`` exclusion, empty-projection tolerance
  (no raise -- the valid transitional state), and the re-asserted
  WP01->WP02 non-empty/unique invariant on a non-empty result.
- ``project_template_set``: artifact-key keying (NOT step id), template-less
  step dropping, ``None`` when empty.
- The ``MissionTypeRepository`` cached-accessor injection (T007):
  ``default()`` memoization + ``cache_clear()`` test seam, and the
  transitional fallback to the raw YAML-authored value when a mission
  type's builtin steps are not yet annotated with
  ``sequence_index``/``in_action_sequence``/``template`` (today's state for
  all four built-in types, pending WP03/WP05), plus the projection
  *winning* once steps carry that data.

FR-002, FR-003 (S-B, mission-step-authority-01KXNZMT WP02).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from charter.offering.missions.mission_step_repository import MissionStepRepository
from charter.offering.missions.mission_type_repository import MissionTypeRepository
from charter.offering.missions.models import MissionStep, MissionStepTemplateRef
from charter.offering.missions.step_projection import (
    iter_template_refs,
    project_action_sequence,
    project_template_set,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _step(
    step_id: str,
    *,
    in_action_sequence: bool = False,
    sequence_index: int | None = None,
    template: MissionStepTemplateRef | None = None,
) -> MissionStep:
    """Build a minimal, directly-constructed ``MissionStep`` for pure-function tests."""
    return MissionStep(
        id=step_id,
        display_name=step_id.title(),
        step_type="agent",
        prompt_template="prompt.md",
        in_action_sequence=in_action_sequence,
        sequence_index=sequence_index,
        template=template,
    )


def _write_builtin_step_yaml(
    builtin_root: Path, mission_type_id: str, step_id: str, body: str
) -> None:
    """Write *body* verbatim as ``step.yaml`` under the builtin-layout path."""
    step_dir = builtin_root / mission_type_id / step_id
    step_dir.mkdir(parents=True, exist_ok=True)
    (step_dir / "step.yaml").write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# project_action_sequence
# ---------------------------------------------------------------------------


class TestProjectActionSequence:
    def test_sorted_by_sequence_index(self) -> None:
        alpha = _step("alpha", in_action_sequence=True, sequence_index=2)
        beta = _step("beta", in_action_sequence=True, sequence_index=0)
        gamma = _step("gamma", in_action_sequence=True, sequence_index=1)

        result = project_action_sequence([alpha, beta, gamma])

        assert result == ["beta", "gamma", "alpha"]

    def test_deterministic_regardless_of_input_order(self) -> None:
        alpha = _step("alpha", in_action_sequence=True, sequence_index=2)
        beta = _step("beta", in_action_sequence=True, sequence_index=0)
        gamma = _step("gamma", in_action_sequence=True, sequence_index=1)

        forward = project_action_sequence([alpha, beta, gamma])
        shuffled = project_action_sequence([gamma, alpha, beta])
        reversed_input = project_action_sequence([gamma, beta, alpha])

        assert forward == shuffled == reversed_input

    def test_repeated_calls_are_byte_identical(self) -> None:
        steps = [
            _step("specify", in_action_sequence=True, sequence_index=0),
            _step("plan", in_action_sequence=True, sequence_index=1),
        ]

        first_projection = project_action_sequence(steps)
        second_projection = project_action_sequence(steps)
        assert first_projection == second_projection

    def test_excludes_steps_not_in_action_sequence(self) -> None:
        specify = _step("specify", in_action_sequence=True, sequence_index=0)
        retrospect = _step("retrospect", in_action_sequence=False, sequence_index=None)

        result = project_action_sequence([specify, retrospect])

        assert result == ["specify"]
        assert "retrospect" not in result

    def test_all_members_excluded_returns_empty_list_without_raising(self) -> None:
        retrospect = _step("retrospect", in_action_sequence=False)
        charter = _step("charter", in_action_sequence=False)

        result = project_action_sequence([retrospect, charter])

        assert result == []

    def test_empty_input_returns_empty_list(self) -> None:
        assert project_action_sequence([]) == []

    def test_duplicate_ids_raise_via_relocated_invariant(self) -> None:
        """WP01->WP02 contract: the projection re-asserts uniqueness itself.

        Two steps sharing an ``id`` cannot occur via the dict-keyed
        ``MissionStepRepository.resolve_all_for_mission_type`` result, but a
        direct caller of this pure function (the DRG extractor, WP04; the
        runtime seam, WP06) must still get the same guarantee
        ``MissionType`` applies to the raw field -- this is the
        ``validate_action_sequence`` re-assertion, not a reimplementation.
        """
        first = _step("specify", in_action_sequence=True, sequence_index=0)
        duplicate = _step("specify", in_action_sequence=True, sequence_index=1)

        with pytest.raises(ValueError, match="unique step IDs"):
            project_action_sequence([first, duplicate])


# ---------------------------------------------------------------------------
# project_template_set
# ---------------------------------------------------------------------------


class TestProjectTemplateSet:
    def test_keyed_by_artifact_key_not_step_id(self) -> None:
        specify_step = _step(
            "specify",
            template=MissionStepTemplateRef(
                artifact_key="spec", template_file="spec-template.md"
            ),
        )

        result = project_template_set([specify_step])

        assert result == {"spec": "spec-template.md"}
        assert "specify" not in (result or {})

    def test_drops_steps_without_a_template(self) -> None:
        specify_step = _step(
            "specify",
            template=MissionStepTemplateRef(
                artifact_key="spec", template_file="spec-template.md"
            ),
        )
        implement_step = _step("implement", template=None)

        result = project_template_set([specify_step, implement_step])

        assert result == {"spec": "spec-template.md"}

    def test_returns_none_when_no_step_has_a_template(self) -> None:
        implement_step = _step("implement", template=None)
        review_step = _step("review", template=None)

        assert project_template_set([implement_step, review_step]) is None

    def test_returns_none_on_empty_input(self) -> None:
        assert project_template_set([]) is None

    def test_multiple_templates_all_present(self) -> None:
        specify_step = _step(
            "specify",
            template=MissionStepTemplateRef(
                artifact_key="spec", template_file="spec-template.md"
            ),
        )
        plan_step = _step(
            "plan",
            template=MissionStepTemplateRef(
                artifact_key="plan", template_file="plan-template.md"
            ),
        )

        result = project_template_set([specify_step, plan_step])

        assert result == {"spec": "spec-template.md", "plan": "plan-template.md"}


# ---------------------------------------------------------------------------
# iter_template_refs (T003 — the sole traversal, promoted from the former
# private ``_step_template_ref``; project_template_set and the future
# FR-009 DRG extractor pass both build from this helper)
# ---------------------------------------------------------------------------


class TestIterTemplateRefs:
    def test_drops_steps_without_a_template(self) -> None:
        specify_step = _step(
            "specify",
            sequence_index=0,
            template=MissionStepTemplateRef(
                artifact_key="spec", template_file="spec-template.md"
            ),
        )
        implement_step = _step("implement", sequence_index=1, template=None)

        refs = iter_template_refs([specify_step, implement_step])

        assert [step.id for step, _ref in refs] == ["specify"]

    def test_ordered_by_sequence_index_not_input_order(self) -> None:
        plan_step = _step(
            "plan",
            sequence_index=1,
            template=MissionStepTemplateRef(
                artifact_key="plan", template_file="plan-template.md"
            ),
        )
        specify_step = _step(
            "specify",
            sequence_index=0,
            template=MissionStepTemplateRef(
                artifact_key="spec", template_file="spec-template.md"
            ),
        )

        # Input order is [plan, specify] -- reversed relative to sequence_index.
        refs = iter_template_refs([plan_step, specify_step])

        assert [step.id for step, _ref in refs] == ["specify", "plan"]

    def test_returns_step_and_ref_pairs(self) -> None:
        template = MissionStepTemplateRef(artifact_key="spec", template_file="spec-template.md")
        specify_step = _step("specify", sequence_index=0, template=template)

        refs = iter_template_refs([specify_step])

        assert refs == [(specify_step, template)]

    def test_empty_input_returns_empty_list(self) -> None:
        assert iter_template_refs([]) == []


# ---------------------------------------------------------------------------
# MissionTypeRepository cached accessor + injection (T007)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_mission_type_default_cache() -> Iterator[None]:
    """Prevent this module's ``default()`` exercises from leaking into other tests.

    Mirrors the ``builtin_mission_type_ids`` cache-vs-test-seam fixture in
    ``tests/charter_offering/missions/test_builtin_mission_type_ids.py`` (C-010).
    """
    MissionTypeRepository.default.cache_clear()
    yield
    MissionTypeRepository.default.cache_clear()


class TestMissionTypeRepositoryProjectionInjection:
    """The ``_load`` injection: transitional fallback + projection preference."""

    def test_unannotated_builtin_steps_fall_back_to_authored_yaml(
        self, tmp_path: Path
    ) -> None:
        """Today, software-dev's real builtin steps carry no sequence_index/
        in_action_sequence yet (pending WP03) -- the injected value must fall
        back to the still-authored YAML rather than overwrite it with an
        empty projection.

        ``template_set`` is no longer part of this fallback contract (S-C
        cutover, mission-step-creatability-01KXQA6R WP01) -- the field and
        its overlay are retired entirely, so this fixture only authors
        ``action_sequence``.
        """
        mission_types_dir = tmp_path / "mission_types"
        mission_types_dir.mkdir()
        (mission_types_dir / "software-dev.yaml").write_text(
            "schema_version: 1\n"
            "id: software-dev\n"
            "display_name: Software Development\n"
            "action_sequence:\n"
            "  - specify\n"
            "  - plan\n"
            "  - tasks\n"
            "  - implement\n"
            "  - review\n",
            encoding="utf-8",
        )

        repo = MissionTypeRepository(mission_types_dir)
        mt = repo.get("software-dev")

        assert mt is not None
        assert mt.action_sequence == ["specify", "plan", "tasks", "implement", "review"]

    def test_annotated_builtin_steps_override_stale_authored_yaml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Once a mission type's builtin steps carry sequence_index/
        in_action_sequence/template (WP03/WP05 future state), the *projected*
        value wins over a stale raw YAML value -- proving the injection is
        live, not a one-time copy.
        """
        builtin_steps_root = tmp_path / "mission-steps"
        _write_builtin_step_yaml(
            builtin_steps_root,
            "synth-type",
            "alpha",
            "id: alpha\n"
            "display_name: Alpha\n"
            "step_type: agent\n"
            "prompt_template: prompt.md\n"
            "in_action_sequence: true\n"
            "sequence_index: 1\n"
            "template:\n"
            "  artifact_key: alpha-artifact\n"
            "  template_file: alpha-template.md\n",
        )
        _write_builtin_step_yaml(
            builtin_steps_root,
            "synth-type",
            "beta",
            "id: beta\n"
            "display_name: Beta\n"
            "step_type: agent\n"
            "prompt_template: prompt.md\n"
            "in_action_sequence: true\n"
            "sequence_index: 0\n",
        )

        def _fake_step_repo_default(cls: type[MissionStepRepository]) -> MissionStepRepository:
            return cls(builtin_steps_root)

        monkeypatch.setattr(
            MissionStepRepository, "default", classmethod(_fake_step_repo_default)
        )

        mission_types_dir = tmp_path / "mission_types"
        mission_types_dir.mkdir()
        (mission_types_dir / "synth-type.yaml").write_text(
            "schema_version: 1\n"
            "id: synth-type\n"
            "display_name: Synth\n"
            "action_sequence:\n"
            "  - stale-a\n"
            "  - stale-b\n",
            encoding="utf-8",
        )

        repo = MissionTypeRepository(mission_types_dir)
        mt = repo.get("synth-type")

        assert mt is not None
        assert mt.action_sequence == ["beta", "alpha"]

        # template_set (S-C cutover, WP01): no longer a MissionType field or
        # overlay -- the alpha step's template ref still feeds the
        # consumption-boundary projection (proving the ref is genuinely
        # wired, not merely present-but-unused).
        steps = list(
            MissionStepRepository.default()
            .resolve_all_for_mission_type("synth-type", pack_context=None)
            .values()
        )
        assert project_template_set(steps) == {"alpha-artifact": "alpha-template.md"}


class TestDefaultMemoization:
    """``MissionTypeRepository.default()`` is memoized per NFR-007."""

    def test_repeated_calls_return_the_same_cached_instance(self) -> None:
        first = MissionTypeRepository.default()
        second = MissionTypeRepository.default()

        assert first is second

    def test_cache_clear_forces_a_rebuild(self, monkeypatch: pytest.MonkeyPatch) -> None:
        load_calls: list[int] = []
        original_load = MissionTypeRepository._load

        def _counting_load(directory: Path) -> dict[str, object]:
            load_calls.append(1)
            return original_load(directory)  # type: ignore[return-value]

        monkeypatch.setattr(MissionTypeRepository, "_load", staticmethod(_counting_load))
        MissionTypeRepository.default.cache_clear()

        first = MissionTypeRepository.default()
        second = MissionTypeRepository.default()
        assert first is second
        assert len(load_calls) == 1

        MissionTypeRepository.default.cache_clear()
        third = MissionTypeRepository.default()

        assert third is not first
        assert len(load_calls) == 2
